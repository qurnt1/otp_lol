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
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "global_spell_1": "Heal",
            "global_spell_2": "Flash",
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "hotkey_toggle_window": "alt+c",
            "hotkey_open_site": "alt+p",
            "hotkey_overlay_mode": "alt+o",
            "theme": "darkly",
            "role_profiles": {
                "MIDDLE": {
                    "selected_pick_1": "Ahri",
                    "selected_pick_2": "",
                    "selected_pick_3": "",
                    "selected_ban": "Zed",
                    "spell_1": "Ignite",
                    "spell_2": "",
                }
            },
        }
        self.telegram_open_calls = 0
        self.suspend_hotkeys_calls = 0
        self.resume_hotkeys_calls = 0
        self.toasts = []

    def get_params(self):
        return self.params

    def update_param(self, key, value):
        self.params[key] = value

    def open_telegram_settings(self):
        self.telegram_open_calls += 1

    def suspend_hotkeys(self):
        self.suspend_hotkeys_calls += 1

    def resume_hotkeys(self):
        self.resume_hotkeys_calls += 1

    def show_toast(self, message):
        self.toasts.append(message)


class DummyButton:
    def __init__(self):
        self.config = {}

    def configure(self, **kwargs):
        self.config.update(kwargs)


class SettingsWindowLogicTests(unittest.TestCase):
    def make_window(self):
        window = SettingsWindow.__new__(SettingsWindow)
        window.parent = FakeParent()
        window.profile_role_var = DummyVar("MIDDLE")
        return window

    def test_get_profile_role_data_includes_spells(self):
        window = self.make_window()

        data = window._get_profile_role_data()

        self.assertEqual(data["selected_pick_1"], "Ahri")
        self.assertEqual(data["spell_1"], "Ignite")
        self.assertEqual(data["spell_2"], "")

    def test_get_excluded_champions_for_ban_includes_picks(self):
        window = self.make_window()

        excluded = window._get_excluded_champions("ban")

        self.assertEqual(excluded, {"Ahri"})

    def test_set_profile_value_updates_role_profile_payload(self):
        window = self.make_window()

        window._set_profile_value("spell_2", "Flash")

        self.assertEqual(window.parent.params["role_profiles"]["MIDDLE"]["spell_2"], "Flash")

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

    def test_toggle_theme_updates_parent_once_and_cycles_theme(self):
        window = self.make_window()
        window.theme_var = DummyVar("darkly")
        refresh_calls = []
        window._refresh_theme_button = lambda: refresh_calls.append(True)

        window._toggle_theme()

        self.assertEqual(window.theme_var.get(), "flatly")
        self.assertEqual(window.parent.params["theme"], "flatly")
        self.assertEqual(len(refresh_calls), 1)

    def test_open_telegram_settings_delegates_to_parent(self):
        window = self.make_window()

        window._open_telegram_settings()

        self.assertEqual(window.parent.telegram_open_calls, 1)

    def test_hotkey_capture_suspends_and_resumes_existing_hotkeys(self):
        window = self.make_window()
        window._capture_target = None
        window._pressed_modifiers = set()
        window.hotkey_toggle_var = DummyVar("alt+c")
        window.hotkey_open_site_var = DummyVar("alt+p")
        window.hotkey_overlay_mode_var = DummyVar("alt+o")
        window.hotkey_toggle_btn = DummyButton()
        window.hotkey_open_btn = DummyButton()
        window.hotkey_overlay_mode_btn = DummyButton()

        class DummyFocusWindow:
            def __init__(self):
                self.focus_calls = 0

            def focus_force(self):
                self.focus_calls += 1

        window.window = DummyFocusWindow()

        window._start_hotkey_capture("toggle")

        self.assertEqual(window.parent.suspend_hotkeys_calls, 1)
        self.assertEqual(window._capture_target, "toggle")
        self.assertEqual(window.hotkey_toggle_btn.config["state"], "normal")
        self.assertEqual(window.hotkey_open_btn.config["state"], "disabled")
        self.assertEqual(window.hotkey_overlay_mode_btn.config["state"], "disabled")
        self.assertEqual(window.window.focus_calls, 1)

        window._cancel_hotkey_capture()

        self.assertEqual(window.parent.resume_hotkeys_calls, 1)
        self.assertIsNone(window._capture_target)
        self.assertEqual(window.hotkey_toggle_btn.config["state"], "normal")
        self.assertEqual(window.hotkey_open_btn.config["state"], "normal")
        self.assertEqual(window.hotkey_overlay_mode_btn.config["state"], "normal")

    def test_finish_hotkey_capture_updates_value_then_resumes_hotkeys(self):
        window = self.make_window()
        window._capture_target = "site"
        window._pressed_modifiers = {"ctrl"}
        window.hotkey_toggle_var = DummyVar("alt+c")
        window.hotkey_open_site_var = DummyVar("alt+p")
        window.hotkey_overlay_mode_var = DummyVar("alt+o")
        window.hotkey_toggle_btn = DummyButton()
        window.hotkey_open_btn = DummyButton()
        window.hotkey_overlay_mode_btn = DummyButton()

        window._finish_hotkey_capture("ctrl+shift+p")

        self.assertEqual(window.parent.params["hotkey_open_site"], "ctrl+shift+p")
        self.assertEqual(window.parent.resume_hotkeys_calls, 1)
        self.assertIsNone(window._capture_target)

    def test_finish_hotkey_capture_updates_overlay_mode_hotkey(self):
        window = self.make_window()
        window._capture_target = "overlay_mode"
        window._pressed_modifiers = {"ctrl"}
        window.hotkey_toggle_var = DummyVar("alt+c")
        window.hotkey_open_site_var = DummyVar("alt+p")
        window.hotkey_overlay_mode_var = DummyVar("alt+o")
        window.hotkey_toggle_btn = DummyButton()
        window.hotkey_open_btn = DummyButton()
        window.hotkey_overlay_mode_btn = DummyButton()

        window._finish_hotkey_capture("ctrl+shift+o")

        self.assertEqual(window.parent.params["hotkey_overlay_mode"], "ctrl+shift+o")
        self.assertEqual(window.parent.resume_hotkeys_calls, 1)


if __name__ == "__main__":
    unittest.main()
