"""Qt WebEngine host for the frameless in-game stats overlay."""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from typing import Sequence

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView


DEFAULT_OVERLAY_TITLE = "MAIN LOL - Overlay stats"
DEFAULT_WIDTH_RATIO = 0.92
DEFAULT_HEIGHT_RATIO = 0.88
MIN_OVERLAY_WIDTH = 960
MIN_OVERLAY_HEIGHT = 700
MAX_OVERLAY_WIDTH = 2200
MAX_OVERLAY_HEIGHT = 1400
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = -1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MAIN LOL Qt stats overlay host")
    parser.add_argument("--qt-overlay", action="store_true", help="Internal flag used by the frozen app entrypoint.")
    parser.add_argument("--url", required=True, help="Stats page to display in the overlay window.")
    parser.add_argument("--title", default=DEFAULT_OVERLAY_TITLE, help="Overlay window title.")
    parser.add_argument("--width-ratio", type=float, default=DEFAULT_WIDTH_RATIO, help="Overlay width as a fraction of the work area.")
    parser.add_argument("--height-ratio", type=float, default=DEFAULT_HEIGHT_RATIO, help="Overlay height as a fraction of the work area.")
    parser.add_argument("--x", type=int, default=-1, help="Optional X position. Negative values keep the default placement.")
    parser.add_argument("--y", type=int, default=-1, help="Optional Y position. Negative values keep the default placement.")
    return parser


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def compute_overlay_geometry(app: QApplication, width_ratio: float, height_ratio: float, x: int = -1, y: int = -1) -> tuple[int, int, int, int]:
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
    def __init__(self, url: str, title: str, width: int, height: int, x: int, y: int) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._x = x
        self._y = y
        self.setWindowTitle(title)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        if hasattr(Qt.WindowType, "WindowDoesNotAcceptFocus"):
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags)
        if hasattr(Qt.WidgetAttribute, "WA_ShowWithoutActivating"):
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if hasattr(Qt.WidgetAttribute, "WA_DontCreateNativeAncestors"):
            self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setGeometry(x, y, width, height)

        self.view = QWebEngineView(self)
        self.view.setUrl(QUrl(url))
        self.setCentralWidget(self.view)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#11161e"))
        self.setPalette(palette)

    def showEvent(self, event) -> None:  # pragma: no cover - requires real GUI
        super().showEvent(event)
        QTimer.singleShot(0, self._reinforce_windows_overlay_style)

    def _reinforce_windows_overlay_style(self) -> None:  # pragma: no cover - requires real GUI
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            ex_style = get_window_long(hwnd, GWL_EXSTYLE)
            set_window_long(hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                self._x,
                self._y,
                self._width,
                self._height,
                SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_FRAMECHANGED,
            )
        except Exception as exc:
            logging.debug("Impossible d'appliquer les styles Windows de l'overlay Qt: %s", exc)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    width, height, x, y = compute_overlay_geometry(app, args.width_ratio, args.height_ratio, args.x, args.y)
    window = OverlayWindow(args.url, args.title, width, height, x, y)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
