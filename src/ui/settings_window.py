"""Settings window UI."""

import logging
import os
from datetime import datetime
from tkinter import filedialog
from typing import TYPE_CHECKING, Dict, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.scrolled import ScrolledFrame

from ..config import (
    APP_IMAGE_FILES,
    HOTKEY_SITE_LABELS,
    REGION_LIST,
    ROLE_PROFILE_ICON_FILES,
    ROLE_PROFILE_LABELS,
    ROLE_PROFILE_ORDER,
    STATS_SITE_LABELS,
    SUMMONER_SPELL_LIST,
    THEME_LABELS,
    THEME_ORDER,
    export_parameters_to_file,
    import_parameters_from_file,
    resource_path,
)
from .champion_picker import open_champion_picker
from .role_picker import open_role_picker
from .site_picker import open_site_picker

if TYPE_CHECKING:
    from .main_window import LoLAssistantUI


class SettingsWindow:
    """Application settings window."""

    def __init__(self, parent: "LoLAssistantUI"):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Settings - MAIN LOL")
        self.window.geometry("620x780")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self.main_frame: Optional[ttk.Frame] = None
        self.scroll_frame: Optional[ScrolledFrame] = None
        self.role_icon_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.website_logo_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.role_picker_window: Optional[ttk.Toplevel] = None
        self.site_picker_window: Optional[ttk.Toplevel] = None
        self._capture_target: Optional[str] = None
        self._pressed_modifiers: set[str] = set()
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
        self.auto_pick_var = tk.BooleanVar(value=params.get("auto_pick_enabled", True))
        self.auto_ban_var = tk.BooleanVar(value=params.get("auto_ban_enabled", True))
        self.auto_summoners_var = tk.BooleanVar(value=params.get("auto_summoners_enabled", True))
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

        current_row = 0
        current_row = self._create_top_actions_section(current_row)
        current_row = self._create_pick_section(current_row)
        current_row = self._create_ban_section(current_row)
        current_row = self._create_spells_section(current_row)
        current_row = self._create_summoner_detection_section(current_row)
        self._create_misc_section(current_row)

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        self._load_initial_icons()

    def _create_top_actions_section(self, start_row: int) -> int:
        top_frame = ttk.Frame(self.main_frame)
        top_frame.grid(row=start_row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
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
            text="Automatically accept match",
            variable=self.auto_accept_var,
            command=lambda: self.parent.update_param("auto_accept_enabled", self.auto_accept_var.get()),
            bootstyle="success-round-toggle",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        return start_row + 1

    def _create_pick_section(self, start_row: int) -> int:
        role_frame = ttk.Frame(self.main_frame)
        role_frame.grid(row=start_row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
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

        ttk.Separator(self.main_frame).grid(row=start_row + 1, column=0, columnspan=2, sticky="we", pady=(4, 8))

        ttk.Checkbutton(
            self.main_frame,
            text="Lock my champion",
            variable=self.auto_pick_var,
            command=lambda: (
                self.parent.update_param("auto_pick_enabled", self.auto_pick_var.get()),
                self.toggle_pick(),
            ),
            bootstyle="info-round-toggle",
        ).grid(row=start_row + 2, column=0, columnspan=2, sticky="w", pady=(4, 5))

        for offset, label_text in enumerate(["Pick 1 :", "Pick 2 :", "Pick 3 :"], start=3):
            ttk.Label(self.main_frame, text=label_text).grid(row=start_row + offset, column=0, sticky="e", padx=5, pady=3)

        self.btn_pick_1 = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_pick_1.grid(row=start_row + 3, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_1.configure(command=lambda: self._open_champion_picker("pick", 1))

        self.btn_pick_2 = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_pick_2.grid(row=start_row + 4, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_2.configure(command=lambda: self._open_champion_picker("pick", 2))

        self.btn_pick_3 = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_pick_3.grid(row=start_row + 5, column=1, sticky="ew", padx=5, pady=3)
        self.btn_pick_3.configure(command=lambda: self._open_champion_picker("pick", 3))
        return start_row + 6

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
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))

        ttk.Label(self.main_frame, text="Ban:").grid(row=start_row + 1, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_ban.grid(row=start_row + 1, column=1, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))
        return start_row + 2

    def _create_spells_section(self, start_row: int) -> int:
        ttk.Checkbutton(
            self.main_frame,
            text="Configure spells",
            variable=self.auto_summoners_var,
            command=lambda: (
                self.parent.update_param("auto_summoners_enabled", self.auto_summoners_var.get()),
                self.toggle_spells(),
            ),
            bootstyle="warning-round-toggle",
        ).grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(15, 5))

        ttk.Label(self.main_frame, text="Spell 1:").grid(row=start_row + 1, column=0, sticky="e", padx=5, pady=3)
        ttk.Label(self.main_frame, text="Spell 2:").grid(row=start_row + 2, column=0, sticky="e", padx=5, pady=3)

        self.btn_spell_1 = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_spell_1.grid(row=start_row + 1, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_1.configure(command=lambda: self._open_spell_picker(1))

        self.btn_spell_2 = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_spell_2.grid(row=start_row + 2, column=1, sticky="ew", padx=5, pady=3)
        self.btn_spell_2.configure(command=lambda: self._open_spell_picker(2))
        return start_row + 3

    def _create_summoner_detection_section(self, start_row: int) -> int:
        params = self.parent.get_params()
        ttk.Separator(self.main_frame).grid(row=start_row, column=0, columnspan=2, sticky="we", pady=(15, 10))
        detect_frame = ttk.Frame(self.main_frame)
        detect_frame.grid(row=start_row + 1, column=0, columnspan=2, sticky="w", pady=(0, 5))

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
        self.summ_entry.grid(row=start_row + 2, column=1, sticky="ew", padx=5)

        ttk.Label(self.main_frame, text="Region:", anchor="w").grid(row=start_row + 3, column=0, sticky="e", padx=5, pady=5)
        self.region_var = tk.StringVar(value=params.get("manual_region", "euw"))
        self.region_cb = ttk.Combobox(self.main_frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=start_row + 3, column=1, sticky="ew", padx=5)
        self.region_cb.bind("<<ComboboxSelected>>", self._on_manual_region_selected)
        return start_row + 4

    def _create_misc_section(self, start_row: int) -> None:
        ttk.Separator(self.main_frame).grid(row=start_row, column=0, columnspan=2, sticky="we", pady=(15, 8))
        misc_frame = ttk.Frame(self.main_frame)
        misc_frame.grid(row=start_row + 1, column=0, columnspan=2, sticky="ew")

        site_frame = ttk.Frame(misc_frame)
        site_frame.pack(anchor="w", pady=(0, 8), fill="x")
        ttk.Label(site_frame, text="Preferred stats site:").pack(side="left", padx=(0, 10))
        self.stats_site_btn = ttk.Button(
            site_frame,
            bootstyle="secondary-outline",
            command=lambda: self._open_site_picker("stats"),
            width=24,
            padding=(10, 8),
        )
        self.stats_site_btn.pack(side="left")
        self._refresh_stats_site_button()

        hotkey_frame = ttk.Frame(misc_frame)
        hotkey_frame.pack(anchor="w", pady=(0, 8), fill="x")
        ttk.Label(hotkey_frame, text="Shortcut website:").pack(side="left", padx=(0, 10))
        self.hotkey_site_btn = ttk.Button(
            hotkey_frame,
            bootstyle="secondary-outline",
            command=lambda: self._open_site_picker("hotkey"),
            width=24,
            padding=(10, 8),
        )
        self.hotkey_site_btn.pack(side="left")
        self._refresh_hotkey_site_button()

        ttk.Separator(misc_frame).pack(fill="x", pady=(4, 10))

        shortcut_frame = ttk.Frame(misc_frame)
        shortcut_frame.pack(anchor="w", pady=(0, 8), fill="x")
        ttk.Label(shortcut_frame, text="Show/hide shortcut:").pack(side="left", padx=(0, 10))
        self.hotkey_toggle_btn = ttk.Button(
            shortcut_frame,
            text=self._format_hotkey_display(self.hotkey_toggle_var.get()),
            bootstyle="secondary-outline",
            width=22,
            command=lambda: self._start_hotkey_capture("toggle"),
            padding=(10, 8),
        )
        self.hotkey_toggle_btn.pack(side="left")

        shortcut_site_frame = ttk.Frame(misc_frame)
        shortcut_site_frame.pack(anchor="w", pady=(0, 8), fill="x")
        ttk.Label(shortcut_site_frame, text="Open website shortcut:").pack(side="left", padx=(0, 10))
        self.hotkey_open_btn = ttk.Button(
            shortcut_site_frame,
            text=self._format_hotkey_display(self.hotkey_open_site_var.get()),
            bootstyle="secondary-outline",
            width=22,
            command=lambda: self._start_hotkey_capture("site"),
            padding=(10, 8),
        )
        self.hotkey_open_btn.pack(side="left")

        ttk.Checkbutton(
            misc_frame,
            text="Automatically return to lobby after the game",
            variable=self.play_again_var,
            command=lambda: self.parent.update_param("auto_play_again_enabled", self.play_again_var.get()),
            bootstyle="info-round-toggle",
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            misc_frame,
            text="Hide Main LOL when LoL starts (3 seconds)",
            variable=self.auto_hide_var,
            command=lambda: self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get()),
            bootstyle="secondary-round-toggle",
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            misc_frame,
            text="Close Main LOL when LoL closes",
            variable=self.close_on_exit_var,
            command=lambda: self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get()),
            bootstyle="danger-round-toggle",
        ).pack(anchor="w", pady=2)

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

    def _get_profile_role_data(self, role: Optional[str] = None) -> Dict[str, str]:
        params = self.parent.get_params()
        target_role = self._normalize_role(role or self._get_selected_profile_role())
        if target_role == "GLOBAL":
            return {
                "selected_pick_1": params.get("selected_pick_1", ""),
                "selected_pick_2": params.get("selected_pick_2", ""),
                "selected_pick_3": params.get("selected_pick_3", ""),
                "selected_ban": params.get("selected_ban", ""),
                "spell_1": params.get("global_spell_1", ""),
                "spell_2": params.get("global_spell_2", ""),
            }
        role_profiles = params.get("role_profiles", {})
        role_data = role_profiles.get(target_role, {}) if isinstance(role_profiles, dict) else {}
        if not isinstance(role_data, dict):
            role_data = {}
        return {
            "selected_pick_1": role_data.get("selected_pick_1", ""),
            "selected_pick_2": role_data.get("selected_pick_2", ""),
            "selected_pick_3": role_data.get("selected_pick_3", ""),
            "selected_ban": role_data.get("selected_ban", ""),
            "spell_1": role_data.get("spell_1", ""),
            "spell_2": role_data.get("spell_2", ""),
        }

    def _get_profile_value(self, key: str) -> str:
        return self._get_profile_role_data().get(key, "")

    def _get_global_fallback_value(self, key: str) -> str:
        params = self.parent.get_params()
        global_map = {
            "selected_pick_1": params.get("selected_pick_1", ""),
            "selected_pick_2": params.get("selected_pick_2", ""),
            "selected_pick_3": params.get("selected_pick_3", ""),
            "selected_ban": params.get("selected_ban", ""),
            "spell_1": params.get("global_spell_1", ""),
            "spell_2": params.get("global_spell_2", ""),
        }
        return global_map.get(key, "")

    def _get_display_value(self, key: str) -> str:
        value = self._get_profile_value(key)
        if value:
            return value
        if self._get_selected_profile_role() != "GLOBAL":
            fallback = self._get_global_fallback_value(key)
            if fallback:
                return f"Fallback: {fallback}"
        return "..."

    def _set_profile_value(self, key: str, value: str) -> None:
        role = self._get_selected_profile_role()
        if role == "GLOBAL":
            key_map = {"spell_1": "global_spell_1", "spell_2": "global_spell_2"}
            self.parent.update_param(key_map.get(key, key), value)
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

    def _select_champion(self, context: str, champ_name: str, slot_num: int = 1) -> None:
        if context == "ban":
            self._set_profile_value("selected_ban", champ_name)
        elif slot_num == 1:
            self._set_profile_value("selected_pick_1", champ_name)
        elif slot_num == 2:
            self._set_profile_value("selected_pick_2", champ_name)
        elif slot_num == 3:
            self._set_profile_value("selected_pick_3", champ_name)
        self._refresh_profile_buttons()

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

    def _refresh_stats_site_button(self) -> None:
        if hasattr(self, "stats_site_btn"):
            label = STATS_SITE_LABELS.get(self.preferred_stats_site_var.get(), STATS_SITE_LABELS["opgg"])
            self.stats_site_btn.configure(text=label)

    def _refresh_hotkey_site_button(self) -> None:
        if hasattr(self, "hotkey_site_btn"):
            label = HOTKEY_SITE_LABELS.get(self.preferred_hotkey_site_var.get(), HOTKEY_SITE_LABELS["porofessor"])
            self.hotkey_site_btn.configure(text=label)

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
        self._refresh_profile_buttons()
        self._refresh_spell_buttons()
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
        return {champion for champion in excluded if champion}

    def _open_champion_picker(self, context: str, slot_num: int = 1) -> None:
        open_champion_picker(self, context, slot_num)

    def _open_spell_picker(self, spell_slot_num: int) -> None:
        if not self.auto_summoners_var.get():
            return

        picker = ttk.Toplevel(self.window)
        if self.window._icon_img:
            picker.iconphoto(False, self.window._icon_img)
        picker.title(f"Choose Spell {spell_slot_num}")
        picker.geometry(f"380x420+{self.window.winfo_x()+50}+{self.window.winfo_y()+100}")
        picker.resizable(False, False)
        container = ttk.Frame(picker, padding=10)
        container.pack(fill="both", expand=True)

        def on_pick(spell_name: str) -> None:
            other_key = "spell_2" if spell_slot_num == 1 else "spell_1"
            current_other = self._get_profile_value(other_key) or self._get_global_fallback_value(other_key)
            if spell_name == current_other and spell_name != "(None)":
                self._set_profile_value(other_key, "(None)")

            target_key = "spell_1" if spell_slot_num == 1 else "spell_2"
            self._set_profile_value(target_key, spell_name)
            self._refresh_spell_buttons()
            picker.destroy()

        row, col = 0, 0
        for spell in self.spell_list:
            spell_frame = ttk.Frame(container)
            spell_frame.grid(row=row, column=col, padx=5, pady=5)
            btn = ttk.Button(spell_frame, text=spell, bootstyle="link", command=lambda s=spell: on_pick(s), compound="top")
            btn.pack()
            self._load_img_into_btn(btn, spell, False, size=(42, 42))
            col += 1
            if col > 3:
                col = 0
                row += 1

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

    def _refresh_profile_buttons(self) -> None:
        self._update_btn_content(self.btn_ban, self._get_display_value("selected_ban"), True)
        self._update_btn_content(self.btn_pick_1, self._get_display_value("selected_pick_1"), True)
        self._update_btn_content(self.btn_pick_2, self._get_display_value("selected_pick_2"), True)
        self._update_btn_content(self.btn_pick_3, self._get_display_value("selected_pick_3"), True)
        self._refresh_role_selector_button()

    def _refresh_spell_buttons(self) -> None:
        self._update_btn_content(self.btn_spell_1, self._get_display_value("spell_1"), False)
        self._update_btn_content(self.btn_spell_2, self._get_display_value("spell_2"), False)

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
            self.lbl_auto_detect.configure(text=f"Automatic account detection (detected account: {detected})")
        else:
            self.lbl_auto_detect.configure(text="Automatic account detection")

    def _sync_from_params(self) -> None:
        params = self.parent.get_params()
        self.auto_accept_var.set(params.get("auto_accept_enabled", True))
        self.auto_pick_var.set(params.get("auto_pick_enabled", True))
        self.auto_ban_var.set(params.get("auto_ban_enabled", True))
        self.auto_summoners_var.set(params.get("auto_summoners_enabled", True))
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
        self.parent.update_param("auto_summoners_enabled", self.auto_summoners_var.get())
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
