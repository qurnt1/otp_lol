"""
FILE NAME: src/config/logging_config.py
GLOBAL PURPOSE:
- Configure application-wide logging once during import.
- Route logs to both a file and the current console stream.
- Expose the resolved log-file path to the rest of the application.

KEY FUNCTIONS:
- _setup_logging: Configure root logger handlers and return the final log path.

AUDIENCE & LOGIC:
Why:
This module exists so all runtime modules share the same logging format, output paths, and encoding behavior.
For whom:
Developers debugging runtime behavior or maintaining the logging setup.

DEPENDENCIES:
Used by:
- src.config.__init__ and any module importing `LOG_FILE_PATH`.
Uses:
- Standard library: logging, os, sys, tempfile
"""

import logging
import os
import sys
import tempfile


def _setup_logging() -> str:
    """Configure root logging handlers and return the resolved log-file path."""
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

    # Reconfigure stdout when possible so console logs do not break on Unicode output.
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
