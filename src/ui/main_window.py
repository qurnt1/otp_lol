"""
FILE NAME: src/ui/main_window.py
GLOBAL PURPOSE:
- Render the main desktop window and keep it synchronized with live client state.
- Centralize user-facing controls such as status, previews, tray integration, hotkeys, history, and update prompts.
- Expose a safe UI-thread boundary for events emitted by the websocket layer.

KEY FUNCTIONS:
- LoLAssistantUI: Own the main window, shared UI services, and event wiring.
- get_effective_profile_config: Resolve the profile data shown by the main preview when the websocket is unavailable.
- _refresh_feature_preview: Rebuild the compact home-screen summary of picks, ban, and skin state.
- _handle_core_event: Translate core-layer events into safe Tk UI updates.
- stop: Shut down background helpers and destroy the Tk root cleanly.

AUDIENCE & LOGIC:
Why:
This module exists as the single UI shell so cross-cutting behaviors such as tray control, hotkeys, preview state, and event marshaling stay consistent.
For whom:
Developers maintaining the desktop UX, UI-thread boundaries, and interactions with core services.

DEPENDENCIES:
Used by:
- launcher.py and src/ui/settings_window.py
Uses:
- Standard library: concurrent.futures, logging, os, re, tkinter, typing, webbrowser
- Third-party libraries: Pillow, ttkbootstrap
- Local modules: src.config, src.services.history, src.utils, src.ui.hotkeys, src.ui.media, src.ui.settings_window, src.ui.tray
"""

import logging
import os
import re
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from tkinter import scrolledtext
from typing import Any, Callable, Dict, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from ..config import (
    APP_NAME,
    APP_IMAGE_FILES,
    CURRENT_VERSION,
    GITHUB_DOWNLOAD_ZIP_URL,
    GITHUB_REPO_URL,
    THEME_PALETTE,
    WEBSITE_LOGO_FILES,
    resource_path,
)
from ..services.history import clear_history_entries, format_history_entry, get_history_entries
from ..utils import build_hotkey_site_url, build_stats_site_url, is_valid_riot_id
from .hotkeys import HotkeyManager
from .main_preview import MainPreviewMixin
from .main_skin_overrides import MainSkinOverridesMixin
from .media import AudioManager
from .settings_window import SettingsWindow
from .tray import TrayController


