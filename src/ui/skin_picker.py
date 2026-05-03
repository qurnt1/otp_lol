"""
FILE NAME: src/ui/skin_picker.py
GLOBAL PURPOSE:
- Build the skin-selection dialog used by the settings window.
- Merge catalog metadata with detected ownership and random-pool selections.
- Keep skin-picker-specific sorting, confirmation, and preview behavior isolated from the main settings module.

KEY FUNCTIONS:
- open_skin_picker: Open the skin picker for one preset slot.
- _merge_catalog_and_owned_skins: Merge catalog entries with owned-skin metadata.
- _sort_skins_for_display: Prioritize selected skins at the top of the picker.
- _confirm_unowned_skin_selection: Confirm selection when a skin is not detected on the account.

AUDIENCE & LOGIC:
Why:
This module exists so skin-picking rules, ownership prompts, and preview ordering remain maintainable outside the already large settings module.
For whom:
Developers maintaining skin selection UX and random skin pool behavior.

DEPENDENCIES:
Used by:
- src.ui.settings_window
Uses:
- Standard library: tkinter, typing
- Third-party library: ttkbootstrap
- Local modules: src.config
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

from ..config import THEME_PALETTE

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


def _merge_catalog_and_owned_skins(
    catalog_skins: List[Dict[str, Any]],
    owned_skins: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge catalog skin entries with owned-skin metadata while preserving one row per skin."""
    owned_by_id: dict[int, Dict[str, Any]] = {}
    for entry in owned_skins:
        if not isinstance(entry, dict):
            continue
        skin_id = int(entry.get("skin_id") or 0)
        if skin_id <= 0:
            continue
        owned_by_id[skin_id] = dict(entry)

    merged: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    for entry in catalog_skins:
        if not isinstance(entry, dict):
            continue
        skin_id = int(entry.get("skin_id") or 0)
        if skin_id <= 0 or skin_id in seen_ids:
            continue
        seen_ids.add(skin_id)
        owned_entry = owned_by_id.get(skin_id, {})
        merged_entry = dict(entry)
        for key, value in owned_entry.items():
            if value not in {"", None}:
                merged_entry[key] = value
        is_default_skin = int(merged_entry.get("skin_num") or 0) == 0
        merged_entry["owned"] = skin_id in owned_by_id or is_default_skin
        merged_entry["preview_url"] = (
            merged_entry.get("preview_url")
            or merged_entry.get("tile_url")
            or merged_entry.get("centered_splash_url")
            or merged_entry.get("uncentered_splash_url")
            or merged_entry.get("splash_url")
            or ""
        )
        merged.append(merged_entry)

    for skin_id, entry in owned_by_id.items():
        if skin_id in seen_ids:
            continue
        merged_entry = dict(entry)
        merged_entry["owned"] = True
        merged_entry["preview_url"] = (
            merged_entry.get("preview_url")
            or merged_entry.get("tile_url")
            or merged_entry.get("splash_url")
            or ""
        )
        merged.append(merged_entry)
    return merged


def _get_picker_image_url(skin: Dict[str, Any]) -> str:
    """Return the best available preview image URL for the picker card."""
    return str(
        skin.get("centered_splash_url")
        or skin.get("splash_url")
        or skin.get("tile_url")
        or skin.get("preview_url")
        or ""
    )


def _sort_skins_for_display(
    skins: List[Dict[str, Any]],
    *,
    mode: str,
    fixed_skin_id: int = 0,
    pool_ids: Optional[set[int]] = None,
) -> List[Dict[str, Any]]:
    """Move selected skins to the top while keeping the remaining list order stable."""
    normalized_mode = str(mode or "fixed").strip().lower()
    selected_ids = set(pool_ids or set()) if normalized_mode == "random" else set()
    prioritized: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []
    for skin in skins:
        skin_id = int(skin.get("skin_id") or 0)
        is_selected = skin_id in selected_ids if normalized_mode == "random" else skin_id == int(fixed_skin_id or 0)
        (prioritized if is_selected else others).append(skin)
    return [*prioritized, *others]


