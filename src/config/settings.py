"""Settings loading, defaults and migration helpers."""

import json
import logging
import os
from typing import Any, Dict

from .constants import ROLE_PROFILE_ORDER
from .paths import PARAMETERS_PATH, ICONS_CACHE_DIR, SPELLS_CACHE_DIR


DEFAULT_PARAMS: Dict[str, Any] = {
    "auto_accept_enabled": True,
    "auto_pick_enabled": True,
    "auto_ban_enabled": True,
    "auto_summoners_enabled": True,
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "theme": "darkly",
    "summoner_name_auto_detect": True,
    "manual_summoner_name": "VotrePseudo#VotreTag",
    "manual_region": "euw",
    "auto_detected_riot_id": "",
    "auto_detected_region": "",
    "auto_detected_platform": "",
    "selected_profile_role": "GLOBAL",
    "role_profiles": {},
    "global_spell_1": "Heal",
    "global_spell_2": "Flash",
    "auto_play_again_enabled": False,
    "auto_hide_on_connect": True,
    "close_app_on_lol_exit": True,
}


def load_parameters() -> Dict[str, Any]:
    """Load parameters from the JSON file."""
    if not os.path.exists(PARAMETERS_PATH):
        return DEFAULT_PARAMS.copy()

    try:
        with open(PARAMETERS_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return _normalize_parameters(config)
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Erreur chargement paramètres: {e}")
        return DEFAULT_PARAMS.copy()


def save_parameters(params: Dict[str, Any]) -> bool:
    """Save parameters to the JSON file."""
    try:
        os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
        sanitized = _normalize_parameters(params)
        with open(PARAMETERS_PATH, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=4, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        logging.error(f"Erreur sauvegarde paramètres: {e}")
        return False


def _normalize_parameters(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize loaded parameters and migrate old keys."""
    merged = DEFAULT_PARAMS.copy()
    merged.update(config)

    if "manual_region" not in config:
        merged["manual_region"] = config.get("region", DEFAULT_PARAMS["manual_region"])

    if "auto_detected_region" not in config and config.get("summoner_name_auto_detect"):
        merged["auto_detected_region"] = ""

    if "auto_detected_riot_id" not in config:
        merged["auto_detected_riot_id"] = ""

    if "auto_detected_platform" not in config:
        merged["auto_detected_platform"] = ""

    selected_profile_role = str(merged.get("selected_profile_role", "GLOBAL")).upper()
    selected_profile_role = {
        "MID": "MIDDLE",
        "ADC": "BOTTOM",
        "BOT": "BOTTOM",
        "SUP": "UTILITY",
        "SUPPORT": "UTILITY",
        "JGL": "JUNGLE",
    }.get(selected_profile_role, selected_profile_role)
    merged["selected_profile_role"] = selected_profile_role if selected_profile_role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"

    raw_profiles = config.get("role_profiles", {}) if isinstance(config.get("role_profiles", {}), dict) else {}
    normalized_profiles: Dict[str, Dict[str, str]] = {}
    for role in ROLE_PROFILE_ORDER:
        role_data = raw_profiles.get(role, {})
        if not isinstance(role_data, dict):
            role_data = {}
        normalized_profiles[role] = {
            "selected_pick_1": str(role_data.get("selected_pick_1", "")),
            "selected_pick_2": str(role_data.get("selected_pick_2", "")),
            "selected_pick_3": str(role_data.get("selected_pick_3", "")),
            "selected_ban": str(role_data.get("selected_ban", "")),
        }
    merged["role_profiles"] = normalized_profiles

    return {key: merged[key] for key in DEFAULT_PARAMS}


def get_cache_dirs() -> None:
    """Create cache directories if they do not exist."""
    for cache_dir in [ICONS_CACHE_DIR, SPELLS_CACHE_DIR]:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
