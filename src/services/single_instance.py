"""Single-instance helpers."""

import logging
import os

import psutil

from src.config import LOCKFILE_PATH


def check_single_instance() -> bool:
    """Ensure a single app instance is running."""
    if os.path.exists(LOCKFILE_PATH):
        try:
            with open(LOCKFILE_PATH, "r") as f:
                pid = int(f.read())
            if pid != os.getpid() and psutil.pid_exists(pid):
                logging.info(f"Existing instance detected (PID: {pid})")
                return False
        except (ValueError, IOError):
            pass

    try:
        with open(LOCKFILE_PATH, "w") as f:
            f.write(str(os.getpid()))
    except IOError:
        pass

    return True


def remove_lockfile() -> None:
    """Delete the lockfile during shutdown."""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except IOError:
        pass
