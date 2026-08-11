import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ImportIsolationTests(unittest.TestCase):
    def test_game_state_import_does_not_load_ui_or_optional_graphics(self):
        script = """
from src.core.game_state import GameState
from src.services.profile_config import build_effective_profile_config
assert GameState is not None
assert build_effective_profile_config is not None
assert 'tkinter' not in __import__('sys').modules
assert 'ttkbootstrap' not in __import__('sys').modules
assert 'pystray' not in __import__('sys').modules
assert 'PIL' not in __import__('sys').modules
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_import_uses_pyside_without_loading_removed_toolkits(self):
        script = """
import launcher
modules = __import__('sys').modules
assert launcher.OtpLolApplication is not None
assert 'PySide6.QtWidgets' in modules
assert 'tkinter' not in modules
assert 'ttkbootstrap' not in modules
assert 'pystray' not in modules
assert 'pygame' not in modules
assert 'src.ui' not in modules
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
