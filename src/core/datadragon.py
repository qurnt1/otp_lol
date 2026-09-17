"""
FILE NAME: src/core/datadragon.py
GLOBAL PURPOSE:
- Fetch, cache, and resolve champion and summoner metadata from Riot sources.
- Provide image-loading helpers for champion icons, spells, and skin previews.
- Offer resilient fallback behavior when network access or cache data is unavailable.

KEY FUNCTIONS:
- DataDragon: Own champion metadata, image caches, and lookup helpers.
- load: Populate champion metadata from Data Dragon, cache, or local fallback data.
- resolve_champion: Convert a champion name or identifier into a champion id.
- get_remote_image: Fetch and cache remote images used by the UI.

AUDIENCE & LOGIC:
Why:
This module exists so metadata retrieval, caching, and image access stay consistent across automation and UI code.
For whom:
Developers maintaining champion metadata, image caches, and Riot data integration.

DEPENDENCIES:
Used by:
- src.lcu.runtime, src.core.websocket, and the desktop frontend.
Uses:
- Standard library: io, json, logging, os, re, threading, typing, unicodedata
- Third-party libraries: Pillow, requests
- Local modules: src.config
"""

import glob
import json
import logging
import os
import re
import unicodedata
from collections import OrderedDict
from io import BytesIO
from threading import Event, Lock
from time import monotonic
from typing import Any, Dict, List, Optional

import requests
from PIL import Image, ImageDraw

from ..config import (
    DDRAGON_CACHE_FILE,
    ICONS_CACHE_DIR,
    SKINS_CACHE_DIR,
    SPELLS_CACHE_DIR,
    URL_CDRAGON_ASSET_PREFIX,
    URL_CDRAGON_CHAMPION_DETAIL,
    URL_DD_CHAMPION_DETAIL,
    URL_DD_CHAMPIONS,
    URL_DD_IMG_CHAMP,
    URL_DD_IMG_SPELL,
    URL_DD_SKIN_SPLASH,
    URL_DD_SUMMONERS,
    URL_DD_VERSIONS,
    URL_PERK_ICON_PREFIX,
    SUMMONER_SPELL_MAP,
    get_cache_dirs,
)
from ..integrations.communitydragon import CommunityDragonClient

NETWORK_COOLDOWN_SECONDS = 45
DETAIL_FAILURE_TTL_SECONDS = 45


