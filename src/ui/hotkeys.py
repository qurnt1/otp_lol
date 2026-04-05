"""Hotkey helpers for the main window."""

import logging

import keyboard


class HotkeyManager:
    """Manage keyboard hotkeys and their cleanup."""

    def __init__(self):
        self.available = False
        self.handles = []

    def setup(self, toggle_window, open_porofessor) -> bool:
        try:
            self.handles = [
                keyboard.add_hotkey("alt+p", open_porofessor),
                keyboard.add_hotkey("alt+c", toggle_window),
            ]
            self.available = True
        except Exception as e:
            self.available = False
            self.handles = []
            logging.debug(f"Impossible de configurer les hotkeys: {e}")
        return self.available

    def shutdown(self) -> None:
        for handle in self.handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception as e:
                logging.debug(f"Erreur suppression hotkey: {e}")
        self.handles = []
