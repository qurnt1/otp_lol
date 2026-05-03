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
- launcher.py, src.core.websocket, and multiple UI modules.
Uses:
- Standard library: io, json, logging, os, re, threading, typing, unicodedata
- Third-party libraries: Pillow, requests
- Local modules: src.config
"""

import json
import logging
import os
import re
import unicodedata
from io import BytesIO
from threading import Lock
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
    URL_DD_CHAMPIONS,
    URL_DD_CHAMPION_DETAIL,
    URL_DD_IMG_CHAMP,
    URL_DD_IMG_SPELL,
    URL_DD_SKIN_SPLASH,
    URL_DD_SPLASH,
    URL_DD_SUMMONERS,
    URL_DD_VERSIONS,
    URL_PERK_ICON_PREFIX,
    get_cache_dirs,
)


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
        self._image_cache: Dict[str, Image.Image] = {}
        self._champion_detail_cache: Dict[int, Dict[str, Any]] = {}
        self._cdragon_champion_detail_cache: Dict[int, Dict[str, Any]] = {}
        self._rune_perk_icon_path_by_id: Optional[Dict[int, str]] = None
        self._rune_perk_name_by_id: Optional[Dict[int, str]] = None
        self._cache_lock = Lock()

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
        try:
            if os.path.exists(DDRAGON_CACHE_FILE):
                with open(DDRAGON_CACHE_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                cached_version = payload.get("version")
                if target_version and cached_version != target_version:
                    return False
                self.version = cached_version
                self.by_norm_name = {k: int(v) for k, v in payload.get("by_norm_name", {}).items()}
                self.by_id = {int(k): v for k, v in payload.get("by_id", {}).items()}
                self.name_by_id = {int(k): v for k, v in payload.get("name_by_id", {}).items()}
                self.all_names = sorted(list(self.name_by_id.values()))
                self.loaded = True
                return True
        except Exception as e:
            logging.warning(f"DataDragon: Cache error - {e}")
        return False

    def _save_cache(self) -> None:
        """Persist the current champion metadata cache to disk."""
        try:
            with open(DDRAGON_CACHE_FILE, "w", encoding="utf-8") as f:
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
            logging.warning(f"DataDragon: Cache save error - {e}")

    def load(self) -> None:
        """Load champion metadata, preferring fresh Data Dragon data, then cache, then fallback."""
        if self.loaded:
            return

        # Cache directories are prepared up front because both metadata and image
        # fetches rely on them later in the session.
        get_cache_dirs()
        online_version = self._fetch_latest_version()
        if self._load_from_cache(target_version=online_version):
            logging.info(f"DataDragon: Loaded from cache (version {self.version})")
            return

        if not online_version:
            logging.warning("DataDragon: No online version and invalid cache, using fallback data")
            self._load_fallback_data()
            return

        try:
            url_champs = URL_DD_CHAMPIONS.format(version=online_version)
            response = requests.get(url_champs, timeout=10)
            response.raise_for_status()
            champions_data = response.json().get("data", {})

            self.by_id = {}
            self.name_by_id = {}
            self.by_norm_name = {}

            for champ_slug, info in champions_data.items():
                champ_name = info.get("name") or champ_slug
                champion_id = int(info.get("key"))
                self.by_id[champion_id] = info
                self.name_by_id[champion_id] = champ_name
                self.by_norm_name[self._normalize(champ_name)] = champion_id
                self.by_norm_name[self._normalize(info.get("id", champ_slug))] = champion_id

            self._add_champion_aliases()
            self.version = online_version
            self.all_names = sorted(list(self.name_by_id.values()))
            self.loaded = True
            self._save_cache()
            logging.info(
                f"DataDragon: Loaded from API (version {online_version}, {len(self.all_names)} champions)"
            )
        except requests.RequestException as e:
            logging.error(f"DataDragon: Network error while loading - {e}")
            self._load_fallback_data()
        except Exception as e:
            logging.error(f"DataDragon: Unexpected error - {e}")
            self._load_fallback_data()

    def _fetch_latest_version(self) -> Optional[str]:
        """Return the latest online Data Dragon version when the network is reachable."""
        try:
            response = requests.get(URL_DD_VERSIONS, timeout=5)
            response.raise_for_status()
            versions = response.json()
            if versions:
                return versions[0]
        except requests.RequestException as e:
            logging.warning(f"DataDragon: Unable to fetch online version - {e}")
        except Exception as e:
            logging.warning(f"DataDragon: Version parsing error - {e}")
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

        cache_key = f"champ_{champion_id}"
        with self._cache_lock:
            if cache_key in self._image_cache:
                return self._image_cache[cache_key].copy()

        champ_data = self.by_id.get(champion_id)
        if not champ_data:
            return None

        image_filename = champ_data.get("image", {}).get("full")
        if not image_filename:
            return None

        local_path = os.path.join(ICONS_CACHE_DIR, image_filename)
        if os.path.exists(local_path):
            try:
                img = Image.open(local_path)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
            except Exception as e:
                logging.debug(f"Icon cache read error for {image_filename}: {e}")

        url = URL_DD_IMG_CHAMP.format(version=self.version, filename=image_filename)
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                with open(local_path, "wb") as f:
                    f.write(response.content)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
        except Exception as e:
            logging.warning(f"DataDragon: Champion icon download error - {e}")
        return None

    def load_summoners(self) -> None:
        if self.summoner_loaded:
            return
        if not self.version:
            self.load()

        url = URL_DD_SUMMONERS.format(version=self.version)
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json().get("data", {})
                for _, info in data.items():
                    name = info.get("name")
                    image_full = info.get("image", {}).get("full")
                    if name and image_full:
                        self.summoner_data[name] = image_full
                self.summoner_loaded = True
        except Exception as e:
            logging.warning(f"DataDragon: Summoner data loading error - {e}")

    def get_summoner_icon(self, spell_name: str) -> Optional[Image.Image]:
        if spell_name in {"(None)", "(Aucun)"} or not spell_name:
            return None

        cache_key = f"spell_{spell_name}"
        with self._cache_lock:
            if cache_key in self._image_cache:
                return self._image_cache[cache_key].copy()

        self.load_summoners()
        image_filename = self.summoner_data.get(spell_name)
        if not image_filename:
            return None

        local_path = os.path.join(SPELLS_CACHE_DIR, image_filename)
        if os.path.exists(local_path):
            try:
                img = Image.open(local_path)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
            except Exception as e:
                logging.debug(f"Summ icon cache read error for {image_filename}: {e}")

        url = URL_DD_IMG_SPELL.format(version=self.version, filename=image_filename)
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                with open(local_path, "wb") as f:
                    f.write(response.content)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
        except Exception as e:
            logging.warning(f"DataDragon: Summ icon download error - {e}")
        return None

    def get_splash_art(self, champion_name: str) -> Optional[Image.Image]:
        champion_id = self.resolve_champion(champion_name)
        if not champion_id:
            return None

        real_name = self.by_id[champion_id].get("id", champion_name)
        url = URL_DD_SPLASH.format(champion=real_name)
        return self.get_remote_image(url, cache_key=f"splash_{real_name}_0")

    def get_champion_detail(self, name_or_id: Any) -> Optional[Dict[str, Any]]:
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return None

        with self._cache_lock:
            cached = self._champion_detail_cache.get(champion_id)
            if cached:
                return dict(cached)

        if not self.version:
            self.load()

        champ_data = self.by_id.get(champion_id) or {}
        champion_slug = champ_data.get("id")
        if not champion_slug or not self.version:
            return None

        try:
            url = URL_DD_CHAMPION_DETAIL.format(version=self.version, champion=champion_slug)
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            payload = response.json().get("data", {})
            detail = payload.get(champion_slug)
            if isinstance(detail, dict):
                with self._cache_lock:
                    self._champion_detail_cache[champion_id] = detail
                return dict(detail)
        except requests.RequestException as e:
            logging.warning(f"DataDragon: Champion detail download error - {e}")
        except Exception as e:
            logging.warning(f"DataDragon: Champion detail parsing error - {e}")
        return None

    @staticmethod
    def cdragon_url_from_asset_path(asset_path: str) -> Optional[str]:
        raw_path = str(asset_path or "").strip()
        if not raw_path:
            return None
        normalized = raw_path.replace("\\", "/")
        prefix = "/lol-game-data/assets/"
        lowered = normalized.lower()
        if lowered.startswith(prefix):
            relative = lowered[len(prefix):]
        else:
            relative = lowered.lstrip("/")
        if not relative.startswith("assets/"):
            return None
        return f"{URL_CDRAGON_ASSET_PREFIX}{relative}"

    def get_cdragon_champion_detail(self, name_or_id: Any) -> Optional[Dict[str, Any]]:
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return None

        with self._cache_lock:
            cached = self._cdragon_champion_detail_cache.get(champion_id)
            if cached:
                return dict(cached)

        try:
            url = URL_CDRAGON_CHAMPION_DETAIL.format(champion_id=champion_id)
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            detail = response.json()
            if isinstance(detail, dict):
                with self._cache_lock:
                    self._cdragon_champion_detail_cache[champion_id] = detail
                return dict(detail)
        except requests.RequestException as e:
            logging.warning(f"DataDragon: CDragon champion detail download error - {e}")
        except Exception as e:
            logging.warning(f"DataDragon: CDragon champion detail parsing error - {e}")
        return None

    def get_skin_catalog(self, name_or_id: Any) -> List[Dict[str, Any]]:
        champion_id = self.resolve_champion(name_or_id)
        if not champion_id:
            return []

        detail = self.get_champion_detail(champion_id)
        if not detail:
            return []
        cdragon_detail = self.get_cdragon_champion_detail(champion_id) or {}

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

    def get_skin_splash_url(
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
        return skin_data.get("splash_url") if skin_data else None

    def get_skin_tile_url(
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
        return skin_data.get("tile_url") if skin_data else None

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

    def get_skin_picker_url(
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
            skin_data.get("centered_splash_url")
            or skin_data.get("splash_url")
            or skin_data.get("tile_url")
        )

    def get_skin_splash_art(
        self,
        champion_name_or_id: Any,
        *,
        skin_name: Optional[str] = None,
        skin_id: Optional[Any] = None,
        skin_num: Optional[Any] = None,
    ) -> Optional[Image.Image]:
        skin_data = self.resolve_skin_data(
            champion_name_or_id,
            skin_name=skin_name,
            skin_id=skin_id,
            skin_num=skin_num,
        )
        if not skin_data:
            return None
        cache_key = f"skin_{skin_data['champion_slug']}_{skin_data['skin_num']}"
        return self.get_remote_image(skin_data["splash_url"], cache_key=cache_key)

    @staticmethod
    def _communitydragon_asset_url(asset_path: str) -> Optional[str]:
        normalized_path = str(asset_path or "").strip().replace("\\", "/")
        if not normalized_path:
            return None
        if normalized_path.startswith(("http://", "https://")):
            return normalized_path
        normalized_path = normalized_path.lstrip("/")
        lcu_prefix = "lol-game-data/assets/"
        if normalized_path.startswith(lcu_prefix):
            normalized_path = normalized_path[len(lcu_prefix):]
        normalized_path = normalized_path.lower().lstrip("/")
        if not normalized_path:
            return None
        return f"{URL_PERK_ICON_PREFIX}/{normalized_path}"

    def _get_communitydragon_image(self, asset_path: str, *, cache_prefix: str) -> Optional[Image.Image]:
        url = self._communitydragon_asset_url(asset_path)
        if not url:
            return None
        cache_key = f"{cache_prefix}_{url.rsplit('/', 1)[-1].replace('.png', '')}"
        with self._cache_lock:
            if cache_key in self._image_cache:
                return self._image_cache[cache_key].copy()

        try:
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
        except Exception as e:
            logging.warning("DataDragon: CommunityDragon rune icon download error for %s: %s", url, e)
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
            response = requests.get(url, timeout=8)
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
        with self._cache_lock:
            if cache_key in self._image_cache:
                return self._image_cache[cache_key].copy()

        try:
            cache_filename = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in cache_key)
            cache_path = os.path.join(SKINS_CACHE_DIR, f"{cache_filename}.img")
            if os.path.exists(cache_path):
                img = Image.open(cache_path)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img

            response = requests.get(url, stream=True, timeout=8)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                with open(cache_path, "wb") as f:
                    f.write(response.content)
                with self._cache_lock:
                    self._image_cache[cache_key] = img.copy()
                return img
        except Exception as e:
            logging.warning(f"DataDragon: Remote image error for {url} - {e}")
        return None
