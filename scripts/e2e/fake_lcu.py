"""TLS/WSS fake LCU used by the full-stack E2E process."""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import os
import re
import ssl
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web


class FakeLcuServer:
    """Speak the LCU driver's HTTP and WebSocket protocol on loopback."""

    TOKEN = "otp-lol-e2e-token"
    ACCOUNT_RESPONSE_PATHS = frozenset(
        {
            "/lol-chat/v1/me",
            "/lol-summoner/v1/current-summoner",
            "/lol-ranked/v1/current-ranked-stats",
            "/lol-champion-mastery/v1/local-player/champion-mastery",
            "/lol-champion-mastery/v1/local-player/champion-mastery-score",
            "/lol-challenges/v1/challenges/local-player",
            "/lol-challenges/v1/challenges/category-data",
            "/lol-match-history/v1/products/lol/current-summoner/matches",
        }
    )
    ASSET_RESPONSE_PATH = re.compile(
        r"/lol-game-data/assets/v1/(?:champion-icons|summoner-spells|perk-images|items|skins)/[A-Za-z0-9_.\-/]+"
    )
    MAX_ASSET_FIXTURE_BYTES = 8 * 1024 * 1024

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self._runner: web.AppRunner | None = None
        self._sockets: set[web.WebSocketResponse] = set()
        self._ssl_context = self._create_ssl_context()
        self._app = web.Application()
        self._app.router.add_route("*", "/{tail:.*}", self._handle)
        self.port: int | None = None
        self.requests: list[dict[str, Any]] = []
        self.account_responses: dict[str, dict[str, Any]] = {}
        self.asset_responses: dict[str, dict[str, Any]] = {}
        self.mutation_responses: dict[str, list[int]] = {}
        self.static_data_online = False
        self.game_version = "16.1.1"
        self.region = "EUW"
        self.platform = "EUW1"
        self.static_catalogues: dict[str, Any] = {
            "/lol-game-data/assets/v1/champion-summary.json": [
                {"id": 86, "name": "Garen", "alias": "Garen", "squarePortraitPath": "/lol-game-data/assets/v1/champion-icons/86.png"}
            ],
            "/lol-game-data/assets/v1/summoner-spells.json": [
                {"summonerSpellId": 4, "name": "Flash", "iconPath": "/lol-game-data/assets/v1/summoner-spells/Flash.png"}
            ],
            "/lol-game-data/assets/v1/perks.json": [
                {"id": 8005, "name": "Press the Attack", "iconPath": "/lol-game-data/assets/v1/perk-images/8005.png"}
            ],
            "/lol-game-data/assets/v1/items.json": [
                {"id": 1001, "name": "Boots", "iconPath": "/lol-game-data/assets/v1/items/1001.png"}
            ],
            "/lol-game-data/assets/v1/maps.json": [
                {"mapId": 11, "name": "Summoner's Rift"}
            ],
            "/lol-game-data/assets/v1/queues.json": [
                {"queueId": 420, "name": "Ranked Solo", "mapId": 11}
            ],
        }
        self.phase = "None"
        self.ready_check = {"state": "InProgress", "playerResponse": "None"}
        self.session: dict[str, Any] = {
            "gameConfig": {"queueId": 420, "gameMode": "CLASSIC"},
            "localPlayerCellId": 1,
            "myTeam": [
                {
                    "cellId": 1,
                    "summonerId": 24680135,
                    "assignedPosition": "TOP",
                    "championId": 0,
                    "spell1Id": 0,
                    "spell2Id": 0,
                    "selectedRunePageId": 0,
                    "selectedSkinId": 0,
                }
            ],
            "actions": [],
            "bans": {"myTeamBans": [], "theirTeamBans": []},
        }
        self.pickable_champion_ids: list[int] = []
        self.pickable_skins: list[dict[str, Any]] = []
        self.inventory_skins: list[dict[str, Any]] = [
            {"id": 86001, "ownershipType": "owned"},
            {"id": 86013, "ownershipType": "owned"},
        ]
        self.rune_pages: list[dict[str, Any]] = [
            {
                "id": 401,
                "name": "E2E Top",
                "primaryStyleId": 8000,
                "subStyleId": 8100,
                "selectedPerkIds": [8005, 8008, 9101, 8014, 8106, 8120, 5008, 5008, 5011],
                "current": True,
                "isValid": True,
            }
        ]
        self.current_rune_page: dict[str, Any] = deepcopy(self.rune_pages[0])
        self.rune_styles: list[dict[str, Any]] = [
            {
                "id": 8000,
                "name": "Precision",
                "iconPath": "lol-game-data/assets/v1/perk-images/styles/precision/precision.png",
                "perks": [
                    {"id": 8005, "name": "Press the Attack", "iconPath": "lol-game-data/assets/v1/perk-images/8005.png"},
                    {"id": 8008, "name": "Lethal Tempo", "iconPath": "lol-game-data/assets/v1/perk-images/8008.png"},
                    {"id": 9101, "name": "Overheal", "iconPath": "lol-game-data/assets/v1/perk-images/9101.png"},
                    {"id": 8014, "name": "Coup de Grace", "iconPath": "lol-game-data/assets/v1/perk-images/8014.png"},
                ],
            },
            {
                "id": 8100,
                "name": "Domination",
                "iconPath": "lol-game-data/assets/v1/perk-images/styles/domination/domination.png",
                "perks": [
                    {"id": 8106, "name": "Cheap Shot", "iconPath": "lol-game-data/assets/v1/perk-images/8106.png"},
                    {"id": 8120, "name": "Ghost Poro", "iconPath": "lol-game-data/assets/v1/perk-images/8120.png"},
                ],
            },
        ]

    def _create_ssl_context(self) -> ssl.SSLContext:
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
        except ImportError as error:
            raise RuntimeError(
                "The E2E LCU fixture requires the Python 'cryptography' package to "
                "create its ephemeral loopback certificate."
            ) from error

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        cert_path = self.state_dir / "fake-lcu-cert.pem"
        key_path = self.state_dir / "fake-lcu-key.pem"
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        os.chmod(key_path, 0o600)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        return context

    async def start(self) -> int:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0, ssl_context=self._ssl_context)
        await site.start()
        server = site._server
        if server is None or not server.sockets:
            raise RuntimeError("The fake LCU did not bind a loopback socket.")
        self.port = int(server.sockets[0].getsockname()[1])
        return self.port

    async def stop(self) -> None:
        errors: list[Exception] = []
        for websocket in tuple(self._sockets):
            try:
                await websocket.close()
            except Exception as error:  # noqa: BLE001 - attempt every remaining cleanup.
                errors.append(error)
        self._sockets.clear()
        if self._runner is not None:
            try:
                await self._runner.cleanup()
            except Exception as error:  # noqa: BLE001 - attempt every remaining cleanup.
                errors.append(error)
            self._runner = None
        if errors:
            raise RuntimeError(f"Fake LCU cleanup failed for {len(errors)} resource(s).") from errors[0]

    async def disconnect_websockets(self) -> int:
        active = tuple(websocket for websocket in self._sockets if not websocket.closed)
        if not active:
            raise RuntimeError("Cannot simulate an LCU disconnect before a WebSocket subscription is active.")
        errors: list[Exception] = []
        for websocket in active:
            try:
                await asyncio.wait_for(
                    websocket.close(code=1001, message=b"Synthetic League client disconnected"),
                    timeout=5,
                )
            except Exception as error:  # noqa: BLE001 - disconnect every active fixture client.
                errors.append(error)
        if errors:
            raise RuntimeError(f"Fake LCU disconnect failed for {len(errors)} WebSocket(s).") from errors[0]
        return len(active)

    async def emit(self, uri: str, data: Any) -> None:
        if uri == "/lol-gameflow/v1/gameflow-phase":
            self.phase = str(data or "None")
        elif uri == "/lol-matchmaking/v1/ready-check" and isinstance(data, dict):
            self.ready_check = deepcopy(data)
        elif uri in {"/lol-champ-select/v1/session", "/lol-champ-select/v1/session/timer"} and isinstance(data, dict):
            self.session = deepcopy(data)
        frame = [8, "OnJsonApiEvent", {"uri": uri, "eventType": "Update", "data": data}]
        for websocket in tuple(self._sockets):
            if not websocket.closed:
                await websocket.send_json(frame)

    def configure(self, state: dict[str, Any]) -> None:
        allowed = {
            "game_version",
            "static_data_online",
            "region",
            "platform",
            "phase",
            "ready_check",
            "session",
            "pickable_champion_ids",
            "pickable_skins",
            "inventory_skins",
            "rune_pages",
            "current_rune_page",
            "rune_styles",
            "account_responses",
            "static_catalogues",
            "asset_responses",
            "mutation_responses",
        }
        unknown = state.keys() - allowed
        if unknown:
            raise ValueError(f"Unsupported fake LCU state keys: {', '.join(sorted(unknown))}")
        account_responses = state.get("account_responses")
        if account_responses is not None:
            if not isinstance(account_responses, dict):
                raise ValueError("Fake account responses must be an object keyed by an allowlisted LCU GET path")
            for path, response in account_responses.items():
                is_match_path = bool(
                    re.fullmatch(r"/lol-match-history/v1/(?:games|game-timelines)/\d+", path)
                ) if isinstance(path, str) else False
                if path not in self.ACCOUNT_RESPONSE_PATHS and not is_match_path:
                    raise ValueError(f"Unsupported fake account response path: {path}")
                if (
                    not isinstance(response, dict)
                    or set(response) != {"status", "payload"}
                    or type(response["status"]) is not int
                    or not 200 <= response["status"] <= 599
                ):
                    raise ValueError(f"Invalid fake account response for {path}")
        static_catalogues = state.get("static_catalogues")
        if static_catalogues is not None and (
            not isinstance(static_catalogues, dict)
            or set(static_catalogues) != set(self.static_catalogues)
            or any(not isinstance(payload, (dict, list)) for payload in static_catalogues.values())
        ):
            raise ValueError("Fake static catalogues must contain the complete catalogue map")
        asset_responses = state.get("asset_responses")
        if asset_responses is not None:
            if not isinstance(asset_responses, dict):
                raise ValueError("Fake asset responses must be an object keyed by an allowlisted LCU asset path")
            for path, response in asset_responses.items():
                if (
                    not isinstance(path, str)
                    or not self.ASSET_RESPONSE_PATH.fullmatch(path)
                    or any(segment in {".", ".."} for segment in path.split("/"))
                ):
                    raise ValueError(f"Unsupported fake asset response path: {path}")
                if (
                    not isinstance(response, dict)
                    or set(response) != {"status", "content_type", "body_base64"}
                    or type(response["status"]) is not int
                    or not 200 <= response["status"] <= 599
                    or not isinstance(response["content_type"], str)
                    or len(response["content_type"]) > 128
                    or not isinstance(response["body_base64"], str)
                ):
                    raise ValueError(f"Invalid fake asset response for {path}")
                try:
                    decoded = base64.b64decode(response["body_base64"], validate=True)
                except (ValueError, base64.binascii.Error) as error:
                    raise ValueError(f"Invalid fake asset body for {path}") from error
                if len(decoded) > self.MAX_ASSET_FIXTURE_BYTES:
                    raise ValueError(f"Fake asset response exceeds the fixture limit for {path}")
        mutation_responses = state.get("mutation_responses")
        if mutation_responses is not None:
            if not isinstance(mutation_responses, dict):
                raise ValueError("Fake mutation responses must map an allowlisted method and path to status codes")
            for operation, statuses in mutation_responses.items():
                if not isinstance(operation, str) or not re.fullmatch(
                    r"(?:PATCH /lol-champ-select/v1/session/actions/\d+|PUT /lol-perks/v1/pages/\d+|POST /lol-matchmaking/v1/ready-check/accept|POST /lol-lobby/v2/play-again)",
                    operation,
                ):
                    raise ValueError(
                        f"Unsupported fake mutation response operation: {operation}"
                    )
                if (
                    not isinstance(statuses, list)
                    or not 1 <= len(statuses) <= 4
                    or any(type(status) is not int or not 400 <= status <= 599 for status in statuses)
                ):
                    raise ValueError(f"Invalid fake mutation response statuses for {operation}")
        for key, value in state.items():
            setattr(self, key, deepcopy(value))

    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "ready_check": deepcopy(self.ready_check),
            "session": deepcopy(self.session),
            "rune_pages": deepcopy(self.rune_pages),
            "current_rune_page": deepcopy(self.current_rune_page),
        }

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        peer = request.transport.get_extra_info("peername") if request.transport else None
        if not peer or peer[0] != "127.0.0.1":
            return web.Response(status=403)
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return await self._handle_websocket(request)

        if request.method == "GET" and request.path == "/riotclient/region-locale":
            self._record_request(request, None)
            return web.json_response({"platformId": self.platform, "region": self.region})

        expected_auth = "Basic " + base64.b64encode(f"riot:{self.TOKEN}".encode()).decode()
        if request.headers.get("Authorization") != expected_auth:
            return web.Response(status=401)

        try:
            body = await request.json() if request.can_read_body else None
        except (json.JSONDecodeError, UnicodeDecodeError, web.HTTPException):
            body = None
        self._record_request(request, body)
        response_statuses = self.mutation_responses.get(f"{request.method} {request.path}")
        if response_statuses:
            rejection_body = {"detail": "Synthetic LCU mutation rejected"}
            response = web.json_response(rejection_body, status=response_statuses.pop(0))
            await response.prepare(request)
            await response.write_eof()
            self._emit_request(
                {
                    "type": "lcu-response",
                    "method": request.method,
                    "path": request.path,
                    "status": response.status,
                    "body": rejection_body,
                    "complete": True,
                }
            )
            return response

        account_response = self.account_responses.get(request.path)
        if request.method == "GET" and account_response is not None:
            return web.json_response(
                account_response["payload"],
                status=account_response["status"],
            )
        asset_response = self.asset_responses.get(request.path)
        if request.method == "GET" and asset_response is not None:
            return web.Response(
                body=base64.b64decode(asset_response["body_base64"]),
                status=asset_response["status"],
                content_type=asset_response["content_type"],
            )

        if request.method == "GET" and request.path == "/lol-chat/v1/me":
            return web.json_response(
                {
                    "gameName": "E2E Player",
                    "gameTag": "SAFE",
                    "summonerId": 24680135,
                    "name": "E2E Player",
                    "puuid": "otp-lol-e2e-puuid",
                }
            )
        if request.method == "GET" and request.path == "/lol-summoner/v1/current-summoner":
            return web.json_response(
                {
                    "displayName": "E2E Player",
                    "summonerId": 24680135,
                    "puuid": "otp-lol-e2e-puuid",
                }
            )
        if request.method == "GET" and request.path == "/lol-patch/v1/game-version":
            if not self.static_data_online:
                return web.json_response({"detail": "Synthetic static data unavailable"}, status=503)
            return web.json_response(self.game_version)
        if request.method == "GET" and request.path in self.static_catalogues:
            if not self.static_data_online:
                return web.json_response({"detail": "Synthetic static data unavailable"}, status=503)
            return web.json_response(self.static_catalogues[request.path])
        if request.method == "GET" and request.path == "/lol-gameflow/v1/gameflow-phase":
            return web.json_response(self.phase)
        if request.method == "GET" and request.path == "/lol-lobby/v2/lobby":
            return web.json_response({"gameConfig": {"queueId": 420, "gameMode": "CLASSIC"}})
        if request.method == "GET" and request.path == "/lol-matchmaking/v1/ready-check":
            return web.json_response(self.ready_check)
        if request.method == "GET" and request.path in {"/lol-champ-select/v1/session", "/lol-champ-select-legacy/v1/session"}:
            return web.json_response(self.session)
        if request.method == "GET" and request.path == "/lol-champ-select/v1/session/actions":
            return web.json_response([action for group in self.session.get("actions", []) for action in group])
        action_match = re.fullmatch(r"/lol-champ-select/v1/session/actions/(\d+)", request.path)
        complete_match = re.fullmatch(r"/lol-champ-select/v1/session/actions/(\d+)/complete", request.path)
        if action_match and request.method == "GET":
            action = self._find_action(int(action_match.group(1)))
            return web.json_response(action) if action is not None else web.Response(status=404)
        if request.method == "GET" and request.path == "/lol-champ-select/v1/pickable-champion-ids":
            return web.json_response(self.pickable_champion_ids)
        if request.method == "GET" and request.path == "/lol-champ-select/v1/pickable-skins":
            return web.json_response(self.pickable_skins)
        inventory_match = re.fullmatch(
            r"/lol-champions/v1/inventories/\d+/champions/(\d+)/skins",
            request.path,
        )
        if request.method == "GET" and inventory_match:
            return web.json_response(self.inventory_skins if inventory_match.group(1) == "86" else [])
        if request.path in {"/lol-champ-select/v1/session/my-selection", "/lol-champ-select-legacy/v1/session/my-selection"} and request.method == "GET":
            return web.json_response(self._local_selection())
        if request.path == "/lol-perks/v1/pages" and request.method == "GET":
            return web.json_response(self.rune_pages)
        if request.path == "/lol-perks/v1/currentpage" and request.method == "GET":
            return web.json_response(self.current_rune_page)
        if request.method == "GET" and request.path == "/lol-perks/v1/styles":
            return web.json_response(self.rune_styles)
        if request.method == "GET" and request.path in {
            "/lol-ranked/v1/current-ranked-stats",
            "/lol-champion-mastery/v1/local-player/champion-mastery",
            "/lol-match-history/v1/products/lol/current-summoner/matches",
        }:
            return web.json_response({"detail": "Synthetic LCU data unavailable"}, status=503)
        if request.method == "POST" and request.path == "/lol-matchmaking/v1/ready-check/accept":
            self.ready_check["playerResponse"] = "Accepted"
            return web.Response(status=204)
        if request.method == "POST" and request.path == "/lol-lobby/v2/play-again":
            self.phase = "Lobby"
            return web.Response(status=204)
        if action_match and request.method == "PATCH":
            action = self._find_action(int(action_match.group(1)))
            if action is not None and isinstance(body, dict):
                action.update(body)
                if action.get("type") == "pick" and body.get("completed") and int(body.get("championId") or 0) > 0:
                    self._local_selection()["championId"] = int(body["championId"])
                elif action.get("type") == "ban" and body.get("completed") and int(body.get("championId") or 0) > 0:
                    bans = self.session.setdefault("bans", {}).setdefault("myTeamBans", [])
                    champion_id = int(body["championId"])
                    if champion_id not in bans:
                        bans.append(champion_id)
                return web.Response(status=204)
            return web.json_response({"detail": "Unknown action or invalid body"}, status=404)
        if complete_match and request.method == "POST":
            action = self._find_action(int(complete_match.group(1)))
            if action is not None:
                action["completed"] = True
                return web.Response(status=204)
            return web.json_response({"detail": "Unknown action"}, status=404)
        if request.method == "PATCH" and request.path in {"/lol-champ-select/v1/session/my-selection", "/lol-champ-select-legacy/v1/session/my-selection"} and isinstance(body, dict):
            self._local_selection().update(body)
            return web.Response(status=204)
        rune_page_match = re.fullmatch(r"/lol-perks/v1/pages/(\d+)", request.path)
        if rune_page_match and request.method == "PUT" and isinstance(body, dict):
            page_id = int(rune_page_match.group(1))
            if not any(int(page.get("id") or 0) == page_id for page in self.rune_pages):
                return web.json_response({"detail": "Unknown rune page"}, status=404)
            self.rune_pages = [
                {**page, "current": int(page.get("id") or 0) == page_id}
                for page in self.rune_pages
            ]
            self.current_rune_page = next(
                (deepcopy(page) for page in self.rune_pages if int(page.get("id") or 0) == page_id),
                {},
            )
            local_selection = self._local_selection()
            local_selection["selectedRunePageId"] = page_id
            return web.Response(status=204)
        if request.method == "POST" and request.path == "/lol-perks/v1/pages" and isinstance(body, dict):
            page = {**body, "id": max((int(item.get("id") or 0) for item in self.rune_pages), default=1000) + 1}
            self.rune_pages = [{**item, "current": False} for item in self.rune_pages] + [page]
            self.current_rune_page = deepcopy(page)
            return web.json_response(page)
        if rune_page_match and request.method == "DELETE":
            page_id = int(rune_page_match.group(1))
            if not any(int(page.get("id") or 0) == page_id for page in self.rune_pages):
                return web.json_response({"detail": "Unknown rune page"}, status=404)
            self.rune_pages = [page for page in self.rune_pages if int(page.get("id") or 0) != page_id]
            if int(self.current_rune_page.get("id") or 0) == page_id:
                self.current_rune_page = {}
            return web.Response(status=204)
        if request.method in {"PUT", "POST", "PATCH", "DELETE"}:
            return web.json_response({"detail": "Unsupported synthetic LCU mutation"}, status=404)
        return web.json_response({"detail": "Unsupported synthetic LCU request"}, status=404)

    def _find_action(self, action_id: int) -> dict[str, Any] | None:
        for group in self.session.get("actions", []):
            for action in group:
                if int(action.get("id") or 0) == action_id:
                    return action
        return None

    def _local_selection(self) -> dict[str, Any]:
        local_id = self.session.get("localPlayerCellId")
        for player in self.session.get("myTeam", []):
            if player.get("cellId") == local_id:
                return player
        selection: dict[str, Any] = {"cellId": local_id}
        self.session.setdefault("myTeam", []).append(selection)
        return selection

    async def _handle_websocket(self, request: web.Request) -> web.StreamResponse:
        expected_auth = "Basic " + base64.b64encode(f"riot:{self.TOKEN}".encode()).decode()
        if request.headers.get("Authorization") != expected_auth:
            return web.Response(status=401)

        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        self._sockets.add(websocket)
        try:
            first_message = await websocket.receive_json(timeout=10)
            if first_message != [5, "OnJsonApiEvent"]:
                await websocket.close(code=1002, message=b"unexpected LCU subscription")
                return websocket
            await websocket.send_json([8, "OnJsonApiEvent"])
            self._emit_request(
                {
                    "type": "lcu-websocket-subscribed",
                    "path": request.path,
                    "protocol": "wss",
                    "host": "127.0.0.1",
                    "port": self.port,
                }
            )
            async for message in websocket:
                if message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                    break
        finally:
            self._sockets.discard(websocket)
        return websocket

    def _record_request(self, request: web.Request, body: Any) -> None:
        record = {
            "method": request.method,
            "path": request.path,
            "body": body,
            "host": "127.0.0.1",
            "port": self.port,
        }
        self.requests.append(record)
        self._emit_request({"type": "lcu-request", **record})

    @staticmethod
    def _emit_request(record: dict[str, Any]) -> None:
        print(json.dumps(record, separators=(",", ":")), flush=True)
