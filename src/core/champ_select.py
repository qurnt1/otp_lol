"""Champion select logic extracted from the LCU manager."""

import asyncio
import logging
from time import time
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from ..config import EP_PICKABLE, SUMMONER_SPELL_MAP

if TYPE_CHECKING:
    from .websocket import WebSocketManager


class ChampSelectMixin:
    """Mixin regroupant la logique de champ select et post-game."""

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
            logging.debug(f"Error fetching pickable champions: {e}")
        return None

    def _get_pick_priority(self: "WebSocketManager", params: Dict[str, Any]) -> List[str]:
        effective = self._get_effective_champ_select_config(params)
        return [
            effective.get("selected_pick_1", ""),
            effective.get("selected_pick_2", ""),
            effective.get("selected_pick_3", ""),
        ]

    def _pick_first_viable_champion(
        self: "WebSocketManager", params: Dict[str, Any], pickable_ids: Optional[Set[int]]
    ) -> Optional[tuple[str, int]]:
        for champion_name in self._get_pick_priority(params):
            if not champion_name:
                continue
            champion_id = self.dd.resolve_champion(champion_name)
            if not champion_id:
                continue
            if pickable_ids is None or champion_id in pickable_ids:
                return champion_name, champion_id
        return None

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
            logging.debug(f"Error fetching champ select session: {e}")
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
                    self._notify_ui(self.EVENT_STATUS, (f"Assigned role detected: {pos}", "ℹ️"))

        actions_groups = session.get("actions", [])
        my_actions = []
        for group in actions_groups:
            for action in group:
                if action.get("actorCellId") == local_id and not action.get("completed"):
                    my_actions.append(action)

        effective = self._get_effective_champ_select_config(params)
        pickable_set = await self._fetch_pickable_ids()

        if params.get("auto_pick_enabled") and effective.get("selected_pick_1"):
            pick_action = next((a for a in my_actions if a.get("type") == "pick"), None)
            if pick_action:
                best_pick = self._pick_first_viable_champion(params, pickable_set)
                target_champion_id = best_pick[1] if best_pick else None
                current_hover = pick_action.get("championId")
                if target_champion_id and current_hover != target_champion_id:
                    if time() - self.state.last_intent_try_ts > 0.5 and self._can_hover_now():
                        hover_success = await self._hover_champion(pick_action["id"], target_champion_id)
                        if not hover_success:
                            logging.debug("Pre-pick ignore: le hover LCU n'a pas ete confirme.")
                        self.state.last_intent_try_ts = time()

        active_action = next((a for a in my_actions if a.get("isInProgress") is True), None)
        if active_action:
            action_type = active_action.get("type")
            if action_type == "ban" and params.get("auto_ban_enabled"):
                await self._logic_do_ban(active_action, effective)
            elif action_type == "pick" and params.get("auto_pick_enabled"):
                await self._logic_do_pick(active_action, params, pickable_set)

    async def _hover_champion(self: "WebSocketManager", action_id: int, champion_id: int) -> bool:
        url = f"/lol-champ-select/v1/session/actions/{action_id}"
        response = await self.connection.request("patch", url, json={"championId": champion_id})
        success = bool(response and response.status < 400)
        if success:
            champion_name = self.dd.id_to_name(champion_id) or str(champion_id)
            self._log_history(
                "hover",
                f"Pre-pick envoye sur {champion_name}.",
                {"champion": champion_name},
                category="Champion Select",
                action="hover",
            )
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
        if time() - self.state.last_action_try_ts < 0.1:
            return
        self.state.last_action_try_ts = time()

        champion_id = self.dd.resolve_champion(selected_ban)
        if not champion_id:
            return

        success = await self._lock_in_champion(action["id"], champion_id)
        if success:
            self.state.has_banned = True
            self._log_history(
                "ban",
                f"Automatic ban confirmed on {selected_ban}.",
                {"champion": selected_ban},
                level="success",
                category="Champion Select",
                action="ban",
            )
            self._notify_ui(self.EVENT_CHAMPION_BANNED, selected_ban)
            self._notify_ui(self.EVENT_STATUS, (f"Ciao! {selected_ban} has been banned.", "💀"))

    async def _logic_do_pick(
        self: "WebSocketManager",
        action: Dict[str, Any],
        params: Dict[str, Any],
        pickable_set: Optional[Set[int]] = None,
    ) -> None:
        if time() - self.state.last_action_try_ts < 0.1:
            return
        self.state.last_action_try_ts = time()
        if pickable_set is None:
            pickable_set = await self._fetch_pickable_ids()
        viable_pick = self._pick_first_viable_champion(params, pickable_set)
        if not viable_pick:
            if pickable_set is None:
                self._notify_ui(self.EVENT_STATUS, ("Unable to check pickable champions right now.", "⚠️"))
            else:
                self._notify_ui(self.EVENT_STATUS, ("No configured champion is available (or all are banned)!", "⚠️"))
            return

        champion_name, champion_id = viable_pick
        success = await self._lock_in_champion(action["id"], champion_id)
        if success:
            self.state.has_picked = True
            self._log_history(
                "pick",
                f"Champion automatically locked in: {champion_name}.",
                {"champion": champion_name},
                level="success",
                category="Champion Select",
                action="pick",
            )
            self._notify_ui(self.EVENT_CHAMPION_PICKED, champion_name)
            self._notify_ui(self.EVENT_STATUS, (f"{champion_name} locked in! Your turn to play.", "🔒"))
            if params.get("auto_summoners_enabled"):
                asyncio.create_task(self._set_spells(params))
            return

        self._notify_ui(self.EVENT_STATUS, (f"LCU lock failed for {champion_name}, will retry later.", "⚠️"))

    async def _lock_in_champion(self: "WebSocketManager", action_id: int, champion_id: int) -> bool:
        """Hover then lock a champion, with confirmation because the LCU can accept partial updates."""
        url_action = f"/lol-champ-select/v1/session/actions/{action_id}"

        hover_response = await self.connection.request("patch", url_action, json={"championId": champion_id})
        if not hover_response or hover_response.status >= 400:
            return False

        await asyncio.sleep(0.05)

        patch_response = await self.connection.request(
            "patch",
            url_action,
            json={"championId": champion_id, "completed": True},
        )
        if patch_response and patch_response.status < 400:
            confirmation = await self.connection.request("get", url_action)
            if confirmation and confirmation.status == 200:
                payload = await confirmation.json()
                if payload.get("championId") == champion_id and payload.get("completed") is True:
                    return True

        response = await self.connection.request("post", f"{url_action}/complete")
        if not response or response.status >= 400:
            return False

        confirmation = await self.connection.request("get", url_action)
        if confirmation and confirmation.status == 200:
            payload = await confirmation.json()
            return payload.get("championId") == champion_id and payload.get("completed") is True
        return False

    async def _set_spells(self: "WebSocketManager", params: Dict[str, Any]) -> None:
        if not self.connection:
            return

        effective = self.get_effective_profile_config(params=params)
        spell1_name = effective.get("spell_1") or params.get("global_spell_1", "Heal")
        spell2_name = effective.get("spell_2") or params.get("global_spell_2", "Flash")
        spell1_name = "(None)" if spell1_name == "(Aucun)" else spell1_name
        spell2_name = "(None)" if spell2_name == "(Aucun)" else spell2_name
        spell1_id = SUMMONER_SPELL_MAP.get(spell1_name, 7)
        spell2_id = SUMMONER_SPELL_MAP.get(spell2_name, 4)
        payload = {"spell1Id": spell1_id, "spell2Id": spell2_id}
        response = await self.connection.request("patch", "/lol-champ-select/v1/session/my-selection", json=payload)

        if response and response.status < 400:
            self._log_history(
                "spells",
                f"Automatic spells applied: {spell1_name} + {spell2_name}.",
                {"spell_1": spell1_name, "spell_2": spell2_name, "role": effective.get("resolved_role", "GLOBAL")},
                level="success",
                category="Spells",
                action="set",
            )
            self._notify_ui(self.EVENT_SPELLS_SET, (spell1_name, spell2_name))
            self._notify_ui(self.EVENT_STATUS, (f"Spells auto-selected ({spell1_name}, {spell2_name})", "🪄"))

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
                self._notify_ui(self.EVENT_STATUS, ("Auto play again succeeded!", "✅"))
                break
