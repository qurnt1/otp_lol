"""Hotkey helpers for the main window."""

import logging

import keyboard


class HotkeyManager:
    """Manage keyboard hotkeys and their cleanup."""

    def __init__(self):
        self.available = False
        self.handles = []

    def setup(self, toggle_window, open_hotkey_site, toggle_hotkey: str, stats_hotkey: str) -> bool:
        """Register the global hotkeys through the OS-level keyboard hook."""
        registered_handles = []
        try:
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
            logging.debug(f"Unable to configure hotkeys: {e}")
        return self.available

    def shutdown(self) -> None:
        """Remove all registered global hotkeys."""
        for handle in self.handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception as e:
                logging.debug(f"Error removing hotkey: {e}")
        self.handles = []
        self.available = False
