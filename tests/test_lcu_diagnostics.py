import asyncio
import json
import threading
import unittest
from urllib.parse import urlsplit

from src.lcu.client import LcuResponse
from src.lcu.diagnostics import (
    ENDPOINT_CHECKS,
    ERROR_BUFFER_SIZE,
    EVENT_BUFFER_SIZE,
    MAX_PAYLOAD_BYTES,
    REQUEST_BUFFER_SIZE,
    DiagnosticsService,
)


class DiagnosticsServiceTests(unittest.TestCase):
    def test_endpoint_registry_contains_only_fixed_get_ids_and_paths(self):
        self.assertTrue(ENDPOINT_CHECKS)
        for endpoint_id, check in ENDPOINT_CHECKS.items():
            with self.subTest(endpoint_id=endpoint_id):
                self.assertEqual(endpoint_id, check.id)
                self.assertEqual(check.method, "GET")
                parts = urlsplit(check.path)
                self.assertFalse(parts.scheme)
                self.assertFalse(parts.netloc)
                self.assertFalse(parts.query)
                self.assertFalse(parts.fragment)
                self.assertTrue(parts.path.startswith(("/lol-", "/riotclient/")))

    def test_snapshot_returns_detached_serializable_copies(self):
        service = DiagnosticsService()
        service.record_event("/lol-gameflow/v1/gameflow-phase", "Update", {"phase": "Lobby"})

        snapshot = service.snapshot()
        serialized = json.dumps(snapshot)
        snapshot["events"][0]["payload"]["phase"] = "tampered"

        self.assertIn('"phase": "Lobby"', serialized)
        self.assertEqual(service.snapshot()["events"][0]["payload"]["phase"], "Lobby")

    def test_event_payload_redacts_identifiers_credentials_and_local_paths(self):
        service = DiagnosticsService()
        service.record_event(
            "/lol-gameflow/v1/gameflow-phase",
            "Update",
            {
                "riot_id": "Maitre Kacaf#6767",
                "puuid": "PUUID_SENTINEL_012345678901234567890123456789",
                "access_token": "ACCESS_TOKEN_SENTINEL",
                "Authorization": "Bearer AUTH_SENTINEL",
                "cookie": "COOKIE_SENTINEL",
                "note": "Riot identity Alice#EUW",
                "windows_path": r"C:\Users\quent\AppData\Roaming\OTP LOL\app_debug.log",
                "unix_path": "/home/quent/.config/otp-lol/settings.json",
                "env_path": r"%APPDATA%\OTP LOL\parameters.toml",
                "free_text": (
                    "Authorization: Bearer FREE_TEXT_SECRET_SENTINEL "
                    "Cookie: sid=COOKIE_HEADER_ONE; session=COOKIE_HEADER_TWO "
                    "access_token=FREE_TEXT_ACCESS_TOKEN_SENTINEL "
                    "refresh_token=FREE_TEXT_REFRESH_TOKEN_SENTINEL "
                    "api_key=FREE_TEXT_API_KEY_SENTINEL"
                ),
                "phase": "Lobby",
            },
        )

        event = service.snapshot()["events"][0]
        rendered = json.dumps(event, ensure_ascii=False)
        for sentinel in (
            "Maitre Kacaf#6767",
            "PUUID_SENTINEL",
            "ACCESS_TOKEN_SENTINEL",
            "AUTH_SENTINEL",
            "COOKIE_SENTINEL",
            "Alice#EUW",
            "C:\\Users\\quent",
            "/home/quent",
            "%APPDATA%",
            "FREE_TEXT_SECRET_SENTINEL",
            "COOKIE_HEADER_ONE",
            "COOKIE_HEADER_TWO",
            "FREE_TEXT_ACCESS_TOKEN_SENTINEL",
            "FREE_TEXT_REFRESH_TOKEN_SENTINEL",
            "FREE_TEXT_API_KEY_SENTINEL",
        ):
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, rendered)
        self.assertTrue(event["payload_redacted"])
        self.assertEqual(event["summary"], "phase=Lobby")

    def test_event_redacts_account_name_fields_without_riot_id_tags(self):
        service = DiagnosticsService()
        service.record_event(
            "/lol-chat/v1/me",
            "Update",
            {
                "displayName": "DISPLAY_NAME_SENTINEL",
                "playerName": "PLAYER_NAME_SENTINEL",
                "name": "ACCOUNT_NAME_SENTINEL",
            },
        )

        event = service.snapshot()["events"][0]

        self.assertNotIn("DISPLAY_NAME_SENTINEL", json.dumps(event))
        self.assertNotIn("PLAYER_NAME_SENTINEL", json.dumps(event))
        self.assertNotIn("ACCOUNT_NAME_SENTINEL", json.dumps(event))
        self.assertEqual(
            event["payload"],
            {"displayName": "[REDACTED]", "playerName": "[REDACTED]", "name": "[REDACTED]"},
        )
        self.assertTrue(event["payload_redacted"])

    def test_summoner_update_redacts_account_name_without_riot_id_tag(self):
        service = DiagnosticsService()
        service.record_event("otp-lol/summoner_update", "Update", "ACCOUNT_NAME_SENTINEL")

        event = service.snapshot()["events"][0]
        default_export = json.dumps(service.export())

        self.assertNotIn("ACCOUNT_NAME_SENTINEL", json.dumps(event))
        self.assertNotIn("ACCOUNT_NAME_SENTINEL", default_export)
        self.assertEqual(event["payload"], "[REDACTED]")
        self.assertEqual(event["summary"], "[REDACTED]")
        self.assertTrue(event["payload_redacted"])

    def test_payload_is_valid_json_and_capped_at_four_kibibytes(self):
        service = DiagnosticsService()
        service.record_event(
            "/lol-gameflow/v1/gameflow-phase",
            "Update",
            {f"field_{index}": "x" * 1000 for index in range(100)},
        )

        event = service.snapshot()["events"][0]
        encoded_payload = json.dumps(event["payload"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertLessEqual(len(encoded_payload), MAX_PAYLOAD_BYTES)
        self.assertTrue(event["payload_truncated"])
        self.assertIsInstance(json.loads(encoded_payload), dict)

    def test_all_buffers_remain_count_bounded_and_drop_oldest_entries(self):
        service = DiagnosticsService()
        for index in range(REQUEST_BUFFER_SIZE + 5):
            service.record_request(
                {
                    "timestamp": f"request-{index}",
                    "method": "GET",
                    "path": "/lol-gameflow/v1/gameflow-phase",
                    "status": 200,
                    "duration_ms": 1.0,
                    "success": True,
                    "error": None,
                }
            )
        for index in range(EVENT_BUFFER_SIZE + 5):
            service.record_event("/lol-gameflow/v1/gameflow-phase", "Update", {"index": index})
        for index in range(ERROR_BUFFER_SIZE + 5):
            service.record_error("test", f"normalized-{index}")

        snapshot = service.snapshot()
        self.assertEqual(len(snapshot["requests"]), REQUEST_BUFFER_SIZE)
        self.assertEqual(len(snapshot["events"]), EVENT_BUFFER_SIZE)
        self.assertEqual(len(snapshot["errors"]), ERROR_BUFFER_SIZE)
        self.assertEqual(snapshot["requests"][0]["timestamp"], "request-5")
        self.assertEqual(snapshot["events"][0]["payload"]["index"], 5)
        self.assertEqual(snapshot["errors"][0]["error"], "unknown_error")

    def test_request_observer_metadata_is_redacted_and_copy_safe(self):
        service = DiagnosticsService()
        source = {
            "timestamp": "2026-09-17T10:00:00Z",
            "method": "GET",
            "path": "/lol-match-history/v1/matches/PUUID_SENTINEL_012345678901234567890123456789",
            "status": 503,
            "duration_ms": 20.25,
            "success": False,
            "error": "Authorization: Bearer REQUEST_SECRET_SENTINEL",
        }
        service.record_request(source)
        source["path"] = "/tampered"

        request = service.snapshot()["requests"][0]
        self.assertEqual(request["path"], "/lol-match-history/v1/matches/[REDACTED_ID]")
        self.assertEqual(request["error"], "unknown_error")
        self.assertEqual(request["status"], 503)
        self.assertEqual(request["duration_ms"], 20.2)
        self.assertNotIn("REQUEST_SECRET_SENTINEL", json.dumps(request))

    def test_errors_never_store_exception_text_and_redact_error_context(self):
        service = DiagnosticsService()
        service.record_error(
            "GET for Alice#EUW",
            RuntimeError(
                "Bearer EXCEPTION_SECRET_SENTINEL PUUID_SENTINEL_012345678901234567890123456789 "
                r"C:\Users\quent\private.txt"
            ),
            method="GET",
            path="/lol-summoner/v1/users/PUUID_SENTINEL_012345678901234567890123456789",
            status=500,
        )

        error = service.snapshot()["errors"][0]
        rendered = json.dumps(error)
        self.assertEqual(error["error"], "RuntimeError")
        self.assertEqual(error["source"], "[RIOT_ID]")
        for sentinel in ("EXCEPTION_SECRET_SENTINEL", "PUUID_SENTINEL", "quent", "private.txt", "Alice#EUW"):
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, rendered)

    def test_export_omits_account_identity_by_default_and_only_adds_riot_id_on_opt_in(self):
        service = DiagnosticsService(get_riot_id=lambda: "Maitre Kacaf#6767")
        service.record_event("topic", "Update", {"riot_id": "Maitre Kacaf#6767", "puuid": "PUUID_SENTINEL"})

        default_export = json.dumps(service.export(), ensure_ascii=False)
        opted_in_export = service.export(include_riot_id=True)

        self.assertNotIn("Maitre Kacaf#6767", default_export)
        self.assertNotIn("PUUID_SENTINEL", default_export)
        self.assertEqual(opted_in_export["riot_id"], "Maitre Kacaf#6767")
        self.assertNotIn("PUUID_SENTINEL", json.dumps(opted_in_export))

    def test_each_buffer_lock_is_independent(self):
        service = DiagnosticsService()
        completed = threading.Event()

        def record_event():
            service.record_event("topic", "Update", {"phase": "Lobby"})
            completed.set()

        with service._requests_lock:
            worker = threading.Thread(target=record_event, daemon=True)
            worker.start()
            self.assertTrue(completed.wait(timeout=1))
        worker.join(timeout=1)
        self.assertEqual(len(service.snapshot()["events"]), 1)


class DiagnosticsRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_accepts_registry_ids_only_and_executes_only_get_paths(self):
        service_holder = {}
        calls = []

        async def fake_get(path):
            calls.append(path)
            service_holder["service"].record_request(
                {
                    "method": "GET",
                    "path": path,
                    "status": 200,
                    "duration_ms": 3.0,
                    "success": True,
                    "error": None,
                }
            )
            return LcuResponse(200, 3.0, payload={"phase": "Lobby", "riot_id": "Hidden#EUW"})

        service = DiagnosticsService(fake_get)
        service_holder["service"] = service

        results = await service.run(["gameflow_phase"])

        self.assertEqual(calls, [ENDPOINT_CHECKS["gameflow_phase"].path])
        self.assertEqual(results[0]["method"], "GET")
        self.assertEqual(results[0]["summary"], "phase=Lobby")
        self.assertEqual(service.snapshot()["endpoint_results"], results)
        self.assertEqual(service.export()["endpoint_results"], results)
        self.assertNotIn("Hidden#EUW", json.dumps(results))
        for invalid in (["/lol-gameflow/v1/gameflow-phase"], ["unknown"]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                await service.run(invalid)
        with self.assertRaises(TypeError):
            await service.run("gameflow_phase")
        self.assertEqual(len(calls), 1)

    async def test_failed_check_reports_normalized_error_without_response_body(self):
        service = DiagnosticsService(
            lambda _path: _response(
                LcuResponse(503, 9.0, payload={"token": "RESPONSE_SECRET_SENTINEL"}, error="http_error")
            )
        )

        result = await service.run(["gameflow_phase"])

        self.assertEqual(result[0]["status"], 503)
        self.assertEqual(result[0]["error"], "http_error")
        self.assertNotIn("RESPONSE_SECRET_SENTINEL", json.dumps(result))
        self.assertEqual(service.snapshot()["errors"][0]["error"], "http_error")
        self.assertEqual(service.snapshot()["endpoint_results"], result)

    async def test_partial_runs_keep_the_latest_result_for_each_checked_endpoint(self):
        service = DiagnosticsService(
            lambda path: _response(
                LcuResponse(200, 3.0, payload={"path": path})
            )
        )

        await service.run(["gameflow_phase"])
        await service.run(["game_version"])

        results = service.snapshot()["endpoint_results"]
        self.assertEqual([entry["id"] for entry in results], ["gameflow_phase", "game_version"])
        self.assertEqual(results[0]["summary"], "object keys: path")

    async def test_runner_serializes_concurrent_diagnostic_runs(self):
        active = 0
        max_active = 0

        async def fake_get(_path):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return LcuResponse(200, 10.0, payload={"phase": "Lobby"})

        service = DiagnosticsService(fake_get)
        await asyncio.gather(
            service.run(["gameflow_phase"]),
            service.run(["gameflow_phase"]),
        )

        self.assertEqual(max_active, 1)

    async def test_raw_exception_text_is_not_returned_and_later_checks_continue(self):
        async def fake_get(path):
            if path == ENDPOINT_CHECKS["gameflow_phase"].path:
                raise RuntimeError(
                    "TOKEN_SENTINEL Alice#EUW "
                    r"C:\Users\quent\private.txt"
                )
            return LcuResponse(200, 2.0, payload={"version": "16.1"})

        service = DiagnosticsService(fake_get)
        results = await service.run(["gameflow_phase", "game_version"])

        rendered = json.dumps({"results": results, "export": service.export()}, ensure_ascii=False)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["error"], "RuntimeError")
        self.assertTrue(results[1]["success"])
        for sentinel in ("TOKEN_SENTINEL", "Alice#EUW", "quent", "private.txt"):
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, rendered)


async def _response(value):
    return value


if __name__ == "__main__":
    unittest.main()
