"""Logging configuration for MAIN LOL."""

import logging
import os
import tempfile


def _setup_logging() -> str:
    """Configure logging in AppData/MainLoL/app_debug.log."""
    app_data_dir = os.getenv("APPDATA")
    if not app_data_dir:
        app_data_dir = os.path.expanduser("~")

    log_folder = os.path.join(app_data_dir, "MainLoL")

    if not os.path.exists(log_folder):
        try:
            os.makedirs(log_folder, exist_ok=True)
        except OSError:
            log_folder = tempfile.gettempdir()

    log_path = os.path.join(log_folder, "app_debug.log")

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        encoding="utf-8",
    )

    return log_path


LOG_FILE_PATH: str = _setup_logging()
