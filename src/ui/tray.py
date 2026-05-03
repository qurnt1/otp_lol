"""
FILE NAME: src/ui/tray.py
GLOBAL PURPOSE:
- Create and manage the system tray icon for the desktop app.
- Expose tray actions that delegate back to the main window callbacks.
- Keep pystray integration and cleanup outside the main UI module.

KEY FUNCTIONS:
- TrayController: Wrap tray setup, menu refresh, and shutdown.
- setup: Build the tray icon and register tray menu callbacks.
- shutdown: Stop the tray icon cleanly during application shutdown.

AUDIENCE & LOGIC:
Why:
This module exists so system tray integration remains isolated from the rest of the UI lifecycle code.
For whom:
Developers maintaining tray behavior, callback wiring, and pystray integration.

DEPENDENCIES:
Used by:
- src.ui.main_window
Uses:
- Standard library: logging
- Third-party libraries: Pillow, pystray
- Local modules: src.config
"""

import logging

import pystray
from PIL import Image

from ..config import APP_IMAGE_FILES, APP_NAME, resource_path


class TrayController:
    """Wrap system tray creation, menu callbacks, and shutdown cleanup."""

    def __init__(self):
        self.icon = None
        self.available = False

    def setup(
        self,
        executor,
        toggle_window,
        open_settings,
        toggle_presets_automation,
        toggle_auto_ban,
        is_presets_automation_enabled,
        is_auto_ban_enabled,
        quit_callback,
        on_failure,
    ) -> bool:
        """Create the tray icon, wire callbacks, and run the tray loop in the provided executor."""
        try:
            image = Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((64, 64))

            def on_toggle(icon=None, item=None):
                try:
                    toggle_window()
                except Exception as e:
                    logging.debug("Tray toggle callback error: %s", e)

            def on_settings(icon=None, item=None):
                try:
                    open_settings()
                except Exception as e:
                    logging.debug("Tray settings callback error: %s", e)

            def on_presets(icon=None, item=None):
                try:
                    toggle_presets_automation()
                    if self.icon:
                        self.icon.update_menu()
                except Exception as e:
                    logging.debug("Tray presets callback error: %s", e)

            def on_auto_ban(icon=None, item=None):
                try:
                    toggle_auto_ban()
                    if self.icon:
                        self.icon.update_menu()
                except Exception as e:
                    logging.debug("Tray auto-ban callback error: %s", e)

            def on_quit(icon=None, item=None):
                try:
                    quit_callback()
                except Exception as e:
                    logging.debug("Tray quit callback error: %s", e)

            menu = pystray.Menu(
                pystray.MenuItem("Show/Hide", on_toggle),
                pystray.MenuItem("Settings", on_settings),
                pystray.MenuItem(
                    "Enable presets automations",
                    on_presets,
                    checked=lambda item: bool(is_presets_automation_enabled()),
                ),
                pystray.MenuItem(
                    "Auto-ban",
                    on_auto_ban,
                    checked=lambda item: bool(is_auto_ban_enabled()),
                ),
                pystray.MenuItem("Quit", on_quit),
            )
            self.icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
            self.available = True

            def run_tray():
                """Run the pystray loop and report failures back to the UI layer."""
                try:
                    self.icon.run()
                except Exception as e:
                    self.available = False
                    logging.debug("System tray error: %s", e)
                    on_failure()

            executor.submit(run_tray)
        except Exception as e:
            self.available = False
            logging.warning("Unable to create system tray: %s", e)
        return self.available

    def shutdown(self) -> None:
        """Stop the tray icon when it was created successfully."""
        try:
            if self.icon:
                self.icon.stop()
        except Exception as e:
            logging.debug("Error stopping tray icon: %s", e)
