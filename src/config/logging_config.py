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
import threading

APP_LOG_FOLDER = "OTP LOL"


def _setup_logging() -> str:
    """Configure root logging handlers and return the resolved log-file path."""
    app_data_dir = os.getenv("APPDATA")
    if not app_data_dir:
        app_data_dir = os.path.expanduser("~")

    log_folder = os.path.join(app_data_dir, APP_LOG_FOLDER)

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
    level_name = os.environ.get("OTP_LOL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-7s [%(name)s] [%(threadName)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root_logger.addHandler(file_handler)
    console_stream = sys.stdout or sys.stderr
    if console_stream is not None:
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(level)
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s.%(msecs)03d %(levelname)-7s [%(name)s] [%(threadName)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root_logger.addHandler(console_handler)

    def thread_exception_hook(args: threading.ExceptHookArgs) -> None:
        logging.getLogger("otp_lol.thread").error(
            "Unhandled thread exception thread=%s",
            args.thread.name if args.thread is not None else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = thread_exception_hook

    return log_path


LOG_FILE_PATH: str = _setup_logging()
