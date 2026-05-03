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
- Local modules: src.config
"""

from typing import Any, Dict, List, Optional

from ..config import PICK_SLOT_ORDER, ROLE_PROFILE_ORDER


class MainSkinOverridesMixin:
    """Skin override and mode cycling helpers for the main window."""

    def _cycle_main_preview_skin_mode(self) -> Optional[str]:
        effective = self.get_effective_profile_config(role=self._get_main_preview_role())
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
        effective = self.get_effective_profile_config(role=self._get_main_preview_role())
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
        effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
        slot_modes = [
            self._get_effective_main_preview_skin_mode_for_slot(slot_key, effective=effective)
            for slot_key in PICK_SLOT_ORDER
        ]
        if not any(mode in {"fixed", "random"} for mode in slot_modes):
            return "none"
        unique_modes = {mode for mode in slot_modes}
        if len(unique_modes) == 1:
            return unique_modes.pop()
        return "mixed"


    def _get_effective_main_preview_skin_mode_for_slot(
        self,
        slot_key: str,
        *,
        effective: Optional[Dict[str, Any]] = None,
    ) -> str:
        effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
        overrides = self._get_main_skin_overrides()
        override_mode = overrides.get(slot_key, "inherit")
        if override_mode in {"none", "fixed", "random"}:
            return override_mode
        pick_slots = effective.get("pick_slots", {})
        slot_mode = str(pick_slots.get(slot_key, {}).get("skin_mode") or "none").strip().lower()
        return slot_mode if slot_mode in {"fixed", "random"} else "none"

    def _get_main_preview_skin_cycle_modes(self, slot_data: Optional[Dict[str, Any]] = None, *, effective: Optional[Dict[str, Any]] = None) -> List[str]:
        if slot_data is None:
            effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
            pick_slots = effective.get("pick_slots", {})
            modes = ["none"]
            if any(self._has_fixed_skin(pick_slots.get(slot_key, {})) for slot_key in PICK_SLOT_ORDER):
                modes.append("fixed")
            if any(self._has_random_skin(pick_slots.get(slot_key, {})) for slot_key in PICK_SLOT_ORDER):
                modes.append("random")
            return modes
        modes = ["none"]
        if self._has_fixed_skin(slot_data):
            modes.append("fixed")
        if self._has_random_skin(slot_data):
            modes.append("random")
        return modes


    def _get_main_preview_skin_target_role(self, effective: Optional[Dict[str, Any]] = None) -> str:
        effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
        slot_data = effective.get("pick_slots", {}).get("pick_1", {})
        source_role = str(slot_data.get("skin_source_role") or "GLOBAL").upper()
        return source_role if source_role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"


    def _get_main_skin_overrides(self) -> Dict[str, str]:
        try:
            params = self.get_params()
        except Exception:
            params = {}
        raw_overrides = params.get("main_skin_mode_overrides", {})
        legacy_mode = str(params.get("main_skin_mode_override", "inherit") or "inherit").strip().lower()
        if legacy_mode not in {"inherit", "none", "fixed", "random"}:
            legacy_mode = "inherit"
        overrides = {slot: "inherit" for slot in PICK_SLOT_ORDER}
        if legacy_mode != "inherit":
            for slot in overrides:
                overrides[slot] = legacy_mode
        if isinstance(raw_overrides, dict):
            for slot in PICK_SLOT_ORDER:
                mode = str(raw_overrides.get(slot, overrides[slot]) or overrides[slot]).strip().lower()
                overrides[slot] = mode if mode in {"inherit", "none", "fixed", "random"} else "inherit"
        return overrides


    def _get_pick_slot_config_for_role(self, role: str, slot_key: str) -> Dict[str, Any]:
        params = self.get_params()
        normalized_role = self._normalize_profile_role(role)
        if normalized_role == "GLOBAL":
            pick_slots = params.get("pick_slots", {})
        else:
            role_profiles = params.get("role_profiles", {})
            role_data = role_profiles.get(normalized_role, {}) if isinstance(role_profiles, dict) else {}
            pick_slots = role_data.get("pick_slots", {}) if isinstance(role_data, dict) else {}
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        return dict(slot_data) if isinstance(slot_data, dict) else {}


    def _set_pick_slot_skin_mode(self, slot_key: str, mode: str) -> None:
        role = self._get_main_preview_role()
        params = self.get_params()
        if role == "GLOBAL":
            pick_slots = params.get("pick_slots", {})
            if not isinstance(pick_slots, dict):
                pick_slots = {}
            new_slots = {s: (d.copy() if isinstance(d, dict) else {}) for s, d in pick_slots.items()}
            slot_data = new_slots.get(slot_key, {})
            slot_data["skin_mode"] = mode
            new_slots[slot_key] = slot_data
            self.update_param("pick_slots", new_slots)
            return

        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {r: (d.copy() if isinstance(d, dict) else {}) for r, d in role_profiles.items()}
        role_data = new_profiles.get(role, {})
        pick_slots = role_data.get("pick_slots", {})
        if not isinstance(pick_slots, dict):
            pick_slots = {}
        new_slots = {s: (d.copy() if isinstance(d, dict) else {}) for s, d in pick_slots.items()}
        slot_data = new_slots.get(slot_key, {})
        slot_data["skin_mode"] = mode
        new_slots[slot_key] = slot_data
        role_data["pick_slots"] = new_slots
        new_profiles[role] = role_data
        self.update_param("role_profiles", new_profiles)



