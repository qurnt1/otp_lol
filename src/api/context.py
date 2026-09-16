"""Application-wide state shared by API routes and the desktop shell."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, Dict, Mapping

from ..config import PICK_SLOT_ORDER, load_parameters, normalize_parameters, save_parameters
from ..core.datadragon import DataDragon
from ..domain.events import EventBroker
from ..domain.hotkeys import validate_hotkey_pair
from ..lcu.runtime import LcuRuntime


@dataclass
class ApplicationContext:
    """Own persistent settings, metadata, events and the LCU runtime."""

    params: Dict[str, Any]
    data_dragon: DataDragon = field(default_factory=DataDragon)
    broker: EventBroker = field(default_factory=EventBroker)
    _params_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _data_dragon_lock: asyncio.Lock | None = field(default=None, init=False, repr=False)
    _data_dragon_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)
    _connected: bool = field(default=False, init=False, repr=False)
    _window: Any = field(default=None, init=False, repr=False)
    _shutdown_callback: Callable[[], None] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.params = normalize_parameters(self.params)
        self.runtime = LcuRuntime(
            data_dragon=self.data_dragon,
            get_params=self.get_params,
            update_param=self.update_param,
            broker=self.broker,
            event_hook=self._handle_runtime_event,
        )

    def bind_window(self, window: Any, *, shutdown_callback: Callable[[], None] | None = None) -> None:
        """Bind native lifecycle effects after the local API and WebView exist."""
        self._window = window
        self._shutdown_callback = shutdown_callback

    def _handle_runtime_event(self, event_type: str, _data: Any = None) -> None:
        if event_type == "connected":
            if self._connected:
                return
            self._connected = True
            if self.get_params().get("auto_hide_on_connect", True) and self._window is not None:
                self._window.hide()
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
            candidate = normalize_parameters(candidate)
            return self._commit_candidate_locked(candidate)

    async def ensure_data_dragon(self) -> None:
        if self.data_dragon.loaded:
            return
        if self._data_dragon_task is not None:
            await self._data_dragon_task
            return
        if self._data_dragon_lock is None:
            self._data_dragon_lock = asyncio.Lock()
        async with self._data_dragon_lock:
            if not self.data_dragon.loaded:
                await self.runtime.load_data_dragon()

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        await asyncio.to_thread(self.data_dragon.load_cached)
        self.runtime.start()
        self._data_dragon_task = asyncio.create_task(
            asyncio.to_thread(self.data_dragon.refresh),
            name="otp-lol-datadragon-refresh",
        )

    async def stop(self) -> None:
        if self._data_dragon_task and not self._data_dragon_task.done():
            self._data_dragon_task.cancel()
            await asyncio.gather(self._data_dragon_task, return_exceptions=True)
        if self._started:
            await asyncio.to_thread(self.runtime.stop)
            self._started = False
        self.save()