def _confirm_unowned_skin_selection(
    skin: Dict[str, Any],
    *,
    owner: Optional["SettingsWindow"] = None,
    ask_fn: Optional[Any] = None,
) -> bool:
    """Ask for confirmation before selecting a skin that was not detected on the account."""
    if bool(skin.get("owned")):
        return True
    if ask_fn is not None:
        return bool(
            ask_fn(
                "Skin not detected",
                "Warning: this skin is not detected on this account.\n"
                "Are you sure you want to select it?",
            )
        )
    if owner is None:
        return False

    prompt = ttk.Toplevel(owner.window)
    if getattr(owner.window, "_icon_img", None):
        prompt.iconphoto(False, owner.window._icon_img)
    prompt.title("Skin not detected")
    prompt.resizable(False, False)
    prompt.transient(owner.window)
    prompt.geometry(f"380x140+{owner.window.winfo_x()+110}+{owner.window.winfo_y()+120}")

    result = False

    def _on_yes():
        nonlocal result
        result = True
        prompt.destroy()

    prompt.protocol("WM_DELETE_WINDOW", prompt.destroy)

    frame = ttk.Frame(prompt, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="Warning: this skin is not detected on this account.\nAre you sure you want to select it?",
        wraplength=340,
        font=("Segoe UI", 10),
    ).pack(pady=(0, 16))

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e")
    ttk.Button(buttons, text="Yes", bootstyle="primary", width=10, command=_on_yes).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="No", bootstyle="secondary-outline", width=10, command=prompt.destroy).pack(side="left")

    prompt.grab_set()
    prompt.focus_force()
    prompt.wait_window()
    return result


def _get_skin_fetch_status_text(result: Dict[str, Any]) -> str:
    """Convert an owned-skins fetch result into a user-facing status message."""
    if result.get("ok"):
        return ""
    lcu_message = "Impossible to fetch skins: LCU is not detected. To update the list, launch League of Legends."
    message = str(result.get("message") or "").strip()
    if not message:
        return lcu_message
    lowered = message.lower()
    if "connection" in lowered or "league of legends" in lowered or "lol client" in lowered or "lcu" in lowered:
        return lcu_message
    return f"Unable to fetch owned skins: {message}"


def _get_skin_picker_colors(theme_name: str) -> Dict[str, str]:
    """Return high-contrast colors for the skin picker controls."""
    palette = THEME_PALETTE.get(theme_name, THEME_PALETTE["darkly"])
    if theme_name == "flatly":
        return {
            "window_bg": palette["window_bg"],
            "surface_bg": "#ffffff",
            "surface_hover": "#f1f5f9",
            "selected_bg": "#3f4a3d",
            "selected_hover": "#4a5747",
            "selected_text": "#ffffff",
            "text": palette["text"],
            "muted": "#4b5563",
            "border": "#cbd5e1",
            "active_border": "#7f9a7a",
            "warning": "#c9973a",
            "button_bg": "#f8fafc",
            "button_text": "#ffffff",
            "inactive_button_text": "#1f2937",
        }
    return {
        "window_bg": palette["window_bg"],
        "surface_bg": "#242424",
        "surface_hover": "#303030",
        "selected_bg": "#3f4a3d",
        "selected_hover": "#4a5747",
        "selected_text": "#ffffff",
        "text": palette["text"],
        "muted": "#c3c3c3",
        "border": "#4a4a4a",
        "active_border": "#7f9a7a",
        "warning": "#d6a84f",
        "button_bg": "#242424",
        "button_text": palette["text"],
        "inactive_button_text": palette["text"],
    }


