"""Platform-specific helpers."""


def enable_high_dpi() -> None:
    """Enable High DPI awareness on Windows."""
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
