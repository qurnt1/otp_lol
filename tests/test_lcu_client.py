import asyncio
import unittest
from unittest.mock import patch

from src.lcu.client import LcuClient


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "application/json"):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self._body = body

    async def read(self):
        return self._body


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def request(self, method, path):
        self.calls.append((method, path))
        return self.response


class LcuClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_json_get_uses_the_existing_connection_and_records_safe_metadata(self):
        connection = FakeConnection(FakeResponse(b'{"phase":"InProgress"}'))
        records = []
        client = LcuClient(lambda: connection, request_observer=records.append)

        response = await client.get_json("/lol-gameflow/v1/gameflow-phase")

        self.assertTrue(response.ok)
        self.assertEqual(response.payload, {"phase": "InProgress"})
        self.assertEqual(connection.calls, [("get", "/lol-gameflow/v1/gameflow-phase")])
        self.assertEqual(records[0]["method"], "GET")
        self.assertTrue(records[0]["success"])
        self.assertNotIn("Authorization", records[0])
        self.assertNotIn("token", str(records[0]).lower())

    async def test_http_and_malformed_json_errors_are_normalized(self):
        http_client = LcuClient(lambda: FakeConnection(FakeResponse(b"secret body", status=503)))
        http_result = await http_client.get_json("/lol-ranked/v1/current-ranked-stats")
        self.assertEqual(http_result.status_code, 503)
        self.assertEqual(http_result.error, "http_error")
        self.assertIsNone(http_result.payload)

        malformed_client = LcuClient(lambda: FakeConnection(FakeResponse(b"not json")))
        malformed_result = await malformed_client.get_json("/lol-gameflow/v1/gameflow-phase")
        self.assertEqual(malformed_result.status_code, 200)
        self.assertEqual(malformed_result.error, "invalid_json")

    async def test_disconnected_and_timeout_results_do_not_expose_exceptions(self):
        disconnected = await LcuClient(lambda: None).get_json("/lol-gameflow/v1/gameflow-phase")
        self.assertEqual(disconnected.error, "disconnected")

        class SlowConnection:
            async def request(self, _method, _path):
                await asyncio.sleep(0.05)

        timed_out = await LcuClient(lambda: SlowConnection(), timeout_s=0.001).get_json(
            "/lol-gameflow/v1/gameflow-phase"
        )
        self.assertEqual(timed_out.error, "timeout")
        self.assertNotIn("token", str(timed_out).lower())

    async def test_diagnostic_observer_failure_does_not_hide_a_successful_get(self):
        connection = FakeConnection(FakeResponse(b'{"ok":true}'))

        def fail_observer(_record):
            raise RuntimeError("token=must-not-be-logged")

        result = await LcuClient(lambda: connection, request_observer=fail_observer).get_json(
            "/lol-gameflow/v1/gameflow-phase"
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.payload, {"ok": True})

    async def test_rejects_non_lcu_urls_and_path_traversal_before_request(self):
        connection = FakeConnection(FakeResponse(b"{}"))
        client = LcuClient(lambda: connection)
        for path in (
            "https://example.com/lol-gameflow/v1/gameflow-phase",
            "//example.com/lol-gameflow/v1/gameflow-phase",
            "/lol-game-data/../settings",
            "/lol-game-data/%2e%2e/settings",
            "/lol-game-data/%252e%252e/settings",
            "/lol-game-data/%25252e%25252e/settings",
            "/lol-gameflow/v1/gameflow-phase?token=secret",
            "/lol-gameflow/v1/gameflow-phase?begIndex=0&endIndex=19",
            "/lol-match-history/v1/products/lol/current-summoner/matches?puuid=private",
            "/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=10&endIndex=9",
            "/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=100",
            "/lol-gameflow/v1/gameflow-phase#fragment",
            "\\\\example.com\\lol-gameflow",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                await client.get_json(path)
        self.assertEqual(connection.calls, [])

    async def test_match_history_query_is_limited_to_bounded_index_range(self):
        connection = FakeConnection(FakeResponse(b"[]"))
        path = "/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=19"

        result = await LcuClient(lambda: connection).get_json(path)

        self.assertTrue(result.ok)
        self.assertEqual(connection.calls, [("get", path)])

    async def test_binary_response_is_bounded(self):
        connection = FakeConnection(FakeResponse(b"12345", content_type="image/png"))
        with patch("src.lcu.client.MAX_BINARY_RESPONSE_BYTES", 4):
            result = await LcuClient(lambda: connection).get_bytes(
                "/lol-game-data/assets/v1/champion-icons/86.png"
            )
        self.assertEqual(result.error, "response_too_large")
        self.assertIsNone(result.payload)


if __name__ == "__main__":
    unittest.main()
