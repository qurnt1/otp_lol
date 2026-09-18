"""
FILE NAME: src/config/settings.py
GLOBAL PURPOSE:
- Define default configuration payloads for the application.
- Load, normalize, reset, import, and export persisted settings.
- Keep current-schema validation, first-launch defaults, and normalization centralized.

KEY FUNCTIONS:
- build_pick_slot_defaults: Build a normalized pick-slot structure.
- load_parameters: Load and validate the persisted settings file.
- save_parameters: Persist normalized settings to disk.
- _normalize_parameters: Enforce the current configuration schema.

AUDIENCE & LOGIC:
Why:
This module exists so current settings schema rules, first-launch defaults, and normalization remain centralized and predictable.
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
import tempfile
import tomllib
from typing import Any, Dict

import tomli_w

from .constants import (
    APP_VERSION,
    CONFIG_SCHEMA_VERSION,
    CURRENT_VERSION,
    HOTKEY_PROVIDERS,
    PICK_SLOT_ORDER,
    STATS_PROVIDERS,
    SUMMONER_SPELL_MAP,
)
from ..domain.hotkeys import normalize_hotkey, validate_hotkey_pair
from .paths import (
    ICONS_CACHE_DIR,
    PARAMETERS_PATH,
    RUNES_CACHE_DIR,
    SKINS_CACHE_DIR,
    SPELLS_CACHE_DIR,
)


def build_pick_slot_defaults() -> Dict[str, Dict[str, Any]]:
    """Return blank pick-slot defaults for the current settings format."""
    return {
        slot: {
            "spell_1": "",
            "spell_2": "",
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


def build_demo_pick_slots() -> Dict[str, Dict[str, Any]]:
    """Return optional preview slots with visible spell and skin examples."""
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


DEMO_PRESETS: Dict[str, Any] = {
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "pick_slots": build_demo_pick_slots(),
}


FACTORY_DEFAULT_SETTINGS: Dict[str, Any] = {
    "config_version": CURRENT_VERSION,
    "config_schema_version": CONFIG_SCHEMA_VERSION,
    "auto_accept_enabled": False,
    "auto_pick_enabled": False,
    "auto_ban_enabled": False,
    "auto_summoners_enabled": False,
    "presets_enabled": False,
    "selected_pick_1": "",
    "selected_pick_2": "",
    "selected_pick_3": "",
    "selected_ban": "",
    "pick_slots": build_pick_slot_defaults(),
    "theme": "darkly",
    "summoner_name_auto_detect": True,
    "manual_summoner_name": "",
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
    "skin_automation_enabled": False,
    "onboarding_completed": False,
    "window_x": 0,
    "window_y": 0,
    "window_width": 1100,
    "window_height": 760,
    "window_maximized": False,
}

DEFAULT_PARAMS: Dict[str, Any] = copy.deepcopy(FACTORY_DEFAULT_SETTINGS)
DEFAULT_PARAMS.update(
    {
        "selected_pick_1": "",
        "selected_pick_2": "",
        "selected_pick_3": "",
        "selected_ban": "",
        "pick_slots": build_pick_slot_defaults(),
        # Existing settings files that predate onboarding are already configured.
        "onboarding_completed": True,
    }
)

DEMO_PARAMS: Dict[str, Any] = copy.deepcopy(DEFAULT_PARAMS)
DEMO_PARAMS.update(
    {
        "auto_accept_enabled": True,
        "auto_pick_enabled": True,
        "auto_ban_enabled": True,
        "auto_summoners_enabled": True,
        "skin_automation_enabled": True,
        **copy.deepcopy(DEMO_PRESETS),
    }
)

def build_starter_pick_slots() -> Dict[str, Dict[str, Any]]:
    """Return editable starter picks without account-specific skins or runes."""
    slots = build_pick_slot_defaults()
    for slot in slots.values():
        slot["rune_auto_apply"] = False
    slots["pick_1"].update({"spell_1": "Flash", "spell_2": "Ignite"})
    slots["pick_2"].update({"spell_1": "Flash", "spell_2": "Barrier"})
    slots["pick_3"].update({"spell_1": "Flash", "spell_2": "Heal"})
    return slots


STARTER_PRESET_CONFIG: Dict[str, Any] = {
    "selected_pick_1": "Garen",
    "selected_pick_2": "Lux",
    "selected_pick_3": "Ashe",
    "selected_ban": "Teemo",
    "pick_slots": build_starter_pick_slots(),
}

FIRST_LAUNCH_PARAMS: Dict[str, Any] = copy.deepcopy(DEFAULT_PARAMS)
FIRST_LAUNCH_PARAMS.update(copy.deepcopy(FACTORY_DEFAULT_SETTINGS))
FIRST_LAUNCH_PARAMS.update(copy.deepcopy(STARTER_PRESET_CONFIG))


def _build_first_launch_payload() -> Dict[str, Any]:
    """Return the fully normalized settings payload used for a true first launch."""
    return _normalize_parameters(copy.deepcopy(FIRST_LAUNCH_PARAMS))


def _atomic_write_bytes(path: str, content: bytes) -> None:
    """Write bytes to a temporary file and replace the destination atomically."""
    absolute_path = os.path.abspath(path)
    directory = os.path.dirname(absolute_path) or "."
    os.makedirs(directory, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(absolute_path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            file_descriptor = None
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, absolute_path)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                logging.debug("Unable to remove temporary settings file: %s", temporary_path)


def _write_parameters_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and write the settings payload to the main parameters file."""
    sanitized = _normalize_parameters(payload)
    _atomic_write_bytes(PARAMETERS_PATH, tomli_w.dumps(sanitized).encode("utf-8"))
    return sanitized


