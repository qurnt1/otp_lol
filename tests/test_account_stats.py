import inspect
import json
import tempfile
import unittest
from pathlib import Path

from src.lcu.account_stats import AccountStatsService
from src.lcu.client import LcuResponse

SUMMARY_PATH = "/lol-summoner/v1/current-summoner"
RANKED_PATH = "/lol-ranked/v1/current-ranked-stats"
MASTERY_PATH = "/lol-champion-mastery/v1/local-player/champion-mastery"
MASTERY_SCORE_PATH = "/lol-champion-mastery/v1/local-player/champion-mastery-score"
CHALLENGES_PATH = "/lol-challenges/v1/challenges/local-player"
CATEGORIES_PATH = "/lol-challenges/v1/challenges/category-data"
MATCHES_PATH = "/lol-match-history/v1/products/lol/current-summoner/matches"
TIMELINE_PATH = "/lol-match-history/v1/game-timelines/4242"


class FakeLcu:
    def __init__(self, cache_dir: str, *, connected: bool = True, identity=None):
        self.connected = connected
        self.identity = identity or {
            "riot_id": "FixtureAccount#TST",
            "region": "EUW",
            "puuid": "FIXTURE_PUUID_SENTINEL_0123456789",
            "summoner_id": 123456,
        }
        self.responses = {}
        self.calls = []
        self.service = AccountStatsService(
            self.request_json,
            lambda: self.connected,
            cache_dir,
            lambda: self.identity,
        )

    async def request_json(self, path: str) -> LcuResponse:
        self.calls.append(path)
        value = self.responses.get(path)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, LcuResponse):
            return value
        return LcuResponse(200, 1.0, payload=value)


def ok(payload):
    return LcuResponse(200, 2.5, payload=payload)


def failed(status=503, error="http_error", payload=None):
    return LcuResponse(status, 4.0, payload=payload, error=error)


class AccountStatsTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_and_ranked_normalize_known_shapes_and_drop_unknown_fields(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[SUMMARY_PATH] = {
                "summonerLevel": 321,
                "profileIconId": 42,
                "xpSinceLastLevel": 900,
                "xpUntilNextLevel": 100,
                "displayName": "PRIVATE_RIOT_ID_SENTINEL",
                "puuid": "PRIVATE_PUUID_SENTINEL",
                "token": "PRIVATE_TOKEN_SENTINEL",
                "unexpected": {"secret": "DROP_ME"},
            }
            fake.responses[RANKED_PATH] = {
                "queueMap": {
                    "RANKED_SOLO_5x5": {
                        "tier": "gold",
                        "division": "II",
                        "leaguePoints": 23,
                        "wins": 14,
                        "losses": 9,
                        "puuid": "PRIVATE_PUUID_SENTINEL",
                    },
                    "RANKED_FLEX_SR": {"tier": "UNRANKED", "division": "NA"},
                },
                "futureField": "DROP_ME",
            }

            summary = await fake.service.get_summary()
            ranked = await fake.service.get_ranked()

            self.assertEqual(
                summary.data,
                {
                    "level": 321,
                    "profile_icon_id": 42,
                    "xp_since_last_level": 900,
                    "xp_until_next_level": 100,
                },
            )
            self.assertEqual(
                ranked.data,
                {
                    "queues": [
                        {
                            "queue_type": "RANKED_SOLO_5x5",
                            "tier": "GOLD",
                            "division": "II",
                            "league_points": 23,
                            "wins": 14,
                            "losses": 9,
                        },
                        {
                            "queue_type": "RANKED_FLEX_SR",
                            "tier": "UNRANKED",
                            "division": "NA",
                        },
                    ]
                },
            )
            self.assertEqual(
                set(summary.as_dict()),
                {"data", "available", "stale", "last_synced", "error", "source", "from_cache", "errors"},
            )
            serialized = json.dumps([summary.as_dict(), ranked.as_dict()])
            for secret in ("PRIVATE_RIOT_ID_SENTINEL", "PRIVATE_PUUID_SENTINEL", "PRIVATE_TOKEN_SENTINEL", "DROP_ME"):
                self.assertNotIn(secret, serialized)

    async def test_masteries_and_challenges_are_bounded_allowlisted_and_failure_isolated(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[MASTERY_PATH] = [
                {
                    "championId": champion_id,
                    "championLevel": 7,
                    "championPoints": champion_id * 100,
                    "lastPlayTime": 1234,
                    "chestGranted": True,
                    "puuid": "PRIVATE_PUUID_SENTINEL",
                    "unknown": "DROP_ME",
                }
                for champion_id in range(1, 16)
            ]
            fake.responses[MASTERY_SCORE_PATH] = failed(payload={"token": "NO_STORE"})
            fake.responses[CHALLENGES_PATH] = {
                "challenges": [
                    {"challengeId": challenge_id, "value": 5, "level": "GOLD", "percentile": 12.5}
                    for challenge_id in range(10)
                ],
                "totalPoints": {"current": 765},
                "accountId": "DROP_ME",
            }
            fake.responses[CATEGORIES_PATH] = failed(payload={"credential": "NO_STORE"})

            masteries = await fake.service.get_masteries()
            challenges = await fake.service.get_challenges()

            self.assertEqual(len(masteries.data["champions"]), 10)
            self.assertIsNone(masteries.data["score"])
            self.assertTrue(masteries.available)
            self.assertFalse(masteries.stale)
            self.assertEqual(masteries.errors["score"], "http_error")
            self.assertEqual(len(challenges.data["challenges"]["challenges"]), 3)
            self.assertEqual(challenges.data["challenges"]["total_points"], 765)
            self.assertEqual(challenges.errors["categories"], "http_error")
            fake.connected = False
            offline_masteries = await fake.service.get_masteries(20)
            self.assertEqual(len(offline_masteries.data["champions"]), 10)
            self.assertTrue(offline_masteries.stale)
            offline_challenges = await fake.service.get_challenges(50)
            self.assertEqual(len(offline_challenges.data["challenges"]["challenges"]), 10)
            self.assertTrue(offline_challenges.stale)
            self.assertNotIn("timeline", fake.calls)

    async def test_overview_and_match_page_do_not_fetch_detail_or_timeline(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[SUMMARY_PATH] = {"summonerLevel": 88}
            page_path = f"{MATCHES_PATH}?begIndex=0&endIndex=19"
            fake.responses[page_path] = {
                "games": {
                    "gameCount": 29,
                    "games": [
                        {
                            "gameId": game_id,
                            "gameCreation": 1700000000000,
                            "gameDuration": 1200,
                            "queueId": 420,
                            "participantIdentities": [
                                {
                                    "participantId": 1,
                                    "player": {
                                        "puuid": fake.identity["puuid"],
                                        "summonerName": "PRIVATE_PLAYER_SENTINEL",
                                    },
                                }
                            ],
                            "participants": [
                                {
                                    "participantId": 1,
                                    "championId": 86,
                                    "stats": {
                                        "win": True,
                                        "kills": 4,
                                        "deaths": 2,
                                        "assists": 7,
                                        "unknown": "DROP_ME",
                                    },
                                }
                            ],
                            "rawCredential": "PRIVATE_CREDENTIAL_SENTINEL",
                        }
                        for game_id in range(100, 140)
                    ],
                },
            }

            summary = await fake.service.get_summary()
            page = await fake.service.get_matches()

            self.assertEqual(summary.data, {"level": 88})
            self.assertEqual(len(page.data["matches"]), 20)
            self.assertEqual(page.data["total"], 29)
            self.assertEqual(page.data["matches"][0]["champion_id"], 86)
            self.assertEqual(page.data["matches"][0]["win"], True)
            self.assertEqual(fake.calls, [SUMMARY_PATH, page_path])
            serialized = json.dumps(page.as_dict())
            for secret in ("PRIVATE_PLAYER_SENTINEL", "PRIVATE_CREDENTIAL_SENTINEL", "DROP_ME"):
                self.assertNotIn(secret, serialized)
            self.assertFalse(any("/games/" in path or "timeline" in path for path in fake.calls))

    async def test_match_page_uses_inclusive_validated_pagination_and_caps_output(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            path = f"{MATCHES_PATH}?begIndex=20&endIndex=24"
            fake.responses[path] = {
                "games": {
                    "games": [{"gameId": value, "gameCreation": value * 1000} for value in range(200, 230)]
                }
            }

            result = await fake.service.matches(limit=5, offset=20)

            self.assertEqual(fake.calls, [path])
            self.assertEqual(result.data["offset"], 20)
            self.assertEqual([item["game_id"] for item in result.data["matches"]], ["200", "201", "202", "203", "204"])

            for invalid in (0, 21, -1, True, 1.5):
                with self.subTest(limit=invalid), self.assertRaises(ValueError):
                    await fake.service.get_matches(limit=invalid)
            for invalid in (-1, True, 1.5, 1_000_001):
                with self.subTest(offset=invalid), self.assertRaises(ValueError):
                    await fake.service.matches(offset=invalid)
            self.assertEqual(fake.calls, [path])

            fake.connected = False
            stale = await fake.service.matches(limit=5, offset=20)
            self.assertTrue(stale.stale)
            self.assertTrue(stale.available)
            self.assertEqual(stale.source, "cache")
            self.assertEqual(stale.data["offset"], 20)
            self.assertEqual(fake.calls, [path])

    async def test_route_facing_method_names_and_signatures_are_stable(self):
        expected = {
            "get_summary": ([], {}),
            "get_ranked": ([], {}),
            "get_masteries": (["limit"], {"limit": 10}),
            "get_challenges": (["limit"], {"limit": 3}),
            "get_matches": (["limit"], {"limit": 20}),
            "get_match_detail": (["game_id"], {}),
        }
        for method_name, (parameters, defaults) in expected.items():
            with self.subTest(method=method_name):
                signature = inspect.signature(getattr(AccountStatsService, method_name))
                route_parameters = list(signature.parameters.values())[1:]
                self.assertEqual([parameter.name for parameter in route_parameters], parameters)
                self.assertEqual(
                    {parameter.name: parameter.default for parameter in route_parameters if parameter.default is not inspect.Parameter.empty},
                    defaults,
                )

    async def test_match_detail_is_explicit_allowlisted_and_cached_stale_offline(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            path = "/lol-match-history/v1/games/4242"
            fake.responses[path] = {
                "gameId": 4242,
                "gameCreation": 1700000000000,
                "gameDuration": 1400,
                "queueId": 420,
                "participants": [
                    {
                        "championId": 86,
                        "teamId": 100,
                        "puuid": "PRIVATE_PUUID_SENTINEL",
                        "summonerName": "PRIVATE_NAME_SENTINEL",
                        "stats": {
                            "win": True,
                            "kills": 2,
                            "deaths": 3,
                            "assists": 4,
                            "goldEarned": 9000,
                            "item0": 1055,
                            "item1": 0,
                            "item6": 3400,
                        },
                    }
                ],
                "headers": {"Authorization": "PRIVATE_HEADER_SENTINEL"},
            }

            detail = await fake.service.get_match_detail("4242")
            self.assertEqual(fake.calls, [path])
            self.assertEqual(detail.data["game_id"], "4242")
            self.assertEqual(detail.data["participants"][0]["champion_id"], 86)
            self.assertEqual(detail.data["participants"][0]["items"], [1055, 3400])
            self.assertNotIn("PRIVATE_NAME_SENTINEL", json.dumps(detail.as_dict()))
            self.assertNotIn("PRIVATE_HEADER_SENTINEL", json.dumps(detail.as_dict()))

            fake.connected = False
            stale = await fake.service.get_match_detail(4242)
            self.assertTrue(stale.available)
            self.assertTrue(stale.stale)
            self.assertEqual(stale.source, "cache")
            self.assertEqual(stale.data, detail.data)
            self.assertEqual(fake.calls, [path])

    async def test_offline_restart_loads_last_account_cache_without_persisting_identity(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[SUMMARY_PATH] = {"summonerLevel": 88, "puuid": fake.identity["puuid"]}
            fresh = await fake.service.get_summary()
            self.assertEqual(fresh.source, "lcu")

            pointer_path = Path(cache_dir) / "last-account.json"
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            self.assertRegex(pointer["cache_key"], r"^[a-f0-9]{64}$")
            self.assertNotIn(fake.identity["puuid"], pointer_path.read_text(encoding="utf-8"))

            offline_service = AccountStatsService(
                fake.request_json,
                lambda: False,
                cache_dir,
                dict,
            )
            stale = await offline_service.get_summary()

            self.assertEqual(stale.data, {"level": 88})
            self.assertEqual(stale.source, "cache")
            self.assertTrue(stale.stale)

    async def test_invalid_match_ids_never_issue_requests(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            for invalid in (0, -1, 1.25, True, "../4242", "4242?token=secret", "18446744073709551616", ""):
                with self.subTest(game_id=invalid), self.assertRaises((TypeError, ValueError)):
                    await fake.service.get_match_detail(invalid)
            self.assertEqual(fake.calls, [])

    async def test_match_timeline_is_explicit_lazy_and_normalized_without_player_identity(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[TIMELINE_PATH] = {
                "gameId": 4242,
                "frames": [
                    {
                        "timestamp": 60000,
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 65000,
                                "killerId": 2,
                                "victimId": 7,
                                "assistingParticipantIds": [3, "bad"],
                                "puuid": "PRIVATE_PUUID_SENTINEL",
                                "summonerName": "PRIVATE_NAME_SENTINEL",
                            },
                            {"type": "UNKNOWN_EVENT", "timestamp": 66000, "secret": "DROP_ME"},
                        ],
                    }
                ],
            }

            timeline = await fake.service.timeline(4242)

            self.assertEqual(fake.calls, [TIMELINE_PATH])
            self.assertEqual(
                timeline.data,
                {
                    "game_id": "4242",
                    "events": [
                        {
                            "type": "CHAMPION_KILL",
                            "timestamp": 65000,
                            "killer_id": 2,
                            "victim_id": 7,
                            "assisting_participant_ids": [3],
                        }
                    ],
                },
            )
            serialized = json.dumps(timeline.as_dict())
            for private in ("PRIVATE_PUUID_SENTINEL", "PRIVATE_NAME_SENTINEL", "DROP_ME"):
                self.assertNotIn(private, serialized)

    async def test_summary_stale_cache_and_corrupt_cache_are_safe(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[SUMMARY_PATH] = {
                "summonerLevel": 50,
                "displayName": "PRIVATE_RIOT_ID_SENTINEL",
                "puuid": fake.identity["puuid"],
                "token": "PRIVATE_TOKEN_SENTINEL",
            }
            fresh = await fake.service.get_summary()
            self.assertEqual(fresh.source, "lcu")
            self.assertFalse(fresh.stale)
            cache_file = next(Path(cache_dir).glob("account-*.json"))
            cache_json = cache_file.read_text(encoding="utf-8")
            for secret in ("PRIVATE_RIOT_ID_SENTINEL", "PRIVATE_PUUID_SENTINEL", "PRIVATE_TOKEN_SENTINEL"):
                self.assertNotIn(secret, cache_json)
            self.assertNotIn("FixtureAccount#TST", cache_file.name)
            self.assertEqual(list(Path(cache_dir).glob("*.tmp")), [])

            fake.responses[SUMMARY_PATH] = failed()
            stale = await fake.service.get_summary()
            self.assertTrue(stale.available)
            self.assertTrue(stale.stale)
            self.assertEqual(stale.data, fresh.data)
            self.assertIsNotNone(stale.last_synced)

            cache_file.write_text("{broken json", encoding="utf-8")
            fake.connected = False
            corrupt = await fake.service.get_summary()
            self.assertFalse(corrupt.available)
            self.assertFalse(corrupt.stale)
            self.assertEqual(corrupt.errors["cache"], "cache_corrupt")
            self.assertEqual(corrupt.error, "disconnected")

    async def test_summary_failure_does_not_block_other_account_sections(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[SUMMARY_PATH] = failed()
            fake.responses[RANKED_PATH] = {"queueMap": {}}

            summary = await fake.service.get_summary()
            ranked = await fake.service.get_ranked()

            self.assertFalse(summary.available)
            self.assertEqual(summary.error, "http_error")
            self.assertTrue(ranked.available)
            self.assertEqual(ranked.source, "lcu")
            self.assertEqual(fake.calls, [SUMMARY_PATH, RANKED_PATH])

    async def test_cache_is_account_scoped_and_rewrites_only_normalized_data(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            first = FakeLcu(cache_dir)
            first.responses[SUMMARY_PATH] = {"summonerLevel": 20}
            await first.service.get_summary()
            cache_file = next(Path(cache_dir).glob("account-*.json"))
            document = json.loads(cache_file.read_text(encoding="utf-8"))
            document["headers"] = {"Authorization": "RAW_HEADER_SENTINEL"}
            document["sections"]["ranked"] = {
                "data": {
                    "queues": [{"queue_type": "RANKED_SOLO_5x5", "tier": "GOLD", "token": "RAW_DTO_SENTINEL"}],
                    "rawResponse": "RAW_OBJECT_SENTINEL",
                },
                "synced_at": "2026-09-17T12:00:00+00:00",
            }
            document["details"] = {
                "77": {
                    "data": {
                        "gameId": 77,
                        "participants": [{"championId": 1, "summonerName": "RAW_NAME_SENTINEL"}],
                        "headers": {"Authorization": "RAW_DETAIL_SENTINEL"},
                    },
                    "synced_at": "2026-09-17T12:00:00+00:00",
                }
            }
            cache_file.write_text(json.dumps(document), encoding="utf-8")
            first.responses[RANKED_PATH] = {"queueMap": {}}

            await first.service.get_ranked()

            rewritten = cache_file.read_text(encoding="utf-8")
            for secret in (
                "RAW_HEADER_SENTINEL",
                "RAW_DTO_SENTINEL",
                "RAW_OBJECT_SENTINEL",
                "RAW_NAME_SENTINEL",
                "RAW_DETAIL_SENTINEL",
            ):
                self.assertNotIn(secret, rewritten)

            second = FakeLcu(
                cache_dir,
                connected=False,
                identity={
                    "riot_id": "DifferentFixture#TST",
                    "region": "EUW",
                    "puuid": "OTHER_FIXTURE_PUUID",
                },
            )
            isolated = await second.service.get_summary()
            self.assertFalse(isolated.available)
            self.assertFalse(isolated.stale)
            self.assertEqual(second.calls, [])

    async def test_runtime_exception_text_is_not_returned_or_cached(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            fake = FakeLcu(cache_dir)
            fake.responses[SUMMARY_PATH] = RuntimeError(
                "TOKEN_SENTINEL PRIVATE_ACCOUNT_SENTINEL C:\\private\\secret.txt"
            )

            result = await fake.service.get_summary()

            self.assertEqual(result.errors["summary"], "request_error")
            self.assertEqual(result.error, "request_error")
            rendered = json.dumps(result.as_dict())
            for secret in ("TOKEN_SENTINEL", "PRIVATE_ACCOUNT_SENTINEL", "secret.txt"):
                self.assertNotIn(secret, rendered)
            self.assertEqual(list(Path(cache_dir).glob("account-*.json")), [])


if __name__ == "__main__":
    unittest.main()
