"""Small pywebview bridge for native desktop window controls."""

from __future__ import annotations

from typing import TYPE_CHECKING
import os
import webbrowser

from ..services.urls import is_allowed_external_url

if TYPE_CHECKING:
    from .window import WebViewWindow


class DesktopBridge:
    """Expose the small set of native window operations used by the React shell."""

    def __init__(self) -> None:
        self._window: WebViewWindow | None = None

    def attach(self, window: WebViewWindow) -> None:
        self._window = window

    def resize_window(self, width: int, height: int) -> None:
        if self._window is None:
            return
        self._window.resize(width, height)

    def toggle_fullscreen(self) -> bool:
        """Toggle fullscreen when the installed pywebview backend supports it."""
        if self._window is None or self._window.window is None:
            return False
        toggle = getattr(self._window.window, "toggle_fullscreen", None)
        if not callable(toggle):
            return False
        toggle()
        return True

    def open_external_url(self, url: str) -> bool:
        """Open an allowlisted HTTPS provider URL in the system browser."""
        if not is_allowed_external_url(url):
            return False
        return bool(webbrowser.open(url))

    def open_local_folder(self, folder: str) -> bool:
        """Open only application-owned folders from the Advanced settings page."""
        from ..config import LOG_FILE_PATH, PARAMETERS_PATH

        if folder == "logs":
            target = os.path.dirname(LOG_FILE_PATH)
        elif folder == "appdata":
            target = os.path.dirname(PARAMETERS_PATH)
        else:
            return False
        if not os.path.isdir(target):
            return False
        try:
            os.startfile(target)
        except (AttributeError, OSError):
            return False
        return True
