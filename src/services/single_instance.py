"""
FILE NAME: src/services/single_instance.py
GLOBAL PURPOSE:
- Prevent multiple application processes from running at the same time.
- Store and clear the process lock file used by the runtime guard.
- Keep instance-detection behavior separate from launcher startup logic.

KEY FUNCTIONS:
- check_single_instance: Validate the existing lock file and write the current process id.
- remove_lockfile: Delete the lock file during shutdown.

AUDIENCE & LOGIC:
Why:
This module exists so single-instance enforcement is explicit and reusable without mixing process checks into launcher code.
For whom:
Developers maintaining startup guards and shutdown cleanup.

DEPENDENCIES:
Used by:
- launcher.py through src.utils.
Uses:
- Standard library: logging, os
- Third-party library: psutil
- Local modules: src.config
"""

import logging
import os

import psutil

from src.config import LOCKFILE_PATH


def check_single_instance() -> bool:
    """Return False when another live process still owns the lock file."""
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
    """Delete the lock file during shutdown when it still exists."""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except IOError:
        pass
