"""Opt-in, read-only provider probes for a currently active League match.

Run with ``OTP_LOL_LIVE_PROVIDER_AUDIT=1 python -m pytest -s tests/test_live_provider_audit.py``.
The probe refuses to contact providers unless the LCU reports ``InProgress``.
"""

import os
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import requests

from src.config.constants import PLATFORM_TO_REGION, REGION_LIST
from src.domain.providers import LIVE_PROVIDER_IDS, PROVIDER_REGISTRY
from src.services.urls import is_valid_riot_id


def _cloudflare_signals(headers, body_text):
    normalized_headers = {str(name).casefold(): str(value) for name, value in headers.items()}
    body_text = body_text.casefold()
    cloudflare = bool(normalized_headers.get("cf-ray"))
    challenge = normalized_headers.get("cf-mitigated", "").casefold() == "challenge" or any(
        marker in body_text
        for marker in ("just a moment", "verify you are human", "checking your browser")
    )
    return cloudflare, challenge


class CloudflareSignalTests(unittest.TestCase):
    def test_cf_ray_alone_does_not_mean_challenge(self):
        self.assertEqual(_cloudflare_signals({"CF-Ray": "sample"}, "page loaded"), (True, False))

    def test_challenge_header_and_page_text_are_detected(self):
        self.assertEqual(_cloudflare_signals({"cf-mitigated": "challenge"}, ""), (False, True))
        self.assertEqual(_cloudflare_signals({}, "Just a moment..."), (False, True))


@unittest.skipUnless(
    os.environ.get("OTP_LOL_LIVE_PROVIDER_AUDIT") == "1",
    "requires explicit opt-in; contacts live providers only during an active match",
)
class LiveProviderAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psutil
        except ImportError:
            raise unittest.SkipTest("LCU audit dependencies are unavailable") from None

        lcu_credentials = None
        for process in psutil.process_iter(["name", "exe"]):
            try:
                process_name = (process.info.get("name") or "").casefold()
                executable = process.info.get("exe")
                if process_name not in {"leagueclient.exe", "leagueclientux.exe"} or not executable:
                    continue
                lockfile = Path(executable).parent / "lockfile"
                if lockfile.is_file():
                    lockfile_fields = lockfile.read_text(encoding="utf-8").split(":")
                    lcu_credentials = (int(lockfile_fields[2]), lockfile_fields[3])
                    break
            except (OSError, ValueError, IndexError, psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        if not lcu_credentials:
            raise unittest.SkipTest("League Client lockfile is unavailable; no provider request sent")

        port, password = lcu_credentials
        lcu_session = requests.Session()
        lcu_session.auth = ("riot", password)
        lcu_session.verify = False

        def get_lcu_json(endpoint):
            try:
                response = lcu_session.get(f"https://127.0.0.1:{port}{endpoint}", timeout=5)
                return response.json() if response.status_code == 200 else None
            except requests.RequestException:
                return None

        try:
            phase = get_lcu_json("/lol-gameflow/v1/gameflow-phase")
            if phase != "InProgress":
                raise unittest.SkipTest("LCU is not InProgress; no provider request sent")
            account = get_lcu_json("/lol-chat/v1/me") or {}
            region = get_lcu_json("/riotclient/get_region_locale")
            if not isinstance(region, dict):
                region = get_lcu_json("/riotclient/region-locale")
        finally:
            lcu_session.close()
        platform = str((region or {}).get("platformId") or (region or {}).get("region") or "").lower()
        region = PLATFORM_TO_REGION.get(platform, platform)

        game_name, tag_line = account.get("gameName"), account.get("gameTag")
        if not game_name or not tag_line or region not in REGION_LIST:
            raise unittest.SkipTest("LCU account or region is unavailable; no provider request sent")

        cls.riot_id = f"{game_name}#{tag_line}"
        if not is_valid_riot_id(cls.riot_id):
            raise unittest.SkipTest("LCU Riot ID is malformed; no provider request sent")
        cls.region = region

    def test_current_live_pages_report_redirect_and_frame_policy(self):
        for provider_id in LIVE_PROVIDER_IDS:
            with self.subTest(provider=provider_id):
                provider = PROVIDER_REGISTRY[provider_id]
                url = provider.live_builder(self.region, self.riot_id)
                try:
                    response_context = requests.get(url, timeout=20, allow_redirects=True, stream=True)
                    with response_context as response:
                        final_url = urlsplit(response.url)
                        self.assertEqual(final_url.scheme, "https")
                        final_host = (final_url.hostname or "").lower()
                        self.assertIn(final_host, provider.allowed_hosts)
                        headers = response.headers
                        csp = headers.get("content-security-policy", "")
                        frame_ancestors = next(
                            (part.strip() for part in csp.split(";") if part.strip().lower().startswith("frame-ancestors ")),
                            "absent",
                        )
                        body = bytearray()
                        for chunk in response.iter_content(chunk_size=8192):
                            body.extend(chunk)
                            if len(body) >= 100_000:
                                break
                        body_text = bytes(body[:100_000]).decode("utf-8", errors="ignore").lower()
                        cloudflare, challenge = _cloudflare_signals(headers, body_text)
                        print(
                            f"{provider_id}: status={response.status_code}, final_host={final_host}, "
                            f"X-Frame-Options={headers.get('x-frame-options', 'absent')}, "
                            f"frame-ancestors={frame_ancestors}, cloudflare={cloudflare}, challenge={challenge}"
                        )
                except requests.RequestException as error:
                    self.fail(f"{provider_id} request failed ({type(error).__name__})")


if __name__ == "__main__":
    unittest.main()
