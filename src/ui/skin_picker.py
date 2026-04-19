"""Skin picker helpers for preset settings."""

from typing import TYPE_CHECKING, Any, Dict, List

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


def _merge_catalog_and_owned_skins(
    catalog_skins: List[Dict[str, Any]],
    owned_skins: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
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
    return str(
        skin.get("centered_splash_url")
        or skin.get("splash_url")
        or skin.get("tile_url")
        or skin.get("preview_url")
        or ""
    )


def open_skin_picker(owner: "SettingsWindow", slot_key: str) -> None:
    """Open the skin picker for a preset slot."""
    if getattr(owner, "skin_picker_window", None) and owner.skin_picker_window.winfo_exists():
        owner.skin_picker_window.destroy()

    picker = ttk.Toplevel(owner.window)
    owner.skin_picker_window = picker
    if owner.window._icon_img:
        picker.iconphoto(False, owner.window._icon_img)
    picker.title(f"{owner._get_preset_label(slot_key)} - Skin")
    picker.geometry(f"960x760+{owner.window.winfo_x()+30}+{owner.window.winfo_y()+40}")

    def on_close() -> None:
        if picker.winfo_exists():
            picker.destroy()
        owner.skin_picker_window = None

    picker.protocol("WM_DELETE_WINDOW", on_close)

    champion_name = owner._get_slot_champion_name(slot_key)
    champion_id = owner.parent.dd.resolve_champion(champion_name) if champion_name not in {"", "(None)"} else None
    status_var = tk.StringVar(value="Loading skins...")
    result_var = tk.StringVar(value="")
    available_skins: list[Dict[str, Any]] = []
    catalog_skins: list[Dict[str, Any]] = []
    layout_state = {"columns": 3, "after_id": None}
    pool_var_by_skin_id: dict[int, tk.BooleanVar] = {}

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

    def get_current_config() -> Dict[str, Any]:
        return owner._get_effective_pick_slot_config(slot_key)

    def get_pool_ids() -> set[int]:
        return {int(entry.get("skin_id") or 0) for entry in owner._get_random_skin_pool(slot_key)}

    def get_pool_skins() -> list[Dict[str, Any]]:
        pool_ids = get_pool_ids()
        return [skin for skin in available_skins if int(skin.get("skin_id") or 0) in pool_ids]

    def get_owned_skins() -> list[Dict[str, Any]]:
        return [skin for skin in available_skins if bool(skin.get("owned"))]

    def get_other_skins() -> list[Dict[str, Any]]:
        return [skin for skin in available_skins if not bool(skin.get("owned"))]

    def refresh_parent_buttons() -> None:
        owner._refresh_skin_buttons()

    def apply_fixed(skin: Dict[str, Any]) -> None:
        owner._set_pick_slot_skin_selection(slot_key, mode="fixed", fixed_skin=skin)
        refresh_parent_buttons()
        on_close()

    def clear_selection() -> None:
        owner._clear_pick_slot_skin(slot_key)
        refresh_parent_buttons()
        on_close()

    def apply_random_from_pool(*, force_new_roll: bool = False) -> None:
        current_config = get_current_config()
        pool_skins = get_pool_skins()
        if not pool_skins:
            owner.parent.show_toast("Select at least one skin for the random pool.")
            return

        exclude_skin_id = int(current_config.get("random_skin_id") or 0) if force_new_roll else 0
        chosen = owner._choose_random_skin_entry(pool_skins, exclude_skin_id=exclude_skin_id)
        if not chosen:
            owner.parent.show_toast("No skin available for random mode.")
            return

        owner._set_random_skin_pool(slot_key, pool_skins)
        owner._set_pick_slot_skin_selection(slot_key, mode="random", random_skin=chosen)
        refresh_parent_buttons()
        populate_grid()

    def sync_random_pool_selection() -> None:
        selected = [
            skin
            for skin in available_skins
            if pool_var_by_skin_id.get(int(skin.get("skin_id") or 0))
            and pool_var_by_skin_id[int(skin.get("skin_id") or 0)].get()
        ]
        owner._set_random_skin_pool(slot_key, selected)
        current_config = get_current_config()
        if current_config.get("skin_mode") == "random":
            if not selected:
                owner._set_pick_slot_skin_selection(slot_key, mode="none")
            elif int(current_config.get("random_skin_id") or 0) not in {
                int(entry.get("skin_id") or 0) for entry in selected
            }:
                chosen = owner._choose_random_skin_entry(selected)
                if chosen:
                    owner._set_pick_slot_skin_selection(slot_key, mode="random", random_skin=chosen)
        refresh_parent_buttons()
        populate_grid()

    def compute_columns() -> int:
        available_width = max(picker.winfo_width() - 80, 520)
        return max(2, available_width // 250)

    def render_control_cards(columns: int) -> int:
        current_config = get_current_config()
        pool_skins = get_pool_skins()

        ttk.Label(grid_frame, text="Selection", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=columns, sticky="w", pady=(0, 8)
        )

        clear_card = ttk.Frame(grid_frame, padding=8)
        clear_card.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        clear_btn = ttk.Button(
            clear_card,
            text="Clear skin setup",
            bootstyle="secondary-outline",
            compound="top",
            width=20,
            padding=(8, 10),
            command=clear_selection,
        )
        clear_btn.pack(fill="x")
        ttk.Label(clear_card, text="Use the default client skin", bootstyle="secondary").pack(pady=(6, 0))

        random_card = ttk.Frame(grid_frame, padding=8)
        random_card.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        random_btn = ttk.Button(
            random_card,
            text=f"Random pool ({len(pool_skins)})",
            bootstyle="info-outline",
            compound="top",
            width=20,
            padding=(8, 10),
            command=lambda: apply_random_from_pool(force_new_roll=True),
            state="normal" if pool_skins else "disabled",
        )
        random_btn.pack(fill="x")

        if current_config.get("skin_mode") == "random" and current_config.get("random_skin_name"):
            ttk.Label(
                random_card,
                text=f"Next: {current_config['random_skin_name']}",
                bootstyle="secondary",
            ).pack(pady=(6, 0))
        else:
            ttk.Label(
                random_card,
                text="Roll only among checked skins below",
                bootstyle="secondary",
            ).pack(pady=(6, 0))

        if current_config.get("skin_mode") == "random" and champion_name not in {"", "(None)"}:
            preview_url = owner.parent.dd.get_skin_picker_url(
                champion_name,
                skin_id=current_config.get("random_skin_id"),
                skin_num=current_config.get("random_skin_num"),
                skin_name=current_config.get("random_skin_name"),
            )
            if preview_url:
                owner._load_remote_img_into_btn(
                    random_btn,
                    preview_url,
                    cache_key=(
                        f"skin_picker_random_{slot_key}_"
                        f"{current_config.get('random_skin_num') or current_config.get('random_skin_id') or 0}"
                    ),
                    size=(150, 84),
                    cover=True,
                )
        return 3

    def render_skin_cards(start_row: int, columns: int, section_title: str, skins: list[Dict[str, Any]]) -> int:
        current_config = get_current_config()
        current_pool_ids = get_pool_ids()
        ttk.Label(grid_frame, text=section_title, font=("Segoe UI", 10, "bold")).grid(
            row=start_row, column=0, columnspan=columns, sticky="w", pady=(14, 8)
        )

        row = start_row + 1
        col = 0
        for column in range(columns):
            grid_frame.columnconfigure(column, weight=1)

        for skin in skins:
            skin_id = int(skin.get("skin_id") or 0)
            card = ttk.Frame(grid_frame, padding=8)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            select_btn = ttk.Button(
                card,
                text=skin["skin_name"],
                bootstyle=(
                    "success-outline"
                    if current_config.get("skin_mode") == "fixed" and int(current_config.get("skin_id") or 0) == skin_id
                    else "secondary-outline"
                ),
                compound="top",
                width=20,
                padding=(8, 10),
                command=lambda s=skin: apply_fixed(s),
            )
            select_btn.pack(fill="x")
            preview_url = _get_picker_image_url(skin)
            if preview_url:
                owner._load_remote_img_into_btn(
                    select_btn,
                    preview_url,
                    cache_key=(
                        f"skin_picker_{slot_key}_{skin['skin_num'] or skin['skin_id']}_"
                        f"{'owned' if skin.get('owned') else 'other'}"
                    ),
                    size=(150, 84),
                    cover=True,
                )

            if current_config.get("skin_mode") == "fixed" and int(current_config.get("skin_id") or 0) == skin_id:
                status_text = "Selected fixed skin"
            elif skin.get("owned"):
                status_text = "Owned skin"
            else:
                status_text = "Not owned on this account"
            ttk.Label(card, text=status_text, bootstyle="secondary").pack(pady=(6, 2))
            ttk.Label(card, text="Click to use as fixed skin", bootstyle="secondary").pack(pady=(0, 2))

            pool_var = tk.BooleanVar(value=skin_id in current_pool_ids)
            pool_var_by_skin_id[skin_id] = pool_var
            ttk.Checkbutton(
                card,
                text="Include in random pool",
                variable=pool_var,
                bootstyle="info-round-toggle",
                command=sync_random_pool_selection,
            ).pack(anchor="w", pady=(2, 0))

            col += 1
            if col >= columns:
                col = 0
                row += 1
        if col != 0:
            row += 1
        return row

    def render_empty_section(start_row: int, columns: int, section_title: str, message: str) -> int:
        ttk.Label(grid_frame, text=section_title, font=("Segoe UI", 10, "bold")).grid(
            row=start_row, column=0, columnspan=columns, sticky="w", pady=(14, 8)
        )
        ttk.Label(grid_frame, text=message, bootstyle="secondary").grid(
            row=start_row + 1, column=0, columnspan=columns, sticky="w"
        )
        return start_row + 2

    def populate_grid() -> None:
        current_pool_ids = get_pool_ids()
        pool_var_by_skin_id.clear()
        for widget in grid_frame.winfo_children():
            widget.destroy()

        columns = compute_columns()
        layout_state["columns"] = columns
        next_row = render_control_cards(columns)
        owned_skins = get_owned_skins()
        other_skins = get_other_skins()
        if owned_skins:
            next_row = render_skin_cards(next_row, columns, "Owned skins", owned_skins)
        elif available_skins:
            next_row = render_empty_section(next_row, columns, "Owned skins", "No owned skins detected.")

        if other_skins:
            next_row = render_skin_cards(next_row, columns, "Other skins", other_skins)
        elif not available_skins and not status_var.get():
            ttk.Label(
                grid_frame,
                text="No skins found for this champion.",
                bootstyle="secondary",
            ).grid(row=next_row, column=0, columnspan=columns, sticky="w", pady=(14, 0))

        # Preserve checkbox state during relayouts.
        for skin_id in current_pool_ids:
            if skin_id in pool_var_by_skin_id:
                pool_var_by_skin_id[skin_id].set(True)

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

    catalog_skins.extend(owner.parent.dd.get_skin_catalog(champion_name))

    def load_skins() -> None:
        ws_manager = getattr(owner.parent, "ws_manager", None)
        if not ws_manager:
            result = {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "owned_skins": [],
            }
        else:
            result = ws_manager.fetch_owned_skins_for_champion(champion_id)

        def update_ui() -> None:
            if not picker.winfo_exists():
                return
            available_skins.clear()
            available_skins.extend(_merge_catalog_and_owned_skins(catalog_skins, result.get("owned_skins", [])))
            owned_count = len(get_owned_skins())
            other_count = len(get_other_skins())
            if result.get("ok"):
                status_var.set("")
                result_var.set(f"{owned_count} owned skin(s), {other_count} other skin(s)")
            else:
                status_var.set(result.get("message") or "Impossible de recuperer les skins.")
                if available_skins:
                    result_var.set("Inventory unavailable, showing full skin catalog for testing.")
                else:
                    result_var.set("Connectez League of Legends puis reessayez.")
            populate_grid()

        picker.after(0, update_ui)

    toolbar = ttk.Frame(header)
    toolbar.pack(anchor="w", pady=(8, 0))
    ttk.Button(
        toolbar,
        text="Refresh skins",
        bootstyle="secondary-outline",
        command=lambda: owner.parent.executor.submit(load_skins),
    ).pack(side="left")

    populate_grid()
    owner.parent.executor.submit(load_skins)
