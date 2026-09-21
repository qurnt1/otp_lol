import unittest
from pathlib import Path

from src.config.constants import CURRENT_VERSION, GITHUB_REPO_NAME


ROOT_DIR = Path(__file__).resolve().parent.parent


class ReleaseMetadataTests(unittest.TestCase):
    def test_current_version_targets_v11(self):
        self.assertEqual(CURRENT_VERSION, "11.0")

    def test_readme_mentions_current_version(self):
        readme_text = (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
        self.assertIn(f"Current project version: `{CURRENT_VERSION}`", readme_text)
        self.assertIn(f"https://img.shields.io/badge/version-{CURRENT_VERSION}-", readme_text)
        self.assertIn(f"## Version {CURRENT_VERSION} Highlights", readme_text)
        self.assertIn(f"https://github.com/{GITHUB_REPO_NAME}.git", readme_text)

    def test_readme_has_no_conflict_markers(self):
        readme_text = (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", readme_text)
        self.assertNotIn("=======", readme_text)
        self.assertNotIn(">>>>>>>", readme_text)

    def test_build_script_uses_current_version_constant(self):
        build_text = (ROOT_DIR / "create_exe.py").read_text(encoding="utf-8")
        self.assertIn("from src.config import APP_BUILD_NAME, APP_NAME, CURRENT_VERSION", build_text)

    def test_test_dependencies_are_separate_from_packaging_dependencies(self):
        test_requirements = (ROOT_DIR / "requirements-test.txt").read_text(encoding="utf-8")
        build_requirements = (ROOT_DIR / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("httpx", test_requirements)
        self.assertNotIn("httpx", build_requirements)


if __name__ == "__main__":
    unittest.main()
