"""System tray helpers for the main window."""

import logging

import pystray
from PIL import Image

from ..config import APP_IMAGE_FILES, APP_NAME, resource_path


class TrayController:
    """Wrap systray creation and cleanup."""

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
        try:
            image = Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((64, 64))

            def on_toggle(icon=None, item=None):
                try:
                    toggle_window()
                except Exception as e:
                    logging.debug(f"Tray toggle callback error: {e}")

            def on_settings(icon=None, item=None):
                try:
                    open_settings()
                except Exception as e:
                    logging.debug(f"Tray settings callback error: {e}")

            def on_presets(icon=None, item=None):
                try:
                    toggle_presets_automation()
                    if self.icon:
                        self.icon.update_menu()
                except Exception as e:
                    logging.debug(f"Tray presets callback error: {e}")

            def on_auto_ban(icon=None, item=None):
                try:
                    toggle_auto_ban()
                    if self.icon:
                        self.icon.update_menu()
                except Exception as e:
                    logging.debug(f"Tray auto-ban callback error: {e}")

            def on_quit(icon=None, item=None):
                try:
                    quit_callback()
                except Exception as e:
                    logging.debug(f"Tray quit callback error: {e}")

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
                try:
                    self.icon.run()
                except Exception as e:
                    self.available = False
                    logging.debug(f"System tray error: {e}")
                    on_failure()

            executor.submit(run_tray)
        except Exception as e:
            self.available = False
            logging.warning(f"Unable to create system tray: {e}")
        return self.available

    def shutdown(self) -> None:
        try:
            if self.icon:
                self.icon.stop()
        except Exception as e:
            logging.debug(f"Error stopping tray icon: {e}")
