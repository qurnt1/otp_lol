"""WebView desktop entry point for the progressive React migration."""

import logging
import sys

from src.desktop.webview import run_webview

logger = logging.getLogger(__name__)


def main() -> int:
    """Start the local FastAPI server and host the React UI in pywebview."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if "--self-test" in sys.argv:
        from src.desktop.self_test import run_self_test

        return run_self_test()
    if "--headless-smoke" in sys.argv:
        from src.desktop.self_test import run_headless_smoke

        return run_headless_smoke()
    try:
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
