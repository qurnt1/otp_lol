import unittest
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from PIL import Image

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


class DataDragonSkinCatalogTests(unittest.TestCase):
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
