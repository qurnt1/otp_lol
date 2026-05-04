"""
FILE NAME: src/ui/settings_window.py
GLOBAL PURPOSE:
- Render and manage the editable application settings window.
- Persist user edits back to the main window state while keeping previews and shortcuts synchronized.

KEY FUNCTIONS:
- SettingsWindow: Own the settings dialog and its editing state.
- _get_effective_pick_slot_config: Compute the effective slot configuration with global fallbacks.
- _start_hotkey_capture: Temporarily enter shortcut capture mode without triggering existing hotkeys.
- on_close: Persist edited values back into the parent UI state before destroying the window.

AUDIENCE & LOGIC:
Why:
This module isolates settings editing complexity so picker dialogs and shortcut capture rules do not leak into the main window.
For whom:
Developers maintaining configuration UX and settings persistence.

DEPENDENCIES:
Used by:
- src/ui/main_window.py
Uses:
- Standard library: datetime, logging, os, random, tkinter, typing
- Third-party libraries: Pillow, ttkbootstrap
- Local modules: src.config, src.ui.champion_picker, src.ui.role_picker, src.ui.skin_picker, src.ui.site_picker
"""

import logging
import os
import webbrowser
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
    GITHUB_REPO_URL,
    HOTKEY_SITE_LABELS,
    PICK_SLOT_LABELS,
    PICK_SLOT_ORDER,
    REGION_LIST,
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
from .settings_hotkeys import SettingsHotkeysMixin
from .settings_runes import SettingsRunesMixin
from .settings_skin import SettingsSkinMixin
from .site_picker import _load_site_logo, open_site_picker

if TYPE_CHECKING:
    from .main_window import LoLAssistantUI


