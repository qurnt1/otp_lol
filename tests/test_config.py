import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import config


class ConfigTests(unittest.TestCase):
    def test_load_parameters_first_launch_is_safe_but_keeps_demo_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertFalse(loaded["auto_accept_enabled"])
        self.assertFalse(loaded["auto_pick_enabled"])
        self.assertFalse(loaded["auto_ban_enabled"])
        self.assertFalse(loaded["auto_summoners_enabled"])
        self.assertFalse(loaded["presets_enabled"])
        self.assertFalse(loaded["auto_play_again_enabled"])
        self.assertEqual(loaded["selected_pick_1"], "Garen")
        self.assertEqual(loaded["selected_pick_2"], "Lux")
        self.assertEqual(loaded["selected_pick_3"], "Ashe")
        self.assertEqual(loaded["selected_ban"], "Teemo")
        self.assertEqual(loaded["pick_slots"]["pick_1"]["spell_1"], "Heal")
        self.assertEqual(loaded["pick_slots"]["pick_1"]["spell_2"], "Flash")
        self.assertFalse(loaded["role_profiles"]["TOP"]["presets_enabled"])

    def test_load_parameters_migrates_legacy_region_to_manual_region(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps(
                    {
                        "region": "na",
                        "manual_summoner_name": "Testeur#EUW",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["manual_region"], "na")
        self.assertEqual(loaded["manual_summoner_name"], "Testeur#EUW")
        self.assertEqual(loaded["auto_detected_region"], "")
        self.assertEqual(loaded["auto_detected_riot_id"], "")
        self.assertIn("TOP", loaded["role_profiles"])
        self.assertEqual(loaded["role_profiles"]["TOP"]["selected_pick_1"], "")
        self.assertEqual(loaded["role_profiles"]["TOP"]["pick_slots"]["pick_1"]["spell_1"], "")

    def test_save_parameters_filters_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["manual_region"] = "kr"
            payload["pick_slots"]["pick_2"]["spell_1"] = "Ignite"
            payload["unexpected_key"] = "should_not_be_saved"

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                saved = config.save_parameters(payload)
                self.assertTrue(saved)
                written = json.loads(params_path.read_text(encoding="utf-8"))

        self.assertEqual(written["manual_region"], "kr")
        self.assertEqual(written["pick_slots"]["pick_2"]["spell_1"], "Ignite")
        self.assertNotIn("unexpected_key", written)
        self.assertEqual(set(written), set(config.DEFAULT_PARAMS))

    def test_load_parameters_normalizes_role_profiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps(
                    {
                        "selected_profile_role": "mid",
                        "role_profiles": {
                            "MIDDLE": {
                                "selected_pick_1": "Ahri",
                                "selected_ban": "Zed",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["selected_profile_role"], "MIDDLE")
        self.assertEqual(loaded["role_profiles"]["MIDDLE"]["selected_pick_1"], "Ahri")
        self.assertEqual(loaded["role_profiles"]["MIDDLE"]["selected_ban"], "Zed")
        self.assertTrue(loaded["role_profiles"]["MIDDLE"]["presets_enabled"])
        self.assertEqual(loaded["role_profiles"]["MIDDLE"]["selected_pick_2"], "")
        self.assertEqual(loaded["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["spell_1"], "")
        self.assertEqual(loaded["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["spell_2"], "")

    def test_load_parameters_supports_global_and_role_presets_toggle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps(
                    {
                        "presets_enabled": False,
                        "role_profiles": {
                            "TOP": {
                                "presets_enabled": True,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertFalse(loaded["presets_enabled"])
        self.assertTrue(loaded["role_profiles"]["TOP"]["presets_enabled"])
        self.assertFalse(loaded["role_profiles"]["JUNGLE"]["presets_enabled"])

    def test_load_parameters_migrates_legacy_global_spells_to_pick_slots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps(
                    {
                        "global_spell_1": "Smite",
                        "global_spell_2": "Flash",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        for slot_key in ("pick_1", "pick_2", "pick_3"):
            self.assertEqual(loaded["pick_slots"][slot_key]["spell_1"], "Smite")
            self.assertEqual(loaded["pick_slots"][slot_key]["spell_2"], "Flash")

    def test_load_parameters_migrates_legacy_role_spells_to_pick_slots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps(
                    {
                        "role_profiles": {
                            "JUNGLE": {
                                "spell_1": "Smite",
                                "spell_2": "Flash",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        for slot_key in ("pick_1", "pick_2", "pick_3"):
            self.assertEqual(loaded["role_profiles"]["JUNGLE"]["pick_slots"][slot_key]["spell_1"], "Smite")
            self.assertEqual(loaded["role_profiles"]["JUNGLE"]["pick_slots"][slot_key]["spell_2"], "Flash")

    def test_load_parameters_normalizes_preferred_stats_site(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(json.dumps({"preferred_stats_site": "LeagueOfGraphs"}), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["preferred_stats_site"], "leagueofgraphs")

    def test_load_parameters_normalizes_preferred_hotkey_site(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(json.dumps({"preferred_hotkey_site": "DeepLOL"}), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["preferred_hotkey_site"], "deeplol")

    def test_load_parameters_rejects_non_ingame_hotkey_site(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(json.dumps({"preferred_hotkey_site": "leagueofgraphs"}), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["preferred_hotkey_site"], "porofessor")

    def test_load_parameters_normalizes_custom_hotkeys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(
                json.dumps(
                    {
                        "hotkey_toggle_window": " ALT+SHIFT+C ",
                        "hotkey_open_site": " CTRL+ALT+P ",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["hotkey_toggle_window"], "alt+shift+c")
        self.assertEqual(loaded["hotkey_open_site"], "ctrl+alt+p")

    def test_load_parameters_normalizes_theme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.json"
            params_path.write_text(json.dumps({"theme": "FLATLY"}), encoding="utf-8")

            with patch.object(config, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["theme"], "flatly")

    def test_import_export_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["preferred_stats_site"] = "deeplol"
            payload["preferred_hotkey_site"] = "porofessor"
            payload["hotkey_toggle_window"] = "alt+shift+c"
            payload["hotkey_open_site"] = "ctrl+alt+p"
            payload["role_profiles"]["TOP"]["pick_slots"]["pick_1"]["spell_1"] = "Teleport"
            payload["role_profiles"]["TOP"]["pick_slots"]["pick_1"]["spell_2"] = "Flash"

            exported = config.export_parameters_to_file(str(export_path), payload)
            self.assertTrue(exported)

            imported = config.import_parameters_from_file(str(export_path))

        self.assertEqual(imported["preferred_stats_site"], "deeplol")
        self.assertEqual(imported["preferred_hotkey_site"], "porofessor")
        self.assertEqual(imported["hotkey_toggle_window"], "alt+shift+c")
        self.assertEqual(imported["hotkey_open_site"], "ctrl+alt+p")
        self.assertEqual(imported["role_profiles"]["TOP"]["pick_slots"]["pick_1"]["spell_1"], "Teleport")
        self.assertEqual(imported["role_profiles"]["TOP"]["pick_slots"]["pick_1"]["spell_2"], "Flash")


if __name__ == "__main__":
    unittest.main()
