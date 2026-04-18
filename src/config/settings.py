"""Settings loading, defaults and migration helpers."""

import copy
import json
import logging
import os
from typing import Any, Dict

from .constants import PICK_SLOT_ORDER, ROLE_PROFILE_ORDER, SUMMONER_SPELL_MAP
from .paths import ICONS_CACHE_DIR, PARAMETERS_PATH, SKINS_CACHE_DIR, SPELLS_CACHE_DIR


def build_pick_slot_defaults(*, spell_1: str = "", spell_2: str = "") -> Dict[str, Dict[str, Any]]:
    """Return a pick-slot payload with optional default summs."""
    return {
        slot: {
            "spell_1": spell_1,
            "spell_2": spell_2,
            "skin_mode": "none",
            "skin_id": 0,
            "skin_name": "",
            "skin_num": 0,
            "random_skin_id": 0,
            "random_skin_name": "",
            "random_skin_num": 0,
        }
        for slot in PICK_SLOT_ORDER
    }


def build_role_profile_defaults(*, presets_enabled: bool = True) -> Dict[str, Dict[str, Any]]:
    """Return a fully initialized role profile payload."""
    return {
        role: {
            "presets_enabled": presets_enabled,
            "selected_pick_1": "",
            "selected_pick_2": "",
            "selected_pick_3": "",
            "selected_ban": "",
            "pick_slots": build_pick_slot_defaults(),
        }
        for role in ROLE_PROFILE_ORDER
    }


DEFAULT_PARAMS: Dict[str, Any] = {
    "auto_accept_enabled": True,
    "auto_pick_enabled": True,
    "auto_ban_enabled": True,
    "auto_summoners_enabled": True,
    "presets_enabled": True,
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "pick_slots": build_pick_slot_defaults(spell_1="Heal", spell_2="Flash"),
    "theme": "darkly",
    "summoner_name_auto_detect": True,
    "manual_summoner_name": "VotrePseudo#VotreTag",
    "manual_region": "euw",
    "auto_detected_riot_id": "",
    "auto_detected_region": "",
    "auto_detected_platform": "",
    "selected_profile_role": "GLOBAL",
    "role_profiles": build_role_profile_defaults(),
    "preferred_stats_site": "opgg",
    "preferred_hotkey_site": "porofessor",
    "hotkey_toggle_window": "alt+c",
    "hotkey_open_site": "alt+p",
    "auto_play_again_enabled": False,
    "auto_hide_on_connect": True,
    "close_app_on_lol_exit": True,
}

FIRST_LAUNCH_PARAMS: Dict[str, Any] = copy.deepcopy(DEFAULT_PARAMS)
FIRST_LAUNCH_PARAMS.update(
    {
        "auto_accept_enabled": False,
        "auto_pick_enabled": False,
        "auto_ban_enabled": False,
        "auto_summoners_enabled": False,
        "presets_enabled": False,
        "auto_play_again_enabled": False,
        "role_profiles": build_role_profile_defaults(presets_enabled=False),
    }
)


