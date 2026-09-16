import unittest
from threading import Thread

from src.api.context import ApplicationContext


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

        self.context._handle_runtime_event("disconnected")
        self.assertEqual(window.hide_count, 0)
        self.assertEqual(shutdowns, [])

        self.context._handle_runtime_event("connected")
        self.context._handle_runtime_event("connected")
        self.assertEqual(window.hide_count, 1)
        self.context._handle_runtime_event("disconnected")
        self.assertEqual(shutdowns, [True])


if __name__ == "__main__":
    unittest.main()
