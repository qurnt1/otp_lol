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

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_first_launch_defaults_include_demo_spells_and_skins(self):
        slots = config.FIRST_LAUNCH_PARAMS["pick_slots"]

        self.assertEqual(slots["pick_1"]["spell_1"], "Flash")
        self.assertEqual(slots["pick_1"]["spell_2"], "Ignite")
        self.assertEqual(slots["pick_1"]["skin_mode"], "fixed")
        self.assertEqual(slots["pick_1"]["skin_name"], "God-King Garen")

        self.assertEqual(slots["pick_2"]["spell_1"], "Flash")
        self.assertEqual(slots["pick_2"]["spell_2"], "Teleport")
        self.assertEqual(slots["pick_2"]["skin_mode"], "random")
        self.assertEqual(slots["pick_2"]["random_skin_name"], "Star Guardian Lux")
        self.assertEqual(
            [skin["skin_name"] for skin in slots["pick_2"]["random_skin_pool"]],
            ["Star Guardian Lux", "Battle Academia Lux"],
        )

        self.assertEqual(slots["pick_3"]["spell_1"], "Flash")
        self.assertEqual(slots["pick_3"]["spell_2"], "Barrier")
        self.assertEqual(slots["pick_3"]["skin_mode"], "fixed")
        self.assertEqual(slots["pick_3"]["skin_name"], "Queen Ashe")

    def test_pick_slot_defaults_include_rune_fields(self):
        from src.config.settings import build_pick_slot_defaults
        slots = build_pick_slot_defaults()
        for slot_key in ("pick_1", "pick_2", "pick_3"):
            self.assertIn("rune_page_id", slots[slot_key])
            self.assertIn("rune_page_name", slots[slot_key])
            self.assertIn("rune_auto_apply", slots[slot_key])
            self.assertEqual(slots[slot_key]["rune_page_id"], 0)
            self.assertEqual(slots[slot_key]["rune_page_name"], "")
            self.assertTrue(slots[slot_key]["rune_auto_apply"])

    def test_default_params_no_longer_has_global_auto_runes_enabled(self):
        self.assertNotIn("auto_runes_enabled", config.DEFAULT_PARAMS)
        self.assertNotIn("auto_runes_enabled", config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_invalid_json_to_first_launch_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text("{ invalid json", encoding="utf-8")
            skins_cache_dir = Path(tmpdir) / "otp_lol_skins"
            skins_cache_dir.mkdir()
            (skins_cache_dir / "old_skin.img").write_text("cached", encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)), patch.object(
                config._settings, "SKINS_CACHE_DIR", str(skins_cache_dir)
            ):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)
        self.assertFalse((skins_cache_dir / "old_skin.img").exists())

    def test_load_parameters_resets_when_config_version_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(json.dumps({"selected_pick_1": "Ahri"}), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_when_config_version_mismatches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["config_version"] = "9.0"
            payload["selected_pick_1"] = "Ahri"
            params_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_resets_when_schema_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            del payload["pick_slots"]
            params_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)

    def test_load_parameters_accepts_current_exact_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["preferred_stats_site"] = "dpm"
            payload["preferred_hotkey_site"] = "dpm"
            params_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
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

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
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
