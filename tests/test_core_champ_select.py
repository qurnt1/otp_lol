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

    async def text(self):
        return "" if self._payload is None else str(self._payload)


class DummyDataDragon:
    def __init__(self, mapping):
        self.mapping = mapping
        self.skins = {
            99: {
                99007: {"skin_id": 99007, "skin_num": 7, "skin_name": "Star Guardian Lux", "splash_url": "url-a", "tile_url": "tile-a"},
                99010: {"skin_id": 99010, "skin_num": 10, "skin_name": "Battle Academia Lux", "splash_url": "url-b", "tile_url": "tile-b"},
            },
            86: {
                86000: {"skin_id": 86000, "skin_num": 0, "skin_name": "Default Garen", "splash_url": "garen-a", "tile_url": "garen-tile"},
            },
        }

    def resolve_champion(self, name_or_id):
        return self.mapping.get(name_or_id)

    def id_to_name(self, champion_id):
        reverse = {value: key for key, value in self.mapping.items()}
        return reverse.get(champion_id)

    def get_champion_tags(self, name_or_id):
        return ["Fighter"]

    def get_skin_catalog(self, name_or_id):
        champion_id = self.resolve_champion(name_or_id) if isinstance(name_or_id, str) else int(name_or_id or 0)
        return [dict(entry) for entry in self.skins.get(champion_id, {}).values()]

    def resolve_skin_data(self, name_or_id, skin_id=None, skin_name=None):
        champion_id = self.resolve_champion(name_or_id) if isinstance(name_or_id, str) else int(name_or_id or 0)
        skins = self.skins.get(champion_id, {})
        if skin_id not in {None, ""}:
            try:
                target_skin_id = int(skin_id)
            except (TypeError, ValueError):
                target_skin_id = 0
            if target_skin_id in skins:
                return dict(skins[target_skin_id])
        normalized_name = str(skin_name or "").strip().lower()
        if normalized_name:
            for entry in skins.values():
                if str(entry.get("skin_name") or "").strip().lower() == normalized_name:
                    return dict(entry)
        return None


class ChampSelectLogicTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.events = []
        self.params = {
            "auto_pick_enabled": True,
            "auto_ban_enabled": True,
            "auto_summoners_enabled": False,
            "presets_enabled": True,
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "pick_slots": {
                "pick_1": {"spell_1": "Heal", "spell_2": "Flash", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
                "pick_2": {"spell_1": "Ghost", "spell_2": "Flash", "skin_mode": "fixed", "skin_id": 99010, "skin_name": "Battle Academia Lux", "skin_num": 10, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
                "pick_3": {"spell_1": "Barrier", "spell_2": "Ignite", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
            },
            "role_profiles": {
                "MIDDLE": {
                    "presets_enabled": False,
                    "selected_pick_1": "Lux",
                    "selected_pick_2": "Ashe",
                    "selected_pick_3": "",
                    "selected_ban": "Teemo",
                    "pick_slots": {
                        "pick_1": {"spell_1": "Ignite", "spell_2": "", "skin_mode": "random", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 99007, "random_skin_name": "Star Guardian Lux", "random_skin_num": 7, "random_skin_pool": [{"skin_id": 99007, "skin_name": "Star Guardian Lux", "skin_num": 7}, {"skin_id": 99010, "skin_name": "Battle Academia Lux", "skin_num": 10}]},
                        "pick_2": {"spell_1": "Heal", "spell_2": "Ghost", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
                        "pick_3": {"spell_1": "", "spell_2": "", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
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

    async def test_inventory_skin_is_owned_uses_explicit_fields(self):
        self.assertTrue(self.manager._inventory_skin_is_owned({"ownershipType": "OWNED"}))
        self.assertFalse(self.manager._inventory_skin_is_owned({"ownershipType": "UNOWNED"}))
        self.assertTrue(self.manager._inventory_skin_is_owned({"owned": True}))
        self.assertFalse(self.manager._inventory_skin_is_owned({"owned": False}))

    async def test_fetch_owned_skins_falls_back_to_pickable_when_inventory_fails(self):
        self.manager.state.summoner_id = 12345

        async def request(method, url, **kwargs):
            if method == "get" and url == "/lol-champions/v1/inventories/12345/champions/99/skins":
                return FakeResponse(404, {"errorCode": "missing"})
            if method == "get" and url == "/lol-champ-select/v1/pickable-skins":
                return FakeResponse(
                    200,
                    [
                        {"skinId": 99007, "name": "Star Guardian Lux", "championId": 99},
                        {"skinId": 99010, "name": "Battle Academia Lux", "championId": 99},
                    ],
                )
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        result = await self.manager._fetch_owned_skins_for_champion(99)

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "pickable")
        self.assertEqual([entry["skin_id"] for entry in result["owned_skins"]], [99007, 99010])

    async def test_is_transient_ws_scan_error_detects_process_lookup_failures(self):
        self.assertTrue(self.manager._is_transient_ws_scan_error(ProcessLookupError("gone")))
        self.assertTrue(self.manager._is_transient_ws_scan_error(RuntimeError("process no longer exists (pid=356)")))
        self.assertFalse(self.manager._is_transient_ws_scan_error(RuntimeError("boom")))

    async def test_fetch_rune_styles_parses_slot_based_perks(self):
        async def request(method, url, **kwargs):
            self.assertEqual(method, "get")
            self.assertEqual(url, "/lol-perks/v1/styles")
            return FakeResponse(
                200,
                [
                    {
                        "id": "8000",
                        "name": "Precision",
                        "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/7201_Precision.png",
                        "slots": [
                            {
                                "perks": [
                                    {
                                        "id": "8010",
                                        "name": "Conqueror",
                                        "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/Precision/Conqueror/Conqueror.png",
                                    }
                                ]
                            }
                        ],
                    }
                ],
            )

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        styles = await self.manager._fetch_rune_styles_async()

        self.assertEqual(styles[8000]["perks"][0]["id"], 8010)
        self.assertEqual(styles[8000]["perks"][0]["name"], "Conqueror")
        self.assertIn("Conqueror.png", styles[8000]["perks"][0]["iconPath"])

    async def test_extract_rune_style_perks_accepts_flat_perks(self):
        perks = self.manager._extract_rune_style_perks(
            {
                "perks": [
                    {
                        "id": "8214",
                        "name": "Summon Aery",
                        "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/Sorcery/SummonAery/SummonAery.png",
                    }
                ]
            }
        )

        self.assertEqual(perks[0]["id"], 8214)
        self.assertEqual(perks[0]["name"], "Summon Aery")

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

    async def test_resolve_skin_selection_respects_main_skin_mode_override(self):
        self.manager.state.assigned_position = "TOP"
        self.params["main_skin_mode_overrides"] = {"pick_1": "fixed", "pick_2": "inherit", "pick_3": "inherit"}
        self.params["pick_slots"]["pick_1"].update(
            {
                "skin_mode": "random",
                "skin_id": 86000,
                "skin_name": "Default Garen",
                "skin_num": 0,
                "random_skin_id": 86001,
                "random_skin_name": "Fancy Garen",
                "random_skin_num": 1,
                "random_skin_pool": [{"skin_id": 86001, "skin_name": "Fancy Garen", "skin_num": 1}],
            }
        )

        skin_selection, chosen_slot = self.manager._resolve_skin_selection(self.params, slot_key="pick_1")

        self.assertEqual(chosen_slot, "pick_1")
        self.assertIsNotNone(skin_selection)
        self.assertEqual(skin_selection["mode"], "fixed")
        self.assertEqual(skin_selection["skin_id"], 86000)

    async def test_resolve_skin_selection_returns_none_when_override_is_none(self):
        self.manager.state.assigned_position = "TOP"
        self.params["main_skin_mode_overrides"] = {"pick_1": "none", "pick_2": "inherit", "pick_3": "inherit"}
        self.params["pick_slots"]["pick_1"].update(
            {"skin_mode": "fixed", "skin_id": 86000, "skin_name": "Default Garen", "skin_num": 0}
        )

        skin_selection, chosen_slot = self.manager._resolve_skin_selection(self.params, slot_key="pick_1")

        self.assertIsNone(skin_selection)
        self.assertEqual(chosen_slot, "pick_1")

    async def test_resolve_skin_selection_uses_slot_specific_override_only_for_target_slot(self):
        self.manager.state.assigned_position = "TOP"
        self.params["main_skin_mode_overrides"] = {"pick_1": "none", "pick_2": "fixed", "pick_3": "inherit"}
        self.params["pick_slots"]["pick_2"].update(
            {"skin_mode": "random", "skin_id": 99010, "skin_name": "Battle Academia Lux", "skin_num": 10}
        )

        skin_selection, chosen_slot = self.manager._resolve_skin_selection(self.params, slot_key="pick_2")

        self.assertEqual(chosen_slot, "pick_2")
        self.assertIsNotNone(skin_selection)
        self.assertEqual(skin_selection["mode"], "fixed")
        self.assertEqual(skin_selection["skin_id"], 99010)

    async def test_prepick_uses_first_pickable_champion_in_priority(self):
        self.manager.state.assigned_position = "MID"
        self.params["role_profiles"]["MIDDLE"]["presets_enabled"] = True
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

    async def test_set_skin_fixed_validates_pickable_before_applying(self):
        self.manager.state.assigned_position = "MID"
        self.params["role_profiles"]["MIDDLE"]["presets_enabled"] = True
        self.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_2"].update(
            {"skin_mode": "fixed", "skin_id": 99010, "skin_name": "Battle Academia Lux", "skin_num": 10}
        )
        self.manager.state.last_locked_pick_slot = "pick_2"

        async def request(method, url, **kwargs):
            if method == "get" and url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "championId": 99, "selectedSkinId": 99010}],
                    },
                )
            if method == "get" and url == "/lol-champ-select/v1/pickable-skins":
                return FakeResponse(200, [{"skinId": 99010, "name": "Battle Academia Lux", "championId": 99}])
            if method == "patch" and url == "/lol-champ-select/v1/session/my-selection":
                self.assertEqual(kwargs["json"]["selectedSkinId"], 99010)
                return FakeResponse(200, {})
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._set_skin(self.params)

        self.assertEqual(self.manager.state.last_confirmed_skin_id, 99010)

    async def test_set_skin_fixed_skips_non_pickable_skin(self):
        self.manager.state.assigned_position = "MID"
        self.params["role_profiles"]["MIDDLE"]["presets_enabled"] = True
        self.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_2"].update(
            {"skin_mode": "fixed", "skin_id": 99010, "skin_name": "Battle Academia Lux", "skin_num": 10}
        )
        self.manager.state.last_locked_pick_slot = "pick_2"

        async def request(method, url, **kwargs):
            if method == "get" and url == "/lol-champ-select/v1/session":
                return FakeResponse(
                    200,
                    {
                        "localPlayerCellId": 1,
                        "myTeam": [{"cellId": 1, "championId": 99, "selectedSkinId": 0}],
                    },
                )
            if method == "get" and url == "/lol-champ-select/v1/pickable-skins":
                return FakeResponse(200, [{"skinId": 99007, "name": "Star Guardian Lux", "championId": 99}])
            if method == "patch":
                raise AssertionError("Patch should not be attempted for a non-pickable fixed skin")
            raise AssertionError(f"Unexpected request: {method} {url}")

        self.manager.connection = type("Connection", (), {})()
        self.manager.connection.request = AsyncMock(side_effect=request)

        await self.manager._set_skin(self.params)

        patch_calls = [call for call in self.manager.connection.request.await_args_list if call.args[0] == "patch"]
        self.assertEqual(patch_calls, [])
        self.assertNotEqual(self.manager.state.last_confirmed_skin_id, 99010)

    async def test_champ_select_tick_retries_spells_when_session_does_not_match(self):
        self.manager.state.assigned_position = "MID"
        self.manager.state.has_picked = True
        self.manager.state.last_locked_pick_slot = "pick_2"
        self.manager.state.last_spell_try_ts = 0
        self.params["auto_summoners_enabled"] = True
        self.params["role_profiles"]["MIDDLE"]["presets_enabled"] = True
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

    async def test_ban_does_not_wait_for_prepick_summs_confirmation(self):
        self.manager.state.assigned_position = "TOP"
        self.manager.state.has_prepicked = True
        self.manager.state.last_prepick_slot = "pick_1"
        self.params["auto_summoners_enabled"] = True
        self.params["role_profiles"]["MIDDLE"]["presets_enabled"] = True
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
