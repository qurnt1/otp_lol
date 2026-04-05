import unittest
from pathlib import Path

from src.config.constants import CURRENT_VERSION


ROOT_DIR = Path(__file__).resolve().parent.parent


class ReleaseMetadataTests(unittest.TestCase):
    def test_current_version_targets_v7(self):
        self.assertEqual(CURRENT_VERSION, "7.0")

    def test_readme_mentions_current_version(self):
        readme_text = (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
        self.assertIn(f"Version actuelle du projet: `{CURRENT_VERSION}`", readme_text)

    def test_build_script_uses_current_version_constant(self):
        build_text = (ROOT_DIR / "create_exe.py").read_text(encoding="utf-8")
        self.assertIn("from src.config import APP_BUILD_NAME, CURRENT_VERSION", build_text)


if __name__ == "__main__":
    unittest.main()
