"""
FILE NAME: src/services/skin_modes.py
GLOBAL PURPOSE:
- Resolve skin modes and main-window skin overrides from normalized settings.
- Keep skin-mode rules shared between the main preview and champion-select automation.

KEY FUNCTIONS:
- build_main_skin_overrides: Normalize per-slot skin mode overrides.
- get_effective_skin_mode_for_slot: Resolve the active skin mode for one preset slot.
- get_skin_cycle_modes: Return the skin modes available for preview toggles.

AUDIENCE & LOGIC:
Why:
This module prevents UI mixins and champion-select automation from duplicating skin override rules.
For whom:
Developers maintaining skin selection, main preview toggles, and champion-select skin application.

DEPENDENCIES:
Used by:
- src.core.champ_select, src.ui.main_preview, and src.ui.main_skin_overrides
Uses:
- Standard library: typing
- Local modules: src.config.constants
"""

from typing import Any, Mapping

from ..config.constants import PICK_SLOT_ORDER

VALID_SKIN_MODES = {"none", "fixed", "random"}
VALID_SKIN_OVERRIDES = {"inherit", "none", "fixed", "random"}


def normalize_skin_mode(value: Any, *, default: str = "none") -> str:
    """Return a valid skin mode."""
    fallback = default if default in VALID_SKIN_MODES else "none"
    mode = str(value or fallback).strip().lower()
    return mode if mode in VALID_SKIN_MODES else fallback


def normalize_skin_override(value: Any, *, default: str = "inherit") -> str:
    """Return a valid main-preview skin override mode."""
    fallback = default if default in VALID_SKIN_OVERRIDES else "inherit"
    mode = str(value or fallback).strip().lower()
    return mode if mode in VALID_SKIN_OVERRIDES else fallback


def has_fixed_skin(slot_data: Mapping[str, Any]) -> bool:
    """Return True when a slot contains a fixed skin selection."""
    return _to_int(slot_data.get("skin_id")) > 0 or bool(str(slot_data.get("skin_name") or "").strip())


def has_random_skin(slot_data: Mapping[str, Any]) -> bool:
    """Return True when a slot contains a random skin selection."""
    return (
        _to_int(slot_data.get("random_skin_id")) > 0
        or bool(str(slot_data.get("random_skin_name") or "").strip())
        or bool(slot_data.get("random_skin_pool"))
    )


def build_main_skin_overrides(params: Mapping[str, Any]) -> dict[str, str]:
    """Normalize global and slot-specific main-window skin overrides."""
    raw_overrides = params.get("main_skin_mode_overrides", {})
    legacy_mode = normalize_skin_override(params.get("main_skin_mode_override", "inherit"))
    overrides = {slot: "inherit" for slot in PICK_SLOT_ORDER}
    if legacy_mode != "inherit":
        overrides = {slot: legacy_mode for slot in PICK_SLOT_ORDER}
    if isinstance(raw_overrides, Mapping):
        for slot in PICK_SLOT_ORDER:
            overrides[slot] = normalize_skin_override(raw_overrides.get(slot, overrides[slot]))
    return overrides


def get_effective_skin_mode_for_slot(
    slot_key: str,
    effective: Mapping[str, Any],
    overrides: Mapping[str, str],
    *,
    fallback_slot_key: str | None = None,
) -> str:
    """Resolve the effective skin mode for one preset slot."""
    override_mode = normalize_skin_override(overrides.get(slot_key, "inherit"))
    if override_mode in {"none", "fixed", "random"}:
        return override_mode

    pick_slots = effective.get("pick_slots", {})
    slot_data = _get_slot_data(pick_slots, slot_key)
    raw_mode = slot_data.get("skin_mode")
    if raw_mode in {None, ""} and fallback_slot_key and fallback_slot_key != slot_key:
        raw_mode = _get_slot_data(pick_slots, fallback_slot_key).get("skin_mode")
    return normalize_skin_mode(raw_mode)


def get_effective_skin_mode(
    effective: Mapping[str, Any],
    overrides: Mapping[str, str],
) -> str:
    """Resolve the aggregate skin mode shown by the main preview."""
    slot_modes = [
        get_effective_skin_mode_for_slot(slot_key, effective, overrides)
        for slot_key in PICK_SLOT_ORDER
    ]
    if not any(mode in {"fixed", "random"} for mode in slot_modes):
        return "none"
    unique_modes = set(slot_modes)
    if len(unique_modes) == 1:
        return unique_modes.pop()
    return "mixed"


def get_skin_cycle_modes(
    *,
    slot_data: Mapping[str, Any] | None = None,
    effective: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return the skin modes available for a global or slot-level toggle."""
    if slot_data is not None:
        return _skin_cycle_modes_for_slots([slot_data])
    if effective is None:
        return ["none"]
    pick_slots = effective.get("pick_slots", {})
    slots = [_get_slot_data(pick_slots, slot_key) for slot_key in PICK_SLOT_ORDER]
    return _skin_cycle_modes_for_slots(slots)


def _skin_cycle_modes_for_slots(slots: list[Mapping[str, Any]]) -> list[str]:
    modes = ["none"]
    if any(has_fixed_skin(slot) for slot in slots):
        modes.append("fixed")
    if any(has_random_skin(slot) for slot in slots):
        modes.append("random")
    return modes


def _get_slot_data(pick_slots: Any, slot_key: str) -> Mapping[str, Any]:
    if not isinstance(pick_slots, Mapping):
        return {}
    slot_data = pick_slots.get(slot_key, {})
    return slot_data if isinstance(slot_data, Mapping) else {}


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
