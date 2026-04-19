import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import config


class ConfigTests(unittest.TestCase):
    def test_load_parameters_first_launch_creates_default_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_invalid_json_to_first_launch_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text("{ invalid json", encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_when_config_version_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(json.dumps({"selected_pick_1": "Ahri"}), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_when_config_version_mismatches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["config_version"] = "9.0"
            payload["selected_pick_1"] = "Ahri"
            params_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_when_schema_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            del payload["pick_slots"]
            params_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_accepts_current_exact_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["preferred_stats_site"] = "dpm"
            payload["preferred_hotkey_site"] = "dpm"
            params_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, payload)

    def test_save_parameters_filters_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["manual_region"] = "kr"
            payload["pick_slots"]["pick_2"]["spell_1"] = "Ignite"
            payload["preferred_stats_site"] = "dpm"
            payload["preferred_hotkey_site"] = "dpm"
            payload["unexpected_key"] = "should_not_be_saved"

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                saved = config.save_parameters(payload)
                self.assertTrue(saved)
                written = json.loads(params_path.read_text(encoding="utf-8"))

        self.assertEqual(written["manual_region"], "kr")
        self.assertEqual(written["pick_slots"]["pick_2"]["spell_1"], "Ignite")
        self.assertEqual(written["preferred_stats_site"], "dpm")
        self.assertEqual(written["preferred_hotkey_site"], "dpm")
        self.assertNotIn("unexpected_key", written)
        self.assertEqual(set(written), set(config.DEFAULT_PARAMS))

    def test_import_export_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["preferred_stats_site"] = "dpm"
            payload["preferred_hotkey_site"] = "dpm"
            payload["hotkey_toggle_window"] = "alt+shift+c"
            payload["hotkey_open_site"] = "ctrl+alt+p"

            exported = config.export_parameters_to_file(str(export_path), payload)
            self.assertTrue(exported)

            imported = config.import_parameters_from_file(str(export_path))

        self.assertEqual(imported["preferred_stats_site"], "dpm")
        self.assertEqual(imported["preferred_hotkey_site"], "dpm")
        self.assertEqual(imported["hotkey_toggle_window"], "alt+shift+c")
        self.assertEqual(imported["hotkey_open_site"], "ctrl+alt+p")


if __name__ == "__main__":
    unittest.main()
