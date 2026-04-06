"""Qt overlay window used for the persistent in-game stats view."""

from __future__ import annotations

import ctypes
import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

from .overlay_runtime import MODE_INTERACTIVE, MODE_PASSIVE, normalize_overlay_mode


MIN_OVERLAY_WIDTH = 960
MIN_OVERLAY_HEIGHT = 700
MAX_OVERLAY_WIDTH = 2200
MAX_OVERLAY_HEIGHT = 1400
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def compute_overlay_geometry(
    app: QApplication,
    width_ratio: float,
    height_ratio: float,
    x: int = -1,
    y: int = -1,
) -> tuple[int, int, int, int]:
    screen = app.primaryScreen()
    rect = screen.availableGeometry() if screen else None
    screen_x = rect.x() if rect else 0
    screen_y = rect.y() if rect else 0
    screen_width = rect.width() if rect else 1920
    screen_height = rect.height() if rect else 1080
    safe_width_ratio = min(max(width_ratio, 0.45), 0.98)
    safe_height_ratio = min(max(height_ratio, 0.45), 0.98)
    width = clamp(int(screen_width * safe_width_ratio), MIN_OVERLAY_WIDTH, min(MAX_OVERLAY_WIDTH, screen_width))
    height = clamp(int(screen_height * safe_height_ratio), MIN_OVERLAY_HEIGHT, min(MAX_OVERLAY_HEIGHT, screen_height))
    target_x = x if x >= 0 else screen_x + max(0, (screen_width - width) // 2)
    target_y = y if y >= 0 else screen_y + max(0, (screen_height - height) // 2)
    return width, height, target_x, target_y


class OverlayWindow(QMainWindow):
    """Persistent Qt overlay with interactive and passive modes."""

    def __init__(self, title: str, width: int, height: int, x: int, y: int, initial_mode: str) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._x = x
        self._y = y
        self._mode = normalize_overlay_mode(initial_mode)
        self._current_url = ""
        self._configure_window(title)
        self._build_view()
        self._apply_mode(activate=False)

    @property
    def mode(self) -> str:
        return self._mode

    def _configure_window(self, title: str) -> None:
        self.setWindowTitle(title)
        self.setGeometry(self._x, self._y, self._width, self._height)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#11161e"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def _build_view(self) -> None:
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

    def navigate(self, url: str) -> None:
        url = str(url or "").strip()
        if not url or url == self._current_url:
            return
        self._current_url = url
        self.view.setUrl(QUrl(url))

    def show_overlay(self, activate: bool = False) -> None:
        self._apply_mode(activate=activate)
        self.show()
        self.raise_()
        self._apply_windows_overlay_style(passive=(self._mode == MODE_PASSIVE))
        if activate:
            self.activateWindow()
            self.view.setFocus()

    def hide_overlay(self) -> None:
        self.hide()

    def set_mode(self, mode: str, *, activate: bool | None = None) -> str:
        self._mode = normalize_overlay_mode(mode)
        self._apply_mode(activate=(self._mode == MODE_INTERACTIVE) if activate is None else activate)
        return self._mode

    def toggle_mode(self) -> str:
        next_mode = MODE_PASSIVE if self._mode == MODE_INTERACTIVE else MODE_INTERACTIVE
        return self.set_mode(next_mode, activate=(next_mode == MODE_INTERACTIVE))

    def _apply_mode(self, *, activate: bool) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        passive = self._mode == MODE_PASSIVE
        if passive and hasattr(Qt.WindowType, "WindowDoesNotAcceptFocus"):
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus if passive else Qt.FocusPolicy.StrongFocus)
        if hasattr(Qt.WidgetAttribute, "WA_ShowWithoutActivating"):
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, passive)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, passive)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, passive)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus if passive else Qt.FocusPolicy.StrongFocus)
        if self.isVisible():
            self.show()
            self.raise_()
            if activate and not passive:
                self.activateWindow()
                self.view.setFocus()
        self._apply_windows_overlay_style(passive=passive)

    def _apply_windows_overlay_style(self, *, passive: bool) -> None:
        """Reinforce overlay behaviour with native Windows styles."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            ex_style = int(get_window_long(hwnd, GWL_EXSTYLE))
            ex_style |= WS_EX_TOOLWINDOW
            if passive:
                ex_style |= WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
            else:
                ex_style &= ~WS_EX_NOACTIVATE
                ex_style &= ~WS_EX_TRANSPARENT
            set_window_long(hwnd, GWL_EXSTYLE, ex_style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | (SWP_NOACTIVATE if passive else 0),
            )
        except Exception as exc:  # pragma: no cover - needs real Windows GUI
            logging.debug("Impossible d'appliquer les styles Windows overlay: %s", exc)
