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
        merged_entry["owned"] = skin_id in owned_by_id
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

    theme_name = getattr(owner.parent, "theme", "darkly")
    palette = THEME_PALETTE.get(theme_name, THEME_PALETTE["darkly"])
    prompt = ttk.Toplevel(owner.window)
    if getattr(owner.window, "_icon_img", None):
        prompt.iconphoto(False, owner.window._icon_img)
    prompt.title("Skin not detected")
    prompt.resizable(False, False)
    prompt.transient(owner.window)
    prompt.geometry(f"400x160+{owner.window.winfo_x()+110}+{owner.window.winfo_y()+120}")
    prompt.configure(bg=palette["window_bg"])

    result = {"value": False}

    def _close(value: bool) -> None:
        result["value"] = value
        try:
            prompt.grab_release()
        except Exception:
            pass
        prompt.destroy()

    prompt.protocol("WM_DELETE_WINDOW", lambda: _close(False))

    container = tk.Frame(prompt, bg=palette["window_bg"], padx=18, pady=18)
    container.pack(fill="both", expand=True)

    title_label = tk.Label(
        container,
        text="Skin not detected",
        bg=palette["window_bg"],
        fg=palette["text"],
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    )
    title_label.pack(fill="x", pady=(0, 8))

    message_label = tk.Label(
        container,
        text="Warning: this skin is not detected on this account.\nAre you sure you want to select it?",
        bg=palette["window_bg"],
        fg=palette["text"],
        justify="left",
        anchor="w",
        font=("Segoe UI", 10),
    )
    message_label.pack(fill="x")

    buttons = tk.Frame(container, bg=palette["window_bg"])
    buttons.pack(anchor="e", pady=(16, 0))
    ttk.Button(buttons, text="Yes", bootstyle="primary", width=10, command=lambda: _close(True)).pack(
        side="left", padx=(0, 8)
    )
    ttk.Button(buttons, text="No", bootstyle="secondary-outline", width=10, command=lambda: _close(False)).pack(
        side="left"
    )

    prompt.grab_set()
    prompt.focus_force()
    prompt.wait_window()
    return bool(result["value"])


def _get_skin_fetch_status_text(result: Dict[str, Any]) -> str:
    """Convert an owned-skins fetch result into a user-facing status message."""
    if result.get("ok"):
        return ""
    message = str(result.get("message") or "").strip()
    if not message:
        return "Unable to fetch owned skins: LoL client is not detected."
    lowered = message.lower()
    if "connection" in lowered or "league of legends" in lowered or "lcu" in lowered:
        return "Unable to fetch owned skins: LoL client is not detected."
    return f"Unable to fetch owned skins: {message}"


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

    container = ttk.Frame(picker, padding=12)
    container.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(container, textvariable=status_var, bootstyle="warning")
    status_label.pack(fill="x", pady=(0, 8))
    status_label.configure(wraplength=340, justify="left")
    if not ws_manager or not getattr(ws_manager, "is_active", False):
        status_var.set("Unable to fetch owned skins: LoL client is not detected.")

    mode_bar = ttk.Frame(container)
    mode_bar.pack(fill="x")
    fixed_mode_btn = ttk.Button(mode_bar, text="Choose a skin")
    random_mode_btn = ttk.Button(mode_bar, text="Choose from a list")
    fixed_mode_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
    random_mode_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

    scroll_container = ScrolledFrame(container, autohide=False)
    scroll_container.pack(fill="both", expand=True, pady=(10, 0))
    list_frame = ttk.Frame(scroll_container)
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

    def refresh_mode_buttons() -> None:
        active_mode = picker_mode_var.get()
        fixed_mode_btn.configure(bootstyle="primary" if active_mode == "fixed" else "secondary-outline")
        random_mode_btn.configure(bootstyle="primary" if active_mode == "random" else "secondary-outline")

    def set_picker_mode(mode: str) -> None:
        picker_mode_var.set("random" if mode == "random" else "fixed")
        refresh_mode_buttons()
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
        row_btn = ttk.Button(
            parent,
            text=f"  {skin['skin_name']}",
            bootstyle="primary" if selected else "secondary-outline",
            compound="left",
            width=26,
            padding=(8, 8),
            command=lambda s=skin: toggle_skin_selection(s),
        )
        row_btn.pack(fill="x", pady=4)
        preview_url = _get_picker_image_url(skin)
        if preview_url:
            owner._load_remote_img_into_btn(
                row_btn,
                preview_url,
                cache_key=(
                    f"skin_picker_{slot_key}_{skin['skin_num'] or skin['skin_id']}_"
                    f"{'owned' if skin.get('owned') else 'other'}"
                ),
                size=(88, 50),
                cover=True,
            )

    def render_section(parent: ttk.Frame, title: str, skins: list[Dict[str, Any]], empty_message: str) -> None:
        section = ttk.Frame(parent)
        section.pack(fill="x", pady=(0, 12))
        ttk.Label(section, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        if not skins:
            ttk.Label(section, text=empty_message, bootstyle="secondary").pack(anchor="w")
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

    fixed_mode_btn.configure(command=lambda: set_picker_mode("fixed"))
    random_mode_btn.configure(command=lambda: set_picker_mode("random"))

    if not champion_id:
        refresh_mode_buttons()
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
            refresh_mode_buttons()
            populate_list()

        picker.after(0, update_ui)

    refresh_mode_buttons()
    populate_list()
    owner.parent.executor.submit(load_skins)
