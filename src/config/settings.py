"""
FILE NAME: src/config/settings.py
GLOBAL PURPOSE:
- Define default configuration payloads for the application.
- Load, normalize, reset, import, and export persisted settings.
- Keep schema migration rules explicit for profile data, pick slots, and skin settings.

KEY FUNCTIONS:
- build_pick_slot_defaults: Build a normalized pick-slot structure.
- build_role_profile_defaults: Build default role-profile payloads.
- load_parameters: Load and validate the persisted settings file.
- save_parameters: Persist normalized settings to disk.
- _normalize_parameters: Enforce the current configuration schema.

AUDIENCE & LOGIC:
Why:
This module exists so settings schema rules, first-launch defaults, and migration behavior remain centralized and predictable.
For whom:
Developers maintaining settings persistence, schema evolution, and configuration import or export.

DEPENDENCIES:
Used by:
- src.config.__init__ and runtime modules that load or save settings.
Uses:
- Standard library: copy, json, logging, os, shutil, typing
- Local modules: src.config.constants, src.config.paths
"""

import copy
import json
import logging
import os
import shutil
from typing import Any, Dict

from .constants import CURRENT_VERSION, PICK_SLOT_ORDER, SUMMONER_SPELL_MAP
from .paths import ICONS_CACHE_DIR, PARAMETERS_PATH, RUNES_CACHE_DIR, SKINS_CACHE_DIR, SPELLS_CACHE_DIR


def build_pick_slot_defaults(*, spell_1: str = "", spell_2: str = "") -> Dict[str, Dict[str, Any]]:
    """Return a normalized pick-slot payload with optional default summoner spells."""
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
            "random_skin_pool": [],
            "rune_page_id": 0,
            "rune_page_name": "",
            "rune_auto_apply": True,
            "rune_keystone_path": "",
            "rune_sub_style_icon_path": "",
        }
        for slot in PICK_SLOT_ORDER
    }


def build_main_skin_mode_overrides(*, default_mode: str = "inherit") -> Dict[str, str]:
    """Return main-window skin override defaults for each preset slot."""
    return {slot: default_mode for slot in PICK_SLOT_ORDER}


def build_demo_pick_slots() -> Dict[str, Dict[str, Any]]:
    """Return first-launch preset slots with visible spell and skin examples."""
    slots = build_pick_slot_defaults()
    slots["pick_1"].update(
        {
            "spell_1": "Flash",
            "spell_2": "Ignite",
            "skin_mode": "fixed",
            "skin_id": 86013,
            "skin_name": "God-King Garen",
            "skin_num": 13,
        }
    )
    slots["pick_2"].update(
        {
            "spell_1": "Flash",
            "spell_2": "Teleport",
            "skin_mode": "random",
            "random_skin_id": 99007,
            "random_skin_name": "Star Guardian Lux",
            "random_skin_num": 7,
            "random_skin_pool": [
                {"skin_id": 99007, "skin_name": "Star Guardian Lux", "skin_num": 7},
                {"skin_id": 99010, "skin_name": "Battle Academia Lux", "skin_num": 10},
            ],
        }
    )
    slots["pick_3"].update(
        {
            "spell_1": "Flash",
            "spell_2": "Barrier",
            "skin_mode": "fixed",
            "skin_id": 22004,
            "skin_name": "Queen Ashe",
            "skin_num": 4,
        }
    )
    return slots


DEFAULT_PARAMS: Dict[str, Any] = {
    "config_version": CURRENT_VERSION,
    "auto_accept_enabled": True,
    "auto_pick_enabled": True,
    "auto_ban_enabled": True,
    "auto_summoners_enabled": True,
    "presets_enabled": True,
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "pick_slots": build_demo_pick_slots(),
    "theme": "darkly",
    "summoner_name_auto_detect": True,
    "manual_summoner_name": "VotrePseudo#VotreTag",
    "manual_region": "euw",
    "auto_detected_riot_id": "",
    "auto_detected_region": "",
    "auto_detected_platform": "",
    "preferred_stats_site": "opgg",
    "preferred_hotkey_site": "porofessor",
    "hotkey_toggle_window": "alt+c",
    "hotkey_open_site": "alt+p",
    "auto_play_again_enabled": False,
    "auto_hide_on_connect": True,
    "close_app_on_lol_exit": True,
    "ignored_update_version": "",
    "main_skin_mode_override": "inherit",
    "main_skin_mode_overrides": build_main_skin_mode_overrides(),
    "window_x": 0,
    "window_y": 0,
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
    }
)


def _build_first_launch_payload() -> Dict[str, Any]:
    """Return the fully normalized settings payload used for a true first launch."""
    return _normalize_parameters(copy.deepcopy(FIRST_LAUNCH_PARAMS))