def _backup_parameters_file() -> bool:
    """Preserve an unreadable settings file before replacing it with safe defaults."""
    if not os.path.exists(PARAMETERS_PATH):
        return True
    backup_path = f"{PARAMETERS_PATH}.bak"
    try:
        shutil.copy2(PARAMETERS_PATH, backup_path)
        logging.warning("Backed up unreadable settings to %s", backup_path)
        return True
    except OSError as e:
        logging.error("Unable to back up unreadable settings to %s: %s", backup_path, e)
        return False


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
    logging.warning("Resetting parameters.toml to first-launch defaults: %s", reason)
    had_parameters_file = os.path.exists(PARAMETERS_PATH)
    if not _backup_parameters_file():
        return _build_first_launch_payload()
    payload = _build_first_launch_payload()
    try:
        written = _write_parameters_file(payload)
    except (OSError, TypeError, ValueError) as e:
        logging.error("Unable to write recovery settings: %s", e)
        return payload
    if had_parameters_file:
        _clear_skin_cache()
    return written


def _read_schema_version(config: Dict[str, Any]) -> int:
    """Read the canonical settings schema marker."""
    raw_schema_version = config.get("config_schema_version")
    if isinstance(raw_schema_version, bool):
        raise ValueError(f"invalid settings schema version: {raw_schema_version!r}")
    try:
        schema_version = int(raw_schema_version or 0)
    except (TypeError, ValueError, OverflowError) as e:
        raise ValueError(f"invalid settings schema version: {raw_schema_version!r}") from e
    if schema_version < 0:
        raise ValueError(f"invalid settings schema version: {schema_version}")
    return schema_version


