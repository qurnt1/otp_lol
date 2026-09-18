"""Small pywebview bridge for native desktop window controls."""

from __future__ import annotations

import os
import webbrowser
from typing import TYPE_CHECKING

from ..services.urls import (
    build_provider_url,
    is_allowed_external_url,
    is_allowed_provider_url,
    resolve_provider_account,
)

if TYPE_CHECKING:
    from .window import WebViewWindow


class DesktopBridge:
    """Expose the small set of native window operations used by the React shell."""

    def __init__(self, context=None) -> None:
        self._window: WebViewWindow | None = None
        self._context = context
        self._provider_windows = {}

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

    def open_provider_window(self, provider_id: str, kind: str) -> bool:
        """Open a selected account provider without accepting frontend-supplied URLs."""
        if self._context is None or kind not in {"stats", "live"}:
            return False
        params = self._context.get_params()
        setting = "preferred_stats_site" if kind == "stats" else "preferred_hotkey_site"
        if str(params.get(setting) or "").strip().lower() != str(provider_id or "").strip().lower():
            return False
        riot_id, region, _account_source = resolve_provider_account(params, self._context.runtime)
        url = build_provider_url(provider_id, kind, region, riot_id)
        if not url or not is_allowed_provider_url(provider_id, url):
            return False

        key = (provider_id, kind)
        existing = self._provider_windows.get(key)
        if existing is not None and existing.window is not None:
            existing.window.show()
            return True

        from .provider_browser import ProviderBrowserWindow

        provider_window = ProviderBrowserWindow(
            provider_id,
            url,
            on_closed=lambda: self._provider_windows.pop(key, None),
        )
        if not provider_window.open():
            return False
        self._provider_windows[key] = provider_window
        return True

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
