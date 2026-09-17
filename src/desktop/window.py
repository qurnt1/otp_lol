"""Small lifecycle wrapper around pywebview's native window API."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

_WEBVIEW2_CLIENT_GUIDS = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",
)
_APP_ROUTES = frozenset({
    "dashboard",
    "presets",
    "statistics",
    "live",
    "history",
    *(f"settings/{section}" for section in (
        "general",
        "automations",
        "account",
        "links",
        "shortcuts",
        "appearance",
        "advanced",
    )),
})


def has_webview2_runtime() -> bool:
    """Return whether a registered Microsoft Edge WebView2 runtime is available."""
    if sys.platform != "win32":
        return True

    import winreg

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for guid in _WEBVIEW2_CLIENT_GUIDS:
            for suffix in ("", r"WOW6432Node"):
                registry_prefix = r"SOFTWARE\Microsoft" if not suffix else rf"SOFTWARE\{suffix}\Microsoft"
                path = rf"{registry_prefix}\EdgeUpdate\Clients\{guid}"
                try:
                    with winreg.OpenKey(root, path) as key:
                        version, _ = winreg.QueryValueEx(key, "pv")
                    if str(version).strip() and str(version).strip() != "0.0.0.0":
                        return True
                except OSError:
                    continue
    return False


@dataclass(frozen=True, slots=True)
class WebViewWindowConfig:
    title: str
    url: str
    width: int = 1100
    height: int = 760
    min_width: int = 800
    min_height: int = 540
    icon: str | None = None
    resizable: bool = True
    js_api: Any = None
    x: int | None = None
    y: int | None = None
    maximized: bool = False


class WebViewWindow:
    """Create and start one pywebview window without importing it at module load."""

    def __init__(self, config: WebViewWindowConfig) -> None:
        self.config = config
        self.window = None
        self._visible = True
        self._maximized = config.maximized

    def create(self) -> None:
        import webview

        create_kwargs = {
            "url": self.config.url,
            "width": self.config.width,
            "height": self.config.height,
            "min_size": (self.config.min_width, self.config.min_height),
            "resizable": self.config.resizable,
            "maximized": self.config.maximized,
            "js_api": self.config.js_api,
        }
        if (
            self.config.x is not None
            and self.config.y is not None
            and _valid_window_position(self.config.x, self.config.y)
        ):
            create_kwargs.update(x=self.config.x, y=self.config.y)
        self.window = webview.create_window(self.config.title, **create_kwargs)
        events = getattr(self.window, "events", None)
        if events is not None:
            maximized = getattr(events, "maximized", None)
            restored = getattr(events, "restored", None)
            if maximized is not None:
                maximized += lambda: setattr(self, "_maximized", True)
            if restored is not None:
                restored += lambda: setattr(self, "_maximized", False)

    def restore_geometry(self, params: dict[str, Any]) -> None:
        """Restore saved bounds when their top-left corner can still be displayed."""
        if self.window is None or not self._native_window_ready():
            return
        width = max(int(params.get("window_width", self.config.width)), self.config.min_width)
        height = max(int(params.get("window_height", self.config.height)), self.config.min_height)
        x = int(params.get("window_x", 0) or 0)
        y = int(params.get("window_y", 0) or 0)
        if _valid_window_position(x, y):
            move = getattr(self.window, "move", None)
            if callable(move):
                move(x, y)
        self.resize(width, height)
        if bool(params.get("window_maximized")):
            maximize = getattr(self.window, "maximize", None)
            if callable(maximize):
                maximize()
                self._maximized = True

    def geometry(self) -> dict[str, Any]:
        """Read native bounds defensively for shutdown persistence."""
        if self.window is None or not self._native_window_ready():
            return {}
        result: dict[str, Any] = {}
        get_size = getattr(self.window, "get_size", None)
        get_position = getattr(self.window, "get_position", None)
        if callable(get_size):
            try:
                width, height = get_size()
                result.update(window_width=int(width), window_height=int(height))
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                pass
        if "window_width" not in result or "window_height" not in result:
            try:
                result.update(
                    window_width=int(getattr(self.window, "width")),
                    window_height=int(getattr(self.window, "height")),
                )
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                pass
        if callable(get_position):
            try:
                x, y = get_position()
                result.update(window_x=int(x), window_y=int(y))
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                pass
        if "window_x" not in result or "window_y" not in result:
            try:
                result.update(
                    window_x=int(getattr(self.window, "x")),
                    window_y=int(getattr(self.window, "y")),
                )
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                pass
        maximized = getattr(self.window, "is_maximized", None)
        if not isinstance(maximized, bool):
            maximized = self._maximized
        result["window_maximized"] = maximized
        return result

    def _native_window_ready(self) -> bool:
        """Avoid pywebview calls that wait until the native window is shown."""
        if self.window is None:
            return False
        events = getattr(self.window, "events", None)
        shown = getattr(events, "shown", None)
        is_set = getattr(shown, "is_set", None)
        return bool(is_set()) if callable(is_set) else True

    def start(self) -> None:
        if not has_webview2_runtime():
            raise RuntimeError("Microsoft Edge WebView2 Runtime is required to open OTP LOL.")

        import webview

        webview.start(debug=False, icon=self.config.icon)

    def show(self) -> None:
        """Show the native window when a tray or hotkey callback requests it."""
        if self.window is not None:
            self.window.show()
            self._visible = True

    def hide(self) -> None:
        """Hide the native window without destroying the embedded application."""
        if self.window is not None:
            self.window.hide()
            self._visible = False

    @property
    def visible(self) -> bool:
        return self._visible

    def destroy(self) -> None:
        """Close the native window and let the shell finish its shutdown path."""
        if self.window is not None:
            self.window.destroy()
        self._visible = False

    def resize(self, width: int, height: int) -> None:
        """Resize the native window when the React route changes its density."""
        if self.window is not None:
            self.window.resize(max(width, self.config.min_width), max(height, self.config.min_height))

    def open_route(self, route: str) -> bool:
        """Show the native window and navigate to a known frontend route."""
        if self.window is None or route not in _APP_ROUTES:
            return False
        if getattr(self.window, "minimized", False):
            restore = getattr(self.window, "restore", None)
            if callable(restore):
                restore()
        self.window.show()
        self._visible = True
        base_url = self.config.url.split("#", 1)[0]
        self.window.load_url(f"{base_url}#{route}")
        return True

    def open_settings(self) -> None:
        """Navigate the frontend to its default settings section."""
        self.open_route("settings/general")


def _valid_window_position(x: int, y: int) -> bool:
    """Reject stale coordinates that would place the window entirely off-screen."""
    if sys.platform != "win32":
        return x >= -100 and y >= -100
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        rect_type = wintypes.RECT

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", rect_type), ("rcWork", rect_type), ("dwFlags", wintypes.DWORD)]

        work_areas: list[tuple[int, int, int, int]] = []
        callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)

        @callback_type(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(rect_type), wintypes.LPARAM)
        def collect_work_area(monitor, _dc, _rect, _data):
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(MonitorInfo)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                area = info.rcWork
                work_areas.append((int(area.left), int(area.top), int(area.right), int(area.bottom)))
            return 1

        if user32.EnumDisplayMonitors(None, None, collect_work_area, 0) and work_areas:
            return any(x < right and x + 40 > left and y < bottom and y + 40 > top for left, top, right, bottom in work_areas)

        virtual_left = int(user32.GetSystemMetrics(76))
        virtual_top = int(user32.GetSystemMetrics(77))
        virtual_width = int(user32.GetSystemMetrics(78))
        virtual_height = int(user32.GetSystemMetrics(79))
        return x < virtual_left + virtual_width and x + 40 > virtual_left and y < virtual_top + virtual_height and y + 40 > virtual_top
    except (AttributeError, OSError, TypeError, ValueError):
        return x >= -100 and y >= -100
