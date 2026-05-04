"""
FILE NAME: src/ui/main_preview.py
GLOBAL PURPOSE:
- Mixin providing feature preview and profile configuration methods for LoLAssistantUI.
- Groups preview rendering, icon loading, feature toggling, and effective config resolution.

DEPENDENCIES:
Used by:
- src/ui/main_window.py via LoLAssistantUI inheritance.
Uses:
- Standard library: logging, os, tkinter, typing
- Third-party libraries: Pillow, ttkbootstrap
- Local modules: src.config
"""

import logging
import os
from typing import Any, Dict, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from ..config import (
    APP_IMAGE_FILES,
    PICK_SLOT_ORDER,
    THEME_PALETTE,
    resource_path,
)


class MainPreviewMixin:
    """Feature preview and effective profile resolution helpers."""

    def _apply_preview_palette(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        if self.feature_preview_frame and self.feature_preview_frame.winfo_exists():
            self.feature_preview_frame.configure(bg=palette["window_bg"])
        for group in self.feature_group_frames.values():
            for current in self._iter_widget_tree(group):
                try:
                    if isinstance(current, (tk.Frame, tk.Label)):
                        current.configure(bg=palette["window_bg"])
                        if isinstance(current, tk.Label):
                            current.configure(fg=palette["text"])
                except Exception:
                    continue
        for icon_labels in self.feature_icon_labels.values():
            for label in icon_labels:
                try:
                    label.configure(bg=palette["window_bg"], fg=palette["muted"])
                except Exception:
                    continue


    def _build_feature_preview_payload(self, params: Dict[str, Any], effective: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        presets_enabled = bool(effective.get("presets_enabled", True))
        pick_slots = effective.get("pick_slots", {})
        skin_values = []
        slot_modes = []
        for slot_key in PICK_SLOT_ORDER:
            slot_mode = self._get_effective_main_preview_skin_mode_for_slot(slot_key, effective=effective)
            slot_modes.append(slot_mode)
            
            # Inject champion name so the skin preview thumbnail can load properly
            slot_data = dict(pick_slots.get(slot_key, {}))
            slot_data["champion"] = str(effective.get(f"selected_{slot_key}") or "").strip()
            skin_values.append(self._build_slot_skin_preview_value(slot_data, mode=slot_mode))
            
        if not any(mode in {"fixed", "random"} for mode in slot_modes):
            skin_mode = "none"
        elif len(set(slot_modes)) == 1:
            skin_mode = slot_modes[0]
        else:
            skin_mode = "mixed"
        return {
            "presets": {
                "enabled": (
                    params.get("auto_pick_enabled", True)
                    and params.get("auto_summoners_enabled", True)
                    and presets_enabled
                ),
                "style": "info",
                "is_champion": True,
                "values": [
                    effective.get("selected_pick_1") or "",
                    effective.get("selected_pick_2") or "",
                    effective.get("selected_pick_3") or "",
                ],
            },
            "skins": {
                "enabled": any(mode in {"fixed", "random"} for mode in slot_modes),
                "style": "info",
                "is_skin": True,
                "mode": skin_mode,
                "values": skin_values,
            },
            "ban": {
                "enabled": params.get("auto_ban_enabled", True),
                "style": "danger",
                "is_champion": True,
                "values": [effective.get("selected_ban") or ""],
            },
        }


    def _build_preview_signature(self, preview_data: Dict[str, Dict[str, Any]]) -> tuple:
        signature = []
        for key in ("presets", "skins", "ban"):
            data = preview_data.get(key, {})
            values = []
            for value in data.get("values", []):
                if isinstance(value, dict):
                    values.append(tuple(sorted(value.items())))
                else:
                    values.append(value)
            signature.append(
                (
                    key,
                    bool(data.get("enabled")),
                    data.get("mode"),
                    tuple(values),
                )
            )
        return tuple(signature)


    def _build_slot_skin_preview_value(self, slot_data: Dict[str, Any], *, mode: str) -> Dict[str, Any]:
        champion_name = str(slot_data.get("champion") or "").strip()
        if mode == "fixed" and self._has_fixed_skin(slot_data):
            return {
                "mode": "fixed",
                "champion_name": champion_name,
                "skin_id": int(slot_data.get("skin_id") or 0),
                "skin_name": str(slot_data.get("skin_name") or ""),
                "skin_num": int(slot_data.get("skin_num") or 0),
            }
        if mode == "random" and self._has_random_skin(slot_data):
            return {"mode": "random"}
        return {"mode": "none"}


    def _create_feature_preview(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        self.feature_preview_frame = tk.Frame(self.root, bg=palette["window_bg"], bd=0, highlightthickness=0)
        self.feature_preview_frame.place(relx=0.5, rely=self.PREVIEW_TOP_RELY, anchor="n")

        for column, (key, label_text, icon_count, status_style) in enumerate(self.FEATURE_PREVIEW_DEFINITIONS):
            group = tk.Frame(self.feature_preview_frame, bg=palette["window_bg"], bd=0, highlightthickness=0, padx=4, pady=1)
            group.grid(row=0, column=column, padx=4)
            self.feature_group_frames[key] = group

            header = tk.Frame(group, bg=palette["window_bg"], bd=0, highlightthickness=0)
            header.pack(anchor="w")
            title = tk.Label(header, text=label_text, bg=palette["window_bg"], fg=palette["text"], font=("Segoe UI", 9, "bold"))
            title.pack(side="left")
            status = tk.Label(
                header,
                text="OFF",
                bg=palette["window_bg"],
                fg=palette["muted"],
                font=("Segoe UI", 9),
                padx=4,
            )
            status.pack(side="left", padx=(6, 0))
            self.feature_status_labels[key] = status

            icons_row = tk.Frame(group, bg=palette["window_bg"], bd=0, highlightthickness=0)
            icons_row.pack(anchor="w", pady=(4, 0))
            labels: list[tk.Label] = []
            for index in range(icon_count):
                slot = tk.Label(
                    icons_row,
                    text="",
                    anchor="center",
                    compound="center",
                    image=self.preview_placeholder,
                    bg=palette["window_bg"],
                    fg=palette["muted"],
                    font=("Segoe UI", 9),
                    bd=0,
                    highlightthickness=0,
                )
                slot.pack(side="left", padx=2, pady=0)
                slot.image = self.preview_placeholder
                labels.append(slot)
            self.feature_icon_labels[key] = labels
            if key == "skins":
                self._bind_click_tree(header, lambda event, feature_key=key: self._on_feature_group_click(feature_key, event))
                for index, slot in enumerate(labels):
                    slot_key = PICK_SLOT_ORDER[index]
                    self._bind_click_tree(slot, lambda event, current_slot=slot_key: self._on_skin_preview_click(current_slot, event))
            else:
                self._bind_feature_group(group, key)

        self._queue_feature_preview_refresh(force=True)


    def _get_feature_status_colors(self, accent: str, enabled: bool) -> tuple[str, str]:
        if not enabled:
            return ("", THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])["muted"])
        palette = {
            "info": "#3da5ff",
            "danger": "#ff6b5a",
        }
        return ("", palette.get(accent, "#3da5ff"))


    def _get_preview_icon_cache_key(self, name: str, is_champion: bool, size: Optional[int] = None) -> tuple[str, str, int]:
        kind = "champ" if is_champion else "spell"
        return kind, name, size or self.PREVIEW_ICON_SIZE


    def _get_random_skin_placeholder_asset(self) -> str:
        return APP_IMAGE_FILES["question_mark_black_mode"] if self.theme == "flatly" else APP_IMAGE_FILES["question_mark_white_mode"]


    @staticmethod
    def _has_fixed_skin(slot_data: Dict[str, Any]) -> bool:
        return int(slot_data.get("skin_id") or 0) > 0 or bool(str(slot_data.get("skin_name") or "").strip())


    @staticmethod
    def _has_random_skin(slot_data: Dict[str, Any]) -> bool:
        return (
            int(slot_data.get("random_skin_id") or 0) > 0
            or bool(str(slot_data.get("random_skin_name") or "").strip())
            or bool(slot_data.get("random_skin_pool"))
        )


    def _load_local_preview_asset(self, asset_rel_path: str, cache_key: tuple[Any, ...]) -> Optional[ImageTk.PhotoImage]:
        if cache_key in self.preview_icon_cache:
            return self.preview_icon_cache[cache_key]
        asset_path = resource_path(asset_rel_path)
        if not os.path.exists(asset_path):
            return None
        try:
            photo = ImageTk.PhotoImage(Image.open(asset_path).convert("RGBA").resize((self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), Image.LANCZOS))
            self.preview_icon_cache[cache_key] = photo
            return photo
        except Exception as e:
            logging.debug("Unable to load local preview asset %s: %s", asset_rel_path, e)
            return None


    def _on_feature_group_click(self, feature_key: str, event=None):
        self._toggle_main_preview_feature(feature_key)
        return "break"


    def _on_skin_preview_click(self, slot_key: str, event=None):
        self._toggle_main_preview_skin_slot(slot_key)
        return "break"


    def _queue_feature_preview_refresh(self, force: bool = False) -> None:
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return
        if self._preview_refresh_after_id is not None:
            return

        def _run():
            self._preview_refresh_after_id = None
            self._refresh_feature_preview(force=force)

        self._preview_refresh_after_id = self.root.after(80, _run)

    def _refresh_feature_preview(self, force: bool = False) -> None:
        if not self.feature_preview_frame or not self.feature_preview_frame.winfo_exists():
            return

        effective = self.get_effective_profile_config()
        params = self.get_params()
        preview_data = self._build_feature_preview_payload(params, effective)
        signature = self._build_preview_signature(preview_data)
        if not force and signature == self._last_preview_signature:
            return
        self._last_preview_signature = signature
        self._apply_preview_palette()

        for key, data in preview_data.items():
            status = self.feature_status_labels.get(key)
            if status:
                _, fg = self._get_feature_status_colors(data["style"], data["enabled"])
                status_text = "ON" if data["enabled"] else "OFF"
                if key == "skins":
                    skin_mode = str(data.get("mode") or "none").upper()
                    status_text = "OFF" if skin_mode == "NONE" else skin_mode
                status.configure(
                    text=status_text,
                    bg=THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])["window_bg"],
                    fg=fg,
                )
            for widget, value in zip(self.feature_icon_labels.get(key, []), data["values"]):
                if data.get("is_skin"):
                    self._set_skin_feature_icon(widget, value, data["enabled"], data["style"])
                else:
                    self._set_feature_icon(widget, value, data["is_champion"], data["enabled"], data["style"])


    def _set_feature_icon(self, widget: ttk.Label, name: str, is_champion: bool, enabled: bool, accent: str) -> None:
        display_name = name or "..."
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        if not name:
            self._set_preview_placeholder(widget)
            return

        cache_key = self._get_preview_icon_cache_key(name, is_champion, self.PREVIEW_ICON_SIZE)
        if cache_key in self.preview_icon_cache:
            cached_photo = self.preview_icon_cache[cache_key]
            widget.configure(text="", image=cached_photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
            widget.image = cached_photo
            return

        widget.configure(text="", image=self.preview_placeholder, compound="center", bg=palette["window_bg"], fg=palette["text"])
        widget.image = self.preview_placeholder

        def task():
            try:
                image = self.dd.get_champion_icon(name) if is_champion else self.dd.get_summoner_icon(name)
                if image:
                    resized_image = image.resize((self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), Image.LANCZOS)

                    def update_ui():
                        if widget.winfo_exists():
                            photo = ImageTk.PhotoImage(resized_image)
                            self.preview_icon_cache[cache_key] = photo
                            widget.configure(image=photo, text="", compound="center", bg=palette["window_bg"], fg=palette["text"])
                            widget.image = photo

                    widget.after(0, update_ui)
                else:
                    def update_ui_no_img():
                        if widget.winfo_exists():
                            self._set_preview_placeholder(widget)

                    widget.after(0, update_ui_no_img)
            except Exception as e:
                logging.debug("Main preview loading error for %s: %s", display_name, e)

        self.executor.submit(task)

    def _set_preview_placeholder(self, widget: ttk.Label, *, fg: Optional[str] = None) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        widget.configure(
            text="",
            image=self.preview_placeholder,
            compound="center",
            bg=palette["window_bg"],
            fg=fg or palette["muted"],
        )
        widget.image = self.preview_placeholder


    def _set_skin_feature_icon(self, widget: ttk.Label, skin_data: Dict[str, Any], enabled: bool, accent: str) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        if not isinstance(skin_data, dict):
            self._set_preview_placeholder(widget)
            return

        mode = str(skin_data.get("mode") or "none").strip().lower()
        if mode == "random":
            cache_key = ("asset", self._get_random_skin_placeholder_asset(), self.PREVIEW_ICON_SIZE)
            photo = self._load_local_preview_asset(self._get_random_skin_placeholder_asset(), cache_key)
            if photo:
                widget.configure(text="", image=photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
                widget.image = photo
            else:
                self._set_preview_placeholder(widget)
            return

        if mode != "fixed":
            self._set_preview_placeholder(widget)
            return

        champion_name = str(skin_data.get("champion_name") or "").strip()
        if not champion_name:
            self._set_preview_placeholder(widget)
            return

        preview_url = self.dd.get_skin_preview_url(
            champion_name,
            skin_id=skin_data.get("skin_id"),
            skin_num=skin_data.get("skin_num"),
            skin_name=skin_data.get("skin_name"),
        )
        if not preview_url:
            self._set_preview_placeholder(widget)
            return

        cache_suffix = skin_data.get("skin_num") or skin_data.get("skin_id") or skin_data.get("skin_name") or "0"
        cache_key = ("skin", champion_name, str(cache_suffix), self.PREVIEW_ICON_SIZE)
        if cache_key in self.preview_icon_cache:
            photo = self.preview_icon_cache[cache_key]
            widget.configure(text="", image=photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
            widget.image = photo
            return

        self._set_preview_placeholder(widget, fg=palette["text"])

        def task():
            try:
                image = self.dd.get_remote_image(preview_url, cache_key=f"main_preview_skin_{champion_name}_{cache_suffix}")
                if not image:
                    return
                resized_image = image.resize((self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), Image.LANCZOS)

                def update_ui():
                    if widget.winfo_exists():
                        photo = ImageTk.PhotoImage(resized_image)
                        self.preview_icon_cache[cache_key] = photo
                        widget.configure(text="", image=photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
                        widget.image = photo

                widget.after(0, update_ui)
            except Exception as e:
                logging.debug("Main preview loading error for skin %s: %s", skin_data.get("skin_name") or cache_suffix, e)

        self.executor.submit(task)

    def _toggle_main_preview_feature(self, feature_key: str) -> None:
        if feature_key == "presets":
            next_value = not self.is_main_preview_presets_enabled()
            self.set_main_preview_presets_enabled(next_value)
            self._sync_settings_window_if_open()
            state_label = "active" if next_value else "disabled"
            self.show_toast(f"{self.FEATURE_LABEL_MAP.get(feature_key, feature_key)} {state_label}.", duration=1200)
            return

        if feature_key == "skins":
            next_mode = self._cycle_main_preview_skin_mode()
            if next_mode is None:
                self.show_toast("No skin configured in presets.", duration=1400)
                return
            self._sync_settings_window_if_open()
            label_map = {
                "none": "Skin off.",
                "fixed": "Fixed skin enabled.",
                "random": "Random skins enabled.",
            }
            self.show_toast(label_map.get(next_mode, "Skin updated."), duration=1200)
            return

        param_key = self.FEATURE_PARAM_MAP.get(feature_key)
        if not param_key:
            return

        current_value = bool(self.get_params().get(param_key, True))
        next_value = not current_value
        self.update_param(param_key, next_value)
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win._sync_from_params()
        state_label = "active" if next_value else "disabled"
        self.show_toast(f"{self.FEATURE_LABEL_MAP.get(feature_key, feature_key)} {state_label}.", duration=1200)


    def _toggle_main_preview_skin_slot(self, slot_key: str) -> None:
        next_mode = self._cycle_main_preview_skin_mode_for_slot(slot_key)
        if next_mode is None:
            return
        self._sync_settings_window_if_open()
        slot_label = slot_key.replace("_", " ").title()
        label_map = {
            "none": f"{slot_label} skin off.",
            "fixed": f"{slot_label} fixed skin enabled.",
            "random": f"{slot_label} random skin enabled.",
        }
        self.show_toast(label_map.get(next_mode, f"{slot_label} skin updated."), duration=1100)


    def get_effective_profile_config(self) -> Dict[str, Any]:
        """Return the effective preview profile, even before the websocket is ready."""
        if self.ws_manager:
            return self.ws_manager.get_effective_profile_config()

        params = self.get_params()
        pick_slots = params.get("pick_slots", {})
        if not isinstance(pick_slots, dict):
            pick_slots = {}

        def _resolve_slot(slot_key: str, pick_key: str) -> Dict[str, Any]:
            slot = pick_slots.get(slot_key, {}) if isinstance(pick_slots.get(slot_key, {}), dict) else {}
            def _to_int(value: Any) -> int:
                try:
                    return int(value or 0)
                except (TypeError, ValueError):
                    return 0
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
                "random_skin_pool": (
                    [dict(e) for e in slot["random_skin_pool"]]
                    if isinstance(slot.get("random_skin_pool"), list) else []
                ),
            }

        slots = {
            slot_key: _resolve_slot(slot_key, f"selected_pick_{index}")
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

    def is_main_preview_presets_enabled(self) -> bool:
        params = self.get_params()
        effective = self.get_effective_profile_config()
        return (
            bool(params.get("auto_pick_enabled", True))
            and bool(params.get("auto_summoners_enabled", True))
            and bool(effective.get("presets_enabled", True))
        )


    def set_main_preview_presets_enabled(self, enabled: bool) -> None:
        self.update_param("auto_pick_enabled", enabled)
        self.update_param("auto_summoners_enabled", enabled)
        self.update_param("presets_enabled", enabled)



