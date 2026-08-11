"""PySide6 desktop presentation layer."""

__all__ = ["CoreEventBridge", "DesktopApplication", "MainWindow"]


def __getattr__(name: str):
    if name == "CoreEventBridge":
        from .event_bridge import CoreEventBridge

        return CoreEventBridge
    if name == "DesktopApplication":
        from .application import DesktopApplication

        return DesktopApplication
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
