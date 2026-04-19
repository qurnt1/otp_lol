"""Main application window UI."""

import logging
import os
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from tkinter import scrolledtext
from typing import Any, Callable, Dict, List, Optional

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from ..config import (
    APP_NAME,
    APP_IMAGE_FILES,
    CURRENT_VERSION,
    GITHUB_REPO_URL,
    PICK_SLOT_ORDER,
    ROLE_PROFILE_LABELS,
    ROLE_PROFILE_ORDER,
    STATS_SITE_LABELS,
    THEME_PALETTE,
    resource_path,
)
from ..services.history import clear_history_entries, format_history_entry, get_history_entries
from ..utils import build_hotkey_site_url, build_stats_site_url, is_valid_riot_id
from .hotkeys import HotkeyManager
from .media import AudioManager
from .settings_window import SettingsWindow
from .tray import TrayController


class LoLAssistantUI:
    """Main OTP LOL graphical interface."""

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
        self.theme = params.get("theme", "darkly") if params.get("theme", "darkly") in THEME_PALETTE else "darkly"
        self.root = ttk.Window(themename=self.theme)
        self.root.title(APP_NAME)
        self.root.geometry("420x250")
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
        self.settings_gear_label: Optional[ttk.Label] = None
        self.history_filter_var = tk.StringVar(value="All")
        self.create_ui()
        self.apply_theme(self.theme)
        self.create_system_tray()
        self.setup_hotkeys()
        self._refresh_safe_controls()

    @property
    def tray_available(self) -> bool:
        return self.tray_controller.available

    @property
    def hotkeys_available(self) -> bool:
        return self.hotkey_manager.available

    def set_ws_manager(self, ws_manager) -> None:
        self.ws_manager = ws_manager
        self._queue_feature_preview_refresh(force=True)
        self._refresh_stats_button()

    def get_params(self) -> Dict[str, Any]:
        return self._get_params_callback()

    def update_param(self, key: str, value: Any) -> None:
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
            logging.debug(f"Unable to apply theme {theme_name}: {e}")

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

    def get_effective_profile_config(self, role: Optional[str] = None) -> Dict[str, Any]:
        if self.ws_manager:
            return self.ws_manager.get_effective_profile_config(role=role)

        params = self.get_params()
        resolved_role = (role or "GLOBAL").upper()
        aliases = {
            "MID": "MIDDLE",
            "ADC": "BOTTOM",
            "BOT": "BOTTOM",
            "SUP": "UTILITY",
            "SUPPORT": "UTILITY",
            "JGL": "JUNGLE",
        }
        resolved_role = aliases.get(resolved_role, resolved_role)
        if resolved_role not in ROLE_PROFILE_ORDER:
            resolved_role = "GLOBAL"
        role_profiles = params.get("role_profiles", {})
        role_data = role_profiles.get(resolved_role, {}) if isinstance(role_profiles, dict) else {}
        if not isinstance(role_data, dict):
            role_data = {}
        global_pick_slots = params.get("pick_slots", {}) if isinstance(params.get("pick_slots", {}), dict) else {}
        role_pick_slots = role_data.get("pick_slots", {}) if isinstance(role_data.get("pick_slots", {}), dict) else {}

        def _resolve_slot(slot_key: str, pick_key: str) -> Dict[str, Any]:
            global_slot = global_pick_slots.get(slot_key, {}) if isinstance(global_pick_slots.get(slot_key, {}), dict) else {}
            role_slot = role_pick_slots.get(slot_key, {}) if isinstance(role_pick_slots.get(slot_key, {}), dict) else {}
            def _to_int(value: Any) -> int:
                try:
                    return int(value or 0)
                except (TypeError, ValueError):
                    return 0

            def _pick_skin_mode() -> str:
                role_mode = str(role_slot.get("skin_mode") or "").strip().lower()
                global_mode = str(global_slot.get("skin_mode") or "").strip().lower()
                if role_mode in {"fixed", "random"}:
                    return role_mode
                if global_mode in {"fixed", "random"}:
                    return global_mode
                return "none"

            def _pick_skin_text(field: str) -> str:
                role_value = str(role_slot.get(field) or "").strip()
                if role_value:
                    return role_value
                return str(global_slot.get(field) or "").strip()

            def _pick_skin_int(field: str) -> int:
                role_value = _to_int(role_slot.get(field))
                if role_value > 0:
                    return role_value
                return _to_int(global_slot.get(field))

            def _pick_skin_pool() -> List[Dict[str, Any]]:
                role_pool = role_slot.get("random_skin_pool")
                if isinstance(role_pool, list) and role_pool:
                    return role_pool
                global_pool = global_slot.get("random_skin_pool")
                if isinstance(global_pool, list) and global_pool:
                    return global_pool
                return []

            role_skin_mode = str(role_slot.get("skin_mode") or "").strip().lower()
            role_has_skin_override = (
                role_skin_mode in {"fixed", "random"}
                or _to_int(role_slot.get("skin_id")) > 0
                or _to_int(role_slot.get("random_skin_id")) > 0
                or bool(str(role_slot.get("skin_name") or "").strip())
                or bool(str(role_slot.get("random_skin_name") or "").strip())
                or bool(role_slot.get("random_skin_pool"))
            )
            skin_source_role = (
                resolved_role if role_has_skin_override else "GLOBAL"
            )
            return {
                "champion": role_data.get(pick_key) or params.get(pick_key, ""),
                "spell_1": role_slot.get("spell_1") or global_slot.get("spell_1", ""),
                "spell_2": role_slot.get("spell_2") or global_slot.get("spell_2", ""),
                "skin_mode": _pick_skin_mode(),
                "skin_id": _pick_skin_int("skin_id"),
                "skin_name": _pick_skin_text("skin_name"),
                "skin_num": _pick_skin_int("skin_num"),
                "random_skin_id": _pick_skin_int("random_skin_id"),
                "random_skin_name": _pick_skin_text("random_skin_name"),
                "random_skin_num": _pick_skin_int("random_skin_num"),
                "random_skin_pool": _pick_skin_pool(),
                "skin_source_role": skin_source_role,
            }

        pick_slots = {
            slot_key: _resolve_slot(slot_key, f"selected_pick_{index}")
            for index, slot_key in enumerate(PICK_SLOT_ORDER, start=1)
        }
        first_slot = pick_slots["pick_1"]
        return {
            "detected_role": resolved_role,
            "resolved_role": resolved_role,
            "resolved_role_label": ROLE_PROFILE_LABELS.get(resolved_role, "Global"),
            "fallback_policy": "The detected role profile has priority, then the global config fills empty fields.",
            "presets_enabled": (
                bool(role_data.get("presets_enabled"))
                if "presets_enabled" in role_data
                else bool(params.get("presets_enabled", True))
            ),
            "pick_slots": pick_slots,
            "selected_pick_1": pick_slots["pick_1"]["champion"],
            "selected_pick_2": pick_slots["pick_2"]["champion"],
            "selected_pick_3": pick_slots["pick_3"]["champion"],
            "selected_ban": role_data.get("selected_ban") or params.get("selected_ban", ""),
            "spell_1": first_slot.get("spell_1", ""),
            "spell_2": first_slot.get("spell_2", ""),
            "sources": {
                "presets_enabled": resolved_role if "presets_enabled" in role_data else "GLOBAL",
                "selected_pick_1": resolved_role if role_data.get("selected_pick_1") else "GLOBAL",
                "selected_pick_2": resolved_role if role_data.get("selected_pick_2") else "GLOBAL",
                "selected_pick_3": resolved_role if role_data.get("selected_pick_3") else "GLOBAL",
                "selected_ban": resolved_role if role_data.get("selected_ban") else "GLOBAL",
                "spell_1": resolved_role if role_pick_slots.get("pick_1", {}).get("spell_1") else "GLOBAL",
                "spell_2": resolved_role if role_pick_slots.get("pick_1", {}).get("spell_2") else "GLOBAL",
            },
        }

    def create_ui(self) -> None:
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

    def _create_banner(self) -> None:
        try:
            garen_icon = ImageTk.PhotoImage(Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((32, 32)))
            self.root.iconphoto(False, garen_icon)
            banner_img = ImageTk.PhotoImage(Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((48, 48)))
            self.banner_label = ttk.Label(self.root, image=banner_img)
            self.banner_label.image = banner_img
            self.banner_label.place(relx=0.5, rely=0.08, anchor="n")
        except Exception as e:
            logging.debug(f"Unable to load banner images: {e}")

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

    def _create_feature_preview(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        self.feature_preview_frame = tk.Frame(self.root, bg=palette["window_bg"], bd=0, highlightthickness=0)
        self.feature_preview_frame.place(relx=0.5, rely=self.PREVIEW_TOP_RELY, anchor="n")

        for column, (key, label_text, icon_count, status_style) in enumerate(self.FEATURE_PREVIEW_DEFINITIONS):
            group = tk.Frame(self.feature_preview_frame, bg=palette["window_bg"], bd=0, highlightthickness=0, padx=4, pady=1)
            group.grid(row=0, column=column, padx=4)
            self.feature_group_frames[key] = group

            header = tk.Frame(group, bg=palette["window_bg"], bd=0, highlightthickness=0)
            header.pack(anchor="w")
            title = tk.Label(header, text=label_text, bg=palette["window_bg"], fg=palette["text"], font=("Segoe UI", 9, "bold"))
            title.pack(side="left")
            status = tk.Label(
                header,
                text="OFF",
                bg=palette["window_bg"],
                fg=palette["muted"],
                font=("Segoe UI", 9),
                padx=4,
            )
            status.pack(side="left", padx=(6, 0))
            self.feature_status_labels[key] = status

            icons_row = tk.Frame(group, bg=palette["window_bg"], bd=0, highlightthickness=0)
            icons_row.pack(anchor="w", pady=(4, 0))
            labels: list[tk.Label] = []
            for index in range(icon_count):
                slot = tk.Label(
                    icons_row,
                    text="",
                    anchor="center",
                    compound="center",
                    image=self.preview_placeholder,
                    bg=palette["window_bg"],
                    fg=palette["muted"],
                    font=("Segoe UI", 9),
                    bd=0,
                    highlightthickness=0,
                )
                slot.pack(side="left", padx=2, pady=0)
                slot.image = self.preview_placeholder
                labels.append(slot)
            self.feature_icon_labels[key] = labels
            if key == "skins":
                self._bind_click_tree(header, lambda event, feature_key=key: self._on_feature_group_click(feature_key, event))
                for index, slot in enumerate(labels):
                    slot_key = PICK_SLOT_ORDER[index]
                    self._bind_click_tree(slot, lambda event, current_slot=slot_key: self._on_skin_preview_click(current_slot, event))
            else:
                self._bind_feature_group(group, key)

        self._queue_feature_preview_refresh(force=True)

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
                logging.debug(f"Unable to load gear icon: {e}")
        self.settings_gear_label.configure(image="", text="⚙")
        self.settings_gear_label.image = None

    def _create_opgg_button(self) -> None:
        self.stats_btn = ttk.Button(
            self.root,
            text=self._get_stats_button_text(),
            bootstyle="success-outline",
            padding=(16, 10),
            width=22,
            command=self.open_preferred_stats_site,
        )
        self.stats_btn.place(relx=0.5, rely=self.STATS_BUTTON_TOP_RELY, anchor="n")
        self._refresh_stats_button()

    def _apply_preview_palette(self) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        if self.feature_preview_frame and self.feature_preview_frame.winfo_exists():
            self.feature_preview_frame.configure(bg=palette["window_bg"])
        for group in self.feature_group_frames.values():
            for current in self._iter_widget_tree(group):
                try:
                    if isinstance(current, (tk.Frame, tk.Label)):
                        current.configure(bg=palette["window_bg"])
                        if isinstance(current, tk.Label):
                            current.configure(fg=palette["text"])
                except Exception:
                    continue
        for icon_labels in self.feature_icon_labels.values():
            for label in icon_labels:
                try:
                    label.configure(bg=palette["window_bg"], fg=palette["muted"])
                except Exception:
                    continue

    def _get_preview_icon_cache_key(self, name: str, is_champion: bool, size: Optional[int] = None) -> tuple[str, str, int]:
        kind = "champ" if is_champion else "spell"
        return kind, name, size or self.PREVIEW_ICON_SIZE

    def _set_preview_placeholder(self, widget: ttk.Label, *, fg: Optional[str] = None) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        widget.configure(
            text="",
            image=self.preview_placeholder,
            compound="center",
            bg=palette["window_bg"],
            fg=fg or palette["muted"],
        )
        widget.image = self.preview_placeholder

    def _get_random_skin_placeholder_asset(self) -> str:
        return APP_IMAGE_FILES["question_mark_black_mode"] if self.theme == "flatly" else APP_IMAGE_FILES["question_mark_white_mode"]

    def _load_local_preview_asset(self, asset_rel_path: str, cache_key: tuple[Any, ...]) -> Optional[ImageTk.PhotoImage]:
        if cache_key in self.preview_icon_cache:
            return self.preview_icon_cache[cache_key]
        asset_path = resource_path(asset_rel_path)
        if not os.path.exists(asset_path):
            return None
        try:
            photo = ImageTk.PhotoImage(Image.open(asset_path).convert("RGBA").resize((self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), Image.LANCZOS))
            self.preview_icon_cache[cache_key] = photo
            return photo
        except Exception as e:
            logging.debug("Unable to load local preview asset %s: %s", asset_rel_path, e)
            return None

    def _set_skin_feature_icon(self, widget: ttk.Label, skin_data: Dict[str, Any], enabled: bool, accent: str) -> None:
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        if not enabled or not isinstance(skin_data, dict):
            self._set_preview_placeholder(widget)
            return

        mode = str(skin_data.get("mode") or "none").strip().lower()
        if mode == "random":
            cache_key = ("asset", self._get_random_skin_placeholder_asset(), self.PREVIEW_ICON_SIZE)
            photo = self._load_local_preview_asset(self._get_random_skin_placeholder_asset(), cache_key)
            if photo:
                widget.configure(text="", image=photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
                widget.image = photo
            else:
                self._set_preview_placeholder(widget)
            return

        if mode != "fixed":
            self._set_preview_placeholder(widget)
            return

        champion_name = str(skin_data.get("champion_name") or "").strip()
        if not champion_name:
            self._set_preview_placeholder(widget)
            return

        preview_url = self.dd.get_skin_preview_url(
            champion_name,
            skin_id=skin_data.get("skin_id"),
            skin_num=skin_data.get("skin_num"),
            skin_name=skin_data.get("skin_name"),
        )
        if not preview_url:
            self._set_preview_placeholder(widget)
            return

        cache_suffix = skin_data.get("skin_num") or skin_data.get("skin_id") or skin_data.get("skin_name") or "0"
        cache_key = ("skin", champion_name, str(cache_suffix), self.PREVIEW_ICON_SIZE)
        if cache_key in self.preview_icon_cache:
            photo = self.preview_icon_cache[cache_key]
            widget.configure(text="", image=photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
            widget.image = photo
            return

        self._set_preview_placeholder(widget, fg=palette["text"])

        def task():
            try:
                image = self.dd.get_remote_image(preview_url, cache_key=f"main_preview_skin_{champion_name}_{cache_suffix}")
                if not image:
                    return
                resized_image = image.resize((self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), Image.LANCZOS)

                def update_ui():
                    if widget.winfo_exists():
                        photo = ImageTk.PhotoImage(resized_image)
                        self.preview_icon_cache[cache_key] = photo
                        widget.configure(text="", image=photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
                        widget.image = photo

                widget.after(0, update_ui)
            except Exception as e:
                logging.debug("Main preview loading error for skin %s: %s", skin_data.get("skin_name") or cache_suffix, e)

        self.executor.submit(task)

    def _set_feature_icon(self, widget: ttk.Label, name: str, is_champion: bool, enabled: bool, accent: str) -> None:
        display_name = name or "..."
        palette = THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])
        if not enabled:
            self._set_preview_placeholder(widget)
            return
        if not name:
            self._set_preview_placeholder(widget)
            return

        cache_key = self._get_preview_icon_cache_key(name, is_champion, self.PREVIEW_ICON_SIZE)
        if cache_key in self.preview_icon_cache:
            cached_photo = self.preview_icon_cache[cache_key]
            widget.configure(text="", image=cached_photo, compound="center", bg=palette["window_bg"], fg=palette["text"])
            widget.image = cached_photo
            return

        widget.configure(text="", image=self.preview_placeholder, compound="center", bg=palette["window_bg"], fg=palette["text"])
        widget.image = self.preview_placeholder

        def task():
            try:
                image = self.dd.get_champion_icon(name) if is_champion else self.dd.get_summoner_icon(name)
                if image:
                    resized_image = image.resize((self.PREVIEW_ICON_SIZE, self.PREVIEW_ICON_SIZE), Image.LANCZOS)

                    def update_ui():
                        if widget.winfo_exists():
                            photo = ImageTk.PhotoImage(resized_image)
                            self.preview_icon_cache[cache_key] = photo
                            widget.configure(image=photo, text="", compound="center", bg=palette["window_bg"], fg=palette["text"])
                            widget.image = photo

                    widget.after(0, update_ui)
                else:
                    def update_ui_no_img():
                        if widget.winfo_exists():
                            self._set_preview_placeholder(widget)

                    widget.after(0, update_ui_no_img)
            except Exception as e:
                logging.debug(f"Main preview loading error for {display_name}: {e}")

        self.executor.submit(task)

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

    def _on_feature_group_click(self, feature_key: str, event=None):
        self._toggle_main_preview_feature(feature_key)
        return "break"

    def _on_skin_preview_click(self, slot_key: str, event=None):
        self._toggle_main_preview_skin_slot(slot_key)
        return "break"

    @staticmethod
    def _has_fixed_skin(slot_data: Dict[str, Any]) -> bool:
        return int(slot_data.get("skin_id") or 0) > 0 or bool(str(slot_data.get("skin_name") or "").strip())

    @staticmethod
    def _has_random_skin(slot_data: Dict[str, Any]) -> bool:
        return (
            int(slot_data.get("random_skin_id") or 0) > 0
            or bool(str(slot_data.get("random_skin_name") or "").strip())
            or bool(slot_data.get("random_skin_pool"))
        )

    def _get_main_preview_skin_target_role(self, effective: Optional[Dict[str, Any]] = None) -> str:
        effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
        slot_data = effective.get("pick_slots", {}).get("pick_1", {})
        source_role = str(slot_data.get("skin_source_role") or "GLOBAL").upper()
        return source_role if source_role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"

    def _get_pick_slot_config_for_role(self, role: str, slot_key: str) -> Dict[str, Any]:
        params = self.get_params()
        normalized_role = self._normalize_profile_role(role)
        if normalized_role == "GLOBAL":
            pick_slots = params.get("pick_slots", {})
        else:
            role_profiles = params.get("role_profiles", {})
            role_data = role_profiles.get(normalized_role, {}) if isinstance(role_profiles, dict) else {}
            pick_slots = role_data.get("pick_slots", {}) if isinstance(role_data, dict) else {}
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        return dict(slot_data) if isinstance(slot_data, dict) else {}

    def _get_main_skin_overrides(self) -> Dict[str, str]:
        try:
            params = self.get_params()
        except Exception:
            params = {}
        raw_overrides = params.get("main_skin_mode_overrides", {})
        legacy_mode = str(params.get("main_skin_mode_override", "inherit") or "inherit").strip().lower()
        if legacy_mode not in {"inherit", "none", "fixed", "random"}:
            legacy_mode = "inherit"
        overrides = {slot: "inherit" for slot in PICK_SLOT_ORDER}
        if legacy_mode != "inherit":
            for slot in overrides:
                overrides[slot] = legacy_mode
        if isinstance(raw_overrides, dict):
            for slot in PICK_SLOT_ORDER:
                mode = str(raw_overrides.get(slot, overrides[slot]) or overrides[slot]).strip().lower()
                overrides[slot] = mode if mode in {"inherit", "none", "fixed", "random"} else "inherit"
        return overrides

    def _get_main_preview_skin_cycle_modes(self, slot_data: Optional[Dict[str, Any]] = None, *, effective: Optional[Dict[str, Any]] = None) -> List[str]:
        if slot_data is None:
            effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
            pick_slots = effective.get("pick_slots", {})
            modes = ["none"]
            if any(self._has_fixed_skin(pick_slots.get(slot_key, {})) for slot_key in PICK_SLOT_ORDER):
                modes.append("fixed")
            if any(self._has_random_skin(pick_slots.get(slot_key, {})) for slot_key in PICK_SLOT_ORDER):
                modes.append("random")
            return modes
        modes = ["none"]
        if self._has_fixed_skin(slot_data):
            modes.append("fixed")
        if self._has_random_skin(slot_data):
            modes.append("random")
        return modes

    def _get_effective_main_preview_skin_mode_for_slot(
        self,
        slot_key: str,
        *,
        effective: Optional[Dict[str, Any]] = None,
    ) -> str:
        effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
        overrides = self._get_main_skin_overrides()
        override_mode = overrides.get(slot_key, "inherit")
        if override_mode in {"none", "fixed", "random"}:
            return override_mode
        pick_slots = effective.get("pick_slots", {})
        slot_mode = str(pick_slots.get(slot_key, {}).get("skin_mode") or "none").strip().lower()
        return slot_mode if slot_mode in {"fixed", "random"} else "none"

    def _get_effective_main_preview_skin_mode(self, effective: Optional[Dict[str, Any]] = None) -> str:
        effective = effective or self.get_effective_profile_config(role=self._get_main_preview_role())
        slot_modes = [
            self._get_effective_main_preview_skin_mode_for_slot(slot_key, effective=effective)
            for slot_key in PICK_SLOT_ORDER
        ]
        if not any(mode in {"fixed", "random"} for mode in slot_modes):
            return "none"
        unique_modes = {mode for mode in slot_modes}
        if len(unique_modes) == 1:
            return unique_modes.pop()
        return "mixed"

    def _cycle_main_preview_skin_mode(self) -> Optional[str]:
        effective = self.get_effective_profile_config(role=self._get_main_preview_role())
        cycle_modes = self._get_main_preview_skin_cycle_modes(effective=effective)
        if len(cycle_modes) == 1:
            return None
        current_mode = self._get_effective_main_preview_skin_mode(effective=effective)
        if current_mode not in cycle_modes:
            current_mode = "none"
        next_mode = cycle_modes[(cycle_modes.index(current_mode) + 1) % len(cycle_modes)]
        overrides = self._get_main_skin_overrides()
        for slot_key in PICK_SLOT_ORDER:
            overrides[slot_key] = next_mode
        self.update_param("main_skin_mode_overrides", overrides)
        return next_mode

    def _cycle_main_preview_skin_mode_for_slot(self, slot_key: str) -> Optional[str]:
        effective = self.get_effective_profile_config(role=self._get_main_preview_role())
        pick_slots = effective.get("pick_slots", {})
        slot_data = pick_slots.get(slot_key, {}) if isinstance(pick_slots, dict) else {}
        cycle_modes = self._get_main_preview_skin_cycle_modes(slot_data)
        if len(cycle_modes) == 1:
            return None
        current_mode = self._get_effective_main_preview_skin_mode_for_slot(slot_key, effective=effective)
        if current_mode not in cycle_modes:
            current_mode = "none"
        next_mode = cycle_modes[(cycle_modes.index(current_mode) + 1) % len(cycle_modes)]
        overrides = self._get_main_skin_overrides()
        overrides[slot_key] = next_mode
        self.update_param("main_skin_mode_overrides", overrides)
        return next_mode

    def _build_slot_skin_preview_value(self, slot_data: Dict[str, Any], *, mode: str) -> Dict[str, Any]:
        champion_name = str(slot_data.get("champion") or "").strip()
        if mode == "fixed" and self._has_fixed_skin(slot_data):
            return {
                "mode": "fixed",
                "champion_name": champion_name,
                "skin_id": int(slot_data.get("skin_id") or 0),
                "skin_name": str(slot_data.get("skin_name") or ""),
                "skin_num": int(slot_data.get("skin_num") or 0),
            }
        if mode == "random" and self._has_random_skin(slot_data):
            return {"mode": "random"}
        return {"mode": "none"}

    def _build_feature_preview_payload(self, params: Dict[str, Any], effective: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        presets_enabled = bool(effective.get("presets_enabled", True))
        pick_slots = effective.get("pick_slots", {})
        skin_values = []
        slot_modes = []
        for slot_key in PICK_SLOT_ORDER:
            slot_mode = self._get_effective_main_preview_skin_mode_for_slot(slot_key, effective=effective)
            slot_modes.append(slot_mode)
            skin_values.append(self._build_slot_skin_preview_value(pick_slots.get(slot_key, {}), mode=slot_mode))
        if not any(mode in {"fixed", "random"} for mode in slot_modes):
            skin_mode = "none"
        elif len(set(slot_modes)) == 1:
            skin_mode = slot_modes[0]
        else:
            skin_mode = "mixed"
        return {
            "presets": {
                "enabled": (
                    params.get("auto_pick_enabled", True)
                    and params.get("auto_summoners_enabled", True)
                    and presets_enabled
                ),
                "style": "info",
                "is_champion": True,
                "values": [
                    effective.get("selected_pick_1") or "",
                    effective.get("selected_pick_2") or "",
                    effective.get("selected_pick_3") or "",
                ],
            },
            "skins": {
                "enabled": any(mode in {"fixed", "random"} for mode in slot_modes),
                "style": "info",
                "is_skin": True,
                "mode": skin_mode,
                "values": skin_values,
            },
            "ban": {
                "enabled": params.get("auto_ban_enabled", True),
                "style": "danger",
                "is_champion": True,
                "values": [effective.get("selected_ban") or ""],
            },
        }

    def _toggle_main_preview_feature(self, feature_key: str) -> None:
        if feature_key == "presets":
            next_value = not self.is_main_preview_presets_enabled()
            self.set_main_preview_presets_enabled(next_value)
            self._sync_settings_window_if_open()
            state_label = "active" if next_value else "disabled"
            self.show_toast(f"{self.FEATURE_LABEL_MAP.get(feature_key, feature_key)} {state_label}.", duration=1200)
            return

        if feature_key == "skins":
            next_mode = self._cycle_main_preview_skin_mode()
            if next_mode is None:
                self.show_toast("No skin configured in presets.", duration=1400)
                return
            self._sync_settings_window_if_open()
            label_map = {
                "none": "Skin off.",
                "fixed": "Fixed skin enabled.",
                "random": "Random skins enabled.",
            }
            self.show_toast(label_map.get(next_mode, "Skin updated."), duration=1200)
            return

        param_key = self.FEATURE_PARAM_MAP.get(feature_key)
        if not param_key:
            return

        current_value = bool(self.get_params().get(param_key, True))
        next_value = not current_value
        self.update_param(param_key, next_value)
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win._sync_from_params()
        state_label = "active" if next_value else "disabled"
        self.show_toast(f"{self.FEATURE_LABEL_MAP.get(feature_key, feature_key)} {state_label}.", duration=1200)

    def _toggle_main_preview_skin_slot(self, slot_key: str) -> None:
        next_mode = self._cycle_main_preview_skin_mode_for_slot(slot_key)
        if next_mode is None:
            return
        self._sync_settings_window_if_open()
        slot_label = slot_key.replace("_", " ").title()
        label_map = {
            "none": f"{slot_label} skin off.",
            "fixed": f"{slot_label} fixed skin enabled.",
            "random": f"{slot_label} random skin enabled.",
        }
        self.show_toast(label_map.get(next_mode, f"{slot_label} skin updated."), duration=1100)

    def _queue_feature_preview_refresh(self, force: bool = False) -> None:
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return
        if self._preview_refresh_after_id is not None:
            return

        def _run():
            self._preview_refresh_after_id = None
            self._refresh_feature_preview(force=force)

        self._preview_refresh_after_id = self.root.after(80, _run)

    def _build_preview_signature(self, preview_data: Dict[str, Dict[str, Any]]) -> tuple:
        signature = []
        for key in ("presets", "skins", "ban"):
            data = preview_data.get(key, {})
            values = []
            for value in data.get("values", []):
                if isinstance(value, dict):
                    values.append(tuple(sorted(value.items())))
                else:
                    values.append(value)
            signature.append(
                (
                    key,
                    bool(data.get("enabled")),
                    data.get("mode"),
                    tuple(values),
                )
            )
        return tuple(signature)

    def _get_feature_status_colors(self, accent: str, enabled: bool) -> tuple[str, str]:
        if not enabled:
            return ("", THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])["muted"])
        palette = {
            "info": "#3da5ff",
            "danger": "#ff6b5a",
        }
        return ("", palette.get(accent, "#3da5ff"))

    def _refresh_feature_preview(self, force: bool = False) -> None:
        if not self.feature_preview_frame or not self.feature_preview_frame.winfo_exists():
            return

        detected_role = "GLOBAL"
        if self.ws_manager and self.ws_manager.state.assigned_position:
            detected_role = self.ws_manager.state.assigned_position
        effective = self.get_effective_profile_config(role=detected_role)
        params = self.get_params()
        preview_data = self._build_feature_preview_payload(params, effective)
        signature = self._build_preview_signature(preview_data)
        if not force and signature == self._last_preview_signature:
            return
        self._last_preview_signature = signature
        self._apply_preview_palette()

        for key, data in preview_data.items():
            status = self.feature_status_labels.get(key)
            if status:
                _, fg = self._get_feature_status_colors(data["style"], data["enabled"])
                status_text = "ON" if data["enabled"] else "OFF"
                if key == "skins":
                    skin_mode = str(data.get("mode") or "none").upper()
                    status_text = "OFF" if skin_mode == "NONE" else skin_mode
                status.configure(
                    text=status_text,
                    bg=THEME_PALETTE.get(self.theme, THEME_PALETTE["darkly"])["window_bg"],
                    fg=fg,
                )
            for widget, value in zip(self.feature_icon_labels.get(key, []), data["values"]):
                if data.get("is_skin"):
                    self._set_skin_feature_icon(widget, value, data["enabled"], data["style"])
                else:
                    self._set_feature_icon(widget, value, data["is_champion"], data["enabled"], data["style"])

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

    def get_preferred_stats_site_label(self) -> str:
        site = self.get_params().get("preferred_stats_site", "opgg")
        return STATS_SITE_LABELS.get(site, STATS_SITE_LABELS["opgg"])

    def _get_stats_button_text(self) -> str:
        return f"View my stats ({self.get_preferred_stats_site_label()})"

    def _has_valid_riot_id(self) -> bool:
        return is_valid_riot_id(self._get_riot_id_display() or self.get_params().get("manual_summoner_name", ""))

    def _refresh_stats_button(self) -> None:
        if self.stats_btn and self.stats_btn.winfo_exists():
            enabled = self._has_valid_riot_id()
            self.stats_btn.configure(
                text=self._get_stats_button_text(),
                state="normal" if enabled else "disabled",
                image="",
            )

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
            logging.debug(f"Unable to schedule tray toggle on UI thread: {e}")

    def request_quit_from_external_thread(self) -> None:
        logging.info("[TRAY] Quit requested from tray thread.")
        try:
            self.root.after(0, self._quit_callback)
        except Exception as e:
            logging.debug(f"Unable to schedule tray quit on UI thread: {e}")

    @staticmethod
    def _normalize_profile_role(role: str) -> str:
        normalized_role = (role or "GLOBAL").upper()
        aliases = {
            "MID": "MIDDLE",
            "ADC": "BOTTOM",
            "BOT": "BOTTOM",
            "SUP": "UTILITY",
            "SUPPORT": "UTILITY",
            "JGL": "JUNGLE",
        }
        normalized_role = aliases.get(normalized_role, normalized_role)
        return normalized_role if normalized_role in {"GLOBAL", *ROLE_PROFILE_ORDER} else "GLOBAL"

    def _get_selected_profile_role(self) -> str:
        return self._normalize_profile_role(self.get_params().get("selected_profile_role", "GLOBAL"))

    def _sync_settings_window_if_open(self) -> None:
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win._sync_from_params()

    def _get_main_preview_role(self) -> str:
        if self.ws_manager and self.ws_manager.state.assigned_position:
            return self._normalize_profile_role(self.ws_manager.state.assigned_position)
        return "GLOBAL"

    def is_main_preview_presets_enabled(self) -> bool:
        params = self.get_params()
        effective = self.get_effective_profile_config(role=self._get_main_preview_role())
        return (
            bool(params.get("auto_pick_enabled", True))
            and bool(params.get("auto_summoners_enabled", True))
            and bool(effective.get("presets_enabled", True))
        )

    def set_main_preview_presets_enabled(self, enabled: bool) -> None:
        params = self.get_params()
        target_role = self._get_main_preview_role()
        self.update_param("auto_pick_enabled", enabled)
        self.update_param("auto_summoners_enabled", enabled)

        if target_role == "GLOBAL":
            self.update_param("presets_enabled", enabled)
            return

        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
        role_data = new_profiles.get(target_role, {})
        role_data["presets_enabled"] = enabled
        new_profiles[target_role] = role_data
        self.update_param("role_profiles", new_profiles)

    def is_tray_presets_automation_enabled(self) -> bool:
        params = self.get_params()
        selected_role = self._get_selected_profile_role()
        if selected_role == "GLOBAL":
            return bool(params.get("presets_enabled", True))

        role_profiles = params.get("role_profiles", {})
        role_data = role_profiles.get(selected_role, {}) if isinstance(role_profiles, dict) else {}
        if not isinstance(role_data, dict):
            role_data = {}
        return bool(role_data.get("presets_enabled", params.get("presets_enabled", True)))

    def is_tray_auto_ban_enabled(self) -> bool:
        return bool(self.get_params().get("auto_ban_enabled", True))

    def toggle_tray_presets_automation(self) -> None:
        params = self.get_params()
        selected_role = self._get_selected_profile_role()
        next_value = not self.is_tray_presets_automation_enabled()

        if selected_role == "GLOBAL":
            self.update_param("presets_enabled", next_value)
        else:
            role_profiles = params.get("role_profiles", {})
            if not isinstance(role_profiles, dict):
                role_profiles = {}
            new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
            role_data = new_profiles.get(selected_role, {})
            role_data["presets_enabled"] = next_value
            new_profiles[selected_role] = role_data
            self.update_param("role_profiles", new_profiles)

        self._sync_settings_window_if_open()
        state_label = "active" if next_value else "disabled"
        role_label = ROLE_PROFILE_LABELS.get(selected_role, "Global")
        self.show_toast(f"Presets automation {state_label} for {role_label}.", duration=1200)

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
            logging.debug(f"Unable to schedule tray settings on UI thread: {e}")

    def request_toggle_presets_automation_from_external_thread(self) -> None:
        logging.info("[TRAY] Presets automation requested from tray thread.")
        try:
            self.root.after(0, self.toggle_tray_presets_automation)
        except Exception as e:
            logging.debug(f"Unable to schedule tray presets toggle on UI thread: {e}")

    def request_toggle_auto_ban_from_external_thread(self) -> None:
        logging.info("[TRAY] Auto-ban requested from tray thread.")
        try:
            self.root.after(0, self.toggle_tray_auto_ban)
        except Exception as e:
            logging.debug(f"Unable to schedule tray auto-ban toggle on UI thread: {e}")

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
            logging.debug(f"History icon error: {e}")

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
        try:
            toast = ttk.Label(self.root, text=message, bootstyle="success", font=("Segoe UI", 10, "bold"))
            toast.place(relx=0.5, rely=0.98, anchor="s")
            self.root.after(duration, toast.destroy)
        except Exception as e:
            logging.debug(f"Toast display error: {e}")

    def show_update_popup(self, new_version: str) -> None:
        popup = ttk.Toplevel(self.root)
        popup.title(f"{APP_NAME} Update")
        popup.geometry("400x250")
        popup.resizable(False, False)
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
            logging.debug(f"Update popup icon error: {e}")

        title_lbl = ttk.Label(popup, text="New version detected!", font=("Segoe UI Emoji", 14, "bold"), bootstyle="inverse-primary")
        title_lbl.pack(fill="x", pady=(0, 15), ipady=10)

        info_frame = ttk.Frame(popup, padding=10)
        info_frame.pack(fill="both", expand=True)
        info_text = (
            "An update is available on GitHub.\n\n"
            f"Current version: {CURRENT_VERSION}\n"
            f"New version: {new_version}"
        )
        ttk.Label(info_frame, text=info_text, justify="center", font=("Segoe UI", 11)).pack(pady=5)

        btn_frame = ttk.Frame(popup, padding=(0, 0, 0, 20))
        btn_frame.pack(fill="x")

        def on_download():
            webbrowser.open(GITHUB_REPO_URL)
            popup.destroy()

        ttk.Button(btn_frame, text="Download", bootstyle="success", command=on_download, width=15).pack(side="left", padx=(40, 10), expand=True)
        ttk.Button(btn_frame, text="Later", bootstyle="secondary", command=popup.destroy, width=15).pack(side="right", padx=(10, 40), expand=True)
        popup.attributes("-topmost", True)
        popup.focus_force()

    def on_core_event(self, event_type: str, data: Any) -> None:
        self.root.after(0, lambda: self._handle_core_event(event_type, data))

    def _handle_core_event(self, event_type: str, data: Any) -> None:
        from ..core import WebSocketManager

        if event_type == WebSocketManager.EVENT_CONNECTED:
            self._cancel_disconnect_close()
            self.update_connection_indicator(True)
            if self.get_params().get("auto_hide_on_connect", True):
                self.root.after(3000, self.hide_window)
        elif event_type == WebSocketManager.EVENT_DISCONNECTED:
            self.update_connection_indicator(False)
            if self.get_params().get("close_app_on_lol_exit", True):
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

        self._queue_feature_preview_refresh()
        self._refresh_stats_button()
        if self.history_window and self.history_window.winfo_exists():
            self.refresh_history_window()

    def run(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        if self.closing_requested:
            return
        self.closing_requested = True
        self.running = False
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
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            logging.debug(f"Executor shutdown error: {e}")

        def destroy_root():
            if self.root.winfo_exists():
                self.root.destroy()

        try:
            self.root.after(0, destroy_root)
        except Exception:
            destroy_root()
