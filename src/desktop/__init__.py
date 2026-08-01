"""PyQt6 desktop presentation layer."""

from .application import DesktopApplication
from .event_bridge import CoreEventBridge
from .main_window import MainWindow

__all__ = ["CoreEventBridge", "DesktopApplication", "MainWindow"]
