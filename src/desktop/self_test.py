"""Non-GUI smoke checks used by Windows packaging and release CI."""

from __future__ import annotations

import logging
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ..config import FIRST_LAUNCH_PARAMS, load_parameters, save_parameters
from ..config import settings as settings_module
from .window import has_webview2_runtime

logger = logging.getLogger(__name__)


def run_self_test(*, require_webview2: bool = True) -> int:
    """Check packaged resources and persistence without opening a window."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    checks = {
        "frontend_dist": (root / "frontend" / "dist" / "index.html").is_file(),
        "frontend_assets": (root / "frontend" / "dist" / "assets").is_dir(),
        "config_assets": (root / "config").is_dir(),
    }
    webview2_available = has_webview2_runtime()
    if webview2_available or require_webview2:
        checks["webview2_detection"] = webview2_available
    else:
        logger.info("SKIP webview2_detection (runtime prerequisite is checked by the installer)")
    with tempfile.TemporaryDirectory(prefix="otp-lol-self-test-") as temp_dir:
        temp_path = Path(temp_dir) / "parameters.toml"
        previous_path = settings_module.PARAMETERS_PATH
        settings_module.PARAMETERS_PATH = str(temp_path)
        try:
            checks["settings_write"] = save_parameters(FIRST_LAUNCH_PARAMS)
            checks["settings_read"] = load_parameters() == FIRST_LAUNCH_PARAMS
        finally:
            settings_module.PARAMETERS_PATH = previous_path
    checks["embedded_api_smoke"] = run_headless_smoke() == 0
    for name, passed in checks.items():
        logger.info("%s%s", "PASS " if passed else "FAIL ", name)
    return 0 if all(checks.values()) else 1


def run_headless_smoke() -> int:
    """Start the embedded API, probe health, and stop it without opening a GUI."""
    from ..api.app import create_app
    from ..api.context import ApplicationContext
    from .server import EmbeddedApiServer

    context = ApplicationContext(params=FIRST_LAUNCH_PARAMS)

    async def no_start() -> None:
        return None

    async def no_stop() -> None:
        return None

    context.start = no_start
    context.stop = no_stop
    server = EmbeddedApiServer(create_app(context), host="127.0.0.1", port=0)
    server.start()
    port_ready = server.port > 0
    health_ready = False
    bootstrap_ready = False
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.port}/api/health", timeout=0.5
                ) as response:
                    health_ready = response.status == 200 and response.headers.get(
                        "content-type", ""
                    ).startswith("application/json")
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.port}/api/bootstrap", timeout=0.5
                ) as response:
                    bootstrap_ready = response.status == 200 and response.headers.get(
                        "content-type", ""
                    ).startswith("application/json")
                    if health_ready and bootstrap_ready:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
    finally:
        server.stop()

    stopped = server._thread is None
    logger.info("%sport_reserved", "PASS " if port_ready else "FAIL ")
    logger.info("%shealth_endpoint", "PASS " if health_ready else "FAIL ")
    logger.info("%sbootstrap_endpoint", "PASS " if bootstrap_ready else "FAIL ")
    logger.info("%sserver_stop", "PASS " if stopped else "FAIL ")
    return 0 if port_ready and health_ready and bootstrap_ready and stopped else 1


def run_provider_smoke() -> int:
    """Exercise provider lifecycle decisions with a deterministic fake WebView."""
    from ..api.context import ApplicationContext
    from .provider_browser import ProviderWindowManager

    class Signal:
        def __iadd__(self, callback):
            self.callback = callback
            return self

        def __isub__(self, callback):
            return self

    class NativeWindow:
        def __init__(self):
            self.events = SimpleNamespace(
                loaded=Signal(), shown=Signal(), closed=Signal()
            )

        def show(self):
            return None

        def hide(self):
            return None

        def bring_to_front(self):
            return None

        def reload(self):
            return None

        def destroy(self):
            return None

    created = []
    fake_webview = SimpleNamespace(
        settings={},
        create_window=lambda *_args, **kwargs: created.append(kwargs) or NativeWindow(),
    )
    params = dict(FIRST_LAUNCH_PARAMS)
    params.update(
        {
            "preferred_stats_site": "opgg",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#EUW",
            "manual_region": "euw",
        }
    )
    context = ApplicationContext(params=params)
    context.network_status = SimpleNamespace(is_online=lambda: True)
    manager = ProviderWindowManager(context)
    with patch.dict(sys.modules, {"webview": fake_webview}):
        blocked = manager.open_result("opgg", "stats")
        manager.mark_main_window_shown(preload=False)
        opened = manager.open_result("opgg", "stats")
        manager.close("stats")
        preloaded = manager.create_result("stats", "opgg", preload=True)
        manager.shutdown()
    checks = {
        "main_not_ready_reason": blocked.get("reason") == "main_not_ready",
        "provider_opened": bool(opened.get("ok")),
        "preload_opened": bool(preloaded.get("ok")),
        "preload_window_on_screen": len(created) >= 2
        and "x" not in created[1]
        and "y" not in created[1],
        "provider_closed": manager.status()["stats"]["state"] == "closed",
    }
    for name, passed in checks.items():
        logger.info("%s%s", "PASS " if passed else "FAIL ", name)
    return 0 if all(checks.values()) else 1
