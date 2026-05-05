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
- launcher.py.
Uses:
- Standard library: logging, msvcrt, os
- Third-party libraries: psutil
- Local modules: src.config
"""

import logging
import msvcrt
import os

import psutil

from src.config import LOCKFILE_PATH

_lock_fd = None


def _is_stale_lockfile() -> bool:
    """Return True when the lock file exists but the PID inside is no longer alive."""
    try:
        with open(LOCKFILE_PATH, "r") as f:
            pid_str = f.read().strip()
        if not pid_str:
            return True
        pid = int(pid_str)
        try:
            psutil.Process(pid)
            return False
        except psutil.NoSuchProcess:
            return True
    except (OSError, ValueError):
        return True


def check_single_instance() -> bool:
    """Atomically create and lock the instance file. Returns False when another instance holds the lock."""
    global _lock_fd
    try:
        _lock_fd = os.open(LOCKFILE_PATH, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        msvcrt.locking(_lock_fd, msvcrt.LK_NBLCK, 1)
        os.write(_lock_fd, str(os.getpid()).encode())
        return True
    except (OSError, IOError):
        if _is_stale_lockfile():
            logging.warning("Stale lock file detected (PID no longer running), cleaning up.")
            _force_remove_lockfile()
            return check_single_instance()
        logging.info("Existing instance detected (lock file in use).")
        return False


def remove_lockfile() -> None:
    """Release the lock and delete the file during shutdown."""
    global _lock_fd
    try:
        if _lock_fd is not None:
            os.lseek(_lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(_lock_fd, msvcrt.LK_UNLCK, 1)
            os.close(_lock_fd)
            _lock_fd = None
    except (OSError, IOError) as e:
        logging.debug("Error releasing lock: %s", e)
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except (OSError, IOError) as e:
        logging.debug("Error removing lockfile: %s", e)


def _force_remove_lockfile() -> None:
    """Remove the lock file without holding a reference to it (stale recovery)."""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except (OSError, IOError) as e:
        logging.debug("Error force-removing lockfile: %s", e)
