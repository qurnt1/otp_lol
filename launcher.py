"""Bootstrap the PySide6 desktop application and its runtime controller."""

import logging
import sys
from threading import Lock

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from src.application import ApplicationController, SettingsStore
from src.config import APP_IMAGE_FILES, APP_NAME, CURRENT_VERSION, get_cache_dirs, resource_path
from src.core.datadragon import DataDragon
from src.services.single_instance import check_single_instance, remove_lockfile


class OtpLolApplication:
    """Create Qt first, then wire the presentation and background runtime once."""

    def __init__(self) -> None:
        self._cleanup_lock = Lock()
        self._cleanup_done = False
        if not check_single_instance():
            logging.info("Another instance is already running. Closing.")
            raise SystemExit(0)

        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationVersion(CURRENT_VERSION)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setWindowIcon(QIcon(resource_path(APP_IMAGE_FILES["icon_ico"])))

        from src.desktop.application import DesktopApplication
        from src.desktop.event_bridge import CoreEventBridge
        from src.desktop.main_window import MainWindow
        from src.desktop.tasks import TaskRunner

        self.settings_store = SettingsStore()
        get_cache_dirs()
        self.data_dragon = DataDragon()
        self.event_bridge = CoreEventBridge()
        self.task_runner = TaskRunner()
        self.main_window = MainWindow(
            self.settings_store.snapshot(),
            data_dragon=self.data_dragon,
            task_runner=self.task_runner,
        )
        self.controller = ApplicationController(
            settings_store=self.settings_store,
            data_dragon=self.data_dragon,
            event_callback=self.event_bridge.publish,
        )
        self.desktop = DesktopApplication(
            qt_app=self.qt_app,
            controller=self.controller,
            event_bridge=self.event_bridge,
            main_window=self.main_window,
            task_runner=self.task_runner,
        )
        self.qt_app.aboutToQuit.connect(self.cleanup)

    def _save_params(self) -> None:
        if self.controller.save_settings():
            logging.info("Settings saved successfully.")
        else:
            logging.error("Failed to save settings.")

    def run(self) -> int:
        logging.info("OTP LOL v%s started with PySide6", CURRENT_VERSION)
        self.desktop.show()
        self.controller.start()
        return self.qt_app.exec()

    def quit_app(self) -> None:
        self.desktop.quit()

    def cleanup(self) -> None:
        with self._cleanup_lock:
            if self._cleanup_done:
                return
            self._cleanup_done = True
        if hasattr(self, "controller"):
            self.controller.stop()
        remove_lockfile()
        logging.info("Cleanup complete.")


def main() -> int:
    application: OtpLolApplication | None = None
    try:
        application = OtpLolApplication()
        return application.run()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected.")
        return 130
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception:
        logging.exception("Fatal error")
        return 1
    finally:
        if application is not None:
            application.cleanup()
        else:
            remove_lockfile()


if __name__ == "__main__":
    raise SystemExit(main())
