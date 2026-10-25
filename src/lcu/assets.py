"""Typed, bounded asset reads from paths indexed by an LCU data snapshot."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Literal

from .client import LcuResponse
from .static_data import LcuStaticDataService, _validate_asset_path

AssetKind = Literal["champion", "spell", "perk", "item", "skin"]
MAX_ASSET_BYTES = 8 * 1024 * 1024
MAX_ASSET_CACHE_BYTES = 64 * 1024 * 1024
MAX_ASSET_CACHE_FILES = 256
_MIME_SIGNATURES = {
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda data: (
        len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    ),
    "image/gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
}


@dataclass(frozen=True, slots=True)
class LcuAsset:
    content: bytes
    content_type: str


class LcuAssetService:
    """Fetch indexed LCU assets; the API caller owns any Data Dragon fallback."""

    def __init__(
        self,
        request_bytes: Callable[[str], Awaitable[LcuResponse]],
        static_data: LcuStaticDataService,
        cache_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        self._request_bytes = request_bytes
        self._static_data = static_data
        base_cache_dir = cache_dir or getattr(static_data, "cache_dir", None)
        self._asset_cache_dir = Path(base_cache_dir) / "assets" if base_cache_dir else None
        self._cache_lock = RLock()

    async def get_asset(
        self, kind: AssetKind, asset_id: int, *, variant: Literal["default", "splash"] = "default"
    ) -> LcuAsset | None:
        """Return ``None`` for unknown/missing assets so callers can use Data Dragon."""
        if kind not in ("champion", "spell", "perk", "item", "skin"):
            raise ValueError("Unknown LCU asset kind")
        if variant not in ("default", "splash") or (kind != "skin" and variant != "default"):
            raise ValueError("Unknown LCU asset variant")
        if isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id <= 0:
            return None
        cache_path = self._cache_path(kind, asset_id, variant)
        if cache_path is not None:
            cached = await asyncio.to_thread(self._read_cached_asset, cache_path)
            if cached is not None:
                return cached
        catalog_path = (
            self._static_data.asset_path(kind, asset_id)
            if variant == "default"
            else self._static_data.asset_path(kind, asset_id, variant=variant)
        )
        path = _validate_asset_path(catalog_path)
        if path is None:
            return None
        response = await self._request_bytes(path)
        if not response.ok:
            return None
        if (
            not isinstance(response.payload, bytes)
            or len(response.payload) > MAX_ASSET_BYTES
        ):
            return None
        content_type = response.content_type.partition(";")[0].strip().lower()
        signature_check = _MIME_SIGNATURES.get(content_type)
        if signature_check is None or not signature_check(response.payload):
            return None
        asset = LcuAsset(content=response.payload, content_type=content_type)
        if cache_path is not None:
            await asyncio.to_thread(self._save_cached_asset, cache_path, asset)
        return asset

    def _cache_path(self, kind: AssetKind, asset_id: int, variant: str) -> Path | None:
        if self._asset_cache_dir is None:
            return None
        status = getattr(self._static_data, "status", {})
        catalogues = status.get("catalogs") if isinstance(status, dict) else None
        catalogue_name = "champions" if kind in ("champion", "skin") else {
            "spell": "spells",
            "perk": "perks",
            "item": "items",
        }[kind]
        catalogue = catalogues.get(catalogue_name) if isinstance(catalogues, dict) else None
        version = catalogue.get("version") if isinstance(catalogue, dict) else None
        if not isinstance(version, str) or not version:
            version = status.get("cache_version") or status.get("game_version")
        if not isinstance(version, str) or not version:
            return None
        version_key = hashlib.sha256(version.encode("utf-8")).hexdigest()[:16]
        return self._asset_cache_dir / version_key / f"{kind}-{asset_id}-{variant}.asset"

    def _read_cached_asset(self, path: Path) -> LcuAsset | None:
        try:
            if (
                self._asset_cache_dir is None
                or self._asset_cache_dir.is_symlink()
                or path.parent.is_symlink()
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > MAX_ASSET_BYTES
            ):
                return None
            content = path.read_bytes()
        except OSError:
            return None
        content_type = _content_type_for_bytes(content)
        return LcuAsset(content, content_type) if content_type else None

    def _save_cached_asset(self, path: Path, asset: LcuAsset) -> None:
        if len(asset.content) > MAX_ASSET_BYTES or self._asset_cache_dir is None:
            return
        with self._cache_lock:
            try:
                self._asset_cache_dir.mkdir(parents=True, exist_ok=True)
                if self._asset_cache_dir.is_symlink():
                    return
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.parent.is_symlink() or path.is_symlink():
                    return
                self._evict_assets(path, len(asset.content))
                temporary_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        dir=path.parent, prefix=".asset-", suffix=".tmp", delete=False
                    ) as temporary_file:
                        temporary_path = Path(temporary_file.name)
                        temporary_file.write(asset.content)
                        temporary_file.flush()
                        os.fsync(temporary_file.fileno())
                    os.replace(temporary_path, path)
                finally:
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)
            except OSError:
                return

    def _evict_assets(self, protected_path: Path, incoming_size: int) -> None:
        entries = _cached_asset_files(self._asset_cache_dir)
        existing = next((entry for entry in entries if entry[0] == protected_path), None)
        total_size = sum(size for path, size, _modified in entries if path != protected_path)
        file_count = len(entries) - (1 if existing else 0)
        removable = sorted(
            (entry for entry in entries if entry[0] != protected_path),
            key=lambda entry: entry[2],
        )
        while removable and (
            total_size + incoming_size > MAX_ASSET_CACHE_BYTES
            or file_count + 1 > MAX_ASSET_CACHE_FILES
        ):
            path, size, _modified = removable.pop(0)
            try:
                path.unlink()
            except OSError:
                continue
            total_size -= size
            file_count -= 1
        if (
            total_size + incoming_size > MAX_ASSET_CACHE_BYTES
            or file_count + 1 > MAX_ASSET_CACHE_FILES
        ):
            return


def _content_type_for_bytes(content: bytes) -> str | None:
    for content_type, signature_check in _MIME_SIGNATURES.items():
        if signature_check(content):
            return content_type
    return None


def _cached_asset_files(root: Path | None) -> list[tuple[Path, int, float]]:
    if root is None or root.is_symlink() or not root.is_dir():
        return []
    entries = []
    try:
        version_dirs = list(root.iterdir())
    except OSError:
        return []
    for version_dir in version_dirs:
        if version_dir.is_symlink() or not version_dir.is_dir():
            continue
        try:
            files = list(version_dir.iterdir())
        except OSError:
            continue
        for path in files:
            if path.suffix != ".asset" or path.is_symlink() or not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append((path, stat.st_size, stat.st_mtime))
    return entries


__all__ = [
    "MAX_ASSET_BYTES",
    "MAX_ASSET_CACHE_BYTES",
    "MAX_ASSET_CACHE_FILES",
    "AssetKind",
    "LcuAsset",
    "LcuAssetService",
]
