"""Logging configuration for OTP LOL."""

import logging
import os
import sys
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

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except OSError:
            pass

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return log_path


LOG_FILE_PATH: str = _setup_logging()
