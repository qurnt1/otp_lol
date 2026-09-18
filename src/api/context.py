"""Application-wide state shared by API routes and the desktop shell."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, Dict, Mapping

from ..config import (
    ACCOUNT_CACHE_DIR,
    LCU_CACHE_DIR,
    PICK_SLOT_ORDER,
    load_parameters,
    normalize_parameters,
    save_parameters,
)
from ..core.datadragon import DataDragon
from ..domain.events import EventBroker
from ..domain.hotkeys import validate_hotkey_pair
from ..lcu.account_stats import AccountStatsService
from ..lcu.assets import LcuAssetService
from ..lcu.diagnostics import DiagnosticsService
from ..lcu.runtime import LcuRuntime
from ..lcu.static_data import LcuStaticDataService
from ..services.urls import is_valid_detected_account


@dataclass
class ApplicationContext:
    """Own persistent settings, metadata, events and the LCU runtime."""

    params: Dict[str, Any]
    data_dragon: DataDragon = field(default_factory=DataDragon)
    broker: EventBroker = field(default_factory=EventBroker)
    _params_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _data_dragon_lock: asyncio.Lock | None = field(default=None, init=False, repr=False)
    _static_data_refresh_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _async_loop: asyncio.AbstractEventLoop | None = field(default=None, init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)
    _connected: bool = field(default=False, init=False, repr=False)
    _window: Any = field(default=None, init=False, repr=False)
    _shutdown_callback: Callable[[], None] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.params = normalize_parameters(self.params)
        self.diagnostics = DiagnosticsService(
            self._request_diagnostics,
            get_riot_id=self._get_diagnostic_riot_id,
        )
        self.runtime = LcuRuntime(
            data_dragon=self.data_dragon,
            get_params=self.get_params,
            update_param=self.update_param,
            persist_detected_account=self.persist_detected_account,
            broker=self.broker,
            event_hook=self._handle_runtime_event,
            request_observer=self.diagnostics.record_request,
            event_observer=self.diagnostics.record_event,
        )
        self.static_data = LcuStaticDataService(self.runtime.request_json, LCU_CACHE_DIR)
        self.asset_service = LcuAssetService(self.runtime.request_bytes, self.static_data)
        self.account_stats = AccountStatsService(
            self.runtime.request_json,
            connected=lambda: self.runtime.is_active,
            cache_path=ACCOUNT_CACHE_DIR,
            get_identity=self._get_account_identity,
        )

    async def _request_diagnostics(self, path: str) -> Any:
        return await self.runtime.request_json(path)

    def _get_diagnostic_riot_id(self) -> str | None:
        return self.runtime.manager.get_riot_id()

    def _get_account_identity(self) -> dict[str, Any]:
        state = self.runtime.manager.state
        return {
            "puuid": getattr(state, "puuid", None),
            "summoner_id": getattr(state, "summoner_id", None),
            "riot_id": self.runtime.manager.get_riot_id(),
            "region": self.runtime.manager.get_platform_for_websites(),
        }

    def bind_window(self, window: Any, *, shutdown_callback: Callable[[], None] | None = None) -> None:
        """Bind native lifecycle effects after the local API and WebView exist."""
        self._window = window
        self._shutdown_callback = shutdown_callback

    def _handle_runtime_event(self, event_type: str, _data: Any = None) -> None:
        self.diagnostics.record_event(f"otp-lol/{event_type}", "Update", _data)
        if event_type == "connected":
            if self._connected:
                return
            self._connected = True
            if self.get_params().get("auto_hide_on_connect", True) and self._window is not None:
                self._window.hide()
            if self._async_loop is not None and self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(self._start_static_data_refresh)
        elif event_type == "disconnected":
            was_connected = self._connected
            self._connected = False
            if was_connected and self.get_params().get("close_app_on_lol_exit", True):
                callback = self._shutdown_callback
                if callback is not None:
                    callback()

    @classmethod
    def from_system(cls) -> "ApplicationContext":
        return cls(params=load_parameters())

    def get_params(self) -> Dict[str, Any]:
        with self._params_lock:
            return copy.deepcopy(self.params)

    def update_param(self, key: str, value: Any) -> None:
        with self._params_lock:
            updated = copy.deepcopy(self.params)
            updated[key] = copy.deepcopy(value)
            self.params = normalize_parameters(updated)

    def update_parameters(self, values: Mapping[str, Any]) -> Dict[str, Any]:
        with self._params_lock:
            updated = copy.deepcopy(self.params)
            for key, value in values.items():
                updated[key] = copy.deepcopy(value)
            self.params = normalize_parameters(updated)
            return copy.deepcopy(self.params)

    def persist_detected_account(self, riot_id: str, region: str, platform: str) -> bool:
        """Persist one validated LCU identity without mixing partial account data."""
        normalized_riot_id = str(riot_id or "").strip()
        normalized_region = str(region or "").strip().lower()
        normalized_platform = str(platform or "").strip().lower()
        if (
            not is_valid_detected_account(normalized_riot_id, normalized_region, normalized_platform)
        ):
            return False

        values = {
            "auto_detected_riot_id": normalized_riot_id,
            "auto_detected_region": normalized_region,
            "auto_detected_platform": normalized_platform,
        }
        with self._params_lock:
            changed = any(self.params.get(key) != value for key, value in values.items())
            updated = self.persist_parameters(values) if changed else self.get_params()
        if updated is None:
            return False
        self.broker.publish("account_identity_updated", {"keys": list(values)})
        return True

    def save(self) -> bool:
        return save_parameters(self.get_params())

    def _commit_candidate_locked(self, candidate: Dict[str, Any]) -> Dict[str, Any] | None:
        """Persist a candidate while keeping memory unchanged when disk writing fails."""
        previous = self.params
        self.params = candidate
        persisted = False
        try:
            if self.save():
                persisted = True
                return copy.deepcopy(self.params)
            return None
        finally:
            if not persisted:
                self.params = previous

    def persist_parameters(self, values: Mapping[str, Any]) -> Dict[str, Any] | None:
        """Atomically merge, persist, and install a new settings snapshot."""
        with self._params_lock:
            candidate = copy.deepcopy(self.params)
            for key, value in values.items():
                candidate[key] = copy.deepcopy(value)
            validate_hotkey_pair(candidate["hotkey_toggle_window"], candidate["hotkey_open_site"])
            candidate = normalize_parameters(candidate)
            return self._commit_candidate_locked(candidate)

    def persist_preset_slot(
        self,
        slot_key: str,
        values: Mapping[str, Any],
        *,
        selected_champion: str | None = None,
    ) -> Dict[str, Any] | None:
        """Update one preset from the latest state and persist it under the same lock."""
        if slot_key not in PICK_SLOT_ORDER:
            raise ValueError(f"Unknown preset slot: {slot_key}")
        with self._params_lock:
            candidate = copy.deepcopy(self.params)
            pick_slots = candidate.setdefault("pick_slots", {})
            slot_data = pick_slots.setdefault(slot_key, {})
            slot_data.update(copy.deepcopy(dict(values)))
            if selected_champion is not None:
                slot_number = PICK_SLOT_ORDER.index(slot_key) + 1
                candidate[f"selected_pick_{slot_number}"] = selected_champion
            candidate["onboarding_completed"] = True
            candidate = normalize_parameters(candidate)
            return self._commit_candidate_locked(candidate)

    async def ensure_data_dragon(self) -> None:
        if self.data_dragon.loaded:
            return
        if self._data_dragon_lock is None:
            self._data_dragon_lock = asyncio.Lock()
        async with self._data_dragon_lock:
            if not self.data_dragon.loaded:
                await self.runtime.load_data_dragon()

    async def ensure_static_data(self) -> None:
        """Refresh missing static data from the connected client on demand."""
        status = self.static_data.status
        if (
            self.runtime.is_active
            and status["game_version"] is None
            and not status["cache_available"]
        ):
            refreshed = await self.static_data.refresh()
            self.diagnostics.record_event(
                "otp-lol/data/static-data",
                "refresh",
                {"refreshed": refreshed, "status": self.static_data.status},
            )

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._async_loop = asyncio.get_running_loop()
        await asyncio.to_thread(self.static_data.load_from_cache)
        await asyncio.to_thread(self.data_dragon.load_cached)
        self.runtime.start()

    def _start_static_data_refresh(self) -> None:
        task = self._static_data_refresh_task
        if task is not None and not task.done():
            return
        self._static_data_refresh_task = asyncio.create_task(
            self._refresh_static_data(),
            name="otp-lol-lcu-static-data-refresh",
        )

    async def _refresh_static_data(self) -> None:
        try:
            refreshed = await self.static_data.refresh()
        except Exception as error:  # noqa: BLE001 - preserve the live runtime if a catalogue refresh fails.
            self.diagnostics.record_error("static_data", error)
            return
        self.diagnostics.record_event(
            "otp-lol/data/static-data",
            "refresh",
            {"refreshed": refreshed, "status": self.static_data.status},
        )
        if refreshed:
            self.broker.publish("game_data_updated", self.static_data.status)

    async def stop(self) -> None:
        if self._static_data_refresh_task and not self._static_data_refresh_task.done():
            self._static_data_refresh_task.cancel()
            await asyncio.gather(self._static_data_refresh_task, return_exceptions=True)
        if self._started:
            await asyncio.to_thread(self.runtime.stop)
            self._started = False
        self._async_loop = None
        self.save()
