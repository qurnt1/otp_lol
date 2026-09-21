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

    def test_first_launch_combines_factory_defaults_with_safe_starter_presets(self):
        slots = config.FIRST_LAUNCH_PARAMS["pick_slots"]

        self.assertEqual(config.DEMO_PRESETS["selected_pick_1"], "Garen")
        self.assertEqual(config.DEMO_PRESETS["pick_slots"]["pick_1"]["spell_1"], "Flash")
        self.assertEqual(config.DEMO_PRESETS["pick_slots"]["pick_2"]["skin_mode"], "random")
        self.assertEqual(config.DEMO_PRESETS["pick_slots"]["pick_3"]["skin_name"], "Queen Ashe")
        self.assertEqual(config.STARTER_PRESET_CONFIG["selected_pick_1"], "Garen")
        self.assertEqual(config.STARTER_PRESET_CONFIG["selected_pick_2"], "Lux")
        self.assertEqual(config.STARTER_PRESET_CONFIG["selected_pick_3"], "Ashe")
        self.assertEqual([slots[key]["spell_1"] for key in ("pick_1", "pick_2", "pick_3")], ["Flash"] * 3)
        self.assertEqual([slots[key]["spell_2"] for key in ("pick_1", "pick_2", "pick_3")], ["Ignite", "Barrier", "Heal"])
        self.assertTrue(all(slots[key]["skin_mode"] == "none" for key in slots))
        self.assertTrue(all(slots[key]["skin_id"] == 0 and slots[key]["rune_page_id"] == 0 for key in slots))
        self.assertTrue(all(slots[key]["rune_keystone_id"] == 0 for key in slots))
        self.assertEqual(config.FIRST_LAUNCH_PARAMS["selected_ban"], "Teemo")
        self.assertFalse(config.FIRST_LAUNCH_PARAMS["onboarding_completed"])
        for key in (
            "auto_accept_enabled",
            "auto_pick_enabled",
            "auto_ban_enabled",
            "auto_summoners_enabled",
            "presets_enabled",
            "skin_automation_enabled",
            "auto_play_again_enabled",
        ):
            self.assertFalse(config.FIRST_LAUNCH_PARAMS[key], key)

    def test_settings_missing_onboarding_defaults_during_current_schema_normalization(self):
        existing_settings = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
        existing_settings.pop("onboarding_completed")

        normalized = config.normalize_parameters(existing_settings)

        self.assertTrue(normalized["onboarding_completed"])
        self.assertFalse(config.FACTORY_DEFAULT_SETTINGS["onboarding_completed"])

    def test_pick_slot_defaults_include_rune_fields(self):
        from src.config.settings import build_pick_slot_defaults
        slots = build_pick_slot_defaults()
        for slot_key in ("pick_1", "pick_2", "pick_3"):
            self.assertIn("rune_page_id", slots[slot_key])
            self.assertIn("rune_page_name", slots[slot_key])
            self.assertIn("rune_keystone_id", slots[slot_key])
            self.assertEqual(slots[slot_key]["rune_page_id"], 0)
            self.assertEqual(slots[slot_key]["rune_page_name"], "")
            self.assertEqual(slots[slot_key]["rune_keystone_id"], 0)

    def test_default_params_no_longer_has_global_auto_runes_enabled(self):
        self.assertNotIn("auto_runes_enabled", config.DEFAULT_PARAMS)
        self.assertNotIn("auto_runes_enabled", config.FIRST_LAUNCH_PARAMS)
        self.assertFalse(config.FIRST_LAUNCH_PARAMS["skin_automation_enabled"])

    def test_legacy_rune_auto_apply_false_clears_page_and_true_preserves_it(self):
        raw = copy.deepcopy(config.FIRST_LAUNCH_PARAMS)
        raw["pick_slots"]["pick_1"].update(
            {
                "rune_page_id": 123,
                "rune_page_name": "Legacy page",
                "rune_keystone_id": 8005,
                "rune_auto_apply": False,
            }
        )
        normalized = config.normalize_parameters(raw)
        self.assertEqual(normalized["pick_slots"]["pick_1"]["rune_page_id"], 0)
        self.assertEqual(normalized["pick_slots"]["pick_1"]["rune_keystone_id"], 0)

        raw["pick_slots"]["pick_1"]["rune_auto_apply"] = True
        normalized = config.normalize_parameters(raw)
        self.assertEqual(normalized["pick_slots"]["pick_1"]["rune_page_id"], 123)
        self.assertEqual(normalized["pick_slots"]["pick_1"]["rune_keystone_id"], 8005)

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

    def test_load_parameters_ignores_a_separate_legacy_json_file(self):
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
