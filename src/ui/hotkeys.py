"""
FILE NAME: src/ui/hotkeys.py
GLOBAL PURPOSE:
- Register and remove global keyboard shortcuts for the desktop app.
- Isolate OS-level keyboard-hook behavior from the main UI logic.
- Keep hotkey cleanup explicit during reloads and shutdown.

KEY FUNCTIONS:
- HotkeyManager: Own global hotkey registration and cleanup.
- setup: Register the current hotkey set and roll back cleanly on failure.
- shutdown: Remove all registered hotkeys.

AUDIENCE & LOGIC:
Why:
This module exists so keyboard-hook setup and cleanup stay isolated from the main window lifecycle code.
For whom:
Developers maintaining global shortcuts and hotkey reliability.

DEPENDENCIES:
Used by:
- src.ui.main_window
Uses:
- Standard library: logging
- Third-party library: keyboard
"""

import logging

import keyboard


class HotkeyManager:
    """Manage global keyboard hotkeys and their cleanup lifecycle."""

    def __init__(self):
        self.available = False
        self.handles = []

    def setup(self, toggle_window, open_hotkey_site, toggle_hotkey: str, stats_hotkey: str) -> bool:
        """Register the global hotkeys through the OS-level keyboard hook."""
        registered_handles = []
        try:
            # Clear any previous registrations first so reloads never leave stale hooks behind.
            self.shutdown()
            registered_handles.append(keyboard.add_hotkey(stats_hotkey, open_hotkey_site))
            registered_handles.append(keyboard.add_hotkey(toggle_hotkey, toggle_window))
            self.handles = registered_handles
            self.available = True
        except Exception as e:
            for handle in registered_handles:
                try:
                    keyboard.remove_hotkey(handle)
                except Exception:
                    pass
            self.available = False
            self.handles = []
            logging.debug("Unable to configure hotkeys: %s", e)
        return self.available

    def shutdown(self) -> None:
        """Remove all registered global hotkeys and reset manager state."""
        for handle in self.handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception as e:
                logging.debug("Error removing hotkey: %s", e)
        self.handles = []
        self.available = False
