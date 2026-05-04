"""
FILE NAME: src/ui/settings_skin.py
GLOBAL PURPOSE:
- Mixin that provides skin-picker and skin-configuration methods for SettingsWindow.
- Keeps skin selection, random-skin pool management, and skin button rendering grouped together.

DEPENDENCIES:
Used by:
- src/ui/settings_window.py via SettingsWindow inheritance.
Uses:
- Standard library: logging, os, typing
- Third-party libraries: Pillow, ttkbootstrap
- Local modules: src.config, src.ui.skin_picker
"""

import random
from typing import Any, Dict, Optional

from ..config import APP_IMAGE_FILES
from .skin_picker import open_skin_picker


class SettingsSkinMixin:
    """Skin selection and configuration helpers for the settings window."""

    def _get_skin_button_label(self, slot_key: str) -> str:
        skin_config = self._get_effective_pick_slot_config(slot_key)
        skin_mode = str(skin_config.get("skin_mode") or "none")
        if skin_mode == "fixed" and skin_config.get("skin_name"):
            return str(skin_config["skin_name"])
        if skin_mode == "random":
            return "Random"
        return "Skin"

    def _get_skin_button_display_text(self, slot_key: str) -> str:
        return self._truncate_button_label(self._get_skin_button_label(slot_key))

    def _get_random_skin_placeholder_asset(self) -> str:
        theme = str(self.theme_var.get() or "darkly").strip().lower()
        if theme == "flatly":
            return APP_IMAGE_FILES["question_mark_black_mode"]
        return APP_IMAGE_FILES["question_mark_white_mode"]

    def _open_skin_picker(self, slot_key: str) -> None:
        if not self.presets_enabled_var.get():
            return
        open_skin_picker(self, slot_key)

    def _clear_pick_slot_skin(self, slot_key: str) -> None:
        self._set_pick_slot_skin_selection(slot_key, mode="none")

    def _get_random_skin_pool(self, slot_key: str) -> list[Dict[str, Any]]:
        pool = self._get_effective_pick_slot_config(slot_key).get("random_skin_pool", [])
        return [dict(entry) for entry in pool if isinstance(entry, dict)]

    def _set_random_skin_pool(self, slot_key: str, skins: list[Dict[str, Any]]) -> None:
        normalized_pool: list[Dict[str, Any]] = []
        seen_ids: set[int] = set()
        for skin in skins:
            if not isinstance(skin, dict):
                continue
            skin_id = int(skin.get("skin_id") or 0)
            if skin_id <= 0 or skin_id in seen_ids:
                continue
            seen_ids.add(skin_id)
            normalized_pool.append(
                {
                    "skin_id": skin_id,
                    "skin_name": str(skin.get("skin_name") or ""),
                    "skin_num": int(skin.get("skin_num") or 0),
                }
            )
        self._set_pick_slot_value(slot_key, "random_skin_pool", normalized_pool)

    def _set_pick_slot_skin_selection(
        self,
        slot_key: str,
        *,
        mode: str,
        fixed_skin: Optional[Dict[str, Any]] = None,
        random_skin: Optional[Dict[str, Any]] = None,
    ) -> None:
        normalized_mode = str(mode or "none").strip().lower()
        if normalized_mode not in {"none", "fixed", "random"}:
            normalized_mode = "none"

        if normalized_mode == "fixed" and fixed_skin:
            self._set_pick_slot_value(slot_key, "skin_mode", "fixed")
            self._set_pick_slot_value(slot_key, "skin_id", int(fixed_skin.get("skin_id") or 0))
            self._set_pick_slot_value(slot_key, "skin_name", str(fixed_skin.get("skin_name") or ""))
            self._set_pick_slot_value(slot_key, "skin_num", int(fixed_skin.get("skin_num") or 0))
            self._set_pick_slot_value(slot_key, "random_skin_id", 0)
            self._set_pick_slot_value(slot_key, "random_skin_name", "")
            self._set_pick_slot_value(slot_key, "random_skin_num", 0)
            self._reset_main_skin_override(slot_key)
            return

        if normalized_mode == "random" and random_skin:
            self._set_pick_slot_value(slot_key, "skin_mode", "random")
            self._set_pick_slot_value(slot_key, "skin_id", 0)
            self._set_pick_slot_value(slot_key, "skin_name", "")
            self._set_pick_slot_value(slot_key, "skin_num", 0)
            self._set_pick_slot_value(slot_key, "random_skin_id", int(random_skin.get("skin_id") or 0))
            self._set_pick_slot_value(slot_key, "random_skin_name", str(random_skin.get("skin_name") or ""))
            self._set_pick_slot_value(slot_key, "random_skin_num", int(random_skin.get("skin_num") or 0))
            current_pool = self._get_random_skin_pool(slot_key)
            if not any(int(entry.get("skin_id") or 0) == int(random_skin.get("skin_id") or 0) for entry in current_pool):
                self._set_random_skin_pool(slot_key, [*current_pool, random_skin])
            self._reset_main_skin_override(slot_key)
            return

        self._set_pick_slot_value(slot_key, "skin_mode", "none")
        self._set_pick_slot_value(slot_key, "skin_id", 0)
        self._set_pick_slot_value(slot_key, "skin_name", "")
        self._set_pick_slot_value(slot_key, "skin_num", 0)
        self._set_pick_slot_value(slot_key, "random_skin_id", 0)
        self._set_pick_slot_value(slot_key, "random_skin_name", "")
        self._set_pick_slot_value(slot_key, "random_skin_num", 0)
        self._set_random_skin_pool(slot_key, [])
        self._reset_main_skin_override(slot_key)

    def _reset_main_skin_override(self, slot_key: str) -> None:
        overrides = self.parent.get_params().get("main_skin_mode_overrides", {})
        if isinstance(overrides, dict) and overrides.get(slot_key) != "inherit":
            new_overrides = dict(overrides)
            new_overrides[slot_key] = "inherit"
            self.parent.update_param("main_skin_mode_overrides", new_overrides)

    @staticmethod
    def _choose_random_skin_entry(
        skins: list[Dict[str, Any]],
        *,
        exclude_skin_id: int = 0,
    ) -> Optional[Dict[str, Any]]:
        available = [skin for skin in skins if int(skin.get("skin_id") or 0) != int(exclude_skin_id or 0)]
        pool = available or skins
        return random.choice(pool) if pool else None

    def _refresh_skin_buttons(self) -> None:
        for slot_key, button in self.pick_skin_buttons.items():
            if not button.winfo_exists():
                continue
            champion_name = self._get_slot_champion_name(slot_key)
            skin_config = self._get_effective_pick_slot_config(slot_key)
            skin_mode = str(skin_config.get("skin_mode") or "none")
            button.configure(
                text=f"  {self._get_skin_button_display_text(slot_key)}",
                compound="left",
                bootstyle="secondary-outline",
            )
            self._load_empty_img_into_btn(button, size=self.PICK_ICON_SIZE)

            if champion_name in {"", "(None)"} or skin_mode == "none":
                continue

            if skin_mode == "random":
                self._load_local_img_into_btn(
                    button,
                    self._get_random_skin_placeholder_asset(),
                    size=self.PICK_ICON_SIZE,
                )
                continue

            skin_kwargs: Dict[str, Any] = {}
            if skin_mode == "fixed":
                skin_kwargs = {
                    "skin_id": skin_config.get("skin_id"),
                    "skin_num": skin_config.get("skin_num"),
                    "skin_name": skin_config.get("skin_name"),
                }
            preview_url = self.parent.dd.get_skin_preview_url(champion_name, **skin_kwargs)
            if not preview_url:
                continue
            cache_suffix = skin_kwargs.get("skin_num") or skin_kwargs.get("skin_id") or skin_kwargs.get("skin_name") or "0"
            self._load_remote_img_into_btn(
                button,
                preview_url,
                cache_key=f"skin_btn_{champion_name}_{cache_suffix}",
                size=self.PICK_ICON_SIZE,
            )
