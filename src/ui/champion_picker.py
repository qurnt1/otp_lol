"""Champion picker helpers for settings."""

from typing import TYPE_CHECKING

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


def open_champion_picker(owner: "SettingsWindow", context: str, slot_num: int = 1) -> None:
    """Open the champion picker without favorites."""
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

    search_frame = ttk.Frame(picker, padding=10)
    search_frame.pack(fill="x")
    ttk.Label(search_frame, text="Search:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=28)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)
    search_entry.focus_set()
    result_var = tk.StringVar(value="")
    ttk.Label(search_frame, textvariable=result_var, bootstyle="secondary").pack(side="right")

    scroll_container = ScrolledFrame(picker, autohide=False)
    scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
    grid_frame = scroll_container

    excluded = owner._get_excluded_champions(context, slot_num)
    valid_champs = [champion for champion in owner.all_champions if champion not in excluded]
    layout_state = {"columns": 3, "after_id": None}

    def on_select(champ_name: str) -> None:
        owner._select_champion(context, champ_name, slot_num)
        picker.destroy()

    def compute_columns() -> int:
        available_width = max(picker.winfo_width() - 70, 420)
        return max(3, available_width // 170)

    def render_cards(champions: list[str], start_row: int, columns: int) -> None:
        row = start_row
        col = 0
        for column in range(columns):
            grid_frame.columnconfigure(column, weight=1)
        for champ_name in champions:
            card = ttk.Frame(grid_frame, padding=8)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            select_btn = ttk.Button(
                card,
                text=champ_name,
                bootstyle="secondary-outline",
                compound="top",
                width=18,
                padding=(8, 10),
                command=lambda c=champ_name: on_select(c),
            )
            select_btn.pack(fill="x")
            owner._load_img_into_btn(select_btn, champ_name, is_champ=True, size=(54, 54))

            tags = owner.parent.dd.get_champion_tags(champ_name)
            tags_text = " / ".join(tags[:2]) if tags else "Champion"
            ttk.Label(card, text=tags_text, bootstyle="secondary").pack(pady=(6, 0))

            col += 1
            if col >= columns:
                col = 0
                row += 1

    def render_none_card(columns: int) -> None:
        ttk.Label(grid_frame, text="No selection", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=columns, sticky="w", pady=(0, 8)
        )
        card = ttk.Frame(grid_frame, padding=8)
        card.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        select_btn = ttk.Button(
            card,
            text="None",
            bootstyle="secondary-outline",
            compound="top",
            width=18,
            padding=(8, 10),
            command=lambda: on_select("(None)"),
        )
        select_btn.pack(fill="x")
        ttk.Label(card, text="Leave this slot empty", bootstyle="secondary").pack(pady=(6, 0))

    def populate_grid(filter_text: str = "") -> None:
        for widget in grid_frame.winfo_children():
            widget.destroy()

        filter_text = filter_text.lower().strip()
        filtered = [champion for champion in valid_champs if filter_text in champion.lower()]
        result_var.set(f"{len(filtered)} champion(s)")
        columns = compute_columns()
        layout_state["columns"] = columns

        render_none_card(columns)
        ttk.Label(grid_frame, text="All champions", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, columnspan=columns, sticky="w", pady=(14, 8)
        )
        render_cards(filtered, 3, columns)

    def schedule_relayout(event=None) -> None:
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

    search_var.trace_add("write", lambda *args: populate_grid(search_var.get()))
    search_entry.bind("<Return>", lambda e: None)
    picker.bind("<Configure>", schedule_relayout)
    populate_grid()
