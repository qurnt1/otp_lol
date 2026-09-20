import unittest
import tempfile
from threading import Thread
from pathlib import Path
from unittest.mock import Mock, patch

from src.api.context import ApplicationContext
from src.config import FIRST_LAUNCH_PARAMS, load_parameters
from src.config import settings as settings_module


class ApplicationContextSettingsTests(unittest.TestCase):
    def setUp(self):
        self.context = ApplicationContext(
            params={
                "pick_slots": {"pick_1": {"skin_mode": "fixed"}},
                "theme": "darkly",
            }
        )

    def test_get_params_deep_copies_nested_values(self):
        snapshot = self.context.get_params()
        snapshot["pick_slots"]["pick_1"]["skin_mode"] = "random"

        self.assertEqual(self.context.get_params()["pick_slots"]["pick_1"]["skin_mode"], "fixed")

    def test_update_parameters_copies_nested_values(self):
        value = {"pick_1": {"skin_mode": "random"}}
        self.context.update_param("pick_slots", value)
        value["pick_1"]["skin_mode"] = "none"

        self.assertEqual(self.context.get_params()["pick_slots"]["pick_1"]["skin_mode"], "random")

    def test_persist_parameters_rolls_back_memory_when_disk_save_fails(self):
        self.context.save = lambda: False

        result = self.context.persist_parameters({"theme": "flatly"})

        self.assertIsNone(result)
        self.assertEqual(self.context.get_params()["theme"], "darkly")

    def test_detected_account_is_validated_persisted_atomically_and_emits_identity_event(self):
        self.context.save = Mock(return_value=True)
        self.context.broker.publish = Mock()

        saved = self.context.persist_detected_account("Player#EUW", "euw", "euw1")

        self.assertTrue(saved)
        params = self.context.get_params()
        self.assertEqual(
            (params["auto_detected_riot_id"], params["auto_detected_region"], params["auto_detected_platform"]),
            ("Player#EUW", "euw", "euw1"),
        )
        self.context.broker.publish.assert_called_once_with(
            "account_identity_updated",
            {"keys": ["auto_detected_riot_id", "auto_detected_region", "auto_detected_platform"]},
        )

    def test_detected_account_rejects_partial_or_mismatched_identity_without_mutation(self):
        self.context.save = Mock(return_value=True)
        original = self.context.get_params()

        self.assertFalse(self.context.persist_detected_account("Player#EUW", "na", "euw1"))
        self.assertFalse(self.context.persist_detected_account("Player", "euw", "euw1"))

        self.context.save.assert_not_called()
        params = self.context.get_params()
        self.assertEqual(params["auto_detected_riot_id"], original["auto_detected_riot_id"])
        self.assertEqual(params["auto_detected_region"], original["auto_detected_region"])
        self.assertEqual(params["auto_detected_platform"], original["auto_detected_platform"])

    def test_identical_detected_account_does_not_emit_duplicate_identity_event(self):
        self.context.save = Mock(return_value=True)
        self.context.broker.publish = Mock()

        self.assertTrue(self.context.persist_detected_account("Player#EUW", "euw", "euw1"))
        self.context.broker.publish.reset_mock()
        self.context.save.reset_mock()

        self.assertTrue(self.context.persist_detected_account("Player#EUW", "euw", "euw1"))
        self.context.save.assert_not_called()
        self.context.broker.publish.assert_not_called()

    def test_detected_account_survives_context_reload_while_offline(self):
        with tempfile.TemporaryDirectory(prefix="otp-lol-account-") as temp_dir:
            settings_path = str(Path(temp_dir) / "parameters.toml")
            with patch.object(settings_module, "PARAMETERS_PATH", settings_path):
                context = ApplicationContext(params=FIRST_LAUNCH_PARAMS)
                self.assertTrue(context.persist_detected_account("Saved#EUW", "euw", "euw1"))
                restored = ApplicationContext(params=load_parameters())

        params = restored.get_params()
        self.assertEqual(params["auto_detected_riot_id"], "Saved#EUW")
        self.assertEqual(params["auto_detected_region"], "euw")
        self.assertEqual(params["auto_detected_platform"], "euw1")

    def test_persist_preset_slot_keeps_parallel_updates(self):
        self.context.save = lambda: True
        errors = []

        def persist(slot_key, skin_mode):
            try:
                self.context.persist_preset_slot(slot_key, {"skin_mode": skin_mode})
            except Exception as error:  # pragma: no cover - a failing worker is asserted below
                errors.append(error)

        threads = [
            Thread(target=persist, args=("pick_1", "fixed")),
            Thread(target=persist, args=("pick_2", "random")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertFalse(errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        params = self.context.get_params()
        self.assertEqual(params["pick_slots"]["pick_1"]["skin_mode"], "fixed")
        self.assertEqual(params["pick_slots"]["pick_2"]["skin_mode"], "random")

    def test_runtime_transition_hides_once_and_closes_only_after_a_real_connection(self):
        class FakeWindow:
            def __init__(self):
                self.hide_count = 0

            def hide(self):
                self.hide_count += 1

        window = FakeWindow()
        shutdowns = []
        self.context.bind_window(window, shutdown_callback=lambda: shutdowns.append(True))
        self.context.process_checker = lambda: False

        self.context._handle_runtime_event("disconnected")
        self.assertEqual(window.hide_count, 0)
        self.assertEqual(shutdowns, [])

        self.context._handle_runtime_event("connected")
        self.context._handle_runtime_event("connected")
        self.assertEqual(window.hide_count, 1)
        self.context._handle_runtime_event("disconnected")
        self.assertEqual(shutdowns, [True])

    def test_transient_disconnect_never_closes_the_application(self):
        shutdowns = []
        self.context.bind_window(Mock(), shutdown_callback=lambda: shutdowns.append(True))
        self.context.process_checker = lambda: False
        self.context._handle_runtime_event("connected")

        self.context._handle_runtime_event("disconnected", {"transient": True, "reason": "retry"})

        self.assertEqual(shutdowns, [])

    def test_definitive_disconnect_keeps_application_open_while_league_process_exists(self):
        shutdowns = []
        self.context.bind_window(Mock(), shutdown_callback=lambda: shutdowns.append(True))
        self.context.process_checker = lambda: True
        self.context._handle_runtime_event("connected")

        self.context._handle_runtime_event("disconnected", {"transient": False})

        self.assertEqual(shutdowns, [])

    def test_definitive_disconnect_closes_when_league_process_is_gone(self):
        shutdowns = []
        self.context.bind_window(Mock(), shutdown_callback=lambda: shutdowns.append(True))
        self.context.process_checker = lambda: False
        self.context._handle_runtime_event("connected")

        self.context._handle_runtime_event("disconnected", {"transient": False})

        self.assertEqual(shutdowns, [True])

    def test_definitive_disconnect_does_not_close_when_option_is_disabled(self):
        shutdowns = []
        self.context.bind_window(Mock(), shutdown_callback=lambda: shutdowns.append(True))
        self.context.process_checker = lambda: False
        self.context.update_param("close_app_on_lol_exit", False)
        self.context._handle_runtime_event("connected")

        self.context._handle_runtime_event("disconnected", {"transient": False})

        self.assertEqual(shutdowns, [])

    def test_runtime_events_are_available_to_local_diagnostics(self):
        self.context._handle_runtime_event("status", {"action": "ban_confirmed"})

        event = self.context.diagnostics.snapshot()["events"][-1]
        self.assertEqual(event["topic"], "otp-lol/status")
        self.assertEqual(event["payload"]["action"], "ban_confirmed")


if __name__ == "__main__":
    unittest.main()
