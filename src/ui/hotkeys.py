"""Hotkey helpers for the main window."""

import logging

import keyboard


class HotkeyManager:
    """Manage keyboard hotkeys and their cleanup."""

    def __init__(self):
        self.available = False
        self.handles = []

    def setup(
        self,
        toggle_window,
        open_hotkey_site,
        toggle_overlay_mode,
        toggle_hotkey: str,
        stats_hotkey: str,
        overlay_mode_hotkey: str,
    ) -> bool:
        try:
            self.shutdown()
            self.handles = [
                keyboard.add_hotkey(stats_hotkey, open_hotkey_site),
                keyboard.add_hotkey(toggle_hotkey, toggle_window),
                keyboard.add_hotkey(overlay_mode_hotkey, toggle_overlay_mode),
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
