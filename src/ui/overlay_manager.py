"""Main-process manager for the persistent Qt overlay host."""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
import time
from typing import Optional

from .overlay_runtime import (
    CMD_HIDE,
    CMD_NAVIGATE,
    CMD_SET_MODE,
    CMD_SHOW,
    CMD_SHUTDOWN,
    CMD_TOGGLE_MODE,
    MODE_INTERACTIVE,
    MODE_PASSIVE,
    generate_overlay_token,
    normalize_overlay_mode,
    reserve_local_port,
    send_overlay_command,
)


class OverlayManager:
    """Keep a persistent Qt overlay process alive across hotkey presses."""

    DEFAULT_TITLE = "MAIN LOL - Overlay stats"
    DEFAULT_WIDTH_RATIO = 0.92
    DEFAULT_HEIGHT_RATIO = 0.88
    STARTUP_GRACE_SECONDS = 0.7

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._port: Optional[int] = None
        self._token: Optional[str] = None
        self._last_url: str = ""
        self._visible = False
        self._mode = MODE_INTERACTIVE

    def is_available(self) -> bool:
        return importlib.util.find_spec("PySide6") is not None and importlib.util.find_spec(
            "PySide6.QtWebEngineWidgets"
        ) is not None

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def is_visible(self) -> bool:
        return self.is_running() and self._visible

    def current_mode(self) -> str:
        return self._mode

    def get_diagnostics(self) -> dict[str, object]:
        return {
            "running": self.is_running(),
            "visible": self.is_visible(),
            "available": self.is_available(),
            "mode": self._mode,
            "last_url": self._last_url,
            "pid": self._process.pid if self.is_running() and self._process else None,
        }

    def show(self, url: str, mode: str = MODE_INTERACTIVE) -> tuple[bool, str]:
        url = str(url or "").strip()
        mode = normalize_overlay_mode(mode)
        if not url:
            return False, "URL overlay invalide."
        if not self.is_available():
            return False, "PySide6 WebEngine n'est pas installe."
        if not self.is_running():
            return self._launch_process(url, mode)

        if not self._send_command(CMD_SHOW, url=url, mode=mode):
            return False, "Impossible de piloter l'overlay."
        self._last_url = url
        self._mode = mode
        self._visible = True
        return True, f"Overlay stats {mode} ouvert."

    def hide(self) -> tuple[bool, str]:
        if not self.is_running():
            self._visible = False
            return True, "Overlay stats ferme."
        if not self._send_command(CMD_HIDE):
            return False, "Impossible de masquer l'overlay."
        self._visible = False
        return True, "Overlay stats ferme."

    def toggle(self, url: str, mode: str = MODE_INTERACTIVE) -> tuple[bool, str]:
        if self.is_visible():
            return self.hide()
        return self.show(url, mode=mode)

    def navigate(self, url: str) -> tuple[bool, str]:
        if not self.is_running():
            return False, "Overlay indisponible."
        url = str(url or "").strip()
        if not url:
            return False, "URL overlay invalide."
        if not self._send_command(CMD_NAVIGATE, url=url):
            return False, "Impossible de mettre a jour l'overlay."
        self._last_url = url
        return True, "Overlay mis a jour."

    def set_mode(self, mode: str) -> tuple[bool, str]:
        mode = normalize_overlay_mode(mode)
        if not self.is_running():
            self._mode = mode
            return False, "Overlay indisponible."
        if not self._send_command(CMD_SET_MODE, mode=mode):
            return False, "Impossible de changer le mode overlay."
        self._mode = mode
        return True, f"Mode overlay : {mode}."

    def toggle_mode(self) -> tuple[bool, str]:
        next_mode = MODE_PASSIVE if self._mode == MODE_INTERACTIVE else MODE_INTERACTIVE
        if not self.is_running():
            self._mode = next_mode
            return False, "Overlay indisponible."
        if not self._send_command(CMD_TOGGLE_MODE):
            return False, "Impossible de basculer le mode overlay."
        self._mode = next_mode
        return True, f"Mode overlay : {next_mode}."

    def shutdown(self) -> None:
        process = self._process
        self._process = None
        self._visible = False
        if process is None or process.poll() is not None:
            return
        try:
            if self._port and self._token:
                send_overlay_command(self._port, self._token, CMD_SHUTDOWN)
                process.wait(timeout=1.5)
                return
        except Exception:
            pass
        try:
            process.terminate()
            process.wait(timeout=1.5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except Exception as exc:
                logging.debug("Impossible d'arreter l'overlay Qt persistant: %s", exc)

    stop = shutdown

    def _launch_process(self, url: str, mode: str) -> tuple[bool, str]:
        self.shutdown()
        self._port = reserve_local_port()
        self._token = generate_overlay_token()
        command = self._build_launch_command(url, mode)
        env = os.environ.copy()
        env.update(
            {
                "MAIN_LOL_OVERLAY_PORT": str(self._port),
                "MAIN_LOL_OVERLAY_TOKEN": str(self._token),
                "MAIN_LOL_OVERLAY_URL": url,
                "MAIN_LOL_OVERLAY_MODE": mode,
                "MAIN_LOL_OVERLAY_TITLE": self.DEFAULT_TITLE,
                "MAIN_LOL_OVERLAY_WIDTH_RATIO": str(self.DEFAULT_WIDTH_RATIO),
                "MAIN_LOL_OVERLAY_HEIGHT_RATIO": str(self.DEFAULT_HEIGHT_RATIO),
            }
        )
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": self._get_launch_cwd(),
            "env": env,
        }
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if create_no_window:
            kwargs["creationflags"] = create_no_window

        try:
            process = subprocess.Popen(command, **kwargs)
        except OSError as exc:
            logging.error("Impossible de lancer l'overlay Qt persistant: %s", exc)
            self._process = None
            return False, "Impossible de lancer l'overlay Qt."

        self._process = process
        self._last_url = url
        self._mode = mode
        self._visible = True
        time.sleep(self.STARTUP_GRACE_SECONDS)
        if self._process.poll() is not None:
            self._process = None
            self._visible = False
            return False, "L'overlay Qt s'est ferme au lancement."
        return True, f"Overlay stats {mode} ouvert."

    def _build_launch_command(self, url: str, mode: str) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--overlay-host"]
        return [sys.executable, "-m", "src.ui.overlay_host", "--overlay-host"]

    def _send_command(self, command: str, **payload) -> bool:
        if not (self.is_running() and self._port and self._token):
            return False
        try:
            send_overlay_command(self._port, self._token, command, **payload)
            return True
        except OSError as exc:
            logging.debug("Impossible d'envoyer une commande overlay: %s", exc)
            self._process = None
            self._visible = False
            return False

    def _get_launch_cwd(self) -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
