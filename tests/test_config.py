import copy
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import tomli_w

from src import config


class ConfigTests(unittest.TestCase):
    def test_load_parameters_first_launch_creates_default_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            skins_cache_dir = Path(tmpdir) / "skins"
            skins_cache_dir.mkdir()
            cached_skin = skins_cache_dir / "preview.img"
            cached_skin.write_text("cached", encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)), patch.object(
                config._settings, "SKINS_CACHE_DIR", str(skins_cache_dir)
            ):
                loaded = config.load_parameters()
            persisted = tomllib.loads(params_path.read_text(encoding="utf-8"))
            cached_skin_exists = cached_skin.exists()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)
        self.assertEqual(persisted, config.FIRST_LAUNCH_PARAMS)
        self.assertTrue(cached_skin_exists)

    def test_demo_presets_are_separate_from_blank_first_launch(self):
        slots = config.FIRST_LAUNCH_PARAMS["pick_slots"]

        self.assertEqual(config.DEMO_PRESETS["selected_pick_1"], "Garen")
        self.assertEqual(config.DEMO_PRESETS["pick_slots"]["pick_1"]["spell_1"], "Flash")
        self.assertEqual(config.DEMO_PRESETS["pick_slots"]["pick_2"]["skin_mode"], "random")
        self.assertEqual(config.DEMO_PRESETS["pick_slots"]["pick_3"]["skin_name"], "Queen Ashe")
        self.assertEqual(slots["pick_1"]["spell_1"], "")
        self.assertEqual(slots["pick_1"]["spell_2"], "")
        self.assertEqual(slots["pick_1"]["skin_mode"], "none")
        self.assertEqual(slots["pick_1"]["skin_name"], "")
        self.assertEqual(config.FIRST_LAUNCH_PARAMS["selected_pick_1"], "")
        self.assertEqual(config.FIRST_LAUNCH_PARAMS["selected_ban"], "")

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
        self.assertTrue(config.FIRST_LAUNCH_PARAMS["skin_automation_enabled"])

    def test_window_geometry_has_desktop_defaults(self):
        self.assertEqual(config.FIRST_LAUNCH_PARAMS["window_width"], 1100)
        self.assertEqual(config.FIRST_LAUNCH_PARAMS["window_height"], 760)
        self.assertFalse(config.FIRST_LAUNCH_PARAMS["window_maximized"])

    def test_load_parameters_backs_up_invalid_toml_before_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            invalid_content = "{ invalid toml"
            params_path.write_text(invalid_content, encoding="utf-8")
            skins_cache_dir = Path(tmpdir) / "otp_lol_skins"
            skins_cache_dir.mkdir()
            (skins_cache_dir / "old_skin.img").write_text("cached", encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)), patch.object(
                config._settings, "SKINS_CACHE_DIR", str(skins_cache_dir)
            ):
                loaded = config.load_parameters()
            backup_content = Path(f"{params_path}.bak").read_text(encoding="utf-8")
            cache_exists = (skins_cache_dir / "old_skin.img").exists()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)
        self.assertFalse(cache_exists)
        self.assertEqual(backup_content, invalid_content)

    def test_load_parameters_preserves_settings_when_app_version_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload.pop("config_version")
            payload["selected_pick_1"] = "Ahri"
            params_path.write_text(tomli_w.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["selected_pick_1"], "Ahri")
        self.assertEqual(loaded["config_version"], config._settings.CURRENT_VERSION)
        self.assertEqual(loaded["config_schema_version"], config._settings.CONFIG_SCHEMA_VERSION)

    def test_load_parameters_preserves_settings_across_app_version_upgrade(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["config_version"] = "9.0"
            payload["selected_pick_1"] = "Ahri"
            params_path.write_text(tomli_w.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded["selected_pick_1"], "Ahri")
        self.assertEqual(loaded["config_version"], config._settings.CURRENT_VERSION)

    def test_load_parameters_fills_missing_fields_without_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            del payload["pick_slots"]
            payload["selected_pick_1"] = "Ahri"
            params_path.write_text(tomli_w.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()
            backup_exists = Path(f"{params_path}.bak").exists()

        self.assertEqual(loaded["selected_pick_1"], "Ahri")
        self.assertIn("pick_1", loaded["pick_slots"])
        self.assertFalse(backup_exists)

    def test_load_parameters_migrates_complete_schema_five_settings_without_losing_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload.update(
                {
                    "config_schema_version": 5,
                    "config_version": "10.0",
                    "auto_accept_enabled": True,
                    "auto_pick_enabled": True,
                    "auto_ban_enabled": True,
                    "auto_summoners_enabled": True,
                    "presets_enabled": True,
                    "selected_pick_1": "Garen",
                    "selected_pick_2": "Lux",
                    "selected_pick_3": "Ashe",
                    "selected_ban": "Teemo",
                    "theme": "flatly",
                    "summoner_name_auto_detect": False,
                    "manual_summoner_name": "Player#EUW",
                    "manual_region": "kr",
                    "preferred_stats_site": "dpm",
                    "preferred_hotkey_site": "deeplol",
                    "hotkey_toggle_window": "ctrl+shift+c",
                    "hotkey_open_site": "ctrl+shift+p",
                    "skin_automation_enabled": False,
                    "window_x": 51,
                    "window_y": 72,
                    "window_width": 1280,
                    "window_height": 840,
                    "window_maximized": True,
                    "main_skin_mode_override": "none",
                    "main_skin_mode_overrides": {
                        "pick_1": "fixed",
                        "pick_2": "inherit",
                    },
                }
            )
            payload["pick_slots"]["pick_1"].update(
                {
                    "spell_1": "Flash",
                    "spell_2": "Ignite",
                    "skin_mode": "none",
                    "skin_id": 86013,
                    "skin_name": "God-King Garen",
                    "skin_num": 13,
                    "rune_page_id": 4,
                    "rune_page_name": "Precision",
                    "rune_auto_apply": False,
                    "rune_keystone_path": "/perk/8005.png",
                    "rune_sub_style_icon_path": "/style/8100.png",
                }
            )
            payload["pick_slots"]["pick_2"].update(
                {
                    "spell_1": "Flash",
                    "spell_2": "Teleport",
                    "skin_mode": "random",
                    "random_skin_id": 99007,
                    "random_skin_name": "Star Guardian Lux",
                    "random_skin_num": 7,
                    "random_skin_pool": [
                        {"skin_id": 99007, "skin_name": "Star Guardian Lux", "skin_num": 7}
                    ],
                }
            )
            payload["pick_slots"]["pick_3"]["skin_mode"] = "fixed"
            original = tomli_w.dumps(payload)
            params_path.write_text(original, encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()
            persisted = tomllib.loads(params_path.read_text(encoding="utf-8"))
            backup_exists = Path(f"{params_path}.bak").exists()

        self.assertEqual(loaded["config_schema_version"], 6)
        self.assertEqual(loaded["config_schema_version"], config._settings.CONFIG_SCHEMA_VERSION)
        self.assertEqual(loaded["config_version"], config._settings.CURRENT_VERSION)
        self.assertEqual(persisted, loaded)
        self.assertFalse(backup_exists)
        self.assertTrue(loaded["auto_accept_enabled"])
        self.assertTrue(loaded["auto_pick_enabled"])
        self.assertTrue(loaded["auto_ban_enabled"])
        self.assertTrue(loaded["auto_summoners_enabled"])
        self.assertTrue(loaded["presets_enabled"])
        self.assertEqual([loaded[f"selected_pick_{index}"] for index in (1, 2, 3)], ["Garen", "Lux", "Ashe"])
        self.assertEqual(loaded["selected_ban"], "Teemo")
        self.assertEqual(loaded["pick_slots"]["pick_1"]["spell_1"], "Flash")
        self.assertEqual(loaded["pick_slots"]["pick_1"]["spell_2"], "Ignite")
        self.assertEqual(loaded["pick_slots"]["pick_1"]["skin_id"], 86013)
        self.assertEqual(loaded["pick_slots"]["pick_1"]["skin_mode"], "fixed")
        self.assertEqual(loaded["pick_slots"]["pick_1"]["rune_page_id"], 4)
        self.assertFalse(loaded["pick_slots"]["pick_1"]["rune_auto_apply"])
        self.assertEqual(loaded["pick_slots"]["pick_2"]["skin_mode"], "random")
        self.assertEqual(loaded["pick_slots"]["pick_2"]["random_skin_pool"][0]["skin_id"], 99007)
        self.assertEqual(loaded["pick_slots"]["pick_3"]["skin_mode"], "none")
        self.assertEqual(loaded["theme"], "flatly")
        self.assertFalse(loaded["summoner_name_auto_detect"])
        self.assertEqual(loaded["manual_summoner_name"], "Player#EUW")
        self.assertEqual(loaded["manual_region"], "kr")
        self.assertEqual(loaded["preferred_stats_site"], "dpm")
        self.assertEqual(loaded["preferred_hotkey_site"], "deeplol")
        self.assertEqual(loaded["hotkey_toggle_window"], "ctrl+shift+c")
        self.assertEqual(loaded["hotkey_open_site"], "ctrl+shift+p")
        self.assertFalse(loaded["skin_automation_enabled"])
        self.assertEqual((loaded["window_x"], loaded["window_y"]), (51, 72))
        self.assertEqual((loaded["window_width"], loaded["window_height"]), (1280, 840))
        self.assertTrue(loaded["window_maximized"])
        self.assertNotIn("main_skin_mode_override", loaded)
        self.assertNotIn("main_skin_mode_overrides", loaded)

    def test_schema_five_singular_skin_override_applies_to_all_slots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["config_schema_version"] = 5
            payload["main_skin_mode_override"] = "random"
            payload["pick_slots"]["pick_1"]["skin_mode"] = "fixed"
            params_path.write_text(tomli_w.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(
            [loaded["pick_slots"][slot]["skin_mode"] for slot in ("pick_1", "pick_2", "pick_3")],
            ["random", "random", "random"],
        )

    def test_load_parameters_resets_and_backs_up_unsupported_future_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            skins_cache_dir = Path(tmpdir) / "skins"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["config_schema_version"] = config._settings.CONFIG_SCHEMA_VERSION + 1
            original = tomli_w.dumps(payload)
            params_path.write_text(original, encoding="utf-8")
            skins_cache_dir.mkdir()

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)), patch.object(
                config._settings, "SKINS_CACHE_DIR", str(skins_cache_dir)
            ):
                loaded = config.load_parameters()
            backup_content = Path(f"{params_path}.bak").read_text(encoding="utf-8")

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)
        self.assertEqual(backup_content, original)

    def test_load_parameters_accepts_current_exact_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
            payload["preferred_stats_site"] = "dpm"
            payload["preferred_hotkey_site"] = "dpm"
            params_path.write_text(tomli_w.dumps(payload), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                loaded = config.load_parameters()

        self.assertEqual(loaded, payload)

    def test_normalize_parameters_recovers_from_invalid_or_duplicate_hotkeys(self):
        invalid = copy.deepcopy(config.DEMO_PARAMS)
        invalid["hotkey_toggle_window"] = "ctrl"
        invalid["hotkey_open_site"] = "alt+alt+p"

        normalized = config.normalize_parameters(invalid)

        self.assertEqual(normalized["hotkey_toggle_window"], "alt+c")
        self.assertEqual(normalized["hotkey_open_site"], "alt+p")

        duplicate = copy.deepcopy(config.DEMO_PARAMS)
        duplicate["hotkey_open_site"] = "alt+c"
        self.assertEqual(config.normalize_parameters(duplicate)["hotkey_open_site"], "alt+p")

    def test_skin_pool_uses_only_current_field_names(self):
        payload = copy.deepcopy(config.DEFAULT_PARAMS)
        payload["pick_slots"]["pick_1"]["random_skin_pool"] = [
            {"id": 86013, "name": "God-King Garen", "num": 13}
        ]

        normalized = config.normalize_parameters(payload)

        self.assertEqual(normalized["pick_slots"]["pick_1"]["random_skin_pool"], [])

    def test_save_parameters_filters_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["manual_region"] = "kr"
            payload["pick_slots"]["pick_2"]["spell_1"] = "Ignite"
            payload["preferred_stats_site"] = "dpm"
            payload["preferred_hotkey_site"] = "dpm"
            payload["unexpected_key"] = "should_not_be_saved"

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)):
                saved = config.save_parameters(payload)
                self.assertTrue(saved)
                written = tomllib.loads(params_path.read_text(encoding="utf-8"))

        self.assertEqual(written["manual_region"], "kr")
        self.assertEqual(written["pick_slots"]["pick_2"]["spell_1"], "Ignite")
        self.assertEqual(written["preferred_stats_site"], "dpm")
        self.assertEqual(written["preferred_hotkey_site"], "dpm")
        self.assertNotIn("unexpected_key", written)
        self.assertEqual(set(written), set(config.DEFAULT_PARAMS))

    def test_save_parameters_keeps_previous_file_when_atomic_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "parameters.toml"
            original = tomli_w.dumps(config.FIRST_LAUNCH_PARAMS)
            params_path.write_text(original, encoding="utf-8")
            payload = copy.deepcopy(config.DEFAULT_PARAMS)
            payload["selected_pick_1"] = "Ahri"

            with patch.object(config._settings, "PARAMETERS_PATH", str(params_path)), patch.object(
                config._settings.os, "replace", side_effect=OSError("interrupted")
            ):
                self.assertFalse(config.save_parameters(payload))

            self.assertEqual(params_path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(Path(tmpdir).glob("*.tmp")), [])

    def test_legacy_json_settings_are_not_migrated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = Path(tmpdir) / "parameters.toml"
            json_path = Path(tmpdir) / "parameters.json"
            json_path.write_text(json.dumps(config.FIRST_LAUNCH_PARAMS), encoding="utf-8")

            with patch.object(config._settings, "PARAMETERS_PATH", str(toml_path)):
                loaded = config.load_parameters()
            toml_exists = toml_path.exists()
            legacy_json_exists = json_path.exists()

        self.assertEqual(loaded, config.FIRST_LAUNCH_PARAMS)
        self.assertTrue(toml_exists)
        self.assertTrue(legacy_json_exists)

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
