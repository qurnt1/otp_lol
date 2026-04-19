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
                "pick_1": {"spell_1": "Heal", "spell_2": "Flash", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
                "pick_2": {"spell_1": "Ghost", "spell_2": "Flash", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
                "pick_3": {"spell_1": "Barrier", "spell_2": "Ignite", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
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
                        "pick_1": {"spell_1": "Ignite", "spell_2": "", "skin_mode": "random", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 9999, "random_skin_name": "Star Guardian Ahri", "random_skin_num": 7, "random_skin_pool": [{"skin_id": 9999, "skin_name": "Star Guardian Ahri", "skin_num": 7}]},
                        "pick_2": {"spell_1": "", "spell_2": "", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
                        "pick_3": {"spell_1": "", "spell_2": "", "skin_mode": "none", "skin_id": 0, "skin_name": "", "skin_num": 0, "random_skin_id": 0, "random_skin_name": "", "random_skin_num": 0, "random_skin_pool": []},
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

    def test_get_profile_role_data_includes_pick_slots(self):
        window = self.make_window()

        data = window._get_profile_role_data()

        self.assertEqual(data["selected_pick_1"], "Ahri")
        self.assertEqual(data["pick_slots"]["pick_1"]["spell_1"], "Ignite")
        self.assertEqual(data["pick_slots"]["pick_1"]["spell_2"], "")
        self.assertTrue(data["presets_enabled"])

    def test_get_excluded_champions_for_ban_includes_picks(self):
        window = self.make_window()

        excluded = window._get_excluded_champions("ban")

        self.assertEqual(excluded, {"Ahri"})

    def test_set_pick_slot_value_updates_role_profile_payload(self):
        window = self.make_window()

        window._set_pick_slot_value("pick_1", "spell_2", "Flash")

        self.assertEqual(window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["spell_2"], "Flash")

    def test_set_profile_presets_enabled_updates_role_profile_payload(self):
        window = self.make_window()

        window._set_profile_presets_enabled(False)

        self.assertFalse(window.parent.params["role_profiles"]["MIDDLE"]["presets_enabled"])

    def test_set_pick_slot_skin_selection_updates_role_profile_payload(self):
        window = self.make_window()

        window._set_pick_slot_skin_selection(
            "pick_1",
            mode="fixed",
            fixed_skin={"skin_id": 1234, "skin_name": "Elementalist Lux", "skin_num": 7},
        )

        slot = window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]
        self.assertEqual(slot["skin_mode"], "fixed")
        self.assertEqual(slot["skin_id"], 1234)
        self.assertEqual(slot["skin_name"], "Elementalist Lux")
        self.assertEqual(slot["skin_num"], 7)

    def test_set_random_skin_pool_updates_role_profile_payload(self):
        window = self.make_window()

        window._set_random_skin_pool(
            "pick_1",
            [
                {"skin_id": 111, "skin_name": "Skin A", "skin_num": 1},
                {"skin_id": 222, "skin_name": "Skin B", "skin_num": 2},
            ],
        )

        self.assertEqual(
            window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["random_skin_pool"],
            [
                {"skin_id": 111, "skin_name": "Skin A", "skin_num": 1},
                {"skin_id": 222, "skin_name": "Skin B", "skin_num": 2},
            ],
        )

    def test_get_skin_button_label_returns_random_for_random_mode(self):
        window = self.make_window()

        label = window._get_skin_button_label("pick_1")

        self.assertEqual(label, "Random")

    def test_refresh_skin_buttons_prefers_preview_url(self):
        class FakeButton:
            def __init__(self):
                self.config = {}

            def winfo_exists(self):
                return True

            def configure(self, **kwargs):
                self.config.update(kwargs)

        window = self.make_window()
        window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["skin_mode"] = "fixed"
        window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["skin_id"] = 1234
        window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["skin_name"] = "Elementalist Lux"
        window.parent.params["role_profiles"]["MIDDLE"]["pick_slots"]["pick_1"]["skin_num"] = 7
        window.pick_skin_buttons = {"pick_1": FakeButton()}
        window._get_slot_champion_name = lambda slot_key: "Ahri"
        window._load_remote_img_into_btn_calls = []
        window._load_remote_img_into_btn = (
            lambda btn, url, **kwargs: window._load_remote_img_into_btn_calls.append((url, kwargs))
        )

        window._refresh_skin_buttons()

        self.assertEqual(window._load_remote_img_into_btn_calls[0][0], "https://example.com/tile.jpg")
        self.assertEqual(window._load_remote_img_into_btn_calls[0][1]["size"], (30, 30))
        self.assertEqual(window.pick_skin_buttons["pick_1"].config["bootstyle"], "info-outline")

    def test_refresh_skin_buttons_uses_theme_placeholder_for_random(self):
        class FakeButton:
            def __init__(self):
                self.config = {}

            def winfo_exists(self):
                return True

            def configure(self, **kwargs):
                self.config.update(kwargs)

        window = self.make_window()
        window.pick_skin_buttons = {"pick_1": FakeButton()}
        window._get_slot_champion_name = lambda slot_key: "Ahri"
        window._load_remote_img_into_btn_calls = []
        window._load_remote_img_into_btn = (
            lambda btn, url, **kwargs: window._load_remote_img_into_btn_calls.append((url, kwargs))
        )
        window._load_local_img_into_btn_calls = []
        window._load_local_img_into_btn = (
            lambda btn, path, **kwargs: window._load_local_img_into_btn_calls.append((path, kwargs))
        )

        window._refresh_skin_buttons()

        self.assertEqual(window._load_remote_img_into_btn_calls, [])
        self.assertEqual(
            window._load_local_img_into_btn_calls[0][0],
            "config/images/app/question-mark-white_mode.png",
        )
        self.assertEqual(window.pick_skin_buttons["pick_1"].config["text"], "  Random")

    def test_random_skin_placeholder_uses_black_icon_on_light_theme(self):
        window = self.make_window()
        window.theme_var = DummyVar("flatly")

        self.assertEqual(
            window._get_random_skin_placeholder_asset(),
            "config/images/app/question-mark-black_mode.png",
        )

    def test_pick_slot_display_uses_global_fallback(self):
        window = self.make_window()

        display = window._get_pick_slot_display_value("pick_1", "spell_2")

        self.assertEqual(display, "Fallback: Flash")

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
