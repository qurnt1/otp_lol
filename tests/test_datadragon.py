import json
import tempfile
import threading
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch

import requests
from PIL import Image

from src.config.constants import SUMMONER_SPELL_MAP
from src.core.datadragon import DataDragon
from src.integrations.communitydragon import CommunityDragonClient


class FakeResponse:
    def __init__(self, payload, *, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self.content = json.dumps(payload).encode("utf-8")
        self.text = json.dumps(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class ObservedEvent(threading.Event):
    def __init__(self, waiter_started):
        super().__init__()
        self.waiter_started = waiter_started

    def wait(self, timeout=None):
        self.waiter_started.set()
        return super().wait(timeout)


class DataDragonSkinCatalogTests(unittest.TestCase):
    @staticmethod
    def _loaded_garen():
        dd = DataDragon()
        dd.loaded = True
        dd.version = "16.18.1"
        dd.by_norm_name = {"garen": 86}
        dd.by_id = {86: {"id": "Garen", "name": "Garen", "key": "86", "image": {"full": "Garen.png"}}}
        dd.name_by_id = {86: "Garen"}
        return dd

    @patch("src.core.datadragon.get_cache_dirs")
    def test_load_cached_reads_metadata_without_network(self, _get_cache_dirs):
        dd = DataDragon()
        payload = {
            "version": "15.1.1",
            "by_norm_name": {"garen": 86},
            "by_id": {"86": {"id": "Garen", "name": "Garen", "key": "86"}},
            "name_by_id": {"86": "Garen"},
        }
        with patch("src.core.datadragon.DDRAGON_CACHE_FILE") as cache_file:
            cache_file = str(cache_file)
            with patch("builtins.open", mock_open(read_data=json.dumps(payload))), patch(
                "src.core.datadragon.os.path.exists", return_value=True
            ):
                self.assertTrue(dd.load_cached())

        self.assertTrue(dd.loaded)
        self.assertEqual(dd.resolve_champion("Garen"), 86)

    @patch("src.core.datadragon.get_cache_dirs")
    def test_valid_local_cache_survives_dns_failure_without_repeated_version_requests(self, _get_cache_dirs):
        dd = DataDragon()
        payload = {
            "version": "16.18.1",
            "by_norm_name": {"garen": 86},
            "by_id": {"86": {"id": "Garen", "name": "Garen", "key": "86"}},
            "name_by_id": {"86": "Garen"},
        }
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory, "ddragon.json")
            cache_file.write_text(json.dumps(payload), encoding="utf-8")
            with (
                patch("src.core.datadragon.DDRAGON_CACHE_FILE", str(cache_file)),
                patch("src.core.datadragon.requests.get", side_effect=requests.ConnectionError("DNS unavailable")) as get,
            ):
                self.assertTrue(dd.load_cached())
                with self.assertLogs(level="WARNING") as logs:
                    dd.refresh()
                    dd.refresh()

        self.assertEqual(dd.version, "16.18.1")
        self.assertEqual(dd.id_to_name(86), "Garen")
        get.assert_called_once()
        self.assertEqual(len(logs.records), 1)
        self.assertIn("Network unavailable", logs.records[0].getMessage())

    def test_refresh_loads_the_matching_versioned_catalogue_before_requesting_network(self):
        dd = self._loaded_garen()
        replacement = {
            "version": "16.18.2",
            "by_norm_name": {"lux": 99},
            "by_id": {"99": {"id": "Lux", "name": "Lux", "key": "99"}},
            "name_by_id": {"99": "Lux"},
        }
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory, "ddragon.json")
            Path(f"{cache_file}.16.18.2.json").write_text(json.dumps(replacement), encoding="utf-8")
            with (
                patch("src.core.datadragon.DDRAGON_CACHE_FILE", str(cache_file)),
                patch.object(dd, "_fetch_latest_version", return_value="16.18.2"),
                patch.object(dd, "_load_remote_version", side_effect=AssertionError("cache should be used")),
            ):
                dd.refresh()

        self.assertEqual(dd.version, "16.18.2")
        self.assertEqual(dd.id_to_name(99), "Lux")

    def test_champion_splash_uses_catalog_slug_without_fetching_champion_detail(self):
        dd = self._loaded_garen()
        splash = Image.new("RGBA", (4, 2))
        with (
            patch.object(dd, "get_champion_detail", side_effect=AssertionError("detail requested")) as get_detail,
            patch.object(dd, "get_remote_image", return_value=splash) as get_remote_image,
        ):
            result = dd.get_champion_splash(86)

        self.assertIs(result, splash)
        get_detail.assert_not_called()
        self.assertIn("/Garen_0.jpg", get_remote_image.call_args.args[0])

    def test_concurrent_champion_detail_requests_share_one_download(self):
        dd = self._loaded_garen()
        request_started = threading.Event()
        second_waiting = threading.Event()
        release_request = threading.Event()
        response = FakeResponse({"data": {"Garen": {"id": "Garen", "name": "Garen", "skins": []}}})
        call_count = 0
        count_lock = threading.Lock()

        def fetch_detail(*_args, **_kwargs):
            nonlocal call_count
            with count_lock:
                call_count += 1
            request_started.set()
            release_request.wait(timeout=2)
            return response

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("src.core.datadragon.SKINS_CACHE_DIR", directory),
            patch("src.core.datadragon.Event", side_effect=lambda: ObservedEvent(second_waiting)),
            patch("src.core.datadragon.requests.get", side_effect=fetch_detail),
        ):
            results = []
            first = threading.Thread(target=lambda: results.append(dd.get_champion_detail(86)))
            second = threading.Thread(target=lambda: results.append(dd.get_champion_detail(86)))
            first.start()
            self.assertTrue(request_started.wait(timeout=2))
            second.start()
            self.assertTrue(second_waiting.wait(timeout=2))
            release_request.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(call_count, 1)
        self.assertEqual(results, [{"id": "Garen", "name": "Garen", "skins": []}] * 2)

    def test_concurrent_communitydragon_detail_requests_share_one_download(self):
        dd = self._loaded_garen()
        request_started = threading.Event()
        second_waiting = threading.Event()
        release_request = threading.Event()
        response = FakeResponse({"skins": []})
        call_count = 0

        def fetch_detail(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            request_started.set()
            release_request.wait(timeout=2)
            return response

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("src.core.datadragon.SKINS_CACHE_DIR", directory),
            patch("src.core.datadragon.Event", side_effect=lambda: ObservedEvent(second_waiting)),
            patch("src.core.datadragon.requests.get", side_effect=fetch_detail),
        ):
            results = []
            first = threading.Thread(target=lambda: results.append(dd.get_cdragon_champion_detail(86)))
            second = threading.Thread(target=lambda: results.append(dd.get_cdragon_champion_detail(86)))
            first.start()
            self.assertTrue(request_started.wait(timeout=2))
            second.start()
            self.assertTrue(second_waiting.wait(timeout=2))
            release_request.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(call_count, 1)
        self.assertEqual(results, [{"skins": []}] * 2)

    def test_champion_detail_failure_is_negative_cached(self):
        dd = self._loaded_garen()
        with (
            patch("src.core.datadragon.monotonic", return_value=100),
            patch("src.core.datadragon.requests.get", side_effect=requests.HTTPError("detail unavailable")) as get,
        ):
            self.assertIsNone(dd.get_champion_detail(86))
            # Isolate the per-champion negative cache from the global network cooldown.
            dd._network_cooldown_until = 0
            self.assertIsNone(dd.get_champion_detail(86))

        get.assert_called_once()

    def test_network_cooldown_expires_and_allows_a_new_request(self):
        dd = self._loaded_garen()
        now = [100.0]
        response = FakeResponse({"ok": True})
        with (
            patch("src.core.datadragon.monotonic", side_effect=lambda: now[0]),
            patch(
                "src.core.datadragon.requests.get",
                side_effect=[requests.Timeout("offline"), response],
            ) as get,
        ):
            self.assertIsNone(dd._request_get("https://ddragon.example/first"))
            now[0] += 44
            self.assertIsNone(dd._request_get("https://ddragon.example/during-cooldown"))
            now[0] += 2
            self.assertIs(dd._request_get("https://ddragon.example/after-cooldown"), response)

        self.assertEqual(get.call_count, 2)

    def test_current_version_image_cache_is_reused_without_network(self):
        dd = self._loaded_garen()
        image_bytes = BytesIO()
        Image.new("RGBA", (3, 2), (20, 40, 60, 255)).save(image_bytes, format="PNG")
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory, dd.version, "skin_86_13.img")
            cache_path.parent.mkdir()
            cache_path.write_bytes(image_bytes.getvalue())
            with (
                patch("src.core.datadragon.SKINS_CACHE_DIR", directory),
                patch("src.core.datadragon.requests.get") as get,
            ):
                image = dd.get_remote_image("https://ddragon.example/skin.png", cache_key="skin_86_13")

        self.assertIsNotNone(image)
        self.assertEqual(image.getpixel((0, 0)), (20, 40, 60, 255))
        get.assert_not_called()

    def test_new_version_download_does_not_reuse_previous_version_as_fresh(self):
        dd = self._loaded_garen()
        dd.version = "16.18.2"
        old_png = BytesIO()
        Image.new("RGBA", (2, 2), (200, 0, 0, 255)).save(old_png, format="PNG")
        new_png = BytesIO()
        Image.new("RGBA", (2, 2), (0, 0, 200, 255)).save(new_png, format="PNG")
        response = SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=new_png.getvalue(),
        )

        with tempfile.TemporaryDirectory() as directory:
            old_path = Path(directory, "16.18.1", "skin_86_13.img")
            old_path.parent.mkdir()
            old_path.write_bytes(old_png.getvalue())
            with (
                patch("src.core.datadragon.SKINS_CACHE_DIR", directory),
                patch("src.core.datadragon.requests.get", return_value=response) as get,
            ):
                image = dd.get_remote_image(
                    "https://ddragon.example/cdn/16.18.2/skin.png", cache_key="skin_86_13"
                )
                new_path = Path(directory, "16.18.2", "skin_86_13.img")
                new_exists = new_path.exists()
                with Image.open(new_path) as cached:
                    cached_pixel = cached.getpixel((0, 0))

        self.assertEqual(image.getpixel((0, 0)), (0, 0, 200, 255))
        self.assertEqual(get.call_args.args[0], "https://ddragon.example/cdn/16.18.2/skin.png")
        self.assertTrue(new_exists)
        self.assertEqual(cached_pixel, (0, 0, 200, 255))

    def test_previous_version_image_is_used_only_after_network_failure(self):
        dd = self._loaded_garen()
        dd.version = "16.18.2"
        dd._network_cooldown_until = 10**9
        old_png = BytesIO()
        Image.new("RGBA", (2, 2), (200, 0, 0, 255)).save(old_png, format="PNG")

        with tempfile.TemporaryDirectory() as directory:
            old_path = Path(directory, "16.18.1", "skin_86_13.img")
            old_path.parent.mkdir()
            old_path.write_bytes(old_png.getvalue())
            with patch("src.core.datadragon.SKINS_CACHE_DIR", directory):
                image = dd.get_remote_image("https://ddragon.example/cdn/16.18.2/skin.png", cache_key="skin_86_13")
                current_path = Path(directory, "16.18.2", "skin_86_13.img")
                current_exists = current_path.exists()

        self.assertEqual(image.getpixel((0, 0)), (200, 0, 0, 255))
        self.assertFalse(current_exists)

    def test_downloading_one_champion_does_not_mark_sibling_images_fresh(self):
        dd = self._loaded_garen()
        payload = BytesIO()
        Image.new("RGBA", (2, 2), (0, 100, 20, 255)).save(payload, format="PNG")
        response = SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=payload.getvalue(),
        )

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("src.core.datadragon.ICONS_CACHE_DIR", directory),
                patch("src.core.datadragon.requests.get", return_value=response),
            ):
                self.assertIsNotNone(dd.get_champion_icon(86))

            version_dir = Path(directory, dd.version)
            versioned_files = list(version_dir.iterdir())
            legacy_marker_exists = (Path(directory) / "dd_version.txt").exists()

        self.assertEqual(versioned_files, [version_dir / "Garen.png"])
        self.assertFalse(legacy_marker_exists)

    def test_summoner_spell_data_is_mapped_by_numeric_key(self):
        dd = self._loaded_garen()
        spells = {
            "SummonerFlash": {"name": "Flash", "key": 4, "image": {"full": "SummonerFlash.png"}},
            "SummonerBarrier": {"name": "Barrier", "key": "21", "image": {"full": "SummonerBarrier.png"}},
            "SummonerNew": {"name": "New Spell", "key": 999, "image": {"full": "New.png"}},
            "SummonerNone": {"name": "None", "key": 0, "image": {"full": "None.png"}},
        }
        with patch("src.core.datadragon.requests.get", return_value=FakeResponse({"data": spells})):
            dd.load_summoners()

        self.assertEqual(
            dd.summoner_data,
            {"Flash": "SummonerFlash.png", "Barrier": "SummonerBarrier.png"},
        )
        self.assertEqual(set(dd.summoner_data), {name for name, spell_id in SUMMONER_SPELL_MAP.items() if spell_id in {4, 21}})

    def test_corrupt_cached_image_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory, "corrupt.img")
            cache_path.write_bytes(b"not an image")
            with patch("src.core.datadragon.Image.open", side_effect=Image.DecompressionBombError):
                self.assertIsNone(DataDragon._read_cached_image(str(cache_path)))

    def test_skin_details_persist_by_version_and_champion_for_offline_picker(self):
        dd = self._loaded_garen()
        champion_detail = {
            "data": {
                "Garen": {
                    "id": "Garen",
                    "name": "Garen",
                    "skins": [{"id": "86013", "num": 13, "name": "God-King Garen"}],
                }
            }
        }
        cdragon_detail = {"skins": [{"id": 86013, "num": 13, "name": "God-King Garen"}]}

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("src.core.datadragon.SKINS_CACHE_DIR", directory),
            patch(
                "src.core.datadragon.requests.get",
                side_effect=[FakeResponse(champion_detail), FakeResponse(cdragon_detail)],
            ) as get,
        ):
            self.assertEqual(len(dd.get_skin_catalog(86)), 1)

            offline_dd = self._loaded_garen()
            catalog = offline_dd.get_skin_catalog(86)
            cached_catalog = offline_dd.get_cached_skin_catalog(86)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(len(cached_catalog), 1)
        self.assertEqual(catalog[0]["skin_name"], "God-King Garen")
        self.assertEqual(get.call_count, 2)

    @patch("src.integrations.communitydragon.requests.get")
    def test_communitydragon_rejects_non_image_content_type_with_lowercase_header(self, mock_get):
        payload = BytesIO()
        Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(payload, format="PNG")
        mock_get.return_value = SimpleNamespace(
            status_code=200,
            headers={"content-type": "text/html"},
            content=payload.getvalue(),
        )

        self.assertIsNone(
            CommunityDragonClient.fetch_image(
                "lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png"
            )
        )

    def test_rune_asset_path_is_converted_to_communitydragon_url(self):
        url = DataDragon._communitydragon_asset_url(
            "/lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png"
        )

        self.assertEqual(
            url,
            (
                "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
                "v1/perk-images/styles/7204_resolve.png"
            ),
        )

    @patch("src.core.datadragon.requests.get")
    def test_rune_perk_icon_path_uses_communitydragon_perks_index(self, mock_get):
        dd = DataDragon()
        mock_get.return_value = FakeResponse(
            [
                {
                    "id": 8010,
                    "name": "Conqueror",
                    "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/Precision/Conqueror/Conqueror.png",
                },
                {
                    "id": "8214",
                    "name": "Summon Aery",
                    "iconPath": "/lol-game-data/assets/v1/perk-images/Styles/Sorcery/SummonAery/SummonAery.png",
                },
            ]
        )

        self.assertEqual(
            dd.get_rune_perk_icon_path(8010),
            "/lol-game-data/assets/v1/perk-images/Styles/Precision/Conqueror/Conqueror.png",
        )
        self.assertEqual(
            dd.get_rune_perk_icon_path("8214"),
            "/lol-game-data/assets/v1/perk-images/Styles/Sorcery/SummonAery/SummonAery.png",
        )
        self.assertEqual(dd.get_rune_perk_name(8010), "Conqueror")
        self.assertEqual(dd.get_rune_perk_name("8214"), "Summon Aery")
        mock_get.assert_called_once_with(
            "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/perks.json",
            timeout=8,
        )

    def test_rune_button_composite_supports_rectangular_button_size(self):
        dd = DataDragon()
        dd.get_rune_perk_icon = lambda path: Image.new("RGBA", (64, 64), (30, 80, 255, 255))
        dd.get_rune_style_icon = lambda path: Image.new("RGBA", (64, 64), (0, 220, 120, 255))

        composite = dd.compose_rune_button_icon("keystone.png", "style.png", size=(44, 30))

        self.assertIsNotNone(composite)
        self.assertEqual(composite.size, (44, 30))
        self.assertNotEqual(composite.getpixel((38, 15))[3], 0)

    def test_cdragon_asset_path_is_converted_to_raw_url(self):
        url = DataDragon.cdragon_url_from_asset_path(
            "/lol-game-data/assets/ASSETS/Characters/Garen/Skins/Skin13/Images/garen_splash_tile_13.jpg"
        )

        self.assertEqual(
            url,
            (
                "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
                "assets/characters/garen/skins/skin13/images/garen_splash_tile_13.jpg"
            ),
        )

    def test_rune_asset_url_rejects_absolute_and_traversal_paths(self):
        for path in (
            "https://example.com/foo.png",
            "http://127.0.0.1:1234/foo",
            "http://169.254.169.254/latest/meta-data",
            "//attacker.example/foo",
            "file:///C:/Windows/win.ini",
            "../../../foo",
            "lol-game-data/assets/%2e%2e/private.png",
            "lol-game-data/assets/%252e%252e/private.png",
            "lol-game-data/assets/v1/%2e%2e/%2e%2e/private.png",
            "lol-game-data/assets/v1/%5c%5cattacker.example/private.png",
            "lol-game-data/assets/v1/" + ("a" * 2050) + ".png",
            "lol-game-data/assets/v1/bad%00name.png",
        ):
            self.assertIsNone(DataDragon._communitydragon_asset_url(path), path)

        self.assertIsNotNone(
            DataDragon._communitydragon_asset_url(
                "lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png"
            )
        )

    def test_cdragon_rune_asset_path_is_converted_to_raw_url(self):
        url = DataDragon.cdragon_url_from_asset_path(
            "/lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png"
        )

        self.assertEqual(
            url,
            (
                "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
                "v1/perk-images/styles/7204_resolve.png"
            ),
        )

    @patch("src.core.datadragon.requests.get")
    def test_skin_catalog_includes_tile_url_from_cdragon(self, mock_get):
        dd = DataDragon()
        dd.loaded = True
        dd.version = "1.0.0"
        dd.by_norm_name = {"garen": 86}
        dd.by_id = {86: {"id": "Garen", "name": "Garen", "key": "86"}}
        dd.name_by_id = {86: "Garen"}

        mock_get.side_effect = [
            FakeResponse(
                {
                    "data": {
                        "Garen": {
                            "id": "Garen",
                            "name": "Garen",
                            "skins": [
                                {"id": "86013", "num": 13, "name": "God-King Garen", "parentSkin": None}
                            ],
                        }
                    }
                }
            ),
            FakeResponse(
                {
                    "skins": [
                        {
                            "id": 86013,
                            "num": 13,
                            "name": "God-King Garen",
                            "tilePath": (
                                "/lol-game-data/assets/ASSETS/Characters/Garen/Skins/Skin13/Images/"
                                "garen_splash_tile_13.jpg"
                            ),
                            "splashPath": (
                                "/lol-game-data/assets/ASSETS/Characters/Garen/Skins/Skin13/Images/"
                                "garen_splash_centered_13.jpg"
                            ),
                        }
                    ]
                }
            ),
        ]

        catalog = dd.get_skin_catalog("Garen")

        self.assertEqual(len(catalog), 1)
        self.assertEqual(
            catalog[0]["tile_url"],
            (
                "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
                "assets/characters/garen/skins/skin13/images/garen_splash_tile_13.jpg"
            ),
        )
        self.assertEqual(
            dd.get_skin_preview_url("Garen", skin_id=86013),
            catalog[0]["tile_url"],
        )


if __name__ == "__main__":
    unittest.main()
