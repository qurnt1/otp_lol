"""Dedicated pywebview host for the in-game stats overlay.

The main Tk application already owns the primary GUI loop, while pywebview
expects to run on a main thread as well. Running the overlay in a dedicated
process keeps both toolkits isolated and avoids focus / shutdown conflicts.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
from typing import Sequence


DEFAULT_OVERLAY_TITLE = "MAIN LOL - Overlay stats"
DEFAULT_WIDTH_RATIO = 0.92
DEFAULT_HEIGHT_RATIO = 0.88
MIN_OVERLAY_WIDTH = 960
MIN_OVERLAY_HEIGHT = 700
MAX_OVERLAY_WIDTH = 2200
MAX_OVERLAY_HEIGHT = 1400
SPI_GETWORKAREA = 0x0030
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = -1


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MAIN LOL stats overlay host")
    parser.add_argument("--stats-overlay", action="store_true", help="Internal flag used by the frozen app entrypoint.")
    parser.add_argument("--url", required=True, help="Stats page to display in the overlay window.")
    parser.add_argument("--title", default=DEFAULT_OVERLAY_TITLE, help="Overlay window title.")
    parser.add_argument("--width-ratio", type=float, default=DEFAULT_WIDTH_RATIO, help="Overlay width as a fraction of the work area.")
    parser.add_argument("--height-ratio", type=float, default=DEFAULT_HEIGHT_RATIO, help="Overlay height as a fraction of the work area.")
    parser.add_argument("--x", type=int, default=-1, help="Optional X position. Negative values keep the default placement.")
    parser.add_argument("--y", type=int, default=-1, help="Optional Y position. Negative values keep the default placement.")
    return parser


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def get_work_area() -> tuple[int, int, int, int]:
    """Return the usable desktop work area, excluding the taskbar on Windows."""
    rect = RECT()
    try:
        if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception as exc:
        logging.debug("Impossible de lire la zone de travail Windows: %s", exc)

    try:
        user32 = ctypes.windll.user32
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception as exc:
        logging.debug("Impossible de lire la taille d'ecran Windows: %s", exc)
        return 0, 0, 1920, 1080


def compute_overlay_geometry(width_ratio: float, height_ratio: float, x: int = -1, y: int = -1) -> tuple[int, int, int, int]:
    """Compute a centered overlay geometry from the current desktop work area."""
    left, top, right, bottom = get_work_area()
    work_width = max(800, right - left)
    work_height = max(600, bottom - top)
    safe_width_ratio = min(max(width_ratio, 0.45), 0.98)
    safe_height_ratio = min(max(height_ratio, 0.45), 0.98)
    width = clamp(int(work_width * safe_width_ratio), MIN_OVERLAY_WIDTH, min(MAX_OVERLAY_WIDTH, work_width))
    height = clamp(int(work_height * safe_height_ratio), MIN_OVERLAY_HEIGHT, min(MAX_OVERLAY_HEIGHT, work_height))
    target_x = x if x >= 0 else left + max(0, (work_width - width) // 2)
    target_y = y if y >= 0 else top + max(0, (work_height - height) // 2)
    return width, height, target_x, target_y


def _resolve_hwnd(window) -> int | None:
    native = getattr(window, "native", None)
    if native is None:
        return None

    handle = getattr(native, "Handle", None)
    if handle is None:
        return None

    try:
        if hasattr(handle, "ToInt64"):
            return int(handle.ToInt64())
        return int(handle)
    except Exception:
        return None


def _apply_windows_overlay_behavior(window, width: int, height: int, x: int, y: int) -> None:
    """Reinforce topmost + no-activate behaviour on Windows using the native handle."""
    hwnd = _resolve_hwnd(window)
    if not hwnd:
        return

    try:
        user32 = ctypes.windll.user32
        get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        ex_style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            x,
            y,
            width,
            height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_FRAMECHANGED,
        )
    except Exception as exc:
        logging.debug("Impossible de renforcer le comportement Windows de l'overlay: %s", exc)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        import webview
    except Exception as exc:  # pragma: no cover - depends on local runtime
        logging.error("Impossible de charger pywebview pour l'overlay stats: %s", exc)
        return 1

    width, height, x, y = compute_overlay_geometry(args.width_ratio, args.height_ratio, args.x, args.y)

    window_kwargs = {
        "on_top": True,
        "focus": False,
        "width": width,
        "height": height,
        "x": x,
        "y": y,
        "resizable": True,
    }

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    window = webview.create_window(args.title, args.url, **window_kwargs)
    try:
        window.events.before_show += lambda *args: _apply_windows_overlay_behavior(window, width, height, x, y)
    except Exception as exc:
        logging.debug("Impossible d'attacher le hook before_show de l'overlay: %s", exc)
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
