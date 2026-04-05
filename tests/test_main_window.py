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


class MainWindowLogicTests(unittest.TestCase):
    def test_build_feature_preview_payload_uses_global_flags_and_effective_values(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        params = {
            "auto_pick_enabled": True,
            "auto_ban_enabled": False,
            "auto_summoners_enabled": True,
        }
        effective = {
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "spell_1": "Flash",
            "spell_2": "Ignite",
        }

        payload = window._build_feature_preview_payload(params, effective)

        self.assertTrue(payload["pick"]["enabled"])
        self.assertFalse(payload["ban"]["enabled"])
        self.assertEqual(payload["pick"]["values"], ["Garen", "Lux", "Ashe"])
        self.assertEqual(payload["ban"]["values"], ["Teemo"])
        self.assertEqual(payload["spells"]["values"], ["Flash", "Ignite"])

    def test_toggle_main_preview_feature_updates_param_and_syncs_settings(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)
        params = {"auto_pick_enabled": True}
        updates = []
        recorder = DummyToastRecorder()
        settings = DummySettingsWindow()

        window.get_params = lambda: params.copy()
        window.update_param = lambda key, value: updates.append((key, value))
        window.show_toast = recorder
        window.settings_win = settings

        window._toggle_main_preview_feature("pick")

        self.assertEqual(updates, [("auto_pick_enabled", False)])
        self.assertEqual(settings.sync_calls, 1)
        self.assertEqual(recorder.messages[0][0], "Auto-pick desactive.")

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
            "pick": {"enabled": True, "values": ["Garen", "Lux", "Ashe"]},
            "ban": {"enabled": True, "values": ["Teemo"]},
            "spells": {"enabled": False, "values": ["Flash", "Ignite"]},
        }
        preview_b = {
            "pick": {"enabled": True, "values": ["Garen", "Lux", "Ashe"]},
            "ban": {"enabled": False, "values": ["Teemo"]},
            "spells": {"enabled": False, "values": ["Flash", "Ignite"]},
        }

        self.assertNotEqual(window._build_preview_signature(preview_a), window._build_preview_signature(preview_b))

    def test_preview_icon_cache_key_separates_type_and_name(self):
        window = LoLAssistantUI.__new__(LoLAssistantUI)

        champion_key = window._get_preview_icon_cache_key("Garen", True)
        spell_key = window._get_preview_icon_cache_key("Garen", False)

        self.assertNotEqual(champion_key, spell_key)
        self.assertEqual(champion_key, ("champ", "Garen", 30))


if __name__ == "__main__":
    unittest.main()
