"""
FILE NAME: tests/fake_lcu_server.py
GLOBAL PURPOSE:
- Provide a minimal fake LCU server for integration tests.
- Simulate HTTP endpoints and support runtime state changes.

USAGE:
    server = FakeLCUServer()
    await server.start()
    # ... run tests ...
    await server.stop()
"""

import socket
from typing import Any, Dict, Optional

from aiohttp import web


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeLCUServer:
    """Minimal fake LCU that responds to the endpoints used by WebSocketManager."""

    def __init__(self):
        self.port: int = _find_free_port()
        self._app: web.Application = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._auth_token: str = "fake-test-token"
        self._setup_routes()

        # Mutable state — change these between tests
        self.phase: str = "None"
        self.summoner_name: str = "TestPlayer"
        self.summoner_id: int = 12345678
        self.profile_icon_id: int = 42
        self.summoner_level: int = 125
        self.current_summoner_status: int = 200
        self.auto_game_name: str = "TestPlayer"
        self.auto_tag_line: str = "EUW"
        self.puuid: str = "fake-puuid-1234"
        self.platform_id: str = "euw1"
        self.ranked_stats_status: int = 200
        self.ranked_stats: Dict[str, Any] = {
            "queues": [
                {
                    "queueType": "RANKED_SOLO_5x5",
                    "tier": "GOLD",
                    "division": "II",
                    "leaguePoints": 75,
                    "wins": 20,
                    "losses": 15,
                    "isProvisional": False,
                }
            ]
        }
        self.ready_check_state: str = "InProgress"
        self.ready_check_player_response: str = "None"
        self.champ_select_data: Dict[str, Any] = {"actions": [], "myTeam": []}

    # ----------------------------------------------------------------
    # Route setup
    # ----------------------------------------------------------------

    def _setup_routes(self) -> None:
        self._app.router.add_get("/lol-summoner/v1/current-summoner", self._handle_current_summoner)
        self._app.router.add_get("/lol-chat/v1/me", self._handle_chat_me)
        self._app.router.add_get("/lol-ranked/v1/current-ranked-stats", self._handle_ranked_stats)
        self._app.router.add_get("/lol-gameflow/v1/gameflow-phase", self._handle_gameflow_phase)
        self._app.router.add_get("/lol-matchmaking/v1/ready-check", self._handle_ready_check)
        self._app.router.add_post("/lol-matchmaking/v1/ready-check/accept", self._handle_accept_ready)
        self._app.router.add_get("/lol-perks/v1/pages", self._handle_perks_pages)
        self._app.router.add_get("/lol-perks/v1/styles", self._handle_perks_styles)
        self._app.router.add_get("/lol-perks/v1/currentpage", self._handle_perks_current_page)
        self._app.router.add_get("/riotclient/get_region_locale", self._handle_region_locale)
        self._app.router.add_get("/riotclient/region-locale", self._handle_region_locale)
        self._app.router.add_get("/lol-champ-select/v1/session", self._handle_champ_select_session)
        self._app.router.add_get("/lol-champ-select/v1/pickable-champion-ids", self._handle_pickable_champions)
        self._app.router.add_get("/lol-champ-select/v1/pickable-skins", self._handle_pickable_skins)
        self._app.router.add_get(
            "/lol-champions/v1/inventories/{summoner_id}/champions/{champion_id}/skins",
            self._handle_inventory_skins,
        )

        # Track requests for assertion purposes
        self.requests: list[Dict[str, Any]] = []
        self.accept_requests: int = 0

    # ----------------------------------------------------------------
    # HTTP handlers
    # ----------------------------------------------------------------

    async def _handle_current_summoner(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        if self.current_summoner_status != 200:
            return web.Response(status=self.current_summoner_status)
        return web.json_response(
            {
                "displayName": self.summoner_name,
                "summonerId": self.summoner_id,
                "puuid": self.puuid,
                "profileIconId": self.profile_icon_id,
                "summonerLevel": self.summoner_level,
            }
        )

    async def _handle_chat_me(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response(
            {
                "gameName": self.auto_game_name,
                "gameTag": self.auto_tag_line,
                "summonerId": self.summoner_id,
                "name": self.summoner_name,
                "puuid": self.puuid,
            }
        )

    async def _handle_ranked_stats(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        if self.ranked_stats_status != 200:
            return web.Response(status=self.ranked_stats_status)
        return web.json_response(self.ranked_stats)

    async def _handle_gameflow_phase(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.Response(text=f'"{self.phase}"')

    async def _handle_ready_check(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response(
            {
                "state": self.ready_check_state,
                "playerResponse": self.ready_check_player_response,
            }
        )

    async def _handle_accept_ready(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "POST", "path": request.path})
        self.accept_requests += 1
        return web.Response(status=204)

    async def _handle_perks_pages(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response(
            [
                {
                    "id": 1001,
                    "name": "Test Rune Page",
                    "primaryStyleId": 8000,
                    "subStyleId": 8400,
                    "selectedPerkIds": [8005, 8008, 8002, 8003, 8401, 8410, 5001, 5002, 5003],
                    "current": True,
                    "isValid": True,
                    "isDeletable": True,
                },
                {
                    "id": 1002,
                    "name": "Second Test Page",
                    "primaryStyleId": 8100,
                    "subStyleId": 8200,
                    "selectedPerkIds": [8112, 8124, 8134, 8105, 8229, 8234, 5005, 5008, 5001],
                    "current": False,
                    "isValid": True,
                    "isDeletable": True,
                },
            ]
        )

    async def _handle_perks_styles(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response(
            [
                {
                    "id": 8000,
                    "name": "Precision",
                    "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/7201_Precision.png",
                    "slots": [
                        {"perks": [{"id": 8005, "name": "Press the Attack"}, {"id": 8008, "name": "Lethal Tempo"}, {"id": 8021, "name": "Fleet Footwork"}, {"id": 8010, "name": "Conqueror"}]},
                        {"perks": [{"id": 8002, "name": "Overheal"}]},
                        {"perks": [{"id": 8003, "name": "Legend: Alacrity"}]},
                    ],
                },
                {
                    "id": 8100,
                    "name": "Domination",
                    "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/7200_Domination.png",
                    "slots": [
                        {"perks": [{"id": 8112, "name": "Electrocute"}]},
                        {"perks": [{"id": 8124, "name": "Sudden Impact"}]},
                        {"perks": [{"id": 8134, "name": "Eyeball Collection"}]},
                    ],
                },
                {
                    "id": 8400,
                    "name": "Resolve",
                    "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png",
                    "slots": [
                        {"perks": [{"id": 8401, "name": "Demolish"}]},
                        {"perks": [{"id": 8410, "name": "Conditioning"}]},
                    ],
                },
                {
                    "id": 8200,
                    "name": "Sorcery",
                    "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/7202_Sorcery.png",
                    "slots": [
                        {"perks": [{"id": 8229, "name": "Transcendence"}]},
                        {"perks": [{"id": 8234, "name": "Gathering Storm"}]},
                    ],
                },
            ]
        )

    async def _handle_perks_current_page(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response(
            {
                "id": 1001,
                "name": "Test Rune Page",
                "primaryStyleId": 8000,
                "subStyleId": 8400,
                "selectedPerkIds": [8005, 8008, 8002, 8003, 8401, 8410, 5001, 5002, 5003],
                "current": True,
                "isValid": True,
                "isDeletable": True,
            }
        )

    async def _handle_region_locale(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response({"platformId": self.platform_id, "region": self.platform_id})

    async def _handle_champ_select_session(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response(self.champ_select_data)

    async def _handle_pickable_champions(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response([])

    async def _handle_pickable_skins(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response([])

    async def _handle_inventory_skins(self, request: web.Request) -> web.Response:
        self.requests.append({"method": "GET", "path": request.path})
        return web.json_response([])

    # ----------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def clear_requests(self) -> None:
        self.requests.clear()
        self.accept_requests = 0
