"""
FILE NAME: src/ui/champion_picker.py
GLOBAL PURPOSE:
- Build the champion-selection dialog used by the settings window.
- Filter unavailable champions based on the current editing context.
- Keep picker-specific layout and search behavior outside the main settings module.

KEY FUNCTIONS:
- open_champion_picker: Open the searchable champion picker for a pick or ban slot.

AUDIENCE & LOGIC:
Why:
This module exists so champion-picker layout and filtering logic do not clutter the larger settings window implementation.
For whom:
Developers maintaining the settings pickers and champion selection UX.

DEPENDENCIES:
Used by:
- src.ui.settings_window
Uses:
- Standard library: tkinter, typing
- Third-party library: ttkbootstrap
"""

from typing import TYPE_CHECKING, Dict, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.scrolled import ScrolledFrame

# Inline role definitions (filter bar, not profile system)
_ROLE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
_ROLE_LABELS = {"GLOBAL": "All", "TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}
_ROLE_ICONS = {
    "GLOBAL": "config/images/roles/global.png",
    "TOP": "config/images/roles/top.png",
    "JUNGLE": "config/images/roles/jungle.png",
    "MIDDLE": "config/images/roles/middle.png",
    "BOTTOM": "config/images/roles/bottom.png",
    "UTILITY": "config/images/roles/utility.png",
}

from ..config import THEME_PALETTE, resource_path
from ..services.champion_roles import champion_matches_role, sort_champions_for_role

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


ROLE_FILTER_ORDER = ["GLOBAL", *_ROLE_ORDER]


def _get_champion_picker_colors(theme_name: str) -> Dict[str, str]:
    """Return high-contrast colors for champion picker controls."""
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
            "entry_bg": "#ffffff",
            "entry_text": "#1f2937",
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
        "entry_bg": "#1f1f1f",
        "entry_text": palette["text"],
    }


def _load_role_icon(role: str, cache: Dict[str, ImageTk.PhotoImage], *, size: int = 24) -> Optional[ImageTk.PhotoImage]:
    """Load and cache a role icon for the picker filter bar."""
    cache_key = f"{role}_{size}"
    if cache_key in cache:
        return cache[cache_key]
    icon_path = _ROLE_ICONS.get(role)
    if not icon_path:
        return None
    try:
        image = Image.open(resource_path(icon_path)).convert("RGBA").resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        cache[cache_key] = photo
        return photo
    except Exception:
        return None