def open_skin_picker(owner: "SettingsWindow", slot_key: str) -> None:
    """Open the skin picker for a preset slot."""
    if getattr(owner, "skin_picker_window", None) and owner.skin_picker_window.winfo_exists():
        owner.skin_picker_window.destroy()

    picker = ttk.Toplevel(owner.window)
    owner.skin_picker_window = picker
    if owner.window._icon_img:
        picker.iconphoto(False, owner.window._icon_img)
    picker.title(f"{owner._get_preset_label(slot_key)} - Skin")
    picker.resizable(False, False)
    picker.transient(owner.window)
    picker.geometry(f"380x620+{owner.window.winfo_x()+60}+{owner.window.winfo_y()+80}")
    theme_name = getattr(owner.parent, "theme", "darkly")
    colors = _get_skin_picker_colors(theme_name)
    picker.configure(bg=colors["window_bg"])

    def on_close() -> None:
        if picker.winfo_exists():
            picker.destroy()
        owner.skin_picker_window = None

    picker.protocol("WM_DELETE_WINDOW", on_close)

    # The picker depends on the currently assigned champion because ownership and
    # preview data are champion-specific.
    champion_name = owner._get_slot_champion_name(slot_key)
    champion_id = owner.parent.dd.resolve_champion(champion_name) if champion_name not in {"", "(None)"} else None
    ws_manager = getattr(owner.parent, "ws_manager", None)
    picker_mode_var = tk.StringVar(
        value="random" if owner._get_effective_pick_slot_config(slot_key).get("skin_mode") == "random" else "fixed"
    )
    available_skins: list[Dict[str, Any]] = []
    catalog_skins: list[Dict[str, Any]] = []

    container = tk.Frame(picker, bg=colors["window_bg"], padx=12, pady=12)
    container.pack(fill="both", expand=True)

    mode_bar = tk.Frame(container, bg=colors["window_bg"])
    mode_bar.pack(fill="x")
    mode_bar.columnconfigure(0, weight=1, uniform="skin_mode")
    mode_bar.columnconfigure(1, weight=1, uniform="skin_mode")
    mode_option_widgets: dict[str, tuple[tk.Frame, tk.Label]] = {}

    def create_mode_option(mode: str, text: str, *, column: int, padx: tuple[int, int]) -> None:
        option_frame = tk.Frame(
            mode_bar,
            bd=0,
            bg=colors["button_bg"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            cursor="hand2",
        )
        option_frame.grid(row=0, column=column, sticky="ew", padx=padx)
        option_label = tk.Label(
            option_frame,
            text=text,
            bg=colors["button_bg"],
            fg=colors["inactive_button_text"],
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=10,
            pady=8,
        )
        option_label.pack(fill="x")
        mode_option_widgets[mode] = (option_frame, option_label)

    create_mode_option("fixed", "One skin", column=0, padx=(0, 4))
    create_mode_option("random", "Random skin list", column=1, padx=(4, 0))

    status_var = tk.StringVar(value="")
    status_label = tk.Label(
        container,
        textvariable=status_var,
        bg=colors["window_bg"],
        fg=colors["warning"],
        font=("Segoe UI", 9, "bold"),
        justify="left",
        anchor="w",
        wraplength=340,
    )
    status_label.pack(fill="x", pady=(8, 0))
    if not ws_manager or not getattr(ws_manager, "is_active", False):
        status_var.set(_get_skin_fetch_status_text({"ok": False, "message": "LCU is not detected."}))

    scroll_container = ScrolledFrame(container, autohide=False)
    scroll_container.pack(fill="both", expand=True, pady=(10, 0))
    list_frame = tk.Frame(scroll_container, bg=colors["window_bg"])
    list_frame.pack(fill="both", expand=True)

    def get_current_config() -> Dict[str, Any]:
        return owner._get_effective_pick_slot_config(slot_key)

    def get_pool_ids() -> set[int]:
        return {int(entry.get("skin_id") or 0) for entry in owner._get_random_skin_pool(slot_key)}

    def get_owned_skins() -> list[Dict[str, Any]]:
        return [skin for skin in available_skins if bool(skin.get("owned"))]

    def get_other_skins() -> list[Dict[str, Any]]:
        return [skin for skin in available_skins if not bool(skin.get("owned"))]

    def refresh_parent_buttons() -> None:
        owner._refresh_skin_buttons()

    def apply_mode_option_colors(mode: str, *, hover: bool = False) -> None:
        option_frame, option_label = mode_option_widgets[mode]
        active_mode = picker_mode_var.get()
        is_active = active_mode == mode
        bg = colors["selected_bg"] if is_active else colors["surface_hover" if hover else "button_bg"]
        if is_active and hover:
            bg = colors["selected_hover"]
        fg = colors["selected_text"] if is_active else colors["inactive_button_text"]
        border = colors["active_border"] if is_active else colors["border"]
        option_frame.configure(bg=bg, highlightbackground=border)
        option_label.configure(bg=bg, fg=fg)

    def refresh_mode_options() -> None:
        for mode in mode_option_widgets:
            apply_mode_option_colors(mode)

    def set_picker_mode(mode: str) -> None:
        picker_mode_var.set("random" if mode == "random" else "fixed")
        refresh_mode_options()
        populate_list()

    def choose_random_preview(selected_skins: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not selected_skins:
            return None
        current_config = get_current_config()
        current_random_skin_id = int(current_config.get("random_skin_id") or 0)
        if current_random_skin_id:
            for skin in selected_skins:
                if int(skin.get("skin_id") or 0) == current_random_skin_id:
                    return skin
        return owner._choose_random_skin_entry(selected_skins)

    def toggle_skin_selection(skin: Dict[str, Any]) -> None:
        skin_id = int(skin.get("skin_id") or 0)
        active_mode = picker_mode_var.get()
        if active_mode == "fixed":
            current_config = get_current_config()
            if int(current_config.get("skin_id") or 0) == skin_id and current_config.get("skin_mode") == "fixed":
                owner._clear_pick_slot_skin(slot_key)
            else:
                if not _confirm_unowned_skin_selection(skin, owner=owner):
                    return
                owner._set_pick_slot_skin_selection(slot_key, mode="fixed", fixed_skin=skin)
            refresh_parent_buttons()
            populate_list()
            return

        pool_ids = get_pool_ids()
        if skin_id in pool_ids:
            pool_ids.discard(skin_id)
        else:
            if not _confirm_unowned_skin_selection(skin, owner=owner):
                return
            pool_ids.add(skin_id)
        selected_skins = [entry for entry in available_skins if int(entry.get("skin_id") or 0) in pool_ids]
        owner._set_random_skin_pool(slot_key, selected_skins)
        if not selected_skins:
            owner._set_pick_slot_skin_selection(slot_key, mode="none")
        else:
            chosen = choose_random_preview(selected_skins)
            if chosen:
                owner._set_pick_slot_skin_selection(slot_key, mode="random", random_skin=chosen)
        refresh_parent_buttons()
        populate_list()

    def render_skin_row(parent: ttk.Frame, skin: Dict[str, Any]) -> None:
        current_config = get_current_config()
        active_mode = picker_mode_var.get()
        skin_id = int(skin.get("skin_id") or 0)
        selected = (
            skin_id in get_pool_ids()
            if active_mode == "random"
            else int(current_config.get("skin_id") or 0) == skin_id and current_config.get("skin_mode") == "fixed"
        )
        row = tk.Frame(
            parent,
            bd=0,
            highlightthickness=1,
            highlightbackground=colors["border"],
            cursor="hand2",
            padx=8,
            pady=8,
        )
        row.pack(fill="x", pady=4)
        image_label = tk.Label(row, bg=colors["surface_bg"], cursor="hand2")
        image_label.pack(side="left", padx=(0, 12))
        name_label = tk.Label(
            row,
            text=str(skin.get("skin_name") or ""),
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        name_label.pack(side="left", fill="x", expand=True)

        def apply_row_colors(*, hover: bool = False) -> None:
            row_bg = colors["selected_bg"] if selected else colors["surface_hover" if hover else "surface_bg"]
            if selected and hover:
                row_bg = colors["selected_hover"]
            row_fg = colors["selected_text"] if selected else colors["text"]
            if not selected and not bool(skin.get("owned")):
                row_fg = colors["muted"]
            row_border = colors["warning"] if selected else colors["border"]
            row.configure(bg=row_bg, highlightbackground=row_border)
            image_label.configure(bg=row_bg)
            name_label.configure(bg=row_bg, fg=row_fg)

        def on_row_click(_event: object) -> None:
            toggle_skin_selection(skin)

        def on_row_enter(_event: object) -> None:
            apply_row_colors(hover=True)

        def on_row_leave(_event: object) -> None:
            apply_row_colors(hover=False)

        for widget in (row, image_label, name_label):
            widget.bind("<Button-1>", on_row_click)
            widget.bind("<Enter>", on_row_enter)
            widget.bind("<Leave>", on_row_leave)

        apply_row_colors()
        preview_url = _get_picker_image_url(skin)
        if preview_url:
            owner._load_remote_img_into_btn(
                image_label,
                preview_url,
                cache_key=(
                    f"skin_picker_{champion_name}_{slot_key}_{skin['skin_num'] or skin['skin_id']}_"
                    f"{'owned' if skin.get('owned') else 'other'}"
                ),
                size=(88, 50),
                cover=True,
            )

    def render_section(parent: tk.Frame, title: str, skins: list[Dict[str, Any]], empty_message: str) -> None:
        section = tk.Frame(parent, bg=colors["window_bg"])
        section.pack(fill="x", pady=(0, 12))
        tk.Label(
            section,
            text=title,
            bg=colors["window_bg"],
            fg=colors["text"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        if not skins:
            tk.Label(
                section,
                text=empty_message,
                bg=colors["window_bg"],
                fg=colors["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x")
            return
        for skin in skins:
            render_skin_row(section, skin)

    def populate_list() -> None:
        current_config = get_current_config()
        active_mode = picker_mode_var.get()
        fixed_skin_id = int(current_config.get("skin_id") or 0)
        pool_ids = get_pool_ids()
        for widget in list_frame.winfo_children():
            widget.destroy()

        owned_skins = _sort_skins_for_display(
            get_owned_skins(),
            mode=active_mode,
            fixed_skin_id=fixed_skin_id,
            pool_ids=pool_ids,
        )
        other_skins = _sort_skins_for_display(
            get_other_skins(),
            mode=active_mode,
            fixed_skin_id=fixed_skin_id,
            pool_ids=pool_ids,
        )

        render_section(list_frame, "Owned skins", owned_skins, "No owned skins detected.")
        other_empty_message = "No skins found for this champion." if not available_skins else "No other skins found."
        render_section(list_frame, "Other skins", other_skins, other_empty_message)

    for mode, widgets in mode_option_widgets.items():
        option_frame, option_label = widgets
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, selected_mode=mode: set_picker_mode(selected_mode))
            widget.bind("<Enter>", lambda _event, hovered_mode=mode: apply_mode_option_colors(hovered_mode, hover=True))
            widget.bind("<Leave>", lambda _event, hovered_mode=mode: apply_mode_option_colors(hovered_mode))

    if not champion_id:
        refresh_mode_options()
        populate_list()
        return

    catalog_skins.extend(owner.parent.dd.get_skin_catalog(champion_name))

    def load_skins() -> None:
        if not ws_manager or not getattr(ws_manager, "is_active", False):
            result = {
                "ok": False,
                "message": "LoL client is not detected.",
                "owned_skins": [],
            }
        else:
            result = ws_manager.fetch_owned_skins_for_champion(champion_id)

        def update_ui() -> None:
            if not picker.winfo_exists():
                return
            available_skins.clear()
            available_skins.extend(_merge_catalog_and_owned_skins(catalog_skins, result.get("owned_skins", [])))
            status_var.set(_get_skin_fetch_status_text(result))
            refresh_mode_options()
            populate_list()

        picker.after(0, update_ui)

    refresh_mode_options()
    populate_list()
    owner.parent.executor.submit(load_skins)
