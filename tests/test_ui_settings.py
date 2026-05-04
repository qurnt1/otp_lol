import unittest

from src.ui.settings_window import SettingsWindow


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeParent:
    def __init__(self):
        self.params = {
            "selected_profile_role": "MIDDLE",
            "presets_enabled": False,
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "pick_slots": {
                "pick_1": {"spell_1": "Heal", "spell_2": "Flash", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": [], "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True},
                "pick_2": {"spell_1": "Ghost", "spell_2": "Flash", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": [], "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True},
                "pick_3": {"spell_1": "Barrier", "spell_2": "Ignite", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": [], "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True},
            },
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "hotkey_toggle_window": "alt+c",
            "hotkey_open_site": "alt+p",
            "theme": "darkly",
            "role_profiles": {
                "MIDDLE": {
                    "presets_enabled": True,
                    "selected_pick_1": "Ahri",
                    "selected_pick_2": "",
                    "selected_pick_3": "",
                    "selected_ban": "Zed",
                    "pick_slots": {
                        "pick_1": {"spell_1": "Ignite", "spell_2": "", "skin_mode": "random", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 9999, "random_skin_name": "Star Guardian Ahri", "random_skin_num": 7, "random_skin_pool": [{"skin_id": 9999, "skin_name": "Star Guardian Ahri", "skin_num": 7}], "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True},
                        "pick_2": {"spell_1": "", "spell_2": "", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": [], "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True},
                        "pick_3": {"spell_1": "", "spell_2": "", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": [], "rune_page_id": 0, "rune_page_name": "", "rune_auto_apply": True},
                    },
                }
            },
        }
        self.suspend_calls = 0
        self.resume_calls = 0
        self.toasts = []
        self.dd = type(
            "DummyDD",
            (),
            {
                "get_skin_preview_url": lambda self, champion_name, **kwargs: "https://example.com/tile.jpg",
                "get_rune_perk_icon_path": lambda self, perk_id: {
                    8214: "/lol-game-data/assets/v1/perk-images/Styles/Sorcery/SummonAery/SummonAery.png",
                }.get(int(perk_id or 0), ""),
                "get_rune_perk_name": lambda self, perk_id: {
                    8214: "Summon Aery",
                }.get(int(perk_id or 0), ""),
            },
        )()

    def get_params(self):
        return self.params

    def update_param(self, key, value):
        self.params[key] = value

    def suspend_hotkeys(self):
        self.suspend_calls += 1

    def resume_hotkeys(self):
        self.resume_calls += 1

    def show_toast(self, message):
        self.toasts.append(message)


class SettingsWindowLogicTests(unittest.TestCase):
    def make_window(self):
        window = SettingsWindow.__new__(SettingsWindow)
        window.parent = FakeParent()
        window.profile_role_var = DummyVar("MIDDLE")
        window.pick_buttons = {}
        window.pick_spell_buttons = {}
        window.pick_skin_buttons = {}
        window.theme_var = DummyVar("darkly")
        window.local_button_image_cache = {}
        return window

    def test_random_skin_placeholder_uses_black_icon_on_light_theme(self):
        window = self.make_window()
        window.theme_var = DummyVar("flatly")

        self.assertEqual(
            window._get_random_skin_placeholder_asset(),
            "config/images/app/question-mark-black_mode.png",
        )

    def test_find_rune_keystone_path_uses_selected_perk_id(self):
        window = self.make_window()
        page = {"selectedPerkIds": ["8214"]}
        primary_style = {
            "perks": [
                {"id": 8229, "iconPath": "wrong.png"},
            ]
        }

        path = window._find_rune_keystone_path(page, primary_style)

        self.assertIn("SummonAery.png", path)

    def test_find_rune_keystone_path_falls_back_to_first_perk(self):
        window = self.make_window()
        page = {"selectedPerkIds": []}
        primary_style = {"perks": [{"id": 8010, "iconPath": "conqueror.png"}]}

        self.assertEqual(window._find_rune_keystone_path(page, primary_style), "conqueror.png")

    def test_get_rune_page_icon_paths_returns_keystone_and_sub_style(self):
        window = self.make_window()
        page = {
            "id": 12,
            "primaryStyleId": 8200,
            "subStyleId": 8400,
            "selectedPerkIds": ["8214"],
        }
        styles = {
            8200: {"perks": []},
            8400: {"iconPath": "/lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png"},
        }

        keystone_path, sub_style_path = window._get_rune_page_icon_paths(page, styles)

        self.assertIn("SummonAery.png", keystone_path)
        self.assertEqual(sub_style_path, "/lol-game-data/assets/v1/perk-images/Styles/7204_Resolve.png")

    def test_split_rune_page_perk_ids_groups_primary_secondary_and_shards(self):
        page = {"selectedPerkIds": [8010, "9111", 9104, 8014, 8224, 8234, 5008, 5008, 5001]}

        primary_ids, secondary_ids, shard_ids = SettingsWindow._split_rune_page_perk_ids(page)

        self.assertEqual(primary_ids, [8010, 9111, 9104, 8014])
        self.assertEqual(secondary_ids, [8224, 8234])
        self.assertEqual(shard_ids, [5008, 5008, 5001])

    def test_strip_active_suffix_removes_only_lcu_active_marker(self):
        self.assertEqual(SettingsWindow._strip_active_suffix("Garen Test (active)"), "Garen Test")
        self.assertEqual(SettingsWindow._strip_active_suffix("Actually active"), "Actually active")

    def test_refresh_site_buttons_show_logo_and_left_compound(self):
        class FakeButton:
            def __init__(self):
                self.config = {}
                self.image = None

            def configure(self, **kwargs):
                self.config.update(kwargs)

        window = self.make_window()
        window.stats_site_btn = FakeButton()
        window.hotkey_site_btn = FakeButton()
        window.preferred_stats_site_var = DummyVar("dpm")
        window.preferred_hotkey_site_var = DummyVar("opgg")
        window._load_website_logo = lambda site, size=30: f"logo-{site}-{size}"

        window._refresh_stats_site_button()
        window._refresh_hotkey_site_button()

        self.assertEqual(window.stats_site_btn.config["text"], "  DPM.LOL")
        self.assertEqual(window.stats_site_btn.config["compound"], "left")
        self.assertEqual(window.stats_site_btn.image, "logo-dpm-30")
        self.assertEqual(window.hotkey_site_btn.config["text"], "  OP.GG")
        self.assertEqual(window.hotkey_site_btn.config["compound"], "left")
        self.assertEqual(window.hotkey_site_btn.image, "logo-opgg-30")

    def test_open_pick_slot_champion_picker_maps_slot_key_to_expected_slot_number(self):
        window = self.make_window()
        calls = []
        window._open_champion_picker = lambda context, slot_num=1: calls.append((context, slot_num))

        window._open_pick_slot_champion_picker("pick_1")
        window._open_pick_slot_champion_picker("pick_2")
        window._open_pick_slot_champion_picker("pick_3")

        self.assertEqual(
            calls,
            [("pick", 1), ("pick", 2), ("pick", 3)],
        )

    def test_stats_site_selection_updates_parent_config(self):
        window = self.make_window()

        class DummyCombo:
            def get(self):
                return "DeepLOL"

        window.stats_site_cb = DummyCombo()
        window.preferred_stats_site_var = DummyVar("opgg")

        window._on_stats_site_selected()

        self.assertEqual(window.parent.params["preferred_stats_site"], "deeplol")
        self.assertEqual(window.preferred_stats_site_var.get(), "deeplol")

    def test_hotkey_site_selection_updates_parent_config(self):
        window = self.make_window()

        class DummyCombo:
            def get(self):
                return "OP.GG"

        window.hotkey_site_cb = DummyCombo()
        window.preferred_hotkey_site_var = DummyVar("porofessor")

        window._on_hotkey_site_selected()

        self.assertEqual(window.parent.params["preferred_hotkey_site"], "opgg")
        self.assertEqual(window.preferred_hotkey_site_var.get(), "opgg")

    def test_format_hotkey_display_is_human_readable(self):
        self.assertEqual(SettingsWindow._format_hotkey_display("ctrl+alt+p"), "CTRL + ALT + P")

    def test_hotkey_capture_suspends_and_resumes_global_hotkeys_on_cancel(self):
        window = self.make_window()
        window.hotkey_toggle_var = DummyVar("alt+c")
        window.hotkey_open_site_var = DummyVar("alt+p")
        window._capture_target = None
        window._pressed_modifiers = set()
        window.window = type("DummyTkWindow", (), {"focus_force": lambda self: None})()

        window._start_hotkey_capture("site")
        window._cancel_hotkey_capture()

        self.assertEqual(window.parent.suspend_calls, 1)
        self.assertEqual(window.parent.resume_calls, 1)
        self.assertIsNone(window._capture_target)

    def test_hotkey_capture_resumes_after_successful_shortcut_update(self):
        window = self.make_window()
        window.hotkey_toggle_var = DummyVar("alt+c")
        window.hotkey_open_site_var = DummyVar("alt+p")
        window._capture_target = None
        window._pressed_modifiers = set()
        window.window = type("DummyTkWindow", (), {"focus_force": lambda self: None})()

        window._start_hotkey_capture("toggle")
        window._finish_hotkey_capture("ctrl+alt+x")

        self.assertEqual(window.hotkey_toggle_var.get(), "ctrl+alt+x")
        self.assertEqual(window.parent.params["hotkey_toggle_window"], "ctrl+alt+x")
        self.assertEqual(window.parent.resume_calls, 1)

    def test_hotkey_capture_resumes_when_shortcut_is_already_used(self):
        window = self.make_window()
        window.hotkey_toggle_var = DummyVar("alt+c")
        window.hotkey_open_site_var = DummyVar("alt+p")
        window._capture_target = None
        window._pressed_modifiers = set()
        window.window = type("DummyTkWindow", (), {"focus_force": lambda self: None})()

        window._start_hotkey_capture("toggle")
        window._finish_hotkey_capture("alt+p")

        self.assertEqual(window.hotkey_toggle_var.get(), "alt+c")
        self.assertEqual(window.parent.toasts, ["Shortcut already in use."])
        self.assertEqual(window.parent.resume_calls, 1)

    def test_toggle_theme_updates_parent_once_and_cycles_theme(self):
        window = self.make_window()
        window.theme_var = DummyVar("darkly")
        refresh_calls = []
        window._refresh_theme_button = lambda: refresh_calls.append(True)

        window._toggle_theme()

        self.assertEqual(window.theme_var.get(), "flatly")
        self.assertEqual(window.parent.params["theme"], "flatly")
        self.assertEqual(len(refresh_calls), 1)


if __name__ == "__main__":
    unittest.main()