def load_parameters() -> Dict[str, Any]:
    """Load parameters from the JSON file."""
    if not os.path.exists(PARAMETERS_PATH):
        return copy.deepcopy(FIRST_LAUNCH_PARAMS)

    try:
        with open(PARAMETERS_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return _normalize_parameters(config)
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Error loading settings: {e}")
        return copy.deepcopy(DEFAULT_PARAMS)


def save_parameters(params: Dict[str, Any]) -> bool:
    """Save parameters to the JSON file."""
    try:
        os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
        sanitized = _normalize_parameters(params)
        with open(PARAMETERS_PATH, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=4, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        logging.error(f"Error saving settings: {e}")
        return False


def export_parameters_to_file(path: str, params: Dict[str, Any]) -> bool:
    """Export sanitized parameters to a chosen JSON file."""
    try:
        sanitized = _normalize_parameters(params)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=4, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        logging.error(f"Error exporting settings: {e}")
        return False


def import_parameters_from_file(path: str) -> Dict[str, Any]:
    """Import parameters from a JSON file and normalize them."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("The configuration file is invalid.")
    return _normalize_parameters(payload)


def _normalize_spell_value(value: Any) -> str:
    """Normalize legacy spell labels while preserving valid Riot spell names."""
    spell_name = str(value or "")
    if spell_name == "(Aucun)":
        return "(None)"
    return spell_name if spell_name in SUMMONER_SPELL_MAP or not spell_name else spell_name


def _normalize_skin_mode(value: Any) -> str:
    mode = str(value or "none").strip().lower()
    return mode if mode in {"none", "fixed", "random"} else "none"


def _normalize_skin_id(value: Any) -> int:
    try:
        skin_id = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return skin_id if skin_id >= 0 else 0


def _build_normalized_pick_slots(
    raw_slots: Any,
    *,
    fallback_spell_1: Any = "",
    fallback_spell_2: Any = "",
) -> Dict[str, Dict[str, Any]]:
    """Normalize a pick-slot payload while supporting legacy global spell fallbacks."""
    fallback_1 = _normalize_spell_value(fallback_spell_1)
    fallback_2 = _normalize_spell_value(fallback_spell_2)
    slots = build_pick_slot_defaults(spell_1=fallback_1, spell_2=fallback_2)

    if not isinstance(raw_slots, dict):
        return slots

    for slot in PICK_SLOT_ORDER:
        slot_data = raw_slots.get(slot, {})
        if not isinstance(slot_data, dict):
            slot_data = {}
        slots[slot].update(
            {
                "spell_1": _normalize_spell_value(slot_data.get("spell_1", slots[slot]["spell_1"])),
                "spell_2": _normalize_spell_value(slot_data.get("spell_2", slots[slot]["spell_2"])),
                "skin_mode": _normalize_skin_mode(slot_data.get("skin_mode", slots[slot]["skin_mode"])),
                "skin_id": _normalize_skin_id(slot_data.get("skin_id", slots[slot]["skin_id"])),
                "skin_name": str(slot_data.get("skin_name", slots[slot]["skin_name"]) or ""),
                "skin_num": _normalize_skin_id(slot_data.get("skin_num", slots[slot]["skin_num"])),
                "random_skin_id": _normalize_skin_id(
                    slot_data.get("random_skin_id", slots[slot]["random_skin_id"])
                ),
                "random_skin_name": str(slot_data.get("random_skin_name", slots[slot]["random_skin_name"]) or ""),
                "random_skin_num": _normalize_skin_id(
                    slot_data.get("random_skin_num", slots[slot]["random_skin_num"])
                ),
            }
        )
    return slots


def _normalize_parameters(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize loaded parameters and migrate old keys."""
    merged = copy.deepcopy(DEFAULT_PARAMS)
    for key, value in config.items():
        if key in {"pick_slots", "role_profiles"}:
            continue
        merged[key] = value

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

    merged["selected_pick_1"] = str(config.get("selected_pick_1", DEFAULT_PARAMS["selected_pick_1"]))
    merged["selected_pick_2"] = str(config.get("selected_pick_2", DEFAULT_PARAMS["selected_pick_2"]))
    merged["selected_pick_3"] = str(config.get("selected_pick_3", DEFAULT_PARAMS["selected_pick_3"]))
    merged["selected_ban"] = str(config.get("selected_ban", DEFAULT_PARAMS["selected_ban"]))
    merged["presets_enabled"] = bool(config.get("presets_enabled", DEFAULT_PARAMS["presets_enabled"]))
    merged["pick_slots"] = _build_normalized_pick_slots(
        config.get("pick_slots"),
        fallback_spell_1=config.get("global_spell_1", DEFAULT_PARAMS["pick_slots"]["pick_1"]["spell_1"]),
        fallback_spell_2=config.get("global_spell_2", DEFAULT_PARAMS["pick_slots"]["pick_1"]["spell_2"]),
    )

    raw_profiles = config.get("role_profiles", {}) if isinstance(config.get("role_profiles", {}), dict) else {}
    normalized_profiles = build_role_profile_defaults(presets_enabled=merged["presets_enabled"])
    for role in ROLE_PROFILE_ORDER:
        role_data = raw_profiles.get(role, {})
        if not isinstance(role_data, dict):
            role_data = {}
        normalized_profiles[role].update(
            {
                "presets_enabled": bool(role_data.get("presets_enabled", merged["presets_enabled"])),
                "selected_pick_1": str(role_data.get("selected_pick_1", "")),
                "selected_pick_2": str(role_data.get("selected_pick_2", "")),
                "selected_pick_3": str(role_data.get("selected_pick_3", "")),
                "selected_ban": str(role_data.get("selected_ban", "")),
                "pick_slots": _build_normalized_pick_slots(
                    role_data.get("pick_slots"),
                    fallback_spell_1=role_data.get("spell_1", ""),
                    fallback_spell_2=role_data.get("spell_2", ""),
                ),
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

    return {key: copy.deepcopy(merged[key]) for key in DEFAULT_PARAMS}


def get_cache_dirs() -> None:
    """Create cache directories if they do not exist."""
    for cache_dir in [ICONS_CACHE_DIR, SPELLS_CACHE_DIR, SKINS_CACHE_DIR]:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
