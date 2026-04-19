"""Settings window UI."""

import logging
import os
import random
from datetime import datetime
from tkinter import filedialog
from typing import TYPE_CHECKING, Any, Dict, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.scrolled import ScrolledFrame

from ..config import (
    APP_NAME,
    APP_IMAGE_FILES,
    HOTKEY_SITE_LABELS,
    PICK_SLOT_LABELS,
    PICK_SLOT_ORDER,
    REGION_LIST,
    ROLE_PROFILE_ICON_FILES,
    ROLE_PROFILE_LABELS,
    ROLE_PROFILE_ORDER,
    STATS_SITE_LABELS,
    SUMMONER_SPELL_LIST,
    URL_PHASE_RUSH_ICON,
    THEME_LABELS,
    THEME_ORDER,
    THEME_PALETTE,
    export_parameters_to_file,
    import_parameters_from_file,
    resource_path,
)
from .champion_picker import open_champion_picker
from .role_picker import open_role_picker
from .skin_picker import open_skin_picker
from .site_picker import _load_site_logo, open_site_picker

if TYPE_CHECKING:
    from .main_window import LoLAssistantUI


class SettingsWindow:
    """Application settings window."""

    PRESET_LABELS = {
        "pick_1": "Preset 1",
        "pick_2": "Preset 2",
        "pick_3": "Preset 3",
    }
    PICK_ICON_SIZE = (30, 30)

    def __init__(self, parent: "LoLAssistantUI"):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title(f"Settings - {APP_NAME}")
        self.window.geometry("980x820")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self.main_frame: Optional[ttk.Frame] = None
        self.scroll_frame: Optional[ScrolledFrame] = None
        self.role_icon_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.website_logo_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.local_button_image_cache: Dict[tuple[str, tuple[int, int], bool], ImageTk.PhotoImage] = {}
        self.role_picker_window: Optional[ttk.Toplevel] = None
        self.site_picker_window: Optional[ttk.Toplevel] = None
        self._capture_target: Optional[str] = None
        self._pressed_modifiers: set[str] = set()
        self.pick_buttons: Dict[str, ttk.Button] = {}
        self.pick_spell_buttons: Dict[tuple[str, int], ttk.Button] = {}
        self.pick_rune_buttons: Dict[str, ttk.Button] = {}
        self.pick_skin_buttons: Dict[str, ttk.Button] = {}
        self.skin_picker_window: Optional[ttk.Toplevel] = None
        self.rune_placeholder_window: Optional[ttk.Toplevel] = None
        self.all_champions = parent.dd.all_names if parent.dd.all_names else ["Garen", "Teemo", "Ashe"]
        self.spell_list = SUMMONER_SPELL_LIST[:]

        self._setup_window_icon()
        self._init_variables()
        self.create_widgets()
        self.window.bind("<KeyPress>", self._on_hotkey_capture_keypress)
        self.window.bind("<KeyRelease>", self._on_hotkey_capture_keyrelease)
        self.window.after(100, self.toggle_summoner_entry)
        self.window.after(1000, self._poll_summoner_label)

    def _setup_window_icon(self) -> None:
        try:
            img = Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((16, 16))
            photo = ImageTk.PhotoImage(img)
            self.window.iconphoto(False, photo)
            self.window._icon_img = photo
        except Exception as e:
            logging.debug(f"Unable to load the settings window icon: {e}")
            self.window._icon_img = None

    def _init_variables(self) -> None:
        params = self.parent.get_params()
        self.auto_accept_var = tk.BooleanVar(value=params.get("auto_accept_enabled", True))
        self.auto_pick_var = tk.BooleanVar(value=True)
        self.auto_ban_var = tk.BooleanVar(value=params.get("auto_ban_enabled", True))
        self.auto_summoners_var = tk.BooleanVar(value=True)
        self.presets_enabled_var = tk.BooleanVar(value=params.get("presets_enabled", True))
        self.summoner_auto_detect_var = tk.BooleanVar(value=params.get("summoner_name_auto_detect", True))
        self.summoner_entry_var = tk.StringVar(value=params.get("manual_summoner_name", ""))
        self.saved_manual_name = params.get("manual_summoner_name", "")
        self.saved_manual_region = params.get("manual_region", "euw")
        self.profile_role_var = tk.StringVar(value=params.get("selected_profile_role", "GLOBAL"))
        self.preferred_stats_site_var = tk.StringVar(value=params.get("preferred_stats_site", "opgg"))
        self.preferred_hotkey_site_var = tk.StringVar(value=params.get("preferred_hotkey_site", "porofessor"))
        self.hotkey_toggle_var = tk.StringVar(value=params.get("hotkey_toggle_window", "alt+c"))
        self.hotkey_open_site_var = tk.StringVar(value=params.get("hotkey_open_site", "alt+p"))
        self.theme_var = tk.StringVar(value=params.get("theme", "darkly"))
        self.play_again_var = tk.BooleanVar(value=params.get("auto_play_again_enabled", False))
        self.auto_hide_var = tk.BooleanVar(value=params.get("auto_hide_on_connect", True))
        self.close_on_exit_var = tk.BooleanVar(value=params.get("close_app_on_lol_exit", True))

    def create_widgets(self) -> None:
        self.scroll_frame = ScrolledFrame(self.window, autohide=True, height=780)
        self.scroll_frame.pack(fill="both", expand=True)

        self.main_frame = ttk.Frame(self.scroll_frame, padding=15)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=0)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.columnconfigure(2, weight=1)
        self.main_frame.columnconfigure(3, weight=1)

        current_row = 0
        current_row = self._create_top_actions_section(current_row)
        current_row = self._create_pick_section(current_row)
        current_row = self._create_ban_section(current_row)
        current_row = self._create_summoner_detection_section(current_row)
        self._create_misc_section(current_row)

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        self._load_initial_icons()

    def _create_top_actions_section(self, start_row: int) -> int:
        top_frame = ttk.Frame(self.main_frame)
        top_frame.grid(row=start_row, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        for column in range(4):
            top_frame.columnconfigure(column, weight=1, uniform="top-actions")

        self.theme_btn = ttk.Button(
            top_frame,
            text=self._get_theme_button_text(),
            bootstyle="secondary-outline",
            command=self._toggle_theme,
            padding=(10, 8),
        )
        self.theme_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            top_frame,
            text="History",
            bootstyle="secondary-outline",
            command=self.parent.open_history_window,
            padding=(10, 8),
        ).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(
            top_frame,
            text="Export config",
            bootstyle="secondary-outline",
            command=self._export_config,
            padding=(10, 8),
        ).grid(row=0, column=2, sticky="ew", padx=2)
        ttk.Button(
            top_frame,
            text="Import config",
            bootstyle="primary-outline",
            command=self._import_config,
            padding=(10, 8),
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        ttk.Checkbutton(
            top_frame,
            text="Automatically accept the game when a match is found",
            variable=self.auto_accept_var,
            command=lambda: self.parent.update_param("auto_accept_enabled", self.auto_accept_var.get()),
            bootstyle="success-round-toggle",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        return start_row + 1

    def _get_preset_label(self, slot_key: str) -> str:
        return self.PRESET_LABELS.get(slot_key, PICK_SLOT_LABELS.get(slot_key, slot_key))

    def _create_pick_section(self, start_row: int) -> int:
        role_frame = ttk.Frame(self.main_frame)
        role_frame.grid(row=start_row, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Label(role_frame, text="Role profile:").pack(side="left")
        self.role_selector_btn = ttk.Button(
            role_frame,
            text=ROLE_PROFILE_LABELS.get(self.profile_role_var.get().upper(), ROLE_PROFILE_LABELS["GLOBAL"]),
            bootstyle="secondary-outline",
            command=self._open_role_picker,
            width=18,
            compound="left",
            padding=(10, 8),
        )
        self.role_selector_btn.pack(side="left", padx=(10, 0))
        self._refresh_role_selector_button()

        ttk.Separator(self.main_frame).grid(row=start_row + 1, column=0, columnspan=4, sticky="we", pady=(4, 8))

        presets_frame = ttk.Frame(self.main_frame)
        presets_frame.grid(row=start_row + 2, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.presets_toggle = ttk.Checkbutton(
            presets_frame,
            text="Enable presets for this profile",
            variable=self.presets_enabled_var,
            command=self._toggle_profile_presets,
            bootstyle="info-round-toggle",
        )
        self.presets_toggle.pack(side="left")

        for slot_num, slot_key in enumerate(PICK_SLOT_ORDER, start=1):
            row_index = start_row + slot_num + 2
            ttk.Label(self.main_frame, text=f"{self._get_preset_label(slot_key)} :").grid(
                row=row_index,
                column=0,
                sticky="e",
                padx=5,
                pady=4,
            )
            row_frame = ttk.Frame(self.main_frame)
            row_frame.grid(row=row_index, column=1, columnspan=3, sticky="ew", padx=5, pady=4)
            row_frame.columnconfigure(0, weight=2)
            row_frame.columnconfigure(1, weight=1)
            row_frame.columnconfigure(2, weight=1)
            row_frame.columnconfigure(3, weight=1)
            row_frame.columnconfigure(4, weight=2)

            champion_btn = ttk.Button(
                row_frame,
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=16,
                command=lambda key=slot_key: self._open_pick_slot_champion_picker(key),
            )
            champion_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            self.pick_buttons[slot_key] = champion_btn

            spell_1_btn = ttk.Button(
                row_frame,
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=13,
                command=lambda key=slot_key: self._open_spell_picker(key, 1),
            )
            spell_1_btn.grid(row=0, column=1, sticky="ew", padx=3)
            self.pick_spell_buttons[(slot_key, 1)] = spell_1_btn

            spell_2_btn = ttk.Button(
                row_frame,
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=13,
                command=lambda key=slot_key: self._open_spell_picker(key, 2),
            )
            spell_2_btn.grid(row=0, column=2, sticky="ew", padx=3)
            self.pick_spell_buttons[(slot_key, 2)] = spell_2_btn

            rune_btn = ttk.Button(
                row_frame,
                text="Rune",
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=13,
                command=self._open_rune_placeholder,
            )
            rune_btn.grid(row=0, column=3, sticky="ew", padx=3)
            self.pick_rune_buttons[slot_key] = rune_btn

            skin_btn = ttk.Button(
                row_frame,
                text="Skin",
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=18,
                command=lambda key=slot_key: self._open_skin_picker(key),
            )
            skin_btn.grid(row=0, column=4, sticky="ew", padx=(6, 0))
            self.pick_skin_buttons[slot_key] = skin_btn

        ttk.Separator(self.main_frame).grid(row=start_row + 6, column=0, columnspan=4, sticky="we", pady=(10, 8))
        return start_row + 7

    def _create_ban_section(self, start_row: int) -> int:
        ttk.Checkbutton(
            self.main_frame,
            text="Ban a champion",
            variable=self.auto_ban_var,
            command=lambda: (
                self.parent.update_param("auto_ban_enabled", self.auto_ban_var.get()),
                self.toggle_ban(),
            ),
            bootstyle="danger-round-toggle",
        ).grid(row=start_row, column=0, columnspan=4, sticky="w", pady=(15, 5))

        ttk.Label(self.main_frame, text="Ban:").grid(row=start_row + 1, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_ban.grid(row=start_row + 1, column=1, columnspan=3, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))
        return start_row + 2

    def _create_summoner_detection_section(self, start_row: int) -> int:
        params = self.parent.get_params()
        ttk.Separator(self.main_frame).grid(row=start_row, column=0, columnspan=4, sticky="we", pady=(15, 10))
        detect_frame = ttk.Frame(self.main_frame)
        detect_frame.grid(row=start_row + 1, column=0, columnspan=4, sticky="w", pady=(0, 5))

        def on_auto_toggle():
            if self.summoner_auto_detect_var.get():
                manual_name = self.summoner_entry_var.get().strip()
                if manual_name and manual_name != "(auto detection...)":
                    self.saved_manual_name = manual_name
                manual_region = self.region_var.get().strip().lower()
                if manual_region in REGION_LIST:
                    self.saved_manual_region = manual_region
                    self.parent.update_param("manual_region", manual_region)
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

        self.lbl_auto_detect = ttk.Label(detect_frame, text="Automatic account detection")
        self.lbl_auto_detect.pack(side="left")

        ttk.Label(self.main_frame, text="Riot ID:", anchor="w").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=5)
        self.summ_entry = ttk.Entry(self.main_frame, textvariable=self.summoner_entry_var, state="readonly")
        self.summ_entry.grid(row=start_row + 2, column=1, columnspan=3, sticky="ew", padx=5)

        ttk.Label(self.main_frame, text="Region:", anchor="w").grid(row=start_row + 3, column=0, sticky="e", padx=5, pady=5)
        self.region_var = tk.StringVar(value=params.get("manual_region", "euw"))
        self.region_cb = ttk.Combobox(self.main_frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=start_row + 3, column=1, columnspan=3, sticky="ew", padx=5)
        self.region_cb.bind("<<ComboboxSelected>>", self._on_manual_region_selected)
        return start_row + 4

    def _create_misc_section(self, start_row: int) -> None:
        ttk.Separator(self.main_frame).grid(row=start_row, column=0, columnspan=4, sticky="we", pady=(15, 8))
        misc_frame = ttk.Frame(self.main_frame)
        misc_frame.grid(row=start_row + 1, column=0, columnspan=4, sticky="ew")
        misc_frame.columnconfigure(0, weight=0, minsize=145)
        misc_frame.columnconfigure(1, weight=0, minsize=250)

        ttk.Label(misc_frame, text="Preferred stats site:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        self.stats_site_btn = ttk.Button(
            misc_frame,
            bootstyle="secondary-outline",
            command=lambda: self._open_site_picker("stats"),
            width=26,
            padding=(8, 8),
            compound="left",
        )
        self.stats_site_btn.grid(row=0, column=1, sticky="w", pady=(0, 8))
        self._refresh_stats_site_button()

        ttk.Label(misc_frame, text="Shortcut website:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        self.hotkey_site_btn = ttk.Button(
            misc_frame,
            bootstyle="secondary-outline",
            command=lambda: self._open_site_picker("hotkey"),
            width=26,
            padding=(8, 8),
            compound="left",
        )
        self.hotkey_site_btn.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self._refresh_hotkey_site_button()

        ttk.Separator(misc_frame).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 10))

        ttk.Label(misc_frame, text="Show/hide app:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        self.hotkey_toggle_btn = ttk.Button(
            misc_frame,
            text=self._format_hotkey_display(self.hotkey_toggle_var.get()),
            bootstyle="secondary-outline",
            width=26,
            command=lambda: self._start_hotkey_capture("toggle"),
            padding=(8, 8),
        )
        self.hotkey_toggle_btn.grid(row=3, column=1, sticky="w", pady=(0, 8))

        ttk.Label(misc_frame, text="Open website shortcut:").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        self.hotkey_open_btn = ttk.Button(
            misc_frame,
            text=self._format_hotkey_display(self.hotkey_open_site_var.get()),
            bootstyle="secondary-outline",
            width=26,
            command=lambda: self._start_hotkey_capture("site"),
            padding=(8, 8),
        )
        self.hotkey_open_btn.grid(row=4, column=1, sticky="w", pady=(0, 8))

        ttk.Separator(misc_frame).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 10))

        ttk.Checkbutton(
            misc_frame,
            text="Automatically return to lobby after the game",
            variable=self.play_again_var,
            command=lambda: self.parent.update_param("auto_play_again_enabled", self.play_again_var.get()),
            bootstyle="info-round-toggle",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

        ttk.Checkbutton(
            misc_frame,
            text=f"Hide {APP_NAME} when LoL starts (3 seconds)",
            variable=self.auto_hide_var,
            command=lambda: self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get()),
            bootstyle="secondary-round-toggle",
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=2)

        ttk.Checkbutton(
            misc_frame,
            text=f"Close {APP_NAME} when LoL closes",
            variable=self.close_on_exit_var,
            command=lambda: self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get()),
            bootstyle="danger-round-toggle",
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=2)

    def _load_initial_icons(self) -> None:
        self._refresh_profile_buttons()
        self._refresh_spell_buttons()

    def _normalize_role(self, role: str) -> str:
        aliases = {
            "MID": "MIDDLE",
            "ADC": "BOTTOM",
            "BOT": "BOTTOM",
            "SUP": "UTILITY",
            "SUPPORT": "UTILITY",
            "JGL": "JUNGLE",
        }
        role = aliases.get((role or "GLOBAL").upper(), (role or "GLOBAL").upper())
        return role if role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"

    def _get_selected_profile_role(self) -> str:
        return self._normalize_role(self.profile_role_var.get())

    def _get_profile_role_data(self, role: Optional[str] = None) -> Dict[str, object]:
        params = self.parent.get_params()
        target_role = self._normalize_role(role or self._get_selected_profile_role())
        if target_role == "GLOBAL":
            return {
                "presets_enabled": params.get("presets_enabled", True),
                "selected_pick_1": params.get("selected_pick_1", ""),
                "selected_pick_2": params.get("selected_pick_2", ""),
                "selected_pick_3": params.get("selected_pick_3", ""),
                "selected_ban": params.get("selected_ban", ""),
                "pick_slots": params.get("pick_slots", {}),
            }
        role_profiles = params.get("role_profiles", {})
        role_data = role_profiles.get(target_role, {}) if isinstance(role_profiles, dict) else {}
        if not isinstance(role_data, dict):
            role_data = {}
        return {
            "presets_enabled": role_data.get("presets_enabled", params.get("presets_enabled", True)),
            "selected_pick_1": role_data.get("selected_pick_1", ""),
            "selected_pick_2": role_data.get("selected_pick_2", ""),
            "selected_pick_3": role_data.get("selected_pick_3", ""),
            "selected_ban": role_data.get("selected_ban", ""),
            "pick_slots": role_data.get("pick_slots", {}),
        }

    def _get_profile_value(self, key: str) -> str:
        return self._get_profile_role_data().get(key, "")

    def _get_profile_presets_enabled(self) -> bool:
        return bool(self._get_profile_role_data().get("presets_enabled", True))

    @staticmethod
    def _normalize_empty_choice(value: str) -> str:
        return "(None)" if value in {"", "..."} else value

    @staticmethod
    def _format_visible_value(value: str) -> str:
        if value == "(None)":
            return "None"
        if not value:
            return "..."
        return value

    @staticmethod
    def _slot_number_from_key(slot_key: str) -> int:
        return PICK_SLOT_ORDER.index(slot_key) + 1

    def _open_pick_slot_champion_picker(self, slot_key: str) -> None:
        self._open_champion_picker("pick", self._slot_number_from_key(slot_key))

    def _get_global_fallback_value(self, key: str) -> str:
        params = self.parent.get_params()
        global_map = {
            "selected_pick_1": params.get("selected_pick_1", ""),
            "selected_pick_2": params.get("selected_pick_2", ""),
            "selected_pick_3": params.get("selected_pick_3", ""),
            "selected_ban": params.get("selected_ban", ""),
        }
        return global_map.get(key, "")

    def _get_display_value(self, key: str) -> str:
        value = self._get_profile_value(key)
        if value:
            return self._format_visible_value(value)
        if self._get_selected_profile_role() != "GLOBAL":
            fallback = self._get_global_fallback_value(key)
            if fallback:
                return f"Fallback: {self._format_visible_value(fallback)}"
        return "..."

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

    def _set_profile_presets_enabled(self, enabled: bool) -> None:
        role = self._get_selected_profile_role()
        if role == "GLOBAL":
            self.parent.update_param("presets_enabled", enabled)
            return

        params = self.parent.get_params()
        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
        role_data = new_profiles.get(role, {})
        role_data["presets_enabled"] = enabled
        new_profiles[role] = role_data
        self.parent.update_param("role_profiles", new_profiles)

    def _get_pick_slot_value(self, slot_key: str, field: str) -> str:
        pick_slots = self._get_profile_role_data().get("pick_slots", {})
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        return str(slot_data.get(field, "")) if isinstance(slot_data, dict) else ""

    def _get_global_pick_slot_value(self, slot_key: str, field: str) -> str:
        params = self.parent.get_params()
        pick_slots = params.get("pick_slots", {})
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        return str(slot_data.get(field, "")) if isinstance(slot_data, dict) else ""

    def _get_pick_slot_display_value(self, slot_key: str, field: str) -> str:
        value = self._get_pick_slot_value(slot_key, field)
        if value:
            return self._format_visible_value(value)
        if self._get_selected_profile_role() != "GLOBAL":
            fallback = self._get_global_pick_slot_value(slot_key, field)
            if fallback:
                return f"Fallback: {self._format_visible_value(fallback)}"
        return "..."

    def _get_effective_pick_slot_config(self, slot_key: str) -> Dict[str, Any]:
        slot_data = self._get_profile_role_data().get("pick_slots", {})
        slot_data = slot_data.get(slot_key, {}) if isinstance(slot_data, dict) else {}
        global_slot = self.parent.get_params().get("pick_slots", {})
        global_slot = global_slot.get(slot_key, {}) if isinstance(global_slot, dict) else {}

        def _pick(field: str, default: Any = "") -> Any:
            value = slot_data.get(field) if isinstance(slot_data, dict) else ""
            if isinstance(value, list):
                if value:
                    return value
            elif value not in {"", 0, None}:
                return value
            fallback = global_slot.get(field) if isinstance(global_slot, dict) else ""
            if isinstance(fallback, list):
                if fallback:
                    return fallback
            elif fallback not in {"", 0, None}:
                return fallback
            return default

        return {
            "spell_1": _pick("spell_1", ""),
            "spell_2": _pick("spell_2", ""),
            "skin_mode": _pick("skin_mode", "none"),
            "skin_id": int(_pick("skin_id", 0) or 0),
            "skin_name": str(_pick("skin_name", "") or ""),
            "skin_num": int(_pick("skin_num", 0) or 0),
            "random_skin_id": int(_pick("random_skin_id", 0) or 0),
            "random_skin_name": str(_pick("random_skin_name", "") or ""),
            "random_skin_num": int(_pick("random_skin_num", 0) or 0),
            "random_skin_pool": [dict(entry) for entry in (_pick("random_skin_pool", []) or []) if isinstance(entry, dict)],
        }

    def _set_pick_slot_value(self, slot_key: str, field: str, value: str) -> None:
        role = self._get_selected_profile_role()
        if role == "GLOBAL":
            params = self.parent.get_params()
            pick_slots = params.get("pick_slots", {})
            if not isinstance(pick_slots, dict):
                pick_slots = {}
            new_slots = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in pick_slots.items()}
            slot_data = new_slots.get(slot_key, {})
            slot_data[field] = value
            new_slots[slot_key] = slot_data
            self.parent.update_param("pick_slots", new_slots)
            return

        params = self.parent.get_params()
        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
        role_data = new_profiles.get(role, {})
        pick_slots = role_data.get("pick_slots", {})
        if not isinstance(pick_slots, dict):
            pick_slots = {}
        new_slots = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in pick_slots.items()}
        slot_data = new_slots.get(slot_key, {})
        slot_data[field] = value
        new_slots[slot_key] = slot_data
        role_data["pick_slots"] = new_slots
        new_profiles[role] = role_data
        self.parent.update_param("role_profiles", new_profiles)

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
            return

        self._set_pick_slot_value(slot_key, "skin_mode", "none")
        self._set_pick_slot_value(slot_key, "skin_id", 0)
        self._set_pick_slot_value(slot_key, "skin_name", "")
        self._set_pick_slot_value(slot_key, "skin_num", 0)
        self._set_pick_slot_value(slot_key, "random_skin_id", 0)
        self._set_pick_slot_value(slot_key, "random_skin_name", "")
        self._set_pick_slot_value(slot_key, "random_skin_num", 0)
        self._set_random_skin_pool(slot_key, [])

    @staticmethod
    def _choose_random_skin_entry(
        skins: list[Dict[str, Any]],
        *,
        exclude_skin_id: int = 0,
    ) -> Optional[Dict[str, Any]]:
        available = [skin for skin in skins if int(skin.get("skin_id") or 0) != int(exclude_skin_id or 0)]
        pool = available or skins
        return random.choice(pool) if pool else None

    def _get_slot_champion_name(self, slot_key: str) -> str:
        slot_number = self._slot_number_from_key(slot_key)
        value = self._get_profile_value(f"selected_pick_{slot_number}")
        if value:
            return value
        return self._get_global_fallback_value(f"selected_pick_{slot_number}")

    def _get_skin_button_label(self, slot_key: str) -> str:
        skin_config = self._get_effective_pick_slot_config(slot_key)
        skin_mode = str(skin_config.get("skin_mode") or "none")
        if skin_mode == "fixed" and skin_config.get("skin_name"):
            return str(skin_config["skin_name"])
        if skin_mode == "random":
            return "Random"
        return "Skin"

    def _get_random_skin_placeholder_asset(self) -> str:
        theme = str(self.theme_var.get() or "darkly").strip().lower()
        if theme == "flatly":
            return APP_IMAGE_FILES["question_mark_black_mode"]
        return APP_IMAGE_FILES["question_mark_white_mode"]

    def _select_champion(self, context: str, champ_name: str, slot_num: int = 1) -> None:
        if context == "ban":
            self._set_profile_value("selected_ban", champ_name)
        elif slot_num == 1:
            self._set_profile_value("selected_pick_1", champ_name)
            self._clear_pick_slot_skin("pick_1")
        elif slot_num == 2:
            self._set_profile_value("selected_pick_2", champ_name)
            self._clear_pick_slot_skin("pick_2")
        elif slot_num == 3:
            self._set_profile_value("selected_pick_3", champ_name)
            self._clear_pick_slot_skin("pick_3")
        self._refresh_profile_buttons()
        self._refresh_skin_buttons()

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
            logging.debug(f"Unable to load role icon {role}: {e}")
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

    def _load_website_logo(self, site: str, *, size: int = 30):
        return _load_site_logo(self, site, size=size)

    def _refresh_stats_site_button(self) -> None:
        if hasattr(self, "stats_site_btn"):
            site = self.preferred_stats_site_var.get()
            label = STATS_SITE_LABELS.get(site, STATS_SITE_LABELS["opgg"])
            icon = self._load_website_logo(site, size=self.PICK_ICON_SIZE[0])
            if icon:
                self.stats_site_btn.configure(text=f"  {label}", image=icon, compound="left")
                self.stats_site_btn.image = icon
            else:
                self.stats_site_btn.configure(text=label, image="")
                self.stats_site_btn.image = None

    def _refresh_hotkey_site_button(self) -> None:
        if hasattr(self, "hotkey_site_btn"):
            site = self.preferred_hotkey_site_var.get()
            label = HOTKEY_SITE_LABELS.get(site, HOTKEY_SITE_LABELS["porofessor"])
            icon = self._load_website_logo(site, size=self.PICK_ICON_SIZE[0])
            if icon:
                self.hotkey_site_btn.configure(text=f"  {label}", image=icon, compound="left")
                self.hotkey_site_btn.image = icon
            else:
                self.hotkey_site_btn.configure(text=label, image="")
                self.hotkey_site_btn.image = None

    def _toggle_profile_presets(self) -> None:
        enabled = self.presets_enabled_var.get()
        self._set_profile_presets_enabled(enabled)
        self.toggle_pick()
        self.toggle_spells()

    def _get_theme_button_text(self) -> str:
        return f"Theme: {THEME_LABELS.get(self.theme_var.get(), THEME_LABELS['darkly'])}"

    def _refresh_theme_button(self) -> None:
        if hasattr(self, "theme_btn"):
            self.theme_btn.configure(text=self._get_theme_button_text())

    def _toggle_theme(self) -> None:
        current = self.theme_var.get()
        index = THEME_ORDER.index(current) if current in THEME_ORDER else 0
        next_theme = THEME_ORDER[(index + 1) % len(THEME_ORDER)]
        self.theme_var.set(next_theme)
        self.parent.update_param("theme", next_theme)
        self._refresh_theme_button()
        if hasattr(self, "pick_skin_buttons"):
            self._refresh_skin_buttons()

    @staticmethod
    def _format_hotkey_display(value: str) -> str:
        return (value or "Set").replace("+", " + ").upper()

    def _refresh_hotkey_buttons(self) -> None:
        if hasattr(self, "hotkey_toggle_btn"):
            self.hotkey_toggle_btn.configure(text=self._format_hotkey_display(self.hotkey_toggle_var.get()))
        if hasattr(self, "hotkey_open_btn"):
            self.hotkey_open_btn.configure(text=self._format_hotkey_display(self.hotkey_open_site_var.get()))

    def _start_hotkey_capture(self, target: str) -> None:
        """Enter the one-shot shortcut capture mode for the selected hotkey button."""
        # While capturing a new shortcut, the already registered global hotkeys
        # must be disabled so pressing the old shortcut does not trigger its action.
        if self._capture_target and self._capture_target != target:
            self._refresh_hotkey_buttons()
        if not self._capture_target and hasattr(self.parent, "suspend_hotkeys"):
            self.parent.suspend_hotkeys()
        self._capture_target = target
        self._pressed_modifiers.clear()
        if target == "toggle" and hasattr(self, "hotkey_toggle_btn"):
            self.hotkey_toggle_btn.configure(text="Press a shortcut...")
        if target == "site" and hasattr(self, "hotkey_open_btn"):
            self.hotkey_open_btn.configure(text="Press a shortcut...")
        self.window.focus_force()

    def _cancel_hotkey_capture(self) -> None:
        """Leave shortcut capture mode without changing the saved shortcut."""
        self._capture_target = None
        self._pressed_modifiers.clear()
        self._refresh_hotkey_buttons()
        if hasattr(self.parent, "resume_hotkeys"):
            self.parent.resume_hotkeys()

    def _finish_hotkey_capture(self, sequence: str) -> None:
        """Persist the captured shortcut and let the main window re-register global hotkeys."""
        target_var = self.hotkey_toggle_var if self._capture_target == "toggle" else self.hotkey_open_site_var
        other_var = self.hotkey_open_site_var if self._capture_target == "toggle" else self.hotkey_toggle_var
        if sequence == other_var.get():
            self.parent.show_toast("Shortcut already in use.")
            self._cancel_hotkey_capture()
            return

        target_var.set(sequence)
        target_key = "hotkey_toggle_window" if self._capture_target == "toggle" else "hotkey_open_site"
        self.parent.update_param(target_key, sequence)
        self._cancel_hotkey_capture()

    def _normalize_capture_key(self, keysym: str) -> Optional[str]:
        key = (keysym or "").lower()
        mapping = {
            "control_l": "ctrl",
            "control_r": "ctrl",
            "alt_l": "alt",
            "alt_r": "alt",
            "shift_l": "shift",
            "shift_r": "shift",
            "prior": "pageup",
            "next": "pagedown",
            "return": "enter",
            "escape": "esc",
            "space": "space",
        }
        return mapping.get(key, key if key else None)

    def _on_hotkey_capture_keypress(self, event) -> Optional[str]:
        """Build a normalized hotkey sequence from Tk key events."""
        if not self._capture_target:
            return None

        key = self._normalize_capture_key(event.keysym)
        if not key:
            return "break"
        if key == "esc":
            self._cancel_hotkey_capture()
            return "break"

        if key in {"ctrl", "alt", "shift"}:
            self._pressed_modifiers.add(key)
            return "break"

        modifiers = [modifier for modifier in ("ctrl", "alt", "shift") if modifier in self._pressed_modifiers]
        if not modifiers:
            self.parent.show_toast("Use at least Ctrl, Alt, or Shift.")
            self._cancel_hotkey_capture()
            return "break"

        self._finish_hotkey_capture("+".join([*modifiers, key]))
        return "break"

    def _on_hotkey_capture_keyrelease(self, event) -> Optional[str]:
        if not self._capture_target:
            return None
        key = self._normalize_capture_key(event.keysym)
        if key in {"ctrl", "alt", "shift"} and key in self._pressed_modifiers:
            self._pressed_modifiers.discard(key)
        return "break"

    def _select_profile_role(self, selected_role: str) -> None:
        self.profile_role_var.set(selected_role)
        self.parent.update_param("selected_profile_role", selected_role)
        self.presets_enabled_var.set(self._get_profile_presets_enabled())
        self._refresh_profile_buttons()
        self._refresh_spell_buttons()
        self.toggle_pick()
        self.toggle_spells()
        self._close_role_picker()

    def _open_role_picker(self) -> None:
        open_role_picker(self)

    def _close_role_picker(self) -> None:
        if getattr(self, "role_picker_window", None) and self.role_picker_window.winfo_exists():
            self.role_picker_window.destroy()
        self.role_picker_window = None

    def _open_site_picker(self, picker_type: str) -> None:
        open_site_picker(self, picker_type)

    def _close_site_picker(self) -> None:
        if getattr(self, "site_picker_window", None) and self.site_picker_window.winfo_exists():
            self.site_picker_window.destroy()
        self.site_picker_window = None

    def _select_stats_site(self, selected_site: str) -> None:
        self.preferred_stats_site_var.set(selected_site)
        self.parent.update_param("preferred_stats_site", selected_site)
        self._refresh_stats_site_button()
        self._close_site_picker()

    def _select_hotkey_site(self, selected_site: str) -> None:
        self.preferred_hotkey_site_var.set(selected_site)
        self.parent.update_param("preferred_hotkey_site", selected_site)
        self._refresh_hotkey_site_button()
        self._close_site_picker()

    def _get_excluded_champions(self, context: str, slot_num: int = 1) -> set[str]:
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
        return {champion for champion in excluded if champion and champion != "(None)"}

    def _open_champion_picker(self, context: str, slot_num: int = 1) -> None:
        if context == "pick" and not self.presets_enabled_var.get():
            return
        open_champion_picker(self, context, slot_num)

    def _open_skin_picker(self, slot_key: str) -> None:
        if not self.presets_enabled_var.get():
            return
        open_skin_picker(self, slot_key)

    def _open_spell_picker(self, pick_slot_key: str, spell_slot_num: int) -> None:
        if not self.auto_summoners_var.get() or not self.presets_enabled_var.get():
            return

        picker = ttk.Toplevel(self.window)
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title(f"{self._get_preset_label(pick_slot_key)} - Summ {spell_slot_num}")
        picker.geometry(f"380x420+{self.window.winfo_x()+50}+{self.window.winfo_y()+100}")
        picker.resizable(False, False)
        container = ttk.Frame(picker, padding=10)
        container.pack(fill="both", expand=True)

        def on_pick(spell_name: str) -> None:
            other_key = "spell_2" if spell_slot_num == 1 else "spell_1"
            current_other = self._get_pick_slot_value(pick_slot_key, other_key) or self._get_global_pick_slot_value(
                pick_slot_key, other_key
            )
            if spell_name == current_other and spell_name != "(None)":
                self._set_pick_slot_value(pick_slot_key, other_key, "(None)")

            target_key = "spell_1" if spell_slot_num == 1 else "spell_2"
            self._set_pick_slot_value(pick_slot_key, target_key, spell_name)
            self._refresh_spell_buttons()
            picker.destroy()

        row, col = 0, 0
        for spell in ["(None)", *self.spell_list]:
            spell_frame = ttk.Frame(container)
            spell_frame.grid(row=row, column=col, padx=5, pady=5)
            btn = ttk.Button(spell_frame, text="None" if spell == "(None)" else spell, bootstyle="link", command=lambda s=spell: on_pick(s), compound="top")
            btn.pack()
            if spell != "(None)":
                self._load_img_into_btn(btn, spell, False, size=self.PICK_ICON_SIZE)
            col += 1
            if col > 3:
                col = 0
                row += 1

    def _open_rune_placeholder(self) -> None:
        if self.rune_placeholder_window and self.rune_placeholder_window.winfo_exists():
            self.rune_placeholder_window.lift()
            self.rune_placeholder_window.focus_force()
            return

        popup = ttk.Toplevel(self.window)
        if self.window._icon_img:
            popup.iconphoto(False, self.window._icon_img)
        popup.title("Runes")
        popup.geometry(f"360x190+{self.window.winfo_x()+90}+{self.window.winfo_y()+120}")
        popup.resizable(False, False)
        popup.transient(self.window)

        def _close_popup() -> None:
            self.rune_placeholder_window = None
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _close_popup)
        self.rune_placeholder_window = popup

        container = ttk.Frame(popup, padding=18)
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text="Working on it !!",
            font=("Segoe UI", 16, "bold"),
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(8, 6))
        ttk.Label(
            container,
            text="Rune automation will arrive in the next update.",
            anchor="center",
            justify="center",
        ).pack(fill="x")
        ttk.Button(container, text="Close", bootstyle="secondary-outline", command=_close_popup, width=12).pack(
            pady=(14, 0)
        )

    def _update_btn_content(self, btn_widget: ttk.Button, name: str, is_champ: bool = True) -> None:
        display_name = name or "..."

        def task():
            try:
                raw_name = display_name.replace("Fallback: ", "")
                img = self.parent.dd.get_champion_icon(raw_name) if is_champ else self.parent.dd.get_summoner_icon(raw_name)
                if img:
                    img = img.resize((30, 30), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo, text=f"  {display_name}", compound="left")
                            btn_widget.image = photo

                    btn_widget.after(0, update_ui)
                else:
                    def update_ui_no_img():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image="", text=f"  {display_name}", compound="left")

                    btn_widget.after(0, update_ui_no_img)
            except Exception as e:
                logging.debug(f"Icon loading error for {display_name}: {e}")

        self.parent.executor.submit(task)

    @staticmethod
    def _resize_cover_image(img: Image.Image, size: tuple[int, int]) -> Image.Image:
        source = img.convert("RGBA")
        src_w, src_h = source.size
        target_w, target_h = size
        if src_w <= 0 or src_h <= 0 or target_w <= 0 or target_h <= 0:
            return source.resize(size, Image.LANCZOS)
        scale = max(target_w / src_w, target_h / src_h)
        resized = source.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))), Image.LANCZOS)
        left = max(0, (resized.width - target_w) // 2)
        top = max(0, (resized.height - target_h) // 2)
        return resized.crop((left, top, left + target_w, top + target_h))

    def _load_img_into_btn(self, btn_widget: ttk.Button, name: str, is_champ: bool = True, size: tuple[int, int] = (40, 40)) -> None:
        def task():
            try:
                img = self.parent.dd.get_champion_icon(name) if is_champ else self.parent.dd.get_summoner_icon(name)
                if img:
                    img = img.resize(size, Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo)
                            btn_widget.image = photo

                    btn_widget.after(0, update_ui)
            except Exception as e:
                logging.debug(f"Image loading error for {name}: {e}")

        self.parent.executor.submit(task)

    def _load_remote_img_into_btn(
        self,
        btn_widget: ttk.Button,
        url: str,
        *,
        cache_key: str,
        size: tuple[int, int] = (40, 40),
        cover: bool = False,
    ) -> None:
        def task():
            try:
                img = self.parent.dd.get_remote_image(url, cache_key=cache_key)
                if img:
                    img = self._resize_cover_image(img, size) if cover else img.resize(size, Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def update_ui():
                        if btn_widget.winfo_exists():
                            btn_widget.configure(image=photo)
                            btn_widget.image = photo

                    btn_widget.after(0, update_ui)
            except Exception as e:
                logging.debug(f"Remote image loading error for {url}: {e}")

        self.parent.executor.submit(task)

    def _load_local_img_into_btn(
        self,
        btn_widget: ttk.Button,
        relative_path: str,
        *,
        size: tuple[int, int] = (40, 40),
        cover: bool = False,
    ) -> None:
        cache_key = (relative_path, size, cover)
        cached = self.local_button_image_cache.get(cache_key)
        if cached:
            if btn_widget.winfo_exists():
                btn_widget.configure(image=cached)
                btn_widget.image = cached
            return

        try:
            img = Image.open(resource_path(relative_path))
            img = self._resize_cover_image(img, size) if cover else img.resize(size, Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.local_button_image_cache[cache_key] = photo
            if btn_widget.winfo_exists():
                btn_widget.configure(image=photo)
                btn_widget.image = photo
        except Exception as e:
            logging.debug(f"Local image loading error for {relative_path}: {e}")

    def _refresh_rune_buttons(self) -> None:
        for slot_key, button in self.pick_rune_buttons.items():
            if not button.winfo_exists():
                continue
            button.configure(text="  Phase Rush", image="", compound="left")
            self._load_remote_img_into_btn(
                button,
                URL_PHASE_RUSH_ICON,
                cache_key=f"rune_phase_rush_{slot_key}",
                size=self.PICK_ICON_SIZE,
            )

    def _refresh_skin_buttons(self) -> None:
        for slot_key, button in self.pick_skin_buttons.items():
            if not button.winfo_exists():
                continue
            champion_name = self._get_slot_champion_name(slot_key)
            skin_config = self._get_effective_pick_slot_config(slot_key)
            skin_mode = str(skin_config.get("skin_mode") or "none")
            button.configure(
                text=f"  {self._get_skin_button_label(slot_key)}",
                image="",
                compound="left",
                bootstyle="secondary-outline",
            )

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

    def _refresh_profile_buttons(self) -> None:
        self._update_btn_content(self.btn_ban, self._get_display_value("selected_ban"), True)
        for index, slot_key in enumerate(PICK_SLOT_ORDER, start=1):
            button = self.pick_buttons.get(slot_key)
            if button and button.winfo_exists():
                self._update_btn_content(button, self._get_display_value(f"selected_pick_{index}"), True)
        self._refresh_role_selector_button()

    def _refresh_spell_buttons(self) -> None:
        for slot_key in PICK_SLOT_ORDER:
            for spell_slot_num in (1, 2):
                button = self.pick_spell_buttons.get((slot_key, spell_slot_num))
                if button and button.winfo_exists():
                    self._update_btn_content(
                        button,
                        self._get_pick_slot_display_value(slot_key, f"spell_{spell_slot_num}"),
                        False,
                    )
        self._refresh_rune_buttons()
        self._refresh_skin_buttons()

    def toggle_summoner_entry(self) -> None:
        if self.summoner_auto_detect_var.get():
            self.summ_entry.configure(state="readonly")
            self.region_cb.configure(state="disabled")
            self.parent.force_refresh_summoner()
            auto_name = self.parent.get_auto_summoner_name()
            self.summoner_entry_var.set(auto_name if auto_name else "(auto detection...)")
            self.region_var.set(self.parent.get_platform_for_websites())
        else:
            self.summ_entry.configure(state="normal")
            self.region_cb.configure(state="readonly")
            self.summoner_entry_var.set(self.saved_manual_name)
            self.region_var.set(self.saved_manual_region or self.parent.get_params().get("manual_region", "euw"))

        self._update_detect_label_text()

    def toggle_pick(self) -> None:
        state = "normal" if self.auto_pick_var.get() and self.presets_enabled_var.get() else "disabled"
        for button in getattr(self, "pick_buttons", {}).values():
            button.configure(state=state)
        for button in getattr(self, "pick_rune_buttons", {}).values():
            button.configure(state=state)
        for button in getattr(self, "pick_skin_buttons", {}).values():
            button.configure(state=state)

    def toggle_ban(self) -> None:
        self.btn_ban.configure(state="normal" if self.auto_ban_var.get() else "disabled")

    def toggle_spells(self) -> None:
        state = "normal" if self.auto_summoners_var.get() and self.presets_enabled_var.get() else "disabled"
        for button in getattr(self, "pick_spell_buttons", {}).values():
            button.configure(state=state)

    def _update_detect_label_text(self) -> None:
        detected = self.parent.get_auto_summoner_name()
        if self.parent.is_ws_active() and detected:
            self.lbl_auto_detect.configure(text=f"Automatic account detection (detected account: {detected})")
        else:
            self.lbl_auto_detect.configure(text="Automatic account detection")

    def _sync_from_params(self) -> None:
        params = self.parent.get_params()
        self.auto_accept_var.set(params.get("auto_accept_enabled", True))
        self.auto_pick_var.set(True)
        self.auto_ban_var.set(params.get("auto_ban_enabled", True))
        self.auto_summoners_var.set(True)
        self.presets_enabled_var.set(self._get_profile_presets_enabled())
        self.summoner_auto_detect_var.set(params.get("summoner_name_auto_detect", True))
        self.summoner_entry_var.set(params.get("manual_summoner_name", ""))
        self.saved_manual_name = params.get("manual_summoner_name", "")
        self.saved_manual_region = params.get("manual_region", "euw")
        self.profile_role_var.set(params.get("selected_profile_role", "GLOBAL"))
        self.preferred_stats_site_var.set(params.get("preferred_stats_site", "opgg"))
        self.preferred_hotkey_site_var.set(params.get("preferred_hotkey_site", "porofessor"))
        self.hotkey_toggle_var.set(params.get("hotkey_toggle_window", "alt+c"))
        self.hotkey_open_site_var.set(params.get("hotkey_open_site", "alt+p"))
        self.theme_var.set(params.get("theme", "darkly"))
        self.play_again_var.set(params.get("auto_play_again_enabled", False))
        self.auto_hide_var.set(params.get("auto_hide_on_connect", True))
        self.close_on_exit_var.set(params.get("close_app_on_lol_exit", True))
        self.region_var.set(params.get("manual_region", "euw"))
        self._refresh_theme_button()
        self._refresh_hotkey_buttons()
        self._refresh_stats_site_button()
        self._refresh_hotkey_site_button()
        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self._refresh_profile_buttons()
        self._refresh_spell_buttons()
        self.toggle_summoner_entry()

    def _on_stats_site_selected(self, event=None) -> None:
        selected_label = self.stats_site_cb.get().strip()
        selected_site = next((site for site, label in STATS_SITE_LABELS.items() if label == selected_label), "opgg")
        self._select_stats_site(selected_site)

    def _on_hotkey_site_selected(self, event=None) -> None:
        selected_label = self.hotkey_site_cb.get().strip()
        selected_site = next((site for site, label in HOTKEY_SITE_LABELS.items() if label == selected_label), "porofessor")
        self._select_hotkey_site(selected_site)

    def _on_manual_region_selected(self, event=None) -> None:
        selected = self.region_var.get().strip().lower()
        if selected in REGION_LIST:
            self.saved_manual_region = selected
            self.parent.update_param("manual_region", selected)

    def _export_config(self) -> None:
        default_name = f"main_lol_config_{datetime.now().strftime('%Y-%m-%d')}.json"
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Export configuration",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON file", "*.json")],
        )
        if not path:
            return
        if export_parameters_to_file(path, self.parent.get_params()):
            self.parent.show_toast("Configuration exported!")
        else:
            self.parent.show_toast("Export failed.")

    def _import_config(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.window,
            title="Import configuration",
            filetypes=[("JSON file", "*.json")],
        )
        if not path:
            return
        try:
            imported = import_parameters_from_file(path)
        except Exception as e:
            logging.warning(f"Import failed: {e}")
            self.parent.show_toast("Invalid configuration.")
            return

        self.parent.replace_params(imported)
        self.parent.save_params()
        self.parent.apply_theme(imported.get("theme", "darkly"))
        self._sync_from_params()
        self.parent.show_toast("Configuration imported!")

    def _poll_summoner_label(self) -> None:
        if not self.window.winfo_exists():
            return

        self._update_detect_label_text()
        if self.summoner_auto_detect_var.get():
            current = self.parent.get_auto_summoner_name() or "(auto detection...)"
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
        if self._capture_target:
            self._cancel_hotkey_capture()
        if getattr(self, "skin_picker_window", None) and self.skin_picker_window.winfo_exists():
            self.skin_picker_window.destroy()
        if getattr(self, "rune_placeholder_window", None) and self.rune_placeholder_window.winfo_exists():
            self.rune_placeholder_window.destroy()
        self.parent.update_param("auto_pick_enabled", True)
        self.parent.update_param("auto_summoners_enabled", True)
        self.parent.update_param("summoner_name_auto_detect", self.summoner_auto_detect_var.get())
        if not self.summoner_auto_detect_var.get():
            self.parent.update_param("manual_summoner_name", self.summoner_entry_var.get())
            self.parent.update_param("manual_region", self.region_var.get())

        self.parent.update_param("auto_play_again_enabled", self.play_again_var.get())
        self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get())
        self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get())
        self.parent.update_param("preferred_stats_site", self.preferred_stats_site_var.get())
        self.parent.update_param("preferred_hotkey_site", self.preferred_hotkey_site_var.get())
        self.parent.update_param("hotkey_toggle_window", self.hotkey_toggle_var.get())
        self.parent.update_param("hotkey_open_site", self.hotkey_open_site_var.get())
        self.parent.update_param("theme", self.theme_var.get())
        self.parent.save_and_notify()
        self.window.destroy()
