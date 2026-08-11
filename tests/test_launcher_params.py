import unittest
from threading import RLock

from launcher import OtpLolApplication


class LauncherParameterIsolationTests(unittest.TestCase):
    def setUp(self):
        self.app = OtpLolApplication.__new__(OtpLolApplication)
        self.app._params_lock = RLock()
        self.app._params = {
            "pick_slots": {"pick_1": {"skin_mode": "fixed"}},
            "theme": "darkly",
        }

    def test_get_params_deep_copies_nested_values(self):
        snapshot = self.app._get_params()
        snapshot["pick_slots"]["pick_1"]["skin_mode"] = "random"

        self.assertEqual(self.app._params["pick_slots"]["pick_1"]["skin_mode"], "fixed")

    def test_update_param_copies_nested_value(self):
        value = {"pick_1": {"skin_mode": "random"}}
        self.app._update_param("pick_slots", value)
        value["pick_1"]["skin_mode"] = "none"

        self.assertEqual(self.app._params["pick_slots"]["pick_1"]["skin_mode"], "random")


if __name__ == "__main__":
    unittest.main()
