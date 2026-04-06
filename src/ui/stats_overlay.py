"""Process manager for the in-game stats overlay."""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
import time
from typing import Optional


class StatsOverlayManager:
    """Launch and stop the pywebview overlay in a dedicated child process."""

    DEFAULT_TITLE = "MAIN LOL - Overlay stats"
    DEFAULT_WIDTH_RATIO = 0.92
    DEFAULT_HEIGHT_RATIO = 0.88
    STARTUP_GRACE_SECONDS = 0.45

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._last_url: str = ""

    def is_available(self) -> bool:
        return importlib.util.find_spec("webview") is not None

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def get_diagnostics(self) -> dict[str, object]:
        return {
            "running": self.is_running(),
            "available": self.is_available(),
            "last_url": self._last_url,
            "pid": self._process.pid if self.is_running() and self._process else None,
        }

    def show(self, url: str) -> tuple[bool, str]:
        """Start the overlay process and keep it on top of the game."""
        url = (url or "").strip()
        if not url:
            return False, "URL overlay invalide."
        if not self.is_available():
            return False, "pywebview n'est pas installe."

        self.stop()
        command = self._build_launch_command(url)
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": self._get_launch_cwd(),
        }
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if create_no_window:
            kwargs["creationflags"] = create_no_window

        try:
            process = subprocess.Popen(command, **kwargs)
        except OSError as exc:
            logging.error("Impossible de lancer l'overlay stats: %s", exc)
            self._process = None
            return False, "Impossible de lancer l'overlay stats."

        self._process = process
        self._last_url = url
        time.sleep(self.STARTUP_GRACE_SECONDS)
        if self._process.poll() is not None:
            self._process = None
            return False, "L'overlay stats s'est ferme au lancement."
        return True, "Overlay stats ouvert."

    def hide(self) -> tuple[bool, str]:
        """Hide the overlay by terminating its dedicated process."""
        self.stop()
        return True, "Overlay stats ferme."

    def toggle(self, url: str) -> tuple[bool, str]:
        if self.is_running():
            return self.hide()
        return self.show(url)

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return

        try:
            process.terminate()
            process.wait(timeout=1.5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except Exception as exc:
                logging.debug("Impossible d'arreter l'overlay stats: %s", exc)

    def _build_launch_command(self, url: str) -> list[str]:
        base_args = [
            "--url",
            url,
            "--title",
            self.DEFAULT_TITLE,
            "--width-ratio",
            str(self.DEFAULT_WIDTH_RATIO),
            "--height-ratio",
            str(self.DEFAULT_HEIGHT_RATIO),
        ]
        if getattr(sys, "frozen", False):
            return [sys.executable, "--stats-overlay", *base_args]
        return [sys.executable, "-m", "src.ui.stats_overlay_host", *base_args]

    def _get_launch_cwd(self) -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
