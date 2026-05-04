"""
FILE NAME: src/ui/settings_runes.py
GLOBAL PURPOSE:
- Mixin that provides rune-picker and rune-configuration methods for SettingsWindow.
- Groups rune page selection, icon rendering, keystone resolution, and persistence together.

DEPENDENCIES:
Used by:
- src/ui/settings_window.py via SettingsWindow inheritance.
Uses:
- Standard library: logging, typing
- Third-party libraries: Pillow, ttkbootstrap
- Local modules: src.config
"""

import logging
from typing import Any, Dict

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from ..config import URL_PHASE_RUSH_ICON


class SettingsRunesMixin:
    """Rune page selection and configuration helpers for the settings window."""

    def _find_rune_keystone_path(self, page: Dict[str, Any], primary_style: Dict[str, Any]) -> str:
        selected_ids = page.get("selectedPerkIds") if isinstance(page, dict) else []
        keystone_id = self._safe_int(selected_ids[0]) if isinstance(selected_ids, list) and selected_ids else 0
        perks = primary_style.get("perks", []) if isinstance(primary_style, dict) else []

        if keystone_id > 0 and hasattr(self.parent, "dd"):
            icon_path = self.parent.dd.get_rune_perk_icon_path(keystone_id)
            if icon_path:
                return icon_path

        if keystone_id > 0:
            for perk in perks if isinstance(perks, list) else []:
                if isinstance(perk, dict) and self._safe_int(perk.get("id")) == keystone_id:
                    return str(perk.get("iconPath") or "")
        if isinstance(perks, list) and perks and isinstance(perks[0], dict):
            return str(perks[0].get("iconPath") or "")
        return ""

    def _get_rune_page_icon_paths(
        self,
        page: Dict[str, Any],
        styles: Dict[Any, Any],
    ) -> tuple[str, str]:
        primary_style = styles.get(page.get("primaryStyleId"), {}) if isinstance(styles, dict) else {}
        sub_style = styles.get(page.get("subStyleId"), {}) if isinstance(styles, dict) else {}
        sub_style_icon_path = str(sub_style.get("iconPath") or "") if isinstance(sub_style, dict) else ""
        keystone_path = self._find_rune_keystone_path(page, primary_style)
        return keystone_path, sub_style_icon_path

    @classmethod
    def _split_rune_page_perk_ids(cls, page: Dict[str, Any]) -> tuple[list[int], list[int], list[int]]:
        selected_ids = page.get("selectedPerkIds") if isinstance(page, dict) else []
        if not isinstance(selected_ids, list):
            selected_ids = []
        normalized_ids = [cls._safe_int(perk_id) for perk_id in selected_ids]
        normalized_ids = [perk_id for perk_id in normalized_ids if perk_id > 0]
        return normalized_ids[:4], normalized_ids[4:6], normalized_ids[6:9]

    def _load_rune_perk_icon_into_label(
        self,
        label_widget: ttk.Label,
        perk_id: Any,
        *,
        size: tuple[int, int],
    ) -> None:
        normalized_perk_id = self._safe_int(perk_id)
        if normalized_perk_id <= 0:
            return

        def task():
            try:
                icon_path = self.parent.dd.get_rune_perk_icon_path(normalized_perk_id)
                perk_name = self.parent.dd.get_rune_perk_name(normalized_perk_id)
                if not icon_path:
                    return
                img = self.parent.dd.get_rune_perk_icon(icon_path)
                if not img:
                    return
                img = img.resize(size, Image.LANCZOS)

                def update_ui():
                    if label_widget.winfo_exists():
                        photo = ImageTk.PhotoImage(img)
                        label_widget.configure(image=photo)
                        label_widget.image = photo
                        self._attach_tooltip(label_widget, perk_name or f"Rune {normalized_perk_id}")

                label_widget.after(0, update_ui)
            except Exception as e:
                logging.debug("Rune perk label load error: %s", e)

        self.parent.executor.submit(task)

    def _load_rune_style_icon_into_label(
        self,
        label_widget: ttk.Label,
        style_icon_path: str,
        *,
        size: tuple[int, int],
        tooltip_text: str = "",
    ) -> None:
        if not style_icon_path:
            return

        def task():
            try:
                img = self.parent.dd.get_rune_style_icon(style_icon_path)
                if not img:
                    return
                img = img.resize(size, Image.LANCZOS)

                def update_ui():
                    if label_widget.winfo_exists():
                        photo = ImageTk.PhotoImage(img)
                        label_widget.configure(image=photo)
                        label_widget.image = photo
                        if tooltip_text:
                            self._attach_tooltip(label_widget, tooltip_text)

                label_widget.after(0, update_ui)
            except Exception as e:
                logging.debug("Rune style label load error: %s", e)

        self.parent.executor.submit(task)

    def _open_rune_picker(self, slot_key: str) -> None:
        if not self.presets_enabled_var.get():
            return

        popup = ttk.Toplevel(self.window)
        if self.window._icon_img:
            popup.iconphoto(False, self.window._icon_img)
        popup.title(f"{self._get_preset_label(slot_key)} - Rune Page")
        popup.geometry(f"460x520+{self.window.winfo_x()+60}+{self.window.winfo_y()+80}")
        popup.resizable(False, False)
        popup.transient(self.window)

        def _close_popup() -> None:
            self.rune_picker_window = None
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _close_popup)
        self.rune_picker_window = popup

        container = ttk.Frame(popup, padding=12)
        container.pack(fill="both", expand=True)

        status_var = tk.StringVar(value="")
        status_label = tk.Label(
            container,
            textvariable=status_var,
            font=("Segoe UI", 9, "bold"),
            justify="left",
            anchor="w",
            wraplength=420,
        )
        status_label.pack(fill="x", pady=(0, 6))

        if self.parent and hasattr(self.parent, "ws_manager"):
            ws = self.parent.ws_manager
        else:
            ws = None

        if not ws or not getattr(ws, "is_active", False):
            status_var.set("Impossible to fetch runes: LCU is not detected. Launch League of Legends.")
            status_label.configure(fg="orange")
        else:
            status_var.set("")

        header = ttk.Frame(container)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Select a rune page", font=("Segoe UI", 13, "bold")).pack(side="left")

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="Fetch runes", bootstyle="info-outline", command=lambda: _refresh_pages(), width=12
                   ).pack(side="left", padx=(0, 6))

        def _build_auto_apply_row():
            """Add the auto-apply toggle as the first row in the pages list."""
            slot_config = self._get_effective_pick_slot_config(slot_key)
            auto_apply = bool(slot_config.get("rune_auto_apply", True))
            row = ttk.Frame(pages_frame)
            row.pack(fill="x", pady=2)
            if auto_apply:
                btn = ttk.Button(
                    row,
                    text="Don't apply runes for this preset",
                    bootstyle="warning-outline",
                    command=lambda: _toggle_auto_apply(),
                )
            else:
                btn = ttk.Button(
                    row,
                    text="Apply runes for this preset",
                    bootstyle="warning",
                    command=lambda: _toggle_auto_apply(),
                )
            btn.pack(fill="x", expand=True)

        def _toggle_auto_apply():
            slot_config = self._get_effective_pick_slot_config(slot_key)
            current_auto_apply = bool(slot_config.get("rune_auto_apply", True))
            if current_auto_apply:
                self._save_rune_page_for_slot(slot_key, 0, "", auto_apply=False)
                self._refresh_rune_buttons()
                _close_popup()
            else:
                current_page_id = int(slot_config.get("rune_page_id") or 0)
                current_page_name = str(slot_config.get("rune_page_name") or "")
                self._save_rune_page_for_slot(
                    slot_key, current_page_id, current_page_name,
                    auto_apply=True,
                )
                self._refresh_rune_buttons()
                _refresh_pages()

        def _select_page(page_id: int, page_name: str, keystone_path: str = "", sub_style_path: str = "") -> None:
            page_name = self._strip_active_suffix(page_name)
            self._save_rune_page_for_slot(
                slot_key, page_id, page_name,
                auto_apply=True,
                keystone_path=keystone_path,
                sub_style_icon_path=sub_style_path,
            )
            self._refresh_rune_buttons()
            _close_popup()

        def _refresh_pages():
            for widget in pages_frame.winfo_children():
                widget.destroy()

            _build_auto_apply_row()
            ttk.Separator(pages_frame).pack(fill="x", pady=(6, 4))

            if not ws or not getattr(ws, "is_active", False):
                status_var.set("Impossible to fetch runes: LCU is not detected. Launch League of Legends.")
                status_label.configure(fg="orange")
                return
            status_var.set("")

            pages = ws.fetch_rune_pages()
            if not pages:
                ttk.Label(pages_frame, text="No valid rune pages found on your account.", bootstyle="secondary").pack(pady=10)
                ttk.Label(pages_frame, text="Create a rune page in the League client first.", bootstyle="secondary").pack(pady=(0, 10))
                return

            styles = ws.fetch_rune_styles()
            current_slot_config = self._get_effective_pick_slot_config(slot_key)
            current_rune_page_id = int(current_slot_config.get("rune_page_id") or 0)
            is_light_theme = str(self.theme_var.get() or "").strip().lower() == "flatly"
            card_bg = "#f7f9fb" if is_light_theme else "#202020"
            card_selected_bg = "#3b6793"
            card_border = "#8ba3b8" if is_light_theme else "#454545"
            text_fg = "#101820" if is_light_theme else "#f4f4f4"
            selected_text_fg = "#ffffff"
            muted_fg = "#52616f" if is_light_theme else "#b7b7b7"

            def _bind_select(widget, page_id: int, page_name: str, keystone_path: str = "", sub_style_path: str = "") -> None:
                widget.bind("<Button-1>", lambda _event, pid=page_id, pname=page_name, kp=keystone_path, sp=sub_style_path: _select_page(pid, pname, keystone_path=kp, sub_style_path=sp))
                try:
                    widget.configure(cursor="hand2")
                except tk.TclError:
                    pass

            def _make_icon_label(parent_widget, size: tuple[int, int], bg: str) -> tk.Label:
                placeholder = ImageTk.PhotoImage(Image.new("RGBA", size, (0, 0, 0, 0)))
                label = tk.Label(parent_widget, image=placeholder, bg=bg, borderwidth=0, highlightthickness=0)
                label.image = placeholder
                return label

            def _add_group_separator(parent_widget, bg: str) -> None:
                tk.Label(parent_widget, text="-", bg=bg, fg=muted_fg, borderwidth=0).pack(side="left", padx=(7, 7))

            for index_page, page in enumerate(pages):
                if index_page > 0:
                    ttk.Separator(pages_frame).pack(fill="x", pady=(4, 4))
                page_id = page["id"]
                page_name = self._strip_active_suffix(page["name"] or f"Page {page_id}")
                page_icon_paths = self._get_rune_page_icon_paths(page, styles) if isinstance(styles, dict) else ("", "")
                page_keystone_path, page_sub_style_path = page_icon_paths
                is_selected = page_id == current_rune_page_id
                row_bg = card_selected_bg if is_selected else card_bg
                row = tk.Frame(
                    pages_frame,
                    bg=row_bg,
                    highlightbackground=card_border,
                    highlightcolor=card_border,
                    highlightthickness=1,
                    borderwidth=0,
                    padx=8,
                    pady=6,
                )
                row.pack(fill="x", pady=(0, 0))
                _bind_select(row, page_id, page_name, keystone_path=page_keystone_path, sub_style_path=page_sub_style_path)

                title = tk.Label(
                    row,
                    text=page_name,
                    bg=row_bg,
                    fg=selected_text_fg if is_selected else text_fg,
                    anchor="w",
                    font=("Segoe UI", 9, "bold" if is_selected else "normal"),
                    borderwidth=0,
                )
                title.pack(fill="x")
                _bind_select(title, page_id, page_name, keystone_path=page_keystone_path, sub_style_path=page_sub_style_path)

                icons_row = tk.Frame(row, bg=row_bg, borderwidth=0, highlightthickness=0)
                icons_row.pack(fill="x", pady=(5, 0))
                _bind_select(icons_row, page_id, page_name, keystone_path=page_keystone_path, sub_style_path=page_sub_style_path)

                if isinstance(styles, dict):
                    primary_ids, secondary_ids, shard_ids = self._split_rune_page_perk_ids(page)
                    sub_style = styles.get(page.get("subStyleId"), {})
                    sub_style_icon_path = str(sub_style.get("iconPath") or "") if isinstance(sub_style, dict) else ""

                    for index, perk_id in enumerate(primary_ids):
                        size = (30, 30) if index == 0 else (26, 26)
                        label = _make_icon_label(icons_row, size, row_bg)
                        label.pack(side="left", padx=(0, 4))
                        _bind_select(label, page_id, page_name)
                        self._load_rune_perk_icon_into_label(
                            label,
                            perk_id,
                            size=size,
                        )

                    if primary_ids and (sub_style_icon_path or secondary_ids or shard_ids):
                        _add_group_separator(icons_row, row_bg)

                    if sub_style_icon_path:
                        sub_style_name = str(sub_style.get("name") or "") if isinstance(sub_style, dict) else ""
                        label = _make_icon_label(icons_row, (26, 26), row_bg)
                        label.pack(side="left", padx=(0, 4))
                        _bind_select(label, page_id, page_name)
                        self._load_rune_style_icon_into_label(
                            label,
                            sub_style_icon_path,
                            size=(26, 26),
                            tooltip_text=sub_style_name,
                        )

                    for index, perk_id in enumerate(secondary_ids):
                        label = _make_icon_label(icons_row, (26, 26), row_bg)
                        label.pack(side="left", padx=(0, 4))
                        _bind_select(label, page_id, page_name)
                        self._load_rune_perk_icon_into_label(
                            label,
                            perk_id,
                            size=(26, 26),
                        )

                    if (sub_style_icon_path or secondary_ids) and shard_ids:
                        _add_group_separator(icons_row, row_bg)

                    for index, perk_id in enumerate(shard_ids):
                        label = _make_icon_label(icons_row, (24, 24), row_bg)
                        label.pack(side="left", padx=(0, 4))
                        _bind_select(label, page_id, page_name)
                        self._load_rune_perk_icon_into_label(
                            label,
                            perk_id,
                            size=(24, 24),
                        )

        pages_frame = ttk.Frame(container)
        pages_frame.pack(fill="both", expand=True)

        if popup.winfo_exists():
            popup.after(100, _refresh_pages)

    def _save_rune_page_for_slot(self, slot_key: str, page_id: int, page_name: str, auto_apply: bool = True, keystone_path: str = "", sub_style_icon_path: str = "") -> None:
        page_name = self._strip_active_suffix(page_name)
        params = self.parent.get_params()
        pick_slots = params.get("pick_slots", {})
        new_slots = {s: (d.copy() if isinstance(d, dict) else {}) for s, d in pick_slots.items()}
        slot_data = new_slots.get(slot_key, {})
        slot_data["rune_page_id"] = page_id
        slot_data["rune_page_name"] = page_name
        slot_data["rune_auto_apply"] = auto_apply
        slot_data["rune_keystone_path"] = keystone_path
        slot_data["rune_sub_style_icon_path"] = sub_style_icon_path
        new_slots[slot_key] = slot_data
        self.parent.update_param("pick_slots", new_slots)

    def _refresh_rune_buttons(self) -> None:
        for slot_key, button in self.pick_rune_buttons.items():
            if not button.winfo_exists():
                continue
            slot_config = self._get_effective_pick_slot_config(slot_key)
            rune_page_id = int(slot_config.get("rune_page_id") or 0)
            rune_page_name = self._strip_active_suffix(str(slot_config.get("rune_page_name") or ""))
            if rune_page_id > 0 and rune_page_name:
                auto_apply = bool(slot_config.get("rune_auto_apply", True))
                if not auto_apply:
                    base_name = rune_page_name if len(rune_page_name) <= 12 else rune_page_name[:10].rstrip() + "..."
                    label = f"{base_name} · Auto apply off"
                else:
                    label = rune_page_name
                display_name = label if len(label) <= 30 else label[:28].rstrip() + "..."
                button.configure(text=f"  {display_name}", image="", compound="left")
                self._load_rune_page_composite_into_btn(button, rune_page_id, slot_key)
            else:
                button.configure(text="  Runes", image="", compound="left")
                self._load_rune_img_into_btn(
                    button,
                    URL_PHASE_RUSH_ICON,
                    size=self.PICK_ICON_SIZE,
                )

    def _load_rune_page_composite_into_btn(self, button: ttk.Button, rune_page_id: int, slot_key: str) -> None:
        ws = getattr(self.parent, "ws_manager", None)

        def _update_btn_with_image(img: Image.Image) -> None:
            if button.winfo_exists():
                photo = ImageTk.PhotoImage(img)
                button.configure(image=photo)
                button.image = photo

        slot_config = self._get_effective_pick_slot_config(slot_key)
        saved_keystone = str(slot_config.get("rune_keystone_path") or "")
        saved_sub_style = str(slot_config.get("rune_sub_style_icon_path") or "")

        if saved_keystone:
            def use_saved_task():
                try:
                    composite = self.parent.dd.compose_rune_button_icon(
                        saved_keystone,
                        saved_sub_style,
                        size=self.RUNE_BUTTON_ICON_SIZE,
                    )
                    if composite:
                        button.after(0, lambda img=composite: _update_btn_with_image(img))
                    else:
                        self._load_rune_img_into_btn(
                            button,
                            URL_PHASE_RUSH_ICON,
                            size=self.PICK_ICON_SIZE,
                        )
                except Exception as e:
                    logging.debug("Rune composite (saved paths) load error: %s", e)
                    self._load_rune_img_into_btn(
                        button,
                        URL_PHASE_RUSH_ICON,
                        size=self.PICK_ICON_SIZE,
                    )

            self.parent.executor.submit(use_saved_task)
            return

        if not ws:
            self._load_rune_img_into_btn(
                button,
                URL_PHASE_RUSH_ICON,
                size=self.PICK_ICON_SIZE,
            )
            return

        def task():
            try:
                pages = ws.fetch_rune_pages()
                page = next((p for p in pages if p["id"] == rune_page_id), None)
                if not page:
                    return
                styles = ws.fetch_rune_styles()
                keystone_path, sub_style_icon_path = self._get_rune_page_icon_paths(page, styles)
                composite = self.parent.dd.compose_rune_button_icon(
                    keystone_path,
                    sub_style_icon_path,
                    size=self.RUNE_BUTTON_ICON_SIZE,
                )
                if composite:
                    button.after(0, lambda img=composite: _update_btn_with_image(img))
                else:
                    self._load_rune_img_into_btn(
                        button,
                        URL_PHASE_RUSH_ICON,
                        size=self.PICK_ICON_SIZE,
                    )
            except Exception as e:
                logging.debug("Rune composite icon load error: %s", e)
                self._load_rune_img_into_btn(
                    button,
                    URL_PHASE_RUSH_ICON,
                    size=self.PICK_ICON_SIZE,
                )

        self.parent.executor.submit(task)

    def _load_rune_img_into_btn(
        self,
        btn_widget: ttk.Button,
        asset_path: str,
        *,
        size: tuple[int, int] = (40, 40),
    ) -> None:
        def task():
            try:
                img = self.parent.dd.get_rune_perk_icon(asset_path)
                if not img:
                    return
                img = img.resize(size, Image.LANCZOS)

                def update_ui():
                    if btn_widget.winfo_exists():
                        photo = ImageTk.PhotoImage(img)
                        btn_widget.configure(image=photo)
                        btn_widget.image = photo

                btn_widget.after(0, update_ui)
            except Exception as e:
                logging.debug("Rune image loading error for %s: %s", asset_path, e)

        self.parent.executor.submit(task)
