"""Public UI API for MAIN LOL.

This package uses lazy imports so lightweight helper processes such as the
Qt overlay host can import ``src.ui.<module>`` without eagerly loading the
main Tk UI and its optional dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["LoLAssistantUI", "SettingsWindow", "TelegramSettingsWindow"]


def __getattr__(name: str) -> Any:
    if name == "LoLAssistantUI":
        return import_module(".main_window", __name__).LoLAssistantUI
    if name == "SettingsWindow":
        return import_module(".settings_window", __name__).SettingsWindow
    if name == "TelegramSettingsWindow":
        return import_module(".telegram_window", __name__).TelegramSettingsWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