class SettingsWindow(SettingsSkinMixin, SettingsRunesMixin, SettingsHotkeysMixin):
    """Manage the settings dialog and the profile-aware configuration it edits."""

    PRESET_LABELS = {
        "pick_1": "Preset 1",
        "pick_2": "Preset 2",
        "pick_3": "Preset 3",
    }
    PICK_ICON_SIZE = (30, 30)
    RUNE_BUTTON_ICON_SIZE = (44, 30)

    def __init__(self, parent: "LoLAssistantUI"):
        """Create the settings dialog and initialize its editable view state."""
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title(f"Settings - {APP_NAME}")
        self.window.geometry("980x820")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self.main_frame: Optional[ttk.Frame] = None
        self.scroll_frame: Optional[ScrolledFrame] = None
        self.website_logo_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.local_button_image_cache: Dict[Any, ImageTk.PhotoImage] = {}
        self.role_picker_window: Optional[ttk.Toplevel] = None
        self.site_picker_window: Optional[ttk.Toplevel] = None
        self._capture_target: Optional[str] = None
        self._pressed_modifiers: set[str] = set()
        self.pick_buttons: Dict[str, ttk.Button] = {}
        self.pick_spell_buttons: Dict[tuple[str, int], ttk.Button] = {}
        self.pick_rune_buttons: Dict[str, ttk.Button] = {}
        self.pick_skin_buttons: Dict[str, ttk.Button] = {}
        self.skin_picker_window: Optional[ttk.Toplevel] = None
        self.rune_picker_window: Optional[ttk.Toplevel] = None
        self.all_champions = parent.dd.all_names if parent.dd.all_names else ["Garen", "Teemo", "Ashe"]
        self.spell_list = SUMMONER_SPELL_LIST[:]

        self._setup_window_icon()
        self._init_variables()
        # Widget creation is separated from state initialization so the window can
        # immediately reflect the current profile and parameter snapshot.
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
            logging.debug("Unable to load the settings window icon: %s", e)
            self.window._icon_img = None

    def _init_variables(self) -> None:
        """Populate Tk variables from the current parent parameter snapshot."""
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
        self.preferred_stats_site_var = tk.StringVar(value=params.get("preferred_stats_site", "opgg"))
        self.preferred_hotkey_site_var = tk.StringVar(value=params.get("preferred_hotkey_site", "porofessor"))
        self.hotkey_toggle_var = tk.StringVar(value=params.get("hotkey_toggle_window", "alt+c"))
        self.hotkey_open_site_var = tk.StringVar(value=params.get("hotkey_open_site", "alt+p"))
        self.theme_var = tk.StringVar(value=params.get("theme", "darkly"))
        self.play_again_var = tk.BooleanVar(value=params.get("auto_play_again_enabled", False))
        self.auto_hide_var = tk.BooleanVar(value=params.get("auto_hide_on_connect", True))
        self.close_on_exit_var = tk.BooleanVar(value=params.get("close_app_on_lol_exit", True))

    def create_widgets(self) -> None:
        """Build the settings UI sections and synchronize their initial state."""
        self.scroll_frame = ScrolledFrame(self.window, autohide=True, height=780)
        self.scroll_frame.pack(fill="both", expand=True)

        self.main_frame = ttk.Frame(self.scroll_frame, padding=15)
        self.main_frame.pack(fill="both", expand=True)
        for col in range(4):
            self.main_frame.columnconfigure(col, weight=1 if col > 0 else 0)

        row = 0
        row = self._create_general_section(row)
        row = self._create_champ_select_section(row)
        row = self._create_websites_section(row)
        row = self._create_shortcuts_section(row)
        self._create_other_section(row)

        report_btn = ttk.Button(
            self.main_frame,
            text="Report Issues",
            bootstyle="link",
            command=lambda: webbrowser.open(f"{GITHUB_REPO_URL}/issues/new"),
        )
        report_btn.grid(row=row + 5, column=0, columnspan=4, pady=(16, 4))

        self.toggle_pick()
        self.toggle_ban()
        self.toggle_spells()
        self.toggle_summoner_entry()
        self._load_initial_icons()

    @staticmethod
    def _create_section_title(parent: ttk.Frame, text: str, row: int) -> int:
        """Create a styled section header spanning all columns."""
        ttk.Separator(parent).grid(row=row, column=0, columnspan=4, sticky="we", pady=(18, 8))
        title = ttk.Label(
            parent,
            text=text,
            font=("Segoe UI", 11, "bold"),
        )
        title.grid(row=row + 1, column=0, columnspan=4, sticky="w", pady=(0, 6))
        return row + 2

    def _create_general_section(self, start_row: int) -> int:
        row = start_row
        # ── Action buttons ──
        top_frame = ttk.Frame(self.main_frame)
        top_frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        for col in range(4):
            top_frame.columnconfigure(col, weight=1, uniform="top-actions")

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
        row += 1

        # ── Auto-accept ──
        ttk.Checkbutton(
            self.main_frame,
            text="Automatically accept the game when a match is found",
            variable=self.auto_accept_var,
            command=lambda: self.parent.update_param("auto_accept_enabled", self.auto_accept_var.get()),
            bootstyle="success-round-toggle",
        ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(4, 0))
        row += 1

        # ── Account detection ──
        row = self._create_section_title(self.main_frame, "ACCOUNT", row)
        params = self.parent.get_params()
        detect_frame = ttk.Frame(self.main_frame)
        detect_frame.grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 5))
        row += 1

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

        ttk.Label(self.main_frame, text="Riot ID:", anchor="w").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.summ_entry = ttk.Entry(self.main_frame, textvariable=self.summoner_entry_var, state="readonly")
        self.summ_entry.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5)
        row += 1

        ttk.Label(self.main_frame, text="Region:", anchor="w").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.region_var = tk.StringVar(value=params.get("manual_region", "euw"))
        self.region_cb = ttk.Combobox(self.main_frame, values=REGION_LIST, textvariable=self.region_var, state="readonly")
        self.region_cb.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5)
        self.region_cb.bind("<<ComboboxSelected>>", self._on_manual_region_selected)
        row += 1

        return row

    def _get_preset_label(self, slot_key: str) -> str:
        return self.PRESET_LABELS.get(slot_key, PICK_SLOT_LABELS.get(slot_key, slot_key))

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _attach_tooltip(self, widget: tk.Widget, text: str) -> None:
        text = str(text or "").strip()
        if not text:
            return

        tooltip_state = {"window": None}

        def show_tooltip(event) -> None:
            if tooltip_state["window"] is not None:
                return
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 10}")
            label = tk.Label(
                tooltip,
                text=text,
                bg="#111827",
                fg="#f9fafb",
                padx=6,
                pady=3,
                borderwidth=1,
                relief="solid",
                font=("Segoe UI", 8),
            )
            label.pack()
            tooltip_state["window"] = tooltip

        def hide_tooltip(_event=None) -> None:
            tooltip = tooltip_state.get("window")
            if tooltip is not None:
                tooltip.destroy()
                tooltip_state["window"] = None

        widget.bind("<Enter>", show_tooltip, add="+")
        widget.bind("<Leave>", hide_tooltip, add="+")
        widget.bind("<ButtonPress>", hide_tooltip, add="+")

    def _create_champ_select_section(self, start_row: int) -> int:
        row = self._create_section_title(self.main_frame, "CHAMPION SELECT", start_row)


        # ── Presets toggle ──
        presets_frame = ttk.Frame(self.main_frame)
        presets_frame.grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.presets_toggle = ttk.Checkbutton(
            presets_frame,
            text="Enable presets",
            variable=self.presets_enabled_var,
            command=self._toggle_profile_presets,
            bootstyle="info-round-toggle",
        )
        self.presets_toggle.pack(side="left")
        row += 1

        # ── Three preset slots ──
        picks_first_row = row
        picks_frame = ttk.Frame(self.main_frame)
        picks_frame.grid(row=picks_first_row, column=1, columnspan=3, sticky="ew", padx=5, pady=4, rowspan=3)
        picks_frame.columnconfigure(0, weight=2, minsize=130)
        picks_frame.columnconfigure(1, weight=1, minsize=110)
        picks_frame.columnconfigure(2, weight=1, minsize=110)
        picks_frame.columnconfigure(3, weight=1, minsize=110)
        picks_frame.columnconfigure(4, weight=2, minsize=140)

        for slot_num, slot_key in enumerate(PICK_SLOT_ORDER, start=1):
            row_index = row + slot_num - 1
            ttk.Label(self.main_frame, text=f"{self._get_preset_label(slot_key)} :").grid(
                row=row_index,
                column=0,
                sticky="e",
                padx=5,
                pady=4,
            )

            inner_row = slot_num - 1
            inner_pady = (0, 6) if inner_row < 2 else (0, 0)

            champion_btn = ttk.Button(
                picks_frame,
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=16,
                command=lambda key=slot_key: self._open_pick_slot_champion_picker(key),
            )
            champion_btn.grid(row=inner_row, column=0, sticky="ew", padx=(0, 6), pady=inner_pady)
            self.pick_buttons[slot_key] = champion_btn

            spell_1_btn = ttk.Button(
                picks_frame,
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=13,
                command=lambda key=slot_key: self._open_spell_picker(key, 1),
            )
            spell_1_btn.grid(row=inner_row, column=1, sticky="ew", padx=3, pady=inner_pady)
            self.pick_spell_buttons[(slot_key, 1)] = spell_1_btn

            spell_2_btn = ttk.Button(
                picks_frame,
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=13,
                command=lambda key=slot_key: self._open_spell_picker(key, 2),
            )
            spell_2_btn.grid(row=inner_row, column=2, sticky="ew", padx=3, pady=inner_pady)
            self.pick_spell_buttons[(slot_key, 2)] = spell_2_btn

            rune_btn = ttk.Button(
                picks_frame,
                text="Runes",
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=13,
                command=lambda key=slot_key: self._open_rune_picker(key),
            )
            rune_btn.grid(row=inner_row, column=3, sticky="ew", padx=3, pady=inner_pady)
            self.pick_rune_buttons[slot_key] = rune_btn

            skin_btn = ttk.Button(
                picks_frame,
                text="Skin",
                bootstyle="secondary-outline",
                padding=(8, 8),
                width=18,
                command=lambda key=slot_key: self._open_skin_picker(key),
            )
            skin_btn.grid(row=inner_row, column=4, sticky="ew", padx=(6, 0), pady=inner_pady)
            self.pick_skin_buttons[slot_key] = skin_btn

        row += 3

        # ── Ban ── (directly after presets, no separator)
        ttk.Checkbutton(
            self.main_frame,
            text="Ban a champion",
            variable=self.auto_ban_var,
            command=lambda: (
                self.parent.update_param("auto_ban_enabled", self.auto_ban_var.get()),
                self.toggle_ban(),
            ),
            bootstyle="danger-round-toggle",
        ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(10, 4))
        row += 1

        ttk.Label(self.main_frame, text="Ban:").grid(row=row, column=0, sticky="e", padx=5)
        self.btn_ban = ttk.Button(self.main_frame, bootstyle="secondary-outline", padding=(10, 8))
        self.btn_ban.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5)
        self.btn_ban.configure(command=lambda: self._open_champion_picker("ban"))
        row += 1

        return row

    def _create_websites_section(self, start_row: int) -> int:
        row = self._create_section_title(self.main_frame, "WEBSITES", start_row)

        ttk.Label(self.main_frame, text="Preferred stats site:").grid(row=row, column=0, sticky="e", padx=5, pady=(0, 8))
        self.stats_site_btn = ttk.Button(
            self.main_frame,
            bootstyle="secondary-outline",
            command=lambda: self._open_site_picker("stats"),
            width=26,
            padding=(8, 8),
            compound="left",
        )
        self.stats_site_btn.grid(row=row, column=1, sticky="w", columnspan=3, pady=(0, 8))
        self._refresh_stats_site_button()
        row += 1

        ttk.Label(self.main_frame, text="Shortcut website:").grid(row=row, column=0, sticky="e", padx=5, pady=(0, 8))
        self.hotkey_site_btn = ttk.Button(
            self.main_frame,
            bootstyle="secondary-outline",
            command=lambda: self._open_site_picker("hotkey"),
            width=26,
            padding=(8, 8),
            compound="left",
        )
        self.hotkey_site_btn.grid(row=row, column=1, sticky="w", columnspan=3, pady=(0, 8))
        self._refresh_hotkey_site_button()
        row += 1

        return row

    def _create_shortcuts_section(self, start_row: int) -> int:
        row = self._create_section_title(self.main_frame, "SHORTCUTS", start_row)

        ttk.Label(self.main_frame, text="Show / hide app:").grid(row=row, column=0, sticky="e", padx=5, pady=(0, 8))
        self.hotkey_toggle_btn = ttk.Button(
            self.main_frame,
            text=self._format_hotkey_display(self.hotkey_toggle_var.get()),
            bootstyle="secondary-outline",
            width=26,
            command=lambda: self._start_hotkey_capture("toggle"),
            padding=(8, 8),
        )
        self.hotkey_toggle_btn.grid(row=row, column=1, sticky="w", columnspan=3, pady=(0, 8))
        row += 1

        ttk.Label(self.main_frame, text="Open website:").grid(row=row, column=0, sticky="e", padx=5, pady=(0, 8))
        self.hotkey_open_btn = ttk.Button(
            self.main_frame,
            text=self._format_hotkey_display(self.hotkey_open_site_var.get()),
            bootstyle="secondary-outline",
            width=26,
            command=lambda: self._start_hotkey_capture("site"),
            padding=(8, 8),
        )
        self.hotkey_open_btn.grid(row=row, column=1, sticky="w", columnspan=3, pady=(0, 8))
        row += 1

        return row

    def _create_other_section(self, start_row: int) -> None:
        self._create_section_title(self.main_frame, "OTHER", start_row)

        ttk.Checkbutton(
            self.main_frame,
            text="Automatically return to lobby after the game",
            variable=self.play_again_var,
            command=lambda: self.parent.update_param("auto_play_again_enabled", self.play_again_var.get()),
            bootstyle="info-round-toggle",
        ).grid(row=start_row + 2, column=0, columnspan=4, sticky="w", pady=(0, 4))

        ttk.Checkbutton(
            self.main_frame,
            text=f"Hide {APP_NAME} when LoL starts (3 seconds)",
            variable=self.auto_hide_var,
            command=lambda: self.parent.update_param("auto_hide_on_connect", self.auto_hide_var.get()),
            bootstyle="secondary-round-toggle",
        ).grid(row=start_row + 3, column=0, columnspan=4, sticky="w", pady=4)

        ttk.Checkbutton(
            self.main_frame,
            text=f"Close {APP_NAME} when LoL closes",
            variable=self.close_on_exit_var,
            command=lambda: self.parent.update_param("close_app_on_lol_exit", self.close_on_exit_var.get()),
            bootstyle="danger-round-toggle",
        ).grid(row=start_row + 4, column=0, columnspan=4, sticky="w", pady=4)

    def _load_initial_icons(self) -> None:
        self._refresh_profile_buttons()
        self._refresh_spell_buttons()










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
    def _strip_active_suffix(value: str) -> str:
        return str(value or "").removesuffix(" (active)")

    @staticmethod
    def _slot_number_from_key(slot_key: str) -> int:
        return PICK_SLOT_ORDER.index(slot_key) + 1

    def _open_pick_slot_champion_picker(self, slot_key: str) -> None:
        self._open_champion_picker("pick", self._slot_number_from_key(slot_key))




















    @staticmethod
    def _truncate_button_label(label: str, max_chars: int = 16) -> str:
        text = str(label or "").strip()
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 3].rstrip()}..."

    def _select_champion(self, context: str, champ_name: str, slot_num: int = 1) -> None:
        if context == "ban":
            self.parent.update_param("selected_ban", champ_name)
        elif slot_num == 1:
            self.parent.update_param("selected_pick_1", champ_name)
            self._clear_pick_slot_skin("pick_1")
        elif slot_num == 2:
            self.parent.update_param("selected_pick_2", champ_name)
            self._clear_pick_slot_skin("pick_2")
        elif slot_num == 3:
            self.parent.update_param("selected_pick_3", champ_name)
            self._clear_pick_slot_skin("pick_3")
        self._refresh_profile_buttons()
        self._refresh_skin_buttons()





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
        self.parent.update_param("auto_pick_enabled", enabled)
        self.parent.update_param("auto_summoners_enabled", enabled)
        self.toggle_pick()
        self.toggle_spells()
        self.toggle_runes()

    def _set_profile_presets_enabled(self, enabled: bool) -> None:
        self.parent.update_param("presets_enabled", enabled)

    def _get_profile_presets_enabled(self) -> bool:
        return bool(self.parent.get_params().get("presets_enabled", True))

    def _get_effective_pick_slot_config(self, slot_key: str) -> Dict[str, Any]:
        pick_slots = self.parent.get_params().get("pick_slots", {})
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        return dict(slot_data) if isinstance(slot_data, dict) else {}

    def _get_slot_champion_name(self, slot_key: str) -> str:
        slot_number = PICK_SLOT_ORDER.index(slot_key) + 1
        return self.parent.get_params().get(f"selected_pick_{slot_number}", "") or ""

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
        params = self.parent.get_params()
        excluded = set()
        pick_1 = params.get("selected_pick_1")
        pick_2 = params.get("selected_pick_2")
        pick_3 = params.get("selected_pick_3")
        banned = params.get("selected_ban")
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
        spell_choices = ["(None)", *[spell for spell in self.spell_list if spell != "(None)"]]
        for spell in spell_choices:
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
                logging.debug("Icon loading error for %s: %s", display_name, e)

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
                logging.debug("Image loading error for %s: %s", name, e)

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
                logging.debug("Remote image loading error for %s: %s", url, e)

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
            logging.debug("Local image loading error for %s: %s", relative_path, e)

    def _load_empty_img_into_btn(
        self,
        btn_widget: ttk.Button,
        *,
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        final_size = size or self.PICK_ICON_SIZE
        cache_key = ("__empty__", final_size)
        cached = self.local_button_image_cache.get(cache_key)
        if not cached:
            photo = ImageTk.PhotoImage(Image.new("RGBA", final_size, (0, 0, 0, 0)))
            self.local_button_image_cache[cache_key] = photo
            cached = photo
        if btn_widget.winfo_exists():
            btn_widget.configure(image=cached)
            btn_widget.image = cached

    def _refresh_profile_buttons(self) -> None:
        params = self.parent.get_params()
        self._update_btn_content(self.btn_ban, self._format_visible_value(params.get("selected_ban", "")), True)
        for index, slot_key in enumerate(PICK_SLOT_ORDER, start=1):
            button = self.pick_buttons.get(slot_key)
            if button and button.winfo_exists():
                self._update_btn_content(button, self._format_visible_value(params.get(f"selected_pick_{index}", "")), True)

    def _refresh_spell_buttons(self) -> None:
        params = self.parent.get_params()
        pick_slots = params.get("pick_slots", {})
        for slot_key in PICK_SLOT_ORDER:
            slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
            for spell_slot_num in (1, 2):
                button = self.pick_spell_buttons.get((slot_key, spell_slot_num))
                if button and button.winfo_exists():
                    self._update_btn_content(
                        button,
                        self._format_visible_value(str(slot_data.get(f"spell_{spell_slot_num}", ""))),
                        False,
                    )
        self._refresh_rune_buttons()
        self._refresh_skin_buttons()

    def toggle_summoner_entry(self) -> None:
        """Switch between auto-detected and manual account entry modes."""
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

    def toggle_runes(self) -> None:
        state = "normal" if self.presets_enabled_var.get() else "disabled"
        for button in getattr(self, "pick_rune_buttons", {}).values():
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
        if self.window.winfo_exists():
            self.window.update_idletasks()

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
        """Export the current parameter snapshot to a user-selected JSON file."""
        default_name = f"otp_lol_config_{datetime.now().strftime('%Y-%m-%d')}.json"
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
        """Import a JSON configuration file and refresh the settings UI from it."""
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
            logging.warning("Import failed: %s", e)
            self.parent.show_toast("Invalid configuration.")
            return

        self.parent.replace_params(imported)
        self.parent.save_params()
        self.parent.apply_theme(imported.get("theme", "darkly"))
        self._sync_from_params()
        self.parent.show_toast("Configuration imported!")

    def _poll_summoner_label(self) -> None:
        """Refresh auto-detected account labels while the settings window stays open."""
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
        """Persist edited settings back to the parent UI and close the dialog."""
        if self._capture_target:
            self._cancel_hotkey_capture()
        if getattr(self, "skin_picker_window", None) and self.skin_picker_window.winfo_exists():
            self.skin_picker_window.destroy()
        if getattr(self, "rune_picker_window", None) and self.rune_picker_window.winfo_exists():
            self.rune_picker_window.destroy()
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
