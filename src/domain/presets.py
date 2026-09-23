"""Validation rules shared by preset routes and settings persistence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..config.constants import PICK_SLOT_ORDER

PRESET_SETTING_KEYS = {
    "selected_pick_1",
    "selected_pick_2",
    "selected_pick_3",
    "selected_ban",
    "pick_slots",
}
PRESET_VALIDATION_KEYS = PRESET_SETTING_KEYS | {
    "presets_enabled",
}
PRESET_SELECTION_KEYS = {
    "presets_enabled",
    "selected_pick_1",
    "selected_pick_2",
    "selected_pick_3",
}


def validate_preset_invariants(
    candidate: Mapping[str, Any],
    *,
    changed_keys: set[str] | None = None,
    validate_pick_selection: bool = False,
) -> None:
    """Reject invalid preset state; callers may run this again under the settings lock."""
    if (
        validate_pick_selection
        and changed_keys is not None
        and PRESET_SELECTION_KEYS.intersection(changed_keys)
    ):
        picks = [
            str(candidate.get(f"selected_pick_{index}") or "").strip()
            for index in range(1, 4)
        ]
        if candidate.get("presets_enabled") and not any(picks):
            raise ValueError(
                "Configure au moins un champion avant d'activer les presets."
            )

    slots = candidate.get("pick_slots")
    if not isinstance(slots, dict):
        slots = {}
    picks = {
        str(candidate.get(f"selected_pick_{index}") or "").strip().casefold()
        for index in range(1, 4)
    }
    ban = str(candidate.get("selected_ban") or "").strip().casefold()
    for slot_key in PICK_SLOT_ORDER:
        slot = slots.get(slot_key)
        if not isinstance(slot, dict):
            continue
        spell_1 = str(slot.get("spell_1") or "").strip()
        spell_2 = str(slot.get("spell_2") or "").strip()
        if spell_1 and spell_2 and spell_1 == spell_2 and spell_1 != "(None)":
            raise ValueError(f"Les deux sorts de {slot_key} doivent être différents.")
    if ban and ban in {pick for pick in picks if pick}:
        raise ValueError("Le champion à bannir doit être différent des picks.")
