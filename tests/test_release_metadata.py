import re
import unittest
from pathlib import Path

from src.config.constants import CURRENT_VERSION, GITHUB_REPO_NAME
from src.desktop.window import _WEBVIEW2_EVERGREEN_CLIENT_GUID

ROOT_DIR = Path(__file__).resolve().parent.parent


class ReleaseMetadataTests(unittest.TestCase):
    def test_current_version_targets_v11_1(self):
        self.assertEqual(CURRENT_VERSION, "11.1")

    def test_readme_leads_with_product_benefits_and_screenshots(self):
        readme_text = (ROOT_DIR / "readme.md").read_text(encoding="utf-8")
        self.assertIn("Spend less time on the same setup", readme_text)
        self.assertIn("Get OTP LOL for Windows", readme_text)
        self.assertIn("See it in action", readme_text)
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
        self.assertIn('OTP LOL\\OTP LOL.exe" --self-test --allow-missing-webview2', workflow_text)

    def test_installer_blocks_missing_webview2_with_official_download_guidance(self):
        installer_text = (ROOT_DIR / "installer/OTP-LOL.iss").read_text(encoding="utf-8")
        self.assertIn("PrepareToInstall", installer_text)
        self.assertIn("developer.microsoft.com/microsoft-edge/webview2", installer_text)

    def test_installer_preflight_matches_the_evergreen_runtime_detection(self):
        installer_text = (ROOT_DIR / "installer/OTP-LOL.iss").read_text(encoding="utf-8")
        installer_code = installer_text.split("[Code]", maxsplit=1)[1]
        installer_guids = re.findall(r"\{[0-9A-F-]{36}\}", installer_code, flags=re.IGNORECASE)

        self.assertEqual(installer_guids, [_WEBVIEW2_EVERGREEN_CLIENT_GUID])
        self.assertIn("function IsValidWebView2Version", installer_code)
        self.assertIn("(PartCount = 4)", installer_code)
        self.assertIn("(Version <> '0.0.0.0')", installer_code)

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
            workflow_text.index("Create draft GitHub Release"),
        )

    def test_release_workflow_creates_a_draft_until_manual_smoke_passes(self):
        workflow_text = (ROOT_DIR / ".github/workflows/release.yml").read_text(encoding="utf-8")
        release_command = next(line for line in workflow_text.splitlines() if "gh release create" in line)

        self.assertIn("--draft", release_command)

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
