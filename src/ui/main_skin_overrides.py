"""
FILE NAME: src/ui/main_skin_overrides.py
GLOBAL PURPOSE:
- Mixin providing skin-override and skin-mode cycling methods for LoLAssistantUI.
- Groups main-window skin mode resolution, override management, and slot-level skin config.

DEPENDENCIES:
Used by:
- src/ui/main_window.py via LoLAssistantUI inheritance.
Uses:
- Standard library: typing
- Local modules: src.config, src.services.skin_modes
"""

from typing import Any, Dict, Optional

from ..config import PICK_SLOT_ORDER
from ..services.skin_modes import (
    build_main_skin_overrides,
    get_effective_skin_mode,
    get_effective_skin_mode_for_slot,
    get_skin_cycle_modes,
)


class MainSkinOverridesMixin:
    """Skin override and mode cycling helpers for the main window."""

    def _cycle_main_preview_skin_mode(self) -> Optional[str]:
        effective = self.get_effective_profile_config()
        cycle_modes = self._get_main_preview_skin_cycle_modes(effective=effective)
        if len(cycle_modes) == 1:
            return None
        current_mode = self._get_effective_main_preview_skin_mode(effective=effective)
        if current_mode not in cycle_modes:
            current_mode = "none"
        next_mode = cycle_modes[(cycle_modes.index(current_mode) + 1) % len(cycle_modes)]
        overrides = self._get_main_skin_overrides()
        for slot_key in PICK_SLOT_ORDER:
            overrides[slot_key] = next_mode
            self._set_pick_slot_skin_mode(slot_key, next_mode)
        self.update_param("main_skin_mode_overrides", overrides)
        return next_mode


    def _cycle_main_preview_skin_mode_for_slot(self, slot_key: str) -> Optional[str]:
        effective = self.get_effective_profile_config()
        pick_slots = effective.get("pick_slots", {})
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        cycle_modes = self._get_main_preview_skin_cycle_modes(slot_data)
        if len(cycle_modes) == 1:
            return None
        current_mode = self._get_effective_main_preview_skin_mode_for_slot(slot_key, effective=effective)
        if current_mode not in cycle_modes:
            current_mode = "none"
        next_mode = cycle_modes[(cycle_modes.index(current_mode) + 1) % len(cycle_modes)]
        overrides = self._get_main_skin_overrides()
        overrides[slot_key] = next_mode
        self._set_pick_slot_skin_mode(slot_key, next_mode)
        self.update_param("main_skin_mode_overrides", overrides)
        return next_mode


    def _get_effective_main_preview_skin_mode(self, effective: Optional[Dict[str, Any]] = None) -> str:
        effective = effective or self.get_effective_profile_config()
        return get_effective_skin_mode(effective, self._get_main_skin_overrides())


    def _get_effective_main_preview_skin_mode_for_slot(
        self,
        slot_key: str,
        *,
        effective: Optional[Dict[str, Any]] = None,
    ) -> str:
        effective = effective or self.get_effective_profile_config()
        return get_effective_skin_mode_for_slot(slot_key, effective, self._get_main_skin_overrides())

    def _get_main_preview_skin_cycle_modes(self, slot_data: Optional[Dict[str, Any]] = None, *, effective: Optional[Dict[str, Any]] = None) -> list[str]:
        if slot_data is not None:
            return get_skin_cycle_modes(slot_data=slot_data)
        return get_skin_cycle_modes(effective=effective or self.get_effective_profile_config())


    def _get_main_skin_overrides(self) -> Dict[str, str]:
        try:
            params = self.get_params()
        except Exception:
            params = {}
        return build_main_skin_overrides(params)


    def _set_pick_slot_skin_mode(self, slot_key: str, mode: str) -> None:
        params = self.get_params()
        pick_slots = params.get("pick_slots", {})
        if not isinstance(pick_slots, dict):
            pick_slots = {}
        new_slots = {s: (d.copy() if isinstance(d, dict) else {}) for s, d in pick_slots.items()}
        slot_data = new_slots.get(slot_key, {})
        slot_data["skin_mode"] = mode
        new_slots[slot_key] = slot_data
        self.update_param("pick_slots", new_slots)