def _write_parameters_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and write the settings payload to the main parameters file."""
    os.makedirs(os.path.dirname(PARAMETERS_PATH), exist_ok=True)
    sanitized = _normalize_parameters(payload)
    with open(PARAMETERS_PATH, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=4, ensure_ascii=False)
    return sanitized


def _clear_skin_cache() -> None:
    """Remove cached skin previews when settings are reset to a clean baseline."""
    if not os.path.isdir(SKINS_CACHE_DIR):
        return
    logging.info("Clearing skin cache: %s", SKINS_CACHE_DIR)
    for entry in os.listdir(SKINS_CACHE_DIR):
        target = os.path.join(SKINS_CACHE_DIR, entry)
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=False)
            else:
                os.remove(target)
        except OSError as e:
            logging.debug("Unable to remove skin cache entry %s: %s", target, e)


def _reset_parameters_file(reason: str) -> Dict[str, Any]:
    """Reset the settings file to first-launch defaults after a validation failure."""
    logging.warning("Resetting parameters.json to first-launch defaults: %s", reason)
    _clear_skin_cache()
    return _write_parameters_file(_build_first_launch_payload())


def load_parameters() -> Dict[str, Any]:
    """Load, validate, and normalize parameters from the JSON settings file."""
    if not os.path.exists(PARAMETERS_PATH):
        return _reset_parameters_file("missing file")

    try:
        with open(PARAMETERS_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        logging.warning("Error loading settings: %s", e)
        return _reset_parameters_file("invalid json")

    if not isinstance(config, dict):
        return _reset_parameters_file("root payload is not an object")

    if str(config.get("config_version") or "").strip() != CURRENT_VERSION:
        return _reset_parameters_file(
            f"config version mismatch (found={config.get('config_version')!r}, expected={CURRENT_VERSION!r})"
        )

    normalized = _normalize_parameters(config)
    if config != normalized:
        return _reset_parameters_file("schema mismatch")
    return normalized


def save_parameters(params: Dict[str, Any]) -> bool:
    """Persist normalized parameters to the JSON settings file."""
    try:
        _write_parameters_file(params)
        return True
    except (IOError, OSError) as e:
        logging.error("Error saving settings: %s", e)
        return False


def export_parameters_to_file(path: str, params: Dict[str, Any]) -> bool:
    """Export sanitized parameters to a chosen JSON file."""
    try:
        sanitized = _normalize_parameters(params)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=4, ensure_ascii=False)
        return True
    except (IOError, OSError) as e:
        logging.error("Error exporting settings: %s", e)
        return False


def import_parameters_from_file(path: str) -> Dict[str, Any]:
    """Import parameters from a JSON file and normalize them to the current schema."""
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
    """Normalize stored skin modes to the supported values."""
    mode = str(value or "none").strip().lower()
    return mode if mode in {"none", "fixed", "random"} else "none"


def _normalize_main_skin_mode_override(value: Any) -> str:
    """Normalize the main-window skin override value to a supported mode."""
    mode = str(value or "inherit").strip().lower()
    return mode if mode in {"inherit", "none", "fixed", "random"} else "inherit"


def _normalize_main_skin_mode_overrides(value: Any, *, legacy_value: Any = "inherit") -> Dict[str, str]:
    """Build the per-slot main-window skin override mapping, including legacy fallbacks."""
    normalized = build_main_skin_mode_overrides()
    legacy_mode = _normalize_main_skin_mode_override(legacy_value)
    if legacy_mode != "inherit":
        for slot in normalized:
            normalized[slot] = legacy_mode
    if isinstance(value, dict):
        for slot in PICK_SLOT_ORDER:
            normalized[slot] = _normalize_main_skin_mode_override(value.get(slot, normalized[slot]))
    return normalized


def _normalize_skin_id(value: Any) -> int:
    """Convert persisted skin identifiers to a safe non-negative integer."""
    try:
        skin_id = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return skin_id if skin_id >= 0 else 0


def _normalize_skin_pool(value: Any) -> list[Dict[str, Any]]:
    """Normalize and deduplicate a persisted random-skin pool."""
    if not isinstance(value, list):
        return []
    normalized_pool: list[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        skin_id = _normalize_skin_id(item.get("skin_id", item.get("id", item.get("skinId", 0))))
        if skin_id <= 0 or skin_id in seen_ids:
            continue
        seen_ids.add(skin_id)
        normalized_pool.append(
            {
                "skin_id": skin_id,
                "skin_name": str(item.get("skin_name", item.get("name", "")) or ""),
                "skin_num": _normalize_skin_id(item.get("skin_num", item.get("num", 0))),
            }
        )
    return normalized_pool


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
                "random_skin_pool": _normalize_skin_pool(
                    slot_data.get("random_skin_pool", slots[slot]["random_skin_pool"])
                ),
                "rune_page_id": int(slot_data.get("rune_page_id", slots[slot]["rune_page_id"]) or 0),
                "rune_page_name": str(slot_data.get("rune_page_name", slots[slot]["rune_page_name"]) or ""),
                "rune_auto_apply": bool(slot_data.get("rune_auto_apply", slots[slot]["rune_auto_apply"])),
                "rune_keystone_path": str(slot_data.get("rune_keystone_path", slots[slot]["rune_keystone_path"]) or ""),
                "rune_sub_style_icon_path": str(slot_data.get("rune_sub_style_icon_path", slots[slot]["rune_sub_style_icon_path"]) or ""),
            }
        )
    return slots


def _normalize_parameters(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize loaded parameters and migrate old keys."""
    merged = copy.deepcopy(DEFAULT_PARAMS)
    for key, value in config.items():
        if key == "pick_slots":
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

    merged["selected_pick_1"] = str(config.get("selected_pick_1", DEFAULT_PARAMS["selected_pick_1"]))
    merged["selected_pick_2"] = str(config.get("selected_pick_2", DEFAULT_PARAMS["selected_pick_2"]))
    merged["selected_pick_3"] = str(config.get("selected_pick_3", DEFAULT_PARAMS["selected_pick_3"]))
    merged["selected_ban"] = str(config.get("selected_ban", DEFAULT_PARAMS["selected_ban"]))
    merged["presets_enabled"] = bool(config.get("presets_enabled", DEFAULT_PARAMS["presets_enabled"]))
    merged["main_skin_mode_override"] = _normalize_main_skin_mode_override(
        config.get("main_skin_mode_override", DEFAULT_PARAMS["main_skin_mode_override"])
    )
    merged["main_skin_mode_overrides"] = _normalize_main_skin_mode_overrides(
        config.get("main_skin_mode_overrides"),
        legacy_value=config.get("main_skin_mode_override", DEFAULT_PARAMS["main_skin_mode_override"]),
    )
    merged["pick_slots"] = _build_normalized_pick_slots(
        config.get("pick_slots"),
        fallback_spell_1=config.get("global_spell_1", DEFAULT_PARAMS["pick_slots"]["pick_1"]["spell_1"]),
        fallback_spell_2=config.get("global_spell_2", DEFAULT_PARAMS["pick_slots"]["pick_1"]["spell_2"]),
    )

    preferred_stats_site = str(config.get("preferred_stats_site", DEFAULT_PARAMS["preferred_stats_site"])).lower().strip()
    if preferred_stats_site not in {"opgg", "deeplol", "dpm", "leagueofgraphs"}:
        preferred_stats_site = DEFAULT_PARAMS["preferred_stats_site"]
    merged["preferred_stats_site"] = preferred_stats_site

    preferred_hotkey_site = str(config.get("preferred_hotkey_site", DEFAULT_PARAMS["preferred_hotkey_site"])).lower().strip()
    if preferred_hotkey_site not in {"porofessor", "deeplol", "dpm", "opgg"}:
        preferred_hotkey_site = DEFAULT_PARAMS["preferred_hotkey_site"]
    merged["preferred_hotkey_site"] = preferred_hotkey_site

    hotkey_toggle_window = str(config.get("hotkey_toggle_window", DEFAULT_PARAMS["hotkey_toggle_window"])).strip().lower()
    hotkey_open_site = str(config.get("hotkey_open_site", DEFAULT_PARAMS["hotkey_open_site"])).strip().lower()
    merged["hotkey_toggle_window"] = hotkey_toggle_window or DEFAULT_PARAMS["hotkey_toggle_window"]
    merged["hotkey_open_site"] = hotkey_open_site or DEFAULT_PARAMS["hotkey_open_site"]
    merged["ignored_update_version"] = str(
        config.get("ignored_update_version", DEFAULT_PARAMS["ignored_update_version"])
    ).strip()

    theme = str(config.get("theme", DEFAULT_PARAMS["theme"])).strip().lower()
    if theme not in {"darkly", "flatly"}:
        theme = DEFAULT_PARAMS["theme"]
    merged["theme"] = theme

    return {key: copy.deepcopy(merged[key]) for key in DEFAULT_PARAMS}


def get_cache_dirs() -> None:
    """Create cache directories if they do not exist."""
    for cache_dir in [ICONS_CACHE_DIR, SPELLS_CACHE_DIR, SKINS_CACHE_DIR, RUNES_CACHE_DIR]:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
