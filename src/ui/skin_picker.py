"""Skin picker helpers for preset settings."""

from typing import TYPE_CHECKING, Any, Dict

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


def open_skin_picker(owner: "SettingsWindow", slot_key: str) -> None:
    """Open the skin picker for a preset slot."""
    if getattr(owner, "skin_picker_window", None) and owner.skin_picker_window.winfo_exists():
        owner.skin_picker_window.destroy()

    picker = ttk.Toplevel(owner.window)
    owner.skin_picker_window = picker
    if owner.window._icon_img:
        picker.iconphoto(False, owner.window._icon_img)
    picker.title(f"{owner._get_preset_label(slot_key)} - Skin")
    picker.geometry(f"900x720+{owner.window.winfo_x()+30}+{owner.window.winfo_y()+40}")

    def on_close() -> None:
        if picker.winfo_exists():
            picker.destroy()
        owner.skin_picker_window = None

    picker.protocol("WM_DELETE_WINDOW", on_close)

    champion_name = owner._get_slot_champion_name(slot_key)
    champion_id = owner.parent.dd.resolve_champion(champion_name) if champion_name not in {"", "(None)"} else None
    current_skin = owner._get_effective_pick_slot_config(slot_key)
    status_var = tk.StringVar(value="Loading skins...")
    result_var = tk.StringVar(value="")
    available_skins: list[Dict[str, Any]] = []
    layout_state = {"columns": 3, "after_id": None}

    header = ttk.Frame(picker, padding=10)
    header.pack(fill="x")
    ttk.Label(header, text=f"{owner._get_preset_label(slot_key)} skin", font=("Segoe UI", 11, "bold")).pack(
        anchor="w"
    )
    if champion_name and champion_name != "(None)":
        ttk.Label(header, text=f"Champion: {champion_name}", bootstyle="secondary").pack(anchor="w", pady=(2, 0))
    ttk.Label(header, textvariable=status_var, bootstyle="warning").pack(anchor="w", pady=(8, 0))
    ttk.Label(header, textvariable=result_var, bootstyle="secondary").pack(anchor="w", pady=(2, 0))

    scroll_container = ScrolledFrame(picker, autohide=False)
    scroll_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    grid_frame = scroll_container

    def apply_none() -> None:
        owner._set_pick_slot_skin_selection(slot_key, mode="none")
        owner._refresh_skin_buttons()
        on_close()

    def apply_fixed(skin: Dict[str, Any]) -> None:
        owner._set_pick_slot_skin_selection(slot_key, mode="fixed", fixed_skin=skin)
        owner._refresh_skin_buttons()
        on_close()

    def apply_random() -> None:
        chosen = owner._choose_random_skin_entry(
            available_skins,
            exclude_skin_id=int(current_skin.get("random_skin_id") or 0),
        )
        if not chosen:
            owner.parent.show_toast("No skin available for random mode.")
            return
        owner._set_pick_slot_skin_selection(slot_key, mode="random", random_skin=chosen)
        owner._refresh_skin_buttons()
        on_close()

    def compute_columns() -> int:
        available_width = max(picker.winfo_width() - 80, 520)
        return max(2, available_width // 240)

    def render_static_cards(columns: int) -> int:
        ttk.Label(grid_frame, text="Selection mode", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=columns, sticky="w", pady=(0, 8)
        )
        none_card = ttk.Frame(grid_frame, padding=8)
        none_card.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        none_btn = ttk.Button(
            none_card,
            text="No skin",
            bootstyle="secondary-outline",
            compound="top",
            width=20,
            padding=(8, 10),
            command=apply_none,
        )
        none_btn.pack(fill="x")
        ttk.Label(none_card, text="Leave the champion skin unchanged", bootstyle="secondary").pack(pady=(6, 0))

        random_card = ttk.Frame(grid_frame, padding=8)
        random_card.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        random_btn = ttk.Button(
            random_card,
            text="Random skin",
            bootstyle="info-outline",
            compound="top",
            width=20,
            padding=(8, 10),
            command=apply_random,
            state="normal" if available_skins else "disabled",
        )
        random_btn.pack(fill="x")
        if current_skin.get("skin_mode") == "random" and current_skin.get("random_skin_name"):
            ttk.Label(
                random_card,
                text=f"Next: {current_skin['random_skin_name']}",
                bootstyle="secondary",
            ).pack(pady=(6, 0))
        else:
            ttk.Label(random_card, text="Choose a new random owned skin", bootstyle="secondary").pack(pady=(6, 0))
        if current_skin.get("skin_mode") == "random" and champion_name not in {"", "(None)"}:
            splash_url = owner.parent.dd.get_skin_splash_url(
                champion_name,
                skin_id=current_skin.get("random_skin_id"),
                skin_num=current_skin.get("random_skin_num"),
                skin_name=current_skin.get("random_skin_name"),
            )
            if splash_url:
                owner._load_remote_img_into_btn(
                    random_btn,
                    splash_url,
                    cache_key=f"skin_picker_random_{slot_key}_{current_skin.get('random_skin_num') or current_skin.get('random_skin_id') or 0}",
                    size=(150, 84),
                    cover=True,
                )
        return 3

    def render_skin_cards(start_row: int, columns: int) -> None:
        ttk.Label(grid_frame, text="Owned skins", font=("Segoe UI", 10, "bold")).grid(
            row=start_row, column=0, columnspan=columns, sticky="w", pady=(14, 8)
        )
        row = start_row + 1
        col = 0
        for column in range(columns):
            grid_frame.columnconfigure(column, weight=1)
        for skin in available_skins:
            card = ttk.Frame(grid_frame, padding=8)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            select_btn = ttk.Button(
                card,
                text=skin["skin_name"],
                bootstyle="secondary-outline",
                compound="top",
                width=20,
                padding=(8, 10),
                command=lambda s=skin: apply_fixed(s),
            )
            select_btn.pack(fill="x")
            if skin.get("splash_url"):
                owner._load_remote_img_into_btn(
                    select_btn,
                    skin["splash_url"],
                    cache_key=f"skin_picker_{slot_key}_{skin['skin_num'] or skin['skin_id']}",
                    size=(150, 84),
                    cover=True,
                )

            subtitle = "Selected" if int(current_skin.get("skin_id") or 0) == int(skin.get("skin_id") or 0) else "Owned skin"
            ttk.Label(card, text=subtitle, bootstyle="secondary").pack(pady=(6, 0))

            col += 1
            if col >= columns:
                col = 0
                row += 1

    def populate_grid() -> None:
        for widget in grid_frame.winfo_children():
            widget.destroy()

        columns = compute_columns()
        layout_state["columns"] = columns
        next_row = render_static_cards(columns)
        if available_skins:
            render_skin_cards(next_row, columns)

    def schedule_relayout(event=None) -> None:
        new_columns = compute_columns()
        if new_columns == layout_state["columns"]:
            return
        if layout_state["after_id"] is not None:
            try:
                picker.after_cancel(layout_state["after_id"])
            except Exception:
                pass

        def relayout() -> None:
            layout_state["after_id"] = None
            populate_grid()

        layout_state["after_id"] = picker.after(120, relayout)

    picker.bind("<Configure>", schedule_relayout)

    if not champion_id:
        status_var.set("Impossible de recuperer les skins sans champion configure.")
        result_var.set("Choisissez d'abord un champion sur ce preset.")
        populate_grid()
        return

    def load_skins() -> None:
        ws_manager = getattr(owner.parent, "ws_manager", None)
        if not ws_manager:
            result = {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "skins": [],
            }
        else:
            result = ws_manager.fetch_owned_skins_for_champion(champion_id)

        def update_ui() -> None:
            if not picker.winfo_exists():
                return
            available_skins.clear()
            available_skins.extend(result.get("skins", []))
            if result.get("ok"):
                status_var.set("")
                result_var.set(f"{len(available_skins)} skin(s) available")
            else:
                status_var.set(result.get("message") or "Impossible de recuperer les skins.")
                result_var.set("Connectez League of Legends puis reessayez.")
            populate_grid()

        picker.after(0, update_ui)

    populate_grid()
    owner.parent.executor.submit(load_skins)
