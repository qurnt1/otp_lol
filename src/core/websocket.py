"""
FILE NAME: src/core/websocket.py
GLOBAL PURPOSE:
- Maintain the live connection to the League Client Update API.
- Translate raw LCU events into application-level callbacks, state updates, and automation triggers.
- Bridge websocket transport, game-state tracking, and champion-select orchestration.

KEY FUNCTIONS:
- WebSocketManager: Own the LCU connector lifecycle and runtime state.
- _ws_loop: Run the connector inside a dedicated asyncio loop and register event handlers.
- get_effective_profile_config: Resolve global and role-specific settings into one effective profile.
- _refresh_player_and_region: Keep detected account and region data synchronized with the client.

AUDIENCE & LOGIC:
Why:
This module isolates transport concerns from UI code so client reconnects, event dispatch, and automation triggers remain explicit and testable.
For whom:
Developers maintaining the live client integration, reconnect behavior, and runtime profile resolution.

DEPENDENCIES:
Used by:
- launcher.py and src/ui/main_window.py through OtpLolApplication wiring.
Uses:
- Standard library: asyncio, logging, threading, time, typing
- Optional third-party libraries: lcu_driver, psutil
- Local modules: src.config, src.services.history, src.core.champ_select, src.core.game_state
"""

import asyncio
import logging
from threading import Event, Thread, current_thread
from time import time
from typing import Any, Callable, Dict, List, Optional

try:
    from lcu_driver import Connector
except ImportError:
    Connector = None

try:
    import psutil
except ImportError:
    psutil = None