def _normalize_current_schema(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize settings using the current configuration schema."""
    schema_version = _read_schema_version(config)
    if schema_version != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported settings schema (found={schema_version}, expected={CONFIG_SCHEMA_VERSION})"
        )
    normalized = copy.deepcopy(config)
    normalized["config_version"] = APP_VERSION
    return _normalize_parameters(normalized)


def load_parameters() -> Dict[str, Any]:
    """Load, validate, and normalize parameters from the TOML settings file."""
    if not os.path.exists(PARAMETERS_PATH):
        return _reset_parameters_file("missing file")

    try:
        with open(PARAMETERS_PATH, "rb") as f:
            config = tomllib.load(f)
    except (tomllib.TOMLDecodeError, IOError, OSError) as e:
        logging.warning("Error loading settings: %s", e)
        return _reset_parameters_file("invalid toml")

    if not isinstance(config, dict):
        return _reset_parameters_file("root payload is not an object")

    try:
        normalized = _normalize_current_schema(config)
    except ValueError as e:
        return _reset_parameters_file(str(e))

    if config != normalized:
        logging.info("Normalizing parameters.toml for settings schema %s", CONFIG_SCHEMA_VERSION)
        try:
            return _write_parameters_file(normalized)
        except (OSError, TypeError, ValueError) as e:
            logging.error("Unable to persist normalized settings: %s", e)
            return normalized
    return normalized


def save_parameters(params: Dict[str, Any]) -> bool:
    """Persist normalized parameters to the TOML settings file."""
    try:
        _write_parameters_file(params)
        return True
    except (IOError, OSError) as e:
        logging.error("Error saving settings: %s", e)
        return False


def normalize_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a defensive, current-schema settings snapshot without writing it."""
    if not isinstance(params, dict):
        raise TypeError("params must be a dictionary")
    return _normalize_parameters(copy.deepcopy(params))


def export_parameters_to_file(path: str, params: Dict[str, Any]) -> bool:
    """Export sanitized parameters to a chosen TOML or JSON file (detected from extension)."""
    try:
        sanitized = _normalize_parameters(params)
        if path.lower().endswith(".json"):
            content = json.dumps(sanitized, indent=4, ensure_ascii=False).encode("utf-8")
        else:
            content = tomli_w.dumps(sanitized).encode("utf-8")
        _atomic_write_bytes(path, content)
        return True
    except (IOError, OSError) as e:
        logging.error("Error exporting settings: %s", e)
        return False


def import_parameters_from_file(path: str) -> Dict[str, Any]:
    """Import parameters from a TOML or JSON file and normalize them to the current schema."""
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        with open(path, "rb") as f:
            payload = tomllib.load(f)
    if not isinstance(payload, dict):
        raise ValueError("The configuration file is invalid.")
    return _normalize_current_schema(payload)


def _normalize_spell_value(value: Any) -> str:
    """Keep only valid Riot summoner spell names."""
    spell_name = str(value or "")
    return spell_name if spell_name in SUMMONER_SPELL_MAP else ""


def _normalize_skin_mode(value: Any) -> str:
    """Normalize stored skin modes to the supported values."""
    mode = str(value or "none").strip().lower()
    return mode if mode in {"none", "fixed", "random"} else "none"


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
        skin_id = _normalize_skin_id(item.get("skin_id"))
        if skin_id <= 0 or skin_id in seen_ids:
            continue
        seen_ids.add(skin_id)
        normalized_pool.append(
            {
                "skin_id": skin_id,
                "skin_name": str(item.get("skin_name") or ""),
                "skin_num": _normalize_skin_id(item.get("skin_num")),
            }
        )
    return normalized_pool


def _build_normalized_pick_slots(
    raw_slots: Any,
) -> Dict[str, Dict[str, Any]]:
    """Normalize pick slots without importing settings from an older format."""
    slots = build_pick_slot_defaults()

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
    """Normalize settings for the current schema."""
    merged = copy.deepcopy(DEFAULT_PARAMS)
    for key, value in config.items():
        if key == "pick_slots" or key not in DEFAULT_PARAMS:
            continue
        merged[key] = value

    merged["config_version"] = APP_VERSION
    merged["config_schema_version"] = CONFIG_SCHEMA_VERSION

    merged["selected_pick_1"] = str(config.get("selected_pick_1", DEFAULT_PARAMS["selected_pick_1"]))
    merged["selected_pick_2"] = str(config.get("selected_pick_2", DEFAULT_PARAMS["selected_pick_2"]))
    merged["selected_pick_3"] = str(config.get("selected_pick_3", DEFAULT_PARAMS["selected_pick_3"]))
    merged["selected_ban"] = str(config.get("selected_ban", DEFAULT_PARAMS["selected_ban"]))
    merged["presets_enabled"] = bool(config.get("presets_enabled", DEFAULT_PARAMS["presets_enabled"]))
    raw_skin_automation = config.get("skin_automation_enabled", DEFAULT_PARAMS["skin_automation_enabled"])
    if isinstance(raw_skin_automation, str):
        raw_skin_automation = raw_skin_automation.strip().lower() in {"1", "true", "yes", "on"}
    merged["skin_automation_enabled"] = bool(raw_skin_automation)
    merged["pick_slots"] = _build_normalized_pick_slots(config.get("pick_slots"))

    preferred_stats_site = str(config.get("preferred_stats_site", DEFAULT_PARAMS["preferred_stats_site"])).lower().strip()
    if preferred_stats_site not in STATS_PROVIDERS:
        preferred_stats_site = DEFAULT_PARAMS["preferred_stats_site"]
    merged["preferred_stats_site"] = preferred_stats_site

    preferred_hotkey_site = str(config.get("preferred_hotkey_site", DEFAULT_PARAMS["preferred_hotkey_site"])).lower().strip()
    if preferred_hotkey_site not in HOTKEY_PROVIDERS:
        preferred_hotkey_site = DEFAULT_PARAMS["preferred_hotkey_site"]
    merged["preferred_hotkey_site"] = preferred_hotkey_site

    default_toggle = DEFAULT_PARAMS["hotkey_toggle_window"]
    default_open_site = DEFAULT_PARAMS["hotkey_open_site"]
    try:
        hotkey_toggle_window = normalize_hotkey(config.get("hotkey_toggle_window", default_toggle))
    except (TypeError, ValueError) as error:
        logging.warning("Invalid window hotkey; using %s: %s", default_toggle, error)
        hotkey_toggle_window = default_toggle
    try:
        hotkey_open_site = normalize_hotkey(config.get("hotkey_open_site", default_open_site))
    except (TypeError, ValueError) as error:
        logging.warning("Invalid stats hotkey; using %s: %s", default_open_site, error)
        hotkey_open_site = default_open_site
    try:
        hotkey_toggle_window, hotkey_open_site = validate_hotkey_pair(hotkey_toggle_window, hotkey_open_site)
    except ValueError as error:
        logging.warning("Duplicate global hotkeys; using %s for the stats shortcut: %s", default_open_site, error)
        hotkey_open_site = default_toggle if hotkey_toggle_window == default_open_site else default_open_site
    merged["hotkey_toggle_window"] = hotkey_toggle_window
    merged["hotkey_open_site"] = hotkey_open_site
    merged["ignored_update_version"] = str(
        config.get("ignored_update_version", DEFAULT_PARAMS["ignored_update_version"])
    ).strip()

    theme = str(config.get("theme", DEFAULT_PARAMS["theme"])).strip().lower()
    if theme not in {"darkly", "flatly"}:
        theme = DEFAULT_PARAMS["theme"]
    merged["theme"] = theme

    for key, minimum, maximum in (
        ("window_width", 800, 7680),
        ("window_height", 540, 4320),
    ):
        try:
            value = int(config.get(key, DEFAULT_PARAMS[key]))
        except (TypeError, ValueError, OverflowError):
            value = DEFAULT_PARAMS[key]
        merged[key] = min(max(value, minimum), maximum)
    merged["window_x"] = _normalize_window_position(config.get("window_x", DEFAULT_PARAMS["window_x"]))
    merged["window_y"] = _normalize_window_position(config.get("window_y", DEFAULT_PARAMS["window_y"]))
    merged["window_maximized"] = bool(config.get("window_maximized", DEFAULT_PARAMS["window_maximized"]))

    return {key: copy.deepcopy(merged[key]) for key in DEFAULT_PARAMS}


def _normalize_window_position(value: Any) -> int:
    """Keep persisted coordinates finite without rejecting an otherwise valid config."""
    try:
        position = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return min(max(position, -10000), 10000)


def get_cache_dirs() -> None:
    """Create cache directories if they do not exist."""
    for cache_dir in [ICONS_CACHE_DIR, SPELLS_CACHE_DIR, SKINS_CACHE_DIR, RUNES_CACHE_DIR]:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
