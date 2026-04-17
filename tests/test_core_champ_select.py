import asyncio
import unittest
from time import time
from unittest.mock import AsyncMock

from src.core import WebSocketManager


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class DummyDataDragon:
    def __init__(self, mapping):
        self.mapping = mapping

    def resolve_champion(self, name_or_id):
        return self.mapping.get(name_or_id)

    def id_to_name(self, champion_id):
        reverse = {value: key for key, value in self.mapping.items()}
        return reverse.get(champion_id)

    def get_champion_tags(self, name_or_id):
        return ["Fighter"]


class ChampSelectLogicTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.events = []
        self.params = {
            "auto_pick_enabled": True,
            "auto_ban_enabled": True,
            "auto_summoners_enabled": False,
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "pick_slots": {
                "pick_1": {"spell_1": "Heal", "spell_2": "Flash"},
                "pick_2": {"spell_1": "Ghost", "spell_2": "Flash"},
                "pick_3": {"spell_1": "Barrier", "spell_2": "Ignite"},
            },
            "role_profiles": {
                "MIDDLE": {
                    "selected_pick_1": "Lux",
                    "selected_pick_2": "Ashe",
                    "selected_pick_3": "",
                    "selected_ban": "Teemo",
                    "pick_slots": {
                        "pick_1": {"spell_1": "Ignite", "spell_2": ""},
                        "pick_2": {"spell_1": "Heal", "spell_2": "Ghost"},
                        "pick_3": {"spell_1": "", "spell_2": ""},
                    },
                }
            },
        }
        self.manager = WebSocketManager(
            ui_callback=lambda event_type, data=None: self.events.append((event_type, data)),
            dd=DummyDataDragon(
                {
                    "Garen": 86,
                    "Lux": 99,
                    "Ashe": 22,
                    "Teemo": 17,
                }
            ),
            get_params=lambda: self.params.copy(),
        )

    async def test_logic_do_pick_falls_back_to_second_pick(self):
        async def request(method, url, **kwargs):
            self.assertEqual(method, "get")
            self.assertEqual(url, "/lol-champ-select/v1/pickable-champion-ids")
            return FakeResponse(200, [99, 22])

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)
        self.manager._lock_in_champion = AsyncMock(return_value=True)

        await self.manager._logic_do_pick({"id": 123}, self.params)

        self.manager._lock_in_champion.assert_awaited_once_with(123, 99, action_type="pick")
        self.assertEqual(self.manager.state.last_locked_pick_slot, "pick_2")
        self.assertIn((WebSocketManager.EVENT_CHAMPION_PICKED, "Lux"), self.events)

    async def test_logic_do_pick_skips_banned_primary_champion(self):
        self.manager._lock_in_champion = AsyncMock(return_value=True)

        await self.manager._logic_do_pick(
            {"id": 123},
            self.params,
            pickable_set={17, 99, 22},
            banned_ids={17},
        )

        self.manager._lock_in_champion.assert_awaited_once_with(123, 99, action_type="pick")
        self.assertEqual(self.manager.state.last_locked_pick_slot, "pick_2")
        self.assertIn((WebSocketManager.EVENT_CHAMPION_PICKED, "Lux"), self.events)

    async def test_logic_do_pick_tries_next_viable_preset_when_first_lock_fails(self):
        self.manager._lock_in_champion = AsyncMock(side_effect=[False, True])

        await self.manager._logic_do_pick(
            {"id": 123},
            self.params,
            pickable_set={86, 99, 22},
            banned_ids=set(),
        )

        self.assertEqual(
            self.manager._lock_in_champion.await_args_list[0].args,
            (123, 86),
        )
        self.assertEqual(
            self.manager._lock_in_champion.await_args_list[1].args,
            (123, 99),
        )
        self.assertEqual(self.manager._lock_in_champion.await_args_list[0].kwargs, {"action_type": "pick"})
        self.assertEqual(self.manager._lock_in_champion.await_args_list[1].kwargs, {"action_type": "pick"})
        self.assertEqual(self.manager.state.last_locked_pick_slot, "pick_2")
        self.assertIn((WebSocketManager.EVENT_CHAMPION_PICKED, "Lux"), self.events)

    async def test_pick_priority_uses_role_profile_with_global_fallback(self):
        self.manager.state.assigned_position = "MID"
        self.params["role_profiles"]["MIDDLE"]["selected_pick_2"] = ""

        effective = self.manager._get_effective_champ_select_config(self.params)

        self.assertEqual(effective["selected_pick_1"], "Lux")
        self.assertEqual(effective["selected_pick_2"], "Lux")
        self.assertEqual(effective["selected_pick_3"], "Ashe")

    async def test_prepick_uses_first_pickable_champion_in_priority(self):
        self.manager.state.assigned_position = "MID"
        self.manager.state.time_left_ms = 5000
        self.manager._hover_champion = AsyncMock(return_value=True)

        async def request(method, url, **kwargs):
            if url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "benchEnabled": False,
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "assignedPosition": "MID"}],
                        "actions": [[{
                            "id": 10,
                            "actorCellId": 1,
                            "completed": False,
                            "type": "pick",
                            "isInProgress": False,
                            "championId": 0,
                        }]],
                    },
                )
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)
        self.manager._logic_do_pick = AsyncMock()
        self.manager._logic_do_ban = AsyncMock()

        await self.manager._champ_select_tick()

        self.manager._hover_champion.assert_awaited_once_with(10, 22)

    async def test_champ_select_tick_handles_prepick_before_active_ban(self):
        self.manager.state.assigned_position = "TOP"
        self.manager.state.time_left_ms = 5000
        self.manager._hover_champion = AsyncMock(return_value=True)
        self.manager._logic_do_ban = AsyncMock()
        self.manager._logic_do_pick = AsyncMock()

        async def request(method, url, **kwargs):
            if url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "benchEnabled": False,
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "assignedPosition": "TOP"}],
                        "actions": [[
                            {
                                "id": 1,
                                "actorCellId": 1,
                                "completed": False,
                                "type": "ban",
                                "isInProgress": True,
                                "championId": 0,
                            },
                            {
                                "id": 2,
                                "actorCellId": 1,
                                "completed": False,
                                "type": "pick",
                                "isInProgress": False,
                                "championId": 0,
                            },
                        ]],
                    },
                )
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [86, 99, 22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._champ_select_tick()

        self.manager._hover_champion.assert_awaited_once_with(2, 86)
        self.manager._logic_do_ban.assert_not_awaited()
        self.manager._logic_do_pick.assert_not_awaited()

    async def test_champ_select_tick_allows_ban_after_prepick_timeout(self):
        self.manager.state.assigned_position = "TOP"
        self.manager.state.time_left_ms = 5000
        self.manager.state.prepick_wait_started_ts = time() - (self.manager.PREPICK_SOFT_TIMEOUT_S + 0.5)
        self.manager._hover_champion = AsyncMock(return_value=True)
        self.manager._logic_do_ban = AsyncMock()
        self.manager._logic_do_pick = AsyncMock()

        async def request(method, url, **kwargs):
            if url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "benchEnabled": False,
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "assignedPosition": "TOP", "championId": 0}],
                        "actions": [[
                            {
                                "id": 1,
                                "actorCellId": 1,
                                "completed": False,
                                "type": "ban",
                                "isInProgress": True,
                                "championId": 0,
                            },
                            {
                                "id": 2,
                                "actorCellId": 1,
                                "completed": False,
                                "type": "pick",
                                "isInProgress": False,
                                "championId": 86,
                            },
                        ]],
                    },
                )
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [86, 99, 22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._champ_select_tick()

        self.manager._logic_do_ban.assert_awaited_once()

    async def test_logic_do_ban_ignores_same_champion_as_pick(self):
        self.params["selected_ban"] = "Garen"
        self.manager._lock_in_champion = AsyncMock(return_value=True)

        await self.manager._logic_do_ban({"id": 456}, self.params)

        self.manager._lock_in_champion.assert_not_awaited()

    async def test_champ_select_tick_ignores_bench_enabled_modes(self):
        async def request(method, url, **kwargs):
            self.assertEqual(method, "get")
            self.assertEqual(url, "/lol-champ-select/v1/session")
            return FakeResponse(200, {"benchEnabled": True})

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)
        self.manager._logic_do_pick = AsyncMock()
        self.manager._logic_do_ban = AsyncMock()

        await self.manager._champ_select_tick()

        self.manager._logic_do_pick.assert_not_awaited()
        self.manager._logic_do_ban.assert_not_awaited()

    async def test_lock_in_champion_fails_when_initial_hover_is_rejected(self):
        async def request(method, url, **kwargs):
            if method == "patch":
                return FakeResponse(500, {})
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        locked = await self.manager._lock_in_champion(12, 86)

        self.assertFalse(locked)

    async def test_lock_in_champion_confirms_pick_from_session_when_action_endpoint_fails(self):
        async def request(method, url, **kwargs):
            if method == "patch" and url == "/lol-champ-select/v1/session/actions/12":
                return FakeResponse(204, {})
            if method == "post" and url == "/lol-champ-select/v1/session/actions/12/complete":
                return FakeResponse(204, {})
            if method == "get" and url == "/lol-champ-select/v1/session/actions/12":
                return FakeResponse(404, {})
            if method == "get" and url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "championId": 86}],
                        "actions": [[
                            {
                                "id": 12,
                                "actorCellId": 1,
                                "championId": 86,
                                "completed": True,
                                "type": "pick",
                                "isInProgress": False,
                            }
                        ]],
                    },
                )
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        locked = await self.manager._lock_in_champion(12, 86, action_type="pick")

        self.assertTrue(locked)

    async def test_effective_profile_config_includes_pick_slot_spell_fallback(self):
        self.manager.state.assigned_position = "MID"

        effective = self.manager.get_effective_profile_config(params=self.params)

        self.assertEqual(effective["selected_pick_1"], "Lux")
        self.assertEqual(effective["pick_slots"]["pick_1"]["spell_1"], "Ignite")
        self.assertEqual(effective["pick_slots"]["pick_1"]["spell_2"], "Flash")
        self.assertEqual(effective["spell_1"], "Ignite")
        self.assertEqual(effective["spell_2"], "Flash")

    async def test_set_spells_uses_selected_pick_slot(self):
        self.manager.state.assigned_position = "MID"
        self.manager.state.last_locked_pick_slot = "pick_2"

        requests = []

        async def request(method, url, **kwargs):
            requests.append((method, url, kwargs))
            if method == "patch":
                self.assertEqual(url, "/lol-champ-select/v1/session/my-selection")
                self.assertEqual(kwargs["json"]["spell1Id"], 7)
                self.assertEqual(kwargs["json"]["spell2Id"], 6)
                return FakeResponse(200, {})
            if method == "get":
                self.assertEqual(url, "/lol-champ-select/v1/session")
                return FakeResponse(
                    200,
                    {
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "spell1Id": 7, "spell2Id": 6}],
                    },
                )
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._set_spells(self.params)

        self.assertEqual(requests[0][1], "/lol-champ-select/v1/session/my-selection")
        self.assertEqual(requests[1][1], "/lol-champ-select/v1/session")
        self.assertEqual(self.manager.state.last_confirmed_spell_ids, (7, 6))
        self.assertIn((WebSocketManager.EVENT_SPELLS_SET, ("Heal", "Ghost")), self.events)

    async def test_set_spells_retries_with_legacy_endpoint_when_confirmation_fails(self):
        self.manager.state.assigned_position = "MID"
        self.manager.state.last_locked_pick_slot = "pick_2"
        self.manager.SPELL_CONFIRM_RETRIES = 0

        async def request(method, url, **kwargs):
            if method == "patch" and url == "/lol-champ-select/v1/session/my-selection":
                return FakeResponse(200, {})
            if method == "patch" and url == "/lol-champ-select-legacy/v1/session/my-selection":
                return FakeResponse(200, {})
            if method == "get" and url == "/lol-champ-select/v1/session":
                if not hasattr(self, "_confirm_calls"):
                    self._confirm_calls = 0
                self._confirm_calls += 1
                if self._confirm_calls == 1:
                    return FakeResponse(
                        200,
                        {
                            "localPlayerCellId": 1,
                            "myTeam": [{"cellId": 1, "spell1Id": 4, "spell2Id": 4}],
                        },
                    )
                return FakeResponse(
                    200,
                    {
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "spell1Id": 7, "spell2Id": 6}],
                    },
                )
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._set_spells(self.params)

        patch_urls = [call.args[1] for call in self.manager.connection.request.await_args_list if call.args[0] == "patch"]
        self.assertEqual(
            patch_urls,
            [
                "/lol-champ-select/v1/session/my-selection",
                "/lol-champ-select-legacy/v1/session/my-selection",
            ],
        )
        self.assertEqual(self.manager.state.last_confirmed_spell_ids, (7, 6))

    async def test_champ_select_tick_retries_spells_when_session_does_not_match(self):
        self.manager.state.assigned_position = "MID"
        self.manager.state.has_picked = True
        self.manager.state.last_locked_pick_slot = "pick_2"
        self.manager.state.last_spell_try_ts = 0
        self.params["auto_summoners_enabled"] = True
        self.manager._set_spells = AsyncMock()

        async def request(method, url, **kwargs):
            if url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "benchEnabled": False,
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "assignedPosition": "MID", "spell1Id": 4, "spell2Id": 4}],
                        "actions": [],
                    },
                )
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [99, 22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)
        self.manager._logic_do_pick = AsyncMock()
        self.manager._logic_do_ban = AsyncMock()

        await self.manager._champ_select_tick()
        await asyncio.sleep(0)

        self.manager._set_spells.assert_awaited_once()

    async def test_champ_select_tick_confirms_prepick_from_session_and_triggers_spells(self):
        self.manager.state.assigned_position = "MID"
        self.params["auto_summoners_enabled"] = True
        self.manager._set_spells = AsyncMock()

        async def request(method, url, **kwargs):
            if url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "benchEnabled": False,
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "assignedPosition": "MID", "championId": 99, "spell1Id": 4, "spell2Id": 4}],
                        "actions": [],
                    },
                )
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [99, 22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)
        self.manager._logic_do_pick = AsyncMock()
        self.manager._logic_do_ban = AsyncMock()

        await self.manager._champ_select_tick()
        await asyncio.sleep(0)

        self.assertTrue(self.manager.state.has_prepicked)
        self.assertEqual(self.manager.state.last_prepick_slot, "pick_1")
        self.manager._set_spells.assert_awaited_once()

    async def test_ban_does_not_wait_for_prepick_summs_confirmation(self):
        self.manager.state.assigned_position = "TOP"
        self.manager.state.has_prepicked = True
        self.manager.state.last_prepick_slot = "pick_1"
        self.params["auto_summoners_enabled"] = True
        self.manager._logic_do_ban = AsyncMock()
        self.manager._logic_do_pick = AsyncMock()
        self.manager._set_spells = AsyncMock()

        async def request(method, url, **kwargs):
            if url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "benchEnabled": False,
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "assignedPosition": "TOP", "championId": 86, "spell1Id": 4, "spell2Id": 12}],
                        "actions": [[
                            {
                                "id": 1,
                                "actorCellId": 1,
                                "completed": False,
                                "type": "ban",
                                "isInProgress": True,
                                "championId": 0,
                            },
                            {
                                "id": 2,
                                "actorCellId": 1,
                                "completed": False,
                                "type": "pick",
                                "isInProgress": False,
                                "championId": 86,
                            },
                        ]],
                    },
                )
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [86, 99, 22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._champ_select_tick()
        await asyncio.sleep(0)

        self.manager._logic_do_ban.assert_awaited_once()
        self.manager._set_spells.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
