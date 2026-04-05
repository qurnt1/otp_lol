"""Main application window UI."""

import logging
import os
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import keyboard
import pystray
import pygame
import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageEnhance, ImageTk

from ..config import CURRENT_VERSION, GITHUB_REPO_URL, resource_path
from ..utils import build_opgg_url, build_porofessor_url
from .settings_window import SettingsWindow


class LoLAssistantUI:
    """Interface graphique principale de MAIN LOL."""

    MAX_WORKERS = 4
    DISCONNECT_CLOSE_DELAY_MS = 8000

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
        self.tray_available = False
        self.hotkeys_available = False
        self.hotkey_handles = []
        self.disconnect_close_after_id = None
        self.executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        self._init_sound()
        self.theme = params.get("theme", "darkly")
        self.root = ttk.Window(themename=self.theme)
        self.root.title("MAIN LOL")
        self.root.geometry("380x180")
        self.root.resizable(False, False)
        self.theme_var = tk.StringVar(value=self.theme)
        self.bg_label: Optional[tk.Label] = None
        self.banner_label: Optional[ttk.Label] = None
        self.connection_indicator: Optional[tk.Canvas] = None
        self.status_label: Optional[ttk.Label] = None
        self.safe_quit_btn: Optional[ttk.Button] = None
        self.create_ui()
        self.create_system_tray()
        self.setup_hotkeys()
        self._refresh_safe_controls()

    def _init_sound(self) -> None:
        try:
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except Exception as e:
            logging.debug(f"Impossible d'initialiser le son: {e}")
            self.sound_effect = None

    def set_ws_manager(self, ws_manager) -> None:
        self.ws_manager = ws_manager

    def get_params(self) -> Dict[str, Any]:
        return self._get_params_callback()

    def update_param(self, key: str, value: Any) -> None:
        self._update_param_callback(key, value)

    def save_and_notify(self) -> None:
        self._save_callback()
        self.show_toast("Parametres sauvegardes !")

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
        self._configure_styles()
        self._create_background()
        self._create_banner()
        self._create_connection_indicator()
        self._create_status_label()
        self._create_settings_gear()
        self._create_opgg_button()
        self._create_safe_quit_button()
        self.root.protocol("WM_DELETE_WINDOW", self._handle_window_close)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.configure(".", font=("Segoe UI Emoji", 10))
        style.configure("Status.TLabel", font=("Segoe UI Emoji", 11), background=self.root["bg"])

    def _create_background(self) -> None:
        self.bg_label = tk.Label(self.root, bg="#2b2b2b")
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_label.lower()

    def _create_banner(self) -> None:
        try:
            garen_icon = ImageTk.PhotoImage(Image.open(resource_path("./config/images/garen.webp")).resize((32, 32)))
            self.root.iconphoto(False, garen_icon)
            banner_img = ImageTk.PhotoImage(Image.open(resource_path("./config/images/garen.webp")).resize((48, 48)))
            self.banner_label = ttk.Label(self.root, image=banner_img)
            self.banner_label.image = banner_img
            self.banner_label.place(relx=0.5, rely=0.08, anchor="n")
        except Exception as e:
            logging.debug(f"Impossible de charger les images de banniere: {e}")

    def _create_connection_indicator(self) -> None:
        self.connection_indicator = tk.Canvas(
            self.root, width=12, height=12, bd=0, highlightthickness=0, bg="#2b2b2b"
        )
        self.connection_indicator.place(relx=0.05, rely=0.05, anchor="nw")
        self.update_connection_indicator(False)

    def _create_status_label(self) -> None:
        self.status_label = ttk.Label(
            self.root,
            text="En attente du lancement de League of Legends...",
            style="Status.TLabel",
            justify="center",
            wraplength=380,
        )
        self.status_label.place(relx=0.5, rely=0.38, anchor="center")

    def _create_settings_gear(self) -> None:
        gear_path = resource_path("./config/images/gear.png")
        if os.path.exists(gear_path):
            try:
                gear_img = ImageTk.PhotoImage(Image.open(gear_path).resize((25, 30)))
                cog = ttk.Label(self.root, image=gear_img, cursor="hand2")
                cog.image = gear_img
                cog.place(relx=0.95, rely=0.05, anchor="ne")
                cog.bind("<Button-1>", lambda e: self.open_settings())
                return
            except Exception as e:
                logging.debug(f"Impossible de charger l'icone engrenage: {e}")
        self._create_fallback_gear()

    def _create_fallback_gear(self) -> None:
        cog = ttk.Button(self.root, text="⚙", command=self.open_settings, bootstyle="link")
        cog.place(relx=0.95, rely=0.05, anchor="ne")

    def _create_opgg_button(self) -> None:
        opgg_btn = ttk.Button(
            self.root,
            text="Voir mes stats (OP.GG)",
            bootstyle="success-outline",
            padding=(20, 10),
            width=22,
            command=lambda: webbrowser.open(self.build_opgg_url()),
        )
        opgg_btn.place(relx=0.5, rely=0.75, anchor="center")

    def _create_safe_quit_button(self) -> None:
        self.safe_quit_btn = ttk.Button(
            self.root,
            text="Quitter",
            command=self._quit_callback,
            bootstyle="danger-outline",
            width=10,
        )
        self.safe_quit_btn.place(relx=0.98, rely=0.95, anchor="se")
        self.safe_quit_btn.place_forget()

    def build_opgg_url(self) -> str:
        riot_id = self._get_riot_id_display() or self.get_params().get("manual_summoner_name", "")
        return build_opgg_url(self.get_platform_for_websites(), riot_id)

    def build_porofessor_url(self) -> str:
        riot_id = self._get_riot_id_display() or self.get_params().get("manual_summoner_name", "")
        return build_porofessor_url(self.get_platform_for_websites(), riot_id)

    def _get_riot_id_display(self) -> Optional[str]:
        params = self.get_params()
        if params.get("summoner_name_auto_detect", True):
            return params.get("auto_detected_riot_id") or self.get_auto_summoner_name()
        return params.get("manual_summoner_name")

    def _refresh_safe_controls(self) -> None:
        safe_mode = not (self.tray_available and self.hotkeys_available)
        if self.safe_quit_btn and self.safe_quit_btn.winfo_exists():
            if safe_mode:
                self.safe_quit_btn.place(relx=0.98, rely=0.95, anchor="se")
            else:
                self.safe_quit_btn.place_forget()

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
        if not self.sound_effect:
            return
        try:
            self.sound_effect.play()
        except Exception as e:
            logging.debug(f"Impossible de jouer le son d'accept: {e}")

    def set_background_splash(self, champion_name: str) -> None:
        def task():
            try:
                img = self.dd.get_splash_art(champion_name)
                if not img:
                    return

                window_w, window_h = 380, 180
                base_width = window_w
                w_percent = base_width / float(img.size[0])
                h_size = int(float(img.size[1]) * w_percent)

                if h_size < window_h:
                    base_height = window_h
                    h_percent = base_height / float(img.size[1])
                    w_size = int(float(img.size[0]) * h_percent)
                    img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)
                else:
                    img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)

                left = (img.width - window_w) / 2
                top = (img.height - window_h) / 2
                right = (img.width + window_w) / 2
                bottom = (img.height + window_h) / 2
                img = img.crop((left, top, right, bottom))
                img = ImageEnhance.Brightness(img).enhance(0.4)
                tk_img = ImageTk.PhotoImage(img)

                def update_ui():
                    if self.root.winfo_exists() and self.bg_label:
                        self.bg_label.configure(image=tk_img)
                        self.bg_label.image = tk_img

                self.root.after(0, update_ui)
            except Exception as e:
                logging.warning(f"Erreur Splash Art pour {champion_name}: {e}")

        self.executor.submit(task)

    def create_system_tray(self) -> None:
        try:
            image = Image.open(resource_path("./config/images/garen.webp")).resize((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("Afficher/Masquer", self.toggle_window),
                pystray.MenuItem("Quitter", self._quit_callback),
            )
            self.icon = pystray.Icon("MAIN LOL", image, "MAIN LOL", menu)
            self.tray_available = True

            def run_tray():
                try:
                    self.icon.run()
                except Exception as e:
                    self.tray_available = False
                    logging.debug(f"Erreur system tray: {e}")
                    self.root.after(0, self._refresh_safe_controls)

            self.executor.submit(run_tray)
        except Exception as e:
            self.tray_available = False
            logging.warning(f"Impossible de creer le system tray: {e}")

    def setup_hotkeys(self) -> None:
        try:
            self.hotkey_handles = [
                keyboard.add_hotkey("alt+p", self.open_porofessor),
                keyboard.add_hotkey("alt+c", self.toggle_window),
            ]
            self.hotkeys_available = True
        except Exception as e:
            self.hotkeys_available = False
            self.hotkey_handles = []
            logging.debug(f"Impossible de configurer les hotkeys: {e}")

    def open_porofessor(self) -> None:
        riot_id = self._get_riot_id_display()
        if riot_id:
            webbrowser.open(self.build_porofessor_url())

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

    def open_settings(self) -> None:
        if self.settings_win and self.settings_win.window.winfo_exists():
            self.settings_win.window.lift()
            self.settings_win.window.focus_force()
            return
        self.settings_win = SettingsWindow(self)

    def update_status(self, message: str, emoji: str = "") -> None:
        now = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{now}] {emoji} {message}" if emoji else f"[{now}] {message}"
        print(log_msg, flush=True)
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
                    self.connection_indicator.create_oval(
                        6 - radius,
                        6 - radius,
                        6 + radius,
                        6 + radius,
                        fill=color,
                        outline="",
                    )
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
            logging.debug(f"Erreur affichage toast: {e}")

    def show_update_popup(self, new_version: str) -> None:
        popup = ttk.Toplevel(self.root)
        popup.title("Mise a jour MAIN LOL")
        popup.geometry("400x250")
        popup.resizable(False, False)
        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        try:
            icon_path = resource_path("./config/images/garen.webp")
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((32, 32))
                photo = ImageTk.PhotoImage(img)
                popup.iconphoto(False, photo)
                popup._icon_ref = photo
        except Exception as e:
            logging.debug(f"Erreur icone popup update: {e}")

        title_lbl = ttk.Label(
            popup,
            text="Nouvelle version detectee !",
            font=("Segoe UI Emoji", 14, "bold"),
            bootstyle="inverse-primary",
        )
        title_lbl.pack(fill="x", pady=(0, 15), ipady=10)

        info_frame = ttk.Frame(popup, padding=10)
        info_frame.pack(fill="both", expand=True)
        info_text = (
            "Une mise a jour est disponible sur GitHub.\n\n"
            f"Version actuelle : {CURRENT_VERSION}\n"
            f"Nouvelle version : {new_version}"
        )
        ttk.Label(info_frame, text=info_text, justify="center", font=("Segoe UI", 11)).pack(pady=5)

        btn_frame = ttk.Frame(popup, padding=(0, 0, 0, 20))
        btn_frame.pack(fill="x")

        def on_download():
            webbrowser.open(GITHUB_REPO_URL)
            popup.destroy()

        ttk.Button(btn_frame, text="Telecharger", bootstyle="success", command=on_download, width=15).pack(
            side="left",
            padx=(40, 10),
            expand=True,
        )
        ttk.Button(btn_frame, text="Plus tard", bootstyle="secondary", command=popup.destroy, width=15).pack(
            side="right",
            padx=(10, 40),
            expand=True,
        )
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
        elif event_type == WebSocketManager.EVENT_CHAMPION_PICKED:
            self.set_background_splash(data)
        elif event_type == WebSocketManager.EVENT_TOAST:
            self.show_toast(data)
        elif event_type == WebSocketManager.EVENT_READY_CHECK_ACCEPTED:
            self.play_accept_sound()

    def run(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        if self.closing_requested:
            return
        self.closing_requested = True
        self.running = False
        self._cancel_disconnect_close()

        for handle in self.hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception as e:
                logging.debug(f"Erreur suppression hotkey: {e}")
        self.hotkey_handles = []

        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            logging.debug(f"Erreur arret executor: {e}")

        try:
            if hasattr(self, "icon"):
                self.icon.stop()
        except Exception as e:
            logging.debug(f"Erreur arret tray icon: {e}")

        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception as e:
            logging.debug(f"Erreur arret mixer pygame: {e}")

        def destroy_root():
            if self.root.winfo_exists():
                self.root.destroy()

        try:
            self.root.after(0, destroy_root)
        except Exception:
            destroy_root()