class LoLAssistantUI(MainPreviewMixin, MainSkinOverridesMixin):
    """Own the primary application window and its user-facing runtime helpers."""

    MAX_WORKERS = 4
    DISCONNECT_CLOSE_DELAY_MS = 8000
    PREVIEW_ICON_SIZE = 30
    PREVIEW_TOP_RELY = 0.47
    STATS_BUTTON_TOP_RELY = 0.79
    FEATURE_PREVIEW_DEFINITIONS = (
        ("presets", "Presets", 3, "info"),
        ("ban", "Ban", 1, "danger"),
        ("skins", "Skin", 3, "info"),
    )
    FEATURE_PARAM_MAP = {
        "ban": "auto_ban_enabled",
    }
    FEATURE_LABEL_MAP = {
        "presets": "Presets",
        "ban": "Auto-ban",
        "skins": "Skin",
    }

    def __init__(
        self,
        dd,
        params: Dict[str, Any],
        save_callback: Callable[[], None],
        update_param_callback: Callable[[str, Any], None],
        get_params_callback: Callable[[], Dict[str, Any]],
        quit_callback: Callable[[], None],
    ):
        """Initialize the main window and the helper services it coordinates."""
        self.dd = dd
        self._params = params
        self._save_callback = save_callback
        self._update_param_callback = update_param_callback
        self._get_params_callback = get_params_callback
        self._quit_callback = quit_callback
        self.running = True
        self.closing_requested = False
        self.settings_win: Optional[SettingsWindow] = None
        self.ws_manager = None
        self.disconnect_close_after_id = None
        self.history_window = None
        self.history_text = None
        self.history_after_id = None
        self.executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        self.audio_manager = AudioManager()
        self.tray_controller = TrayController()
        self.hotkey_manager = HotkeyManager()
        self._hotkeys_suspended = False
        self._hotkeys_were_available = False
        self._toast_queue: list[tuple[str, int]] = []
        self._toast_active = False
        self.theme = params.get("theme", "darkly") if params.get("theme", "darkly") in THEME_PALETTE else "darkly"
        self.root = ttk.Window(themename=self.theme)
        self.root.title(APP_NAME)
        wx = params.get("window_x", 0)
        wy = params.get("window_y", 0)
        geometry = f"420x250+{wx}+{wy}" if wx or wy else "420x250"
        self.root.geometry(geometry)
        self.root.resizable(False, False)
        self.theme_var = tk.StringVar(value=self.theme)
        self.banner_label: Optional[ttk.Label] = None
        self.connection_indicator: Optional[tk.Canvas] = None
        self.status_label: Optional[ttk.Label] = None
        self.preview_placeholder = ImageTk.PhotoImage(
            Image.new("RGBA", (self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), (0, 0, 0, 0))
        )
        self.preview_icon_cache: Dict[tuple[Any, ...], ImageTk.PhotoImage] = {}
        self.feature_preview_frame: Optional[ttk.Frame] = None
        self.feature_group_frames: Dict[str, ttk.Frame] = {}
        self.feature_status_labels: Dict[str, tk.Label] = {}
        self.feature_icon_labels: Dict[str, list[tk.Label]] = {}
        self._last_preview_signature = None
        self._preview_refresh_after_id = None
        self.stats_btn: Optional[ttk.Button] = None
        self.website_logo_cache: Dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.settings_gear_label: Optional[ttk.Label] = None
        self.history_filter_var = tk.StringVar(value="All")
        # Build the window before tray and hotkey services so callbacks always
        # have a valid Tk root to target.
        self.create_ui()
        self.apply_theme(self.theme)
        self.create_system_tray()
        self.setup_hotkeys()
        self._refresh_safe_controls()

    @property
    def tray_available(self) -> bool:
        return self.tray_controller.available

    def set_ws_manager(self, ws_manager) -> None:
        """Attach the live websocket manager once launcher wiring is complete."""
        self.ws_manager = ws_manager
        self._queue_feature_preview_refresh(force=True)
        self._refresh_stats_button()

    def get_params(self) -> Dict[str, Any]:
        return self._get_params_callback()

    def update_param(self, key: str, value: Any) -> None:
        """Update one parameter and refresh the UI surfaces that depend on it."""
        self._update_param_callback(key, value)
        self._queue_feature_preview_refresh(force=True)
        self._refresh_stats_button()
        if key == "theme":
            self.apply_theme(value)
        if key in {"hotkey_toggle_window", "hotkey_open_site"} and not self._hotkeys_suspended:
            self.reload_hotkeys()

    def replace_params(self, params: Dict[str, Any]) -> None:
        for key, value in params.items():
            self._update_param_callback(key, value)
            if key == "theme":
                self.apply_theme(value)
        self._queue_feature_preview_refresh(force=True)
        self._refresh_stats_button()
        if {"hotkey_toggle_window", "hotkey_open_site"} & set(params) and not self._hotkeys_suspended:
            self.reload_hotkeys()

    def save_params(self) -> None:
        self._save_callback()

    def save_and_notify(self) -> None:
        self.save_params()
        self.show_toast("Settings saved!")

    def apply_theme(self, theme_name: str) -> None:
        theme_name = theme_name if theme_name in THEME_PALETTE else "darkly"
        self.theme = theme_name
        self.theme_var.set(theme_name)
        palette = THEME_PALETTE[theme_name]

        try:
            self.root.style.theme_use(theme_name)
        except Exception as e:
            logging.debug("Unable to apply theme %s: %s", theme_name, e)

        self._configure_styles()

        if self.connection_indicator and self.connection_indicator.winfo_exists():
            self.connection_indicator.configure(bg=palette["window_bg"])

        if self.status_label and self.status_label.winfo_exists():
            self.status_label.configure(bg=palette["window_bg"], fg=palette["text"])
        if self.banner_label and self.banner_label.winfo_exists():
            self.banner_label.configure(background=palette["window_bg"])
        if self.settings_gear_label and self.settings_gear_label.winfo_exists():
            self.settings_gear_label.configure(background=palette["window_bg"])
        self._apply_preview_palette()
        self._refresh_history_colors()
        self._refresh_settings_gear_icon()
        self._last_preview_signature = None
        self._queue_feature_preview_refresh(force=True)
        self.update_connection_indicator(self.is_ws_active())

    def is_ws_active(self) -> bool:
        return self.ws_manager.is_active if self.ws_manager else False

    def get_auto_summoner_name(self) -> Optional[str]:
        params = self.get_params()
        return params.get("auto_detected_riot_id") or (self.ws_manager.get_riot_id() if self.ws_manager else None)

    def get_platform_for_websites(self) -> str:
        params = self.get_params()
        if params.get("summoner_name_auto_detect", True):
            detected = self.ws_manager.get_platform_for_websites() if self.ws_manager else "euw"
            return (params.get("auto_detected_region") or detected).lower()
        return params.get("manual_region", "euw").lower()

    def force_refresh_summoner(self) -> None:
        if self.ws_manager:
            self.ws_manager.force_refresh_summoner()

    def create_ui(self) -> None:
        """Build the persistent main-window sections in the order they appear on screen."""
        self._configure_styles()
        self._create_banner()
        self._create_connection_indicator()
        self._create_status_label()
        self._create_feature_preview()
        self._create_settings_gear()
        self._create_opgg_button()
        self.root.protocol("WM_DELETE_WINDOW", self._handle_window_close)

    def _configure_styles(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        self.root.configure(bg=palette["window_bg"])
        style = ttk.Style()
        style.configure(".", font=("Segoe UI Emoji", 10))
        style.configure("Status.TLabel", font=("Segoe UI Emoji", 11), background=palette["window_bg"], foreground=palette["text"])
        style.configure("FeatureTitle.TLabel", font=("Segoe UI", 9, "bold"), background=palette["window_bg"], foreground=palette["text"])
        style.configure("FeatureHint.TLabel", font=("Segoe UI", 9), background=palette["window_bg"], foreground=palette["muted"])
        style.configure("Feature.TFrame", background=palette["surface_bg"])
        style.configure("FeatureSlot.TLabel", font=("Segoe UI", 9), background=palette["surface_bg"], foreground=palette["muted"])
        style.configure("AppSecondary.TButton", padding=(10, 8))
        style.configure("UpdatePopup.TButton", padding=(14, 8))

    def _create_banner(self) -> None:
        try:
            garen_icon = ImageTk.PhotoImage(Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((32, 32)))
            self.root.iconphoto(False, garen_icon)
            banner_img = ImageTk.PhotoImage(Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((48, 48)))
            self.banner_label = ttk.Label(self.root, image=banner_img)
            self.banner_label.image = banner_img
            self.banner_label.place(relx=0.5, rely=0.08, anchor="n")
        except Exception as e:
            logging.debug("Unable to load banner images: %s", e)

    def _create_connection_indicator(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        self.connection_indicator = tk.Canvas(self.root, width=12, height=12, bd=0, highlightthickness=0, bg=palette["window_bg"])
        self.connection_indicator.place(relx=0.05, rely=0.05, anchor="nw")
        self.update_connection_indicator(False)

    def _create_status_label(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        self.status_label = tk.Label(
            self.root,
            text="Waiting for League of Legends to launch...",
            justify="center",
            wraplength=390,
            bg=palette["window_bg"],
            fg=palette["text"],
            font=("Segoe UI Emoji", 11),
        )
        self.status_label.place(relx=0.5, rely=0.34, anchor="center")

    def _create_settings_gear(self) -> None:
        self.settings_gear_label = ttk.Label(self.root, cursor="hand2")
        self.settings_gear_label.place(relx=0.95, rely=0.05, anchor="ne")
        self.settings_gear_label.bind("<Button-1>", lambda e: self.open_settings())
        self._refresh_settings_gear_icon()

    def _get_settings_gear_path(self) -> str:
        icon_key = "gear_light" if self.theme == "darkly" else "gear_dark"
        return resource_path(APP_IMAGE_FILES.get(icon_key, APP_IMAGE_FILES["gear"]))

    def _refresh_settings_gear_icon(self) -> None:
        if not self.settings_gear_label or not self.settings_gear_label.winfo_exists():
            return

        gear_path = self._get_settings_gear_path()
        if os.path.exists(gear_path):
            try:
                gear_img = ImageTk.PhotoImage(Image.open(gear_path).resize((25, 30)))
                self.settings_gear_label.configure(image=gear_img, text="")
                self.settings_gear_label.image = gear_img
                return
            except Exception as e:
                logging.debug("Unable to load gear icon: %s", e)
        self.settings_gear_label.configure(image="", text="⚙")
        self.settings_gear_label.image = None

    def _load_site_logo(self, site: str, size: int = 28):
        cache_key = (site, size)
        if cache_key in self.website_logo_cache:
            return self.website_logo_cache[cache_key]

        icon_rel_path = WEBSITE_LOGO_FILES.get(site)
        if not icon_rel_path:
            return None

        icon_path = resource_path(icon_rel_path)
        if not os.path.exists(icon_path):
            alt_path = os.path.splitext(icon_path)[0] + ".webp"
            if os.path.exists(alt_path):
                icon_path = alt_path
            else:
                return None

        try:
            image = Image.open(icon_path).convert("RGBA")
            image.thumbnail((size, size), Image.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            left = (size - image.width) // 2
            top = (size - image.height) // 2
            canvas.paste(image, (left, top), image)
            photo = ImageTk.PhotoImage(canvas)
            self.website_logo_cache[cache_key] = photo
            return photo
        except Exception:
            return None

    def _create_opgg_button(self) -> None:
        self.stats_btn = ttk.Button(
            self.root,
            text="View my stats",
            bootstyle="success-outline",
            padding=(16, 10),
            width=22,
            compound="right",
            command=self.open_preferred_stats_site,
        )
        self.stats_btn.place(relx=0.5, rely=self.STATS_BUTTON_TOP_RELY, anchor="n")
        self._refresh_stats_button()

    def _bind_click_tree(self, widget: tk.Misc, callback: Callable[[Any], str]) -> None:
        for current in self._iter_widget_tree(widget):
            try:
                current.bind("<Button-1>", callback)
                current.configure(cursor="hand2")
            except Exception:
                continue

    def _bind_feature_group(self, widget: tk.Misc, feature_key: str) -> None:
        self._bind_click_tree(widget, lambda event, key=feature_key: self._on_feature_group_click(key, event))

    def _iter_widget_tree(self, widget: tk.Misc):
        yield widget
        for child in widget.winfo_children():
            yield from self._iter_widget_tree(child)

    def build_preferred_stats_url(self) -> str:
        params = self.get_params()
        riot_id = self._get_riot_id_display() or params.get("manual_summoner_name", "")
        site = params.get("preferred_stats_site", "opgg")
        return build_stats_site_url(site, self.get_platform_for_websites(), riot_id)

    def build_preferred_hotkey_url(self) -> str:
        params = self.get_params()
        riot_id = self._get_riot_id_display() or params.get("manual_summoner_name", "")
        site = params.get("preferred_hotkey_site", "porofessor")
        return build_hotkey_site_url(site, self.get_platform_for_websites(), riot_id)

    def _has_valid_riot_id(self) -> bool:
        return is_valid_riot_id(self._get_riot_id_display() or self.get_params().get("manual_summoner_name", ""))

    def _refresh_stats_button(self) -> None:
        if self.stats_btn and self.stats_btn.winfo_exists():
            enabled = self._has_valid_riot_id()
            site = self.get_params().get("preferred_stats_site", "opgg")
            logo = self._load_site_logo(site, size=27)
            self.stats_btn.configure(
                state="normal" if enabled else "disabled",
            )
            if logo:
                self.stats_btn.configure(image=logo)
                self.stats_btn.image = logo

    def open_preferred_stats_site(self) -> None:
        if not self._has_valid_riot_id():
            self.show_toast("Invalid Riot ID.")
            return
        webbrowser.open(self.build_preferred_stats_url())

    def _get_riot_id_display(self) -> Optional[str]:
        params = self.get_params()
        if params.get("summoner_name_auto_detect", True):
            return params.get("auto_detected_riot_id") or self.get_auto_summoner_name()
        return params.get("manual_summoner_name")

    def _refresh_safe_controls(self) -> None:
        return

    def _handle_window_close(self) -> None:
        if self.tray_available and not self.closing_requested:
            self.hide_window()
            return
        self._quit_callback()

    def _cancel_disconnect_close(self) -> None:
        if self.disconnect_close_after_id is not None:
            try:
                self.root.after_cancel(self.disconnect_close_after_id)
            except Exception:
                pass
            self.disconnect_close_after_id = None

    def _schedule_disconnect_close(self) -> None:
        self._cancel_disconnect_close()

        def close_if_still_disconnected():
            self.disconnect_close_after_id = None
            if not self.running or self.closing_requested:
                return
            if self.is_ws_active():
                return
            if self.get_params().get("close_app_on_lol_exit", True):
                self._quit_callback()

        self.disconnect_close_after_id = self.root.after(self.DISCONNECT_CLOSE_DELAY_MS, close_if_still_disconnected)

    def play_accept_sound(self) -> None:
        self.audio_manager.play_accept_sound()

    def create_system_tray(self) -> None:
        self.tray_controller.setup(
            executor=self.executor,
            toggle_window=self.request_toggle_window_from_external_thread,
            open_settings=self.request_open_settings_from_external_thread,
            toggle_presets_automation=self.request_toggle_presets_automation_from_external_thread,
            toggle_auto_ban=self.request_toggle_auto_ban_from_external_thread,
            is_presets_automation_enabled=self.is_tray_presets_automation_enabled,
            is_auto_ban_enabled=self.is_tray_auto_ban_enabled,
            quit_callback=self.request_quit_from_external_thread,
            on_failure=lambda: self.root.after(0, self._refresh_safe_controls),
        )

    def setup_hotkeys(self) -> None:
        params = self.get_params()
        self.hotkey_manager.setup(
            self.toggle_window,
            self.open_preferred_hotkey_site,
            params.get("hotkey_toggle_window", "alt+c"),
            params.get("hotkey_open_site", "alt+p"),
        )

    def reload_hotkeys(self) -> None:
        if self._hotkeys_suspended:
            return
        self.hotkey_manager.shutdown()
        self.setup_hotkeys()
        self._refresh_safe_controls()

    def suspend_hotkeys(self) -> None:
        """Temporarily disable global shortcuts while the settings window captures a new shortcut."""
        if self._hotkeys_suspended:
            return
        self._hotkeys_suspended = True
        self._hotkeys_were_available = self.hotkey_manager.available
        self.hotkey_manager.shutdown()
        self._refresh_safe_controls()

    def resume_hotkeys(self) -> None:
        """Restore global shortcuts after shortcut capture has finished or been cancelled."""
        if not self._hotkeys_suspended:
            return
        should_restore = self._hotkeys_were_available and self.running and not self.closing_requested
        self._hotkeys_suspended = False
        self._hotkeys_were_available = False
        if should_restore:
            self.setup_hotkeys()
        self._refresh_safe_controls()

    def open_preferred_hotkey_site(self) -> None:
        riot_id = self._get_riot_id_display()
        if riot_id and is_valid_riot_id(riot_id):
            webbrowser.open(self.build_preferred_hotkey_url())

    def show_window(self) -> None:
        if self.root.state() == "withdrawn":
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)

    def hide_window(self) -> None:
        if self.root.state() != "withdrawn":
            self.root.after(0, self.root.withdraw)

    def toggle_window(self, icon=None) -> None:
        if self.root.state() == "withdrawn":
            self.show_window()
        else:
            self.hide_window()

    def request_toggle_window_from_external_thread(self) -> None:
        logging.info("[TRAY] Show/Hide requested from tray thread.")
        try:
            self.root.after(0, self.toggle_window)
        except Exception as e:
            logging.debug("Unable to schedule tray toggle on UI thread: %s", e)

    def request_quit_from_external_thread(self) -> None:
        logging.info("[TRAY] Quit requested from tray thread.")
        try:
            self.root.after(0, self._quit_callback)
        except Exception as e:
            logging.debug("Unable to schedule tray quit on UI thread: %s", e)

    def _sync_settings_window_if_open(self) -> None:
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win._sync_from_params()

    def is_tray_presets_automation_enabled(self) -> bool:
        return bool(self.get_params().get("presets_enabled", True))

    def is_tray_auto_ban_enabled(self) -> bool:
        return bool(self.get_params().get("auto_ban_enabled", True))

    def toggle_tray_presets_automation(self) -> None:
        next_value = not self.is_tray_presets_automation_enabled()
        self.update_param("presets_enabled", next_value)
        self.update_param("auto_pick_enabled", next_value)
        self.update_param("auto_summoners_enabled", next_value)
        self._sync_settings_window_if_open()
        state_label = "active" if next_value else "disabled"
        self.show_toast(f"Presets automation {state_label}.", duration=1200)

    def toggle_tray_auto_ban(self) -> None:
        next_value = not self.is_tray_auto_ban_enabled()
        self.update_param("auto_ban_enabled", next_value)
        self._sync_settings_window_if_open()
        state_label = "active" if next_value else "disabled"
        self.show_toast(f"Auto-ban {state_label}.", duration=1200)

    def request_open_settings_from_external_thread(self) -> None:
        logging.info("[TRAY] Settings requested from tray thread.")
        try:
            self.root.after(0, self.open_settings)
        except Exception as e:
            logging.debug("Unable to schedule tray settings on UI thread: %s", e)

    def request_toggle_presets_automation_from_external_thread(self) -> None:
        logging.info("[TRAY] Presets automation requested from tray thread.")
        try:
            self.root.after(0, self.toggle_tray_presets_automation)
        except Exception as e:
            logging.debug("Unable to schedule tray presets toggle on UI thread: %s", e)

    def request_toggle_auto_ban_from_external_thread(self) -> None:
        logging.info("[TRAY] Auto-ban requested from tray thread.")
        try:
            self.root.after(0, self.toggle_tray_auto_ban)
        except Exception as e:
            logging.debug("Unable to schedule tray auto-ban toggle on UI thread: %s", e)

    def open_settings(self) -> None:
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win.window.lift()
            self.settings_win.window.focus_force()
            return
        self.settings_win = SettingsWindow(self)

    def open_history_window(self) -> None:
        if self.history_window and self.history_window.winfo_exists():
            self.history_window.lift()
            self.refresh_history_window()
            return

        self.history_window = ttk.Toplevel(self.root)
        self.history_window.title("Action history")
        self.history_window.geometry("680x420")
        self.history_window.resizable(True, True)
        self.history_window.transient(self.root)
        self.history_window.protocol("WM_DELETE_WINDOW", self._close_history_window)

        try:
            icon_path = resource_path(APP_IMAGE_FILES["icon_webp"])
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((16, 16))
                photo = ImageTk.PhotoImage(img)
                self.history_window.iconphoto(False, photo)
                self.history_window._icon_ref = photo
        except Exception as e:
            logging.debug("History icon error: %s", e)

        container = ttk.Frame(self.history_window, padding=12)
        container.pack(fill="both", expand=True)

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Label(controls, text="Filter:", style="Status.TLabel").pack(side="left")
        history_filter_cb = ttk.Combobox(
            controls,
            values=["All", "Connection", "Champion Select", "Summs", "Error"],
            textvariable=self.history_filter_var,
            state="readonly",
            width=16,
        )
        history_filter_cb.pack(side="left", padx=(8, 0))
        history_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_history_window())
        ttk.Button(controls, text="Clear", bootstyle="danger-outline", command=self.clear_history_window).pack(
            side="right"
        )

        self.history_text = scrolledtext.ScrolledText(container, wrap="word", font=("Segoe UI", 10))
        self.history_text.pack(fill="both", expand=True)
        self._refresh_history_colors()
        self.history_text.configure(state="disabled")
        self.refresh_history_window()
        self._schedule_history_refresh()

    def _refresh_history_colors(self) -> None:
        if not self.history_text:
            return
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        self.history_text.configure(
            background=palette["window_bg"],
            foreground=palette["text"],
            insertbackground=palette["text"],
        )
        self.history_text.tag_configure("history_time", foreground=palette["history_time"], font=("Segoe UI", 9, "bold"))
        self.history_text.tag_configure("history_info", foreground=palette["history_info"], font=("Segoe UI", 9, "bold"))
        self.history_text.tag_configure("history_success", foreground=palette["history_success"], font=("Segoe UI", 9, "bold"))
        self.history_text.tag_configure("history_warning", foreground=palette["history_warning"], font=("Segoe UI", 9, "bold"))
        self.history_text.tag_configure("history_error", foreground=palette["history_error"], font=("Segoe UI", 9, "bold"))
        self.history_text.tag_configure("history_message", foreground=palette["text"], font=("Segoe UI", 10))
        self.history_text.tag_configure("history_detail", foreground=palette["history_detail"], font=("Segoe UI", 9))

    def _schedule_history_refresh(self) -> None:
        if self.history_after_id is not None:
            try:
                self.root.after_cancel(self.history_after_id)
            except Exception:
                pass
            self.history_after_id = None

        if not self.history_window or not self.history_window.winfo_exists():
            return

        def _tick():
            self.history_after_id = None
            if not self.history_window or not self.history_window.winfo_exists():
                return
            self.refresh_history_window()
            self._schedule_history_refresh()

        self.history_after_id = self.root.after(800, _tick)

    def _close_history_window(self) -> None:
        if self.history_after_id is not None:
            try:
                self.root.after_cancel(self.history_after_id)
            except Exception:
                pass
            self.history_after_id = None
        if self.history_window and self.history_window.winfo_exists():
            self.history_window.destroy()
        self.history_window = None
        self.history_text = None

    def refresh_history_window(self) -> None:
        if not self.history_window or not self.history_window.winfo_exists() or not self.history_text:
            return
        entries = get_history_entries(limit=150)
        selected_filter = self.history_filter_var.get()
        if selected_filter != "All":
            entries = [entry for entry in entries if format_history_entry(entry)["category"] == selected_filter]
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", "end")
        if not entries:
            self.history_text.insert("end", "No history events yet.", "history_detail")
        else:
            for entry in entries:
                formatted = format_history_entry(entry)
                level_tag = f"history_{formatted['level']}"
                self.history_text.insert("end", f"{formatted['time']}  ", "history_time")
                self.history_text.insert("end", f"{formatted['level_label']}  {formatted['category']}\n", level_tag)
                self.history_text.insert("end", f"{formatted['message']}\n", "history_message")
                for line in formatted["detail_lines"]:
                    self.history_text.insert("end", f"{line}\n", "history_detail")
                self.history_text.insert("end", "\n")
        self.history_text.configure(state="disabled")

    def clear_history_window(self) -> None:
        clear_history_entries()
        self.refresh_history_window()
        self.show_toast("History cleared.")

    def update_status(self, message: str, emoji: str = "") -> None:
        marker = f"[{emoji}] " if emoji else ""
        logging.info("[STATUS] %s%s", marker, message)
        self.root.after(0, lambda: self.status_label.config(text=message))

    def update_connection_indicator(self, connected: bool) -> None:
        def draw():
            if not self.connection_indicator or not self.connection_indicator.winfo_exists():
                return
            self.connection_indicator.delete("all")
            color = "#00ff00" if connected else "#ff0000"
            self.connection_indicator.create_oval(2, 2, 10, 10, fill=color, outline="")

            if connected:
                def pulse(step=0):
                    if not self.connection_indicator.winfo_exists():
                        return
                    radius = 4 + int(2 * abs((step % 20) - 10) / 10)
                    self.connection_indicator.delete("all")
                    self.connection_indicator.create_oval(6 - radius, 6 - radius, 6 + radius, 6 + radius, fill=color, outline="")
                    if self.running and self.is_ws_active():
                        self.connection_indicator.after(50, lambda: pulse(step + 1))
                    elif self.connection_indicator.winfo_exists():
                        self.connection_indicator.delete("all")
                        self.connection_indicator.create_oval(2, 2, 10, 10, fill="#ff0000", outline="")

                pulse()

        self.root.after(0, draw)

    def show_toast(self, message: str, duration: int = 2000) -> None:
        if self._toast_active:
            self._toast_queue.append((message, duration))
            return
        self._show_toast_now(message, duration)

    def _show_toast_now(self, message: str, duration: int) -> None:
        self._toast_active = True
        try:
            toast = ttk.Label(self.root, text=message, bootstyle="success", font=("Segoe UI", 10, "bold"))
            toast.place(relx=0.5, rely=0.98, anchor="s")

            def _done():
                toast.destroy()
                self._toast_active = False
                if self._toast_queue:
                    next_msg, next_dur = self._toast_queue.pop(0)
                    self._show_toast_now(next_msg, next_dur)

            self.root.after(duration, _done)
        except Exception as e:
            self._toast_active = False
            logging.debug("Toast display error: %s", e)

    def show_update_popup(self, update_info: Dict[str, str]) -> None:
        new_version = str(update_info.get("version") or "").strip()
        highlights = str(update_info.get("highlights") or "").strip()
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])

        popup = ttk.Toplevel(self.root)
        popup.title(f"{APP_NAME} Update")
        popup.geometry("650x520")
        popup.resizable(False, False)
        popup.transient(self.root)

        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        try:
            icon_path = resource_path(APP_IMAGE_FILES["icon_webp"])
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((32, 32))
                photo = ImageTk.PhotoImage(img)
                popup.iconphoto(False, photo)
                popup._icon_ref = photo
        except Exception as e:
            logging.debug("Update popup icon error: %s", e)

        outer = tk.Frame(popup, bg=palette["window_bg"], padx=20, pady=20)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=palette["window_bg"])
        header.pack(fill="x", pady=(0, 20))

        try:
            banner_img = ImageTk.PhotoImage(Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((42, 42)))
            icon_label = tk.Label(header, image=banner_img, bg=palette["window_bg"])
            icon_label.image = banner_img
            icon_label.pack(side="left", padx=(0, 12))
        except Exception as e:
            logging.debug("Update popup banner icon error: %s", e)

        title_block = tk.Frame(header, bg=palette["window_bg"])
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_block,
            text="Update available",
            font=("Segoe UI", 18, "bold"),
            bg=palette["window_bg"],
            fg=palette["text"],
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="A newer version of OTP LOL was detected on GitHub.",
            font=("Segoe UI", 11),
            bg=palette["window_bg"],
            fg=palette["muted"],
        ).pack(anchor="w", pady=(2, 0))

        summary_card = tk.Frame(
            outer,
            bg=palette["surface_bg"],
            bd=0,
            highlightthickness=0,
            padx=16,
            pady=12,
        )
        summary_card.pack(fill="x", pady=(0, 15))

        badges = tk.Frame(summary_card, bg=palette["surface_bg"])
        badges.pack(anchor="w")

        # Disabled ttk buttons give the compact rounded badge style used for version pills.
        ttk.Button(
            badges,
            text=f"Current version: {CURRENT_VERSION}",
            bootstyle="secondary-outline",
            state="disabled",
        ).pack(side="left")
        ttk.Button(
            badges,
            text=f"Latest version: {new_version}",
            bootstyle="success-outline",
            state="disabled",
        ).pack(side="left", padx=(10, 0))

        content_frame = tk.Frame(outer, bg=palette["window_bg"])
        content_frame.pack(fill="both", expand=True)

        ttk.Label(
            content_frame, 
            text="What's new", 
            font=("Segoe UI", 12, "bold"), 
            background=palette["window_bg"], 
            foreground=palette["text"]
        ).pack(anchor="w", pady=(0, 6))

        sep = tk.Frame(content_frame, bg=palette["muted"], height=1)
        sep.pack(fill="x", pady=(0, 10))

        highlights_box = scrolledtext.ScrolledText(
            content_frame,
            wrap="word",
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            height=10,
        )
        highlights_box.pack(fill="both", expand=True, pady=(0, 15))
        highlights_box.configure(
            background=palette["window_bg"],
            foreground=palette["text"],
            insertbackground=palette["text"],
            highlightbackground=palette["window_bg"],
            highlightcolor=palette["window_bg"],
        )
        self._render_update_markdown(highlights_box, highlights, palette)
        highlights_box.configure(state="disabled")

        btn_frame = tk.Frame(outer, bg=palette["window_bg"], bd=0, highlightthickness=0)
        btn_frame.pack(fill="x")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)

        left_actions = tk.Frame(btn_frame, bg=palette["window_bg"], bd=0, highlightthickness=0)
        left_actions.grid(row=0, column=0, sticky="w")
        center_actions = tk.Frame(btn_frame, bg=palette["window_bg"], bd=0, highlightthickness=0)
        center_actions.grid(row=0, column=1)
        right_actions = tk.Frame(btn_frame, bg=palette["window_bg"], bd=0, highlightthickness=0)
        right_actions.grid(row=0, column=2, sticky="e")

        def _make_text_action(
            parent: tk.Widget,
            text: str,
            command: Callable[[], None],
            *,
            foreground: Optional[str] = None,
            hover_foreground: Optional[str] = None,
        ) -> tk.Label:
            label = tk.Label(
                parent,
                text=text,
                bg=palette["window_bg"],
                fg=foreground or palette["muted"],
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
                bd=0,
                padx=0,
                pady=0,
            )

            def on_enter(_event: object) -> None:
                label.configure(fg=hover_foreground or palette["text"])

            def on_leave(_event: object) -> None:
                label.configure(fg=foreground or palette["muted"])

            label.bind("<Button-1>", lambda _event: command())
            label.bind("<Enter>", on_enter)
            label.bind("<Leave>", on_leave)
            return label

        skip_var = tk.BooleanVar(value=False)

        def _ignore_if_checked() -> None:
            if skip_var.get():
                self.update_param("ignored_update_version", new_version)
                self.save_params()

        def on_download() -> None:
            _ignore_if_checked()
            webbrowser.open(GITHUB_DOWNLOAD_ZIP_URL)

        def on_open_repo() -> None:
            _ignore_if_checked()
            webbrowser.open(GITHUB_REPO_URL)

        ttk.Checkbutton(
            left_actions,
            text="Do not remind me about this update",
            variable=skip_var,
            bootstyle="secondary-round-toggle",
        ).pack(side="left")
        _make_text_action(
            center_actions,
            "Later",
            popup.destroy,
            foreground=palette["muted"],
            hover_foreground=palette["text"],
        ).pack()
        
        # Pack from the right so the primary download action stays aligned to the far edge.
        ttk.Button(
            right_actions,
            text="Download",
            bootstyle="primary",
            command=on_download,
            width=16,
        ).pack(side="right", padx=(10, 0))
        ttk.Button(
            right_actions,
            text="Open in browser",
            bootstyle="info-outline",
            command=on_open_repo,
            width=18,
        ).pack(side="right")

        popup.attributes("-topmost", True)
        popup.grab_set()
        popup.focus_force()

    @staticmethod
    def _insert_markdown_inline(text_widget: scrolledtext.ScrolledText, text: str) -> None:
        parts = re.split(r"(`[^`]+`)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("`") and part.endswith("`") and len(part) >= 2:
                text_widget.insert("end", part[1:-1], ("update_code",))
            else:
                text_widget.insert("end", part)

    def _render_update_markdown(
        self,
        text_widget: scrolledtext.ScrolledText,
        markdown_text: str,
        palette: Dict[str, str],
    ) -> None:
        text_widget.delete("1.0", "end")
        text_widget.tag_configure(
            "update_body",
            font=("Segoe UI", 10),
            foreground=palette["text"],
            lmargin1=8,
            lmargin2=8,
            spacing3=3,
        )
        text_widget.tag_configure(
            "update_bullet",
            font=("Segoe UI", 10),
            foreground=palette["text"],
            lmargin1=12,
            lmargin2=28,
            spacing1=4,
            spacing3=4,
        )
        text_widget.tag_configure(
            "update_code",
            font=("Consolas", 10),
            foreground=palette["history_info"],
        )

        content = markdown_text.strip() or "Release notes are not available for this version yet."
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                text_widget.insert("end", "\n")
                continue
            if stripped.startswith("- "):
                text_widget.insert("end", "• ", ("update_bullet",))
                self._insert_markdown_inline(text_widget, stripped[2:])
                text_widget.insert("end", "\n", ("update_bullet",))
            else:
                self._insert_markdown_inline(text_widget, stripped)
                text_widget.insert("end", "\n", ("update_body",))

    def on_core_event(self, event_type: str, data: Any) -> None:
        """Marshal core events back to Tk because websocket callbacks run off the UI thread."""
        self.root.after(0, lambda: self._handle_core_event(event_type, data))

    def _handle_core_event(self, event_type: str, data: Any) -> None:
        """Update UI surfaces in response to normalized events from the core layer."""
        from ..core import WebSocketManager

        if event_type == WebSocketManager.EVENT_CONNECTED:
            self._cancel_disconnect_close()
            self.update_connection_indicator(True)
            if self.get_params().get("auto_hide_on_connect", True):
                if not (self.settings_win and self.settings_win.window.winfo_exists()):
                    self.root.after(3000, self.hide_window)
        elif event_type == WebSocketManager.EVENT_DISCONNECTED:
            disconnect_info = data if isinstance(data, dict) else {}
            is_transient_disconnect = bool(disconnect_info.get("transient"))
            self.update_connection_indicator(False)
            if is_transient_disconnect:
                self._cancel_disconnect_close()
            elif self.get_params().get("close_app_on_lol_exit", True):
                self._schedule_disconnect_close()
            else:
                self.root.after(100, self.show_window)
        elif event_type == WebSocketManager.EVENT_STATUS:
            message, emoji = data
            self.update_status(message, emoji)
        elif event_type == WebSocketManager.EVENT_TOAST:
            self.show_toast(data)
        elif event_type == WebSocketManager.EVENT_READY_CHECK_ACCEPTED:
            self.play_accept_sound()

        # Refresh secondary surfaces after every core event so the window, stats
        # button, and history stay consistent with the latest runtime state.
        self._queue_feature_preview_refresh()
        self._refresh_stats_button()
        if self.history_window and self.history_window.winfo_exists():
            self.refresh_history_window()

    def run(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        """Shut down UI-owned helpers and destroy the Tk root without leaving callbacks behind."""
        if self.closing_requested:
            return
        self.closing_requested = True
        self.running = False
        self._toast_queue.clear()
        self._toast_active = False
        if self._preview_refresh_after_id is not None:
            try:
                self.root.after_cancel(self._preview_refresh_after_id)
            except Exception:
                pass
            self._preview_refresh_after_id = None
        self._cancel_disconnect_close()
        self.hotkey_manager.shutdown()
        self.tray_controller.shutdown()
        self.audio_manager.shutdown()
        self._close_history_window()

        try:
            if self.root.state() != "withdrawn":
                self.update_param("window_x", self.root.winfo_x())
                self.update_param("window_y", self.root.winfo_y())
        except Exception:
            pass

        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            logging.debug("Executor shutdown error: %s", e)

        def destroy_root():
            if self.root.winfo_exists():
                self.root.destroy()

        try:
            self.root.after(0, destroy_root)
        except Exception:
            destroy_root()
