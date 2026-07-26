import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from launcher import OtpLolApplication


class SharedParameterStateTests(unittest.TestCase):
    def setUp(self):
        self.app = OtpLolApplication.__new__(OtpLolApplication)
        self.app._params_lock = threading.RLock()
        self.app._params = {
            "pick_slots": {"pick_1": {"spell_1": "Flash"}},
            "ignored_update_version": "",
        }

    def test_get_params_returns_deep_independent_snapshot(self):
        snapshot = self.app._get_params()
        snapshot["pick_slots"]["pick_1"]["spell_1"] = "Ignite"

        self.assertEqual(self.app._params["pick_slots"]["pick_1"]["spell_1"], "Flash")

    def test_update_param_copies_mutable_value_before_storing(self):
        pick_slots = {"pick_1": {"spell_1": "Ghost"}}
        self.app._update_param("pick_slots", pick_slots)
        pick_slots["pick_1"]["spell_1"] = "Teleport"

        self.assertEqual(self.app._params["pick_slots"]["pick_1"]["spell_1"], "Ghost")

    def test_concurrent_reads_and_writes_keep_nested_state_consistent(self):
        def worker(index):
            for iteration in range(100):
                self.app._update_param(
                    "pick_slots",
                    {"pick_1": {"spell_1": f"spell-{index}-{iteration}"}},
                )
                snapshot = self.app._get_params()
                snapshot["pick_slots"]["pick_1"]["spell_1"] = "local-only"

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(worker, range(6)))

        stored_value = self.app._params["pick_slots"]["pick_1"]["spell_1"]
        self.assertTrue(stored_value.startswith("spell-"))

    def test_save_uses_snapshot_without_holding_parameter_lock(self):
        save_started = Event()
        release_save = Event()

        def fake_save(params):
            save_started.set()
            release_save.wait(timeout=2)
            self.assertEqual(params["pick_slots"]["pick_1"]["spell_1"], "Flash")
            return True

        with patch("launcher.save_parameters", side_effect=fake_save):
            saver = threading.Thread(target=self.app._save_params)
            saver.start()
            self.assertTrue(save_started.wait(timeout=2))

            self.app._update_param("ignored_update_version", "12.0")
            release_save.set()
            saver.join(timeout=2)

        self.assertFalse(saver.is_alive())
        self.assertEqual(self.app._params["ignored_update_version"], "12.0")


if __name__ == "__main__":
    unittest.main()
