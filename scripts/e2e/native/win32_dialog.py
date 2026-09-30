"""Use Win32 to drive native windows and dialogs owned by the isolated test app."""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from ctypes import wintypes
from pathlib import Path

import psutil

user32 = ctypes.windll.user32
ENUM_WINDOWS = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [ENUM_WINDOWS, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, ENUM_WINDOWS, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.GetMenuItemRect.argtypes = [
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.UINT,
    ctypes.POINTER(wintypes.RECT),
]
user32.GetMenuItemRect.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
user32.keybd_event.restype = None
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class InputUnion(ctypes.Union):
    _fields_ = (
        ("mi", MouseInput),
        ("ki", KeyboardInput),
        ("hi", HardwareInput),
    )


class Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", InputUnion)]


class GuiThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
GUI_POPUPMENUMODE = 0x0010
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000


def _process_tree(root_pid: int) -> set[int]:
    try:
        return {root_pid, *(item.pid for item in psutil.Process(root_pid).children(recursive=True))}
    except psutil.NoSuchProcess:
        return {root_pid}


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _owned_by_tree(hwnd: int, pids: set[int]) -> tuple[bool, int | None]:
    owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
    owner_pid = _window_pid(owner) if owner else None
    window_pid = _window_pid(hwnd)
    if window_pid in pids:
        return True, owner_pid
    current = owner
    while current:
        if _window_pid(current) in pids:
            return True, owner_pid
        current = user32.GetWindow(current, 4)
    return False, owner_pid


def _visible_windows(pids: set[int], *, include_untitled: bool = False) -> list[dict[str, object]]:
    windows: list[dict[str, object]] = []

    def collect(hwnd: int, _parameter: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_text(hwnd)
        if not title and not include_untitled:
            return True
        belongs, owner_pid = _owned_by_tree(hwnd, pids)
        if belongs:
            windows.append(
                {
                    "hwnd": int(hwnd),
                    "pid": _window_pid(hwnd),
                    "ownerPid": owner_pid,
                    "title": title,
                    "className": _class_name(hwnd),
                }
            )
        return True

    user32.EnumWindows(ENUM_WINDOWS(collect), 0)
    return windows


def _tree_windows(pids: set[int]) -> list[dict[str, object]]:
    """Report every app-tree top-level HWND, including hidden or untitled windows."""
    windows: list[dict[str, object]] = []

    def collect(hwnd: int, _parameter: int) -> bool:
        window_pid = _window_pid(hwnd)
        belongs, owner_pid = _owned_by_tree(hwnd, pids)
        if belongs:
            windows.append(
                {
                    "hwnd": int(hwnd),
                    "pid": window_pid,
                    "ownerPid": owner_pid,
                    "visible": bool(user32.IsWindowVisible(hwnd)),
                    "title": _window_text(hwnd),
                    "className": _class_name(hwnd),
                }
            )
        return True

    user32.EnumWindows(ENUM_WINDOWS(collect), 0)
    return windows


def _click_cancel(hwnd: int) -> str:
    candidates: list[int] = []

    def collect(child: int, _parameter: int) -> bool:
        if _class_name(child).casefold() == "button":
            text = _window_text(child).strip().casefold().replace("&", "")
            if text in {"cancel", "annuler"}:
                candidates.append(child)
        return True

    user32.EnumChildWindows(hwnd, ENUM_WINDOWS(collect), 0)
    if candidates:
        user32.SendMessageW(candidates[0], 0x00F5, 0, 0)  # BM_CLICK
        return "BM_CLICK"
    user32.SendMessageW(hwnd, 0x0111, 2, 0)  # WM_COMMAND / IDCANCEL
    return "IDCANCEL"


def _find_dialog(pids: set[int]) -> dict[str, object] | None:
    for window in _visible_windows(pids):
        if window["className"] == "#32770":
            return window
    return None


def _main_window(pids: set[int]) -> dict[str, object] | None:
    return next(
        (
            window
            for window in _tree_windows(pids)
            if window["visible"] and str(window["title"]).startswith("OTP LOL")
        ),
        None,
    )


def _any_main_window(pids: set[int]) -> dict[str, object] | None:
    return next(
        (
            window
            for window in _tree_windows(pids)
            if str(window["title"]).startswith("OTP LOL") and window["className"] != "#32768"
        ),
        None,
    )


def _foreground_menu_state(app_pids: set[int], menu_owner_hwnd: int) -> dict[str, int | bool | None]:
    info = GuiThreadInfo()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
        raise OSError("Could not inspect the foreground GUI thread before native menu input.")

    foreground = int(user32.GetForegroundWindow() or 0)
    foreground_pid = _window_pid(foreground) if foreground else None
    focus = int(info.hwndFocus or 0)
    focus_pid = _window_pid(focus) if focus else None
    active_menu = int(info.hwndMenuOwner or 0)
    state = {
        "foregroundHwnd": foreground or None,
        "foregroundPid": foreground_pid,
        "focusHwnd": focus or None,
        "focusPid": focus_pid,
        "menuOwnerHwnd": active_menu or None,
        "popupMenuMode": bool(info.flags & GUI_POPUPMENUMODE),
    }
    if foreground_pid not in app_pids:
        raise RuntimeError(f"Refusing native menu input because the foreground window is outside the isolated app: {state}")
    if not state["popupMenuMode"] or active_menu != menu_owner_hwnd:
        raise RuntimeError(f"Refusing native menu input because the expected popup is not active on the foreground thread: {state}")
    if focus_pid is not None and focus_pid not in app_pids:
        raise RuntimeError(f"Refusing native menu input because keyboard focus is outside the isolated app: {state}")
    return state


def _send_menu_keys(app_pids: set[int], menu_owner_hwnd: int, keys: list[int]) -> dict[str, object]:
    foreground_before = _foreground_menu_state(app_pids, menu_owner_hwnd)
    events = (Input * (len(keys) * 2))()
    event_index = 0
    for key in keys:
        extended = KEYEVENTF_EXTENDEDKEY if key in {0x24, 0x28} else 0  # VK_HOME / VK_DOWN
        for key_up in (False, True):
            event = events[event_index]
            event.type = INPUT_KEYBOARD
            event.data.ki.wVk = key
            event.data.ki.dwFlags = extended | (KEYEVENTF_KEYUP if key_up else 0)
            event_index += 1

    sent = int(user32.SendInput(len(events), events, ctypes.sizeof(Input)))
    if sent != len(events):
        raise OSError(f"SendInput inserted {sent} of {len(events)} native tray menu keyboard events.")
    return {
        "method": "SendInput keyboard stream to verified foreground popup menu",
        "virtualKeys": keys,
        "eventsSent": sent,
        "foregroundBefore": foreground_before,
    }


def _send_menu_click(
    app_pids: set[int],
    menu_owner_hwnd: int,
    popup_hwnd: int,
    menu_handle: int,
    item_index: int,
) -> dict[str, object]:
    foreground_before = _foreground_menu_state(app_pids, menu_owner_hwnd)
    if not user32.IsWindowVisible(popup_hwnd):
        raise RuntimeError("Refusing mouse input because the recorded native tray popup is no longer visible.")

    item_rect = wintypes.RECT()
    if not user32.GetMenuItemRect(
        menu_owner_hwnd,
        menu_handle,
        item_index,
        ctypes.byref(item_rect),
    ):
        raise OSError(f"Could not locate native tray menu item {item_index} for a real-input click.")
    target = {
        "left": int(item_rect.left),
        "top": int(item_rect.top),
        "right": int(item_rect.right),
        "bottom": int(item_rect.bottom),
    }
    x = (target["left"] + target["right"]) // 2
    y = (target["top"] + target["bottom"]) // 2
    popup_rect = _rect(popup_hwnd)
    if not (popup_rect["left"] <= x < popup_rect["right"] and popup_rect["top"] <= y < popup_rect["bottom"]):
        raise RuntimeError(f"The native tray item rectangle falls outside its active popup: {target}; popup={popup_rect}")

    virtual_left = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    virtual_top = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    virtual_width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    virtual_height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    if virtual_width < 2 or virtual_height < 2:
        raise RuntimeError(f"The virtual desktop dimensions are invalid: {virtual_width}x{virtual_height}.")
    normalized_x = round((x - virtual_left) * 65535 / (virtual_width - 1))
    normalized_y = round((y - virtual_top) * 65535 / (virtual_height - 1))
    if not (0 <= normalized_x <= 65535 and 0 <= normalized_y <= 65535):
        raise RuntimeError(f"The tray menu item is outside the virtual desktop: target=({x},{y}).")

    move_event = Input()
    move_event.type = INPUT_MOUSE
    move_event.data.mi.dx = normalized_x
    move_event.data.mi.dy = normalized_y
    move_event.data.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    sent = int(user32.SendInput(1, ctypes.byref(move_event), ctypes.sizeof(Input)))
    if sent != 1:
        raise OSError(f"SendInput inserted {sent} of 1 tray-menu mouse-move events.")

    cursor = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(cursor)):
        raise OSError("Could not verify the cursor position over the active tray menu item.")
    cursor_position = {"x": int(cursor.x), "y": int(cursor.y)}
    if abs(cursor_position["x"] - x) > 1 or abs(cursor_position["y"] - y) > 1:
        raise RuntimeError(f"The system cursor did not reach the native menu item: expected=({x},{y}); actual={cursor_position}.")
    foreground_after_move = _foreground_menu_state(app_pids, menu_owner_hwnd)

    click_events = (Input * 2)()
    for event, flags in zip(click_events, (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)):
        event.type = INPUT_MOUSE
        event.data.mi.dwFlags = flags
    sent = int(user32.SendInput(len(click_events), click_events, ctypes.sizeof(Input)))
    if sent != len(click_events):
        release_event = Input()
        release_event.type = INPUT_MOUSE
        release_event.data.mi.dwFlags = MOUSEEVENTF_LEFTUP
        user32.SendInput(1, ctypes.byref(release_event), ctypes.sizeof(Input))
        raise OSError(f"SendInput inserted {sent} of {len(click_events)} tray-menu mouse-click events.")

    return {
        "method": "SendInput mouse click on native menu item rectangle",
        "menuItemIndex": item_index,
        "targetRect": target,
        "cursorPosition": cursor_position,
        "eventsSent": 3,
        "foregroundBefore": foreground_before,
        "foregroundAfterMove": foreground_after_move,
    }


def _wait_for_popup_closed(popup_hwnd: int, menu_owner_hwnd: int, timeout: float = 3) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    latest_state: dict[str, int | bool | None] | None = None
    while time.monotonic() < deadline:
        popup_exists = bool(user32.IsWindow(popup_hwnd))
        popup_visible = bool(popup_exists and user32.IsWindowVisible(popup_hwnd))
        info = GuiThreadInfo()
        info.cbSize = ctypes.sizeof(info)
        menu_state_available = bool(user32.GetGUIThreadInfo(0, ctypes.byref(info)))
        latest_state = {
            "popupExists": popup_exists,
            "popupVisible": popup_visible,
            "popupMenuMode": bool(info.flags & GUI_POPUPMENUMODE) if menu_state_available else False,
            "menuOwnerHwnd": int(info.hwndMenuOwner or 0) if menu_state_available else None,
            "menuStateAvailable": menu_state_available,
        }
        menu_still_active = (
            menu_state_available
            and bool(info.flags & GUI_POPUPMENUMODE)
            and int(info.hwndMenuOwner or 0) == menu_owner_hwnd
        )
        if not popup_visible and not menu_still_active:
            return latest_state
        time.sleep(0.05)
    raise RuntimeError(f"The native tray popup did not close after input: {latest_state}")


def _read_tray_callback_markers(path: Path) -> list[dict[str, object]]:
    try:
        markers = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(markers, list):
        raise TypeError("The native tray callback evidence is not a JSON list.")
    return markers


def _wait_for_tray_callback(
    path: Path,
    previous_count: int,
    label: str,
    app_pid: int,
    timeout: float = 5,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    entered = None
    while time.monotonic() < deadline:
        markers = _read_tray_callback_markers(path)
        new_markers = [
            marker
            for marker in markers[previous_count:]
            if marker.get("pid") == app_pid and marker.get("item") == label
        ]
        entered = next((marker for marker in new_markers if marker.get("stage") == "entered"), None)
        if entered:
            completed = next(
                (marker for marker in new_markers if marker.get("stage") in {"returned", "raised"}),
                None,
            )
            if completed:
                return {"observed": True, "entered": entered, "completed": completed}
        time.sleep(0.05)
    if entered:
        return {"observed": True, "entered": entered, "completed": None}
    return {"observed": False, "item": label, "timeoutSeconds": timeout}


def _rect(hwnd: int) -> dict[str, int]:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("GetWindowRect failed for the OTP LOL window.")
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


def _window_snapshot(app_pid: int) -> dict[str, object]:
    pids = _process_tree(app_pid)
    window = _any_main_window(pids)
    if window is None:
        raise RuntimeError("The app-owned OTP LOL HWND is unavailable.")
    hwnd = int(window["hwnd"])
    monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(MonitorInfo)
    bounds = None
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        bounds = {
            "left": int(info.rcMonitor.left),
            "top": int(info.rcMonitor.top),
            "right": int(info.rcMonitor.right),
            "bottom": int(info.rcMonitor.bottom),
            "width": int(info.rcMonitor.right - info.rcMonitor.left),
            "height": int(info.rcMonitor.bottom - info.rcMonitor.top),
        }
    return {
        "nativeWindow": window,
        "rect": _rect(hwnd),
        "monitorBounds": bounds,
    }


def _other_otp_instances(app_pids: set[int]) -> list[dict[str, object]]:
    matches = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if process.pid in app_pids:
                continue
            name = str(process.info.get("name") or "")
            command = process.info.get("cmdline") or []
            command_text = " ".join(str(part) for part in command).casefold()
            if name.casefold() == "otp lol.exe" or "launcher_web.py" in command_text or "native_app.py" in command_text:
                matches.append({"pid": process.pid, "name": name})
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except psutil.AccessDenied as error:
            try:
                if str(process.name()).casefold() == "otp lol.exe":
                    matches.append({"pid": process.pid, "name": "OTP LOL.exe", "inspection": str(error)})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def collect(hwnd: int, _parameter: int) -> bool:
        title = _window_text(hwnd)
        if title.startswith("OTP LOL") and _window_pid(hwnd) not in app_pids:
            matches.append({"pid": _window_pid(hwnd), "name": "window", "title": title})
        return True

    user32.EnumWindows(ENUM_WINDOWS(collect), 0)
    return matches


def _send_hotkey(app_pid: int, key: str) -> dict[str, object]:
    normalized = key.casefold()
    if normalized not in {"c", "p"}:
        raise ValueError("Only the configured Alt+C and Alt+P shortcuts are allowed.")
    pids = _process_tree(app_pid)
    other_instances = _other_otp_instances(pids)
    if other_instances:
        raise RuntimeError(f"Refusing global key input while another OTP LOL process/window exists: {other_instances}")
    window = _main_window(pids)
    if window is None:
        raise RuntimeError("The app window must be visible before sending a global shortcut.")
    hwnd = int(window["hwnd"])
    if not user32.SetForegroundWindow(hwnd):
        foreground = user32.GetForegroundWindow()
        if _window_pid(foreground) not in pids:
            raise RuntimeError("Could not safely focus the isolated OTP LOL window; no key input was sent.")
    foreground = user32.GetForegroundWindow()
    if _window_pid(foreground) not in pids:
        raise RuntimeError("The isolated OTP LOL window is not foreground; no key input was sent.")

    key_code = ord(normalized.upper())
    key_up = 0x0002
    user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU / Alt down
    time.sleep(0.08)
    user32.keybd_event(key_code, 0, 0, 0)
    user32.keybd_event(key_code, 0, key_up, 0)
    time.sleep(0.08)
    user32.keybd_event(0x12, 0, key_up, 0)
    return {
        "hotkey": f"alt+{normalized}",
        "injected": True,
        "foregroundPid": _window_pid(foreground),
        "externalOtpInstances": other_instances,
    }


def _select_tray_menu(app_pid: int, tray_file: str, state_file: str, action: str) -> dict[str, object]:
    item_indices = {"toggle": 0, "settings": 1, "presets": 2, "auto-ban": 3, "quit": 4}
    if action not in {*item_indices, "inspect"}:
        raise ValueError("Unknown tray action.")
    tray = json.loads(Path(tray_file).read_text(encoding="utf-8"))
    tray_states_path = Path(state_file)
    tray_callbacks_path = tray_states_path.with_name("tray-callbacks.json")
    try:
        snapshots_before = json.loads(tray_states_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        snapshots_before = []
    callback_markers_before = _read_tray_callback_markers(tray_callbacks_path)
    if tray.get("pid") != app_pid:
        raise RuntimeError("Refusing to message a tray HWND not recorded for this app process.")
    expected_labels = [
        "Show/Hide",
        "Settings",
        "Enable presets automations",
        "Enable auto-ban",
        "Quit",
    ]
    if tray.get("menuLabels") != expected_labels:
        raise RuntimeError(f"The native tray menu differs from the expected app menu: {tray.get('menuLabels')}")

    pids = _process_tree(app_pid)
    tray_hwnd = int(tray["hwnd"])
    if not user32.IsWindow(tray_hwnd) or _window_pid(tray_hwnd) not in pids:
        raise RuntimeError("The recorded tray notification HWND is no longer owned by the app process tree.")
    menu_owner_hwnd = int(tray["menuHwnd"])
    if not user32.IsWindow(menu_owner_hwnd) or _window_pid(menu_owner_hwnd) not in pids:
        raise RuntimeError("The recorded tray menu-owner HWND is no longer owned by the app process tree.")
    window_before = _any_main_window(pids)
    if window_before is None:
        raise RuntimeError("The main OTP LOL window is unavailable before the tray action.")
    visible_before = bool(window_before["visible"])
    if not user32.PostMessageW(tray_hwnd, 0x040B, 0, 0x0205):  # WM_NOTIFY / WM_RBUTTONUP
        raise OSError("Could not post the native tray right-click notification.")

    deadline = time.monotonic() + 4
    popup = None
    while time.monotonic() < deadline:
        popup = next(
            (item for item in _visible_windows(pids, include_untitled=True) if item["className"] == "#32768"),
            None,
        )
        if popup:
            break
        time.sleep(0.05)
    if popup is None:
        raise RuntimeError("pystray did not show its app-owned native menu after WM_NOTIFY.")

    snapshots = json.loads(tray_states_path.read_text(encoding="utf-8"))
    if len(snapshots) <= len(snapshots_before):
        raise RuntimeError("The native menu snapshot did not advance for this tray interaction.")
    menu_state = snapshots[-1]
    if menu_state.get("pid") != app_pid:
        raise RuntimeError("The captured native tray menu state does not belong to the isolated app.")
    if [item.get("label") for item in menu_state.get("items", [])] != expected_labels:
        raise RuntimeError("The captured native tray menu state has unexpected item labels.")
    if action != "inspect" and not menu_state["items"][item_indices[action]]["enabled"]:
        raise RuntimeError(f"Refusing to select disabled native tray item: {action}.")

    if action == "inspect":
        keys = [0x1B]  # VK_ESCAPE
        input_evidence = _send_menu_keys(pids, menu_owner_hwnd, keys)
    else:
        item_index = item_indices[action]
        menu_handle = int(menu_state.get("menuHandle") or 0)
        if not menu_handle:
            raise RuntimeError("The native tray snapshot has no HMENU for a real-input item click.")
        input_evidence = _send_menu_click(
            pids,
            menu_owner_hwnd,
            int(popup["hwnd"]),
            menu_handle,
            item_index,
        )
    popup_closure = _wait_for_popup_closed(int(popup["hwnd"]), menu_owner_hwnd)
    callback_marker = None
    if action != "inspect":
        callback_marker = _wait_for_tray_callback(
            tray_callbacks_path,
            len(callback_markers_before),
            expected_labels[item_indices[action]],
            app_pid,
        )

    if action == "inspect":
        return {
            "action": "Inspect",
            "notification": "WM_NOTIFY/WM_RBUTTONUP",
            "menuClass": popup["className"],
            "menuPid": popup["pid"],
            "menuState": menu_state,
            "inputEvidence": input_evidence,
            "popupClosure": popup_closure,
            "nativeWindowBefore": window_before,
            "nativeWindowAfter": _any_main_window(_process_tree(app_pid)),
        }

    if not callback_marker["observed"]:
        evidence = {
            "item": expected_labels[item_indices[action]],
            "inputEvidence": input_evidence,
            "popupClosure": popup_closure,
            "callbackMarker": callback_marker,
            "nativeWindowBefore": window_before,
            "nativeWindowAfter": _any_main_window(_process_tree(app_pid)),
        }
        raise RuntimeError(
            "The tray popup closed without an app-owned item callback marker: "
            f"{json.dumps(evidence, separators=(',', ':'))}"
        )

    if action == "toggle":
        expected_visible = not visible_before
        deadline = time.monotonic() + 5
        current = None
        while time.monotonic() < deadline:
            current = _any_main_window(_process_tree(app_pid))
            if current and bool(current["visible"]) == expected_visible:
                return {
                    "action": "Show/Hide",
                    "notification": "WM_NOTIFY/WM_RBUTTONUP",
                    "menuClass": popup["className"],
                    "menuPid": popup["pid"],
                    "visibleBefore": visible_before,
                    "visibleAfter": bool(current["visible"]),
                    "nativeWindowBefore": window_before,
                    "nativeWindowAfter": current,
                    "menuState": menu_state,
                    "inputEvidence": input_evidence,
                    "popupClosure": popup_closure,
                    "callbackMarker": callback_marker,
                    "externalOtpInstances": [],
                }
            time.sleep(0.05)
        evidence = {
            "nativeWindowBefore": window_before,
            "nativeWindowAfter": current,
            "expectedVisibleAfter": expected_visible,
            "inputEvidence": input_evidence,
            "popupClosure": popup_closure,
            "callbackMarker": callback_marker,
        }
        raise RuntimeError(
            "The native Show/Hide tray callback did not change main-window visibility; "
            f"observed={json.dumps(evidence, separators=(',', ':'))}"
        )

    if action == "settings":
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = _any_main_window(_process_tree(app_pid))
            if current and current["visible"]:
                return {
                    "action": "Settings",
                    "notification": "WM_NOTIFY/WM_RBUTTONUP",
                    "menuClass": popup["className"],
                    "menuPid": popup["pid"],
                    "visibleAfter": True,
                    "nativeWindowBefore": window_before,
                    "nativeWindowAfter": current,
                    "menuState": menu_state,
                    "inputEvidence": input_evidence,
                    "popupClosure": popup_closure,
                    "callbackMarker": callback_marker,
                }
            time.sleep(0.05)
        raise RuntimeError("The native Settings tray callback did not show the app window.")

    if action in {"presets", "auto-ban"}:
        return {
            "action": action,
            "notification": "WM_NOTIFY/WM_RBUTTONUP",
            "menuClass": popup["className"],
            "menuPid": popup["pid"],
            "menuState": menu_state,
            "nativeWindowBefore": window_before,
            "nativeWindowAfter": _any_main_window(_process_tree(app_pid)),
            "inputEvidence": input_evidence,
            "popupClosure": popup_closure,
            "callbackMarker": callback_marker,
        }

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not psutil.pid_exists(app_pid):
            return {
                "action": "Quit",
                "notification": "WM_NOTIFY/WM_RBUTTONUP",
                "menuClass": popup["className"],
                "menuPid": popup["pid"],
                "processExited": True,
                "nativeWindowBefore": window_before,
                "inputEvidence": input_evidence,
                "popupClosure": popup_closure,
                "callbackMarker": callback_marker,
            }
        time.sleep(0.1)
    raise RuntimeError("The native Quit tray callback did not stop the isolated app process.")


def main() -> int:
    if __import__("sys").platform != "win32":
        raise SystemExit("The native desktop E2E proof is Windows-only.")

    parser = argparse.ArgumentParser()
    parser.add_argument("--app-pid", type=int, required=True)
    parser.add_argument("--wait-and-cancel", action="store_true")
    parser.add_argument("--wait-main-window", action="store_true")
    parser.add_argument("--window-snapshot", action="store_true")
    parser.add_argument("--send-hotkey", action="store_true")
    parser.add_argument("--key", choices=("c", "p", "C", "P"))
    parser.add_argument("--tray-menu", choices=("toggle", "settings", "presets", "auto-ban", "inspect", "quit"))
    parser.add_argument("--tray-file")
    parser.add_argument("--tray-state-file")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout

    if args.wait_main_window:
        while time.monotonic() < deadline:
            window = _main_window(_process_tree(args.app_pid))
            if window:
                print(json.dumps({"nativeWindow": window}, separators=(",", ":")), flush=True)
                return 0
            time.sleep(0.1)
        pids = _process_tree(args.app_pid)
        windows = _tree_windows(pids)
        print(
            json.dumps(
                {
                    "appTreePids": sorted(pids),
                    "appTreeTopLevelWindows": windows,
                    "visibleAppTreeWindows": sum(bool(window["visible"]) for window in windows),
                },
                separators=(",", ":"),
            ),
            file=__import__("sys").stderr,
            flush=True,
        )
        raise SystemExit("The OTP LOL native window was not found in the isolated process tree.")

    if args.window_snapshot:
        print(json.dumps(_window_snapshot(args.app_pid), separators=(",", ":")))
        return 0

    if args.send_hotkey:
        if not args.key:
            parser.error("--send-hotkey requires --key")
        print(json.dumps(_send_hotkey(args.app_pid, args.key), separators=(",", ":")))
        return 0

    if args.tray_menu:
        if not args.tray_file or not args.tray_state_file:
            parser.error("--tray-menu requires --tray-file and --tray-state-file")
        print(json.dumps(_select_tray_menu(args.app_pid, args.tray_file, args.tray_state_file, args.tray_menu), separators=(",", ":")))
        return 0

    if not args.wait_and_cancel:
        parser.error("Choose --wait-and-cancel or --wait-main-window")

    print(json.dumps({"waitingFor": "native_file_dialog"}), flush=True)
    while time.monotonic() < deadline:
        pids = _process_tree(args.app_pid)
        dialog = _find_dialog(pids)
        if dialog:
            cancel_method = _click_cancel(int(dialog["hwnd"]))
            cancel_deadline = time.monotonic() + 5
            while time.monotonic() < cancel_deadline:
                if not user32.IsWindow(int(dialog["hwnd"])) or not user32.IsWindowVisible(int(dialog["hwnd"])):
                    print(
                        json.dumps(
                            {
                                "nativeDialog": {
                                    "title": dialog["title"],
                                    "className": dialog["className"],
                                    "processOwned": True,
                                },
                                "win32CancelClicked": True,
                                "cancelMethod": cancel_method,
                                "dialogClosed": True,
                            },
                            separators=(",", ":"),
                        ),
                        flush=True,
                    )
                    return 0
                time.sleep(0.1)
            raise SystemExit("Win32 sent Cancel, but the native dialog remained visible.")
        time.sleep(0.1)
    raise SystemExit("No visible native file dialog owned by the test app appeared.")


if __name__ == "__main__":
    main()
