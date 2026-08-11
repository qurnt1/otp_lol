"""Application orchestration shared by the PySide6 entry point and tests."""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from src.core.datadragon import DataDragon
from src.core.events import RuntimeEvent, ToastRequested, UpdateAvailable
from src.core.websocket import WebSocketManager
from src.services.updates import check_for_updates

from .settings_store import SettingsStore

type EventCallback = Callable[[RuntimeEvent], None]
type UpdateChecker = Callable[[], dict[str, str] | None]


class ApplicationController:
    """Own runtime services without depending on a specific desktop toolkit."""

    def __init__(
        self,
        *,
        settings_store: SettingsStore,
        data_dragon: DataDragon,
        event_callback: EventCallback,
        update_checker: UpdateChecker = check_for_updates,
    ) -> None:
        self.settings_store = settings_store
        self.data_dragon = data_dragon
        self._event_callback = event_callback
        self._update_checker = update_checker
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="otp-lol")
        self._lifecycle_lock = Lock()
        self._started = False
        self._stopped = False
        self.websocket_manager = WebSocketManager(
            event_sink=self._emit,
            dd=self.data_dragon,
            get_params=self.settings_store.snapshot,
            update_param=self.settings_store.update,
        )

    def start(self) -> None:
        """Start metadata, update, and LCU work once all UI receivers are ready."""
        with self._lifecycle_lock:
            if self._started or self._stopped:
                return
            self._started = True

        self._executor.submit(self._initialize_runtime)
        self._executor.submit(self._check_updates)

    def stop(self) -> None:
        """Stop runtime services once and prevent late events from reaching a closed UI."""
        with self._lifecycle_lock:
            if self._stopped:
                return
            self._stopped = True

        self.websocket_manager.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def save_settings(self) -> bool:
        return self.settings_store.save()

    def settings_snapshot(self) -> dict[str, object]:
        return self.settings_store.snapshot()

    def update_setting(self, key: str, value: object) -> None:
        self.settings_store.update(key, value)

    def replace_settings(self, settings: dict[str, object]) -> None:
        self.settings_store.replace(settings)

    def set_presets_enabled(self, enabled: bool) -> None:
        self.settings_store.update_many(
            {
                "presets_enabled": enabled,
                "auto_pick_enabled": enabled,
                "auto_summoners_enabled": enabled,
            }
        )

    def _emit(self, event: RuntimeEvent) -> None:
        with self._lifecycle_lock:
            if self._stopped:
                return
        self._event_callback(event)

    def _initialize_runtime(self) -> None:
        """Load champion metadata before allowing champion-select automation to start."""
        self._load_datadragon()
        with self._lifecycle_lock:
            if self._stopped:
                return
        self.websocket_manager.start()

    def _load_datadragon(self) -> None:
        try:
            logging.info("Loading DataDragon in the background...")
            self.data_dragon.load()
            champion_count = len(self.data_dragon.all_names)
            if champion_count:
                self._emit(ToastRequested(f"Champions loaded ({champion_count})", 1500))
                logging.info("DataDragon loaded: %s champions", champion_count)
            else:
                logging.warning("DataDragon loaded without champions")
        except Exception:
            logging.exception("Error while loading DataDragon")
            self._emit(ToastRequested("Champion loading error", 3000))

    def _check_updates(self) -> None:
        try:
            update_info = self._update_checker()
            if not update_info:
                logging.info("Application is up to date.")
                return

            version = str(update_info.get("version") or "").strip()
            ignored_version = str(
                self.settings_store.snapshot().get("ignored_update_version") or ""
            ).strip()
            if ignored_version and ignored_version == version:
                logging.info("Update %s ignored by user preference.", version)
                return

            logging.info("New version available: %s", version)
            self._emit(
                UpdateAvailable(
                    version=version,
                    highlights=str(update_info.get("highlights") or "").strip(),
                )
            )
        except Exception:
            logging.exception("Error while checking for updates")
