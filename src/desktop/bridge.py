"""Small pywebview bridge for native desktop window controls."""

from __future__ import annotations

import json
import logging
import os
import webbrowser
from typing import TYPE_CHECKING

from ..services.urls import (
    is_allowed_external_url,
)

if TYPE_CHECKING:
    from .window import WebViewWindow

LOGGER = logging.getLogger("otp_lol.bridge")


class DesktopBridge:
    """Expose the small set of native window operations used by the React shell."""

    def __init__(self, context=None) -> None:
        self._window: WebViewWindow | None = None
        self._context = context
        from .provider_browser import ProviderWindowManager

        self._provider_manager = ProviderWindowManager(context)
        if context is not None:
            context.provider_window_manager = self._provider_manager
        # Compatibility view for callers/tests that inspected the old per-kind mapping.
        self._provider_windows = self._provider_manager._windows

    def attach(self, window: WebViewWindow) -> None:
        self._window = window

    def resize_window(self, width: int, height: int) -> None:
        if self._window is None or not self._window.native_ready:
            return
        self._window.resize(width, height)

    def toggle_fullscreen(self) -> bool:
        """Toggle fullscreen when the installed pywebview backend supports it."""
        if self._window is None or not self._window.native_ready or self._window.window is None:
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

    def open_provider_window_result(self, provider_id: str, kind: str) -> dict[str, object]:
        """Return a structured provider action result for diagnostics."""
        if self._context is None:
            return {"ok": False, "reason": "context_unavailable", "state": "not_created"}
        if self._window is not None and not self._window.native_ready:
            return {"ok": False, "reason": "bridge_not_ready", "state": "not_created"}
        # A bridge without an attached native window is the deterministic test/browser facade.
        if self._window is None:
            self._provider_manager.mark_main_window_shown(preload=False)
        result = self._provider_manager.open_result(provider_id, kind)
        LOGGER.info(
            "provider_open provider=%s kind=%s ok=%s reason=%s state=%s",
            provider_id,
            kind,
            result.get("ok"),
            result.get("reason"),
            result.get("state"),
        )
        return result

    def open_provider_window(self, provider_id: str, kind: str) -> bool:
        """Open a selected account provider without accepting frontend-supplied URLs."""
        return bool(self.open_provider_window_result(provider_id, kind).get("ok"))

    def reload_provider_window_result(self, kind: str) -> dict[str, object]:
        if self._window is not None and not self._window.native_ready:
            return {"ok": False, "reason": "bridge_not_ready", "state": "not_created"}
        if self._window is None:
            self._provider_manager.mark_main_window_shown(preload=False)
        ok = self._provider_manager.reload(kind)
        status = self._provider_manager.status().get(kind, {})
        return {
            "ok": ok,
            "reason": None if ok else status.get("last_error") or "reload_failed",
            "state": status.get("state", "not_created"),
        }

    def reload_provider_window(self, kind: str) -> bool:
        return bool(self.reload_provider_window_result(kind).get("ok"))

    def provider_window_status(self) -> dict:
        return self._provider_manager.status()

    def mark_main_window_shown(self) -> None:
        self._provider_manager.mark_main_window_shown()

    def notify_provider_identity_updated(self) -> None:
        self._provider_manager.notify_identity_updated()

    def shutdown(self) -> None:
        self._provider_manager.shutdown()

    def export_diagnostics_report(self, include_riot_id: bool = False) -> dict[str, object]:
        """Save one redacted diagnostics report through the native save dialog."""
        if self._context is None or self._window is None or not self._window.native_ready:
            return {"success": False, "error": "native_bridge_unavailable"}
        report = self._context.diagnostics.export(bool(include_riot_id))
        native_window = self._window.window
        create_dialog = getattr(native_window, "create_file_dialog", None)
        if not callable(create_dialog):
            return {"success": False, "error": "save_dialog_unavailable"}
        try:
            import webview

            selected = create_dialog(
                webview.SAVE_DIALOG,
                save_filename="otp-lol-diagnostics.json",
                file_types=("JSON files (*.json)", "All files (*.*)"),
            )
        except (AttributeError, OSError, RuntimeError, TypeError) as error:
            return {"success": False, "error": str(error)}
        path = selected[0] if isinstance(selected, (list, tuple)) and selected else selected
        if not path:
            return {"success": False, "cancelled": True}
        try:
            with open(os.fspath(path), "w", encoding="utf-8", newline="\n") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except (OSError, TypeError, ValueError) as error:
            return {"success": False, "error": str(error)}
        return {"success": True, "path": os.fspath(path)}

    save_diagnostics_report = export_diagnostics_report

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
