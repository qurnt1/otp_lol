"""Champion select logic extracted from the LCU manager."""

import asyncio
import json
import logging
import random
from time import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from ..config import EP_PICKABLE, SUMMONER_SPELL_MAP

if TYPE_CHECKING:
    from .websocket import WebSocketManager


class ChampSelectMixin:
    """Mixin regroupant la logique de champ select et post-game."""

    SPELL_CONFIRM_RETRIES = 5
    SPELL_CONFIRM_DELAY_S = 0.18
    SPELL_RETRY_COOLDOWN_S = 0.45
    SKIN_CONFIRM_RETRIES = 4
    SKIN_CONFIRM_DELAY_S = 0.18
    SKIN_RETRY_COOLDOWN_S = 0.45
    PREPICK_RETRY_COOLDOWN_S = 0.5
    PREPICK_SOFT_TIMEOUT_S = 2.2
    ACTION_RETRY_COOLDOWN_S = 0.25

    @staticmethod
    def _format_debug_value(payload: Any, limit: int = 240) -> str:
        try:
            text = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        except TypeError:
            text = repr(payload)
        if len(text) > limit:
            return f"{text[:limit]}..."
        return text

    def _log_lcu_request(
        self: "WebSocketManager",
        area: str,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        suffix = ""
        if payload is not None:
            suffix = f" payload={self._format_debug_value(payload)}"
        logging.info("[%s] %s %s%s", area, method.upper(), endpoint, suffix)

    def _log_lcu_response(
        self: "WebSocketManager",
        area: str,
        method: str,
        endpoint: str,
        response: Any,
        *,
        body: Optional[Any] = None,
    ) -> None:
        status = getattr(response, "status", "no-response")
        suffix = ""
        if body is not None:
            suffix = f" body={self._format_debug_value(body)}"
        logging.info("[%s] %s %s -> %s%s", area, method.upper(), endpoint, status, suffix)

    def _log_flow_once(self: "WebSocketManager", message: str) -> None:
        if self.state.last_flow_note == message:
            return
        self.state.last_flow_note = message
        logging.info("[FLOW] %s", message)

    async def _fetch_pickable_ids(self: "WebSocketManager") -> Optional[Set[int]]:
        if not self.connection:
            return None
        try:
            response = await self.connection.request("get", EP_PICKABLE)
            if response.status == 200:
                payload = await response.json()
                if isinstance(payload, list):
                    return set(payload)
        except Exception as e:
            logging.debug("Error fetching pickable champions: %s", e)
        return None

    def _get_pick_priority(self: "WebSocketManager", params: Dict[str, Any]) -> List[tuple[str, str]]:
        effective = self._get_effective_champ_select_config(params)
        if not effective.get("presets_enabled", True):
            return []
        return [
            ("pick_1", effective.get("selected_pick_1", "")),
            ("pick_2", effective.get("selected_pick_2", "")),
            ("pick_3", effective.get("selected_pick_3", "")),
        ]

    def _get_viable_pick_candidates(
        self: "WebSocketManager",
        params: Dict[str, Any],
        pickable_ids: Optional[Set[int]],
        banned_ids: Optional[Set[int]] = None,
    ) -> List[tuple[str, str, int]]:
        banned_ids = banned_ids or set()
        candidates: List[tuple[str, str, int]] = []
        for slot_key, champion_name in self._get_pick_priority(params):
            if not champion_name:
                continue
            champion_id = self.dd.resolve_champion(champion_name)
            if not champion_id:
                logging.info("[PICK] Skipping %s on %s: unknown champion id.", champion_name, slot_key)
                continue
            if champion_id in banned_ids:
                logging.info("[PICK] Skipping %s (%s): champion is banned in the current session.", champion_name, champion_id)
                continue
            if pickable_ids is not None and champion_id not in pickable_ids:
                logging.info("[PICK] Skipping %s (%s): champion is not currently pickable.", champion_name, champion_id)
                continue
            candidates.append((slot_key, champion_name, champion_id))
        return candidates

    def _pick_first_viable_champion(
        self: "WebSocketManager",
        params: Dict[str, Any],
        pickable_ids: Optional[Set[int]],
        banned_ids: Optional[Set[int]] = None,
    ) -> Optional[tuple[str, str, int]]:
        candidates = self._get_viable_pick_candidates(params, pickable_ids, banned_ids)
        return candidates[0] if candidates else None

    def _resolve_pick_slot_from_champion_id(
        self: "WebSocketManager",
        params: Dict[str, Any],
        champion_id: int,
    ) -> tuple[Optional[str], Optional[str]]:
        for slot_key, champion_name in self._get_pick_priority(params):
            if not champion_name:
                continue
            if self.dd.resolve_champion(champion_name) == champion_id:
                return slot_key, champion_name
        return None, None

    def _can_hover_now(self: "WebSocketManager") -> bool:
        if self.state.time_left_ms <= 0:
            return True
        return self.state.time_left_ms > 900

    async def _champ_select_timer_tick(self: "WebSocketManager") -> None:
        if not self.connection:
            return

        timer = None
        resp = await self.connection.request("get", "/lol-champ-select/v1/session/timer")
        if resp.status != 200:
            resp = await self.connection.request("get", "/lol-champ-select-legacy/v1/session/timer")
        if resp.status == 200:
            timer = await resp.json()
        if isinstance(timer, dict):
            self.state.timer_phase = str(timer.get("phase") or "")
            raw_time_left = timer.get("adjustedTimeLeftInPhase")
            if raw_time_left is None:
                raw_time_left = timer.get("timeLeftInPhase")
            try:
                self.state.time_left_ms = int(raw_time_left or 0)
            except (TypeError, ValueError):
                self.state.time_left_ms = 0

    async def _champ_select_tick(self: "WebSocketManager") -> None:
        """Read the current champ-select session and perform the next safe automation step."""
        if not self.connection:
            return

        try:
            response = await self.connection.request("get", "/lol-champ-select/v1/session")
            if response.status != 200:
                return
            session = await response.json()
        except Exception as e:
            logging.debug("Error fetching champ select session: %s", e)
            return

        if session.get("benchEnabled") is True:
            return

        local_id = session.get("localPlayerCellId")
        if local_id is None:
            return

        params = self.get_params()

        if not self.state.assigned_position:
            my_team = session.get("myTeam", [])
            my_player_obj = next((p for p in my_team if p.get("cellId") == local_id), None)
            if my_player_obj:
                pos = (my_player_obj.get("assignedPosition") or "").upper()
                if pos:
                    self.state.assigned_position = pos
                    self._notify_ui(self.EVENT_STATUS, (f"Assigned role detected: {pos}", "ROLE"))

        actions_groups = session.get("actions", [])
        my_actions = []
        for group in actions_groups:
            for action in group:
                if action.get("actorCellId") == local_id and not action.get("completed"):
                    my_actions.append(action)

        effective = self._get_effective_champ_select_config(params)
        presets_enabled = bool(effective.get("presets_enabled", True))
        pickable_set = await self._fetch_pickable_ids()
        banned_ids = self._extract_banned_champion_ids(session)
        self._sync_prepick_state_from_session(session, params)

        prepick_action = next(
            (a for a in my_actions if a.get("type") == "pick" and not a.get("isInProgress")),
            None,
        )
        active_ban_action = next(
            (a for a in my_actions if a.get("type") == "ban" and a.get("isInProgress") is True),
            None,
        )
        active_pick_action = next(
            (a for a in my_actions if a.get("type") == "pick" and a.get("isInProgress") is True),
            None,
        )

        if params.get("auto_pick_enabled") and presets_enabled and effective.get("selected_pick_1"):
            if prepick_action:
                best_pick = self._pick_first_viable_champion(params, pickable_set, banned_ids)
                target_champion_id = best_pick[2] if best_pick else None
                current_hover = prepick_action.get("championId")
                if target_champion_id and current_hover != target_champion_id:
                    if time() - self.state.last_prepick_try_ts > self.PREPICK_RETRY_COOLDOWN_S and self._can_hover_now():
                        self.state.last_prepick_try_ts = time()
                        logging.info(
                            "[PREPICK] Action detected on id=%s before ban/pick resolution.",
                            prepick_action.get("id"),
                        )
                        hover_success = await self._hover_champion(prepick_action["id"], target_champion_id)
                        if not hover_success:
                            self._log_flow_once("Pre-pick hover was not confirmed; retry will stay active.")

        prepick_required = (
            params.get("auto_pick_enabled")
            and presets_enabled
            and effective.get("selected_pick_1")
            and prepick_action is not None
        )
        if prepick_required and not self.state.has_prepicked:
            if self.state.prepick_wait_started_ts <= 0:
                self.state.prepick_wait_started_ts = time()
            wait_elapsed = time() - self.state.prepick_wait_started_ts
            if wait_elapsed < self.PREPICK_SOFT_TIMEOUT_S:
                self._log_flow_once("Waiting for pre-pick confirmation before ban/pick actions.")
                return
            self._log_flow_once("Pre-pick confirmation timed out; continuing with ban/pick flow.")

        prepick_sequence_active = params.get("auto_pick_enabled") and presets_enabled and effective.get("selected_pick_1") and (
            prepick_required or (self.state.has_prepicked and not self.state.has_picked)
        )
        prepick_slot = self.state.last_prepick_slot or self.state.last_locked_pick_slot or "pick_1"
        if params.get("auto_summoners_enabled") and presets_enabled and prepick_sequence_active:
            if not self._selection_has_expected_spells(session, params, slot_key=prepick_slot):
                self._log_flow_once(
                    f"Pre-pick summs are not confirmed on {prepick_slot}; retries continue without blocking ban/pick."
                )
                self._ensure_spells_are_applied(session, params, slot_key=prepick_slot)

        if active_ban_action and params.get("auto_ban_enabled"):
            await self._logic_do_ban(active_ban_action, effective)
        elif active_pick_action and params.get("auto_pick_enabled") and presets_enabled:
            await self._logic_do_pick(active_pick_action, params, pickable_set, banned_ids)

        if self.state.has_picked and params.get("auto_summoners_enabled") and presets_enabled:
            self._ensure_spells_are_applied(session, params)
        if self.state.has_picked and presets_enabled:
            self._ensure_skin_is_applied(session, params)

    async def _hover_champion(self: "WebSocketManager", action_id: int, champion_id: int) -> bool:
        area = "PREPICK"
        url = f"/lol-champ-select/v1/session/actions/{action_id}"
        champion_name = self.dd.id_to_name(champion_id) or str(champion_id)
        payload = {"championId": champion_id}
        self._log_lcu_request(area, "patch", url, payload)
        response = await self.connection.request("patch", url, json=payload)
        self._log_lcu_response(area, "patch", url, response)
        success = bool(response and response.status < 400)
        if success:
            self.state.last_flow_note = ""
            self._log_history(
                "hover",
                f"Pre-pick sent for {champion_name}.",
                {"champion": champion_name},
                category="Champion Select",
                action="hover",
            )
        else:
            logging.warning("[PREPICK] Hover request was rejected for %s (%s).", champion_name, champion_id)
        return success

    async def _logic_do_ban(self: "WebSocketManager", action: Dict[str, Any], effective: Dict[str, Any]) -> None:
        selected_ban = effective.get("selected_ban")
        if not selected_ban:
            return
        if selected_ban in {
            effective.get("selected_pick_1"),
            effective.get("selected_pick_2"),
            effective.get("selected_pick_3"),
        }:
            logging.warning("Auto-ban ignored: the banned champion is also configured as a pick.")
            return
        if time() - self.state.last_ban_try_ts < self.ACTION_RETRY_COOLDOWN_S:
            return
        self.state.last_ban_try_ts = time()

        champion_id = self.dd.resolve_champion(selected_ban)
        if not champion_id:
            return

        self._log_flow_once(f"Ban turn active; trying {selected_ban} ({champion_id}).")
        success = await self._lock_in_champion(action["id"], champion_id, action_type="ban")
        if success:
            self.state.has_banned = True
            self.state.last_flow_note = ""
            self._log_history(
                "ban",
                f"Automatic ban confirmed on {selected_ban}.",
                {"champion": selected_ban},
                level="success",
                category="Champion Select",
                action="ban",
            )
            self._notify_ui(self.EVENT_CHAMPION_BANNED, selected_ban)
            self._notify_ui(self.EVENT_STATUS, (f"Ban confirmed: {selected_ban}.", "BAN"))
            return

        self._log_flow_once(f"Ban was not confirmed for {selected_ban}; retry will continue while the action stays active.")

    async def _logic_do_pick(
        self: "WebSocketManager",
        action: Dict[str, Any],
        params: Dict[str, Any],
        pickable_set: Optional[Set[int]] = None,
        banned_ids: Optional[Set[int]] = None,
    ) -> None:
        if time() - self.state.last_pick_try_ts < self.ACTION_RETRY_COOLDOWN_S:
            return
        self.state.last_pick_try_ts = time()
        if pickable_set is None:
            pickable_set = await self._fetch_pickable_ids()
        viable_picks = self._get_viable_pick_candidates(params, pickable_set, banned_ids)
        if not viable_picks:
            if pickable_set is None:
                self._notify_ui(self.EVENT_STATUS, ("Unable to check pickable champions right now.", "WARN"))
            else:
                self._notify_ui(
                    self.EVENT_STATUS,
                    ("No configured champion is available (or all are banned).", "WARN"),
                )
            return

        for slot_key, champion_name, champion_id in viable_picks:
            self._log_flow_once(f"Pick turn active; trying {champion_name} from {slot_key}.")
            success = await self._lock_in_champion(action["id"], champion_id, action_type="pick")
            if success:
                self.state.has_picked = True
                self.state.last_locked_pick_slot = slot_key
                self.state.last_flow_note = ""
                self._log_history(
                    "pick",
                    f"Champion automatically locked in: {champion_name}.",
                    {"champion": champion_name},
                    level="success",
                    category="Champion Select",
                    action="pick",
                )
                self._notify_ui(self.EVENT_CHAMPION_PICKED, champion_name)
                self._notify_ui(self.EVENT_STATUS, (f"{champion_name} locked in. Ready to play.", "PICK"))
                if params.get("auto_summoners_enabled"):
                    asyncio.create_task(self._set_spells(params, slot_key=slot_key))
                asyncio.create_task(self._set_skin(params, slot_key=slot_key))
                return

            logging.warning(
                "[PICK] Lock was not confirmed for %s (%s) on %s; trying the next configured preset if available.",
                champion_name,
                champion_id,
                slot_key,
            )

        self._notify_ui(
            self.EVENT_STATUS,
            ("No configured champion could be confirmed on this pick action; retry scheduled.", "WARN"),
        )
        self._log_flow_once("Pick action failed for all viable presets; retries will continue while the action stays active.")

    def _resolve_spell_selection(
        self: "WebSocketManager",
        params: Dict[str, Any],
        slot_key: Optional[str] = None,
    ) -> tuple[str, str, int, int, str]:
        effective = self.get_effective_profile_config(params=params)
        chosen_slot = slot_key or self.state.last_locked_pick_slot or "pick_1"
        pick_slots = effective.get("pick_slots", {})
        slot_data = pick_slots.get(chosen_slot, {}) if isinstance(pick_slots, dict) else {}
        fallback_slot = pick_slots.get("pick_1", {}) if isinstance(pick_slots, dict) else {}
        spell1_name = slot_data.get("spell_1") or fallback_slot.get("spell_1") or "Heal"
        spell2_name = slot_data.get("spell_2") or fallback_slot.get("spell_2") or "Flash"
        spell1_name = "(None)" if spell1_name == "(Aucun)" else spell1_name
        spell2_name = "(None)" if spell2_name == "(Aucun)" else spell2_name
        spell1_id = SUMMONER_SPELL_MAP.get(spell1_name, 7)
        spell2_id = SUMMONER_SPELL_MAP.get(spell2_name, 4)
        return spell1_name, spell2_name, spell1_id, spell2_id, chosen_slot

    def _resolve_skin_selection(
        self: "WebSocketManager",
        params: Dict[str, Any],
        slot_key: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, Any]], str]:
        effective = self.get_effective_profile_config(params=params)
        chosen_slot = slot_key or self.state.last_locked_pick_slot or "pick_1"
        pick_slots = effective.get("pick_slots", {})
        slot_data = pick_slots.get(chosen_slot, {}) if isinstance(pick_slots, dict) else {}
        fallback_slot = pick_slots.get("pick_1", {}) if isinstance(pick_slots, dict) else {}
        champion_name = slot_data.get("champion") or fallback_slot.get("champion") or effective.get("selected_pick_1", "")
        if not champion_name:
            return None, chosen_slot

        skin_mode = str(slot_data.get("skin_mode") or fallback_slot.get("skin_mode") or "none").strip().lower()
        if skin_mode not in {"fixed", "random"}:
            return None, chosen_slot

        if skin_mode == "fixed":
            return (
                {
                    "mode": "fixed",
                    "champion_name": champion_name,
                    "skin_id": int(slot_data.get("skin_id") or fallback_slot.get("skin_id") or 0),
                    "skin_name": slot_data.get("skin_name") or fallback_slot.get("skin_name") or "",
                    "skin_num": int(slot_data.get("skin_num") or fallback_slot.get("skin_num") or 0),
                    "skin_source_role": slot_data.get("skin_source_role") or fallback_slot.get("skin_source_role") or "GLOBAL",
                },
                chosen_slot,
            )

        return (
            {
                "mode": "random",
                "champion_name": champion_name,
                "skin_id": int(slot_data.get("random_skin_id") or fallback_slot.get("random_skin_id") or 0),
                "skin_name": slot_data.get("random_skin_name") or fallback_slot.get("random_skin_name") or "",
                "skin_num": int(slot_data.get("random_skin_num") or fallback_slot.get("random_skin_num") or 0),
                "random_skin_pool": slot_data.get("random_skin_pool") or fallback_slot.get("random_skin_pool") or [],
                "skin_source_role": slot_data.get("skin_source_role") or fallback_slot.get("skin_source_role") or "GLOBAL",
            },
            chosen_slot,
        )

    @staticmethod
    def _choose_random_skin_entry(
        skins: List[Dict[str, Any]],
        *,
        exclude_skin_id: int = 0,
    ) -> Optional[Dict[str, Any]]:
        pool = [skin for skin in skins if int(skin.get("skin_id") or 0) != int(exclude_skin_id or 0)] or skins
        return random.choice(pool) if pool else None

    def _build_random_skin_pool_candidates(
        self: "WebSocketManager",
        pool: List[Dict[str, Any]],
        pickable_skins: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not pool:
            return []
        pickable_by_id = {int(entry.get("skin_id") or 0): entry for entry in pickable_skins}
        candidates: List[Dict[str, Any]] = []
        seen_ids: Set[int] = set()
        for entry in pool:
            if not isinstance(entry, dict):
                continue
            skin_id = int(entry.get("skin_id") or 0)
            if skin_id <= 0 or skin_id in seen_ids:
                continue
            seen_ids.add(skin_id)
            if pickable_by_id:
                resolved = pickable_by_id.get(skin_id)
                if not resolved:
                    continue
                candidates.append(dict(resolved))
                continue
            candidates.append(
                {
                    "skin_id": skin_id,
                    "skin_name": str(entry.get("skin_name") or ""),
                    "skin_num": int(entry.get("skin_num") or 0),
                }
            )
        return candidates

    def _extract_local_player_selection(
        self: "WebSocketManager",
        session: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(session, dict):
            return None
        local_id = session.get("localPlayerCellId")
        if local_id is None:
            return None
        my_team = session.get("myTeam", [])
        return next((player for player in my_team if player.get("cellId") == local_id), None)

    def _build_selection_debug_snapshot(self, session: Dict[str, Any]) -> Dict[str, Any]:
        my_team = session.get("myTeam", [])
        compact_team = []
        for player in my_team:
            compact_team.append(
                {
                    "cellId": player.get("cellId"),
                    "championId": player.get("championId"),
                    "assignedPosition": player.get("assignedPosition"),
                    "spell1Id": player.get("spell1Id"),
                    "spell2Id": player.get("spell2Id"),
                }
            )
        return {
            "localPlayerCellId": session.get("localPlayerCellId"),
            "myTeam": compact_team,
        }

    def _iter_session_actions(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for group in session.get("actions", []):
            for action in group:
                if isinstance(action, dict):
                    actions.append(action)
        return actions

    def _extract_banned_champion_ids(self, session: Optional[Dict[str, Any]]) -> Set[int]:
        if not isinstance(session, dict):
            return set()

        banned_ids: Set[int] = set()
        for action in self._iter_session_actions(session):
            if action.get("type") != "ban" or action.get("completed") is not True:
                continue
            champion_id = int(action.get("championId") or 0)
            if champion_id > 0:
                banned_ids.add(champion_id)

        bans_block = session.get("bans")
        if isinstance(bans_block, dict):
            for key in ("myTeamBans", "theirTeamBans"):
                values = bans_block.get(key, [])
                if isinstance(values, list):
                    for champion_id in values:
                        try:
                            champion_id = int(champion_id or 0)
                        except (TypeError, ValueError):
                            champion_id = 0
                        if champion_id > 0:
                            banned_ids.add(champion_id)
        return banned_ids

    def _sync_prepick_state_from_session(
        self: "WebSocketManager",
        session: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> bool:
        local_selection = self._extract_local_player_selection(session)
        if not local_selection:
            return False
        champion_id = int(local_selection.get("championId") or 0)
        if champion_id <= 0:
            return False

        slot_key, champion_name = self._resolve_pick_slot_from_champion_id(params, champion_id)
        if not slot_key or not champion_name:
            return False

        was_confirmed = self.state.has_prepicked and self.state.last_prepick_slot == slot_key
        self.state.has_prepicked = True
        self.state.last_prepick_slot = slot_key
        self.state.prepick_wait_started_ts = 0.0
        self.state.last_flow_note = ""
        if not was_confirmed:
            logging.info(
                "[PREPICK] Session confirms champion %s (%s) on %s.",
                champion_name,
                champion_id,
                slot_key,
            )
        return True

    def _selection_has_expected_spells(
        self: "WebSocketManager",
        session: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        *,
        slot_key: Optional[str] = None,
    ) -> bool:
        local_selection = self._extract_local_player_selection(session)
        if not local_selection:
            return False
        _, _, spell1_id, spell2_id, _ = self._resolve_spell_selection(params, slot_key=slot_key)
        return (
            int(local_selection.get("spell1Id") or 0) == spell1_id
            and int(local_selection.get("spell2Id") or 0) == spell2_id
        )

    async def _fetch_current_champ_select_session(
        self: "WebSocketManager",
        *,
        area: str = "SPELLS",
        include_actions: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not self.connection:
            return None
        try:
            endpoint = "/lol-champ-select/v1/session"
            self._log_lcu_request(area, "get", endpoint)
            response = await self.connection.request("get", endpoint)
            if response and response.status == 200:
                payload = await response.json()
                if isinstance(payload, dict):
                    body = self._build_selection_debug_snapshot(payload)
                    if include_actions:
                        body["actions"] = [
                            {
                                "id": action.get("id"),
                                "actorCellId": action.get("actorCellId"),
                                "type": action.get("type"),
                                "completed": action.get("completed"),
                                "isInProgress": action.get("isInProgress"),
                                "championId": action.get("championId"),
                            }
                            for action in self._iter_session_actions(payload)
                        ]
                    self._log_lcu_response(
                        area,
                        "get",
                        endpoint,
                        response,
                        body=body,
                    )
                    return payload

            endpoint = "/lol-champ-select-legacy/v1/session"
            self._log_lcu_request(area, "get", endpoint)
            response = await self.connection.request("get", endpoint)
            if response and response.status == 200:
                payload = await response.json()
                if isinstance(payload, dict):
                    body = self._build_selection_debug_snapshot(payload)
                    if include_actions:
                        body["actions"] = [
                            {
                                "id": action.get("id"),
                                "actorCellId": action.get("actorCellId"),
                                "type": action.get("type"),
                                "completed": action.get("completed"),
                                "isInProgress": action.get("isInProgress"),
                                "championId": action.get("championId"),
                            }
                            for action in self._iter_session_actions(payload)
                        ]
                    self._log_lcu_response(
                        area,
                        "get",
                        endpoint,
                        response,
                        body=body,
                    )
                    return payload
        except Exception as e:
            logging.warning("[%s] Unable to fetch champ-select session for confirmation: %s", area, e)
        return None

    async def _confirm_action_completed_from_session(
        self: "WebSocketManager",
        action_id: int,
        champion_id: int,
        *,
        action_type: str,
    ) -> bool:
        area = action_type.upper()
        for attempt in range(self.SPELL_CONFIRM_RETRIES + 1):
            url_action = f"/lol-champ-select/v1/session/actions/{action_id}"
            self._log_lcu_request(area, "get", url_action)
            confirmation = await self.connection.request("get", url_action)
            if confirmation and confirmation.status == 200:
                payload = await confirmation.json()
                self._log_lcu_response(area, "get", url_action, confirmation, body=payload)
                if payload.get("championId") == champion_id and payload.get("completed") is True:
                    return True
                logging.warning(
                    "[%s] Action endpoint mismatch for action=%s expected championId=%s completed=True, got %s.",
                    area,
                    action_id,
                    champion_id,
                    self._format_debug_value(
                        {
                            "championId": payload.get("championId"),
                            "completed": payload.get("completed"),
                        }
                    ),
                )
            else:
                logging.info(
                    "[%s] Action endpoint unavailable for action=%s; checking session snapshot fallback.",
                    area,
                    action_id,
                )

            session = await self._fetch_current_champ_select_session(area=area, include_actions=True)
            if isinstance(session, dict):
                action_payload = next(
                    (action for action in self._iter_session_actions(session) if action.get("id") == action_id),
                    None,
                )
                if (
                    isinstance(action_payload, dict)
                    and action_payload.get("championId") == champion_id
                    and action_payload.get("completed") is True
                ):
                    logging.info(
                        "[%s] Session actions confirm action=%s championId=%s type=%s.",
                        area,
                        action_id,
                        champion_id,
                        action_type,
                    )
                    return True
            if attempt < self.SPELL_CONFIRM_RETRIES:
                await asyncio.sleep(self.SPELL_CONFIRM_DELAY_S)
        return False

    async def _confirm_spells_applied(
        self: "WebSocketManager",
        spell1_id: int,
        spell2_id: int,
    ) -> bool:
        for attempt in range(self.SPELL_CONFIRM_RETRIES + 1):
            session = await self._fetch_current_champ_select_session(area="SPELLS")
            local_selection = self._extract_local_player_selection(session)
            if local_selection:
                current_spell1 = int(local_selection.get("spell1Id") or 0)
                current_spell2 = int(local_selection.get("spell2Id") or 0)
                logging.info(
                    "[SPELLS] Confirmation %s/%s current=(%s,%s) expected=(%s,%s)",
                    attempt + 1,
                    self.SPELL_CONFIRM_RETRIES + 1,
                    current_spell1,
                    current_spell2,
                    spell1_id,
                    spell2_id,
                )
                if current_spell1 == spell1_id and current_spell2 == spell2_id:
                    return True
            if attempt < self.SPELL_CONFIRM_RETRIES:
                await asyncio.sleep(self.SPELL_CONFIRM_DELAY_S)
        return False

    def _ensure_spells_are_applied(
        self: "WebSocketManager",
        session: Dict[str, Any],
        params: Dict[str, Any],
        slot_key: Optional[str] = None,
    ) -> None:
        if self.state.spell_apply_in_progress or not self.connection:
            return
        local_selection = self._extract_local_player_selection(session)
        if not local_selection:
            return
        _, _, spell1_id, spell2_id, chosen_slot = self._resolve_spell_selection(params, slot_key=slot_key)
        self.state.desired_spell_ids = (spell1_id, spell2_id)
        current_spell1 = int(local_selection.get("spell1Id") or 0)
        current_spell2 = int(local_selection.get("spell2Id") or 0)
        if (current_spell1, current_spell2) == (spell1_id, spell2_id):
            self.state.last_confirmed_spell_ids = (spell1_id, spell2_id)
            return
        if time() - self.state.last_spell_try_ts < self.SPELL_RETRY_COOLDOWN_S:
            return
        logging.info(
            "[SPELLS] Mismatch detected for %s: current=(%s,%s) expected=(%s,%s). Retrying.",
            chosen_slot,
            current_spell1,
            current_spell2,
            spell1_id,
            spell2_id,
        )
        asyncio.create_task(self._set_spells(params, slot_key=chosen_slot))

    async def _fetch_pickable_skins(
        self: "WebSocketManager",
        champion_id: int,
    ) -> List[Dict[str, Any]]:
        if not self.connection:
            return []
        try:
            response = await self.connection.request("get", "/lol-champ-select/v1/pickable-skins")
            if not response or response.status != 200:
                return []
            payload = await response.json()
        except Exception as e:
            logging.debug("[SKIN] Unable to fetch pickable skins: %s", e)
            return []

        if isinstance(payload, dict):
            payload = payload.get("skins") or payload.get("pickableSkins") or []
        if not isinstance(payload, list):
            return []

        skins: List[Dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            raw_champion_id = item.get("championId")
            try:
                item_champion_id = int(raw_champion_id or champion_id or 0)
            except (TypeError, ValueError):
                item_champion_id = champion_id
            if champion_id and raw_champion_id not in {None, ""} and item_champion_id != champion_id:
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
            skin_data = self.dd.resolve_skin_data(champion_id, skin_id=skin_id, skin_name=skin_name)
            if not skin_data:
                continue
            skins.append(
                {
                    "skin_id": int(skin_data.get("skin_id") or skin_id or 0),
                    "skin_num": int(skin_data.get("skin_num") or 0),
                    "skin_name": str(skin_data.get("skin_name") or skin_name or ""),
                    "splash_url": skin_data.get("splash_url", ""),
                }
            )

        unique_skins: List[Dict[str, Any]] = []
        seen_ids = set()
        for skin in skins:
            skin_id = int(skin.get("skin_id") or 0)
            if skin_id in seen_ids:
                continue
            seen_ids.add(skin_id)
            unique_skins.append(skin)
        return unique_skins

    async def _confirm_skin_applied(self: "WebSocketManager", skin_id: int) -> bool:
        for attempt in range(self.SKIN_CONFIRM_RETRIES + 1):
            session = await self._fetch_current_champ_select_session(area="SKIN")
            local_selection = self._extract_local_player_selection(session)
            if local_selection:
                current_skin_id = int(local_selection.get("selectedSkinId") or 0)
                logging.info(
                    "[SKIN] Confirmation %s/%s current=%s expected=%s",
                    attempt + 1,
                    self.SKIN_CONFIRM_RETRIES + 1,
                    current_skin_id,
                    skin_id,
                )
                if current_skin_id == skin_id:
                    return True
            if attempt < self.SKIN_CONFIRM_RETRIES:
                await asyncio.sleep(self.SKIN_CONFIRM_DELAY_S)
        return False

    def _selection_has_expected_skin(
        self: "WebSocketManager",
        session: Optional[Dict[str, Any]],
        params: Dict[str, Any],
        *,
        slot_key: Optional[str] = None,
    ) -> bool:
        local_selection = self._extract_local_player_selection(session)
        if not local_selection:
            return False
        skin_selection, _ = self._resolve_skin_selection(params, slot_key=slot_key)
        if not skin_selection or int(skin_selection.get("skin_id") or 0) <= 0:
            return True
        return int(local_selection.get("selectedSkinId") or 0) == int(skin_selection.get("skin_id") or 0)

    def _ensure_skin_is_applied(
        self: "WebSocketManager",
        session: Dict[str, Any],
        params: Dict[str, Any],
        slot_key: Optional[str] = None,
    ) -> None:
        if self.state.skin_apply_in_progress or not self.connection:
            return
        local_selection = self._extract_local_player_selection(session)
        if not local_selection:
            return
        skin_selection, chosen_slot = self._resolve_skin_selection(params, slot_key=slot_key)
        if not skin_selection:
            return
        desired_skin_id = int(skin_selection.get("skin_id") or 0)
        if desired_skin_id <= 0 and skin_selection.get("mode") != "random":
            return
        self.state.desired_skin_id = desired_skin_id or None
        current_skin_id = int(local_selection.get("selectedSkinId") or 0)
        if desired_skin_id > 0 and current_skin_id == desired_skin_id:
            self.state.last_confirmed_skin_id = desired_skin_id
            return
        if time() - self.state.last_skin_try_ts < self.SKIN_RETRY_COOLDOWN_S:
            return
        logging.info(
            "[SKIN] Mismatch detected for %s: current=%s expected=%s. Retrying.",
            chosen_slot,
            current_skin_id,
            desired_skin_id or "random",
        )
        asyncio.create_task(self._set_skin(params, slot_key=chosen_slot))

    def _persist_random_skin_preview(
        self: "WebSocketManager",
        slot_key: str,
        *,
        source_role: str,
        skin: Dict[str, Any],
    ) -> None:
        if not self.update_param:
            return

        if source_role not in {"GLOBAL", "TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}:
            source_role = "GLOBAL"

        if source_role == "GLOBAL":
            params = self.get_params()
            pick_slots = params.get("pick_slots", {})
            if not isinstance(pick_slots, dict):
                pick_slots = {}
            new_slots = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in pick_slots.items()}
            slot_data = new_slots.get(slot_key, {})
            slot_data.update(
                {
                    "skin_mode": "random",
                    "skin_id": 0,
                    "skin_name": "",
                    "skin_num": 0,
                    "random_skin_id": int(skin.get("skin_id") or 0),
                    "random_skin_name": str(skin.get("skin_name") or ""),
                    "random_skin_num": int(skin.get("skin_num") or 0),
                }
            )
            new_slots[slot_key] = slot_data
            self.update_param("pick_slots", new_slots)
            return

        params = self.get_params()
        role_profiles = params.get("role_profiles", {})
        if not isinstance(role_profiles, dict):
            role_profiles = {}
        new_profiles = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in role_profiles.items()}
        role_data = new_profiles.get(source_role, {})
        pick_slots = role_data.get("pick_slots", {})
        if not isinstance(pick_slots, dict):
            pick_slots = {}
        new_slots = {name: (data.copy() if isinstance(data, dict) else {}) for name, data in pick_slots.items()}
        slot_data = new_slots.get(slot_key, {})
        slot_data.update(
            {
                "skin_mode": "random",
                "skin_id": 0,
                "skin_name": "",
                "skin_num": 0,
                "random_skin_id": int(skin.get("skin_id") or 0),
                "random_skin_name": str(skin.get("skin_name") or ""),
                "random_skin_num": int(skin.get("skin_num") or 0),
            }
        )
        new_slots[slot_key] = slot_data
        role_data["pick_slots"] = new_slots
        new_profiles[source_role] = role_data
        self.update_param("role_profiles", new_profiles)

    async def _lock_in_champion(
        self: "WebSocketManager",
        action_id: int,
        champion_id: int,
        *,
        action_type: str = "pick",
    ) -> bool:
        """Hover then lock a champion, with confirmation because the LCU can accept partial updates."""
        area = action_type.upper()
        url_action = f"/lol-champ-select/v1/session/actions/{action_id}"
        champion_name = self.dd.id_to_name(champion_id) or str(champion_id)
        hover_payload = {"championId": champion_id}
        patch_payload = {"championId": champion_id, "completed": True}

        logging.info("[%s] Starting lock flow for %s (%s) on action %s.", area, champion_name, champion_id, action_id)
        self._log_lcu_request(area, "patch", url_action, hover_payload)
        hover_response = await self.connection.request("patch", url_action, json=hover_payload)
        self._log_lcu_response(area, "patch", url_action, hover_response)
        if not hover_response or hover_response.status >= 400:
            logging.warning("[%s] Hover patch rejected for %s (%s).", area, champion_name, champion_id)
            return False

        await asyncio.sleep(0.05)

        self._log_lcu_request(area, "patch", url_action, patch_payload)
        patch_response = await self.connection.request("patch", url_action, json=patch_payload)
        self._log_lcu_response(area, "patch", url_action, patch_response)
        if not patch_response or patch_response.status >= 400:
            logging.warning("[%s] Complete patch was rejected for %s (%s).", area, champion_name, champion_id)
        elif await self._confirm_action_completed_from_session(action_id, champion_id, action_type=action_type):
            return True

        complete_url = f"{url_action}/complete"
        self._log_lcu_request(area, "post", complete_url)
        response = await self.connection.request("post", complete_url)
        self._log_lcu_response(area, "post", complete_url, response)
        if not response or response.status >= 400:
            logging.warning("[%s] /complete request failed for %s (%s).", area, champion_name, champion_id)

        confirmed = await self._confirm_action_completed_from_session(action_id, champion_id, action_type=action_type)
        if not confirmed:
            logging.warning(
                "[%s] Final confirmation fallback failed for %s (%s) after checking action and session state.",
                area,
                champion_name,
                champion_id,
            )
        return confirmed

    async def _set_spells(self: "WebSocketManager", params: Dict[str, Any], slot_key: Optional[str] = None) -> None:
        if not self.connection or self.state.spell_apply_in_progress:
            return

        self.state.spell_apply_in_progress = True
        spell1_name, spell2_name, spell1_id, spell2_id, chosen_slot = self._resolve_spell_selection(
            params,
            slot_key=slot_key,
        )
        payload = {"spell1Id": spell1_id, "spell2Id": spell2_id}
        self.state.desired_spell_ids = (spell1_id, spell2_id)
        self.state.last_spell_try_ts = time()
        effective = self.get_effective_profile_config(params=params)
        logging.info(
            "[SPELLS] Applying %s for %s: %s(%s) + %s(%s).",
            chosen_slot,
            effective.get("resolved_role", "GLOBAL"),
            spell1_name,
            spell1_id,
            spell2_name,
            spell2_id,
        )

        try:
            for endpoint in (
                "/lol-champ-select/v1/session/my-selection",
                "/lol-champ-select-legacy/v1/session/my-selection",
            ):
                try:
                    self._log_lcu_request("SPELLS", "patch", endpoint, payload)
                    response = await self.connection.request("patch", endpoint, json=payload)
                except Exception as e:
                    logging.warning("[SPELLS] Patch request failed on %s: %s", endpoint, e)
                    response = None

                self._log_lcu_response("SPELLS", "patch", endpoint, response)
                if response and response.status < 400 and await self._confirm_spells_applied(spell1_id, spell2_id):
                    previous_confirmed = self.state.last_confirmed_spell_ids
                    self.state.last_confirmed_spell_ids = (spell1_id, spell2_id)
                    if previous_confirmed != (spell1_id, spell2_id):
                        self._log_history(
                            "spells",
                            f"Automatic summs applied: {spell1_name} + {spell2_name}.",
                            {
                                "spell_1": spell1_name,
                                "spell_2": spell2_name,
                                "role": effective.get("resolved_role", "GLOBAL"),
                                "pick_slot": chosen_slot,
                                "endpoint": endpoint,
                            },
                            level="success",
                            category="Summs",
                            action="set",
                        )
                        self._notify_ui(self.EVENT_SPELLS_SET, (spell1_name, spell2_name))
                        self._notify_ui(
                            self.EVENT_STATUS,
                            (f"Summs auto-selected: {spell1_name} + {spell2_name}.", "SUMMS"),
                        )
                    logging.info("[SPELLS] Confirmed on %s for %s.", endpoint, chosen_slot)
                    return

            logging.warning(
                "[SPELLS] Unable to confirm summoner spells for %s after patch attempts. Expected (%s,%s).",
                chosen_slot,
                spell1_id,
                spell2_id,
            )
            self._notify_ui(
                self.EVENT_STATUS,
                (f"Summs not confirmed yet for {chosen_slot}; retry will continue if possible.", "WARN"),
            )
        finally:
            self.state.spell_apply_in_progress = False

    async def _set_skin(self: "WebSocketManager", params: Dict[str, Any], slot_key: Optional[str] = None) -> None:
        if not self.connection or self.state.skin_apply_in_progress:
            return

        skin_selection, chosen_slot = self._resolve_skin_selection(params, slot_key=slot_key)
        if not skin_selection:
            return

        session = await self._fetch_current_champ_select_session(area="SKIN")
        local_selection = self._extract_local_player_selection(session)
        if not local_selection:
            return

        champion_id = int(local_selection.get("championId") or 0)
        if champion_id <= 0:
            return

        self.state.skin_apply_in_progress = True
        effective = self.get_effective_profile_config(params=params)
        selected_skin = dict(skin_selection)
        try:
            pickable_skins: List[Dict[str, Any]] = []
            if selected_skin.get("mode") == "random":
                pickable_skins = await self._fetch_pickable_skins(champion_id)
                pool_candidates = self._build_random_skin_pool_candidates(
                    list(selected_skin.get("random_skin_pool") or []),
                    pickable_skins,
                )
                if int(selected_skin.get("skin_id") or 0) <= 0:
                    selected_skin = self._choose_random_skin_entry(pool_candidates) or selected_skin
                if int(selected_skin.get("skin_id") or 0) <= 0:
                    return

            skin_id = int(selected_skin.get("skin_id") or 0)
            if skin_id <= 0:
                return

            self.state.desired_skin_id = skin_id
            self.state.last_skin_try_ts = time()
            payload = {"selectedSkinId": skin_id}
            logging.info(
                "[SKIN] Applying %s for %s: %s (%s).",
                chosen_slot,
                effective.get("resolved_role", "GLOBAL"),
                selected_skin.get("skin_name") or skin_id,
                skin_id,
            )

            for endpoint in (
                "/lol-champ-select/v1/session/my-selection",
                "/lol-champ-select-legacy/v1/session/my-selection",
            ):
                try:
                    self._log_lcu_request("SKIN", "patch", endpoint, payload)
                    response = await self.connection.request("patch", endpoint, json=payload)
                except Exception as e:
                    logging.warning("[SKIN] Patch request failed on %s: %s", endpoint, e)
                    response = None

                self._log_lcu_response("SKIN", "patch", endpoint, response)
                if response and response.status < 400 and await self._confirm_skin_applied(skin_id):
                    previous_confirmed = self.state.last_confirmed_skin_id
                    self.state.last_confirmed_skin_id = skin_id
                    if previous_confirmed != skin_id:
                        self._log_history(
                            "skin",
                            f"Skin applied automatically: {selected_skin.get('skin_name') or skin_id}.",
                            {
                                "skin_id": skin_id,
                                "skin_name": selected_skin.get("skin_name") or "",
                                "role": effective.get("resolved_role", "GLOBAL"),
                                "pick_slot": chosen_slot,
                                "endpoint": endpoint,
                            },
                            level="success",
                            category="Champion Select",
                            action="skin",
                        )
                        self._notify_ui(
                            self.EVENT_STATUS,
                            (f"Skin selected: {selected_skin.get('skin_name') or skin_id}.", "SKIN"),
                        )

                    if selected_skin.get("mode") == "random":
                        if not pickable_skins:
                            pickable_skins = await self._fetch_pickable_skins(champion_id)
                        next_pool = self._build_random_skin_pool_candidates(
                            list(selected_skin.get("random_skin_pool") or []),
                            pickable_skins,
                        )
                        next_skin = self._choose_random_skin_entry(next_pool, exclude_skin_id=skin_id)
                        if next_skin:
                            self._persist_random_skin_preview(
                                chosen_slot,
                                source_role=str(selected_skin.get("skin_source_role") or "GLOBAL"),
                                skin=next_skin,
                            )
                    return

            logging.warning(
                "[SKIN] Unable to confirm selected skin for %s after patch attempts. Expected %s.",
                chosen_slot,
                skin_id,
            )
        finally:
            self.state.skin_apply_in_progress = False

    async def _handle_post_game(self: "WebSocketManager") -> None:
        params = self.get_params()
        if not params.get("auto_play_again_enabled"):
            return

        for _ in range(3):
            await asyncio.sleep(2)
            if self.state.current_phase not in ["EndOfGame", "WaitingForStats"]:
                break
            response = await self.connection.request("post", "/lol-lobby/v2/play-again")
            if response and response.status < 400:
                self._log_history(
                    "play_again",
                    "Automatically returned to lobby after the game.",
                    level="success",
                    category="End game",
                    action="play_again",
                )
                self._notify_ui(self.EVENT_PLAY_AGAIN, None)
                self._notify_ui(self.EVENT_STATUS, ("Auto play again succeeded.", "OK"))
                break
