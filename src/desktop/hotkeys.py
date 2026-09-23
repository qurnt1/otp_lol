"""Reliable global shortcuts for the Windows desktop shell."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from threading import Event, Thread
from typing import Callable

import keyboard

from ..domain.hotkeys import normalize_hotkey, validate_hotkey_pair


_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_MOD_NOREPEAT = 0x4000

_MODIFIER_FLAGS = {
    "alt": _MOD_ALT,
    "ctrl": _MOD_CONTROL,
    "control": _MOD_CONTROL,
    "shift": _MOD_SHIFT,
    "win": _MOD_WIN,
    "windows": _MOD_WIN,
    "meta": _MOD_WIN,
}

_SPECIAL_KEYS = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
}


def parse_windows_hotkey(hotkey: str) -> tuple[int, int]:
    """Convert the settings syntax (for example ``alt+c``) to Win32 flags."""
    parts = normalize_hotkey(hotkey).split("+")

    modifiers = 0
    for part in parts[:-1]:
        flag = _MODIFIER_FLAGS.get(part)
        if flag is None:
            raise ValueError(f"Unsupported hotkey modifier: {part}")
        modifiers |= flag

    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        virtual_key = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        virtual_key = 0x70 + int(key[1:]) - 1
    else:
        virtual_key = _SPECIAL_KEYS.get(key)
    if virtual_key is None:
        raise ValueError(f"Unsupported hotkey key: {key}")
    return modifiers | _MOD_NOREPEAT, virtual_key


class _RegisterHotKeyBackend:
    """Own a Win32 message loop so global shortcuts work independently of WebView2."""

    def __init__(self) -> None:
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._specs: dict[int, tuple[int, int]] = {}
        self._labels: dict[int, str] = {}
        self._stop_event = Event()
        self._ready_event = Event()
        self._thread: Thread | None = None
        self._thread_id: int | None = None
        self._error: BaseException | None = None
        self._registered_ids: set[int] = set()

    def setup(self, entries: list[tuple[str, Callable[[], None]]]) -> bool:
        self.shutdown()
        self._callbacks = {index + 1: callback for index, (_, callback) in enumerate(entries)}
        self._labels = {index + 1: normalize_hotkey(hotkey) for index, (hotkey, _) in enumerate(entries)}
        self._specs = {hotkey_id: parse_windows_hotkey(label) for hotkey_id, label in self._labels.items()}
        self._stop_event.clear()
        self._ready_event.clear()
        self._error = None
        self._thread = Thread(target=self._run, daemon=True, name="otp-lol-hotkeys")
        self._thread.start()
        if not self._ready_event.wait(timeout=2):
            self.shutdown()
            return False
        if self._error is not None:
            error = self._error
            self.shutdown()
            logging.debug("Unable to configure Windows hotkeys: %s", error)
            return False
        return bool(self._registered_ids)

    @property
    def registered_indices(self) -> set[int]:
        """Return callback indices that were accepted by RegisterHotKey."""
        return {hotkey_id - 1 for hotkey_id in self._registered_ids}

    def _run(self) -> None:
        user32 = None
        registered_ids: list[int] = []
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            message = wintypes.MSG()
            self._thread_id = int(kernel32.GetCurrentThreadId())
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            for hotkey_id, (modifiers, virtual_key) in self._specs.items():
                if not user32.RegisterHotKey(None, hotkey_id, modifiers, virtual_key):
                    get_last_error = getattr(kernel32, "GetLastError", lambda: 0)
                    error_code = int(get_last_error())
                    logging.info(
                        "Global hotkey %s unavailable through RegisterHotKey (Win32 error %s).",
                        self._labels.get(hotkey_id, f"id {hotkey_id}"),
                        error_code,
                    )
                    continue
                registered_ids.append(hotkey_id)
            self._registered_ids = set(registered_ids)
            self._ready_event.set()
            if not registered_ids:
                self._error = OSError("No Windows hotkey could be registered")
                return
            while not self._stop_event.is_set():
                result = int(user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                if result <= 0:
                    break
                if message.message == _WM_HOTKEY:
                    callback = self._callbacks.get(int(message.wParam))
                    if callback is not None:
                        try:
                            callback()
                        except Exception:
                            logging.exception("Global hotkey callback failed")
        except BaseException as error:
            self._error = error
            self._ready_event.set()
        finally:
            if user32 is not None:
                for hotkey_id in registered_ids:
                    user32.UnregisterHotKey(None, hotkey_id)
            self._registered_ids = set()
            self._thread_id = None

    def shutdown(self) -> None:
        self._stop_event.set()
        thread_id = self._thread_id
        if thread_id is not None and sys.platform == "win32":
            try:
                ctypes.windll.user32.PostThreadMessageW(thread_id, _WM_QUIT, 0, 0)
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None
        self._callbacks = {}
        self._specs = {}
        self._labels = {}
        self._registered_ids = set()


class HotkeyManager:
    """Manage global keyboard hotkeys and their cleanup lifecycle."""

    def __init__(self) -> None:
        self.available = False
        self.handles: list[object] = []
        self._register_backend: _RegisterHotKeyBackend | None = None
        self._backend_by_index: dict[int, str] = {}

    def setup(self, toggle_window, open_hotkey_site, toggle_hotkey: str, stats_hotkey: str) -> bool:
        """Register the configured shortcuts and roll back partial registrations."""
        self.shutdown()
        try:
            normalized_toggle, normalized_stats = validate_hotkey_pair(toggle_hotkey, stats_hotkey)
        except ValueError as error:
            logging.error("Invalid global hotkey configuration: %s", error)
            return False
        callbacks = [(normalized_toggle, toggle_window), (normalized_stats, open_hotkey_site)]

        registered_handles: list[object] = []
        fallback_callbacks: list[tuple[int, tuple[str, Callable[[], None]]]] = []
        for index, entry in enumerate(callbacks):
            hotkey, callback = entry
            try:
                registered_handles.append(keyboard.add_hotkey(hotkey, callback, suppress=False))
                self._backend_by_index[index] = "keyboard_hook"
            except Exception as error:
                logging.info("Keyboard hook unavailable for %s: %s", hotkey, error)
                fallback_callbacks.append((index, entry))

        if fallback_callbacks and sys.platform == "win32":
            try:
                backend = _RegisterHotKeyBackend()
                if backend.setup([entry for _, entry in fallback_callbacks]):
                    self._register_backend = backend
                    registered_indices = backend.registered_indices
                    for local_index, (index, (hotkey, _callback)) in enumerate(fallback_callbacks):
                        if local_index in registered_indices:
                            self._backend_by_index[index] = "register_hotkey"
                        else:
                            logging.warning("Global hotkey unavailable: %s", hotkey)
            except (OSError, ValueError) as error:
                logging.warning("RegisterHotKey backend unavailable: %s", error)

        self.handles = registered_handles
        self.available = bool(self.handles or self._register_backend)
        return self.available

    def status(self, toggle_hotkey: str, stats_hotkey: str) -> dict[str, dict[str, object]]:
        """Return the active backend for each configured shortcut."""
        def label(value: str) -> str:
            try:
                return normalize_hotkey(value)
            except (TypeError, ValueError):
                return str(value or "")

        labels = (label(toggle_hotkey), label(stats_hotkey))
        names = ("window", "site")
        return {
            name: {
                "hotkey": label,
                "backend": self._backend_by_index.get(index, "unavailable"),
                "active": index in self._backend_by_index,
            }
            for index, (name, label) in enumerate(zip(names, labels))
        }

    def shutdown(self) -> None:
        if self._register_backend is not None:
            self._register_backend.shutdown()
            self._register_backend = None
        for handle in self.handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception as error:
                logging.debug("Error removing hotkey: %s", error)
        self.handles = []
        self._backend_by_index = {}
        self.available = False


_WindowsHotkeyBackend = _RegisterHotKeyBackend

__all__ = ["HotkeyManager", "normalize_hotkey", "parse_windows_hotkey", "validate_hotkey_pair"]