def open_champion_picker(owner: "SettingsWindow", context: str, slot_num: int = 1) -> None:
    """Open the searchable champion picker for the requested settings context."""
    is_pick_context = context == "pick"
    enabled = owner.auto_pick_var.get() if is_pick_context else owner.auto_ban_var.get()
    if not enabled:
        return

    picker = ttk.Toplevel(owner.window)
    if owner.window._icon_img:
        picker.iconphoto(False, owner.window._icon_img)
    if is_pick_context:
        picker.title(f"{owner._get_preset_label(f'pick_{slot_num}')} - Champion")
    else:
        picker.title(f"Select Champion ({context.title()})")
    picker.geometry(f"760x700+{owner.window.winfo_x()+20}+{owner.window.winfo_y()+20}")
    theme_name = getattr(owner.parent, "theme", "darkly")
    colors = _get_champion_picker_colors(theme_name)
    picker.configure(bg=colors["window_bg"])

    root_frame = tk.Frame(picker, bg=colors["window_bg"], padx=12, pady=12)
    root_frame.pack(fill="both", expand=True)

    top_bar = tk.Frame(root_frame, bg=colors["window_bg"])
    top_bar.pack(fill="x", pady=(0, 10))
    top_bar.columnconfigure(0, weight=0)
    top_bar.columnconfigure(1, weight=1)

    roles_frame = tk.Frame(top_bar, bg=colors["window_bg"])
    roles_frame.grid(row=0, column=0, sticky="w")
    role_icon_cache: Dict[str, ImageTk.PhotoImage] = {}
    role_widgets: Dict[str, tuple[tk.Frame, tk.Label]] = {}
    selected_role_var = tk.StringVar(value="GLOBAL")

    search_area = tk.Frame(top_bar, bg=colors["window_bg"])
    search_area.grid(row=0, column=1, sticky="e")
    search_var = tk.StringVar()
    search_entry = tk.Entry(
        search_area,
        textvariable=search_var,
        width=28,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=colors["border"],
        highlightcolor=colors["active_border"],
        bg=colors["entry_bg"],
        fg=colors["entry_text"],
        insertbackground=colors["entry_text"],
        font=("Segoe UI", 10),
    )
    search_entry.pack(side="right", ipady=7)
    result_var = tk.StringVar(value="")
    result_label = tk.Label(
        search_area,
        textvariable=result_var,
        bg=colors["window_bg"],
        fg=colors["muted"],
        font=("Segoe UI", 9),
        padx=10,
    )
    result_label.pack(side="right")

    scroll_container = ScrolledFrame(root_frame, autohide=False)
    scroll_container.pack(fill="both", expand=True)
    grid_frame = tk.Frame(scroll_container, bg=colors["window_bg"])
    grid_frame.pack(fill="both", expand=True)

    # Excluded champions prevent duplicate picks or invalid pick-ban combinations
    # while the user is editing one profile.
    excluded = owner._get_excluded_champions(context, slot_num)
    valid_champs = [champion for champion in owner.all_champions if champion not in excluded]
    layout_state = {
        "columns": 0,
        "after_id": None,
        "ready": False,
        "last_signature": None,
    }

    def on_select(champ_name: str) -> None:
        owner._select_champion(context, champ_name, slot_num)
        picker.destroy()

    def compute_columns() -> int:
        available_width = max(picker.winfo_width() - 50, 420)
        return max(4, available_width // 112)

    def apply_role_colors(role: str, *, hover: bool = False) -> None:
        role_frame, role_label = role_widgets[role]
        active = selected_role_var.get() == role
        bg = colors["selected_bg"] if active else colors["surface_hover" if hover else "surface_bg"]
        if active and hover:
            bg = colors["selected_hover"]
        border = colors["active_border"] if active else colors["border"]
        role_frame.configure(bg=bg, highlightbackground=border)
        role_label.configure(bg=bg)

    def refresh_role_filters() -> None:
        for role in role_widgets:
            apply_role_colors(role)

    def set_role_filter(role: str) -> None:
        selected_role_var.set(role)
        refresh_role_filters()
        populate_grid(search_var.get(), force=True)

    def create_role_filter(role: str, column: int) -> None:
        role_frame = tk.Frame(
            roles_frame,
            bd=0,
            bg=colors["surface_bg"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            cursor="hand2",
            padx=7,
            pady=6,
        )
        role_frame.grid(row=0, column=column, padx=(0, 6), sticky="nsew")
        icon = _load_role_icon(role, role_icon_cache, size=22)
        role_label = tk.Label(role_frame, image=icon, bg=colors["surface_bg"], cursor="hand2")
        role_label.image = icon
        role_label.pack()
        role_widgets[role] = (role_frame, role_label)
        label = _ROLE_LABELS.get(role, "All")

        for widget in (role_frame, role_label):
            widget.bind("<Button-1>", lambda _event, selected_role=role: set_role_filter(selected_role))
            widget.bind("<Enter>", lambda _event, hovered_role=role: apply_role_colors(hovered_role, hover=True))
            widget.bind("<Leave>", lambda _event, hovered_role=role: apply_role_colors(hovered_role))
            widget.bind("<FocusIn>", lambda _event, hovered_role=role: apply_role_colors(hovered_role, hover=True))
            widget.bind("<FocusOut>", lambda _event, hovered_role=role: apply_role_colors(hovered_role))
        role_frame.bind("<Enter>", lambda _event, hovered_role=role: apply_role_colors(hovered_role, hover=True))
        role_frame.bind("<Leave>", lambda _event, hovered_role=role: apply_role_colors(hovered_role))
        role_frame.tooltip_text = label

    for index, role_key in enumerate(ROLE_FILTER_ORDER):
        create_role_filter(role_key, index)

    def render_champion_card(champ_name: str, row: int, col: int) -> None:
        card = tk.Frame(
            grid_frame,
            bd=0,
            bg=colors["surface_bg"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            cursor="hand2",
            padx=5,
            pady=5,
        )
        card.grid(row=row, column=col, padx=5, pady=6, sticky="nsew")
        image_label = tk.Label(card, bg=colors["surface_bg"], cursor="hand2")
        image_label.pack()
        name_label = tk.Label(
            card,
            text=champ_name,
            bg=colors["surface_bg"],
            fg=colors["text"],
            font=("Segoe UI", 9),
            anchor="center",
            justify="center",
            cursor="hand2",
            wraplength=86,
        )
        name_label.pack(fill="x", pady=(5, 0))

        def apply_card_colors(*, hover: bool = False) -> None:
            bg = colors["surface_hover"] if hover else colors["surface_bg"]
            border = colors["active_border"] if hover else colors["border"]
            card.configure(bg=bg, highlightbackground=border)
            image_label.configure(bg=bg)
            name_label.configure(bg=bg, fg=colors["text"])

        def on_card_click(_event: object) -> None:
            on_select(champ_name)

        for widget in (card, image_label, name_label):
            widget.bind("<Button-1>", on_card_click)
            widget.bind("<Enter>", lambda _event: apply_card_colors(hover=True))
            widget.bind("<Leave>", lambda _event: apply_card_colors())

        owner._load_img_into_btn(image_label, champ_name, is_champ=True, size=(64, 64))

    def render_none_card(row: int, col: int) -> None:
        card = tk.Frame(
            grid_frame,
            bd=0,
            bg=colors["surface_bg"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            cursor="hand2",
            padx=5,
            pady=5,
        )
        card.grid(row=row, column=col, padx=5, pady=6, sticky="nsew")
        question = tk.Label(
            card,
            text="?",
            bg=colors["surface_bg"],
            fg=colors["muted"],
            font=("Segoe UI", 30, "bold"),
            width=3,
            height=1,
            cursor="hand2",
        )
        question.pack()
        label = tk.Label(
            card,
            text="None",
            bg=colors["surface_bg"],
            fg=colors["text"],
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        label.pack(fill="x", pady=(5, 0))

        def apply_card_colors(*, hover: bool = False) -> None:
            bg = colors["surface_hover"] if hover else colors["surface_bg"]
            border = colors["active_border"] if hover else colors["border"]
            card.configure(bg=bg, highlightbackground=border)
            question.configure(bg=bg)
            label.configure(bg=bg)

        for widget in (card, question, label):
            widget.bind("<Button-1>", lambda _event: on_select("(None)"))
            widget.bind("<Enter>", lambda _event: apply_card_colors(hover=True))
            widget.bind("<Leave>", lambda _event: apply_card_colors())

    def render_cards(champions: list[str], columns: int) -> None:
        col = 0
        for column in range(columns):
            grid_frame.columnconfigure(column, weight=1)
        render_none_card(0, 0)
        col = 1
        row = 0
        for champ_name in champions:
            render_champion_card(champ_name, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def get_filtered_champions(filter_text: str) -> list[str]:
        normalized_filter = filter_text.lower().strip()
        selected_role = selected_role_var.get()
        return [
            champion
            for champion in valid_champs
            if normalized_filter in champion.lower()
            and champion_matches_role(owner.parent.dd, champion, selected_role)
        ]

    def populate_grid(filter_text: str = "", *, force: bool = False) -> None:
        """Rebuild the visible card grid after a search or resize event."""
        if not layout_state["ready"]:
            return
        columns = compute_columns()
        filtered = sort_champions_for_role(get_filtered_champions(filter_text), owner.parent.dd, selected_role_var.get())
        signature = (tuple(filtered), columns, selected_role_var.get(), filter_text.lower().strip())
        if not force and layout_state["last_signature"] == signature:
            return
        layout_state["last_signature"] = signature

        for widget in grid_frame.winfo_children():
            widget.destroy()

        result_var.set(f"{len(filtered)} champion(s)")
        layout_state["columns"] = columns

        render_cards(filtered, columns)

    def schedule_relayout(event=None) -> None:
        if not layout_state["ready"]:
            return
        new_columns = compute_columns()
        if new_columns == layout_state["columns"]:
            return
        if layout_state["after_id"] is not None:
            try:
                picker.after_cancel(layout_state["after_id"])
            except Exception:
                pass

        def relayout():
            layout_state["after_id"] = None
            populate_grid(search_var.get())

        layout_state["after_id"] = picker.after(120, relayout)

    def initial_render() -> None:
        layout_state["ready"] = True
        refresh_role_filters()
        populate_grid(search_var.get(), force=True)

    search_var.trace_add("write", lambda *args: populate_grid(search_var.get(), force=True))
    search_entry.bind("<Return>", lambda e: None)
    picker.bind("<Configure>", schedule_relayout)
    search_entry.focus_set()
    picker.after(80, initial_render)
