"""Coordinate the PySide6 windows and desktop integrations."""

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPoint, QProcess, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from src.application import ApplicationController
from src.config import PICK_SLOT_ORDER
from src.core.events import (
    Connected,
    Disconnected,
    ReadyCheckAccepted,
    RuntimeEvent,
    SummonerUpdated,
    UpdateAvailable,
)
from src.services.profile_config import build_effective_profile_config
from src.services.riot_client import find_riot_client
from src.services.skin_modes import (
    build_main_skin_overrides,
    get_effective_skin_mode_for_slot,
    get_skin_cycle_modes,
)
from src.services.urls import build_hotkey_site_url, build_stats_site_url, is_valid_riot_id

from .event_bridge import CoreEventBridge
from .history_dialog import HistoryDialog
from .integrations import AudioManager, GlobalHotkeyManager, TrayController
from .settings_dialog import SettingsDialog
from .tasks import TaskRunner
from .theme import stylesheet_for
from .update_dialog import UpdateDialog

if TYPE_CHECKING:
    from .main_window import MainWindow


class DesktopApplication(QObject):
    """Own presentation lifecycle while the application controller owns runtime services."""

    def __init__(
        self,
        *,
        qt_app: QApplication,
        controller: ApplicationController,
        event_bridge: CoreEventBridge,
        main_window: "MainWindow",
        task_runner: TaskRunner,
    ) -> None:
        super().__init__()
        self.qt_app = qt_app
        self.controller = controller
        self.event_bridge = event_bridge
        self.main_window = main_window
        self.task_runner = task_runner
        self.settings_dialog: SettingsDialog | None = None
        self.history_dialog: HistoryDialog | None = None
        self.update_dialog: UpdateDialog | None = None
        self._latest_update_event: UpdateAvailable | None = None
        self._connected = False
        self._shutdown_started = False

        self.disconnect_timer = QTimer(self)
        self.disconnect_timer.setSingleShot(True)
        self.disconnect_timer.setInterval(8000)
        self.disconnect_timer.timeout.connect(self.quit)
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.setInterval(3000)
        self.auto_hide_timer.timeout.connect(self._auto_hide_if_allowed)

        self.hotkeys = GlobalHotkeyManager(self)
        self.tray = TrayController(self)
        self.audio = AudioManager(self)
        self._connect_signals()
        self._apply_initial_state()

    def _connect_signals(self) -> None:
        self.event_bridge.event_received.connect(self.main_window.handle_runtime_event)
        self.event_bridge.event_received.connect(self._handle_runtime_event)
        self.main_window.setting_changed.connect(self._set_setting)
        self.main_window.presets_changed.connect(self._set_presets_enabled)
        self.main_window.skin_cycle_requested.connect(self._cycle_skin_mode)
        self.main_window.settings_requested.connect(self.open_settings)
        self.main_window.history_requested.connect(self.open_history)
        self.main_window.stats_requested.connect(self.open_stats_site)
        self.main_window.changelog_requested.connect(self.open_changelog)
        self.main_window.riot_client_requested.connect(self.open_riot_client)
        self.main_window.close_requested.connect(self._handle_main_close)
        self.main_window.quit_requested.connect(self.quit)
        self.hotkeys.toggle_requested.connect(self.toggle_main_window)
        self.hotkeys.website_requested.connect(self.open_hotkey_site)
        self.tray.toggle_requested.connect(self.toggle_main_window)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.presets_requested.connect(self._set_presets_enabled)
        self.tray.auto_ban_requested.connect(lambda enabled: self._set_setting("auto_ban_enabled", enabled))
        self.tray.quit_requested.connect(self.quit)

    def _apply_initial_state(self) -> None:
        settings = self.controller.settings_snapshot()
        self.qt_app.setStyleSheet(stylesheet_for(str(settings.get("theme") or "darkly")))
        self._restore_window_position(settings)
        self.tray.setup(
            presets_enabled=bool(settings.get("presets_enabled", False)),
            auto_ban_enabled=bool(settings.get("auto_ban_enabled", False)),
        )
        self.reload_hotkeys()

    def show(self) -> None:
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    @Slot(str, object)
    def _set_setting(self, key: str, value: Any) -> None:
        self.controller.update_setting(key, value)
        self._settings_changed()

    @Slot(bool)
    def _set_presets_enabled(self, enabled: bool) -> None:
        self.controller.set_presets_enabled(enabled)
        self._settings_changed()

    def _settings_changed(self) -> None:
        settings = self.controller.settings_snapshot()
        if not self.controller.save_settings():
            self.main_window.enqueue_toast("Settings could not be saved.", 3200)
        self.main_window.refresh_settings(settings)
        self.tray.sync(
            presets_enabled=bool(settings.get("presets_enabled", False)),
            auto_ban_enabled=bool(settings.get("auto_ban_enabled", False)),
        )

    def _replace_settings(self, settings: Mapping[str, Any]) -> None:
        self.controller.replace_settings(dict(settings))
        self._settings_changed()
        self.reload_hotkeys()

    def _cycle_skin_mode(self, slot_key: str) -> None:
        if slot_key not in PICK_SLOT_ORDER:
            return
        settings = self.controller.settings_snapshot()
        effective = build_effective_profile_config(settings)
        slot_data = effective.get("pick_slots", {}).get(slot_key, {})
        modes = get_skin_cycle_modes(slot_data=slot_data)
        if len(modes) <= 1:
            self.main_window.enqueue_toast("Configure a fixed or random skin in settings first.", 2600)
            return
        overrides = build_main_skin_overrides(settings)
        current = get_effective_skin_mode_for_slot(slot_key, effective, overrides)
        next_mode = modes[(modes.index(current) + 1) % len(modes)] if current in modes else modes[0]
        overrides[slot_key] = next_mode
        self.controller.update_setting("main_skin_mode_overrides", overrides)
        self._settings_changed()
        self.main_window.enqueue_toast(f"{slot_key.replace('_', ' ').title()} skin mode: {next_mode}", 1800)

    def open_settings(self) -> None:
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(
            settings=self.controller.settings_snapshot(),
            data_dragon=self.controller.data_dragon,
            websocket_manager=self.controller.websocket_manager,
            task_runner=self.task_runner,
            parent=self.main_window,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setting_changed.connect(self._set_setting)
        dialog.presets_changed.connect(self._set_presets_enabled)
        dialog.settings_imported.connect(self._replace_settings)
        dialog.theme_changed.connect(self.apply_theme)
        dialog.history_requested.connect(self.open_history)
        dialog.force_summoner_refresh.connect(self.controller.websocket_manager.force_refresh_summoner)
        dialog.hotkey_capture_started.connect(self.hotkeys.shutdown)
        dialog.hotkey_capture_finished.connect(self.reload_hotkeys)
        dialog.destroyed.connect(lambda: setattr(self, "settings_dialog", None))
        self.settings_dialog = dialog
        dialog.show()

    def open_history(self) -> None:
        if self.history_dialog and self.history_dialog.isVisible():
            self.history_dialog.raise_()
            self.history_dialog.activateWindow()
            return
        dialog = HistoryDialog(self.main_window)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.destroyed.connect(lambda: setattr(self, "history_dialog", None))
        self.history_dialog = dialog
        dialog.show()

    def apply_theme(self, theme_name: str) -> None:
        stylesheet = stylesheet_for(theme_name)
        self.qt_app.setStyleSheet(stylesheet)
        self.main_window.setStyleSheet(stylesheet)

    def reload_hotkeys(self) -> None:
        settings = self.controller.settings_snapshot()
        self.hotkeys.setup(
            str(settings.get("hotkey_toggle_window") or "alt+c"),
            str(settings.get("hotkey_open_site") or "alt+p"),
        )

    def toggle_main_window(self) -> None:
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.main_window.hide()
        else:
            self.show()

    def _handle_main_close(self) -> None:
        self._save_window_position()
        if self.tray.available:
            self.main_window.hide()
        else:
            self.quit()

    def _account_for_websites(self) -> tuple[str, str]:
        settings = self.controller.settings_snapshot()
        if bool(settings.get("summoner_name_auto_detect", True)):
            riot_id = self.controller.websocket_manager.get_riot_id() or str(
                settings.get("auto_detected_riot_id") or ""
            )
            region = self.controller.websocket_manager.get_platform_for_websites() or str(
                settings.get("auto_detected_region") or "euw"
            )
        else:
            riot_id = str(settings.get("manual_summoner_name") or "")
            region = str(settings.get("manual_region") or "euw")
        return riot_id.strip(), region.strip().lower()

    def open_stats_site(self) -> None:
        riot_id, region = self._account_for_websites()
        if not is_valid_riot_id(riot_id):
            self.main_window.enqueue_toast("A valid GameName#Tag is required for stats.", 2600)
            return
        settings = self.controller.settings_snapshot()
        QDesktopServices.openUrl(
            QUrl(build_stats_site_url(str(settings.get("preferred_stats_site") or "opgg"), region, riot_id))
        )

    def open_riot_client(self) -> None:
        executable = find_riot_client()
        if executable is None:
            self.main_window.enqueue_toast("Riot Client introuvable sur ce PC.", 3200)
            return
        launch_result = QProcess.startDetached(
            str(executable),
            ["--launch-product=league_of_legends", "--launch-patchline=live"],
        )
        started = launch_result[0] if isinstance(launch_result, tuple) else launch_result
        if not started:
            self.main_window.enqueue_toast("Impossible de lancer Riot Client.", 3200)

    def open_hotkey_site(self) -> None:
        riot_id, region = self._account_for_websites()
        if not is_valid_riot_id(riot_id):
            self.main_window.enqueue_toast("A valid GameName#Tag is required for the website shortcut.", 2600)
            return
        settings = self.controller.settings_snapshot()
        QDesktopServices.openUrl(
            QUrl(build_hotkey_site_url(str(settings.get("preferred_hotkey_site") or "porofessor"), region, riot_id))
        )

    @Slot(object)
    def _handle_runtime_event(self, event: RuntimeEvent) -> None:
        if isinstance(event, Connected):
            self._connected = True
            self.disconnect_timer.stop()
            if bool(self.controller.settings_snapshot().get("auto_hide_on_connect", True)):
                self.auto_hide_timer.start()
        elif isinstance(event, Disconnected):
            self._connected = False
            self.auto_hide_timer.stop()
            if event.transient:
                self.disconnect_timer.stop()
                return
            settings = self.controller.settings_snapshot()
            if bool(settings.get("close_app_on_lol_exit", True)):
                self.disconnect_timer.start()
            else:
                self.show()
        elif isinstance(event, ReadyCheckAccepted):
            self.audio.play_accept_sound()
        elif isinstance(event, SummonerUpdated):
            self.main_window.refresh_settings(self.controller.settings_snapshot())
        elif isinstance(event, UpdateAvailable):
            self._latest_update_event = event
            self._show_update(event)

    def open_changelog(self) -> None:
        if self._latest_update_event is None:
            self.main_window.statusBar().showMessage("No remote changelog is available yet.")
            return
        self._show_update(self._latest_update_event)

    def _auto_hide_if_allowed(self) -> None:
        if self._connected and not (self.settings_dialog and self.settings_dialog.isVisible()):
            self.main_window.hide()

    def _show_update(self, event: UpdateAvailable) -> None:
        if self.update_dialog and self.update_dialog.isVisible():
            return
        dialog = UpdateDialog(event.version, event.highlights, self.main_window)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.ignored.connect(lambda version: self._set_setting("ignored_update_version", version))
        dialog.destroyed.connect(lambda: setattr(self, "update_dialog", None))
        self.update_dialog = dialog
        dialog.show()

    def _restore_window_position(self, settings: Mapping[str, Any]) -> None:
        x = int(settings.get("window_x") or 0)
        y = int(settings.get("window_y") or 0)
        point = QPoint(x, y)
        screen = QApplication.screenAt(point)
        if screen is not None:
            self.main_window.move(point)
            return
        primary = QApplication.primaryScreen()
        if primary:
            available = primary.availableGeometry()
            self.main_window.move(available.center() - self.main_window.rect().center())

    def _save_window_position(self) -> None:
        position = self.main_window.pos()
        self.controller.settings_store.update_many({"window_x": position.x(), "window_y": position.y()})
        self.controller.save_settings()

    def quit(self) -> None:
        if self._shutdown_started:
            return
        self._shutdown_started = True
        logging.info("Closing PySide6 desktop application")
        self.auto_hide_timer.stop()
        self.disconnect_timer.stop()
        self._save_window_position()
        self.hotkeys.shutdown()
        self.tray.shutdown()
        self.audio.shutdown()
        self.task_runner.shutdown()
        self.controller.stop()
        for dialog in (self.settings_dialog, self.history_dialog, self.update_dialog):
            if dialog:
                dialog.close()
        self.main_window.allow_close()
        self.main_window.close()
        self.qt_app.quit()
