"""Thread-safe in-memory access to the persisted application settings."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from threading import RLock
from typing import Any

from src.config import load_parameters, save_parameters

type Settings = dict[str, Any]
type SettingsLoader = Callable[[], Settings]
type SettingsSaver = Callable[[Settings], bool]


class SettingsStore:
    """Own one synchronized settings snapshot and its persistence callbacks."""

    def __init__(
        self,
        *,
        loader: SettingsLoader = load_parameters,
        saver: SettingsSaver = save_parameters,
    ) -> None:
        self._lock = RLock()
        self._params = deepcopy(loader())
        self._saver = saver

    def snapshot(self) -> Settings:
        """Return a deep copy that callers may mutate independently."""
        with self._lock:
            return deepcopy(self._params)

    def update(self, key: str, value: Any) -> None:
        """Replace one setting while isolating mutable caller-owned values."""
        with self._lock:
            self._params[key] = deepcopy(value)

    def update_many(self, values: Mapping[str, Any]) -> None:
        """Replace related settings atomically from caller-owned values."""
        with self._lock:
            for key, value in values.items():
                self._params[key] = deepcopy(value)

    def replace(self, values: Mapping[str, Any]) -> None:
        """Atomically replace the complete snapshot after a validated import."""
        with self._lock:
            self._params = deepcopy(dict(values))

    def save(self) -> bool:
        """Persist a stable snapshot without holding the in-memory state lock."""
        return self._saver(self.snapshot())
