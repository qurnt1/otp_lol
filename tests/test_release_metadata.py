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

    def test_installer_default_version_matches_current_version(self):
        installer_text = (ROOT_DIR / "installer/OTP-LOL.iss").read_text(encoding="utf-8")
        self.assertIn(f'#define AppVersion "{CURRENT_VERSION}"', installer_text)

    def test_test_dependencies_are_separate_from_packaging_dependencies(self):
        test_requirements = (ROOT_DIR / "requirements-test.txt").read_text(encoding="utf-8")
        build_requirements = (ROOT_DIR / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("httpx", test_requirements)
        self.assertNotIn("httpx", build_requirements)

    def test_release_api_check_runs_after_python_dependencies_are_installed(self):
        workflow_text = (
            ROOT_DIR / ".github/workflows/release.yml"
        ).read_text(encoding="utf-8")
        frontend_start = workflow_text.index("- name: Build frontend")
        python_setup_start = workflow_text.index("- name: Set up Python")

        self.assertNotIn(
            "npm run api:check",
            workflow_text[frontend_start:python_setup_start],
        )
        self.assertEqual(workflow_text.count("npm run api:check"), 1)
        self.assertGreater(
            workflow_text.index("npm run api:check"),
            workflow_text.index("python -m pip install"),
        )

    def test_package_smoke_workflow_builds_and_self_tests_the_windows_executable(self):
        workflow_text = (ROOT_DIR / ".github/workflows/package-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow_text)
        self.assertIn("push:", workflow_text)
        self.assertIn("python create_exe.py --mode onedir --no-shortcut", workflow_text)
        self.assertIn('OTP LOL\\OTP LOL.exe" --self-test', workflow_text)

    def test_installer_blocks_missing_webview2_with_official_download_guidance(self):
        installer_text = (ROOT_DIR / "installer/OTP-LOL.iss").read_text(encoding="utf-8")
        self.assertIn("PrepareToInstall", installer_text)
        self.assertIn("developer.microsoft.com/microsoft-edge/webview2", installer_text)

    def test_release_workflow_requires_signing_secrets_before_publishing(self):
        workflow_text = (ROOT_DIR / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("OTP_LOL_SIGNING_CERT_BASE64", workflow_text)
        self.assertIn("signtool", workflow_text)
        self.assertIn("Verify Authenticode signatures", workflow_text)
        self.assertLess(
            workflow_text.index("Verify Authenticode signatures"),
            workflow_text.index("Generate SHA-256 checksum"),
        )
        self.assertLess(
            workflow_text.index("Generate SHA-256 checksum"),
            workflow_text.index("Publish GitHub Release"),
        )

    def test_documentation_screenshots_are_current_and_shared_with_website(self):
        readme_text = (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
        screenshot_names = (
            "dashboard-web.png",
            "dashboard-web-1440.png",
            "dashboard-web-1920.png",
            "settings-web.png",
        )

        for name in screenshot_names:
            docs_image = ROOT_DIR / "docs" / "images" / name
            self.assertTrue(docs_image.is_file(), name)
            if name in {"dashboard-web.png", "settings-web.png"}:
                self.assertIn(f"./docs/images/{name}", readme_text)
                website_image = ROOT_DIR / "website" / "public" / "assets" / "screenshots" / name
                self.assertEqual(docs_image.read_bytes(), website_image.read_bytes(), name)

        self.assertNotIn("better screenshots in the README", readme_text)


if __name__ == "__main__":
    unittest.main()
