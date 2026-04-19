"""LCU connection lifecycle and event dispatch."""

import asyncio
import logging
from threading import Event, Thread, current_thread
from time import time
from typing import Any, Callable, Dict, List, Optional

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
    PICK_SLOT_ORDER,
    PLATFORM_TO_REGION,
    ROLE_PROFILE_LABELS,
)
from ..services.history import log_history_event
from .champ_select import ChampSelectMixin
from .game_state import GameState


class WebSocketManager(ChampSelectMixin):
    """WebSocket manager for communication with the LoL client."""

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

    def _log_history(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        *,
        level: Optional[str] = None,
        category: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:
        log_history_event(event_type, message, details, level=level, category=category, action=action)

    def start(self) -> None:
        if Connector is None:
            self._notify_ui(self.EVENT_STATUS, ("Error: 'lcu_driver' is missing.", "ERROR"))
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
                logging.debug("WebSocket: incomplete connector stop - %s", e)

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
            "presets_enabled": effective["presets_enabled"],
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
        role_has_presets_override = "presets_enabled" in role_data
        global_pick_slots = params.get("pick_slots", {}) if isinstance(params.get("pick_slots", {}), dict) else {}
        role_pick_slots = role_data.get("pick_slots", {}) if isinstance(role_data.get("pick_slots", {}), dict) else {}

        def _resolve_slot(slot_key: str, pick_key: str) -> Dict[str, Any]:
            global_slot = (
                global_pick_slots.get(slot_key, {}) if isinstance(global_pick_slots.get(slot_key, {}), dict) else {}
            )
            role_slot = role_pick_slots.get(slot_key, {}) if isinstance(role_pick_slots.get(slot_key, {}), dict) else {}
            skin_source_role = (
                resolved_role
                if any(
                    role_slot.get(field)
                    for field in ("skin_mode", "skin_id", "skin_name", "skin_num", "random_skin_pool")
                )
                else "GLOBAL"
            )
            return {
                "champion": role_data.get(pick_key) or params.get(pick_key, ""),
                "spell_1": role_slot.get("spell_1") or global_slot.get("spell_1", ""),
                "spell_2": role_slot.get("spell_2") or global_slot.get("spell_2", ""),
                "skin_mode": role_slot.get("skin_mode") or global_slot.get("skin_mode", "none"),
                "skin_id": int(role_slot.get("skin_id") or global_slot.get("skin_id", 0) or 0),
                "skin_name": role_slot.get("skin_name") or global_slot.get("skin_name", ""),
                "skin_num": int(role_slot.get("skin_num") or global_slot.get("skin_num", 0) or 0),
                "random_skin_id": int(role_slot.get("random_skin_id") or global_slot.get("random_skin_id", 0) or 0),
                "random_skin_name": role_slot.get("random_skin_name") or global_slot.get("random_skin_name", ""),
                "random_skin_num": int(role_slot.get("random_skin_num") or global_slot.get("random_skin_num", 0) or 0),
                "random_skin_pool": role_slot.get("random_skin_pool") or global_slot.get("random_skin_pool", []),
                "skin_source_role": skin_source_role,
            }

        pick_slots = {
            slot_key: _resolve_slot(slot_key, f"selected_pick_{index}")
            for index, slot_key in enumerate(PICK_SLOT_ORDER, start=1)
        }
        first_slot = pick_slots["pick_1"]

        return {
            "detected_role": self._normalize_role(self.state.assigned_position) or "GLOBAL",
            "resolved_role": resolved_role,
            "resolved_role_label": ROLE_PROFILE_LABELS.get(resolved_role, "Global"),
            "fallback_policy": "The detected role profile has priority, then the global config fills empty fields.",
            "presets_enabled": (
                bool(role_data.get("presets_enabled"))
                if role_has_presets_override
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
                "presets_enabled": resolved_role if role_has_presets_override else "GLOBAL",
                "selected_pick_1": resolved_role if role_data.get("selected_pick_1") else "GLOBAL",
                "selected_pick_2": resolved_role if role_data.get("selected_pick_2") else "GLOBAL",
                "selected_pick_3": resolved_role if role_data.get("selected_pick_3") else "GLOBAL",
                "selected_ban": resolved_role if role_data.get("selected_ban") else "GLOBAL",
                "spell_1": (
                    resolved_role
                    if pick_slots["pick_1"].get("spell_1") and role_pick_slots.get("pick_1", {}).get("spell_1")
                    else "GLOBAL"
                ),
                "spell_2": (
                    resolved_role
                    if pick_slots["pick_1"].get("spell_2") and role_pick_slots.get("pick_1", {}).get("spell_2")
                    else "GLOBAL"
                ),
            },
        }

    def get_current_summoner_id(self) -> Optional[int]:
        try:
            return int(self.state.summoner_id or 0) or None
        except (TypeError, ValueError):
            return None

    def fetch_owned_skins_for_champion(self, champion_id: int) -> Dict[str, Any]:
        if not self.ws_active or not self.connection or not self.loop:
            return {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "owned_skins": [],
            }
        future = asyncio.run_coroutine_threadsafe(self._fetch_owned_skins_for_champion(champion_id), self.loop)
        try:
            return future.result(timeout=8)
        except Exception as e:
            logging.debug("WebSocket: owned skins fetch failed - %s", e)
            return {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "owned_skins": [],
            }

    @staticmethod
    def _inventory_skin_is_owned(item: Dict[str, Any]) -> bool:
        bool_fields = ("owned", "isOwned", "unlocked", "isUnlocked", "purchaseable", "purchased")
        ownership_fields_found = False
        for field in bool_fields:
            if field in item and isinstance(item.get(field), bool):
                ownership_fields_found = True
                if field in {"purchaseable"}:
                    continue
                if item[field]:
                    return True
        string_fields = ("ownershipType", "ownership", "purchaseState", "status")
        for field in string_fields:
            raw_value = item.get(field)
            if raw_value in {None, ""}:
                continue
            ownership_fields_found = True
            normalized = str(raw_value).strip().lower()
            if normalized in {"owned", "ownership_owned", "rental", "rent", "free_to_play", "freetoplay", "unlocked"}:
                return True
            if normalized in {"unowned", "not_owned", "locked", "purchasable", "purchaseable"}:
                return False
        nested_ownership = item.get("ownership")
        if isinstance(nested_ownership, dict):
            ownership_fields_found = True
            if isinstance(nested_ownership.get("owned"), bool):
                return bool(nested_ownership.get("owned"))
            if isinstance(nested_ownership.get("isOwned"), bool):
                return bool(nested_ownership.get("isOwned"))
        return not ownership_fields_found

    async def _fetch_owned_skins_for_champion(self, champion_id: int) -> Dict[str, Any]:
        if not self.connection:
            return {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "owned_skins": [],
            }
        summoner_id = self.get_current_summoner_id()
        if not summoner_id:
            await self._refresh_player_and_region()
            summoner_id = self.get_current_summoner_id()
        if not summoner_id:
            return {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "owned_skins": [],
            }

        endpoint = f"/lol-champions/v1/inventories/{summoner_id}/champions/{champion_id}/skins"
        try:
            response = await self.connection.request("get", endpoint)
            if response.status != 200:
                return {
                    "ok": False,
                    "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                    "owned_skins": [],
                }
            payload = await response.json()
        except Exception as e:
            logging.debug("WebSocket: inventory skins request failed - %s", e)
            return {
                "ok": False,
                "message": "Impossible de recuperer les skins. Verifiez votre connexion a League of Legends.",
                "owned_skins": [],
            }

        champion_name = self.dd.id_to_name(champion_id) or str(champion_id)
        catalog = self.dd.get_skin_catalog(champion_name)
        by_skin_id = {int(entry.get("skin_id") or 0): entry for entry in catalog}
        by_name = {str(entry.get("skin_name") or "").strip().lower(): entry for entry in catalog}
        owned_skins: List[Dict[str, Any]] = []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            if not self._inventory_skin_is_owned(item):
                continue
            try:
                skin_id = int(item.get("id") or item.get("skinId") or item.get("championSkinId") or 0)
            except (TypeError, ValueError):
                skin_id = 0
            skin_name = str(item.get("name") or item.get("displayName") or "")
            skin_data = by_skin_id.get(skin_id) or by_name.get(skin_name.strip().lower())
            if not skin_data:
                skin_data = self.dd.resolve_skin_data(champion_name, skin_id=skin_id, skin_name=skin_name)
            if not skin_data:
                continue
            owned_skins.append(
                {
                    "skin_id": int(skin_data.get("skin_id") or skin_id or 0),
                    "skin_num": int(skin_data.get("skin_num") or 0),
                    "skin_name": str(skin_data.get("skin_name") or skin_name or ""),
                    "splash_url": skin_data.get("splash_url", ""),
                    "tile_url": skin_data.get("tile_url", ""),
                    "preview_url": (
                        skin_data.get("tile_url")
                        or skin_data.get("centered_splash_url")
                        or skin_data.get("uncentered_splash_url")
                        or skin_data.get("splash_url", "")
                    ),
                }
            )

        unique_skins = []
        seen_ids = set()
        for skin in owned_skins:
            if skin["skin_id"] in seen_ids:
                continue
            seen_ids.add(skin["skin_id"])
            unique_skins.append(skin)
        return {"ok": True, "message": "", "owned_skins": unique_skins}

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
        """Run the LCU connector in its own asyncio loop and forward LCU events to the UI thread."""
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
                log_history_event(
                    "connection",
                    "LoL client detected and connection established.",
                    {"region": self.get_platform_for_websites()},
                    level="success",
                    category="Connection",
                    action="connected",
                )
                self._notify_ui(self.EVENT_CONNECTED, None)
                self._notify_ui(self.EVENT_STATUS, ("LoL client detected! Ready to help.", "WS"))
                logging.info("[WS] Connected to the LCU client.")
                await self._refresh_player_and_region()

            @connector.close
            async def on_close(connection):
                self.connection = None
                self.ws_active = False
                self.state.last_reported_summoner = None
                if not self._stop_event.is_set():
                    log_history_event(
                        "connection",
                        "LoL client connection lost, trying to reconnect.",
                        level="warning",
                        category="Connection",
                        action="disconnected",
                    )
                    self._notify_ui(self.EVENT_DISCONNECTED, None)
                    self._notify_ui(self.EVENT_STATUS, ("LoL client disconnected. Trying to reconnect...", "WARN"))
                    logging.info("[WS] Disconnected.")
                else:
                    logging.info("[WS] Stop requested.")

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
                    self._notify_ui(self.EVENT_STATUS, ("Login detected...", "INFO"))
                    await self._refresh_player_and_region()

            @connector.ws.register(EP_GAMEFLOW)
            async def _ws_phase(connection, event):
                phase = event.data
                if not phase:
                    return

                if phase != self.state.current_phase:
                    logging.info("[PHASE] %s -> %s", self.state.current_phase, phase)
                self.state.current_phase = phase

                friendly_phase = PHASE_DISPLAY_MAP.get(phase, phase)
                self._notify_ui(self.EVENT_PHASE_CHANGE, phase)
                self._notify_ui(self.EVENT_STATUS, (f"Status: {friendly_phase}", "INFO"))

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
                    accept_url = f"{EP_READY_CHECK}/accept"
                    logging.info("[READY] POST %s", accept_url)
                    response = await connection.request("post", accept_url)
                    logging.info("[READY] POST %s -> %s", accept_url, getattr(response, "status", "no-response"))
                    if response and response.status < 400:
                        log_history_event(
                            "ready_check",
                            "Match automatically accepted.",
                            level="success",
                            category="Match found",
                            action="accepted",
                        )
                        self._notify_ui(self.EVENT_STATUS, ("Match accepted!", "OK"))
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
            logging.critical("[WS] Critical error in the WebSocket loop: %s", e, exc_info=True)
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
                self.state.summoner = chat_me.get("name", "Unknown")
            self.state.summoner_id = chat_me.get("summonerId")
            self.state.puuid = chat_me.get("puuid")
        else:
            resp_me = await self.connection.request("get", "/lol-summoner/v1/current-summoner")
            if resp_me.status == 200:
                me = await resp_me.json()
                self.state.summoner = me.get("displayName", "Unknown")

        if self.state.summoner != self.state.last_reported_summoner:
            self._notify_ui(self.EVENT_SUMMONER_UPDATE, self.get_riot_id())
            self._notify_ui(self.EVENT_STATUS, (f"Connected: {self.get_riot_id()}", "USER"))
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
