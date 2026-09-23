import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.lcu.client import LcuResponse
from src.lcu.static_data import (
    CATALOG_ENDPOINTS,
    GAME_VERSION_PATH,
    LcuStaticDataService,
)


def catalogue_payloads():
    return {
        "champions": [
            {
                "id": 86,
                "name": "Garen",
                "squarePortraitPath": "/lol-game-data/assets/v1/champion-icons/86.png",
                "skins": [
                    {
                        "skinId": 86013,
                        "tilePath": "/lol-game-data/assets/v1/skins/garen-13.png",
                        "splashPath": "/lol-game-data/assets/v1/skins/garen-13-splash.png",
                    }
                ],
            }
        ],
        "spells": [
            {
                "summonerSpellId": "4",
                "name": "Flash",
                "iconPath": "/lol-game-data/assets/v1/spells/flash.png",
            }
        ],
        "perks": [
            {
                "id": "8010",
                "name": "Conqueror",
                "iconPath": "/lol-game-data/assets/v1/perk-images/conqueror.png",
            }
        ],
        "items": {
            "1001": {"itemId": 1001, "name": "Boots"},
            "1055": {"itemId": 1055, "name": "Doran Blade", "iconPath": "/lol-game-data/assets/v1/items/1055.png"},
        },
        "maps": [{"mapId": 11, "name": "Summoner's Rift"}],
        "queues": [{"queueId": 420, "name": "Ranked Solo"}],
    }


class FakeJsonClient:
    def __init__(self, version="16.18.1.123", catalogues=None, overrides=None):
        self.version = version
        self.catalogues = catalogue_payloads() if catalogues is None else catalogues
        self.overrides = overrides or {}
        self.calls = []

    async def request(self, path):
        self.calls.append(path)
        value = self.overrides.get(path)
        if value is not None:
            return value
        if path == GAME_VERSION_PATH:
            payload = self.version
        else:
            name = next(
                name for name, endpoint in CATALOG_ENDPOINTS.items() if endpoint == path
            )
            payload = self.catalogues[name]
        return LcuResponse(200, 1.0, payload=payload, content_type="application/json")


class LcuStaticDataServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_fetches_version_and_all_six_catalogues_before_installing(
        self,
    ):
        client = FakeJsonClient()
        with tempfile.TemporaryDirectory() as cache_dir:
            service = LcuStaticDataService(client.request, cache_dir)

            self.assertTrue(await service.refresh())

            self.assertEqual(
                client.calls, [GAME_VERSION_PATH, *CATALOG_ENDPOINTS.values()]
            )
            bootstrap_status = service.status["catalogs"]
            self.assertTrue(bootstrap_status["champions"]["available"])
            for name in ("spells", "perks", "items", "maps", "queues"):
                self.assertTrue(bootstrap_status[name]["available"])
                self.assertEqual(bootstrap_status[name]["source"], "lcu")
                self.assertEqual(bootstrap_status[name]["version"], "16.18.1.123")
            snapshot_dirs = list(Path(cache_dir).glob("snapshot-*"))
            self.assertEqual(len(snapshot_dirs), 1)
            self.assertTrue((snapshot_dirs[0] / "manifest.json").is_file())
            self.assertEqual(
                {
                    path.stem
                    for path in (snapshot_dirs[0] / "catalogues").glob("*.json")
                },
                set(CATALOG_ENDPOINTS),
            )
            self.assertEqual(service.load_champions()[0]["name"], "Garen")
            self.assertEqual(service.load_items()["1001"]["name"], "Boots")
            self.assertEqual(service.load_perks()[0]["id"], "8010")
            self.assertEqual(service.load_summoner_spells()[0]["name"], "Flash")
            self.assertEqual(service.load_maps()[0]["mapId"], 11)
            self.assertEqual(service.load_queues()[0]["queueId"], 420)
            self.assertEqual(service.status["source"], "lcu")
            self.assertEqual(service.status["game_version"], "16.18.1.123")
            self.assertTrue(
                all(
                    value["source"] == "lcu"
                    for value in service.status["catalogs"].values()
                )
            )
            json.dumps(service.status)

    async def test_refresh_rejects_non_integer_catalogue_ids(self):
        catalogues = catalogue_payloads()
        catalogues["champions"] = [
            {
                "id": 86.5,
                "name": "Malformed champion ID",
                "squarePortraitPath": "/lol-game-data/assets/v1/champion-icons/86.png",
            }
        ]
        with tempfile.TemporaryDirectory() as cache_dir:
            service = LcuStaticDataService(
                FakeJsonClient(catalogues=catalogues).request,
                cache_dir,
            )
            self.assertFalse(await service.refresh())
            self.assertIsNone(service.asset_path("champion", 86))

    async def test_skin_splash_uses_only_splash_specific_catalogue_paths(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            service = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await service.refresh())

            self.assertEqual(
                service.asset_path("skin", 86013, variant="splash"),
                "/lol-game-data/assets/v1/skins/garen-13-splash.png",
            )
            self.assertIsNone(service.asset_path("spell", 4, variant="splash"))

    async def test_item_asset_path_comes_from_the_local_item_catalogue(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            service = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await service.refresh())

            self.assertEqual(
                service.asset_path("item", 1055),
                "/lol-game-data/assets/v1/items/1055.png",
            )

    async def test_cache_load_is_synchronous_offline_and_status_identifies_each_source(
        self,
    ):
        with tempfile.TemporaryDirectory() as cache_dir:
            online = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await online.refresh())
            disconnected_response = LcuResponse(None, 0.1, error="disconnected")

            async def offline_request(_path):
                return disconnected_response

            offline = LcuStaticDataService(offline_request, cache_dir)
            loaded_files = []
            real_json_load = json.load

            def track_json_load(file, *args, **kwargs):
                loaded_files.append(Path(file.name).name)
                return real_json_load(file, *args, **kwargs)

            with patch("src.lcu.static_data.json.load", side_effect=track_json_load):
                self.assertTrue(offline.load_from_cache())
                self.assertEqual(loaded_files, ["manifest.json", "champions.json"])
                self.assertEqual(offline.load_champions()[0]["id"], 86)
                self.assertEqual(offline.load_items()["1001"]["name"], "Boots")
                self.assertEqual(offline.load_items()["1001"]["name"], "Boots")
            self.assertEqual(loaded_files.count("items.json"), 1)
            self.assertNotIn("spells.json", loaded_files)
            self.assertFalse(await offline.refresh())

            status = offline.status
            self.assertFalse(status["connected"])
            self.assertEqual(status["source"], "cache")
            self.assertEqual(status["cache_version"], "16.18.1.123")
            self.assertTrue(status["catalogs"]["champions"]["available"])
            for name in ("spells", "perks", "maps", "queues"):
                self.assertTrue(status["catalogs"][name]["available"])
                self.assertEqual(status["catalogs"][name]["source"], "cache")
                self.assertEqual(status["catalogs"][name]["version"], "16.18.1.123")
            self.assertTrue(status["catalogs"]["items"]["available"])
            self.assertTrue(
                all(
                    entry["version"] == "16.18.1.123"
                    for entry in status["catalogs"].values()
                    if entry["available"]
                )
            )

    async def test_malformed_or_empty_catalogues_never_replace_a_valid_snapshot(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            original = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await original.refresh())

            for catalogue_name, endpoint in CATALOG_ENDPOINTS.items():
                with self.subTest(catalogue=catalogue_name):
                    malformed = {} if catalogue_name == "items" else []
                    client = FakeJsonClient(
                        version="16.18.2.456",
                        overrides={endpoint: LcuResponse(200, 1, payload=malformed)},
                    )
                    service = LcuStaticDataService(client.request, cache_dir)
                    self.assertFalse(await service.refresh())
                    self.assertEqual(service.status["game_version"], "16.18.2.456")
                    self.assertEqual(service.load_champions()[0]["name"], "Garen")
                    self.assertEqual(service.status["game_version"], "16.18.2.456")
                    self.assertEqual(service.status["cache_version"], "16.18.1.123")
                    self.assertEqual(len(list(Path(cache_dir).glob("snapshot-*"))), 1)
                    self.assertEqual(list(Path(cache_dir).glob(".staging-*")), [])

            restored = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(restored.load_from_cache())
            self.assertEqual(restored.status["game_version"], "16.18.1.123")

    async def test_nonempty_catalogues_without_usable_records_never_replace_cache(self):
        malformed_catalogues = {
            "champions": [{"id": "broken", "name": "Garen"}],
            "spells": [{"summonerSpellId": "4"}],
            "perks": [{"id": "8010"}],
            "items": {"1001": {"itemId": 1001}},
            "maps": [{"mapId": 11}],
            "queues": [{"queueId": 420}],
        }
        with tempfile.TemporaryDirectory() as cache_dir:
            original = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await original.refresh())

            for catalogue_name, payload in malformed_catalogues.items():
                with self.subTest(catalogue=catalogue_name):
                    endpoint = CATALOG_ENDPOINTS[catalogue_name]
                    client = FakeJsonClient(
                        version="16.18.2.456",
                        overrides={endpoint: LcuResponse(200, 1, payload=payload)},
                    )
                    service = LcuStaticDataService(client.request, cache_dir)

                    self.assertFalse(await service.refresh())
                    self.assertEqual(service.status["cache_version"], "16.18.1.123")
                    self.assertEqual(len(list(Path(cache_dir).glob("snapshot-*"))), 1)

    async def test_champion_catalogue_requires_a_name_consumed_by_the_api(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            original = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await original.refresh())
            client = FakeJsonClient(
                version="16.18.2.456",
                overrides={
                    CATALOG_ENDPOINTS["champions"]: LcuResponse(
                        200,
                        1,
                        payload=[{"id": 86, "title": "The Might of Demacia"}],
                    )
                },
            )

            self.assertFalse(
                await LcuStaticDataService(client.request, cache_dir).refresh()
            )

    async def test_pruning_keeps_three_complete_versions_when_newer_snapshot_is_corrupt(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            for patch in range(1, 5):
                service = LcuStaticDataService(
                    FakeJsonClient(version=f"16.18.{patch}.123").request, cache_dir
                )
                self.assertTrue(await service.refresh())

            corrupt_snapshot = next(
                directory
                for directory in Path(cache_dir).glob("snapshot-*")
                if json.loads((directory / "manifest.json").read_text(encoding="utf-8"))[
                    "game_version"
                ]
                == "16.18.4.123"
            )
            (corrupt_snapshot / "catalogues" / "items.json").write_text(
                "{}", encoding="utf-8"
            )

            newest = LcuStaticDataService(
                FakeJsonClient(version="16.18.5.123").request, cache_dir
            )
            self.assertTrue(await newest.refresh())
            snapshots = LcuStaticDataService(FakeJsonClient().request, cache_dir)._discover_snapshots()
            versions = {snapshot["game_version"] for _saved_at, snapshot in snapshots}

            self.assertEqual(versions, {"16.18.2.123", "16.18.3.123", "16.18.5.123"})

    async def test_invalid_version_and_request_failures_leave_cache_intact(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            original = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await original.refresh())
            bad_version = FakeJsonClient(version={"version": "../outside"})
            service = LcuStaticDataService(bad_version.request, cache_dir)

            self.assertFalse(await service.refresh())
            self.assertTrue(service.load_from_cache())
            self.assertEqual(service.status["cache_version"], "16.18.1.123")

    async def test_only_three_valid_versions_are_retained(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            for patch in range(1, 5):
                service = LcuStaticDataService(
                    FakeJsonClient(version=f"16.18.{patch}.123").request, cache_dir
                )
                self.assertTrue(await service.refresh())
                await asyncio.sleep(0.002)

            cache_service = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            snapshots = cache_service._discover_snapshots()
            versions = {snapshot["game_version"] for _saved_at, snapshot in snapshots}
            self.assertEqual(len(versions), 3)
            self.assertEqual(versions, {"16.18.2.123", "16.18.3.123", "16.18.4.123"})

    async def test_corrupt_lazy_catalogue_falls_back_per_catalogue_version(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            first = LcuStaticDataService(
                FakeJsonClient(version="16.18.1.123").request,
                cache_dir,
            )
            self.assertTrue(await first.refresh())
            await asyncio.sleep(0.002)
            latest = LcuStaticDataService(
                FakeJsonClient(version="16.18.2.123").request,
                cache_dir,
            )
            self.assertTrue(await latest.refresh())

            latest_snapshot = next(
                directory
                for directory in Path(cache_dir).glob("snapshot-*")
                if json.loads(
                    (directory / "manifest.json").read_text(encoding="utf-8")
                )["game_version"]
                == "16.18.2.123"
            )
            (latest_snapshot / "catalogues" / "items.json").write_text(
                "{}", encoding="utf-8"
            )

            offline = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(offline.load_from_cache())
            self.assertEqual(offline.status["game_version"], "16.18.2.123")
            self.assertEqual(offline.load_items()["1001"]["name"], "Boots")
            self.assertEqual(offline.status["catalogs"]["items"]["source"], "cache")
            self.assertEqual(
                offline.status["catalogs"]["items"]["version"], "16.18.1.123"
            )

    async def test_corrupt_lazy_catalogue_without_older_snapshot_is_unavailable(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            online = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await online.refresh())
            snapshot_dir = next(Path(cache_dir).glob("snapshot-*"))
            (snapshot_dir / "catalogues" / "items.json").write_text(
                "{}", encoding="utf-8"
            )

            offline = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(offline.load_from_cache())
            self.assertIsNone(offline.load_items())
            self.assertFalse(offline.status["catalogs"]["items"]["available"])

    async def test_corrupt_snapshot_is_ignored_without_network_during_cache_load(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            client = FakeJsonClient()
            service = LcuStaticDataService(client.request, cache_dir)
            self.assertTrue(await service.refresh())
            corrupt_dir = Path(cache_dir, "snapshot-corrupt")
            corrupt_dir.mkdir()
            (corrupt_dir / "manifest.json").write_text("{broken", encoding="utf-8")

            def no_network(_path):
                raise AssertionError("load_from_cache must not request LCU data")

            restored = LcuStaticDataService(no_network, cache_dir)
            self.assertTrue(restored.load_from_cache())
            self.assertEqual(restored.load_champions()[0]["name"], "Garen")
            self.assertEqual(
                client.calls, [GAME_VERSION_PATH, *CATALOG_ENDPOINTS.values()]
            )


if __name__ == "__main__":
    unittest.main()
