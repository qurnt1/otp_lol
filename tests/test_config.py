import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import config


class ConfigTests(unittest.TestCase):
    def test_load_parameters_migrates_legacy_region_to_manual_region(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps({
                    "region": "na",
                    "manual_summoner_name": "Testeur#EUW",
                }),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["manual_region"], "na")
        self.assertEqual(loaded["manual_summoner_name"], "Testeur#EUW")
        self.assertEqual(loaded["auto_detected_region"], "")
        self.assertEqual(loaded["auto_detected_riot_id"], "")

    def test_save_parameters_filters_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = config.DEFAULT_PARAMS.copy()
            payload["manual_region"] = "kr"
            payload["unexpected_key"] = "should_not_be_saved"

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                saved = config.save_parameters(payload)
                self.assertTrue(saved)
                written = json.loads(params_path.read_text(encoding="utf-8"))

        self.assertEqual(written["manual_region"], "kr")
        self.assertNotIn("unexpected_key", written)
        self.assertEqual(set(written), set(config.DEFAULT_PARAMS))


if __name__ == "__main__":
    unittest.main()
