import unittest
from unittest.mock import Mock, patch

from src.application.controller import ApplicationController
from src.core.events import ToastRequested, UpdateAvailable


class ApplicationControllerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.settings_store = Mock()
        self.settings_store.snapshot.return_value = {"ignored_update_version": ""}
        self.data_dragon = Mock()
        self.data_dragon.all_names = ["Garen", "Lux"]
        self.websocket_patcher = patch("src.application.controller.WebSocketManager")
        websocket_type = self.websocket_patcher.start()
        self.websocket_manager = websocket_type.return_value
        self.controller = ApplicationController(
            settings_store=self.settings_store,
            data_dragon=self.data_dragon,
            event_callback=self.events.append,
            update_checker=lambda: None,
        )

    def tearDown(self):
        self.controller.stop()
        self.websocket_patcher.stop()

    def test_runtime_waits_for_datadragon_before_starting_websocket(self):
        actions = []
        self.data_dragon.load.side_effect = lambda: actions.append("datadragon")
        self.websocket_manager.start.side_effect = lambda: actions.append("websocket")
        self.controller._initialize_runtime()
        self.assertEqual(actions, ["datadragon", "websocket"])

    def test_datadragon_success_emits_typed_toast(self):
        self.controller._load_datadragon()
        self.assertIn(ToastRequested("Champions loaded (2)", 1500), self.events)

    def test_update_event_preserves_release_metadata(self):
        self.controller._update_checker = lambda: {"version": "12.0", "highlights": "Faster startup"}
        self.controller._check_updates()
        self.assertIn(UpdateAvailable("12.0", "Faster startup"), self.events)

    def test_stop_is_idempotent_and_drops_late_events(self):
        self.controller.stop()
        self.controller.stop()
        self.controller._emit(ToastRequested("late"))
        self.websocket_manager.stop.assert_called_once_with()
        self.assertEqual(self.events, [])

    def test_presets_command_keeps_legacy_keys_aligned(self):
        self.controller.set_presets_enabled(False)
        self.settings_store.update_many.assert_called_once_with(
            {"presets_enabled": False, "auto_pick_enabled": False, "auto_summoners_enabled": False}
        )


if __name__ == "__main__":
    unittest.main()
