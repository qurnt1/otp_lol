"""Versioned local snapshots of League Client static game data."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .client import LcuResponse

GAME_VERSION_PATH = "/lol-patch/v1/game-version"
CATALOG_ENDPOINTS = {
    "champions": "/lol-game-data/assets/v1/champion-summary.json",
    "spells": "/lol-game-data/assets/v1/summoner-spells.json",
    "perks": "/lol-game-data/assets/v1/perks.json",
    "items": "/lol-game-data/assets/v1/items.json",
    "maps": "/lol-game-data/assets/v1/maps.json",
    "queues": "/lol-game-data/assets/v1/queues.json",
}
_CACHE_SCHEMA = 2
_MANIFEST_FILENAME = "manifest.json"
_CATALOG_DIRECTORY = "catalogues"
_CATALOGUE_ID_FIELDS = {
    "champions": ("id", "championId", "key"),
    "spells": ("summonerSpellId", "spellId", "id", "key"),
    "perks": ("perkId", "id", "key"),
    "items": ("itemId", "id", "key"),
    "maps": ("mapId", "id", "key"),
    "queues": ("queueId", "id", "key"),
}
_CATALOGUE_CONTENT_FIELDS = {
    "champions": ("name", "alias"),
    "spells": ("name", "iconPath", "imagePath", "path"),
    "perks": ("name", "iconPath", "imagePath", "path"),
    "items": ("name", "localizedNames", "iconPath", "imagePath", "path"),
    "maps": ("name", "localizedNames"),
    "queues": ("name", "localizedNames"),
}
_WRAPPER_FIELDS = ("data", "items", "champions", "spells", "perks", "maps", "queues")


class LcuStaticDataService:
    """Load validated snapshots, parsing non-bootstrap catalogues only when used."""

    def __init__(
        self,
        request_json: Callable[[str], Awaitable[LcuResponse]],
        cache_dir: str | os.PathLike[str],
    ) -> None:
        self._request_json = request_json
        self.cache_dir = Path(cache_dir)
        self._refresh_lock = asyncio.Lock()
        self._catalogues: dict[str, Any] = {}
        self._catalogue_sources: dict[str, str] = {}
        self._catalogue_versions: dict[str, str] = {}
        self._catalogue_checked: set[str] = set()
        self._game_version: str | None = None
        self._cache_version: str | None = None
        self._connected = False
        self._snapshot_source: str | None = None
        self._asset_index: dict[tuple[str, int, str], str | None] = {}
        self._snapshot: dict[str, Any] | None = None
        self._cache_snapshots: list[dict[str, Any]] = []
        self._cache_checked = False

    def load_from_cache(self) -> bool:
        """Read the newest manifest and champion summary without loading items."""
        snapshots = self._discover_snapshots()
        self._cache_snapshots = snapshots
        self._cache_checked = True
        for _saved_at, snapshot in snapshots:
            champions = self._read_catalogue(snapshot, "champions")
            if champions is None:
                continue
            self._install_snapshot(snapshot, {"champions": champions}, "cache")
            self._cache_version = snapshot["game_version"]
            if self._game_version is None:
                self._game_version = self._cache_version
            return True
        return False

    async def refresh(self) -> bool:
        """Promote only a complete valid snapshot, leaving the current cache on failure."""
        async with self._refresh_lock:
            if not self._catalogue_sources and not self._cache_checked:
                self.load_from_cache()

            version_response = await self._request(GAME_VERSION_PATH)
            self._connected = version_response.status_code is not None
            if not version_response.ok:
                return False
            game_version = _normalize_game_version(version_response.payload)
            if game_version is None:
                return False
            self._game_version = game_version

            staging_dir: Path | None = None
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                staging_dir = Path(
                    tempfile.mkdtemp(prefix=".staging-", dir=self.cache_dir)
                )
                catalogue_dir = staging_dir / _CATALOG_DIRECTORY
                catalogue_dir.mkdir()
                champion_summary: Any | None = None

                for name, path in CATALOG_ENDPOINTS.items():
                    response = await self._request(path)
                    if not response.ok or not _is_catalogue(response.payload, name):
                        return False
                    self._write_json_file(
                        catalogue_dir / f"{name}.json", response.payload
                    )
                    if name == "champions":
                        champion_summary = response.payload
                    del response

                manifest = {
                    "schema": _CACHE_SCHEMA,
                    "game_version": game_version,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "catalogues": {
                        name: {"source": "lcu", "version": game_version}
                        for name in CATALOG_ENDPOINTS
                    },
                }
                self._write_json_file(staging_dir / _MANIFEST_FILENAME, manifest)
                snapshot_dir = self.cache_dir / _snapshot_directory(game_version)
                os.replace(staging_dir, snapshot_dir)
                staging_dir = None
            except (OSError, TypeError, ValueError, RecursionError):
                return False
            finally:
                if staging_dir is not None:
                    shutil.rmtree(staging_dir, ignore_errors=True)

            manifest["directory"] = snapshot_dir
            self._cache_version = game_version
            self._cache_snapshots = self._discover_snapshots()
            self._prune_snapshots()
            self._install_snapshot(manifest, {"champions": champion_summary}, "lcu")
            return True

    def load_champions(self) -> Any | None:
        return self._load_catalogue("champions")

    def load_items(self) -> Any | None:
        return self._load_catalogue("items")

    def load_perks(self) -> Any | None:
        return self._load_catalogue("perks")

    def load_summoner_spells(self) -> Any | None:
        return self._load_catalogue("spells")

    def load_maps(self) -> Any | None:
        return self._load_catalogue("maps")

    def load_queues(self) -> Any | None:
        return self._load_catalogue("queues")

    def asset_path(
        self, kind: str, asset_id: int, *, variant: str = "default"
    ) -> str | None:
        """Return a validated local path for one numeric ID, if indexed."""
        if kind not in {"champion", "spell", "perk", "item", "skin"}:
            return None
        if variant not in {"default", "splash"} or (kind != "skin" and variant != "default"):
            return None
        if isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id <= 0:
            return None
        self._ensure_loaded()
        key = (kind, asset_id, variant)
        if key not in self._asset_index:
            self._asset_index[key] = self._find_asset_path(kind, asset_id, variant)
        return self._asset_index[key]

    @property
    def status(self) -> dict[str, Any]:
        """A JSON-serializable view of connectivity and each catalogue source."""
        catalogue_status = {name: self._catalogue_status(name) for name in CATALOG_ENDPOINTS}
        sources = {
            entry["source"] for entry in catalogue_status.values() if entry["source"]
        }
        source = (
            next(iter(sources)) if len(sources) == 1 else "mixed" if sources else None
        )
        return {
            "connected": self._connected,
            "game_version": self._game_version,
            "cache_available": self._cache_version is not None,
            "cache_version": self._cache_version,
            "source": source,
            "catalogs": catalogue_status,
        }

    def _catalogue_status(self, name: str) -> dict[str, Any]:
        if name in self._catalogues:
            return {
                "available": True,
                "source": self._catalogue_sources.get(name),
                "version": self._catalogue_versions.get(name),
            }
        if name in self._catalogue_checked:
            return {"available": False, "source": None, "version": None}
        for _saved_at, snapshot in self._cache_snapshots:
            directory = snapshot["directory"]
            catalogue_dir = directory / _CATALOG_DIRECTORY
            catalogue_path = catalogue_dir / f"{name}.json"
            if (
                catalogue_dir.is_symlink()
                or catalogue_path.is_symlink()
                or not catalogue_path.is_file()
            ):
                continue
            source = (
                self._snapshot_source
                if self._snapshot is not None
                and directory == self._snapshot.get("directory")
                else "cache"
            )
            return {
                "available": True,
                "source": source,
                "version": snapshot["catalogues"][name]["version"],
            }
        return {"available": False, "source": None, "version": None}

    def _load_catalogue(self, name: str) -> Any | None:
        if name not in CATALOG_ENDPOINTS:
            return None
        self._ensure_loaded()
        if name not in self._catalogues:
            snapshot = self._snapshot
            catalogue = self._read_catalogue(snapshot, name) if snapshot else None
            if catalogue is None:
                catalogue = self._read_older_catalogue(name, snapshot)
            if catalogue is not None:
                self._catalogues[name] = catalogue
                if name not in self._catalogue_sources:
                    self._catalogue_sources[name] = self._snapshot_source or "cache"
                    self._catalogue_versions[name] = snapshot["catalogues"][name][
                        "version"
                    ]
            else:
                self._catalogue_sources.pop(name, None)
                self._catalogue_versions.pop(name, None)
            self._catalogue_checked.add(name)
        catalogue = self._catalogues.get(name)
        return copy.deepcopy(catalogue) if catalogue is not None else None

    def _read_older_catalogue(
        self, name: str, active_snapshot: dict[str, Any] | None
    ) -> Any | None:
        active_directory = active_snapshot.get("directory") if active_snapshot else None
        for _saved_at, snapshot in self._cache_snapshots:
            if snapshot.get("directory") == active_directory:
                continue
            catalogue = self._read_catalogue(snapshot, name)
            if catalogue is None:
                continue
            entry = snapshot["catalogues"][name]
            self._catalogue_sources[name] = "cache"
            self._catalogue_versions[name] = entry["version"]
            return catalogue
        return None

    def _ensure_loaded(self) -> None:
        if not self._catalogue_sources and not self._cache_checked:
            self.load_from_cache()

    async def _request(self, path: str) -> LcuResponse:
        return await self._request_json(path)

    def _install_snapshot(
        self, snapshot: dict[str, Any], loaded: dict[str, Any], source: str
    ) -> None:
        self._snapshot = snapshot
        self._snapshot_source = source
        if self._game_version is None or source == "lcu":
            self._game_version = snapshot["game_version"]
        self._catalogues = loaded
        self._catalogue_checked.clear()
        self._catalogue_sources = {name: source for name in loaded}
        self._catalogue_versions = {
            name: snapshot["catalogues"][name]["version"] for name in loaded
        }
        self._asset_index.clear()
        self._cache_checked = True

    def _write_json_file(self, path: Path, value: Any) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(
                value,
                file,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            file.flush()
            os.fsync(file.fileno())

    def _discover_snapshots(self) -> list[tuple[float, dict[str, Any]]]:
        try:
            entries = list(self.cache_dir.iterdir())
        except OSError:
            return []
        snapshots = []
        for entry in entries:
            if (
                entry.is_symlink()
                or not entry.is_dir()
                or not entry.name.startswith("snapshot-")
            ):
                continue
            manifest = _read_snapshot_manifest(entry / _MANIFEST_FILENAME)
            if manifest is None:
                continue
            saved_at, snapshot = manifest
            snapshot["directory"] = entry
            snapshots.append((saved_at, snapshot))
        return sorted(snapshots, key=lambda item: item[0], reverse=True)

    def _read_catalogue(self, snapshot: dict[str, Any], name: str) -> Any | None:
        if name not in snapshot["catalogues"]:
            return None
        catalogue_dir = snapshot["directory"] / _CATALOG_DIRECTORY
        catalogue_path = catalogue_dir / f"{name}.json"
        if (
            catalogue_dir.is_symlink()
            or catalogue_path.is_symlink()
            or not catalogue_path.is_file()
        ):
            return None
        try:
            with catalogue_path.open("r", encoding="utf-8") as file:
                catalogue = json.load(file, parse_constant=_reject_json_constant)
            return catalogue if _is_catalogue(catalogue, name) else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError, RecursionError):
            return None

    def _prune_snapshots(self) -> None:
        snapshots = self._discover_snapshots()
        newest_by_version: dict[str, Path] = {}
        for _saved_at, snapshot in snapshots:
            if not all(
                self._read_catalogue(snapshot, name) is not None
                for name in CATALOG_ENDPOINTS
            ):
                continue
            newest_by_version.setdefault(
                snapshot["game_version"], snapshot["directory"]
            )
        keep = set(list(newest_by_version.values())[:3])
        for _saved_at, snapshot in snapshots:
            directory = snapshot["directory"]
            if directory in keep or directory.is_symlink():
                continue
            if directory.parent == self.cache_dir:
                shutil.rmtree(directory, ignore_errors=True)
        self._cache_snapshots = self._discover_snapshots()

    def _find_asset_path(self, kind: str, asset_id: int, variant: str) -> str | None:
        catalogue_name, id_fields, path_fields = _ASSET_FIELDS[kind]
        if kind == "skin" and variant == "splash":
            path_fields = (
                "centeredSplashPath",
                "uncenteredSplashPath",
                "splashPath",
                "centeredSplashArtPath",
                "uncenteredSplashArtPath",
            )
        self._ensure_loaded()
        catalogue = self._catalogues.get(catalogue_name)
        if catalogue is None:
            catalogue = self._load_catalogue(catalogue_name)
        if catalogue is None:
            return None
        for record, mapping_key in _iter_records(catalogue):
            candidate_ids = [record.get(field) for field in id_fields]
            candidate_ids.append(mapping_key)
            if not any(
                _numeric_id(candidate) == asset_id for candidate in candidate_ids
            ):
                continue
            for field in path_fields:
                path = _path_value(record.get(field))
                validated = _validate_asset_path(path)
                if validated:
                    return validated
        return None


_ASSET_FIELDS = {
    "champion": (
        "champions",
        ("championId", "key", "id"),
        ("squarePortraitPath", "iconPath", "imagePath", "portraitPath"),
    ),
    "spell": (
        "spells",
        ("spellId", "summonerSpellId", "key", "id"),
        ("iconPath", "imagePath", "path"),
    ),
    "perk": ("perks", ("perkId", "id", "key"), ("iconPath", "imagePath", "path")),
    "item": ("items", ("itemId", "id", "key"), ("iconPath", "imagePath", "path")),
    "skin": (
        "champions",
        ("skinId", "skin_id", "id"),
        (
            "tilePath",
            "splashPath",
            "centeredSplashPath",
            "uncenteredSplashPath",
            "iconPath",
            "imagePath",
            "path",
        ),
    ),
}


def _normalize_game_version(payload: Any) -> str | None:
    if isinstance(payload, dict):
        payload = payload.get("gameVersion", payload.get("version"))
    if not isinstance(payload, str):
        return None
    version = payload.strip()
    if (
        not version
        or len(version) > 128
        or version in {".", ".."}
        or "/" in version
        or "\\" in version
        or any(ord(character) < 32 for character in version)
    ):
        return None
    return version


def _is_catalogue(payload: Any, name: str) -> bool:
    if name not in _CATALOGUE_ID_FIELDS:
        return False
    if isinstance(payload, list):
        return bool(payload) and all(
            _has_catalogue_record(record, name) for record in payload
        )
    if not isinstance(payload, dict) or not payload:
        return False
    for field in _WRAPPER_FIELDS:
        if field in payload and isinstance(payload[field], (list, dict)):
            return _is_catalogue(payload[field], name)
    return all(
        _has_catalogue_record(record, name, mapping_key)
        for mapping_key, record in payload.items()
    )


def _has_catalogue_record(
    record: Any, catalogue_name: str, mapping_key: Any = None
) -> bool:
    if not isinstance(record, dict):
        return False
    has_id = any(
        _numeric_id(record.get(field)) is not None
        for field in _CATALOGUE_ID_FIELDS[catalogue_name]
    ) or _numeric_id(mapping_key) is not None
    has_content = any(
        _has_catalogue_content(record.get(field))
        for field in _CATALOGUE_CONTENT_FIELDS[catalogue_name]
    )
    return has_id and has_content


def _has_catalogue_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(isinstance(entry, str) and entry.strip() for entry in value.values())
    return False


def _read_snapshot_manifest(path: Path) -> tuple[float, dict[str, Any]] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            snapshot = json.load(file, parse_constant=_reject_json_constant)
        catalogues = snapshot.get("catalogues") if isinstance(snapshot, dict) else None
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema") != _CACHE_SCHEMA
            or _normalize_game_version(snapshot.get("game_version"))
            != snapshot.get("game_version")
            or not isinstance(catalogues, dict)
            or set(catalogues) != set(CATALOG_ENDPOINTS)
        ):
            return None
        for entry in catalogues.values():
            if (
                not isinstance(entry, dict)
                or entry.get("source") != "lcu"
                or _normalize_game_version(entry.get("version")) != entry.get("version")
            ):
                return None
        saved_at = datetime.fromisoformat(
            str(snapshot.get("saved_at", "")).replace("Z", "+00:00")
        )
        if saved_at.tzinfo is None:
            return None
        return saved_at.timestamp(), snapshot
    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        OverflowError,
        RecursionError,
    ):
        return None


def _snapshot_directory(version: str) -> str:
    safe_slug = re.sub(r"[^A-Za-z0-9._-]+", "_", version).strip("._")[:48] or "version"
    digest = hashlib.sha256(version.encode("utf-8")).hexdigest()[:12]
    return f"snapshot-{safe_slug}-{digest}-{uuid.uuid4().hex}"


def _iter_records(value: Any, mapping_key: Any = None):
    if isinstance(value, list):
        for record in value:
            if isinstance(record, (dict, list)):
                yield from _iter_records(record)
    elif isinstance(value, dict):
        yield value, mapping_key
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                yield from _iter_records(child, key)


def _numeric_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        result = value
    elif (
        isinstance(value, str)
        and len(value) <= 20
        and value.isascii()
        and value.isdecimal()
    ):
        result = int(value)
    else:
        return None
    return result if result > 0 else None


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-standard JSON constant")


def _path_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("path", "full", "iconPath"):
            if isinstance(value.get(key), str):
                return value[key]
    return None


def _validate_asset_path(path: str | None) -> str | None:
    if not isinstance(path, str) or not path or len(path) > 2048:
        return None
    raw = path.strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme or parts.netloc or parts.query or parts.fragment or "\\" in raw:
        return None
    decoded = raw
    for _ in range(16):
        unquoted = unquote(decoded)
        if unquoted == decoded:
            break
        decoded = unquoted
    else:
        if re.search(r"%[0-9a-fA-F]{2}", decoded):
            return None
    if (
        "\\" in decoded
        or "?" in decoded
        or "#" in decoded
        or any(ord(character) < 32 for character in decoded)
        or "//" in decoded
        or any(segment in {".", ".."} for segment in decoded.split("/"))
    ):
        return None
    normalized = raw if raw.startswith("/") else f"/{raw}"
    decoded_normalized = decoded if decoded.startswith("/") else f"/{decoded}"
    prefix = "/lol-game-data/assets/"
    if not decoded_normalized.lower().startswith(prefix):
        return None
    return normalized


__all__ = ["CATALOG_ENDPOINTS", "GAME_VERSION_PATH", "LcuStaticDataService"]
