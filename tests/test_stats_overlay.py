import unittest
from unittest.mock import patch

from src.ui.stats_overlay import StatsOverlayManager


class DummyProcess:
    def __init__(self, poll_result=None):
        self._poll_result = poll_result
        self.pid = 4242
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self):
        return self._poll_result

    def terminate(self):
        self.terminated = True
        self._poll_result = 0

    def kill(self):
        self.killed = True
        self._poll_result = 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        return 0


class StatsOverlayManagerTests(unittest.TestCase):
    def test_build_launch_command_uses_module_in_dev_mode(self):
        manager = StatsOverlayManager()

        with patch("src.ui.stats_overlay.sys.frozen", new=False, create=True), patch(
            "src.ui.stats_overlay.sys.executable", "C:\\Python\\python.exe"
        ):
            command = manager._build_launch_command("https://example.test")

        self.assertEqual(command[:3], ["C:\\Python\\python.exe", "-m", "src.ui.stats_overlay_host"])
        self.assertIn("https://example.test", command)
        self.assertIn("--width-ratio", command)
        self.assertIn("--height-ratio", command)

    def test_show_returns_false_when_pywebview_is_missing(self):
        manager = StatsOverlayManager()

        with patch.object(manager, "is_available", return_value=False):
            ok, message = manager.show("https://example.test")

        self.assertFalse(ok)
        self.assertIn("pywebview", message)

    def test_hide_stops_running_process(self):
        manager = StatsOverlayManager()
        process = DummyProcess()
        manager._process = process

        ok, message = manager.hide()

        self.assertTrue(ok)
        self.assertEqual(message, "Overlay stats ferme.")
        self.assertTrue(process.terminated)
        self.assertIsNone(manager._process)

    def test_show_spawns_overlay_process(self):
        manager = StatsOverlayManager()
        process = DummyProcess(poll_result=None)

        with patch.object(manager, "is_available", return_value=True), patch.object(
            manager, "_build_launch_command", return_value=["cmd"]
        ), patch("src.ui.stats_overlay.time.sleep"), patch(
            "src.ui.stats_overlay.subprocess.Popen", return_value=process
        ) as popen:
            ok, message = manager.show("https://example.test")

        self.assertTrue(ok)
        self.assertEqual(message, "Overlay stats ouvert.")
        self.assertIs(manager._process, process)
        self.assertEqual(manager._last_url, "https://example.test")
        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
