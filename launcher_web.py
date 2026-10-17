"""WebView desktop entry point for the progressive React migration."""

import logging
import os
import sys
import tempfile
from pathlib import Path

if "--debug-webview" in sys.argv:
    os.environ.setdefault("OTP_LOL_LOG_LEVEL", "DEBUG")
    os.environ.setdefault("PYWEBVIEW_LOG", "debug")

logger = logging.getLogger(__name__)

_DIAGNOSTIC_ENV_VARS = ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP")


def _run_isolated_diagnostic(*, self_test: bool) -> int:
    """Run diagnostics with all user-writable paths redirected to a temp profile."""
    previous_environment = {name: os.environ.get(name) for name in _DIAGNOSTIC_ENV_VARS}
    previous_tempdir = tempfile.tempdir
    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_log_level = root_logger.level
    previously_loaded_src_modules = {
        name for name in sys.modules if name == "src" or name.startswith("src.")
    }

    with tempfile.TemporaryDirectory(prefix="otp-lol-diagnostic-") as temp_root:
        isolated_root = Path(temp_root)
        appdata = isolated_root / "roaming"
        local_appdata = isolated_root / "local"
        temp = isolated_root / "temp"
        for directory in (appdata, local_appdata, temp):
            directory.mkdir()

        try:
            os.environ.update(
                APPDATA=str(appdata),
                LOCALAPPDATA=str(local_appdata),
                TEMP=str(temp),
                TMP=str(temp),
            )
            # tempfile caches its first result, so point it at the isolated directory
            # before importing configuration modules that derive cache paths from it.
            tempfile.tempdir = str(temp)
            from src.desktop.self_test import run_headless_smoke, run_self_test

            if self_test:
                return run_self_test(
                    require_webview2="--allow-missing-webview2" not in sys.argv
                )
            return run_headless_smoke()
        finally:
            for handler in tuple(root_logger.handlers):
                if handler not in previous_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()
            root_logger.handlers[:] = previous_handlers
            root_logger.setLevel(previous_log_level)
            # Do not leave module-level paths derived from the temporary profile
            # cached if main() is invoked again in the same Python process.
            for name in tuple(sys.modules):
                if (
                    name == "src" or name.startswith("src.")
                ) and name not in previously_loaded_src_modules:
                    del sys.modules[name]
            for name, value in previous_environment.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            tempfile.tempdir = previous_tempdir


def main() -> int:
    """Start the local FastAPI server and host the React UI in pywebview."""
    debug = os.environ.get("OTP_LOL_LOG_LEVEL", "").upper() == "DEBUG"
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] [%(threadName)s] %(message)s",
    )
    if "--self-test" in sys.argv:
        return _run_isolated_diagnostic(self_test=True)
    if "--headless-smoke" in sys.argv:
        return _run_isolated_diagnostic(self_test=False)
    try:
        from src.desktop.webview import run_webview

        run_webview()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected.")
        return 0
    except Exception:
        logger.exception("Fatal WebView startup error.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
