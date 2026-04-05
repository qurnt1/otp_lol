"""Settings loading, defaults and migration helpers."""

import json
import logging
import os
from typing import Any, Dict

from .constants import ROLE_PROFILE_ORDER
from .paths import ICONS_CACHE_DIR, PARAMETERS_PATH, SPELLS_CACHE_DIR


def build_role_profile_defaults() -> Dict[str, Dict[str, str]]:
    """Return a fully initialized role profile payload."""
    return {
        role: {
            "selected_pick_1": "",
            "selected_pick_2": "",
            "selected_pick_3": "",
            "selected_ban": "",
            "spell_1": "",
            "spell_2": "",
        }
        for role in ROLE_PROFILE_ORDER
    }


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
    "role_profiles": build_role_profile_defaults(),
    "global_spell_1": "Heal",
    "global_spell_2": "Flash",
    "preferred_stats_site": "opgg",
    "preferred_hotkey_site": "porofessor",
    "hotkey_toggle_window": "alt+c",
    "hotkey_open_site": "alt+p",
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
        logging.warning(f"Erreur chargement parametres: {e}")
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
        logging.error(f"Erreur sauvegarde parametres: {e}")
        return False


def export_parameters_to_file(path: str, params: Dict[str, Any]) -> bool:
    """Export sanitized parameters to a chosen JSON file."""
    try:
        sanitized = _normalize_parameters(params)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=4, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        logging.error(f"Erreur export parametres: {e}")
        return False


def import_parameters_from_file(path: str) -> Dict[str, Any]:
    """Import parameters from a JSON file and normalize them."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Le fichier de configuration est invalide.")
    return _normalize_parameters(payload)


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
    merged["selected_profile_role"] = (
        selected_profile_role if selected_profile_role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"
    )

    raw_profiles = config.get("role_profiles", {}) if isinstance(config.get("role_profiles", {}), dict) else {}
    normalized_profiles = build_role_profile_defaults()
    for role in ROLE_PROFILE_ORDER:
        role_data = raw_profiles.get(role, {})
        if not isinstance(role_data, dict):
            role_data = {}
        normalized_profiles[role].update(
            {
                "selected_pick_1": str(role_data.get("selected_pick_1", "")),
                "selected_pick_2": str(role_data.get("selected_pick_2", "")),
                "selected_pick_3": str(role_data.get("selected_pick_3", "")),
                "selected_ban": str(role_data.get("selected_ban", "")),
                "spell_1": str(role_data.get("spell_1", "")),
                "spell_2": str(role_data.get("spell_2", "")),
            }
        )
    merged["role_profiles"] = normalized_profiles

    preferred_stats_site = str(config.get("preferred_stats_site", DEFAULT_PARAMS["preferred_stats_site"])).lower().strip()
    if preferred_stats_site not in {"opgg", "deeplol", "leagueofgraphs"}:
        preferred_stats_site = DEFAULT_PARAMS["preferred_stats_site"]
    merged["preferred_stats_site"] = preferred_stats_site

    preferred_hotkey_site = str(config.get("preferred_hotkey_site", DEFAULT_PARAMS["preferred_hotkey_site"])).lower().strip()
    if preferred_hotkey_site not in {"porofessor", "deeplol", "opgg"}:
        preferred_hotkey_site = DEFAULT_PARAMS["preferred_hotkey_site"]
    merged["preferred_hotkey_site"] = preferred_hotkey_site

    hotkey_toggle_window = str(config.get("hotkey_toggle_window", DEFAULT_PARAMS["hotkey_toggle_window"])).strip().lower()
    hotkey_open_site = str(config.get("hotkey_open_site", DEFAULT_PARAMS["hotkey_open_site"])).strip().lower()
    merged["hotkey_toggle_window"] = hotkey_toggle_window or DEFAULT_PARAMS["hotkey_toggle_window"]
    merged["hotkey_open_site"] = hotkey_open_site or DEFAULT_PARAMS["hotkey_open_site"]

    theme = str(config.get("theme", DEFAULT_PARAMS["theme"])).strip().lower()
    if theme not in {"darkly", "flatly"}:
        theme = DEFAULT_PARAMS["theme"]
    merged["theme"] = theme

    return {key: merged[key] for key in DEFAULT_PARAMS}


def get_cache_dirs() -> None:
    """Create cache directories if they do not exist."""
    for cache_dir in [ICONS_CACHE_DIR, SPELLS_CACHE_DIR]:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
