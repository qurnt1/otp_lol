import unittest
from unittest.mock import patch

from src.core.datadragon import DataDragon


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DataDragonSkinCatalogTests(unittest.TestCase):
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
        self.assertEqual(
            dd.get_skin_picker_url("Garen", skin_id=86013),
            (
                "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
                "assets/characters/garen/skins/skin13/images/garen_splash_centered_13.jpg"
            ),
        )

    @patch("src.core.datadragon.requests.get")
    def test_skin_picker_url_skips_uncentered_when_centered_missing(self, mock_get):
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
                            "uncenteredSplashPath": (
                                "/lol-game-data/assets/ASSETS/Characters/Garen/Skins/Skin13/Images/"
                                "garen_splash_uncentered_13.jpg"
                            ),
                        }
                    ]
                }
            ),
        ]

        self.assertEqual(
            dd.get_skin_picker_url("Garen", skin_id=86013),
            "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Garen_13.jpg",
        )


if __name__ == "__main__":
    unittest.main()
