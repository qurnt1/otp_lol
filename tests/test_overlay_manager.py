import unittest
from unittest.mock import patch

from src.ui.overlay_manager import OverlayManager


class DummyProcess:
    def __init__(self, poll_result=None):
        self._poll_result = poll_result
        self.pid = 7878
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._poll_result

    def terminate(self):
        self.terminated = True
        self._poll_result = 0

    def kill(self):
        self.killed = True
        self._poll_result = 0

    def wait(self, timeout=None):
        return 0


class OverlayManagerTests(unittest.TestCase):
    def test_build_launch_command_uses_module_in_dev_mode(self):
        manager = OverlayManager()

        with patch("src.ui.overlay_manager.sys.frozen", new=False, create=True), patch(
            "src.ui.overlay_manager.sys.executable", "C:\\Python\\python.exe"
        ):
            command = manager._build_launch_command("https://example.test", "interactive")

        self.assertEqual(command[:3], ["C:\\Python\\python.exe", "-m", "src.ui.overlay_host"])
        self.assertEqual(command[-1], "--overlay-host")

    def test_show_returns_false_when_qt_webengine_is_missing(self):
        manager = OverlayManager()

        with patch.object(manager, "is_available", return_value=False):
            ok, message = manager.show("https://example.test")

        self.assertFalse(ok)
        self.assertIn("PySide6", message)

    def test_show_spawns_persistent_overlay_process(self):
        manager = OverlayManager()
        process = DummyProcess(poll_result=None)

        with patch.object(manager, "is_available", return_value=True), patch(
            "src.ui.overlay_manager.reserve_local_port", return_value=4567
        ), patch("src.ui.overlay_manager.generate_overlay_token", return_value="abc123"), patch.object(
            manager, "_build_launch_command", return_value=["cmd"]
        ), patch("src.ui.overlay_manager.time.sleep"), patch(
            "src.ui.overlay_manager.subprocess.Popen", return_value=process
        ) as popen:
            ok, message = manager.show("https://example.test", mode="interactive")

        self.assertTrue(ok)
        self.assertEqual(message, "Overlay stats interactive ouvert.")
        self.assertIs(manager._process, process)
        self.assertTrue(manager.is_visible())
        popen.assert_called_once()

    def test_toggle_mode_flips_local_state_when_running(self):
        manager = OverlayManager()
        manager._mode = "interactive"
        manager._process = DummyProcess(poll_result=None)
        manager._port = 4567
        manager._token = "abc123"

        with patch.object(manager, "_send_command", return_value=True):
            ok, message = manager.toggle_mode()

        self.assertTrue(ok)
        self.assertEqual(manager.current_mode(), "passive")
        self.assertEqual(message, "Mode overlay : passive.")


if __name__ == "__main__":
    unittest.main()
