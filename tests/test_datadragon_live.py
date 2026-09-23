"""Opt-in checks against Riot's current public Data Dragon assets."""

import os
import unittest

import requests
from PIL import Image
from io import BytesIO

from src.config.constants import (
    SUMMONER_SPELL_MAP,
    URL_DD_CHAMPIONS,
    URL_DD_IMG_CHAMP,
    URL_DD_IMG_SPELL,
    URL_DD_SKIN_SPLASH,
    URL_DD_SUMMONERS,
    URL_DD_VERSIONS,
)


@unittest.skipUnless(os.environ.get("OTP_LOL_LIVE_DDRAGON") == "1", "requires explicit live Data Dragon opt-in")
class LiveDataDragonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        response = requests.get(URL_DD_VERSIONS, timeout=15)
        response.raise_for_status()
        cls.version = response.json()[0]

        champions = requests.get(URL_DD_CHAMPIONS.format(version=cls.version), timeout=20)
        champions.raise_for_status()
        cls.champions = champions.json()["data"]

        summoners = requests.get(URL_DD_SUMMONERS.format(version=cls.version), timeout=20)
        summoners.raise_for_status()
        cls.summoners = summoners.json()["data"]

    @staticmethod
    def _assert_image(response):
        response.raise_for_status()
        with Image.open(BytesIO(response.content)) as image:
            image.verify()

    def test_current_garen_metadata_icon_and_splash_are_available(self):
        garen = next(champion for champion in self.champions.values() if champion.get("key") == "86")
        self.assertEqual(garen["name"], "Garen")
        self.assertEqual(garen["id"], "Garen")
        self.assertEqual(garen["image"]["full"], "Garen.png")

        icon_url = URL_DD_IMG_CHAMP.format(version=self.version, filename=garen["image"]["full"])
        splash_url = URL_DD_SKIN_SPLASH.format(champion=garen["id"], skin_num=0)
        self._assert_image(requests.get(icon_url, timeout=20))
        self._assert_image(requests.get(splash_url, timeout=20))

    def test_supported_summoner_spell_ids_names_and_icons_are_current(self):
        entries_by_key = {}
        for entry in self.summoners.values():
            try:
                entries_by_key[int(entry.get("key"))] = entry
            except (TypeError, ValueError):
                continue

        for expected_name, spell_id in SUMMONER_SPELL_MAP.items():
            if spell_id == 0:
                continue
            with self.subTest(spell=expected_name, version=self.version):
                entry = entries_by_key[spell_id]
                self.assertEqual(entry["name"], expected_name)
                image_full = entry["image"]["full"]
                self.assertTrue(image_full)
                image_url = URL_DD_IMG_SPELL.format(version=self.version, filename=image_full)
                self._assert_image(requests.get(image_url, timeout=20))


if __name__ == "__main__":
    unittest.main()
