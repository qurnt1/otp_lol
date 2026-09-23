import tempfile
import unittest
from unittest.mock import patch

from src.lcu.assets import LcuAssetService
from src.lcu.client import LcuResponse
from src.lcu.static_data import (
    CATALOG_ENDPOINTS,
    GAME_VERSION_PATH,
    LcuStaticDataService,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"test-image-data"


class StaticDataFixture:
    def __init__(self, champion_path="/lol-game-data/assets/v1/champion-icons/86.png"):
        self.paths = {
            ("champion", 86): champion_path,
            ("spell", 4): "/lol-game-data/assets/v1/spells/flash.png",
            ("perk", 8010): "/lol-game-data/assets/v1/perk-images/conqueror.png",
            ("item", 1055): "/lol-game-data/assets/v1/items/1055.png",
            ("skin", 86013): "/lol-game-data/assets/v1/skins/garen-13.png",
            ("skin_splash", 86013): "/lol-game-data/assets/v1/skins/garen-13-splash.png",
        }

    def asset_path(self, kind, asset_id, *, variant="default"):
        if kind == "skin" and variant == "splash":
            return self.paths.get(("skin_splash", asset_id))
        return self.paths.get((kind, asset_id))


class FakeJsonClient:
    async def request(self, path):
        if path == GAME_VERSION_PATH:
            payload = "16.18.1.123"
        else:
            name = next(
                name for name, endpoint in CATALOG_ENDPOINTS.items() if endpoint == path
            )
            payload = {
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
                        "summonerSpellId": 4,
                        "iconPath": "/lol-game-data/assets/v1/spells/flash.png",
                    }
                ],
                "perks": [
                    {
                        "id": 8010,
                        "iconPath": "/lol-game-data/assets/v1/perk-images/conqueror.png",
                    }
                ],
                "items": [{"itemId": 1055, "iconPath": "/lol-game-data/assets/v1/items/1055.png"}],
                "maps": [{"mapId": 11, "name": "Summoner's Rift"}],
                "queues": [{"queueId": 420, "name": "Ranked Solo"}],
            }[name]
        return LcuResponse(200, 1, payload=payload, content_type="application/json")


class LcuAssetServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolves_only_catalogue_ids_and_returns_verified_image_bytes(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            static_data = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(await static_data.refresh())
            requests = []

            async def request_bytes(path):
                requests.append(path)
                return LcuResponse(
                    200, 1, payload=PNG, content_type="image/png; charset=binary"
                )

            service = LcuAssetService(request_bytes, static_data)
            image = await service.get_asset("champion", 86)
            skin = await service.get_asset("skin", 86013)
            splash = await service.get_asset("skin", 86013, variant="splash")
            item = await service.get_asset("item", 1055)

            self.assertEqual(image.content, PNG)
            self.assertEqual(image.content_type, "image/png")
            self.assertEqual(skin.content, PNG)
            self.assertEqual(splash.content, PNG)
            self.assertEqual(item.content, PNG)
            self.assertEqual(
                requests,
                [
                    "/lol-game-data/assets/v1/champion-icons/86.png",
                    "/lol-game-data/assets/v1/skins/garen-13.png",
                    "/lol-game-data/assets/v1/skins/garen-13-splash.png",
                    "/lol-game-data/assets/v1/items/1055.png",
                ],
            )

            offline = LcuStaticDataService(FakeJsonClient().request, cache_dir)
            self.assertTrue(offline.load_from_cache())
            disconnected_requests = []

            async def disconnected(path):
                disconnected_requests.append(path)
                return LcuResponse(None, 0, error="disconnected")

            cached = await LcuAssetService(disconnected, offline).get_asset("champion", 86)
            self.assertEqual(cached.content, PNG)
            self.assertEqual(disconnected_requests, [])

    async def test_unknown_or_non_numeric_ids_do_not_issue_requests(self):
        static_data = StaticDataFixture()
        requests = []

        async def request_bytes(path):
            requests.append(path)
            return LcuResponse(200, 1, payload=PNG, content_type="image/png")

        service = LcuAssetService(request_bytes, static_data)

        self.assertIsNone(await service.get_asset("champion", 999))
        self.assertIsNone(await service.get_asset("champion", "86"))
        self.assertIsNone(await service.get_asset("champion", True))
        self.assertEqual(requests, [])

    async def test_rejects_traversal_and_non_lcu_paths_before_request(self):
        for unsafe_path in (
            "/lol-game-data/assets/v1/../secrets.png",
            "/lol-game-data/assets/v1/%2e%2e/secrets.png",
            "/lol-game-data/assets/v1/%25252e%25252e/secrets.png",
            "https://example.test/lol-game-data/assets/v1/image.png",
            "/lol-game-data/assets/v1/image.png?token=secret",
            "/lol-game-data/assets-elsewhere/image.png",
            "//[",
        ):
            with self.subTest(path=unsafe_path):
                static_data = StaticDataFixture(champion_path=unsafe_path)
                requests = []

                async def request_bytes(path, requests=requests):
                    requests.append(path)
                    return LcuResponse(200, 1, payload=PNG, content_type="image/png")

                service = LcuAssetService(request_bytes, static_data)
                self.assertIsNone(await service.get_asset("champion", 86))
                self.assertEqual(requests, [])

    async def test_rejects_oversized_wrong_mime_and_mismatched_image_content(self):
        static_data = StaticDataFixture()
        responses = [
            LcuResponse(200, 1, payload=PNG * 2, content_type="image/png"),
            LcuResponse(
                200, 1, payload=b"<html>challenge</html>", content_type="text/html"
            ),
            LcuResponse(200, 1, payload=b"not a png", content_type="image/png"),
        ]

        async def request_bytes(_path):
            return responses.pop(0)

        service = LcuAssetService(request_bytes, static_data)
        with patch("src.lcu.assets.MAX_ASSET_BYTES", len(PNG)):
            self.assertIsNone(await service.get_asset("champion", 86))
            self.assertIsNone(await service.get_asset("champion", 86))
            self.assertIsNone(await service.get_asset("champion", 86))

    async def test_missing_lcu_asset_is_returned_as_none_for_caller_fallback(self):
        static_data = StaticDataFixture()

        async def not_found(_path):
            return LcuResponse(404, 1, error="http_error")

        service = LcuAssetService(not_found, static_data)
        self.assertIsNone(await service.get_asset("champion", 86))

    async def test_accepts_supported_jpeg_mime_and_signature(self):
        static_data = StaticDataFixture()

        async def request_bytes(_path):
            return LcuResponse(
                200, 1, payload=b"\xff\xd8\xffdata", content_type="image/jpeg"
            )

        service = LcuAssetService(request_bytes, static_data)
        image = await service.get_asset("perk", 8010)
        self.assertEqual(image.content_type, "image/jpeg")


if __name__ == "__main__":
    unittest.main()
