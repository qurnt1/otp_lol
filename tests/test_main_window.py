import unittest

from src.ui.main_window import LoLAssistantUI


class DummyWidget:
    def __init__(self):
        self.last_config = {}
        self.image = None

    def configure(self, **kwargs):
        self.last_config.update(kwargs)


class DummyToastRecorder:
    def __init__(self):
        self.messages = []

    def __call__(self, message, duration=0):
        self.messages.append((message, duration))


class DummySettingsWindow:
    class Window:
        @staticmethod
        def winfo_exists():
            return True

    def __init__(self):
        self.window = self.Window()
        self.sync_calls = 0

    def _sync_from_params(self):
        self.sync_calls += 1


class MutableParamsWindow:
    def __init__(self, params):
        self._params = params
        self.settings_win = DummySettingsWindow()
        self.toasts = []

    def get_params(self):
        return self._params

    def update_param(self, key, value):
        self._params[key] = value

    def show_toast(self, message, duration=0):
        self.toasts.append((message, duration))


class DummyRoot:
    def __init__(self):
        self.calls = []

    def after(self, delay, callback):
        self.calls.append((delay, callback))


class MainWindowLogicTests(unittest.TestCase):
    def test_build_feature_preview_payload_uses_global_flags_and_effective_values(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        params = {
            "auto_pick_enabled": True,
            "auto_ban_enabled": False,
            "auto_summoners_enabled": True,
        }
        effective = {
            "presets_enabled": False,
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
        }

        payload = window._build_feature_preview_payload(params, effective)

        self.assertFalse(payload["presets"]["enabled"])
        self.assertFalse(payload["ban"]["enabled"])
        self.assertEqual(payload["presets"]["values"], ["Garen", "Lux", "Ashe"])
        self.assertEqual(payload["ban"]["values"], ["Teemo"])

    def test_toggle_main_preview_feature_updates_param_and_syncs_settings(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        params = {
            "auto_pick_enabled": True,
            "auto_summoners_enabled": True,
            "presets_enabled": True,
        }
        updates = []
        recorder = DummyToastRecorder()
        settings = DummySettingsWindow()

        window.get_params = lambda: params.copy()
        window.update_param = lambda key, value: updates.append((key, value))
        window.show_toast = recorder
        window.settings_win = settings
        window.is_main_preview_presets_enabled = lambda: True
        window.set_main_preview_presets_enabled = lambda enabled: updates.extend(
            [
                ("auto_pick_enabled", enabled),
                ("auto_summoners_enabled", enabled),
                ("presets_enabled", enabled),
            ]
        )
        window._sync_settings_window_if_open = lambda: settings._sync_from_params()

        window._toggle_main_preview_feature("presets")

        self.assertEqual(
            updates,
            [
                ("auto_pick_enabled", False),
                ("auto_summoners_enabled", False),
                ("presets_enabled", False),
            ],
        )
        self.assertEqual(settings.sync_calls, 1)
        self.assertEqual(recorder.messages[0][0], "Presets desactive.")

    def test_set_feature_icon_hides_slot_text_when_section_disabled(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.theme = "darkly"
        window.preview_placeholder = object()
        widget = DummyWidget()

        window._set_feature_icon(widget, "Flash", is_champion=False, enabled=False, accent="warning")

        self.assertEqual(widget.last_config["text"], "")
        self.assertIs(widget.image, window.preview_placeholder)

    def test_build_preview_signature_changes_when_values_change(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        preview_a = {
            "presets": {"enabled": True, "values": ["Garen", "Lux", "Ashe"]},
            "ban": {"enabled": True, "values": ["Teemo"]},
        }
        preview_b = {
            "presets": {"enabled": True, "values": ["Garen", "Lux", "Ashe"]},
            "ban": {"enabled": False, "values": ["Teemo"]},
        }

        self.assertNotEqual(window._build_preview_signature(preview_a), window._build_preview_signature(preview_b))

    def test_preview_icon_cache_key_separates_type_and_name(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)

        champion_key = window._get_preview_icon_cache_key("Garen", True)
        spell_key = window._get_preview_icon_cache_key("Garen", False)

        self.assertNotEqual(champion_key, spell_key)
        self.assertEqual(champion_key, ("champ", "Garen", 30))

    def test_request_quit_from_external_thread_schedules_ui_callback(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window._quit_callback = lambda: None

        window.request_quit_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window._quit_callback)

    def test_request_toggle_from_external_thread_schedules_toggle(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.toggle_window = lambda: None

        window.request_toggle_window_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.toggle_window)

    def test_request_open_settings_from_external_thread_schedules_open(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.open_settings = lambda: None

        window.request_open_settings_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.open_settings)

    def test_request_toggle_presets_from_external_thread_schedules_toggle(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.toggle_tray_presets_automation = lambda: None

        window.request_toggle_presets_automation_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.toggle_tray_presets_automation)

    def test_request_toggle_auto_ban_from_external_thread_schedules_toggle(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        window.root = DummyRoot()
        window.toggle_tray_auto_ban = lambda: None

        window.request_toggle_auto_ban_from_external_thread()

        self.assertEqual(len(window.root.calls), 1)
        self.assertEqual(window.root.calls[0][0], 0)
        self.assertIs(window.root.calls[0][1], window.toggle_tray_auto_ban)

    def test_toggle_tray_presets_automation_updates_selected_role(self):
        params = {
            "selected_profile_role": "MIDDLE",
            "presets_enabled": False,
            "role_profiles": {
                "MIDDLE": {
                    "presets_enabled": True,
                }
            },
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win

        window.toggle_tray_presets_automation()

        self.assertFalse(params["role_profiles"]["MIDDLE"]["presets_enabled"])
        self.assertEqual(window.settings_win.sync_calls, 1)
        self.assertEqual(mutable.toasts[0][0], "Presets automation desactive for Mid.")

    def test_toggle_tray_auto_ban_updates_global_setting(self):
        params = {"auto_ban_enabled": True}
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window.show_toast = mutable.show_toast
        window.settings_win = mutable.settings_win

        window.toggle_tray_auto_ban()

        self.assertFalse(params["auto_ban_enabled"])
        self.assertEqual(window.settings_win.sync_calls, 1)
        self.assertEqual(mutable.toasts[0][0], "Auto-ban desactive.")

    def test_set_main_preview_presets_enabled_updates_global_flags_and_global_role(self):
        params = {
            "auto_pick_enabled": False,
            "auto_summoners_enabled": False,
            "presets_enabled": False,
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window._get_main_preview_role = lambda: "GLOBAL"

        window.set_main_preview_presets_enabled(True)

        self.assertTrue(params["auto_pick_enabled"])
        self.assertTrue(params["auto_summoners_enabled"])
        self.assertTrue(params["presets_enabled"])

    def test_set_main_preview_presets_enabled_updates_detected_role_profile(self):
        params = {
            "auto_pick_enabled": False,
            "auto_summoners_enabled": False,
            "presets_enabled": False,
            "role_profiles": {
                "MIDDLE": {
                    "presets_enabled": False,
                }
            },
        }
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        mutable = MutableParamsWindow(params)
        window.get_params = mutable.get_params
        window.update_param = mutable.update_param
        window._get_main_preview_role = lambda: "MIDDLE"

        window.set_main_preview_presets_enabled(True)

        self.assertTrue(params["auto_pick_enabled"])
        self.assertTrue(params["auto_summoners_enabled"])
        self.assertTrue(params["role_profiles"]["MIDDLE"]["presets_enabled"])


if __name__ == "__main__":
    unittest.main()
