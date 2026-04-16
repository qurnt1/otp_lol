import unittest
from pathlib import Path

from src.config.constants import CURRENT_VERSION, GITHUB_REPO_NAME


ROOT_DIR = Path(__file__).resolve().parent.parent


class ReleaseMetadataTests(unittest.TestCase):
    def test_current_version_targets_v9(self):
        self.assertEqual(CURRENT_VERSION, "9.0")

    def test_readme_mentions_current_version(self):
        readme_text = (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
        self.assertIn(f"Current project version: `{CURRENT_VERSION}`", readme_text)
        self.assertIn(f"https://github.com/{GITHUB_REPO_NAME}.git", readme_text)

    def test_build_script_uses_current_version_constant(self):
        build_text = (ROOT_DIR / "create_exe.py").read_text(encoding="utf-8")
        self.assertIn("from src.config import APP_BUILD_NAME, APP_NAME, CURRENT_VERSION", build_text)


if __name__ == "__main__":
    unittest.main()
