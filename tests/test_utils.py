import unittest
from unittest.mock import Mock, patch

from src.utils import (
    build_deeplol_url,
    build_hotkey_site_url,
    build_ingame_stats_url,
    build_leagueofgraphs_url,
    build_opgg_url,
    build_player_stats_url,
    build_porofessor_url,
    build_stats_site_url,
    check_for_updates,
    is_valid_riot_id,
    is_newer_version,
    normalize_version,
)


class UtilsTests(unittest.TestCase):
    def test_semantic_version_comparison(self):
        self.assertFalse(is_newer_version("6.1.0", "6.1"))
        self.assertFalse(is_newer_version("v6.1", "6.1.0"))
        self.assertTrue(is_newer_version("6.2.0", "6.1.9"))

    def test_build_urls_normalize_riot_id(self):
        self.assertEqual(
            build_opgg_url("euw", "MonCompte#EUW"),
            "https://op.gg/fr/lol/summoners/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_porofessor_url("euw", "MonCompte#EUW"),
            "https://porofessor.gg/fr/live/euw/MonCompte-EUW/ranked-only",
        )
        self.assertEqual(
            build_leagueofgraphs_url("euw", "MonCompte#EUW"),
            "https://www.leagueofgraphs.com/fr/summoner/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_deeplol_url("euw", "MonCompte#EUW"),
            "https://www.deeplol.gg/summoner/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_deeplol_url("euw", "MonCompte#EUW", ingame=True),
            "https://www.deeplol.gg/summoner/euw/MonCompte-EUW/ingame",
        )
        self.assertEqual(
            build_opgg_url("euw", "MonCompte#EUW", ingame=True),
            "https://op.gg/fr/lol/summoners/euw/MonCompte-EUW/ingame",
        )

    def test_build_stats_site_url_uses_selected_provider(self):
        self.assertEqual(
            build_stats_site_url("porofessor", "euw", "MonCompte#EUW"),
            "https://op.gg/fr/lol/summoners/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_stats_site_url("leagueofgraphs", "euw", "MonCompte#EUW"),
            "https://www.leagueofgraphs.com/fr/summoner/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_stats_site_url("deeplol", "euw", "MonCompte#EUW"),
            "https://www.deeplol.gg/summoner/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_stats_site_url("unknown", "euw", "MonCompte#EUW"),
            "https://op.gg/fr/lol/summoners/euw/MonCompte-EUW",
        )

    def test_build_hotkey_site_url_uses_selected_provider(self):
        self.assertEqual(
            build_hotkey_site_url("porofessor", "euw", "MonCompte#EUW"),
            "https://porofessor.gg/fr/live/euw/MonCompte-EUW/ranked-only",
        )
        self.assertEqual(
            build_hotkey_site_url("deeplol", "euw", "MonCompte#EUW"),
            "https://www.deeplol.gg/summoner/euw/MonCompte-EUW/ingame",
        )
        self.assertEqual(
            build_hotkey_site_url("opgg", "euw", "MonCompte#EUW"),
            "https://op.gg/fr/lol/summoners/euw/MonCompte-EUW/ingame",
        )
        self.assertEqual(
            build_hotkey_site_url("leagueofgraphs", "euw", "MonCompte#EUW"),
            "https://porofessor.gg/fr/live/euw/MonCompte-EUW/ranked-only",
        )

    def test_build_player_and_ingame_aliases(self):
        self.assertEqual(
            build_player_stats_url("deeplol", "euw", "MonCompte#EUW"),
            "https://www.deeplol.gg/summoner/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_ingame_stats_url("opgg", "euw", "MonCompte#EUW"),
            "https://op.gg/fr/lol/summoners/euw/MonCompte-EUW/ingame",
        )

    def test_riot_id_validation(self):
        self.assertTrue(is_valid_riot_id("MonCompte#EUW"))
        self.assertFalse(is_valid_riot_id("MonCompte-EUW"))
        self.assertFalse(is_valid_riot_id("MonCompte"))

    def test_check_for_updates_uses_semantic_comparison(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"tag_name": "v9.0.0"}

        with patch("src.utils.requests.get", return_value=response):
            self.assertIsNone(check_for_updates())

        response.json.return_value = {"tag_name": "v9.1.0"}
        with patch("src.utils.requests.get", return_value=response):
            self.assertEqual(check_for_updates(), normalize_version("v9.1.0"))


if __name__ == "__main__":
    unittest.main()
