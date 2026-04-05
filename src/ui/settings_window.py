"""Settings window UI."""

import os
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.scrolled import ScrolledFrame

from ..config import (
    REGION_LIST,
    ROLE_PROFILE_ICON_FILES,
    ROLE_PROFILE_LABELS,
    ROLE_PROFILE_ORDER,
    SUMMONER_SPELL_LIST,
    resource_path,
)

if TYPE_CHECKING:
    from .main_window import LoLAssistantUI


class SettingsWindow:
    """Fenetre de parametres de l'application."""

    def __init__(self, parent: "LoLAssistantUI"):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Parametres - MAIN LOL")
        self.window.geometry("500x830")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self._setup_window_icon()
        self._init_variables()
        self.all_champions = parent.dd.all_names if parent.dd.all_names else ["Garen", "Teemo", "Ashe"]
        self.spell_list = SUMMONER_SPELL_LIST[:]
        self.main_frame: Optional[ttk.Frame] = None
        self.role_icon_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.role_picker_window: Optional[ttk.Toplevel] = None
        self.create_widgets()
        self.window.after(100, self.toggle_summoner_entry)
        self.window.after(1000, self._poll_summoner_label)

    def _setup_window_icon(self) -> None:
        try:
            img = Image.open(resource_path("./config/images/garen.webp")).resize((16, 16))
            photo = ImageTk.PhotoImage(img)
            self.window.iconphoto(False, photo)
            self.window._icon_img = photo
        except Exception as e:
            logging.debug(f"Impossible de charger l'icone de la fenetre Settings: {e}")
            self.window._icon_img = None

    def _init_variables(self) -> None:
        params = self.parent.get_params()
        self.auto_accept_var = tk.BooleanVar(value=params.get("auto_accept_enabled", True))
        self.auto_pick_var = tk.BooleanVar(value=params.get("auto_pick_enabled", True))
        self.auto_ban_var = tk.BooleanVar(value=params.get("auto_ban_enabled", True))
        self.auto_summoners_var = tk.BooleanVar(value=params.get("auto_summoners_enabled", True))
        self.summoner_auto_detect_var = tk.BooleanVar(value=params.get("summoner_name_auto_detect", True))
        self.summoner_entry_var = tk.StringVar(value=params.get("manual_summoner_name", ""))
        self.saved_manual_name = params.get("manual_summoner_name", "")
        self.saved_manual_region = params.get("manual_region", "euw")
        self.profile_role_var = tk.StringVar(value=params.get("selected_profile_role", "GLOBAL"))
        self.play_again_var = tk.BooleanVar(value=params.get("auto_play_again_enabled", False))
        self.auto_hide_var = tk.BooleanVar(value=params.get("auto_hide_on_connect", True))
        self.close_on_exit_var = tk.BooleanVar(value=params.get("close_app_on_lol_exit", True))
        self.auto_var = self.auto_accept_var
        self.pick_var = self.auto_pick_var
        self.ban_var = self.auto_ban_var
        self.summ_var = self.auto_summoners_var
        self.summ_auto_var = self.summoner_auto_detect_var
        self.summ_entry_var = self.summoner_entry_var

    def create_widgets(self) -> None:
        self.main_frame = ttk.Frame(self.window, padding=15)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=0)
        self.main_frame.columnconfigure(1, weight=1)

        current_row = 0
        current_row = self._create_auto_accept_section(current_row)
        current_row = self._create_pick_section(current_row)
        current_row = self._create_ban_section(current_row)
        current_row = self._create_spells_section(current_row)
        current_row = self._create_summoner_detection_section(current_row)
        current_row = self._create_misc_section(current_row)

        ttk.Button(self.window, text="Fermer", command=self.on_close, bootstyle="primary").pack(
            pady=(0, 20), side="bottom"
        )

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        self._load_initial_icons()

    def _create_auto_accept_section(self, start_row: int) -> int:
        ttk.Checkbutton(
            self.main_frame,
            text="Accepter la partie automatiquement",
            variable=self.auto_accept_var,
            command=lambda: self.parent.update_param("auto_accept_enabled", self.auto_accept_var.get()),
            bootstyle="success-round-toggle",
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=5)
        return start_row + 1

    def _create_pick_section(self, start_row: int) -> int:
        role_frame = ttk.Frame(self.main_frame)
        role_frame.grid(row=start_row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(role_frame, text="Profil de role :").pack(side="left")
        self.role_selector_btn = ttk.Button(
            role_frame,
            text=ROLE_PROFILE_LABELS.get(self.profile_role_var.get().upper(), ROLE_PROFILE_LABELS["GLOBAL"]),
            bootstyle="secondary-outline",
            command=self._open_role_picker,
            width=18,
            compound="left",
        )
        self.role_selector_btn.pack(side="left", padx=(10, 0))
        self._refresh_role_selector_button()

        ttk.Checkbutton(
            self.main_frame,
            text="Securiser mon Champion",
            variable=self.auto_pick_var,
            command=lambda: (
                self.parent.update_param("auto_pick_enabled", self.auto_pick_var.get()),
                self.toggle_pick(),
            ),
            bootstyle="info-round-toggle",
        ).grid(row=start_row + 1, column=0, columnspan=2, sticky="w", pady=(15, 5))

        ttk.Label(self.main_frame, text="Pick 1 :").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=3)
        self.btn_pick_1 = ttk.Button(
            self.main_frame,
            text=self._get_profile_value("selected_pick_1") or "Garen",
            bootstyle="secondary-outline",
        )
        self.btn_pick_1.grid(row=start_row + 2, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_1.configure(command=lambda: self._open_champion_picker("pick", 1))

        ttk.Label(self.main_frame, text="Pick 2 :").grid(row=start_row + 3, column=0, sticky="e", padx=5, pady=3)
        self.btn_pick_2 = ttk.Button(
            self.main_frame,
            text=self._get_profile_value("selected_pick_2") or "Lux",
            bootstyle="secondary-outline",
        )
        self.btn_pick_2.grid(row=start_row + 3, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_2.configure(command=lambda: self._open_champion_picker("pick", 2))

        ttk.Label(self.main_frame, text="Pick 3 :").grid(row=start_row + 4, column=0, sticky="e", padx=5, pady=3)
        self.btn_pick_3 = ttk.Button(
            self.main_frame,
            text=self._get_profile_value("selected_pick_3") or "Ashe",
            bootstyle="secondary-outline",
        )
        self.btn_pick_3.grid(row=start_row + 4, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_3.configure(command=lambda: self._open_champion_picker("pick", 3))
        return start_row + 5

    def _create_ban_section(self, start_row: int) -> int:
        ttk.Checkbutton(
            self.main_frame,
            text="Bannir un Champion",
            variable=self.auto_ban_var,
            command=lambda: (
                self.parent.update_param("auto_ban_enabled", self.auto_ban_var.get()),
                self.toggle_ban(),
            ),
            bootstyle="danger-round-toggle",
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))

        ttk.Label(self.main_frame, text="Bannir :").grid(row=start_row + 1, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(
            self.main_frame,
            text=self._get_profile_value("selected_ban") or "Teemo",
            bootstyle="secondary-outline",
        )
        self.btn_ban.grid(row=start_row + 1, column=1, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))
        return start_row + 2

    def _create_spells_section(self, start_row: int) -> int:
        params = self.parent.get_params()
        ttk.Checkbutton(
            self.main_frame,
            text="Configurer Sorts",
            variable=self.auto_summoners_var,
            command=lambda: (
                self.parent.update_param("auto_summoners_enabled", self.auto_summoners_var.get()),
                self.toggle_spells(),
            ),
            bootstyle="warning-round-toggle",
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))

        ttk.Label(self.main_frame, text="Sort 1 :").grid(row=start_row + 1, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_1 = ttk.Button(
            self.main_frame,
            text=params.get("global_spell_1", "Heal"),
            bootstyle="secondary-outline",
        )
        self.btn_spell_1.grid(row=start_row + 1, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_1.configure(command=lambda: self._open_spell_picker(1))

        ttk.Label(self.main_frame, text="Sort 2 :").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=3)
        self.btn_spell_2 = ttk.Button(
            self.main_frame,
            text=params.get("global_spell_2", "Flash"),
            bootstyle="secondary-outline",
        )
        self.btn_spell_2.grid(row=start_row + 2, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_2.configure(command=lambda: self._open_spell_picker(2))
        return start_row + 3

    def _create_summoner_detection_section(self, start_row: int) -> int:
        params = self.parent.get_params()
        detect_frame = ttk.Frame(self.main_frame)
        detect_frame.grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))

        def on_auto_toggle():
            self.parent.update_param("summoner_name_auto_detect", self.summoner_auto_detect_var.get())
            self.toggle_summoner_entry()
            if self.summoner_auto_detect_var.get():
                self.parent.force_refresh_summoner()
            self._update_detect_label_text()

        self.switch_auto = ttk.Checkbutton(
            detect_frame,
            variable=self.summoner_auto_detect_var,
            command=on_auto_toggle,
            bootstyle="round-toggle",
        )
        self.switch_auto.pack(side="left", padx=(0, 10))

        self.lbl_auto_detect = ttk.Label(detect_frame, text="Detection auto du compte")
        self.lbl_auto_detect.pack(side="left")

        ttk.Label(self.main_frame, text="Pseudo :", anchor="w").grid(
            row=start_row + 1, column=0, sticky="e", padx=5, pady=5
        )
        self.summ_entry = ttk.Entry(self.main_frame, textvariable=self.summoner_entry_var, state="readonly")
        self.summ_entry.grid(row=start_row + 1, column=1, sticky="ew", padx=5)

        ttk.Label(self.main_frame, text="Region :", anchor="w").grid(
            row=start_row + 2, column=0, sticky="e", padx=5, pady=5
        )
        self.region_var = tk.StringVar(value=params.get("manual_region", "euw"))
        self.region_cb = ttk.Combobox(
            self.main_frame,
            values=REGION_LIST,
            textvariable=self.region_var,
            state="readonly",
        )
        self.region_cb.grid(row=start_row + 2, column=1, sticky="ew", padx=5)
        self.region_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: self.parent.update_param("manual_region", self.region_var.get()),
        )
        return start_row + 3

    def _create_misc_section(self, start_row: int) -> int:
        ttk.Separator(self.main_frame).grid(row=start_row, column=0, columnspan=2, sticky="we", pady=(15, 10))
        misc_frame = ttk.Frame(self.main_frame)
        misc_frame.grid(row=start_row + 1, column=0, columnspan=2, sticky="w")

        ttk.Checkbutton(
            misc_frame,
            text="Retour au salon automatique a la fin de la partie",
            variable=self.play_again_var,
            command=lambda: self.parent.update_param("auto_play_again_enabled", self.play_again_var.get()),
            bootstyle="info-round-toggle",
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            misc_frame,
            text="Masquer Main LOL au lancement de LoL (3 secondes)",
            variable=self.auto_hide_var,
            command=lambda: self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get()),
            bootstyle="secondary-round-toggle",
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            misc_frame,
            text="Fermer Main LOL a la fermeture de LoL",
            variable=self.close_on_exit_var,
            command=lambda: self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get()),
            bootstyle="danger-round-toggle",
        ).pack(anchor="w", pady=2)
        return start_row + 2

    def _load_initial_icons(self) -> None:
        params = self.parent.get_params()
        self._update_btn_content(self.btn_ban, self._get_profile_value("selected_ban"), is_champ=True)
        self._update_btn_content(self.btn_pick_1, self._get_profile_value("selected_pick_1"), is_champ=True)
        self._update_btn_content(self.btn_pick_2, self._get_profile_value("selected_pick_2"), is_champ=True)
        self._update_btn_content(self.btn_pick_3, self._get_profile_value("selected_pick_3"), is_champ=True)
        self._update_btn_content(self.btn_spell_1, params.get("global_spell_1", ""), is_champ=False)
        self._update_btn_content(self.btn_spell_2, params.get("global_spell_2", ""), is_champ=False)

    def _get_selected_profile_role(self) -> str:
        role = self.profile_role_var.get().upper()
        return role if role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"

    def _get_profile_role_data(self, role: Optional[str] = None) -> Dict[str, str]:
        params = self.parent.get_params()
        target_role = (role or self._get_selected_profile_role()).upper()
        if target_role == "GLOBAL":
            return {
                "selected_pick_1": params.get("selected_pick_1", ""),
                "selected_pick_2": params.get("selected_pick_2", ""),
                "selected_pick_3": params.get("selected_pick_3", ""),
                "selected_ban": params.get("selected_ban", ""),
            }
        role_profiles = params.get("role_profiles", {})
        role_data = role_profiles.get(target_role, {}) if isinstance(role_profiles, dict) else {}
        return {
            "selected_pick_1": role_data.get("selected_pick_1", ""),
            "selected_pick_2": role_data.get("selected_pick_2", ""),
            "selected_pick_3": role_data.get("selected_pick_3", ""),
            "selected_ban": role_data.get("selected_ban", ""),
        }

    def _get_profile_value(self, key: str) -> str:
        return self._get_profile_role_data().get(key, "")

    def _set_profile_value(self, key: str, value: str) -> None:
        role = self._get_selected_profile_role()
        if role == "GLOBAL":
            self.parent.update_param(key, value)
            return

        params = self.parent.get_params()
        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
        role_data = new_profiles.get(role, {})
        role_data[key] = value
        new_profiles[role] = role_data
        self.parent.update_param("role_profiles", new_profiles)

    def _refresh_profile_buttons(self) -> None:
        self._update_btn_content(self.btn_ban, self._get_profile_value("selected_ban"), True)
        self._update_btn_content(self.btn_pick_1, self._get_profile_value("selected_pick_1"), True)
        self._update_btn_content(self.btn_pick_2, self._get_profile_value("selected_pick_2"), True)
        self._update_btn_content(self.btn_pick_3, self._get_profile_value("selected_pick_3"), True)
        self._refresh_role_selector_button()

    def _load_role_icon(self, role: str, size: int = 24) -> Optional[ImageTk.PhotoImage]:
        cache_key = (role, size)
        if cache_key in self.role_icon_cache:
            return self.role_icon_cache[cache_key]

        icon_rel_path = ROLE_PROFILE_ICON_FILES.get(role)
        if not icon_rel_path:
            return None

        icon_path = resource_path(icon_rel_path)
        if not os.path.exists(icon_path):
            return None

        try:
            image = Image.open(icon_path).convert("RGBA").resize((size, size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.role_icon_cache[cache_key] = photo
            return photo
        except Exception as e:
            logging.debug(f"Impossible de charger l'icone du role {role}: {e}")
            return None

    def _refresh_role_selector_button(self) -> None:
        role = self._get_selected_profile_role()
        label = ROLE_PROFILE_LABELS.get(role, ROLE_PROFILE_LABELS["GLOBAL"])
        icon = self._load_role_icon(role, size=22)
        if icon:
            self.role_selector_btn.configure(text=f"  {label}", image=icon, compound="left")
            self.role_selector_btn.image = icon
        else:
            self.role_selector_btn.configure(text=label, image="")

    def _select_profile_role(self, selected_role: str) -> None:
        self.profile_role_var.set(selected_role)
        self.parent.update_param("selected_profile_role", selected_role)
        self._refresh_profile_buttons()
        if self.role_picker_window and self.role_picker_window.winfo_exists():
            self.role_picker_window.destroy()
        self.role_picker_window = None

    def _open_role_picker(self) -> None:
        if self.role_picker_window and self.role_picker_window.winfo_exists():
            self.role_picker_window.lift()
            self.role_picker_window.focus_force()
            return

        picker = ttk.Toplevel(self.window)
        self.role_picker_window = picker
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title("Choisir un profil de role")
        picker.resizable(False, False)
        picker.transient(self.window)
        picker.geometry(f"310x360+{self.window.winfo_x()+60}+{self.window.winfo_y()+80}")
        picker.protocol("WM_DELETE_WINDOW", lambda: self._close_role_picker())

        container = ttk.Frame(picker, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Choisis le profil a modifier",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        roles = ["GLOBAL", *ROLE_PROFILE_ORDER]
        current_role = self._get_selected_profile_role()

        for role in roles:
            row_frame = ttk.Frame(container)
            row_frame.pack(fill="x", pady=4)

            icon = self._load_role_icon(role, size=24)
            label = ROLE_PROFILE_LABELS.get(role, role.title())
            suffix = "  ✓" if role == current_role else ""
            btn = ttk.Button(
                row_frame,
                text=f"  {label}{suffix}",
                command=lambda r=role: self._select_profile_role(r),
                bootstyle="secondary-outline" if role != current_role else "primary",
                compound="left",
                width=24,
            )
            if icon:
                btn.configure(image=icon)
                btn.image = icon
            btn.pack(fill="x")

        picker.bind("<Escape>", lambda e: self._close_role_picker())
        picker.focus_force()

    def _close_role_picker(self) -> None:
        if self.role_picker_window and self.role_picker_window.winfo_exists():
            self.role_picker_window.destroy()
        self.role_picker_window = None

    def _open_champion_picker(self, context: str = "pick", slot_num: int = 1) -> None:
        picker = ttk.Toplevel(self.window)
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title(f"Selectionner Champion ({context.title()})")
        picker.geometry(f"480x600+{self.window.winfo_x()+20}+{self.window.winfo_y()+20}")

        search_frame = ttk.Frame(picker, padding=10)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Rechercher :").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.focus_set()

        scroll_container = ScrolledFrame(picker, autohide=False)
        scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
        grid_frame = scroll_container

        profile_data = self._get_profile_role_data()
        excluded = set()
        pick_1 = profile_data.get("selected_pick_1")
        pick_2 = profile_data.get("selected_pick_2")
        pick_3 = profile_data.get("selected_pick_3")
        banned = profile_data.get("selected_ban")
        if context == "pick":
            if banned:
                excluded.add(banned)
            if slot_num == 1:
                excluded.update({pick_2, pick_3})
            elif slot_num == 2:
                excluded.update({pick_1, pick_3})
            elif slot_num == 3:
                excluded.update({pick_1, pick_2})
        elif context == "ban":
            excluded.update({pick_1, pick_2, pick_3})

        valid_champs = [champion for champion in self.all_champions if champion not in excluded]

        def populate_grid(filter_text: str = "") -> None:
            for widget in grid_frame.winfo_children():
                widget.destroy()
            filter_text = filter_text.lower()
            row, col = 0, 0
            for champ_name in valid_champs:
                if filter_text in champ_name.lower():
                    btn = ttk.Button(
                        grid_frame,
                        text=champ_name,
                        bootstyle="link",
                        compound="top",
                        command=lambda c=champ_name: on_select(c),
                    )
                    btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    self._load_img_into_btn(btn, champ_name, is_champ=True)
                    col += 1
                    if col >= 4:
                        col = 0
                        row += 1

        def on_select(champ_name: str) -> None:
            if context == "ban":
                self._set_profile_value("selected_ban", champ_name)
                self._update_btn_content(self.btn_ban, champ_name, True)
            elif context == "pick":
                if slot_num == 1:
                    self._set_profile_value("selected_pick_1", champ_name)
                    self._update_btn_content(self.btn_pick_1, champ_name, True)
                elif slot_num == 2:
                    self._set_profile_value("selected_pick_2", champ_name)
                    self._update_btn_content(self.btn_pick_2, champ_name, True)
                elif slot_num == 3:
                    self._set_profile_value("selected_pick_3", champ_name)
                    self._update_btn_content(self.btn_pick_3, champ_name, True)
            picker.destroy()

        search_var.trace("w", lambda *args: populate_grid(search_var.get()))
        search_entry.bind(
            "<Return>",
            lambda e: grid_frame.winfo_children()[0].invoke() if grid_frame.winfo_children() else None,
        )
        populate_grid()

    def _open_spell_picker(self, spell_slot_num: int) -> None:
        if not self.auto_summoners_var.get():
            return

        picker = ttk.Toplevel(self.window)
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title(f"Choisir Sort {spell_slot_num}")
        picker.geometry(f"350x350+{self.window.winfo_x()+50}+{self.window.winfo_y()+100}")
        picker.resizable(False, False)
        container = ttk.Frame(picker, padding=10)
        container.pack(fill="both", expand=True)

        def on_pick(spell_name: str) -> None:
            params = self.parent.get_params()
            other = params.get("global_spell_2") if spell_slot_num == 1 else params.get("global_spell_1")
            if spell_name == other and spell_name != "(Aucun)":
                if spell_slot_num == 1:
                    self.parent.update_param("global_spell_2", "(Aucun)")
                    self._update_btn_content(self.btn_spell_2, "(Aucun)", False)
                else:
                    self.parent.update_param("global_spell_1", "(Aucun)")
                    self._update_btn_content(self.btn_spell_1, "(Aucun)", False)

            if spell_slot_num == 1:
                self.parent.update_param("global_spell_1", spell_name)
                self._update_btn_content(self.btn_spell_1, spell_name, False)
            else:
                self.parent.update_param("global_spell_2", spell_name)
                self._update_btn_content(self.btn_spell_2, spell_name, False)
            picker.destroy()

        row, col = 0, 0
        for spell in self.spell_list:
            spell_frame = ttk.Frame(container)
            spell_frame.grid(row=row, column=col, padx=5, pady=5)
            btn = ttk.Button(spell_frame, bootstyle="link", command=lambda s=spell: on_pick(s))
            btn.pack()
            self._load_img_into_btn(btn, spell, False)
            col += 1
            if col > 3:
                col = 0
                row += 1

    def _update_btn_content(self, btn_widget: ttk.Button, name: str, is_champ: bool = True) -> None:
        if not name:
            name = "..."

        def task():
            try:
                if is_champ:
                    img = self.parent.dd.get_champion_icon(name)
                else:
                    img = self.parent.dd.get_summoner_icon(name)

                if img:
                    img = img.resize((30, 30), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo, text=f"  {name}", compound="left")
                            btn_widget.image = photo

                    btn_widget.after(0, update_ui)
                else:
                    def update_ui_no_img():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image="", text=f"  {name}", compound="left")

                    btn_widget.after(0, update_ui_no_img)
            except Exception as e:
                logging.debug(f"Erreur chargement icone pour {name}: {e}")

        self.parent.executor.submit(task)

    def _load_img_into_btn(self, btn_widget: ttk.Button, name: str, is_champ: bool = True) -> None:
        def task():
            try:
                if is_champ:
                    img = self.parent.dd.get_champion_icon(name)
                else:
                    img = self.parent.dd.get_summoner_icon(name)

                if img:
                    size = (40, 40) if is_champ else (48, 48)
                    img = img.resize(size, Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo)
                            btn_widget.image = photo

                    btn_widget.after(0, update_ui)
            except Exception as e:
                logging.debug(f"Erreur chargement image pour {name}: {e}")

        self.parent.executor.submit(task)

    def toggle_summoner_entry(self) -> None:
        if self.summoner_auto_detect_var.get():
            current_entry = self.summoner_entry_var.get()
            current_auto = self.parent.get_auto_summoner_name()
            if current_entry != current_auto and current_entry != "(detection auto...)":
                self.saved_manual_name = current_entry
            if self.region_var.get() and self.region_var.get() in REGION_LIST:
                self.saved_manual_region = self.region_var.get()

            self.summ_entry.configure(state="readonly")
            self.region_cb.configure(state="disabled")
            self.parent.force_refresh_summoner()
            auto_name = self.parent.get_auto_summoner_name()
            self.summoner_entry_var.set(auto_name if auto_name else "(detection auto...)")
            self.region_var.set(self.parent.get_platform_for_websites())
        else:
            self.summ_entry.configure(state="normal")
            self.region_cb.configure(state="readonly")
            self.summoner_entry_var.set(self.saved_manual_name)
            self.region_var.set(self.saved_manual_region or self.parent.get_params().get("manual_region", "euw"))

        self._update_detect_label_text()

    def toggle_pick(self) -> None:
        state = "normal" if self.auto_pick_var.get() else "disabled"
        self.btn_pick_1.configure(state=state)
        self.btn_pick_2.configure(state=state)
        self.btn_pick_3.configure(state=state)

    def toggle_ban(self) -> None:
        self.btn_ban.configure(state="normal" if self.auto_ban_var.get() else "disabled")

    def toggle_spells(self) -> None:
        state = "normal" if self.auto_summoners_var.get() else "disabled"
        self.btn_spell_1.configure(state=state)
        self.btn_spell_2.configure(state=state)

    def _update_detect_label_text(self) -> None:
        detected = self.parent.get_auto_summoner_name()
        if self.parent.is_ws_active() and detected:
            self.lbl_auto_detect.configure(text=f"Detection auto du compte (compte detecte : {detected})")
        else:
            self.lbl_auto_detect.configure(text="Detection auto du compte")

    def _poll_summoner_label(self) -> None:
        if not self.window.winfo_exists():
            return

        self._update_detect_label_text()
        if self.summoner_auto_detect_var.get():
            current = self.parent.get_auto_summoner_name() or "(detection auto...)"
            if self.summoner_entry_var.get() != current:
                self.summoner_entry_var.set(current)
            region = self.parent.get_platform_for_websites()
            if self.region_var.get() != region:
                self.region_var.set(region)

        if not self.summoner_auto_detect_var.get():
            self.saved_manual_name = self.summoner_entry_var.get()
            self.saved_manual_region = self.region_var.get()

        self.window.after(1000, self._poll_summoner_label)

    def on_close(self) -> None:
        self.parent.update_param("auto_summoners_enabled", self.auto_summoners_var.get())
        self.parent.update_param("summoner_name_auto_detect", self.summoner_auto_detect_var.get())
        if not self.summoner_auto_detect_var.get():
            self.parent.update_param("manual_summoner_name", self.summoner_entry_var.get())
            self.parent.update_param("manual_region", self.region_var.get())

        self.parent.update_param("auto_play_again_enabled", self.play_again_var.get())
        self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get())
        self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get())
        self.parent.save_and_notify()
        self.window.destroy()
