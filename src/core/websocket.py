"""LCU connection lifecycle and event dispatch."""

import asyncio
import logging
from threading import Event, Thread, current_thread
from time import time
from typing import Any, Callable, Dict, Optional

try:
    from lcu_driver import Connector
except ImportError:
    Connector = None

from ..config import (
    EP_CHAT_ME,
    EP_CURRENT_SUMMONER,
    EP_GAMEFLOW,
    EP_LOGIN,
    EP_READY_CHECK,
    EP_SESSION,
    EP_SESSION_TIMER,
    PHASE_DISPLAY_MAP,
    PLATFORM_TO_REGION,
    ROLE_PROFILE_LABELS,
)
from .champ_select import ChampSelectMixin
from .game_state import GameState
from ..services.history import log_history_event


class WebSocketManager(ChampSelectMixin):
    """Gestionnaire WebSocket pour la communication avec le client LoL."""

    EVENT_CONNECTED = "connected"
    EVENT_DISCONNECTED = "disconnected"
    EVENT_STATUS = "status"
    EVENT_PHASE_CHANGE = "phase_change"
    EVENT_SUMMONER_UPDATE = "summoner_update"
    EVENT_CHAMPION_PICKED = "champion_picked"
    EVENT_CHAMPION_BANNED = "champion_banned"
    EVENT_SPELLS_SET = "spells_set"
    EVENT_PLAY_AGAIN = "play_again"
    EVENT_TOAST = "toast"
    EVENT_READY_CHECK_ACCEPTED = "ready_check_accepted"

    def __init__(
        self,
        ui_callback: Callable[[str, Any], None],
        dd,
        get_params: Callable[[], Dict[str, Any]],
        update_param: Optional[Callable[[str, Any], None]] = None,
    ):
        self.ui_callback = ui_callback
        self.dd = dd
        self.get_params = get_params
        self.update_param = update_param
        self.state = GameState()
        self.connection = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.connector = None
        self.thread: Optional[Thread] = None
        self.ws_active: bool = False
        self._stop_event = Event()
        self._cs_tick_lock = asyncio.Lock()
        self.game_start_cooldown: float = 12.0

    def _notify_ui(self, event_type: str, data: Any = None) -> None:
        self.ui_callback(event_type, data)

    def _log_history(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        log_history_event(event_type, message, details)

    def start(self) -> None:
        if Connector is None:
            self._notify_ui(self.EVENT_STATUS, ("❌ Erreur: 'lcu_driver' manquant.", ""))
            return
        if self.thread and self.thread.is_alive():
            return
        self._stop_event.clear()
        self.thread = Thread(target=self._ws_loop, daemon=True, name="mainlol-lcu")
        self.thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self.connector and self.connection and self.loop and not self.loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(self.connector.stop(), self.loop)
                future.result(timeout=3)
            except Exception as e:
                logging.debug(f"WebSocket: arret du connector incomplet - {e}")

        if self.thread and self.thread.is_alive() and self.thread is not current_thread():
            self.thread.join(timeout=3)

    @property
    def is_active(self) -> bool:
        return self.ws_active

    def get_riot_id(self) -> Optional[str]:
        if self.state.auto_game_name and self.state.auto_tag_line:
            return f"{self.state.auto_game_name}#{self.state.auto_tag_line}"
        return self.state.summoner or None

    def get_platform_for_websites(self) -> str:
        params = self.get_params()
        if not params.get("summoner_name_auto_detect", True):
            return params.get("manual_region", "euw").lower()
        return (
            params.get("auto_detected_region")
            or PLATFORM_TO_REGION.get((self.state.platform_routing or "").lower(), "euw")
        ).lower()

    @staticmethod
    def _normalize_role(role: str) -> str:
        role = (role or "").upper()
        aliases = {
            "MID": "MIDDLE",
            "MIDDLE": "MIDDLE",
            "JGL": "JUNGLE",
            "JUNGLE": "JUNGLE",
            "ADC": "BOTTOM",
            "BOT": "BOTTOM",
            "BOTTOM": "BOTTOM",
            "SUP": "UTILITY",
            "SUPPORT": "UTILITY",
            "UTILITY": "UTILITY",
            "TOP": "TOP",
        }
        return aliases.get(role, role)

    def _get_effective_champ_select_config(self, params: Dict[str, Any]) -> Dict[str, str]:
        effective = self.get_effective_profile_config(params=params)
        return {
            "selected_pick_1": effective["selected_pick_1"],
            "selected_pick_2": effective["selected_pick_2"],
            "selected_pick_3": effective["selected_pick_3"],
            "selected_ban": effective["selected_ban"],
        }

    def get_effective_profile_config(
        self,
        role: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = params or self.get_params()
        role = self._normalize_role(role or self.state.assigned_position)
        resolved_role = role if role in ROLE_PROFILE_LABELS and role != "GLOBAL" else "GLOBAL"
        role_profiles = params.get("role_profiles", {})
        role_data = role_profiles.get(resolved_role, {}) if isinstance(role_profiles, dict) else {}
        if not isinstance(role_data, dict):
            role_data = {}

        return {
            "detected_role": self._normalize_role(self.state.assigned_position) or "GLOBAL",
            "resolved_role": resolved_role,
            "resolved_role_label": ROLE_PROFILE_LABELS.get(resolved_role, "Global"),
            "fallback_policy": "Le profil du role detecte est prioritaire, puis la config globale prend le relais si un champ est vide.",
            "selected_pick_1": role_data.get("selected_pick_1") or params.get("selected_pick_1", ""),
            "selected_pick_2": role_data.get("selected_pick_2") or params.get("selected_pick_2", ""),
            "selected_pick_3": role_data.get("selected_pick_3") or params.get("selected_pick_3", ""),
            "selected_ban": role_data.get("selected_ban") or params.get("selected_ban", ""),
            "spell_1": role_data.get("spell_1") or params.get("global_spell_1", ""),
            "spell_2": role_data.get("spell_2") or params.get("global_spell_2", ""),
            "sources": {
                "selected_pick_1": resolved_role if role_data.get("selected_pick_1") else "GLOBAL",
                "selected_pick_2": resolved_role if role_data.get("selected_pick_2") else "GLOBAL",
                "selected_pick_3": resolved_role if role_data.get("selected_pick_3") else "GLOBAL",
                "selected_ban": resolved_role if role_data.get("selected_ban") else "GLOBAL",
                "spell_1": resolved_role if role_data.get("spell_1") else "GLOBAL",
                "spell_2": resolved_role if role_data.get("spell_2") else "GLOBAL",
            },
        }

    def _store_auto_detected_values(self, riot_id: Optional[str], platform: str = "", region: str = "") -> None:
        if not self.update_param:
            return
        self.update_param("auto_detected_riot_id", riot_id or "")
        if platform:
            self.update_param("auto_detected_platform", platform.lower())
        if region:
            self.update_param("auto_detected_region", region.lower())

    def force_refresh_summoner(self) -> None:
        if self.ws_active and self.connection and self.loop:
            asyncio.run_coroutine_threadsafe(self._refresh_player_and_region(), self.loop)

    def _ws_loop(self) -> None:
        if Connector is None:
            return

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            connector = Connector(loop=loop)
            self.connector = connector

            @connector.ready
            async def on_ready(connection):
                self.connection = connection
                self.ws_active = True
                log_history_event("connection", "Client LoL detecte.")
                self._notify_ui(self.EVENT_CONNECTED, None)
                self._notify_ui(self.EVENT_STATUS, ("Client LoL detecte ! Pret a vous aider.", "⚡"))
                logging.info("WebSocket: Connecte au client LCU.")
                await self._refresh_player_and_region()

            @connector.close
            async def on_close(connection):
                self.connection = None
                self.ws_active = False
                self.state.last_reported_summoner = None
                if not self._stop_event.is_set():
                    log_history_event("connection", "Client LoL deconnecte, reconnexion en cours.")
                    self._notify_ui(self.EVENT_DISCONNECTED, None)
                    self._notify_ui(self.EVENT_STATUS, ("Client LoL deconnecte. Tentative de reconnexion...", "💤"))
                    logging.info("WebSocket: Deconnecte.")
                else:
                    logging.info("WebSocket: Arret demande.")

            @connector.ws.register(EP_CURRENT_SUMMONER)
            async def _ws_summoner_change(connection, event):
                await self._refresh_player_and_region()

            @connector.ws.register(EP_CHAT_ME)
            async def _ws_chat_me_change(connection, event):
                await self._refresh_player_and_region()

            @connector.ws.register(EP_LOGIN)
            async def _ws_login_session(connection, event):
                data = event.data or {}
                if data.get("status") == "SUCCEEDED":
                    self._notify_ui(self.EVENT_STATUS, ("Login detecte...", "🔄"))
                    await self._refresh_player_and_region()

            @connector.ws.register(EP_GAMEFLOW)
            async def _ws_phase(connection, event):
                phase = event.data
                if not phase:
                    return

                if phase != self.state.current_phase:
                    logging.info(f"Phase changee : {self.state.current_phase} -> {phase}")
                self.state.current_phase = phase

                friendly_phase = PHASE_DISPLAY_MAP.get(phase, phase)
                self._notify_ui(self.EVENT_PHASE_CHANGE, phase)
                self._notify_ui(self.EVENT_STATUS, (f"Statut : {friendly_phase}", "ℹ️"))

                if phase == "ChampSelect":
                    self.state.reset_between_games()
                    await self._champ_select_tick()
                if phase in ("EndOfGame", "WaitingForStats"):
                    await self._handle_post_game()

            @connector.ws.register(EP_READY_CHECK)
            async def _ws_ready(connection, event):
                if self.state.current_phase not in ["Matchmaking", "ReadyCheck", "None", "Lobby"]:
                    return
                data = event.data or {}
                params = self.get_params()
                if (
                    params.get("auto_accept_enabled", True)
                    and data.get("state") == "InProgress"
                    and data.get("playerResponse") != "Accepted"
                ):
                    response = await connection.request("post", f"{EP_READY_CHECK}/accept")
                    if response and response.status < 400:
                        log_history_event("ready_check", "Partie acceptee automatiquement.")
                        self._notify_ui(self.EVENT_STATUS, ("Partie acceptee !", "✅"))
                        if not self.state.has_played_accept_sound:
                            self.state.has_played_accept_sound = True
                            self._notify_ui(self.EVENT_READY_CHECK_ACCEPTED, None)

            @connector.ws.register(EP_SESSION)
            async def _ws_cs_session(connection, event):
                if self._cs_tick_lock.locked():
                    return
                async with self._cs_tick_lock:
                    await self._champ_select_tick()

            @connector.ws.register(EP_SESSION_TIMER)
            async def _ws_cs_timer(connection, event):
                if time() - self.state._last_cs_timer_fetch > 0.2:
                    await self._champ_select_timer_tick()
                    self.state._last_cs_timer_fetch = time()

            connector.start()
        except Exception as e:
            logging.critical(f"[WS] Erreur critique dans la boucle WebSocket : {e}", exc_info=True)
            self.ws_active = False
            if not self._stop_event.is_set():
                self._notify_ui(self.EVENT_DISCONNECTED, None)
        finally:
            self.connection = None
            self.ws_active = False
            self.connector = None
            self.loop = None

    async def _refresh_player_and_region(self) -> None:
        if not self.connection:
            return

        chat_me = None
        resp_chat = await self.connection.request("get", "/lol-chat/v1/me")
        if resp_chat.status == 200:
            chat_me = await resp_chat.json()

        if isinstance(chat_me, dict):
            self.state.auto_game_name = chat_me.get("gameName")
            self.state.auto_tag_line = chat_me.get("gameTag")
            if self.state.auto_game_name and self.state.auto_tag_line:
                self.state.summoner = f"{self.state.auto_game_name}#{self.state.auto_tag_line}"
            else:
                self.state.summoner = chat_me.get("name", "Inconnu")
            self.state.summoner_id = chat_me.get("summonerId")
            self.state.puuid = chat_me.get("puuid")
        else:
            resp_me = await self.connection.request("get", "/lol-summoner/v1/current-summoner")
            if resp_me.status == 200:
                me = await resp_me.json()
                self.state.summoner = me.get("displayName", "Inconnu")

        if self.state.summoner != self.state.last_reported_summoner:
            self._notify_ui(self.EVENT_SUMMONER_UPDATE, self.get_riot_id())
            self._notify_ui(self.EVENT_STATUS, (f"Connecte : {self.get_riot_id()}", "👤"))
            self.state.last_reported_summoner = self.state.summoner
        self._store_auto_detected_values(self.get_riot_id(), self.state.platform_routing, self.get_platform_for_websites())

        reg = None
        resp_reg = await self.connection.request("get", "/riotclient/get_region_locale")
        if resp_reg.status != 200:
            resp_reg = await self.connection.request("get", "/riotclient/region-locale")
        if resp_reg.status == 200:
            reg = await resp_reg.json()

        if isinstance(reg, dict):
            platform = (reg.get("platformId") or reg.get("region") or "").lower()
            if platform:
                self.state.platform_routing = platform
                self.state.region_routing = self._platform_to_region_routing(platform)
                self._store_auto_detected_values(
                    self.get_riot_id(),
                    platform,
                    PLATFORM_TO_REGION.get(platform, "euw"),
                )

    @staticmethod
    def _platform_to_region_routing(platform: str) -> str:
        platform = platform.lower()
        if platform in {"euw1", "eun1", "tr1", "ru"}:
            return "europe"
        if platform in {"na1", "br1", "la1", "la2", "oc1"}:
            return "americas"
        if platform in {"kr", "jp1"}:
            return "asia"
        return "europe"
