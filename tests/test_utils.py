import unittest
from unittest.mock import Mock, patch

from src.services.updates import (
    check_for_updates,
    extract_highlights_section,
    extract_version_from_readme,
    format_highlights_for_popup,
    is_newer_version,
    normalize_version,
)
from src.services.urls import (
    build_dpm_url,
    build_deeplol_url,
    build_hotkey_site_url,
    build_hotkey_provider_home_url,
    build_leagueofgraphs_url,
    build_opgg_url,
    build_porofessor_url,
    build_stats_site_url,
    is_valid_riot_id,
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
            build_dpm_url("euw", "MonCompte#EUW"),
            "https://dpm.lol/MonCompte-EUW/",
        )
        self.assertEqual(
            build_dpm_url("euw", "MonCompte#EUW", ingame=True),
            "https://dpm.lol/MonCompte-EUW/live",
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
            build_stats_site_url("dpm", "euw", "MonCompte#EUW"),
            "https://dpm.lol/MonCompte-EUW/",
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
            build_hotkey_site_url("dpm", "euw", "MonCompte#EUW"),
            "https://dpm.lol/MonCompte-EUW/live",
        )
        self.assertEqual(build_hotkey_site_url("porofessor", "", ""), "https://porofessor.gg/")
        self.assertEqual(build_hotkey_site_url("opgg", "", "invalid"), "https://op.gg/")
        self.assertEqual(build_hotkey_site_url("deeplol", "invalid", "Player#TAG"), "https://www.deeplol.gg/")
        self.assertIsNone(build_hotkey_site_url("unknown", "euw", "Player#TAG"))

    def test_riot_id_validation(self):
        self.assertTrue(is_valid_riot_id("MonCompte#EUW"))
        self.assertFalse(is_valid_riot_id("MonCompte-EUW"))
        self.assertFalse(is_valid_riot_id("MonCompte"))

    def test_extract_version_from_readme_supports_version_highlights_header(self):
        readme_text = (
            "## Version 11.0 Highlights\n\n"
            "Version `11.0` focuses on updates.\n"
        )

        self.assertEqual(extract_version_from_readme(readme_text), "11.0")

    def test_extract_highlights_section_returns_matching_block(self):
        readme_text = (
            "## Version 11.0 Highlights\n\n"
            "Version `11.0` focuses on updates.\n\n"
            "- `Feature A`\n"
            "  Description A.\n\n"
            "## Version 10.0 Highlights\n\n"
            "Old notes.\n"
        )

        self.assertIn("Feature A", extract_highlights_section(readme_text, "11.0"))
        self.assertNotIn("Old notes", extract_highlights_section(readme_text, "11.0"))

    def test_format_highlights_for_popup_converts_markdown_lightly(self):
        formatted = format_highlights_for_popup("- `Feature A`\n  Description A.")

        self.assertIn("• Feature A", formatted)
        self.assertIn("Description A.", formatted)

    def test_check_for_updates_returns_version_and_highlights(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "tag_name": "v12.0",
            "name": "OTP LOL 12.0",
            "body": "- `Feature A`\n  Description A.",
            "html_url": "https://github.com/qurnt1/otp_lol/releases/tag/v12.0",
            "assets": [
                {
            "name": "OTP-LOL-Setup.exe",
            "browser_download_url": "https://github.com/qurnt1/otp_lol/releases/download/v12.0/OTP-LOL-Setup.exe",
                },
                {
            "name": "OTP-LOL-Setup.exe.sha256",
            "browser_download_url": "https://github.com/qurnt1/otp_lol/releases/download/v12.0/OTP-LOL-Setup.exe.sha256",
                }
            ],
        }

        with patch("src.services.updates.requests.get", return_value=response):
            update_info = check_for_updates()

        self.assertIsNotNone(update_info)
        self.assertEqual(update_info["version"], normalize_version("12.0"))
        self.assertEqual(update_info["release_url"], response.json.return_value["html_url"])
        self.assertEqual(update_info["asset_url"], response.json.return_value["assets"][0]["browser_download_url"])
        self.assertEqual(update_info["checksum_name"], "OTP-LOL-Setup.exe.sha256")
        self.assertEqual(update_info["checksum_url"], response.json.return_value["assets"][1]["browser_download_url"])
        self.assertIn("`Feature A`", update_info["highlights"])
        self.assertIn("Description A.", update_info["highlights"])

    def test_check_for_updates_ignores_release_without_valid_version(self):
        response = Mock(status_code=200)
        response.json.return_value = {"tag_name": "latest", "body": "notes"}

        with patch("src.services.updates.requests.get", return_value=response):
            self.assertIsNone(check_for_updates())


if __name__ == "__main__":
    unittest.main()
