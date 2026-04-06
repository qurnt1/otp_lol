"""Data Dragon access and local caching."""

import json
import logging
import os
import re
import unicodedata
from io import BytesIO
from threading import Lock
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from ..config import (
    DDRAGON_CACHE_FILE,
    ICONS_CACHE_DIR,
    SPELLS_CACHE_DIR,
    URL_DD_CHAMPIONS,
    URL_DD_IMG_CHAMP,
    URL_DD_IMG_SPELL,
    URL_DD_SPLASH,
    URL_DD_SUMMONERS,
    URL_DD_VERSIONS,
    get_cache_dirs,
)


class DataDragon:
    """Gestionnaire des donnees Data Dragon."""

    def __init__(self):
        self.loaded: bool = False
        self.version: Optional[str] = None
        self.by_norm_name: Dict[str, int] = {}
        self.by_id: Dict[int, Dict[str, Any]] = {}
        self.name_by_id: Dict[int, str] = {}
        self.all_names: List[str] = []
        self.summoner_data: Dict[str, str] = {}
        self.summoner_loaded: bool = False
        self._image_cache: Dict[str, Image.Image] = {}
        self._cache_lock = Lock()

    @staticmethod
    def _normalize(s: str) -> str:
        s = s.strip().lower()
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "", s)
        return s

    def _load_from_cache(self, target_version: Optional[str] = None) -> bool:
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
        self.load()
        return self.name_by_id.get(champion_id)

    def get_champion_tags(self, name_or_id: Any) -> List[str]:
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
            logging.warning(f"DataDragon: Summoner spell loading error - {e}")

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
                logging.debug(f"Spell icon cache read error for {image_filename}: {e}")

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
            logging.warning(f"DataDragon: Summoner spell icon download error - {e}")
        return None

    def get_splash_art(self, champion_name: str) -> Optional[Image.Image]:
        champion_id = self.resolve_champion(champion_name)
        if not champion_id:
            return None

        real_name = self.by_id[champion_id].get("id", champion_name)
        url = URL_DD_SPLASH.format(champion=real_name)

        try:
            response = requests.get(url, stream=True, timeout=5)
            if response.status_code == 200:
                return Image.open(BytesIO(response.content))
        except Exception as e:
            logging.warning(f"DataDragon: Splash art error for {champion_name} - {e}")
        return None
