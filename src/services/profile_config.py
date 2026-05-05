"""
FILE NAME: src/services/profile_config.py
GLOBAL PURPOSE:
- Build the effective champion-select profile from persisted parameters.
- Keep pick, spell, skin, and rune slot normalization in one pure helper.

KEY FUNCTIONS:
- build_effective_profile_config: Return the normalized profile used by UI preview and LCU automation.

AUDIENCE & LOGIC:
Why:
This module prevents UI and websocket layers from duplicating configuration resolution rules.
For whom:
Developers maintaining profile settings, champion-select automation, and main-window previews.

DEPENDENCIES:
Used by:
- src.core.websocket and src.ui.main_preview
Uses:
- Standard library: typing
- Local modules: src.config.constants
"""

from typing import Any, Dict

from ..config.constants import PICK_SLOT_ORDER


def build_effective_profile_config(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return the effective profile from global pick slots and champion picks."""
    pick_slots = params.get("pick_slots", {})
    if not isinstance(pick_slots, dict):
        pick_slots = {}

    slots = {
        slot_key: _resolve_slot(params, pick_slots, slot_key, f"selected_pick_{index}")
        for index, slot_key in enumerate(PICK_SLOT_ORDER, start=1)
    }
    first_slot = slots["pick_1"]
    return {
        "presets_enabled": bool(params.get("presets_enabled", True)),
        "pick_slots": slots,
        "selected_pick_1": slots["pick_1"]["champion"],
        "selected_pick_2": slots["pick_2"]["champion"],
        "selected_pick_3": slots["pick_3"]["champion"],
        "selected_ban": params.get("selected_ban", ""),
        "spell_1": first_slot.get("spell_1", ""),
        "spell_2": first_slot.get("spell_2", ""),
    }


def _resolve_slot(
    params: Dict[str, Any],
    pick_slots: Dict[str, Any],
    slot_key: str,
    pick_key: str,
) -> Dict[str, Any]:
    slot = pick_slots.get(slot_key, {})
    if not isinstance(slot, dict):
        slot = {}
    return {
        "champion": params.get(pick_key, ""),
        "spell_1": slot.get("spell_1", ""),
        "spell_2": slot.get("spell_2", ""),
        "skin_mode": str(slot.get("skin_mode") or "none").strip().lower(),
        "skin_id": _to_int(slot.get("skin_id")),
        "skin_name": str(slot.get("skin_name") or ""),
        "skin_num": _to_int(slot.get("skin_num")),
        "random_skin_id": _to_int(slot.get("random_skin_id")),
        "random_skin_name": str(slot.get("random_skin_name") or ""),
        "random_skin_num": _to_int(slot.get("random_skin_num")),
        "random_skin_pool": _normalize_random_skin_pool(slot.get("random_skin_pool")),
        "rune_page_id": _to_int(slot.get("rune_page_id")),
        "rune_page_name": str(slot.get("rune_page_name") or ""),
        "rune_auto_apply": bool(slot.get("rune_auto_apply", True)),
        "rune_keystone_path": str(slot.get("rune_keystone_path") or ""),
        "rune_sub_style_icon_path": str(slot.get("rune_sub_style_icon_path") or ""),
    }


def _normalize_random_skin_pool(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, dict)]


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
