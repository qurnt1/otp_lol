"""
FILE NAME: src/services/platform.py
GLOBAL PURPOSE:
- Hold small platform-specific runtime helpers.
- Configure Windows-specific process behavior needed by the desktop UI.
- Keep OS integration details out of launcher and UI modules.

KEY FUNCTIONS:
- enable_high_dpi: Enable Windows DPI awareness for sharper desktop rendering.

AUDIENCE & LOGIC:
Why:
This module exists so OS-specific behavior can stay isolated from the rest of the application.
For whom:
Developers maintaining Windows integration or startup behavior.

DEPENDENCIES:
Used by:
- launcher.py through src.utils.
Uses:
- ctypes on Windows when available.
"""


def enable_high_dpi() -> None:
    """Enable High DPI awareness on Windows."""
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
