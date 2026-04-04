import unittest
from unittest.mock import Mock, patch

from src.utils import (
    build_opgg_url,
    build_porofessor_url,
    check_for_updates,
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
            "https://www.op.gg/lol/summoners/euw/MonCompte-EUW",
        )
        self.assertEqual(
            build_porofessor_url("euw", "MonCompte#EUW"),
            "https://porofessor.gg/fr/live/euw/MonCompte-EUW",
        )

    def test_check_for_updates_uses_semantic_comparison(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"tag_name": "v6.1.0"}

        with patch("src.utils.requests.get", return_value=response):
            self.assertIsNone(check_for_updates())

        response.json.return_value = {"tag_name": "v6.2.0"}
        with patch("src.utils.requests.get", return_value=response):
            self.assertEqual(check_for_updates(), normalize_version("v6.2.0"))


if __name__ == "__main__":
    unittest.main()
