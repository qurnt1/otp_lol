"""API boundary checks for account and LCU diagnostics routes."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.context import ApplicationContext
from src.config import DEFAULT_PARAMS
from src.lcu.client import LcuResponse
from src.lcu.diagnostics import DiagnosticsService


class LcuApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ApplicationContext(params=DEFAULT_PARAMS)
        def result(data: dict[str, object]) -> SimpleNamespace:
            return SimpleNamespace(as_dict=lambda: {
                "data": data,
            "available": True,
            "stale": False,
            "last_synced": "2026-09-17T00:00:00+00:00",
            "error": None,
            "source": "lcu",
            "from_cache": False,
            "errors": {},
            })

        self.context.account_stats = SimpleNamespace(
            get_summary=AsyncMock(return_value=result({"level": 100, "profile_icon_id": 1})),
            get_ranked=AsyncMock(return_value=result({"queues": []})),
            get_masteries=AsyncMock(return_value=result({"champions": [], "score": 0})),
            get_challenges=AsyncMock(return_value=result({"challenges": {"challenges": [], "total_points": 0}, "categories": []})),
            get_matches=AsyncMock(return_value=result({"offset": 0, "matches": [], "total": 0})),
            get_match_detail=AsyncMock(return_value=result({"game_id": "123456", "participants": []})),
            timeline=AsyncMock(return_value=result({"game_id": "123456", "events": []})),
        )
        self.context.static_data = SimpleNamespace(
            status={
                "source": "cache",
                "game_version": "16.18.1",
                "connected": False,
                "cache_available": True,
                "cache_version": "16.18.1",
                "catalogs": {
                    name: {"available": True}
                    for name in ("champions", "spells", "perks", "items", "maps", "queues")
                },
            },
            load_queues=Mock(return_value=None),
            load_maps=Mock(return_value=None),
            load_items=Mock(return_value=None),
        )
        self.context.diagnostics = DiagnosticsService(
            self._request_json,
            get_riot_id=lambda: "Test#EUW",
        )
        self.client = TestClient(create_app(self.context))

    async def _request_json(self, path: str) -> LcuResponse:
        if path == "/lol-gameflow/v1/gameflow-phase":
            return LcuResponse(200, 1, "ChampSelect")
        return LcuResponse(200, 1, {"state": "ready"})

    def test_account_sections_are_exposed_as_independent_lazy_endpoints(self) -> None:
        for path in (
            "/api/account/summary",
            "/api/account/ranked",
            "/api/account/masteries",
            "/api/account/challenges",
            "/api/account/matches",
            "/api/account/matches/123456",
            "/api/account/matches/123456/timeline",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["available"])

        self.context.account_stats.get_summary.assert_awaited_once()
        self.context.account_stats.get_match_detail.assert_awaited_once_with(123456)
        self.context.account_stats.timeline.assert_awaited_once_with(123456)

    def test_account_match_limit_and_ids_are_bounded_at_the_api(self) -> None:
        invalid_limit = self.client.get("/api/account/matches?limit=21")
        invalid_game_id = self.client.get("/api/account/matches/0")

        self.assertEqual(invalid_limit.status_code, 422)
        self.assertEqual(invalid_game_id.status_code, 422)
        self.context.account_stats.get_matches.assert_not_awaited()
        self.context.account_stats.get_match_detail.assert_not_awaited()

    def test_match_routes_enrich_queue_map_and_item_ids_from_local_catalogues(self) -> None:
        def result(data: dict[str, object]) -> SimpleNamespace:
            return SimpleNamespace(
                as_dict=lambda: {
                    "data": data,
                    "available": True,
                    "stale": False,
                    "last_synced": "2026-09-17T00:00:00+00:00",
                    "error": None,
                    "source": "lcu",
                    "from_cache": False,
                    "errors": {},
                }
            )

        self.context.account_stats.get_matches = AsyncMock(
            return_value=result(
                {
                    "matches": [{"game_id": "123456", "queue_id": 420}],
                    "offset": 0,
                    "total": 1,
                }
            )
        )
        self.context.account_stats.get_match_detail = AsyncMock(
            return_value=result(
                {
                    "game_id": "123456",
                    "queue_id": 420,
                    "participants": [{"items": [1001, 9999]}],
                }
            )
        )
        self.context.account_stats.timeline = AsyncMock(
            return_value=result(
                {
                    "game_id": "123456",
                    "events": [{"type": "ITEM_PURCHASED", "timestamp": 1000, "item_id": 1001}],
                }
            )
        )
        self.context.static_data.load_queues = Mock(
            return_value=[{"queueId": 420, "mapId": 11, "name": "Ranked Solo"}]
        )
        self.context.static_data.load_maps = Mock(
            return_value=[{"mapId": 11, "name": "Summoner's Rift"}]
        )
        self.context.static_data.load_items = Mock(
            return_value={
                "1001": {
                    "itemId": 1001,
                    "name": "Boots",
                    "localizedNames": {"fr_FR": "Bottes"},
                }
            }
        )

        matches = self.client.get("/api/account/matches").json()["data"]["matches"][0]
        detail = self.client.get("/api/account/matches/123456").json()["data"]
        timeline = self.client.get("/api/account/matches/123456/timeline").json()["data"]

        self.assertEqual(matches["queue_name"], "Ranked Solo")
        self.assertEqual(matches["map_name"], "Summoner's Rift")
        self.assertEqual(detail["queue_name"], "Ranked Solo")
        self.assertEqual(detail["map_name"], "Summoner's Rift")
        self.assertEqual(detail["item_names"], {"1001": "Bottes"})
        self.assertEqual(timeline["item_names"], {"1001": "Bottes"})

    def test_diagnostics_redacts_runtime_account_and_only_runs_fixed_checks(self) -> None:
        overview = self.client.get("/api/diagnostics")
        run = self.client.post(
            "/api/diagnostics/run",
            json={"endpoint_ids": ["gameflow_phase"]},
            headers={"Origin": "http://testserver"},
        )
        rejected = self.client.post(
            "/api/diagnostics/run",
            json={"endpoint_ids": ["/lol-secret/path"]},
            headers={"Origin": "http://testserver"},
        )

        self.assertEqual(overview.status_code, 200)
        self.assertNotIn("riot_id", overview.json()["runtime"])
        self.assertIs(overview.json()["game_data"]["catalogs"]["champions"], True)
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["results"][0]["id"], "gameflow_phase")
        self.assertEqual(rejected.status_code, 422)

    def test_diagnostic_export_requires_explicit_identity_opt_in(self) -> None:
        self.client.post(
            "/api/diagnostics/run",
            json={"endpoint_ids": ["gameflow_phase"]},
            headers={"Origin": "http://testserver"},
        )
        with patch("src.api.routes.diagnostics.get_webview2_runtime_version", return_value="145.0.1.2"):
            redacted = self.client.get("/api/diagnostics/export")
            with_identity = self.client.get("/api/diagnostics/export?include_riot_id=true")

        self.assertEqual(redacted.status_code, 200)
        self.assertNotIn("riot_id", redacted.json())
        self.assertEqual(redacted.json()["webview2_version"], "145.0.1.2")
        self.assertEqual(redacted.json()["endpoint_results"][0]["id"], "gameflow_phase")
        self.assertTrue(redacted.json()["game_data"]["catalogs"]["champions"])
        self.assertEqual(with_identity.json()["riot_id"], "Test#EUW")
        self.assertEqual(
            with_identity.headers["content-disposition"],
            'attachment; filename="otp-lol-diagnostics.json"',
        )

    def test_game_data_status_reports_the_current_source_without_credentials(self) -> None:
        response = self.client.get("/api/game-data/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "cache")
        self.assertEqual(response.json()["cache_version"], "16.18.1")
        self.assertNotIn("riot_id", response.json())

    def test_game_data_status_does_not_mark_unloaded_summoner_fallback_as_available(self) -> None:
        self.context.static_data.status = {
            "source": None,
            "game_version": None,
            "connected": False,
            "cache_available": False,
            "cache_version": None,
            "catalogs": {
                name: {"available": False}
                for name in ("champions", "spells", "perks", "items", "maps", "queues")
            },
        }
        self.context.data_dragon.loaded = True
        self.context.data_dragon.by_id = {86: {"name": "Garen"}}
        self.context.data_dragon.summoner_loaded = True
        self.context.data_dragon.summoner_data = {}

        with patch.object(self.context, "ensure_static_data", new=AsyncMock()):
            response = self.client.get("/api/game-data/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "datadragon")
        self.assertTrue(response.json()["catalogs"]["champions"])
        self.assertFalse(response.json()["catalogs"]["spells"])
        self.assertEqual(response.json()["fallback"], "datadragon")

        self.context.data_dragon.summoner_data = {"Flash": "SummonerFlash.png"}
        with patch.object(self.context, "ensure_static_data", new=AsyncMock()):
            loaded_response = self.client.get("/api/game-data/status")
        self.assertTrue(loaded_response.json()["catalogs"]["spells"])


if __name__ == "__main__":
    unittest.main()