from ..config import (
    EP_CHAT_ME,
    EP_CURRENT_SUMMONER,
    EP_GAMEFLOW,
    EP_LOGIN,
    EP_PERKS_CURRENT_PAGE,
    EP_PERKS_PAGES,
    EP_PERKS_STYLES,
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
    """Manage the LCU connector lifecycle and dispatch live client events."""

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
    WS_RETRY_DELAY_S = 2.0

    def __init__(
        self,
        ui_callback: Callable[[str, Any], None],
        dd,
        get_params: Callable[[], Dict[str, Any]],
        update_param: Optional[Callable[[str, Any], None]] = None,
    ):
        """Store shared collaborators and initialize per-run websocket state."""
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
        """Start the background LCU loop if the connector is available."""
        if Connector is None:
            self._notify_ui(self.EVENT_STATUS, ("Error: 'lcu_driver' is missing.", "ERROR"))
            return
        if self.thread and self.thread.is_alive():
            return
        self._stop_event.clear()
        self.thread = Thread(target=self._ws_loop, daemon=True, name="otp-lol-lcu")
        self.thread.start()

    def stop(self) -> None:
        """Request connector shutdown and wait briefly for the worker thread to exit."""
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
        """Resolve the effective profile by combining role overrides with global fallbacks."""
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
            # Slot-level data follows the same rule everywhere: explicit role
            # overrides win, otherwise global values fill the gaps.

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
                "rune_page_id": int(role_slot.get("rune_page_id") or global_slot.get("rune_page_id") or 0),
                "rune_page_name": str(role_slot.get("rune_page_name") or global_slot.get("rune_page_name") or ""),
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

    async def _fetch_rune_pages_async(self) -> List[Dict[str, Any]]:
        """Fetch all valid rune pages from the LCU."""
        if not self.connection:
            return []
        try:
            response = await self.connection.request("get", EP_PERKS_PAGES)
            if not response or response.status != 200:
                return []
            payload = await response.json()
            if not isinstance(payload, list):
                return []
            pages: List[Dict[str, Any]] = []
            for page in payload:
                if not isinstance(page, dict):
                    continue
                if not page.get("isValid", True):
                    continue
                pages.append({
                    "id": page.get("id", 0),
                    "name": str(page.get("name") or ""),
                    "primaryStyleId": page.get("primaryStyleId", 0),
                    "subStyleId": page.get("subStyleId", 0),
                    "selectedPerkIds": page.get("selectedPerkIds", []),
                    "current": page.get("current", False),
                })
            return pages
        except Exception as e:
            logging.debug("Error fetching rune pages: %s", e)
            return []

    async def _fetch_rune_styles_async(self) -> Dict[int, Dict[str, Any]]:
        """Fetch rune style metadata from the LCU keyed by style id."""
        if not self.connection:
            return {}
        try:
            response = await self.connection.request("get", EP_PERKS_STYLES)
            if not response or response.status != 200:
                return {}
            payload = await response.json()
            if not isinstance(payload, list):
                return {}
            styles: Dict[int, Dict[str, Any]] = {}
            for style in payload:
                if not isinstance(style, dict):
                    continue
                style_id = style.get("id", 0)
                if not style_id:
                    continue
                slots = style.get("slots", [])
                perks: List[Dict[str, Any]] = []
                for slot in slots if isinstance(slots, list) else []:
                    if not isinstance(slot, dict):
                        continue
                    for perk in slot.get("perks", []) if isinstance(slot.get("perks", []), list) else []:
                        if isinstance(perk, dict):
                            perks.append({
                                "id": perk.get("id", 0),
                                "name": str(perk.get("name") or ""),
                                "iconPath": str(perk.get("iconPath") or ""),
                            })
                styles[style_id] = {
                    "name": str(style.get("name") or ""),
                    "iconPath": str(style.get("iconPath") or ""),
                    "perks": perks,
                }
            return styles
        except Exception as e:
            logging.debug("Error fetching rune styles: %s", e)
            return {}

    def fetch_rune_pages(self) -> List[Dict[str, Any]]:
        """Synchronous wrapper to fetch rune pages from the LCU."""
        if not self.ws_active or not self.connection or not self.loop:
            return []
        future = asyncio.run_coroutine_threadsafe(self._fetch_rune_pages_async(), self.loop)
        try:
            return future.result(timeout=5)
        except Exception as e:
            logging.debug("WebSocket: rune pages fetch failed - %s", e)
            return []

    def fetch_rune_styles(self) -> Dict[int, Dict[str, Any]]:
        """Synchronous wrapper to fetch rune style metadata from the LCU."""
        if not self.ws_active or not self.connection or not self.loop:
            return {}
        future = asyncio.run_coroutine_threadsafe(self._fetch_rune_styles_async(), self.loop)
        try:
            return future.result(timeout=5)
        except Exception as e:
            logging.debug("WebSocket: rune styles fetch failed - %s", e)
            return {}

    async def _fetch_current_rune_page_async(self) -> Optional[Dict[str, Any]]:
        """GET /lol-perks/v1/currentpage — return the currently active rune page or None."""
        if not self.connection:
            return None
        try:
            response = await self.connection.request("get", EP_PERKS_CURRENT_PAGE)
            if not response or response.status != 200:
                return None
            payload = await response.json()
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception as e:
            logging.debug("Error fetching current rune page: %s", e)
            return None

    async def _set_rune_page_via_perks_async(self, page_data: Dict[str, Any]) -> bool:
        """PUT /lol-perks/v1/pages/{id} with full page data + current: true."""
        if not self.connection:
            return False
        page_id = page_data.get("id")
        if not page_id:
            return False
        try:
            payload = dict(page_data)
            payload["current"] = True
            endpoint = f"{EP_PERKS_PAGES}/{page_id}"
            self._log_lcu_request("RUNES", "put", endpoint, payload)
            response = await self.connection.request("put", endpoint, json=payload)
            self._log_lcu_response("RUNES", "put", endpoint, response)
            return bool(response and response.status < 400)
        except Exception as e:
            logging.warning("[RUNES] PUT /lol-perks/v1/pages/%s failed: %s", page_id, e)
            return False

    async def _create_rune_page_async(self, page_data: Dict[str, Any]) -> Optional[int]:
        """POST /lol-perks/v1/pages with current: true, return the new page id or None."""
        if not self.connection:
            return None
        try:
            payload = dict(page_data)
            payload.pop("id", None)
            payload["current"] = True
            self._log_lcu_request("RUNES", "post", EP_PERKS_PAGES, payload)
            response = await self.connection.request("post", EP_PERKS_PAGES, json=payload)
            self._log_lcu_response("RUNES", "post", EP_PERKS_PAGES, response)
            if response and response.status < 400:
                created = await response.json()
                return int(created.get("id") or 0) if isinstance(created, dict) else None
            return None
        except Exception as e:
            logging.warning("[RUNES] POST /lol-perks/v1/pages failed: %s", e)
            return None

    async def _delete_rune_page_async(self, page_id: int) -> bool:
        """DELETE /lol-perks/v1/pages/{id}."""
        if not self.connection or page_id <= 0:
            return False
        try:
            endpoint = f"{EP_PERKS_PAGES}/{page_id}"
            self._log_lcu_request("RUNES", "delete", endpoint)
            response = await self.connection.request("delete", endpoint)
            self._log_lcu_response("RUNES", "delete", endpoint, response)
            return bool(response and response.status < 400)
        except Exception as e:
            logging.warning("[RUNES] DELETE /lol-perks/v1/pages/%s failed: %s", page_id, e)
            return False

    def fetch_current_rune_page(self) -> Optional[Dict[str, Any]]:
        """Sync wrapper: get the current active rune page."""
        if not self.ws_active or not self.connection or not self.loop:
            return None
        future = asyncio.run_coroutine_threadsafe(self._fetch_current_rune_page_async(), self.loop)
        try:
            return future.result(timeout=5)
        except Exception as e:
            logging.debug("WebSocket: current rune page fetch failed - %s", e)
            return None

    def set_rune_page_via_perks(self, page_data: Dict[str, Any]) -> bool:
        """Sync wrapper: set a rune page as current via PUT."""
        if not self.ws_active or not self.connection or not self.loop:
            return False
        future = asyncio.run_coroutine_threadsafe(self._set_rune_page_via_perks_async(page_data), self.loop)
        try:
            return future.result(timeout=5)
        except Exception as e:
            logging.debug("WebSocket: set rune page via perks failed - %s", e)
            return False

    def create_rune_page(self, page_data: Dict[str, Any]) -> Optional[int]:
        """Sync wrapper: create a new rune page with current: true, return its id."""
        if not self.ws_active or not self.connection or not self.loop:
            return None
        future = asyncio.run_coroutine_threadsafe(self._create_rune_page_async(page_data), self.loop)
        try:
            return future.result(timeout=5)
        except Exception as e:
            logging.debug("WebSocket: create rune page failed - %s", e)
            return None

    def delete_rune_page(self, page_id: int) -> bool:
        """Sync wrapper: delete a rune page by id."""
        if not self.ws_active or not self.connection or not self.loop:
            return False
        future = asyncio.run_coroutine_threadsafe(self._delete_rune_page_async(page_id), self.loop)
        try:
            return future.result(timeout=5)
        except Exception as e:
            logging.debug("WebSocket: delete rune page failed - %s", e)
            return False

    def fetch_owned_skins_for_champion(self, champion_id: int) -> Dict[str, Any]:
        if not self.ws_active or not self.connection or not self.loop:
            return {
                "ok": False,
                "message": "Unable to fetch skins. Check your League of Legends connection.",
                "owned_skins": [],
            }
        future = asyncio.run_coroutine_threadsafe(self._fetch_owned_skins_for_champion(champion_id), self.loop)
        try:
            return future.result(timeout=8)
        except Exception as e:
            logging.debug("WebSocket: owned skins fetch failed - %s", e)
            return {
                "ok": False,
                "message": "Unable to fetch skins. Check your League of Legends connection.",
                "owned_skins": [],
            }

    @staticmethod
    def _inventory_skin_is_owned(item: Dict[str, Any]) -> bool:
        for field in ("owned", "isOwned", "unlocked", "isUnlocked", "purchased"):
            if item.get(field) is True:
                return True
            if item.get(field) is False:
                return False

        for field in ("purchaseable", "purchasable"):
            if item.get(field) is True:
                return False

        for field in ("ownershipType", "purchaseState", "status"):
            raw_value = item.get(field)
            if raw_value in {None, ""}:
                continue
            normalized = str(raw_value).strip().lower()
            if normalized in {"owned", "ownership_owned", "rental", "rent", "free_to_play", "freetoplay", "unlocked"}:
                return True
            if normalized in {"unowned", "not_owned", "locked", "purchasable", "purchaseable"}:
                return False

        nested_ownership = item.get("ownership")
        if isinstance(nested_ownership, dict):
            if nested_ownership.get("owned") is True or nested_ownership.get("isOwned") is True:
                return True
            if nested_ownership.get("owned") is False or nested_ownership.get("isOwned") is False:
                return False

        return True

    @staticmethod
    async def _read_response_text(response: Any) -> str:
        if not response:
            return ""
        try:
            return await response.text()
        except Exception:
            return ""

    def _resolve_owned_skin_entry(
        self,
        champion_name: str,
        *,
        skin_id: int = 0,
        skin_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        skin_data = None
        if skin_id > 0:
            skin_data = self.dd.resolve_skin_data(champion_name, skin_id=skin_id)
        if not skin_data and skin_name:
            skin_data = self.dd.resolve_skin_data(champion_name, skin_name=skin_name)
        return skin_data

    @staticmethod
    def _normalize_skin_collection_payload(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            payload = payload.get("skins") or payload.get("pickableSkins") or payload.get("inventory") or []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _build_owned_skin_result_entry(
        self,
        skin_data: Dict[str, Any],
        *,
        fallback_skin_id: int = 0,
        fallback_skin_name: str = "",
    ) -> Dict[str, Any]:
        return {
            "skin_id": int(skin_data.get("skin_id") or fallback_skin_id or 0),
            "skin_num": int(skin_data.get("skin_num") or 0),
            "skin_name": str(skin_data.get("skin_name") or fallback_skin_name or ""),
            "splash_url": skin_data.get("splash_url", ""),
            "tile_url": skin_data.get("tile_url", ""),
            "preview_url": (
                skin_data.get("tile_url")
                or skin_data.get("centered_splash_url")
                or skin_data.get("uncentered_splash_url")
                or skin_data.get("splash_url", "")
            ),
        }

    async def _fetch_owned_skins_from_inventory(
        self,
        champion_id: int,
        *,
        summoner_id: int,
    ) -> Dict[str, Any]:
        endpoint = f"/lol-champions/v1/inventories/{summoner_id}/champions/{champion_id}/skins"
        champion_name = self.dd.id_to_name(champion_id) or str(champion_id)
        try:
            response = await self.connection.request("get", endpoint)
            status = response.status if response else "no-response"
            logging.info(
                "[SKIN][OWNED] Inventory request endpoint=%s summoner_id=%s champion_id=%s status=%s",
                endpoint,
                summoner_id,
                champion_id,
                status,
            )
            if not response or response.status != 200:
                body = await self._read_response_text(response)
                logging.warning("[SKIN][OWNED] Inventory request failed: %s", body or "<empty>")
                return {
                    "ok": False,
                    "message": f"LCU inventory error {status}: {body or 'empty response'}",
                    "owned_skins": [],
                    "source": "inventory",
                }
            payload = await response.json()
        except Exception as e:
            logging.exception("[SKIN][OWNED] Inventory request exception for champion_id=%s", champion_id)
            return {
                "ok": False,
                "message": str(e),
                "owned_skins": [],
                "source": "inventory",
            }

        items = self._normalize_skin_collection_payload(payload)
        logging.info("[SKIN][OWNED] Inventory payload items=%s", len(items))
        owned_skins: List[Dict[str, Any]] = []
        unmapped_items = 0
        for item in items:
            if not self._inventory_skin_is_owned(item):
                continue
            try:
                skin_id = int(item.get("id") or item.get("skinId") or item.get("championSkinId") or 0)
            except (TypeError, ValueError):
                skin_id = 0
            skin_name = str(item.get("name") or item.get("displayName") or "")
            skin_data = self._resolve_owned_skin_entry(champion_name, skin_id=skin_id, skin_name=skin_name)
            if not skin_data:
                unmapped_items += 1
                logging.debug(
                    "[SKIN][OWNED] Inventory skin mapping failed champion=%s skin_id=%s skin_name=%s",
                    champion_name,
                    skin_id,
                    skin_name,
                )
                continue
            owned_skins.append(
                self._build_owned_skin_result_entry(
                    skin_data,
                    fallback_skin_id=skin_id,
                    fallback_skin_name=skin_name,
                )
            )

        unique_skins = []
        seen_ids = set()
        for skin in owned_skins:
            skin_id = int(skin.get("skin_id") or 0)
            if skin_id in seen_ids:
                continue
            seen_ids.add(skin_id)
            unique_skins.append(skin)
        logging.info(
            "[SKIN][OWNED] Inventory parsed champion=%s mapped=%s unmapped=%s",
            champion_name,
            len(unique_skins),
            unmapped_items,
        )
        return {
            "ok": True,
            "message": "",
            "owned_skins": unique_skins,
            "source": "inventory",
        }

    async def _fetch_owned_skins_from_pickable(self, champion_id: int) -> Dict[str, Any]:
        endpoint = "/lol-champ-select/v1/pickable-skins"
        champion_name = self.dd.id_to_name(champion_id) or str(champion_id)
        try:
            response = await self.connection.request("get", endpoint)
            status = response.status if response else "no-response"
            logging.info(
                "[SKIN][OWNED] Pickable fallback endpoint=%s champion_id=%s status=%s",
                endpoint,
                champion_id,
                status,
            )
            if not response or response.status != 200:
                body = await self._read_response_text(response)
                logging.warning("[SKIN][OWNED] Pickable fallback failed: %s", body or "<empty>")
                return {
                    "ok": False,
                    "message": f"LCU pickable error {status}: {body or 'empty response'}",
                    "owned_skins": [],
                    "source": "pickable",
                }
            payload = await response.json()
        except Exception as e:
            logging.debug("[SKIN][OWNED] Pickable fallback exception: %s", e)
            return {
                "ok": False,
                "message": str(e),
                "owned_skins": [],
                "source": "pickable",
            }

        items = self._normalize_skin_collection_payload(payload)
        logging.info("[SKIN][OWNED] Pickable fallback payload items=%s", len(items))
        owned_skins: List[Dict[str, Any]] = []
        unmapped_items = 0
        for item in items:
            try:
                item_champion_id = int(item.get("championId") or champion_id or 0)
            except (TypeError, ValueError):
                item_champion_id = champion_id
            if champion_id and item_champion_id != champion_id:
                continue
            try:
                skin_id = int(
                    item.get("id")
                    or item.get("skinId")
                    or item.get("championSkinId")
                    or item.get("selectedSkinId")
                    or 0
                )
            except (TypeError, ValueError):
                skin_id = 0
            skin_name = str(item.get("name") or item.get("displayName") or "")
            skin_data = self._resolve_owned_skin_entry(champion_name, skin_id=skin_id, skin_name=skin_name)
            if not skin_data:
                unmapped_items += 1
                logging.debug(
                    "[SKIN][OWNED] Pickable skin mapping failed champion=%s skin_id=%s skin_name=%s",
                    champion_name,
                    skin_id,
                    skin_name,
                )
                continue
            owned_skins.append(
                self._build_owned_skin_result_entry(
                    skin_data,
                    fallback_skin_id=skin_id,
                    fallback_skin_name=skin_name,
                )
            )

        unique_skins = []
        seen_ids = set()
        for skin in owned_skins:
            skin_id = int(skin.get("skin_id") or 0)
            if skin_id in seen_ids:
                continue
            seen_ids.add(skin_id)
            unique_skins.append(skin)
        logging.info(
            "[SKIN][OWNED] Pickable fallback parsed champion=%s mapped=%s unmapped=%s",
            champion_name,
            len(unique_skins),
            unmapped_items,
        )
        return {
            "ok": True,
            "message": "",
            "owned_skins": unique_skins,
            "source": "pickable",
        }

    async def _fetch_owned_skins_for_champion(self, champion_id: int) -> Dict[str, Any]:
        if not self.connection:
            return {
                "ok": False,
                "message": "Unable to fetch skins. Check your League of Legends connection.",
                "owned_skins": [],
            }
        summoner_id = self.get_current_summoner_id()
        if not summoner_id:
            await self._refresh_player_and_region()
            summoner_id = self.get_current_summoner_id()

        inventory_result = None
        if summoner_id:
            inventory_result = await self._fetch_owned_skins_from_inventory(champion_id, summoner_id=summoner_id)
            if inventory_result.get("ok") and inventory_result.get("owned_skins"):
                return inventory_result
        else:
            logging.warning("[SKIN][OWNED] Missing summoner_id for champion_id=%s", champion_id)

        logging.info(
            "[SKIN][OWNED] Falling back to pickable skins champion_id=%s inventory_ok=%s inventory_count=%s",
            champion_id,
            bool(inventory_result and inventory_result.get("ok")),
            len(inventory_result.get("owned_skins", [])) if inventory_result else 0,
        )
        pickable_result = await self._fetch_owned_skins_from_pickable(champion_id)
        if pickable_result.get("ok") and pickable_result.get("owned_skins"):
            return pickable_result
        if inventory_result and inventory_result.get("ok"):
            return inventory_result
        return pickable_result or {
            "ok": False,
            "message": "Unable to fetch skins. Check your League of Legends connection.",
            "owned_skins": [],
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

    def _reset_ws_runtime_state(self) -> None:
        """Clear per-connection runtime fields before a reconnect or final shutdown."""
        self.connection = None
        self.ws_active = False
        self.state.current_phase = "None"
        self.state.last_reported_summoner = None
        self.state.reset_between_games()

    def _notify_ws_disconnected(self, *, transient: bool, reason: str, status_message: Optional[str] = None) -> None:
        """Emit a structured disconnect event unless shutdown was explicitly requested."""
        if self._stop_event.is_set():
            return
        self._notify_ui(self.EVENT_DISCONNECTED, {"transient": transient, "reason": reason})
        if status_message:
            self._notify_ui(self.EVENT_STATUS, (status_message, "WARN"))

    def _is_transient_ws_scan_error(self, exc: BaseException) -> bool:
        transient_types: tuple[type[BaseException], ...] = (ProcessLookupError,)
        if psutil is not None:
            transient_types = transient_types + (
                psutil.NoSuchProcess,
                psutil.ZombieProcess,
                psutil.AccessDenied,
            )
        if isinstance(exc, transient_types):
            return True
        message = str(exc).strip().lower()
        return "process no longer exists" in message or "no such process" in message

    def _ws_loop(self) -> None:
        """Run the LCU connector in its own asyncio loop and forward LCU events to the UI thread."""
        if Connector is None:
            return

        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            while not self._stop_event.is_set():
                # Recreate the connector on every retry so a broken connection does
                # not leak stale event handlers or internal transport state.
                connector = Connector(loop=loop)
                self.connector = connector

                @connector.ready
                async def on_ready(connection):
                    """Store the live connection and refresh cached player context."""
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
                    """Reset local state and notify the UI that the client disappeared."""
                    self._reset_ws_runtime_state()
                    if not self._stop_event.is_set():
                        log_history_event(
                            "connection",
                            "LoL client connection lost, trying to reconnect.",
                            level="warning",
                            category="Connection",
                            action="disconnected",
                        )
                        self._notify_ws_disconnected(
                            transient=False,
                            reason="client_disconnected",
                            status_message="LoL client disconnected. Trying to reconnect...",
                        )
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
                    # Phase changes are the main trigger for match-flow automation.
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
                    # Session events can burst quickly; serialize ticks so the mixin
                    # never reads and writes champ-select state concurrently.
                    if self._cs_tick_lock.locked():
                        return
                    async with self._cs_tick_lock:
                        await self._champ_select_tick()

                @connector.ws.register(EP_SESSION_TIMER)
                async def _ws_cs_timer(connection, event):
                    # Timer polling is rate-limited because the LCU can emit frequent updates.
                    if time() - self.state._last_cs_timer_fetch > 0.2:
                        await self._champ_select_timer_tick()
                        self.state._last_cs_timer_fetch = time()

                try:
                    connector.start()
                    if self._stop_event.is_set():
                        break
                    logging.warning(
                        "[WS] Connector loop stopped unexpectedly. Retrying in %.1fs.",
                        self.WS_RETRY_DELAY_S,
                    )
                except Exception as e:
                    if self._stop_event.is_set():
                        break
                    self._reset_ws_runtime_state()
                    if self._is_transient_ws_scan_error(e):
                        logging.warning(
                            "[WS] Temporary LCU detection failure: %s. Retrying in %.1fs.",
                            e,
                            self.WS_RETRY_DELAY_S,
                        )
                        self._notify_ws_disconnected(
                            transient=True,
                            reason="lcu_process_scan_failed",
                            status_message="Temporary LCU detection failure. Waiting for League of Legends...",
                        )
                    else:
                        logging.critical("[WS] Critical error in the WebSocket loop: %s", e, exc_info=True)
                        self._notify_ws_disconnected(
                            transient=True,
                            reason="ws_loop_error",
                            status_message="LCU connection error. Trying to reconnect...",
                        )
                finally:
                    self.connector = None

                # Back off briefly between retries so the loop does not hammer process detection.
                if self._stop_event.wait(self.WS_RETRY_DELAY_S):
                    break
        finally:
            self._reset_ws_runtime_state()
            self.connector = None
            self.loop = None
            if loop is not None and not loop.is_closed():
                loop.close()

    async def _refresh_player_and_region(self) -> None:
        """Refresh detected Riot ID and routing data from whichever endpoint is currently available."""
        if not self.connection:
            return

        # Chat identity often exposes the canonical Riot ID earlier than the summoner endpoint.
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

        # Region routing can come from different client endpoints depending on the client state.
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
