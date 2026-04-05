"""System tray helpers for the main window."""

import logging

import pystray
from PIL import Image

from ..config import APP_IMAGE_FILES, resource_path


class TrayController:
    """Wrap systray creation and cleanup."""

    def __init__(self):
        self.icon = None
        self.available = False

    def setup(self, executor, toggle_window, quit_callback, on_failure) -> bool:
        try:
            image = Image.open(resource_path(APP_IMAGE_FILES["icon_webp"])).resize((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("Afficher/Masquer", toggle_window),
                pystray.MenuItem("Quitter", quit_callback),
            )
            self.icon = pystray.Icon("MAIN LOL", image, "MAIN LOL", menu)
            self.available = True

            def run_tray():
                try:
                    self.icon.run()
                except Exception as e:
                    self.available = False
                    logging.debug(f"Erreur system tray: {e}")
                    on_failure()

            executor.submit(run_tray)
        except Exception as e:
            self.available = False
            logging.warning(f"Impossible de creer le system tray: {e}")
        return self.available

    def shutdown(self) -> None:
        try:
            if self.icon:
                self.icon.stop()
        except Exception as e:
            logging.debug(f"Erreur arret tray icon: {e}")
