"""
FILE NAME: src/services/single_instance.py
GLOBAL PURPOSE:
- Prevent multiple application processes from running at the same time.
- Store and clear the process lock file used by the runtime guard.
- Keep instance-detection behavior separate from launcher startup logic.

KEY FUNCTIONS:
- check_single_instance: Atomically create and lock the instance file.
- remove_lockfile: Release the lock and delete the file during shutdown.

AUDIENCE & LOGIC:
Why:
This module exists so single-instance enforcement is explicit and reusable without
mixing process checks into launcher code.
For whom:
Developers maintaining startup guards and shutdown cleanup.

DEPENDENCIES:
Used by:
- launcher.py through src.utils.
Uses:
- Standard library: logging, msvcrt, os
- Local modules: src.config
"""

import logging
import msvcrt
import os

from src.config import LOCKFILE_PATH

_lock_fd = None


def check_single_instance() -> bool:
    """Atomically create and lock the instance file. Returns False when another instance holds the lock."""
    global _lock_fd
    try:
        _lock_fd = os.open(LOCKFILE_PATH, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        msvcrt.locking(_lock_fd, msvcrt.LK_NBLCK, 1)
        os.write(_lock_fd, str(os.getpid()).encode())
        return True
    except (OSError, IOError):
        logging.info("Existing instance detected (lock file in use).")
        return False


def remove_lockfile() -> None:
    """Release the lock and delete the file during shutdown."""
    global _lock_fd
    try:
        if _lock_fd is not None:
            msvcrt.locking(_lock_fd, msvcrt.LK_UNLCK, 1)
            os.close(_lock_fd)
            _lock_fd = None
    except (OSError, IOError):
        pass
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except (OSError, IOError):
        pass
