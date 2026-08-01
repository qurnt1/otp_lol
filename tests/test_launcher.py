import unittest
from unittest.mock import Mock

from launcher import OtpLolApplication


class LauncherControllerTests(unittest.TestCase):
    def test_save_delegates_to_application_controller(self):
        app = OtpLolApplication.__new__(OtpLolApplication)
        app.controller = Mock()
        app.controller.save_settings.return_value = True

        app._save_params()

        app.controller.save_settings.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
