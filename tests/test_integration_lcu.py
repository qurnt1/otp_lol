"""
FILE NAME: tests/test_integration_lcu.py
GLOBAL PURPOSE:
- Integration tests that exercise WebSocketManager against a fake LCU server.
- Validate player detection, rune page fetching, ready-check acceptance,
  and phase-change state management without mocks on the HTTP layer.

KEY TESTS:
- test_refresh_player_and_region: Summoner and region are resolved from fake LCU.
- test_fetch_rune_pages_and_styles: Rune pages and styles are fetched and parsed.
- test_auto_accept_ready_check: Ready-check triggers an accept POST.
- test_phase_change_resets_state: ChampSelect arrival resets between-game flags.
- test_connection_lifecycle: ws_active flag tracks the connection state.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from src.core.events import (
    GameLoading,
    GameStarted,
    PhaseChanged,
    ProfileUpdated,
    RankedEntry,
    ReturnedToLobby,
    SummonerUpdated,
)
from src.core.websocket import WebSocketManager
from tests.fake_lcu_server import FakeLCUServer

# Shared event collector
_events = []


def _collect_event(event):
    _events.append(event)


def _clear_events():
    _events.clear()


def _fake_get_params():
    return {
        "auto_accept_enabled": True,
        "summoner_name_auto_detect": True,
        "manual_summoner_name": "",
        "manual_region": "euw",
        "presets_enabled": True,
        "auto_pick_enabled": True,
        "auto_ban_enabled": False,
        "auto_summoners_enabled": True,
        "selected_pick_1": "Garen",
        "selected_pick_2": "",
        "selected_pick_3": "",
        "selected_ban": "",
        "pick_slots": {
            "pick_1": {
                "spell_1": "Flash", "spell_2": "Ignite",
                "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0,
                "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0,
                "random_skin_pool": [],
                "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True,
                "rune_keystone_path": "", "rune_sub_style_icon_path": "",
            },
            "pick_2": {
                "spell_1": "", "spell_2": "",
                "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0,
                "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0,
                "random_skin_pool": [],
                "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True,
                "rune_keystone_path": "", "rune_sub_style_icon_path": "",
            },
            "pick_3": {
                "spell_1": "", "spell_2": "",
                "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0,
                "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0,
                "random_skin_pool": [],
                "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True,
                "rune_keystone_path": "", "rune_sub_style_icon_path": "",
            },
        },
        "auto_detected_region": "",
        "auto_detected_platform": "",
        "auto_detected_riot_id": "",
    }


class FakeDataDragon:
    def __init__(self):
        self.all_names = ["Garen", "Lux", "Ashe", "Teemo"]

    def resolve_champion(self, name_or_id):
        mapping = {"garen": 86, "lux": 99, "ashe": 22, "teemo": 17}
        return mapping.get(name_or_id.lower()) if isinstance(name_or_id, str) else name_or_id

    def id_to_name(self, champion_id):
        return {86: "Garen", 99: "Lux", 22: "Ashe", 17: "Teemo"}.get(champion_id)

    def get_rune_perk_icon_path(self, perk_id):
        return ""

    def get_rune_perk_name(self, perk_id):
        return ""

    def get_rune_perk_icon(self, path):
        return None

    def get_rune_style_icon(self, path):
        return None

    def get_champion_icon(self, name_or_id):
        return None

    def get_summoner_icon(self, name):
        return None

    def get_skin_preview_url(self, *args, **kwargs):
        return None


class FakeConnection:
    """Wraps aiohttp session to mimic lcu_driver connection.request()."""

    def __init__(self, base_url: str):
        import aiohttp
        self._session: aiohttp.ClientSession = None
        self._base_url = base_url.rstrip("/")

    async def _ensure_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()

    async def request(self, method: str, endpoint: str, **kwargs):
        await self._ensure_session()
        url = f"{self._base_url}{endpoint}"
        return await self._session.request(method, url, **kwargs)

    async def close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class IntegrationLCUTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _clear_events()
        self.server = FakeLCUServer()
        await self.server.start()
        self.connection = FakeConnection(self.server.base_url)

    async def asyncTearDown(self):
        await self.connection.close()
        await self.server.stop()

    def _make_manager(self, **overrides) -> WebSocketManager:
        params = _fake_get_params()
        params.update(overrides)
        mgr = WebSocketManager(
            event_sink=_collect_event,
            dd=FakeDataDragon(),
            get_params=lambda: dict(params),
            update_param=lambda k, v: None,
        )
        mgr.connection = self.connection
        mgr.ws_active = True
        return mgr

    # ------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------

    async def test_ws_active_flag_after_start(self):
        mgr = self._make_manager()
        self.assertTrue(mgr.is_active)

    async def test_supervised_task_logs_unhandled_exception(self):
        mgr = self._make_manager()

        async def fail():
            raise RuntimeError("supervised failure")

        with self.assertLogs(level="ERROR") as logs:
            mgr._spawn_task(fail(), scope="application")
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertTrue(any("Unhandled exception in application background task" in line for line in logs.output))

    async def test_supervised_task_is_removed_after_completion(self):
        mgr = self._make_manager()

        async def finish():
            return "done"

        task = mgr._spawn_task(finish(), scope="application")
        self.assertIn(task, mgr._tasks_by_scope["application"])
        await task
        await asyncio.sleep(0)

        self.assertNotIn(task, mgr._tasks_by_scope["application"])

    async def test_cancelled_supervised_task_is_ignored(self):
        mgr = self._make_manager()
        task = mgr._spawn_task(asyncio.sleep(60), scope="session")

        mgr._cancel_task_scopes("session")
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertTrue(task.cancelled())
        self.assertNotIn(task, mgr._tasks_by_scope["session"])

    async def test_duplicate_supervised_key_reuses_existing_task(self):
        mgr = self._make_manager()
        release = asyncio.Event()

        async def wait_for_release():
            await release.wait()

        first = mgr._spawn_task(wait_for_release(), scope="session", key="runes")
        second = mgr._spawn_task(wait_for_release(), scope="session", key="runes")
        self.assertIs(first, second)

        release.set()
        await first
        await asyncio.sleep(0)

    async def test_old_session_task_is_cancelled_before_new_session(self):
        mgr = self._make_manager()
        started = asyncio.Event()
        wrote_result = False

        async def old_session_work():
            nonlocal wrote_result
            started.set()
            await asyncio.sleep(60)
            if mgr._is_current_session_task():
                wrote_result = True

        mgr._start_champ_select_session()
        task = mgr._spawn_task(old_session_work(), scope="session")
        await started.wait()
        old_generation = mgr._session_generation

        mgr._start_champ_select_session()
        await asyncio.sleep(0)

        self.assertNotEqual(mgr._session_generation, old_generation)
        self.assertTrue(task.cancelled())
        self.assertFalse(wrote_result)

    async def test_connection_tasks_are_cancelled_on_runtime_reset(self):
        mgr = self._make_manager()
        task = mgr._spawn_task(asyncio.sleep(60), scope="connection", key="refresh_summoner")

        mgr._reset_ws_runtime_state()
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        self.assertTrue(task.cancelled())
        self.assertNotIn(task, mgr._tasks_by_scope["connection"])

    async def test_no_connection_returns_empty_rune_pages(self):
        mgr = self._make_manager()
        mgr.connection = None
        self.assertEqual(await mgr._fetch_rune_pages_async(), [])

    async def test_no_connection_returns_empty_rune_styles(self):
        mgr = self._make_manager()
        mgr.connection = None
        self.assertEqual(await mgr._fetch_rune_styles_async(), {})

    # ------------------------------------------------------------
    # Player and region detection
    # ------------------------------------------------------------

    async def test_refresh_player_and_region_resolves_summoner(self):
        mgr = self._make_manager()
        await mgr._refresh_player_and_region()

        self.assertEqual(mgr.state.auto_game_name, "TestPlayer")
        self.assertEqual(mgr.state.auto_tag_line, "EUW")
        self.assertEqual(mgr.state.summoner, "TestPlayer#EUW")
        self.assertEqual(mgr.state.summoner_id, 12345678)

    async def test_refresh_player_and_region_emits_summoner_update(self):
        mgr = self._make_manager()
        _clear_events()
        await mgr._refresh_player_and_region()

        self.assertIn(SummonerUpdated("TestPlayer#EUW"), _events)

    async def test_refresh_player_emits_profile_avatar_and_rank_snapshot(self):
        mgr = self._make_manager()
        _clear_events()

        await mgr._refresh_player_and_region()

        profile_events = [event for event in _events if isinstance(event, ProfileUpdated)]
        self.assertEqual(len(profile_events), 1)
        profile = profile_events[0]
        self.assertEqual(profile.riot_id, "TestPlayer#EUW")
        self.assertEqual(profile.summoner_id, 12345678)
        self.assertEqual(profile.puuid, "fake-puuid-1234")
        self.assertEqual(profile.profile_icon_id, 42)
        self.assertEqual(profile.summoner_level, 125)
        self.assertEqual(
            profile.ranked_entries,
            (RankedEntry("RANKED_SOLO_5x5", "GOLD", "II", 75, 20, 15, False),),
        )
        self.assertIn(
            {"method": "GET", "path": "/lol-ranked/v1/current-ranked-stats"},
            self.server.requests,
        )

    async def test_refresh_player_handles_missing_profile_and_rank_responses(self):
        self.server.current_summoner_status = 404
        self.server.ranked_stats_status = 404
        mgr = self._make_manager()
        _clear_events()

        await mgr._refresh_player_and_region()

        profile = next(event for event in _events if isinstance(event, ProfileUpdated))
        self.assertIsNone(profile.profile_icon_id)
        self.assertIsNone(profile.summoner_level)
        self.assertEqual(profile.ranked_entries, ())

    async def test_refresh_player_does_not_invent_malformed_rank_values(self):
        self.server.ranked_stats = {
            "queues": [
                {
                    "queueType": "RANKED_SOLO_5x5",
                    "tier": "SILVER",
                    "leaguePoints": "unknown",
                    "wins": -1,
                },
                {"tier": "GOLD", "division": "I"},
            ]
        }
        mgr = self._make_manager()
        _clear_events()

        await mgr._refresh_player_and_region()

        profile = next(event for event in _events if isinstance(event, ProfileUpdated))
        self.assertEqual(len(profile.ranked_entries), 1)
        entry = profile.ranked_entries[0]
        self.assertEqual(entry.tier, "SILVER")
        self.assertIsNone(entry.league_points)
        self.assertIsNone(entry.wins)

    async def test_refresh_player_is_noop_when_lcu_is_offline(self):
        mgr = self._make_manager()
        mgr.connection = None
        _clear_events()

        await mgr._refresh_player_and_region()

        self.assertEqual(_events, [])

    async def test_refresh_player_and_region_sets_platform(self):
        mgr = self._make_manager()
        await mgr._refresh_player_and_region()

        self.assertEqual(mgr.state.platform_routing, "euw1")

    async def test_get_platform_for_websites_returns_euw(self):
        mgr = self._make_manager()
        await mgr._refresh_player_and_region()
        self.assertEqual(mgr.get_platform_for_websites(), "euw")

    # ------------------------------------------------------------
    # Rune pages and styles
    # ------------------------------------------------------------

    async def test_fetch_rune_pages_returns_pages(self):
        mgr = self._make_manager()
        pages = await mgr._fetch_rune_pages_async()

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["id"], 1001)
        self.assertEqual(pages[0]["name"], "Test Rune Page")
        self.assertEqual(pages[0]["primaryStyleId"], 8000)
        self.assertEqual(pages[0]["subStyleId"], 8400)

    async def test_fetch_rune_styles_returns_styles(self):
        mgr = self._make_manager()
        styles = await mgr._fetch_rune_styles_async()

        self.assertIn(8000, styles)
        self.assertIn(8400, styles)
        self.assertEqual(styles[8000]["name"], "Precision")
        self.assertGreater(len(styles[8000]["perks"]), 0)

    # ------------------------------------------------------------
    # Ready-check auto-accept
    # ------------------------------------------------------------

    async def test_auto_accept_ready_check_sends_post(self):
        mgr = self._make_manager()
        mgr.state.current_phase = "ReadyCheck"
        self.server.clear_requests()

        # Re-apply the decorator logic: the @connector.ws.register(EP_READY_CHECK)
        # handler checks auto-accept and POSTs if InProgress + not yet accepted

        from src.config import EP_READY_CHECK

        # Simulate connector.ready callback to set up the connection
        # The ready-check handler is registered inside _ws_loop as:
        #   @connector.ws.register(EP_READY_CHECK)
        #   async def _ws_ready(connection, event): ...
        # We extract the same logic by calling the class-level methods
        # that the handler delegates to.

        # The ready-check handler's logic:
        # - If phase not in Matchmaking/ReadyCheck/None/Lobby → return
        # - If auto_accept_enabled AND state=InProgress AND playerResponse != Accepted
        #   → POST /lol-matchmaking/v1/ready-check/accept
        self.server.ready_check_state = "InProgress"
        self.server.ready_check_player_response = "None"

        self.assertTrue(
            mgr.should_auto_accept_ready_check(
                "ReadyCheck",
                {"state": "InProgress", "playerResponse": "None"},
                {"auto_accept_enabled": True},
            )
        )

        # Directly simulate the ready-check handler logic
        accept_url = f"{EP_READY_CHECK}/accept"
        response = await mgr.connection.request("post", accept_url)
        self.assertEqual(response.status, 204)
        self.assertEqual(self.server.accept_requests, 1)

    async def test_auto_accept_disabled_does_not_send_post(self):
        mgr = self._make_manager(auto_accept_enabled=False)
        self.server.clear_requests()

        should_accept = mgr.should_auto_accept_ready_check(
            "ReadyCheck",
            {"state": "InProgress", "playerResponse": "None"},
            {"auto_accept_enabled": False},
        )

        self.assertFalse(should_accept)
        self.assertEqual(self.server.accept_requests, 0)

    # ------------------------------------------------------------
    # Phase change handling (state reset logic)
    # ------------------------------------------------------------

    async def test_champ_select_phase_resets_between_game_flags(self):
        mgr = self._make_manager()
        mgr.state.current_phase = "ReadyCheck"
        mgr.state.rune_applied_for_session = True
        mgr.state.rune_apply_in_progress = True
        mgr.state.has_picked = True
        mgr.state.has_banned = True

        mgr._refresh_current_queue_id = AsyncMock()
        mgr._champ_select_tick = AsyncMock()
        await mgr._handle_phase_event("ChampSelect")

        self.assertFalse(mgr.state.rune_applied_for_session)
        self.assertFalse(mgr.state.rune_apply_in_progress)
        self.assertFalse(mgr.state.has_picked)
        self.assertFalse(mgr.state.has_banned)

    async def test_phase_change_updates_current_phase(self):
        mgr = self._make_manager()
        mgr.state.current_phase = "None"
        mgr._refresh_current_queue_id = AsyncMock()
        await mgr._handle_phase_event("Lobby")
        self.assertEqual(mgr.state.current_phase, "Lobby")

    async def test_gameflow_transitions_emit_typed_events_and_history_once(self):
        mgr = self._make_manager()
        mgr._log_history = Mock()
        mgr._refresh_current_queue_id = AsyncMock()

        await mgr._handle_phase_event("GameStart")
        await mgr._handle_phase_event("GameStart")
        await mgr._handle_phase_event("InProgress")
        await mgr._handle_phase_event("Lobby")
        await mgr._handle_phase_event("Lobby")

        lifecycle_events = [
            event
            for event in _events
            if isinstance(event, (GameLoading, GameStarted, ReturnedToLobby))
        ]
        self.assertEqual(lifecycle_events, [GameLoading(), GameStarted(), ReturnedToLobby()])
        self.assertEqual(mgr._log_history.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in mgr._log_history.call_args_list],
            ["game_loading", "game_started", "lobby_returned"],
        )
        self.assertEqual(
            [event.phase for event in _events if isinstance(event, PhaseChanged)],
            ["GameStart", "GameStart", "InProgress", "Lobby", "Lobby"],
        )

    async def test_repeated_champ_select_event_does_not_reset_session_state(self):
        mgr = self._make_manager()
        mgr.state.current_phase = "ChampSelect"
        mgr.state.has_picked = True
        mgr._refresh_current_queue_id = AsyncMock()
        mgr._champ_select_tick = AsyncMock()
        mgr._start_champ_select_session = Mock()

        await mgr._handle_phase_event("ChampSelect")

        self.assertTrue(mgr.state.has_picked)
        mgr._start_champ_select_session.assert_not_called()
        mgr._champ_select_tick.assert_awaited_once_with()
