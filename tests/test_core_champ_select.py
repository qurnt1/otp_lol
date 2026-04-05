import unittest
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
            "role_profiles": {
                "MIDDLE": {
                    "selected_pick_1": "Lux",
                    "selected_pick_2": "Ashe",
                    "selected_pick_3": "",
                    "selected_ban": "Teemo",
                }
            },
        }
        self.manager = WebSocketManager(
            ui_callback=lambda event_type, data=None: self.events.append((event_type, data)),
            dd=DummyDataDragon({
                "Garen": 86,
                "Lux": 99,
                "Ashe": 22,
                "Teemo": 17,
            }),
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

        self.manager._lock_in_champion.assert_awaited_once_with(123, 99)
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
                return FakeResponse(200, {
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
                })
            if url == "/lol-champ-select/v1/pickable-champion-ids":
                return FakeResponse(200, [22])
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)
        self.manager._logic_do_pick = AsyncMock()
        self.manager._logic_do_ban = AsyncMock()

        await self.manager._champ_select_tick()

        self.manager._hover_champion.assert_awaited_once_with(10, 22)

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


if __name__ == "__main__":
    unittest.main()
