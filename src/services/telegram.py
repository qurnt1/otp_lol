"""Telegram notifications and remote-control helpers for MAIN LOL."""

from __future__ import annotations

import logging
from datetime import datetime
from queue import Empty, Queue
from threading import Event, Thread
from time import sleep
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from ..config import PHASE_DISPLAY_MAP, ROLE_PROFILE_LABELS, ROLE_PROFILE_ORDER, SUMMONER_SPELL_LIST
from .history import format_history_entry, get_history_entries
from .urls import build_hotkey_site_url, build_stats_site_url, is_valid_riot_id


class TelegramService:
    """Small Telegram bot client based on the Bot HTTP API.

    The service has two responsibilities:
    - send outbound notifications for important runtime events
    - poll inbound bot commands to expose a light remote-control surface
    """

    POLL_TIMEOUT_SECONDS = 4
    IDLE_SLEEP_SECONDS = 1.0

    FEATURE_ALIASES = {
        "accept": "auto_accept_enabled",
        "autoaccept": "auto_accept_enabled",
        "auto-accept": "auto_accept_enabled",
        "pick": "auto_pick_enabled",
        "autopick": "auto_pick_enabled",
        "auto-pick": "auto_pick_enabled",
        "ban": "auto_ban_enabled",
        "autoban": "auto_ban_enabled",
        "auto-ban": "auto_ban_enabled",
        "spells": "auto_summoners_enabled",
        "autosorts": "auto_summoners_enabled",
        "autosummoners": "auto_summoners_enabled",
        "auto-spells": "auto_summoners_enabled",
        "playagain": "auto_play_again_enabled",
        "auto-play-again": "auto_play_again_enabled",
    }

    ROLE_ALIASES = {
        "global": "GLOBAL",
        "top": "TOP",
        "jungle": "JUNGLE",
        "jgl": "JUNGLE",
        "mid": "MIDDLE",
        "middle": "MIDDLE",
        "adc": "BOTTOM",
        "bot": "BOTTOM",
        "bottom": "BOTTOM",
        "sup": "UTILITY",
        "support": "UTILITY",
        "utility": "UTILITY",
    }

    def __init__(
        self,
        *,
        dd,
        get_params: Callable[[], Dict[str, Any]],
        update_param: Callable[[str, Any], None],
        save_params: Callable[[], None],
        get_snapshot: Callable[[], Dict[str, Any]],
        commit_remote_changes: Callable[[Optional[str]], None],
    ):
        self.dd = dd
        self.get_params = get_params
        self.update_param = update_param
        self.save_params = save_params
        self.get_snapshot = get_snapshot
        self.commit_remote_changes = commit_remote_changes

        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._session = requests.Session()
        self._outbox: Queue[Tuple[str, Optional[dict]]] = Queue()
        self._last_update_id = 0
        self._runtime_token = ""
        self._runtime_chat_id = ""
        self._last_error = ""
        self._last_error_at = ""
        self._last_command = ""
        self._last_command_at = ""
        self._messages_sent = 0

    def _now_text(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _mark_error(self, message: str) -> None:
        self._last_error = message
        self._last_error_at = self._now_text()
        logging.warning(f"Telegram: {message}")

    def _get_runtime_config(self) -> tuple[bool, str, str]:
        params = self.get_params()
        enabled = bool(params.get("telegram_enabled", False))
        token = str(params.get("telegram_bot_token", "")).strip()
        chat_id = str(params.get("telegram_allowed_chat_id", "")).strip()
        return enabled, token, chat_id

    def _can_run(self) -> bool:
        enabled, token, _ = self._get_runtime_config()
        return enabled and bool(token)

    def _api_url(self, token: str, method: str) -> str:
        return f"https://api.telegram.org/bot{token}/{method}"

    def start(self) -> None:
        if not self._can_run():
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        _, token, chat_id = self._get_runtime_config()
        self._runtime_token = token
        self._runtime_chat_id = chat_id
        self._thread = Thread(target=self._poll_loop, daemon=True, name="mainlol-telegram")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def reconfigure(self) -> None:
        enabled, token, chat_id = self._get_runtime_config()
        needs_thread = enabled and bool(token)
        token_changed = token != self._runtime_token
        if not needs_thread:
            self.stop()
            self._runtime_token = token
            self._runtime_chat_id = chat_id
            return
        self._runtime_chat_id = chat_id
        if token_changed:
            self.stop()
            self._runtime_token = token
            self._last_update_id = 0
        self.start()

    def get_diagnostics(self) -> Dict[str, Any]:
        enabled, token, chat_id = self._get_runtime_config()
        running = bool(self._thread and self._thread.is_alive())
        if not enabled:
            status = "Desactive"
        elif not token:
            status = "Actif mais token manquant"
        elif not chat_id:
            status = "Polling actif, en attente du Chat ID"
        elif running:
            status = "Connecte"
        else:
            status = "Pret a demarrer"
        return {
            "enabled": enabled,
            "running": running,
            "has_token": bool(token),
            "has_chat_id": bool(chat_id),
            "status": status,
            "last_error": self._last_error,
            "last_error_at": self._last_error_at,
            "last_command": self._last_command,
            "last_command_at": self._last_command_at,
            "messages_sent": self._messages_sent,
        }

    def test_connection(self) -> tuple[bool, str]:
        enabled, token, chat_id = self._get_runtime_config()
        if not enabled:
            return False, "Active Telegram dans les parametres d'abord."
        if not token:
            return False, "Renseigne le token du bot Telegram."
        if not chat_id:
            return False, "Renseigne le Chat ID, puis envoie /start a ton bot."
        text = (
            "Test MAIN LOL Telegram OK.\n"
            "Tu peux maintenant recevoir les notifications et piloter l'app a distance."
        )
        try:
            self._send_text(chat_id, text, inline_keyboard=self._build_status_keyboard())
            return True, "Message de test envoye sur Telegram."
        except Exception as e:
            self._mark_error(f"Echec du test Telegram: {e}")
            return False, f"Echec du test Telegram: {e}"

    def send_status_panel(self) -> tuple[bool, str]:
        chat_id = str(self.get_params().get("telegram_allowed_chat_id", "")).strip()
        if not chat_id:
            return False, "Chat ID Telegram manquant."
        try:
            self._send_status_message(chat_id)
            return True, "Panneau Telegram envoye."
        except Exception as e:
            self._mark_error(f"Impossible d'envoyer le panneau Telegram: {e}")
            return False, f"Impossible d'envoyer le panneau Telegram: {e}"

    def handle_core_event(self, event_type: str, data: Any = None) -> None:
        message = self._build_event_message(event_type, data)
        if not message:
            return
        self._outbox.put(message)

    def _build_event_message(self, event_type: str, data: Any) -> Optional[Tuple[str, Optional[dict]]]:
        params = self.get_params()
        if not params.get("telegram_enabled", False):
            return None
        if not str(params.get("telegram_bot_token", "")).strip():
            return None
        chat_id = str(params.get("telegram_allowed_chat_id", "")).strip()
        if not chat_id:
            return None

        if event_type == "connected" and params.get("telegram_notify_connection", True):
            snapshot = self.get_snapshot()
            text = (
                "MAIN LOL: client LoL detecte.\n"
                f"Compte: {snapshot.get('riot_id') or 'Inconnu'}\n"
                f"Region: {snapshot.get('region') or 'euw'}"
            )
            return text, self._build_status_keyboard()
        if event_type == "disconnected" and params.get("telegram_notify_connection", True):
            return "MAIN LOL: client LoL deconnecte, reconnexion en cours.", None
        if event_type == "summoner_update" and params.get("telegram_notify_connection", True) and data:
            return f"Compte detecte: {data}", self._build_status_keyboard()
        if event_type == "ready_check_accepted" and params.get("telegram_notify_ready_check", True):
            return "Partie acceptee automatiquement.", self._build_status_keyboard()
        if event_type == "phase_change" and params.get("telegram_notify_champ_select", True):
            phase = str(data or "")
            if phase in {"ChampSelect", "InProgress"}:
                friendly = PHASE_DISPLAY_MAP.get(phase, phase)
                return f"Phase LoL: {friendly}", self._build_status_keyboard()
        if event_type == "champion_picked" and params.get("telegram_notify_actions", True):
            return f"Champion lock automatiquement: {data}", self._build_status_keyboard()
        if event_type == "champion_banned" and params.get("telegram_notify_actions", True):
            return f"Ban automatique confirme: {data}", self._build_status_keyboard()
        if event_type == "spells_set" and params.get("telegram_notify_actions", True):
            spell_1, spell_2 = data or ("", "")
            return f"Sorts appliques: {spell_1} + {spell_2}", self._build_status_keyboard()
        if event_type == "play_again" and params.get("telegram_notify_post_game", True):
            return "Retour automatique au salon reussi.", self._build_status_keyboard()
        if event_type == "status" and params.get("telegram_notify_errors", True):
            message = str(data[0] if isinstance(data, tuple) and data else data or "")
            if "Erreur" in message or "echec" in message.lower():
                return f"Alerte MAIN LOL: {message}", None
        return None

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._drain_outbox()
                self._poll_updates_once()
            except Exception as e:
                self._mark_error(f"Polling Telegram en erreur: {e}")
                sleep(self.IDLE_SLEEP_SECONDS)

    def _drain_outbox(self) -> None:
        while True:
            try:
                text, keyboard = self._outbox.get_nowait()
            except Empty:
                return
            chat_id = str(self.get_params().get("telegram_allowed_chat_id", "")).strip()
            if not chat_id:
                continue
            try:
                self._send_text(chat_id, text, inline_keyboard=keyboard)
            except Exception as e:
                self._mark_error(f"Envoi Telegram impossible: {e}")

    def _poll_updates_once(self) -> None:
        enabled, token, _ = self._get_runtime_config()
        if not enabled or not token:
            sleep(self.IDLE_SLEEP_SECONDS)
            return
        payload = {"timeout": self.POLL_TIMEOUT_SECONDS}
        if self._last_update_id:
            payload["offset"] = self._last_update_id + 1
        response = self._session.post(
            self._api_url(token, "getUpdates"),
            json=payload,
            timeout=self.POLL_TIMEOUT_SECONDS + 5,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(str(payload))
        for update in payload.get("result", []):
            self._last_update_id = max(self._last_update_id, int(update.get("update_id", 0)))
            self._handle_update(update)

    def _handle_update(self, update: Dict[str, Any]) -> None:
        if "message" in update:
            self._handle_message(update["message"])
        elif "callback_query" in update:
            self._handle_callback_query(update["callback_query"])

    def _handle_message(self, message: Dict[str, Any]) -> None:
        text = str(message.get("text", "")).strip()
        if not text:
            return
        chat = message.get("chat", {}) if isinstance(message.get("chat", {}), dict) else {}
        chat_id = str(chat.get("id", "")).strip()
        self._remember_command(text)
        if not self._is_authorized(chat_id):
            self._reply_setup_or_denied(chat_id)
            return
        response_text, keyboard, changed = self._execute_command(text)
        if changed:
            self.commit_remote_changes("Config mise a jour via Telegram.")
        self._send_text(chat_id, response_text, inline_keyboard=keyboard)

    def _handle_callback_query(self, query: Dict[str, Any]) -> None:
        query_id = str(query.get("id", "")).strip()
        data = str(query.get("data", "")).strip()
        chat_id = str(
            ((query.get("message") or {}).get("chat") or {}).get("id", "")
        ).strip()
        if not self._is_authorized(chat_id):
            self._answer_callback(query_id, "Chat non autorise.")
            self._reply_setup_or_denied(chat_id)
            return

        text, changed = self._execute_callback(data)
        if changed:
            self.commit_remote_changes("Config mise a jour via Telegram.")
        self._answer_callback(query_id, "OK")
        if text:
            self._send_text(chat_id, text, inline_keyboard=self._build_status_keyboard())

    def _remember_command(self, text: str) -> None:
        self._last_command = text
        self._last_command_at = self._now_text()

    def _is_authorized(self, chat_id: str) -> bool:
        allowed = str(self.get_params().get("telegram_allowed_chat_id", "")).strip()
        if not allowed:
            return False
        return chat_id == allowed

    def _reply_setup_or_denied(self, chat_id: str) -> None:
        allowed = str(self.get_params().get("telegram_allowed_chat_id", "")).strip()
        if not chat_id:
            return
        if not allowed:
            self._send_text(
                chat_id,
                (
                    "MAIN LOL Telegram setup.\n"
                    f"Ton Chat ID est: {chat_id}\n"
                    "Colle cette valeur dans les parametres MAIN LOL, puis referme la fenetre pour appliquer."
                ),
            )
            return
        self._send_text(chat_id, "Ce chat n'est pas autorise pour piloter MAIN LOL.")

    def _execute_callback(self, data: str) -> tuple[str, bool]:
        if data == "status":
            return self._build_status_text(), False
        if data == "history":
            return self._build_history_text(), False
        if data.startswith("toggle:"):
            param_key = data.split(":", 1)[1]
            current = bool(self.get_params().get(param_key, False))
            self.update_param(param_key, not current)
            return f"{param_key} -> {'ON' if not current else 'OFF'}", True
        return "Action Telegram inconnue.", False

    def _execute_command(self, text: str) -> tuple[str, Optional[dict], bool]:
        command, _, raw_args = text.partition(" ")
        command = command.lower().strip()
        args = raw_args.strip()

        if command in {"/start", "/help"}:
            return self._build_help_text(), self._build_status_keyboard(), False
        if command == "/whoami":
            chat_id = str(self.get_params().get("telegram_allowed_chat_id", "")).strip() or "non configure"
            return f"Chat autorise actuel: {chat_id}", None, False
        if command == "/status":
            return self._build_status_text(), self._build_status_keyboard(), False
        if command == "/history":
            return self._build_history_text(), self._build_status_keyboard(), False
        if command == "/picks":
            return self._build_picks_text(), self._build_status_keyboard(), False
        if command == "/role":
            if not args:
                return self._build_role_help_text(), None, False
            role = self._normalize_role(args)
            if not role:
                return "Role inconnu. Utilise GLOBAL, TOP, JUNGLE, MIDDLE, BOTTOM ou UTILITY.", None, False
            self.update_param("selected_profile_role", role)
            return f"Profil actif change: {ROLE_PROFILE_LABELS.get(role, role)}", self._build_status_keyboard(), True
        if command.startswith("/set_pick"):
            if not self._remote_control_enabled():
                return "Le controle distant Telegram est desactive.", None, False
            slot = command.replace("/set_pick", "")
            if slot not in {"1", "2", "3"} or not args:
                return "Usage: /set_pick1 Garen", None, False
            result = self._set_champion_value(f"selected_pick_{slot}", args)
            return result, self._build_status_keyboard(), result.startswith("Pick")
        if command == "/set_ban":
            if not self._remote_control_enabled():
                return "Le controle distant Telegram est desactive.", None, False
            if not args:
                return "Usage: /set_ban Teemo", None, False
            result = self._set_champion_value("selected_ban", args)
            return result, self._build_status_keyboard(), result.startswith("Ban")
        if command == "/set_spells":
            if not self._remote_control_enabled():
                return "Le controle distant Telegram est desactive.", None, False
            result, changed = self._set_spell_values(args)
            return result, self._build_status_keyboard(), changed
        if command in {"/enable", "/disable"}:
            if not self._remote_control_enabled():
                return "Le controle distant Telegram est desactive.", None, False
            if not args:
                return "Usage: /enable autopick", None, False
            param_key = self.FEATURE_ALIASES.get(args.lower().strip())
            if not param_key:
                return "Feature inconnue. Essaye autopick, autoban, autoaccept, spells ou playagain.", None, False
            next_value = command == "/enable"
            self.update_param(param_key, next_value)
            return f"{param_key} -> {'ON' if next_value else 'OFF'}", self._build_status_keyboard(), True
        if command == "/stats":
            return self._build_stats_text(), self._build_status_keyboard(), False
        return self._build_help_text(), self._build_status_keyboard(), False

    def _remote_control_enabled(self) -> bool:
        return bool(self.get_params().get("telegram_remote_control_enabled", True))

    def _normalize_role(self, role: str) -> Optional[str]:
        normalized = self.ROLE_ALIASES.get(str(role or "").strip().lower())
        if normalized in {"GLOBAL", *ROLE_PROFILE_ORDER}:
            return normalized
        return None

    def _normalize_spell(self, spell_name: str) -> Optional[str]:
        target = str(spell_name or "").strip().lower()
        for spell in SUMMONER_SPELL_LIST:
            if spell.lower() == target:
                return spell
        return None

    def _resolve_champion_name(self, name: str) -> Optional[str]:
        champion_id = self.dd.resolve_champion(name)
        if not champion_id:
            return None
        return self.dd.id_to_name(champion_id) or str(name).strip()

    def _get_selected_profile_role(self, params: Dict[str, Any]) -> str:
        normalized = self._normalize_role(str(params.get("selected_profile_role", "GLOBAL")))
        return normalized or "GLOBAL"

    def _set_profile_value(self, key: str, value: str) -> None:
        params = self.get_params()
        role = self._get_selected_profile_role(params)
        if role == "GLOBAL":
            global_key = {"spell_1": "global_spell_1", "spell_2": "global_spell_2"}.get(key, key)
            self.update_param(global_key, value)
            return

        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
        role_data = new_profiles.get(role, {})
        role_data[key] = value
        new_profiles[role] = role_data
        self.update_param("role_profiles", new_profiles)

    def _set_champion_value(self, key: str, raw_name: str) -> str:
        champion_name = self._resolve_champion_name(raw_name)
        if not champion_name:
            return f"Champion introuvable: {raw_name}"
        self._set_profile_value(key, champion_name)
        if key == "selected_ban":
            return f"Ban mis a jour: {champion_name}"
        slot = key.rsplit("_", 1)[-1]
        return f"Pick {slot} mis a jour: {champion_name}"

    def _set_spell_values(self, args: str) -> tuple[str, bool]:
        parts = [part for part in args.split() if part]
        if len(parts) != 2:
            return "Usage: /set_spells Flash Heal", False
        spell_1 = self._normalize_spell(parts[0])
        spell_2 = self._normalize_spell(parts[1])
        if not spell_1 or not spell_2:
            return "Sort inconnu. Exemples: Flash, Ignite, Heal, Smite, Teleport.", False
        self._set_profile_value("spell_1", spell_1)
        self._set_profile_value("spell_2", spell_2)
        return f"Sorts mis a jour: {spell_1} + {spell_2}", True

    def _build_stats_urls(self) -> tuple[str, str]:
        snapshot = self.get_snapshot()
        riot_id = str(snapshot.get("riot_id") or "").strip()
        region = str(snapshot.get("region") or "euw").strip().lower()
        params = self.get_params()
        if not is_valid_riot_id(riot_id):
            manual_riot_id = str(params.get("manual_summoner_name", "")).strip()
            if is_valid_riot_id(manual_riot_id):
                riot_id = manual_riot_id
        if not is_valid_riot_id(riot_id):
            return "", ""
        return (
            build_stats_site_url(params.get("preferred_stats_site", "opgg"), region, riot_id),
            build_hotkey_site_url(params.get("preferred_hotkey_site", "porofessor"), region, riot_id),
        )

    def _build_status_text(self) -> str:
        snapshot = self.get_snapshot()
        effective = snapshot.get("effective", {})
        params = snapshot.get("params", {})
        lcu = snapshot.get("lcu", {})
        role = snapshot.get("selected_profile_role") or "GLOBAL"
        lines = [
            "MAIN LOL - Etat distant",
            f"LCU: {'connecte' if snapshot.get('connected') else 'deconnecte'}",
            f"Phase: {snapshot.get('phase_label') or snapshot.get('phase') or 'Inconnue'}",
            f"Compte: {snapshot.get('riot_id') or 'Inconnu'}",
            f"Region: {snapshot.get('region') or 'euw'}",
            f"Profil actif: {ROLE_PROFILE_LABELS.get(role, role)}",
            f"Role detecte: {ROLE_PROFILE_LABELS.get(snapshot.get('detected_role') or 'GLOBAL', snapshot.get('detected_role') or 'Global')}",
            "",
            f"Auto-accept: {'ON' if params.get('auto_accept_enabled', True) else 'OFF'}",
            f"Auto-pick: {'ON' if params.get('auto_pick_enabled', True) else 'OFF'}",
            f"Auto-ban: {'ON' if params.get('auto_ban_enabled', True) else 'OFF'}",
            f"Auto-spells: {'ON' if params.get('auto_summoners_enabled', True) else 'OFF'}",
            f"Play again: {'ON' if params.get('auto_play_again_enabled', False) else 'OFF'}",
            "",
            f"Pick 1: {effective.get('selected_pick_1') or '...'}",
            f"Pick 2: {effective.get('selected_pick_2') or '...'}",
            f"Pick 3: {effective.get('selected_pick_3') or '...'}",
            f"Ban: {effective.get('selected_ban') or '...'}",
            f"Sorts: {effective.get('spell_1') or '...'} + {effective.get('spell_2') or '...'}",
            "",
            f"LCU retries GET: {lcu.get('retry_count', 0)}",
            f"LCU erreurs endpoint: {lcu.get('endpoint_error_count', 0)}",
            f"LCU reconnexions: {lcu.get('reconnect_count', 0)}",
        ]
        if lcu.get("last_error"):
            lines.append(f"Derniere erreur LCU: {lcu.get('last_error')}")
        return "\n".join(lines)

    def _build_picks_text(self) -> str:
        snapshot = self.get_snapshot()
        effective = snapshot.get("effective", {})
        selected_role = snapshot.get("selected_profile_role") or "GLOBAL"
        return (
            f"Profil: {ROLE_PROFILE_LABELS.get(selected_role, selected_role)}\n"
            f"Pick 1: {effective.get('selected_pick_1') or '...'}\n"
            f"Pick 2: {effective.get('selected_pick_2') or '...'}\n"
            f"Pick 3: {effective.get('selected_pick_3') or '...'}\n"
            f"Ban: {effective.get('selected_ban') or '...'}\n"
            f"Sorts: {effective.get('spell_1') or '...'} + {effective.get('spell_2') or '...'}"
        )

    def _build_stats_text(self) -> str:
        stats_url, ingame_url = self._build_stats_urls()
        if not stats_url:
            return "Riot ID invalide ou indisponible pour generer les liens."
        return f"Stats: {stats_url}\nIn-game: {ingame_url}"

    def _build_history_text(self) -> str:
        entries = [format_history_entry(entry) for entry in get_history_entries(limit=5)]
        if not entries:
            return "Aucun historique recent."
        lines = ["Historique recent:"]
        for entry in entries:
            lines.append(f"{entry['time']} | {entry['category']} | {entry['message']}")
        return "\n".join(lines)

    def _build_help_text(self) -> str:
        return (
            "Commandes MAIN LOL Telegram:\n"
            "/status - resume complet\n"
            "/picks - picks, ban et sorts\n"
            "/history - 5 derniers evenements\n"
            "/role top|jungle|mid|adc|support|global\n"
            "/set_pick1 Garen\n"
            "/set_pick2 Lux\n"
            "/set_pick3 Ashe\n"
            "/set_ban Teemo\n"
            "/set_spells Flash Ignite\n"
            "/enable autopick | /disable autoban\n"
            "/stats - liens de stats\n"
            "/whoami - rappel du chat autorise"
        )

    def _build_role_help_text(self) -> str:
        labels = ", ".join(["global", "top", "jungle", "mid", "adc", "support"])
        return f"Usage: /role <role>\nRoles disponibles: {labels}"

    def _build_status_keyboard(self) -> Optional[dict]:
        stats_url, ingame_url = self._build_stats_urls()
        rows = []
        if stats_url:
            rows.append(
                [
                    {"text": "Voir mes stats", "url": stats_url},
                    {"text": "Voir in-game", "url": ingame_url},
                ]
            )
        rows.append(
            [
                {"text": "Refresh statut", "callback_data": "status"},
                {"text": "Historique", "callback_data": "history"},
            ]
        )
        rows.append(
            [
                {"text": "Toggle auto-pick", "callback_data": "toggle:auto_pick_enabled"},
                {"text": "Toggle auto-ban", "callback_data": "toggle:auto_ban_enabled"},
            ]
        )
        rows.append(
            [
                {"text": "Toggle auto-spells", "callback_data": "toggle:auto_summoners_enabled"},
                {"text": "Toggle auto-accept", "callback_data": "toggle:auto_accept_enabled"},
            ]
        )
        return {"inline_keyboard": rows}

    def _send_status_message(self, chat_id: str) -> None:
        self._send_text(chat_id, self._build_status_text(), inline_keyboard=self._build_status_keyboard())

    def _send_text(self, chat_id: str, text: str, *, inline_keyboard: Optional[dict] = None) -> None:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if inline_keyboard:
            payload["reply_markup"] = inline_keyboard
        response = self._session.post(
            self._api_url(str(self.get_params().get("telegram_bot_token", "")).strip(), "sendMessage"),
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(str(data))
        self._messages_sent += 1

    def _answer_callback(self, query_id: str, text: str) -> None:
        token = str(self.get_params().get("telegram_bot_token", "")).strip()
        if not token or not query_id:
            return
        try:
            response = self._session.post(
                self._api_url(token, "answerCallbackQuery"),
                json={"callback_query_id": query_id, "text": text},
                timeout=10,
            )
            response.raise_for_status()
        except Exception as e:
            logging.debug(f"Telegram callback ack impossible: {e}")