class DataDragon:
    """Manage Riot metadata lookups, local caches, and image retrieval helpers."""

    def __init__(self):
        """Initialize metadata containers and in-memory image caches."""
        self.loaded: bool = False
        self.version: Optional[str] = None
        self.by_norm_name: Dict[str, int] = {}
        self.by_id: Dict[int, Dict[str, Any]] = {}
        self.name_by_id: Dict[int, str] = {}
        self.all_names: List[str] = []
        self.summoner_data: Dict[str, str] = {}
        self.summoner_loaded: bool = False
        self._image_cache: OrderedDict[str, Image.Image] = OrderedDict()
        self._image_cache_maxsize: int = 200
        self._champion_detail_cache: Dict[tuple[str, int], Dict[str, Any]] = {}
        self._cdragon_champion_detail_cache: Dict[tuple[str, int], Dict[str, Any]] = {}
        self._champion_detail_failures: Dict[tuple[str, int], float] = {}
        self._champion_detail_inflight: Dict[tuple[str, int], Event] = {}
        self._cdragon_detail_failures: Dict[tuple[str, int], float] = {}
        self._cdragon_detail_inflight: Dict[tuple[str, int], Event] = {}
        self._rune_perk_icon_path_by_id: Optional[Dict[int, str]] = None
        self._rune_perk_name_by_id: Optional[Dict[int, str]] = None
        self._cache_lock = Lock()
        self._network_lock = Lock()
        self._network_cooldown_until = 0.0

    def _request_get(self, url: str, **kwargs: Any) -> Any:
        """Skip requests during a network outage and share one cooldown across sources."""
        if not self._network_available():
            logging.debug("DataDragon: Skipping request during network cooldown")
            return None

        try:
            return requests.get(url, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as error:
            now = monotonic()
            with self._network_lock:
                repeated = now < self._network_cooldown_until
                self._network_cooldown_until = max(
                    self._network_cooldown_until,
                    now + NETWORK_COOLDOWN_SECONDS,
                )
            if repeated:
                logging.debug("DataDragon: Repeated network failure during cooldown")
            else:
                logging.warning(
                    "DataDragon: Network unavailable; retrying in %s seconds - %s",
                    NETWORK_COOLDOWN_SECONDS,
                    error,
                )
            return None

    def _network_available(self) -> bool:
        with self._network_lock:
            return monotonic() >= self._network_cooldown_until

    @staticmethod
    def _decode_image_response(response: Any) -> Optional[Image.Image]:
        """Decode a bounded image response and reject non-image payloads."""
        content = getattr(response, "content", b"")
        if len(content) > 8 * 1024 * 1024:
            return None
        headers = getattr(response, "headers", {})
        content_type = str(headers.get("Content-Type") or headers.get("content-type") or "")
        if content_type and not content_type.lower().startswith("image/"):
            return None
        image = Image.open(BytesIO(content))
        if image.format not in {"PNG", "JPEG", "WEBP", "GIF"}:
            return None
        image.load()
        return image

    def _cache_get(self, key: str) -> Optional[Image.Image]:
        with self._cache_lock:
            if key in self._image_cache:
                self._image_cache.move_to_end(key)
                return self._image_cache[key].copy()
        return None

    def _cache_put(self, key: str, image: Image.Image) -> None:
        with self._cache_lock:
            if key in self._image_cache:
                self._image_cache.move_to_end(key)
            self._image_cache[key] = image
            while len(self._image_cache) > self._image_cache_maxsize:
                self._image_cache.popitem(last=False)

    @staticmethod
    def _detail_cache_path(source: str, version: str, champion_id: int) -> str:
        safe_version = re.sub(r"[^A-Za-z0-9._-]+", "_", version)
        return os.path.join(
            SKINS_CACHE_DIR,
            "metadata",
            safe_version,
            source,
            f"{champion_id}.json",
        )

    def _load_detail_file(self, source: str, version: str, champion_id: int) -> Optional[Dict[str, Any]]:
        path = self._detail_cache_path(source, version, champion_id)
        try:
            with open(path, "r", encoding="utf-8") as file:
                detail = json.load(file)
            return detail if isinstance(detail, dict) else None
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            logging.debug("DataDragon: Ignoring cached %s detail for %s: %s", source, champion_id, error)
            return None

    def _save_detail_file(self, source: str, version: str, champion_id: int, detail: Dict[str, Any]) -> None:
        path = self._detail_cache_path(source, version, champion_id)
        temporary_path = f"{path}.tmp"
        try:
            with self._cache_lock:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(temporary_path, "w", encoding="utf-8") as file:
                    json.dump(detail, file)
                os.replace(temporary_path, path)
        except OSError as error:
            logging.debug("DataDragon: Could not persist %s detail for %s: %s", source, champion_id, error)

    @staticmethod
    def _read_cached_image(path: str) -> Optional[Image.Image]:
        try:
            with Image.open(path) as cached_image:
                cached_image.load()
                return cached_image.copy()
        except (OSError, ValueError, Image.DecompressionBombError):
            return None

    def _download_image(
        self,
        url: str,
        cache_key: str,
        cache_path: str,
        cache_dir: str,
    ) -> Optional[Image.Image]:
        try:
            response = self._request_get(url, stream=True, timeout=8)
            if response is None or response.status_code != 200:
                return None
            image = self._decode_image_response(response)
            if image is None:
                return None
            os.makedirs(os.path.dirname(cache_path) or cache_dir, exist_ok=True)
            with open(cache_path, "wb") as file:
                file.write(response.content)
            self._cache_put(cache_key, image)
            return image.copy()
        except Exception as error:
            logging.warning("DataDragon: Remote image error for %s - %s", url, error)
            return None

    @staticmethod
    def _safe_cache_component(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "offline"))

    def _versioned_image_path(self, cache_dir: str, filename: str) -> str:
        return os.path.join(cache_dir, self._safe_cache_component(self.version or "offline"), filename)

    def _read_older_cached_image(self, cache_dir: str, filename: str) -> Optional[Image.Image]:
        """Use an older image only when the current Data Dragon version is offline."""
        current_version = self._safe_cache_component(self.version or "offline")
        try:
            with os.scandir(cache_dir) as entries:
                version_dirs = [
                    (entry.path, entry.stat().st_mtime)
                    for entry in entries
                    if entry.is_dir(follow_symlinks=False) and entry.name != current_version
                ]
        except OSError:
            version_dirs = []
        version_dirs.sort(key=lambda item: item[1], reverse=True)
        candidates = [os.path.join(directory, filename) for directory, _ in version_dirs]
        candidates.append(os.path.join(cache_dir, filename))
        for path in candidates:
            image = self._read_cached_image(path)
            if image is not None:
                return image
        return None

    @staticmethod
    def _normalize(s: str) -> str:
        """Normalize champion names so user-friendly aliases map to stable lookup keys."""
        s = s.strip().lower()
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    def _load_from_cache(self, target_version: Optional[str] = None) -> bool:
        """Load cached champion metadata when the cache matches the requested version."""
        if target_version:
            version_path = f"{DDRAGON_CACHE_FILE}.{self._safe_cache_component(target_version)}.json"
            cache_paths = [version_path, DDRAGON_CACHE_FILE]
        else:
            versioned_paths = glob.glob(f"{DDRAGON_CACHE_FILE}.*.json")
            versioned_paths.sort(key=os.path.getmtime, reverse=True)
            cache_paths = [*versioned_paths, DDRAGON_CACHE_FILE]

        for cache_path in cache_paths:
            try:
                if not os.path.exists(cache_path):
                    continue
                with open(cache_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                cached_version = payload.get("version")
                if target_version and cached_version != target_version:
                    continue
                self.version = cached_version
                self.by_norm_name = {k: int(v) for k, v in payload.get("by_norm_name", {}).items()}
                self.by_id = {int(k): v for k, v in payload.get("by_id", {}).items()}
                self.name_by_id = {int(k): v for k, v in payload.get("name_by_id", {}).items()}
                self.all_names = sorted(list(self.name_by_id.values()))
                self.loaded = True
                return True
            except Exception as e:
                logging.warning("DataDragon: Cache error for %s - %s", cache_path, e)
        return False

    def _save_cache(self) -> None:
        """Persist the current champion metadata cache to disk."""
        if not self.version:
            return
        cache_path = f"{DDRAGON_CACHE_FILE}.{self._safe_cache_component(self.version)}.json"
        try:
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": self.version,
                        "by_norm_name": self.by_norm_name,
                        "by_id": self.by_id,
                        "name_by_id": self.name_by_id,
                    },
                    f,
                )
        except Exception as e:
            logging.warning("DataDragon: Cache save error - %s", e)

    def load_cached(self) -> bool:
        """Load local champion metadata without performing a network request."""
        if self.loaded:
            return True
        get_cache_dirs()
        loaded = self._load_from_cache()
        if loaded:
            logging.info("DataDragon: Loaded local cache (version %s)", self.version)
        return loaded

    def load(self) -> None:
        """Load champion metadata, preferring fresh Data Dragon data, then cache, then fallback."""
        if self.loaded:
            return

        # Cache directories are prepared up front because both metadata and image
        # fetches rely on them later in the session.
        self.load_cached()
        if self.loaded:
            return
        online_version = self._fetch_latest_version()
        if self._load_from_cache(target_version=online_version):
            logging.info("DataDragon: Loaded from cache (version %s)", self.version)
            return

        if not online_version:
            logging.warning("DataDragon: No online version and invalid cache, using fallback data")
            self._load_fallback_data()
            return

        self._load_remote_version(online_version)

    def refresh(self) -> None:
        """Refresh an already cached catalog after the first UI paint."""
        if not self.loaded:
            self.load()
            return
        online_version = self._fetch_latest_version()
        if not online_version or online_version == self.version:
            return
        if self._load_from_cache(target_version=online_version):
            logging.info("DataDragon: Refreshed from versioned cache (version %s)", self.version)
            return
        self._load_remote_version(online_version)

    def _load_remote_version(self, online_version: str) -> None:
        """Fetch and install one catalog version while preserving a usable cache on failure."""
        try:
            url_champs = URL_DD_CHAMPIONS.format(version=online_version)
            response = self._request_get(url_champs, timeout=10)
            if response is None:
                if not self.loaded:
                    self._load_fallback_data()
                return
            response.raise_for_status()
            champions_data = response.json().get("data", {})

            by_id: Dict[int, Dict[str, Any]] = {}
            name_by_id: Dict[int, str] = {}
            by_norm_name: Dict[str, int] = {}

            for champ_slug, info in champions_data.items():
                champ_name = info.get("name") or champ_slug
                champion_id = int(info.get("key"))
                by_id[champion_id] = info
                name_by_id[champion_id] = champ_name
                by_norm_name[self._normalize(champ_name)] = champion_id
                by_norm_name[self._normalize(info.get("id", champ_slug))] = champion_id

            self.by_id = by_id
            self.name_by_id = name_by_id
            self.by_norm_name = by_norm_name
            self._add_champion_aliases()
            previous_version = self.version
            self.version = online_version
            if previous_version != online_version:
                with self._cache_lock:
                    self._champion_detail_cache.clear()
                    self._cdragon_champion_detail_cache.clear()
                    self._champion_detail_failures.clear()
                    self._cdragon_detail_failures.clear()
                    self.summoner_data.clear()
                    self.summoner_loaded = False
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True
            self._save_cache()
            logging.info(
                "DataDragon: Loaded from API (version %s, %s champions)", online_version, len(self.all_names)
            )
        except requests.RequestException as e:
            logging.error("DataDragon: Network error while loading - %s", e)
            if not self.loaded:
                self._load_fallback_data()
        except Exception as e:
            logging.error("DataDragon: Unexpected error - %s", e)
            if not self.loaded:
                self._load_fallback_data()

    def _fetch_latest_version(self) -> Optional[str]:
        """Return the latest online Data Dragon version when the network is reachable."""
        try:
            response = self._request_get(URL_DD_VERSIONS, timeout=5)
            if response is None:
                return None
            response.raise_for_status()
            versions = response.json()
            if versions:
                return versions[0]
        except requests.RequestException as e:
            logging.warning("DataDragon: Unable to fetch online version - %s", e)
        except Exception as e:
            logging.warning("DataDragon: Version parsing error - %s", e)
        return None

    def _add_champion_aliases(self) -> None:
        """Register manual aliases for champions whose public names differ from internal slugs."""
        aliases = {
            "wukong": "monkeyking",
            "renata": "renataglasc",
        }
        for alias_name, internal_name in aliases.items():
            norm_alias = self._normalize(alias_name)
            norm_internal = self._normalize(internal_name)
            if norm_internal in self.by_norm_name:
                self.by_norm_name[norm_alias] = self.by_norm_name[norm_internal]

    def _load_fallback_data(self) -> None:
        """Load a minimal offline champion list when full metadata cannot be fetched."""
        logging.info("DataDragon: Loading fallback data")
        basic_champions = {
            "Garen": 86,
            "Teemo": 17,
            "Ashe": 22,
            "Lux": 99,
            "Jinx": 222,
            "Ahri": 103,
        }
        for name, champion_id in basic_champions.items():
            norm_name = self._normalize(name)
            self.by_norm_name[norm_name] = champion_id
            self.by_id[champion_id] = {"name": name, "key": str(champion_id)}
            self.name_by_id[champion_id] = name

        self.version = "offline"
        self.all_names = sorted(list(self.name_by_id.values()))
        self.loaded = True

    def resolve_champion(self, name_or_id: Any) -> Optional[int]:
        """Resolve a champion name or identifier to a numeric champion id."""
        self.load()
        if name_or_id is None:
            return None
        try:
            return int(name_or_id)
        except (ValueError, TypeError):
            pass
        normalized_name = self._normalize(str(name_or_id))
        return self.by_norm_name.get(normalized_name)

    def id_to_name(self, champion_id: int) -> Optional[str]:
        """Return the public champion name for a numeric champion id."""
        self.load()
        return self.name_by_id.get(champion_id)

    def get_champion_tags(self, name_or_id: Any) -> List[str]:
        """Return champion role tags from the loaded champion metadata."""
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return []
        champ_data = self.by_id.get(champion_id) or {}
        tags = champ_data.get("tags", [])
        return [str(tag) for tag in tags if str(tag).strip()]

    def get_champion_icon(self, name_or_id: Any) -> Optional[Image.Image]:
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return None

        cache_key = f"dd:{self.version}:champion:{champion_id}"
        champ_data = self.by_id.get(champion_id)
        if not champ_data:
            return None

        image_filename = champ_data.get("image", {}).get("full")
        if not image_filename:
            return None

        local_path = self._versioned_image_path(ICONS_CACHE_DIR, image_filename)
        url = URL_DD_IMG_CHAMP.format(version=self.version, filename=image_filename)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        cached_image = self._read_cached_image(local_path) if os.path.exists(local_path) else None
        if cached_image is not None:
            self._cache_put(cache_key, cached_image)
            return cached_image
        image = self._download_image(url, cache_key, local_path, ICONS_CACHE_DIR)
        if image is not None or self._network_available():
            return image
        return self._read_older_cached_image(ICONS_CACHE_DIR, image_filename)

    def get_champion_splash(self, name_or_id: Any) -> Optional[Image.Image]:
        """Return the base splash art for a champion, using the shared image cache."""
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return None

        champion_slug = (self.by_id.get(champion_id) or {}).get("id")
        if not champion_slug:
            cached_detail = self._get_cached_champion_detail(champion_id)
            champion_slug = (cached_detail or {}).get("id")
        if not champion_slug:
            return None

        return self.get_remote_image(
            URL_DD_SKIN_SPLASH.format(champion=champion_slug, skin_num=0),
            cache_key=f"champion_splash_{champion_id}",
        )

    def get_skin_preview(self, champion_id: Any, skin_num: Any) -> Optional[Image.Image]:
        """Fetch a known skin splash directly without loading the skin catalogue."""
        try:
            normalized_champion_id = int(champion_id)
            normalized_skin_num = int(skin_num)
        except (TypeError, ValueError):
            return None
        if normalized_champion_id <= 0 or normalized_skin_num < 0:
            return None
        champion_slug = str((self.by_id.get(normalized_champion_id) or {}).get("id") or "").strip()
        if not champion_slug:
            return None
        return self.get_remote_image(
            URL_DD_SKIN_SPLASH.format(champion=champion_slug, skin_num=normalized_skin_num),
            cache_key=f"skin_preview_{normalized_champion_id}_{normalized_skin_num}",
        )

    def load_summoners(self) -> None:
        if self.summoner_loaded:
            return
        if not self.version:
            self.load()

        url = URL_DD_SUMMONERS.format(version=self.version)
        try:
            response = self._request_get(url, timeout=5)
            if response is None:
                return
            if response.status_code == 200:
                data = response.json().get("data", {})
                supported_spells = {spell_id: name for name, spell_id in SUMMONER_SPELL_MAP.items() if spell_id}
                for info in data.values():
                    try:
                        spell_id = int(info.get("key"))
                    except (AttributeError, TypeError, ValueError):
                        continue
                    name = supported_spells.get(spell_id)
                    image_full = info.get("image", {}).get("full")
                    if name and image_full:
                        self.summoner_data[name] = image_full
                self.summoner_loaded = True
        except Exception as e:
            logging.warning("DataDragon: Summoner data loading error - %s", e)

    def get_summoner_icon(self, spell_name: str) -> Optional[Image.Image]:
        if spell_name in {"(None)", "(Aucun)"} or not spell_name:
            return None

        cache_key = f"dd:{self.version}:spell:{spell_name}"
        self.load_summoners()
        image_filename = self.summoner_data.get(spell_name)
        if not image_filename:
            return None

        local_path = self._versioned_image_path(SPELLS_CACHE_DIR, image_filename)
        url = URL_DD_IMG_SPELL.format(version=self.version, filename=image_filename)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        cached_image = self._read_cached_image(local_path) if os.path.exists(local_path) else None
        if cached_image is not None:
            self._cache_put(cache_key, cached_image)
            return cached_image
        image = self._download_image(url, cache_key, local_path, SPELLS_CACHE_DIR)
        if image is not None or self._network_available():
            return image
        return self._read_older_cached_image(SPELLS_CACHE_DIR, image_filename)

    def get_champion_detail(self, name_or_id: Any) -> Optional[Dict[str, Any]]:
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return None

        cached = self._get_cached_champion_detail(champion_id)
        if cached:
            return cached

        version = self.version
        champion_slug = (self.by_id.get(champion_id) or {}).get("id")
        if not champion_slug or not version:
            return None
        key = (version, champion_id)
        with self._cache_lock:
            if self._champion_detail_failures.get(key, 0) > monotonic():
                return None
            event = self._champion_detail_inflight.get(key)
            is_owner = event is None
            if is_owner:
                event = Event()
                self._champion_detail_inflight[key] = event

        if not is_owner:
            event.wait()
            return self._get_cached_champion_detail(champion_id)

        detail: Optional[Dict[str, Any]] = None
        try:
            url = URL_DD_CHAMPION_DETAIL.format(version=version, champion=champion_slug)
            response = self._request_get(url, timeout=8)
            if response is not None:
                response.raise_for_status()
                payload = response.json().get("data", {})
                downloaded_detail = payload.get(champion_slug)
                if isinstance(downloaded_detail, dict):
                    detail = downloaded_detail
                else:
                    logging.warning("DataDragon: Champion detail missing for %s", champion_slug)
        except requests.RequestException as e:
            logging.warning("DataDragon: Champion detail download error - %s", e)
        except Exception as e:
            logging.warning("DataDragon: Champion detail parsing error - %s", e)
        finally:
            with self._cache_lock:
                if detail is not None:
                    self._champion_detail_cache[key] = detail
                    self._champion_detail_failures.pop(key, None)
                else:
                    self._champion_detail_failures[key] = monotonic() + DETAIL_FAILURE_TTL_SECONDS
                self._champion_detail_inflight.pop(key, None)
                event.set()

        if detail is not None:
            self._save_detail_file("datadragon", version, champion_id, detail)
            return dict(detail)
        return None

    def _get_cached_champion_detail(self, champion_id: int) -> Optional[Dict[str, Any]]:
        version = self.version
        if not version:
            return None
        key = (version, champion_id)
        with self._cache_lock:
            detail = self._champion_detail_cache.get(key)
        if detail is None:
            detail = self._load_detail_file("datadragon", version, champion_id)
            if detail is not None:
                with self._cache_lock:
                    self._champion_detail_cache[key] = detail
        return dict(detail) if detail is not None else None

    @staticmethod
    def cdragon_url_from_asset_path(asset_path: str) -> Optional[str]:
        raw_path = str(asset_path or "").strip()
        if not raw_path:
            return None
        normalized = raw_path.replace("\\", "/")
        prefix = "/lol-game-data/assets/"
        lowered = normalized.lower()
        if "://" in lowered or lowered.startswith("//") or "?" in lowered or "#" in lowered:
            return None
        if ".." in lowered.split("/"):
            return None
        if lowered.startswith(prefix):
            relative = lowered[len(prefix):]
        else:
            relative = lowered.lstrip("/")
            if not relative.startswith("assets/"):
                return None
        if not relative:
            return None
        return f"{URL_CDRAGON_ASSET_PREFIX}{relative}"

    def get_cdragon_champion_detail(self, name_or_id: Any) -> Optional[Dict[str, Any]]:
        champion_id = self.resolve_champion(name_or_id)
        version = self.version
        if not champion_id or not version:
            return None

        cached = self._get_cached_cdragon_champion_detail(champion_id)
        if cached is not None:
            return cached

        key = (version, champion_id)
        with self._cache_lock:
            if self._cdragon_detail_failures.get(key, 0) > monotonic():
                return None
            event = self._cdragon_detail_inflight.get(key)
            is_owner = event is None
            if is_owner:
                event = Event()
                self._cdragon_detail_inflight[key] = event

        if not is_owner:
            event.wait()
            return self._get_cached_cdragon_champion_detail(champion_id)

        url = URL_CDRAGON_CHAMPION_DETAIL.format(champion_id=champion_id)
        detail: Optional[Dict[str, Any]] = None
        try:
            response = self._request_get(url, timeout=8)
            if response is not None:
                response.raise_for_status()
                downloaded_detail = response.json()
                if isinstance(downloaded_detail, dict):
                    detail = downloaded_detail
        except requests.RequestException as e:
            logging.warning("DataDragon: CDragon champion detail download error - %s", e)
        except Exception as e:
            logging.warning("DataDragon: CDragon champion detail parsing error - %s", e)
        finally:
            with self._cache_lock:
                if detail is not None:
                    self._cdragon_champion_detail_cache[key] = detail
                    self._cdragon_detail_failures.pop(key, None)
                else:
                    self._cdragon_detail_failures[key] = monotonic() + DETAIL_FAILURE_TTL_SECONDS
                self._cdragon_detail_inflight.pop(key, None)
                event.set()

        if detail is not None:
            self._save_detail_file("communitydragon", version, champion_id, detail)
            return dict(detail)
        return None

    def _get_cached_cdragon_champion_detail(self, champion_id: int) -> Optional[Dict[str, Any]]:
        version = self.version
        if not version:
            return None
        key = (version, champion_id)
        with self._cache_lock:
            detail = self._cdragon_champion_detail_cache.get(key)
        if detail is None:
            detail = self._load_detail_file("communitydragon", version, champion_id)
            if detail is not None:
                with self._cache_lock:
                    self._cdragon_champion_detail_cache[key] = detail
        return dict(detail) if detail is not None else None

    def get_skin_catalog(self, name_or_id: Any) -> List[Dict[str, Any]]:
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return []

        detail = self.get_champion_detail(champion_id)
        if not detail:
            return []
        cdragon_detail = self.get_cdragon_champion_detail(champion_id) or {}

        return self._build_skin_catalog(champion_id, name_or_id, detail, cdragon_detail)

    def get_cached_skin_catalog(self, name_or_id: Any) -> List[Dict[str, Any]]:
        """Build skin metadata from memory/disk only; never initiate a network request."""
        try:
            champion_id = int(name_or_id)
        except (TypeError, ValueError):
            champion_id = self.by_norm_name.get(self._normalize(str(name_or_id)))
        if not champion_id:
            return []
        detail = self._get_cached_champion_detail(champion_id)
        if not detail:
            return []
        cdragon_detail = self._get_cached_cdragon_champion_detail(champion_id) or {}
        return self._build_skin_catalog(champion_id, name_or_id, detail, cdragon_detail)

    def _build_skin_catalog(
        self,
        champion_id: int,
        name_or_id: Any,
        detail: Dict[str, Any],
        cdragon_detail: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        champion_slug = detail.get("id") or self.by_id.get(champion_id, {}).get("id")
        champion_name = detail.get("name") or self.id_to_name(champion_id) or str(name_or_id)
        skins = detail.get("skins", [])
        cdragon_skins = cdragon_detail.get("skins", []) if isinstance(cdragon_detail, dict) else []
        cdragon_by_skin_id: Dict[int, Dict[str, Any]] = {}
        cdragon_by_num: Dict[int, Dict[str, Any]] = {}
        cdragon_by_name: Dict[str, Dict[str, Any]] = {}
        for item in cdragon_skins if isinstance(cdragon_skins, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                cdragon_skin_id = int(item.get("id") or item.get("skinId") or 0)
            except (TypeError, ValueError):
                cdragon_skin_id = 0
            try:
                cdragon_skin_num = int(item.get("num") or 0)
            except (TypeError, ValueError):
                cdragon_skin_num = 0
            if cdragon_skin_id:
                cdragon_by_skin_id[cdragon_skin_id] = item
            if cdragon_skin_num >= 0:
                cdragon_by_num[cdragon_skin_num] = item
            normalized_name = self._normalize(str(item.get("name") or ""))
            if normalized_name:
                cdragon_by_name[normalized_name] = item
        catalog: List[Dict[str, Any]] = []
        for skin in skins:
            if skin.get("parentSkin") not in {None, "", 0}:
                continue
            try:
                skin_id = int(skin.get("id") or 0)
            except (TypeError, ValueError):
                skin_id = 0
            try:
                skin_num = int(skin.get("num") or 0)
            except (TypeError, ValueError):
                skin_num = 0
            name = str(skin.get("name") or "")
            cdragon_skin = (
                cdragon_by_skin_id.get(skin_id)
                or cdragon_by_num.get(skin_num)
                or cdragon_by_name.get(self._normalize(name))
                or {}
            )
            entry = {
                "champion_id": champion_id,
                "champion_name": champion_name,
                "champion_slug": champion_slug,
                "skin_id": skin_id,
                "skin_num": skin_num,
                "skin_name": name,
                "splash_url": URL_DD_SKIN_SPLASH.format(champion=champion_slug, skin_num=skin_num),
                "tile_url": self.cdragon_url_from_asset_path(cdragon_skin.get("tilePath", "")),
                "centered_splash_url": self.cdragon_url_from_asset_path(cdragon_skin.get("splashPath", "")),
                "uncentered_splash_url": self.cdragon_url_from_asset_path(
                    cdragon_skin.get("uncenteredSplashPath", "")
                ),
            }
            catalog.append(entry)
        return catalog

    def resolve_skin_data(
        self,
        name_or_id: Any,
        *,
        skin_name: Optional[str] = None,
        skin_id: Optional[Any] = None,
        skin_num: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        catalog = self.get_skin_catalog(name_or_id)
        if not catalog:
            return None

        if skin_id not in {None, ""}:
            try:
                target_skin_id = int(skin_id)
            except (TypeError, ValueError):
                target_skin_id = 0
            if target_skin_id:
                for entry in catalog:
                    if entry["skin_id"] == target_skin_id:
                        return dict(entry)

        if skin_num not in {None, ""}:
            try:
                target_skin_num = int(skin_num)
            except (TypeError, ValueError):
                target_skin_num = 0
            if target_skin_num >= 0:
                for entry in catalog:
                    if entry["skin_num"] == target_skin_num:
                        return dict(entry)

        normalized_name = self._normalize(str(skin_name or ""))
        if normalized_name:
            for entry in catalog:
                if self._normalize(entry["skin_name"]) == normalized_name:
                    return dict(entry)
        return None

    def get_skin_preview_url(
        self,
        champion_name_or_id: Any,
        *,
        skin_name: Optional[str] = None,
        skin_id: Optional[Any] = None,
        skin_num: Optional[Any] = None,
    ) -> Optional[str]:
        skin_data = self.resolve_skin_data(
            champion_name_or_id,
            skin_name=skin_name,
            skin_id=skin_id,
            skin_num=skin_num,
        )
        if not skin_data:
            return None
        return (
            skin_data.get("tile_url")
            or skin_data.get("centered_splash_url")
            or skin_data.get("uncentered_splash_url")
            or skin_data.get("splash_url")
        )

    @staticmethod
    def _communitydragon_asset_url(asset_path: str) -> Optional[str]:
        return CommunityDragonClient.asset_url(asset_path)

    def _get_communitydragon_image(self, asset_path: str, *, cache_prefix: str) -> Optional[Image.Image]:
        url = self._communitydragon_asset_url(asset_path)
        if not url:
            return None
        cache_key = f"{cache_prefix}_{url.rsplit('/', 1)[-1].replace('.png', '')}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            response = self._request_get(url, timeout=8)
            if response is None or response.status_code != 200:
                return None
            image = self._decode_image_response(response)
            if image is None:
                return None
            self._cache_put(cache_key, image)
            return image
        except Exception as error:
            logging.warning("DataDragon: CommunityDragon image error for %s - %s", url, error)
            return None

    def get_rune_perk_icon(self, perk_icon_path: str) -> Optional[Image.Image]:
        """Download a rune perk icon from CommunityDragon."""
        return self._get_communitydragon_image(perk_icon_path, cache_prefix="rune_perk")

    def get_rune_style_icon(self, style_icon_path: str) -> Optional[Image.Image]:
        """Download a rune style (tree) icon from CommunityDragon."""
        return self._get_communitydragon_image(style_icon_path, cache_prefix="rune_style")

    def _fetch_rune_perk_icon_index(self) -> Dict[int, str]:
        if self._rune_perk_icon_path_by_id is not None:
            return self._rune_perk_icon_path_by_id

        url = f"{URL_PERK_ICON_PREFIX}/v1/perks.json"
        try:
            response = self._request_get(url, timeout=8)
            if response is None:
                return {}
            if response.status_code != 200:
                self._rune_perk_icon_path_by_id = {}
                self._rune_perk_name_by_id = {}
                return self._rune_perk_icon_path_by_id
            payload = response.json()
        except Exception as e:
            logging.warning("DataDragon: CommunityDragon rune perk index error: %s", e)
            self._rune_perk_icon_path_by_id = {}
            self._rune_perk_name_by_id = {}
            return self._rune_perk_icon_path_by_id

        if not isinstance(payload, list):
            self._rune_perk_icon_path_by_id = {}
            self._rune_perk_name_by_id = {}
            return self._rune_perk_icon_path_by_id

        index: Dict[int, str] = {}
        names: Dict[int, str] = {}
        for perk in payload:
            if not isinstance(perk, dict):
                continue
            try:
                perk_id = int(perk.get("id") or 0)
            except (TypeError, ValueError):
                continue
            icon_path = str(perk.get("iconPath") or "")
            if perk_id > 0 and icon_path:
                index[perk_id] = icon_path
                names[perk_id] = str(perk.get("name") or "")

        self._rune_perk_icon_path_by_id = index
        self._rune_perk_name_by_id = names
        return self._rune_perk_icon_path_by_id

    def get_rune_perk_icon_path(self, perk_id: Any) -> str:
        """Resolve a rune perk id to its CommunityDragon LCU asset path."""
        try:
            normalized_perk_id = int(perk_id or 0)
        except (TypeError, ValueError):
            normalized_perk_id = 0
        if normalized_perk_id <= 0:
            return ""

        return self._fetch_rune_perk_icon_index().get(normalized_perk_id, "")

    def get_rune_perk_name(self, perk_id: Any) -> str:
        """Resolve a rune perk id to its CommunityDragon display name."""
        try:
            normalized_perk_id = int(perk_id or 0)
        except (TypeError, ValueError):
            normalized_perk_id = 0
        if normalized_perk_id <= 0:
            return ""

        self._fetch_rune_perk_icon_index()
        return (self._rune_perk_name_by_id or {}).get(normalized_perk_id, "")

    @staticmethod
    def _normalize_rune_icon_size(size: Any) -> tuple[int, int]:
        if isinstance(size, tuple) and len(size) == 2:
            try:
                width = int(size[0] or 0)
                height = int(size[1] or 0)
                if width > 0 and height > 0:
                    return width, height
            except (TypeError, ValueError):
                pass
        try:
            square_size = int(size or 32)
        except (TypeError, ValueError):
            square_size = 32
        square_size = max(square_size, 1)
        return square_size, square_size

    def compose_rune_button_icon(self, keystone_icon_path: str, sub_style_icon_path: str = "", size: Any = 32) -> Optional[Image.Image]:
        """Return a composite image with the keystone as the main icon and the sub-style overlaid smaller."""
        target_width, target_height = self._normalize_rune_icon_size(size)
        keystone_img = self.get_rune_perk_icon(keystone_icon_path)
        if not keystone_img:
            return None
        main_size = min(target_width, target_height)
        keystone_img = keystone_img.resize((main_size, main_size), Image.LANCZOS).convert("RGBA")
        composite = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        composite.paste(keystone_img, (0, (target_height - main_size) // 2), keystone_img)
        if not sub_style_icon_path:
            return composite
        sub_img = self.get_rune_style_icon(sub_style_icon_path)
        if not sub_img:
            return composite
        overlay_size = max(min(target_height // 2, target_width - main_size), 14)
        overlay_size = min(overlay_size, target_width, target_height)
        sub_img = sub_img.resize((overlay_size, overlay_size), Image.LANCZOS).convert("RGBA")
        position = (
            max(main_size - overlay_size // 3, target_width - overlay_size),
            (target_height - overlay_size) // 2,
        )
        if position[0] + overlay_size > target_width:
            position = (target_width - overlay_size, position[1])
        backing = Image.new("RGBA", composite.size, (0, 0, 0, 0))
        circle_box = (
            position[0] - 1,
            position[1] - 1,
            position[0] + overlay_size + 1,
            position[1] + overlay_size + 1,
        )
        draw = ImageDraw.Draw(backing)
        draw.ellipse(circle_box, fill=(6, 9, 14, 210), outline=(124, 137, 153, 140))
        composite.alpha_composite(backing)
        composite.paste(sub_img, position, sub_img)
        return composite

    def get_remote_image(self, url: str, *, cache_key: str) -> Optional[Image.Image]:
        cache_filename = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in cache_key)
        cache_filename = f"{cache_filename}.img"
        cache_path = self._versioned_image_path(SKINS_CACHE_DIR, cache_filename)
        cache_key = f"dd:{self.version}:{cache_key}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        cached_image = self._read_cached_image(cache_path) if os.path.exists(cache_path) else None
        if cached_image is not None:
            self._cache_put(cache_key, cached_image)
            return cached_image

        image = self._download_image(url, cache_key, cache_path, SKINS_CACHE_DIR)
        if image is not None or self._network_available():
            return image
        return self._read_older_cached_image(SKINS_CACHE_DIR, cache_filename)
