"""Qt-native tray and audio integrations plus isolated global hotkeys."""

import logging

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.config import APP_IMAGE_FILES, APP_NAME, resource_path


class GlobalHotkeyManager(QObject):
    toggle_requested = Signal()
    website_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handles: list[object] = []
        self.available = False

    def setup(self, toggle_hotkey: str, website_hotkey: str) -> bool:
        self.shutdown()
        registered: list[object] = []
        try:
            import keyboard

            registered.append(keyboard.add_hotkey(toggle_hotkey, self.toggle_requested.emit))
            registered.append(keyboard.add_hotkey(website_hotkey, self.website_requested.emit))
            self._handles = registered
            self.available = True
        except Exception as exc:
            logging.debug("Unable to configure global hotkeys: %s", exc)
            self._remove_handles(registered)
        return self.available

    def shutdown(self) -> None:
        self._remove_handles(self._handles)
        self._handles = []
        self.available = False

    @staticmethod
    def _remove_handles(handles: list[object]) -> None:
        if not handles:
            return
        try:
            import keyboard
        except Exception:
            return
        for handle in handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception as exc:
                logging.debug("Unable to remove global hotkey: %s", exc)


class TrayController(QObject):
    toggle_requested = Signal()
    settings_requested = Signal()
    presets_requested = Signal(bool)
    auto_ban_requested = Signal(bool)
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.icon: QSystemTrayIcon | None = None
        self.presets_action: QAction | None = None
        self.auto_ban_action: QAction | None = None

    @property
    def available(self) -> bool:
        return bool(self.icon and self.icon.isVisible())

    def setup(self, *, presets_enabled: bool, auto_ban_enabled: bool) -> bool:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        icon = QIcon(resource_path(APP_IMAGE_FILES["icon_ico"]))
        if icon.isNull():
            icon = QApplication.windowIcon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(APP_NAME)
        menu = QMenu()
        show_action = menu.addAction("Show / hide")
        show_action.triggered.connect(self.toggle_requested.emit)
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addSeparator()
        self.presets_action = menu.addAction("Enable preset automation")
        self.presets_action.setCheckable(True)
        self.presets_action.setChecked(presets_enabled)
        self.presets_action.toggled.connect(self.presets_requested.emit)
        self.auto_ban_action = menu.addAction("Auto ban")
        self.auto_ban_action.setCheckable(True)
        self.auto_ban_action.setChecked(auto_ban_enabled)
        self.auto_ban_action.toggled.connect(self.auto_ban_requested.emit)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)
        tray.setContextMenu(menu)
        tray.activated.connect(self._activated)
        tray.show()
        self.icon = tray
        return True

    def sync(self, *, presets_enabled: bool, auto_ban_enabled: bool) -> None:
        for action, value in (
            (self.presets_action, presets_enabled),
            (self.auto_ban_action, auto_ban_enabled),
        ):
            if action and action.isChecked() != value:
                action.blockSignals(True)
                action.setChecked(value)
                action.blockSignals(False)

    def shutdown(self) -> None:
        if self.icon:
            self.icon.hide()
            self.icon.deleteLater()
        self.icon = None

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_requested.emit()


class AudioManager(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.effect = QSoundEffect(self)
        self.effect.setSource(QUrl.fromLocalFile(resource_path("config/son.wav")))
        self.effect.setVolume(0.7)

    def play_accept_sound(self) -> None:
        try:
            self.effect.play()
        except Exception as exc:
            logging.debug("Unable to play ready-check sound: %s", exc)

    def shutdown(self) -> None:
        self.effect.stop()
