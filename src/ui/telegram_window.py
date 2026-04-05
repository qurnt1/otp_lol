"""Dedicated Telegram settings window."""

import logging
from typing import Any, Dict, TYPE_CHECKING

import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.scrolled import ScrolledFrame

from ..config import APP_IMAGE_FILES, resource_path

if TYPE_CHECKING:
    from .main_window import LoLAssistantUI


class TelegramSettingsWindow:
    """Dedicated window used to configure and diagnose Telegram integration."""

    def __init__(self, parent: "LoLAssistantUI"):
        self.parent = parent
        self.window = ttk.Toplevel(parent.root)
        self.window.title("Configuration Telegram - MAIN LOL")
        self.window.geometry("620x640")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self._setup_window_icon()
        self._init_variables()
        self._create_widgets()
        self.window.after(500, self._poll_diagnostics)

    def _setup_window_icon(self) -> None:
        try:
            img = Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((16, 16))
            photo = ImageTk.PhotoImage(img)
            self.window.iconphoto(False, photo)
            self.window._icon_img = photo
        except Exception as e:
            logging.debug(f"Impossible de charger l'icone de la fenetre Telegram: {e}")
            self.window._icon_img = None

    def _init_variables(self) -> None:
        params = self.parent.get_params()
        self.telegram_enabled_var = tk.BooleanVar(value=params.get("telegram_enabled", False))
        self.telegram_remote_control_var = tk.BooleanVar(value=params.get("telegram_remote_control_enabled", True))
        self.telegram_token_var = tk.StringVar(value=params.get("telegram_bot_token", ""))
        self.telegram_chat_id_var = tk.StringVar(value=params.get("telegram_allowed_chat_id", ""))
        self.telegram_notify_connection_var = tk.BooleanVar(value=params.get("telegram_notify_connection", True))
        self.telegram_notify_ready_check_var = tk.BooleanVar(value=params.get("telegram_notify_ready_check", True))
        self.telegram_notify_champ_select_var = tk.BooleanVar(value=params.get("telegram_notify_champ_select", True))
        self.telegram_notify_actions_var = tk.BooleanVar(value=params.get("telegram_notify_actions", True))
        self.telegram_notify_post_game_var = tk.BooleanVar(value=params.get("telegram_notify_post_game", True))
        self.telegram_notify_errors_var = tk.BooleanVar(value=params.get("telegram_notify_errors", True))

    def _create_widgets(self) -> None:
        self.scroll_frame = ScrolledFrame(self.window, autohide=True, height=640)
        self.scroll_frame.pack(fill="both", expand=True)

        container = ttk.Frame(self.scroll_frame, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)

        ttk.Label(
            container,
            text="Configuration Telegram",
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        tutorial_text = (
            "Tuto rapide:\n"
            "1. Sur Telegram, ouvre @BotFather puis cree un bot avec /newbot.\n"
            "2. Copie le token recu.\n"
            "3. Active Telegram ici, colle le token, puis clique sur 'Appliquer Telegram'.\n"
            "4. Ouvre ton bot et envoie /start.\n"
            "5. Si aucun Chat ID n'est encore configure, le bot te repondra avec ton Chat ID.\n"
            "6. Colle ce Chat ID ici puis utilise 'Tester Telegram'."
        )
        ttk.Label(
            container,
            text=tutorial_text,
            justify="left",
            wraplength=560,
            bootstyle="secondary",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Checkbutton(
            container,
            text="Activer Telegram",
            variable=self.telegram_enabled_var,
            bootstyle="success-round-toggle",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Checkbutton(
            container,
            text="Autoriser le controle distant Telegram",
            variable=self.telegram_remote_control_var,
            bootstyle="info-round-toggle",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Label(container, text="Bot token :").grid(row=4, column=0, sticky="e", padx=(0, 8), pady=(10, 4))
        ttk.Entry(container, textvariable=self.telegram_token_var, show="*").grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=(10, 4)
        )

        ttk.Label(container, text="Chat ID :").grid(row=5, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Entry(container, textvariable=self.telegram_chat_id_var).grid(
            row=5, column=1, columnspan=2, sticky="ew", pady=4
        )

        actions_frame = ttk.Frame(container)
        actions_frame.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 12))
        ttk.Button(
            actions_frame,
            text="Appliquer Telegram",
            bootstyle="primary-outline",
            command=self._apply_telegram_settings_now,
            padding=(10, 8),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions_frame,
            text="Tester Telegram",
            bootstyle="secondary-outline",
            command=self._test_telegram_connection,
            padding=(10, 8),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions_frame,
            text="Envoyer panneau",
            bootstyle="secondary-outline",
            command=self._send_telegram_panel,
            padding=(10, 8),
        ).pack(side="left")

        notify_frame = ttk.LabelFrame(container, text="Notifications", padding=10)
        notify_frame.grid(row=7, column=0, columnspan=3, sticky="ew")
        ttk.Checkbutton(
            notify_frame,
            text="Connexions",
            variable=self.telegram_notify_connection_var,
            bootstyle="round-toggle",
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            notify_frame,
            text="Game acceptee",
            variable=self.telegram_notify_ready_check_var,
            bootstyle="round-toggle",
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            notify_frame,
            text="Phases LoL",
            variable=self.telegram_notify_champ_select_var,
            bootstyle="round-toggle",
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            notify_frame,
            text="Actions auto",
            variable=self.telegram_notify_actions_var,
            bootstyle="round-toggle",
        ).pack(side="left")

        notify_frame_2 = ttk.Frame(container)
        notify_frame_2.grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 8))
        ttk.Checkbutton(
            notify_frame_2,
            text="Post-game",
            variable=self.telegram_notify_post_game_var,
            bootstyle="round-toggle",
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            notify_frame_2,
            text="Erreurs",
            variable=self.telegram_notify_errors_var,
            bootstyle="round-toggle",
        ).pack(side="left")

        self.telegram_status_label = ttk.Label(container, text="Telegram: statut indisponible", justify="left")
        self.telegram_status_label.grid(row=9, column=0, columnspan=3, sticky="w", pady=(4, 10))

        ttk.Separator(container).grid(row=10, column=0, columnspan=3, sticky="ew", pady=(4, 10))

        ttk.Label(
            container,
            text=(
                "Retry / robustesse LCU:\n"
                "- Les requetes GET critiques sont retentees automatiquement une fois si une erreur transitoire apparait.\n"
                "- Les POST/PATCH ne sont pas retentes automatiquement pour eviter les doubles actions.\n"
                "- Les compteurs ci-dessous aident a voir retries, erreurs endpoint et reconnexions."
            ),
            justify="left",
            wraplength=560,
            bootstyle="secondary",
        ).grid(row=11, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.lcu_diagnostics_label = ttk.Label(container, text="LCU: diagnostic indisponible", justify="left")
        self.lcu_diagnostics_label.grid(row=12, column=0, columnspan=3, sticky="w")

        self._refresh_runtime_diagnostics()

    def _collect_telegram_settings(self) -> Dict[str, Any]:
        return {
            "telegram_enabled": self.telegram_enabled_var.get(),
            "telegram_remote_control_enabled": self.telegram_remote_control_var.get(),
            "telegram_bot_token": self.telegram_token_var.get().strip(),
            "telegram_allowed_chat_id": self.telegram_chat_id_var.get().strip(),
            "telegram_notify_connection": self.telegram_notify_connection_var.get(),
            "telegram_notify_ready_check": self.telegram_notify_ready_check_var.get(),
            "telegram_notify_champ_select": self.telegram_notify_champ_select_var.get(),
            "telegram_notify_actions": self.telegram_notify_actions_var.get(),
            "telegram_notify_post_game": self.telegram_notify_post_game_var.get(),
            "telegram_notify_errors": self.telegram_notify_errors_var.get(),
        }

    def _apply_telegram_settings_to_parent(self) -> None:
        for key, value in self._collect_telegram_settings().items():
            self.parent.update_param(key, value)

    def _apply_telegram_settings_now(self) -> None:
        self._apply_telegram_settings_to_parent()
        self.parent.save_params()
        self.parent.reconfigure_telegram_service()
        self._refresh_runtime_diagnostics()
        self.parent.show_toast("Configuration Telegram appliquee.")

    def _run_telegram_action_async(self, action) -> None:
        def task():
            ok, message = action()

            def update_ui():
                self._refresh_runtime_diagnostics()
                self.parent.show_toast(message, duration=2000 if ok else 3000)

            self.window.after(0, update_ui)

        self._apply_telegram_settings_to_parent()
        self.parent.save_params()
        self.parent.reconfigure_telegram_service()
        self.parent.executor.submit(task)

    def _test_telegram_connection(self) -> None:
        self._run_telegram_action_async(self.parent.test_telegram_connection)

    def _send_telegram_panel(self) -> None:
        self._run_telegram_action_async(self.parent.send_telegram_status_panel)

    def _refresh_runtime_diagnostics(self) -> None:
        telegram = self.parent.get_telegram_diagnostics()
        telegram_lines = [
            f"Telegram: {telegram.get('status', 'Indisponible')}",
            f"Messages envoyes: {telegram.get('messages_sent', 0)}",
        ]
        if telegram.get("last_command"):
            telegram_lines.append(
                f"Derniere commande: {telegram.get('last_command')} a {telegram.get('last_command_at', '--:--:--')}"
            )
        if telegram.get("last_error"):
            telegram_lines.append(
                f"Derniere erreur: {telegram.get('last_error')} ({telegram.get('last_error_at', '--:--:--')})"
            )
        self.telegram_status_label.configure(text="\n".join(telegram_lines))

        lcu = self.parent.get_lcu_diagnostics()
        lines = [
            f"LCU connecte: {'Oui' if lcu.get('connected') else 'Non'}",
            f"Retries GET: {lcu.get('retry_count', 0)}",
            f"Erreurs endpoint: {lcu.get('endpoint_error_count', 0)}",
            f"Reconnexions: {lcu.get('reconnect_count', 0)}",
        ]
        if lcu.get("last_error"):
            lines.append(f"Derniere erreur: {lcu.get('last_error')} ({lcu.get('last_error_at', '--:--:--')})")
        self.lcu_diagnostics_label.configure(text="\n".join(lines))

    def _poll_diagnostics(self) -> None:
        if not self.window.winfo_exists():
            return
        self._refresh_runtime_diagnostics()
        self.window.after(1500, self._poll_diagnostics)

    def _sync_from_params(self) -> None:
        params = self.parent.get_params()
        self.telegram_enabled_var.set(params.get("telegram_enabled", False))
        self.telegram_remote_control_var.set(params.get("telegram_remote_control_enabled", True))
        self.telegram_token_var.set(params.get("telegram_bot_token", ""))
        self.telegram_chat_id_var.set(params.get("telegram_allowed_chat_id", ""))
        self.telegram_notify_connection_var.set(params.get("telegram_notify_connection", True))
        self.telegram_notify_ready_check_var.set(params.get("telegram_notify_ready_check", True))
        self.telegram_notify_champ_select_var.set(params.get("telegram_notify_champ_select", True))
        self.telegram_notify_actions_var.set(params.get("telegram_notify_actions", True))
        self.telegram_notify_post_game_var.set(params.get("telegram_notify_post_game", True))
        self.telegram_notify_errors_var.set(params.get("telegram_notify_errors", True))
        self._refresh_runtime_diagnostics()

    def on_close(self) -> None:
        self._apply_telegram_settings_to_parent()
        self.parent.save_params()
        self.parent.reconfigure_telegram_service()
        self.window.destroy()
