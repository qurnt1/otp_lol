import unittest
from unittest.mock import patch

from src.ui.qt_overlay import QtStatsOverlayManager


class DummyProcess:
    def __init__(self, poll_result=None):
        self._poll_result = poll_result
        self.pid = 5252
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


class QtStatsOverlayManagerTests(unittest.TestCase):
    def test_build_launch_command_uses_module_in_dev_mode(self):
        manager = QtStatsOverlayManager()

        with patch("src.ui.qt_overlay.sys.frozen", new=False, create=True), patch(
            "src.ui.qt_overlay.sys.executable", "C:\\Python\\python.exe"
        ):
            command = manager._build_launch_command("https://example.test")

        self.assertEqual(command[:3], ["C:\\Python\\python.exe", "-m", "src.ui.qt_overlay_host"])
        self.assertIn("--width-ratio", command)
        self.assertIn("--height-ratio", command)

    def test_show_returns_false_when_qt_is_missing(self):
        manager = QtStatsOverlayManager()

        with patch.object(manager, "is_available", return_value=False):
            ok, message = manager.show("https://example.test")

        self.assertFalse(ok)
        self.assertIn("PySide6", message)

    def test_show_spawns_qt_overlay_process(self):
        manager = QtStatsOverlayManager()
        process = DummyProcess(poll_result=None)

        with patch.object(manager, "is_available", return_value=True), patch.object(
            manager, "_build_launch_command", return_value=["cmd"]
        ), patch("src.ui.qt_overlay.time.sleep"), patch(
            "src.ui.qt_overlay.subprocess.Popen", return_value=process
        ) as popen:
            ok, message = manager.show("https://example.test")

        self.assertTrue(ok)
        self.assertEqual(message, "Overlay stats Qt ouvert.")
        self.assertIs(manager._process, process)
        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
