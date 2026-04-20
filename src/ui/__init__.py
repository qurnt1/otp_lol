"""
FILE NAME: src/ui/__init__.py
GLOBAL PURPOSE:
- Provide the public API for the UI layer.
- Re-export the main UI classes used by launcher and other modules.
- Keep imports independent from the internal UI file layout.

KEY FUNCTIONS:
- None.

AUDIENCE & LOGIC:
Why:
This package facade keeps UI imports simple and stable.
For whom:
Developers importing the main UI classes.

DEPENDENCIES:
Used by:
- launcher.py and modules importing from `src.ui`.
Uses:
- Local modules: src.ui.main_window, src.ui.settings_window
"""

from .main_window import LoLAssistantUI
from .settings_window import SettingsWindow

__all__ = ["LoLAssistantUI", "SettingsWindow"]
