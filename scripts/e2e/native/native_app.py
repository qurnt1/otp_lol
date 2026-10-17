"""Start the real OTP LOL source desktop app inside an isolated test profile."""

from __future__ import annotations

import argparse
import ctypes
import ipaddress
import json
import os
import socket
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlsplit


def _league_processes() -> list[dict[str, Any]]:
    import psutil

    found = []
    for process in psutil.process_iter(["name"]):
        try:
            if str(process.info.get("name") or "").casefold() == "leagueclientux.exe":
                found.append({"pid": process.pid, "name": "LeagueClientUx.exe"})
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, psutil.ZombieProcess) as error:
            raise RuntimeError("Cannot verify whether LeagueClientUx.exe is running.") from error
    return found


def _emit(event: str, **payload: Any) -> None:
    print("NATIVE_E2E " + json.dumps({"event": event, **payload}), flush=True)


def _write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def _is_under(path: str | Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _preflight() -> int:
    try:
        clients = _league_processes()
    except RuntimeError as error:
        print(json.dumps({"preflightError": str(error)}, separators=(",", ":")))
        return 24
    print(json.dumps({"leagueProcesses": clients}, separators=(",", ":")))
    return 23 if clients else 0


def _isolate(state_dir: Path) -> tuple[Path, Path, Path]:
    if not state_dir.name.startswith("otp-lol-native-e2e-"):
        raise RuntimeError("Refusing to use a profile outside the native E2E temp namespace.")
    if state_dir.exists() and any(state_dir.iterdir()):
        raise RuntimeError("The native E2E profile directory must be new and empty.")

    profile_dir = state_dir / "profile"
    appdata_dir = profile_dir / "Roaming"
    localappdata_dir = profile_dir / "Local"
    temp_dir = state_dir / "temp"
    for path in (appdata_dir, localappdata_dir, temp_dir):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = str(appdata_dir.resolve())
    os.environ["LOCALAPPDATA"] = str(localappdata_dir.resolve())
    os.environ["TEMP"] = str(temp_dir.resolve())
    os.environ["TMP"] = str(temp_dir.resolve())
    tempfile.tempdir = None
    if Path(tempfile.gettempdir()).resolve() != temp_dir.resolve():
        raise RuntimeError("Python temporary-file resolution escaped the isolated profile.")
    return appdata_dir.resolve(), localappdata_dir.resolve(), temp_dir.resolve()


def _block_external_requests() -> None:
    """Allow app-local HTTP while preventing Python requests from reaching the Internet."""
    import requests

    original_request = requests.sessions.Session.request

    def isolated_request(session, method, url, **kwargs):
        if (urlsplit(str(url)).hostname or "").casefold() in {"127.0.0.1", "localhost", "::1"}:
            return original_request(session, method, url, **kwargs)
        response = requests.Response()
        response.status_code = 503
        response.reason = "External network blocked by native E2E harness"
        response.url = str(url)
        response.request = requests.Request(method=method, url=url).prepare()
        response.headers["Content-Type"] = "application/json"
        response._content = b'{"detail":"External network blocked by native E2E harness"}'
        _emit("external_http_blocked", host=urlsplit(str(url)).hostname or "unknown")
        return response

    requests.sessions.Session.request = isolated_request


def _block_external_sockets() -> None:
    """Prevent Python code in this process from resolving or connecting off loopback."""
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto

    def is_loopback(host: Any) -> bool:
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="ignore")
        if not isinstance(host, str):
            return False
        if host.casefold() == "localhost":
            return True
        try:
            return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
        except ValueError:
            return False

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any):
        if not is_loopback(host):
            _emit("external_socket_blocked", operation="dns")
            raise socket.gaierror(socket.EAI_FAIL, "External DNS is blocked by native E2E harness.")
        return original_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(connection: socket.socket, address: Any) -> None:
        if connection.family in {socket.AF_INET, socket.AF_INET6} and not is_loopback(address[0]):
            _emit("external_socket_blocked", operation="connect")
            raise OSError("External sockets are blocked by native E2E harness.")
        original_connect(connection, address)

    def guarded_connect_ex(connection: socket.socket, address: Any) -> int:
        if connection.family in {socket.AF_INET, socket.AF_INET6} and not is_loopback(address[0]):
            _emit("external_socket_blocked", operation="connect_ex")
            return getattr(socket, "EHOSTUNREACH", 10065)
        return original_connect_ex(connection, address)

    def guarded_sendto(connection: socket.socket, data: Any, *args: Any) -> int:
        address = args[-1] if args else None
        if (
            connection.family in {socket.AF_INET, socket.AF_INET6}
            and isinstance(address, tuple)
            and address
            and not is_loopback(address[0])
        ):
            _emit("external_socket_blocked", operation="sendto")
            raise OSError("External sockets are blocked by native E2E harness.")
        return original_sendto(connection, data, *args)

    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.sendto = guarded_sendto


def _instrument_native_actions(state_dir: Path) -> None:
    """Capture native callbacks while preventing shell actions from escaping the test."""
    shell_path = state_dir / "native-shell-actions.json"
    shell_actions: list[dict[str, Any]] = []
    shell_lock = RLock()

    def record_shell_action(action: dict[str, Any]) -> None:
        with shell_lock:
            shell_actions.append(action)
            _write_json(shell_path, shell_actions)
        _emit("native_shell_action_captured", **action)

    def capture_external_browser(url: str, new: int = 0, autoraise: bool = True) -> bool:
        record_shell_action(
            {
                "kind": "external_url",
                "url": str(url),
                "new": int(new),
                "autoraise": bool(autoraise),
                "launchSuppressed": True,
            }
        )
        return True

    webbrowser.open = capture_external_browser

    if hasattr(os, "startfile"):
        def capture_folder_open(path: str, operation: str = "open") -> None:
            record_shell_action(
                {
                    "kind": "open_folder",
                    "path": os.fspath(path),
                    "operation": str(operation),
                    "launchSuppressed": True,
                }
            )

        os.startfile = capture_folder_open

    try:
        import pystray._win32 as pystray_win32
    except ImportError:
        _emit("tray_instrumentation_unavailable")
        return

    tray_path = state_dir / "tray-window.json"
    tray_states_path = state_dir / "tray-menu-states.json"
    tray_callbacks_path = state_dir / "tray-callbacks.json"
    tray_state_lock = RLock()
    original_show = pystray_win32.Icon._show
    original_notify = pystray_win32.Icon._on_notify
    original_handler = pystray_win32.Icon._handler
    from pystray import _base as pystray_base

    def record_tray_callback(label: str, stage: str, error_type: str | None = None) -> None:
        marker = {
            "pid": os.getpid(),
            "item": label,
            "stage": stage,
            "timeNs": time.time_ns(),
        }
        if error_type is not None:
            marker["errorType"] = error_type
        with tray_state_lock:
            try:
                markers = json.loads(tray_callbacks_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                markers = []
            markers.append(marker)
            _write_json(tray_callbacks_path, markers)
        _emit("tray_callback_marker", **marker)

    def instrument_tray_handler(icon: Any, item: Any):
        action = getattr(item, "_action", None)
        label = str(getattr(item, "text", ""))
        if (
            callable(action)
            and not isinstance(action, pystray_base.Menu)
            and not getattr(action, "_native_e2e_wrapped", False)
        ):
            def record_action(*args: Any, **kwargs: Any):
                record_tray_callback(label, "entered")
                try:
                    result = action(*args, **kwargs)
                except BaseException as error:
                    record_tray_callback(label, "raised", type(error).__name__)
                    raise
                record_tray_callback(label, "returned")
                return result

            record_action._native_e2e_wrapped = True
            item._action = record_action
        return original_handler(icon, item)

    def record_tray_window(icon: Any) -> None:
        original_show(icon)
        menu_items = getattr(icon.menu, "items", ()) if icon.menu else ()
        _write_json(
            tray_path,
            {
                "pid": os.getpid(),
                "hwnd": int(icon._hwnd),
                "menuHwnd": int(icon._menu_hwnd),
                "title": str(icon.title),
                "menuLabels": [str(item.text) for item in menu_items],
            },
        )
        _emit("tray_window_ready", hwnd=int(icon._hwnd), menuHwnd=int(icon._menu_hwnd))

    def record_tray_menu_state(icon: Any, wparam: int, lparam: int) -> None:
        if lparam == pystray_win32.win32.WM_RBUTTONUP and icon._menu_handle:
            menu_handle, _callbacks = icon._menu_handle
            get_menu_item_info = ctypes.windll.user32.GetMenuItemInfoW
            get_menu_item_info.argtypes = [
                pystray_win32.win32.wintypes.HMENU,
                pystray_win32.win32.wintypes.UINT,
                pystray_win32.win32.wintypes.BOOL,
                pystray_win32.win32.LPMENUITEMINFO,
            ]
            get_menu_item_info.restype = pystray_win32.win32.wintypes.BOOL
            items = []
            for index, item in enumerate(icon.menu.items):
                native_item = pystray_win32.win32.MENUITEMINFO()
                native_item.cbSize = ctypes.sizeof(native_item)
                native_item.fMask = pystray_win32.win32.MIIM_STATE
                if not get_menu_item_info(
                    menu_handle,
                    index,
                    True,
                    ctypes.byref(native_item),
                ):
                    raise OSError("Could not inspect the native tray menu item state.")
                items.append(
                    {
                        "label": str(item.text),
                        "enabled": not bool(native_item.fState & pystray_win32.win32.MFS_DISABLED),
                        "checked": bool(native_item.fState & pystray_win32.win32.MFS_CHECKED),
                    }
                )
            with tray_state_lock:
                try:
                    snapshots = json.loads(tray_states_path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    snapshots = []
                snapshots.append({"pid": os.getpid(), "items": items, "menuHandle": int(menu_handle)})
                _write_json(tray_states_path, snapshots)
        original_notify(icon, wparam, lparam)

    pystray_win32.Icon._show = record_tray_window
    pystray_win32.Icon._on_notify = record_tray_menu_state
    pystray_win32.Icon._handler = instrument_tray_handler
    pystray_win32.Icon._handler = instrument_tray_handler


def _instrument_fullscreen_bridge(bridge_type: type) -> None:
    """Report whether the native fullscreen RPC enters, returns, or raises."""
    original = bridge_type.toggle_fullscreen

    def capture_fullscreen_rpc(self):
        _emit("fullscreen_bridge_rpc", stage="entered")
        try:
            result = original(self)
        except Exception as error:
            _emit(
                "fullscreen_bridge_rpc",
                stage="raised",
                errorType=type(error).__name__,
                error=str(error),
            )
            raise
        _emit("fullscreen_bridge_rpc", stage="returned", result=result)
        return result

    bridge_type.toggle_fullscreen = capture_fullscreen_rpc


def _instrument_single_instance(state_dir: Path) -> None:
    """Record the real primary lock contents after production acquires the lock."""
    from src.services import single_instance

    original_check = single_instance.check_single_instance

    def capture_lock() -> bool:
        acquired = original_check()
        if acquired:
            descriptor = single_instance._lock_fd
            if descriptor is None:
                raise RuntimeError("The production instance guard succeeded without retaining its lock descriptor.")
            position = os.lseek(descriptor, 0, os.SEEK_CUR)
            os.lseek(descriptor, 0, os.SEEK_SET)
            owner_pid = int(os.read(descriptor, 64).decode("ascii"))
            os.lseek(descriptor, position, os.SEEK_SET)
            from src.config import LOCKFILE_PATH

            proof = {
                "lockAcquired": True,
                "pid": os.getpid(),
                "lockOwnerPid": owner_pid,
                "lockfilePath": str(Path(LOCKFILE_PATH).resolve()),
            }
            _write_json(state_dir / "primary-single-instance.json", proof)
            _emit("single_instance_lock_acquired", lockOwnerPid=owner_pid)
        return acquired

    single_instance.check_single_instance = capture_lock


def _block_lcu_discovery(state_dir: Path) -> Path:
    """Keep this desktop-only run disconnected and record any attempted LCU target."""
    import lcu_driver.utils as lcu_utils
    import psutil
    from lcu_driver.connection import Connection

    evidence_path = state_dir / "lcu-discovery.json"
    evidence = {"scanner": "lcu_driver.utils.process_iter", "scanCalls": 0, "candidateCount": 0, "attempts": []}
    lock = RLock()

    def save_evidence() -> None:
        with lock:
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    def no_processes(*_args: Any, **_kwargs: Any):
        with lock:
            evidence["scanCalls"] += 1
            save_evidence()
        return iter(())

    async def prevent_connection(connection: Any) -> None:
        try:
            process = psutil.Process(connection._lcu_pid)
            process_name = process.name()
            process_path = process.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            process_name = "unavailable"
            process_path = None

        def safe_target(value: str) -> dict[str, Any]:
            parsed = urlsplit(value)
            return {"scheme": parsed.scheme, "host": parsed.hostname, "port": parsed.port}

        with lock:
            evidence["candidateCount"] += 1
            evidence["attempts"].append(
                {
                    "pid": connection._lcu_pid,
                    "processName": process_name,
                    "processPath": process_path,
                    "port": connection._port,
                    "httpTarget": safe_target(connection.address),
                    "websocketTarget": safe_target(connection.ws_address),
                    "networkOpened": False,
                }
            )
            save_evidence()
        raise RuntimeError("Native E2E guard blocked an LCU connection before HTTP or WebSocket access.")

    lcu_utils.process_iter = no_processes
    Connection.init = prevent_connection
    save_evidence()
    return evidence_path


def _run_app(state_dir: Path, cdp_port: int) -> int:
    roaming, local, temp = _isolate(state_dir)
    repo_root = Path(__file__).resolve().parents[3]
    if not _is_under(local, state_dir.resolve()):
        raise RuntimeError("LOCALAPPDATA escaped the isolated E2E profile.")
    _block_external_sockets()
    _instrument_native_actions(state_dir)
    sys.path.insert(0, str(repo_root))
    clients = _league_processes()
    if clients:
        _emit("preflight_refused", leagueProcesses=clients)
        return 23

    import webview

    if "REMOTE_DEBUGGING_PORT" not in webview.settings:
        raise RuntimeError("Installed pywebview does not expose REMOTE_DEBUGGING_PORT.")
    webview.settings["REMOTE_DEBUGGING_PORT"] = cdp_port

    _block_external_requests()

    # This test never exercises the League connector. Keep the production UI in a
    # deterministic disconnected state even if League starts after preflight.
    lcu_evidence_path = _block_lcu_discovery(state_dir)

    _instrument_single_instance(state_dir)

    import launcher_web
    import src.desktop.bridge as desktop_bridge_module
    import src.api.context as context_module
    import src.config.paths as app_paths

    _instrument_fullscreen_bridge(desktop_bridge_module.DesktopBridge)
    context_module.psutil.process_iter = lambda *_args, **_kwargs: iter(())
    resolved_paths = {
        "parameters": app_paths.PARAMETERS_PATH,
        "history": app_paths.HISTORY_PATH,
        "lockfile": app_paths.LOCKFILE_PATH,
        "ddragonCache": app_paths.DDRAGON_CACHE_FILE,
        "webviewStorage": app_paths.WEBVIEW_STORAGE_DIR,
        "lcuCache": app_paths.LCU_CACHE_DIR,
    }
    if not (
        _is_under(app_paths.PARAMETERS_PATH, roaming)
        and _is_under(app_paths.HISTORY_PATH, roaming)
        and _is_under(app_paths.WEBVIEW_STORAGE_DIR, roaming)
        and all(
            _is_under(path, temp)
            for path in (
                app_paths.LOCKFILE_PATH,
                app_paths.DDRAGON_CACHE_FILE,
                app_paths.ICONS_CACHE_DIR,
                app_paths.SPELLS_CACHE_DIR,
                app_paths.SKINS_CACHE_DIR,
                app_paths.RUNES_CACHE_DIR,
            )
        )
        and _is_under(app_paths.LCU_CACHE_DIR, roaming)
        and _is_under(app_paths.ACCOUNT_CACHE_DIR, roaming)
    ):
        raise RuntimeError("An application storage path escaped the isolated E2E profile.")

    _emit(
        "app_starting",
        pid=os.getpid(),
        cdpPort=cdp_port,
        isolatedProfile=True,
        isolatedPaths=True,
        leagueProcessScan="blocked-empty-in-test-process",
        lcuEvidenceFile=str(lcu_evidence_path.resolve()),
        existingLeagueProcesses=clients,
        productExecutableLaunched=False,
        pathKeys=sorted(resolved_paths),
    )
    return launcher_web.main()


def _process_tree(root_pid: int, expected_browser_arg: str | None = None) -> int:
    import psutil

    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        print(json.dumps({"root": None, "descendants": []}, separators=(",", ":")))
        return 0
    descendants = root.children(recursive=True)
    matching_browser_processes = []
    if expected_browser_arg:
        for process in descendants:
            try:
                command_line = process.cmdline()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            if expected_browser_arg in command_line:
                matching_browser_processes.append({"pid": process.pid, "name": process.name()})
    print(
        json.dumps(
            {
                "root": {
                    "pid": root.pid,
                    "name": root.name(),
                    "createTime": root.create_time(),
                },
                "descendants": [
                    {
                        "pid": process.pid,
                        "name": process.name(),
                        "createTime": process.create_time(),
                    }
                    for process in descendants
                    if process.is_running()
                ],
                "browserIsolationArgumentFound": bool(matching_browser_processes),
                "browserIsolationProcesses": matching_browser_processes,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _remaining_processes(pids: str) -> int:
    import psutil

    alive = []
    for raw_pid in pids.split(","):
        try:
            process = psutil.Process(int(raw_pid))
            alive.append({"pid": process.pid, "name": process.name(), "createTime": process.create_time()})
        except (ValueError, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    print(json.dumps({"alive": alive}, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--tree-pid", type=int)
    parser.add_argument("--expected-browser-arg")
    parser.add_argument("--pids-alive")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--cdp-port", type=int)
    args = parser.parse_args()

    if args.preflight:
        return _preflight()
    if args.tree_pid is not None:
        return _process_tree(args.tree_pid, args.expected_browser_arg)
    if args.pids_alive is not None:
        return _remaining_processes(args.pids_alive)
    if args.run:
        if args.state_dir is None or args.cdp_port is None or not 1 <= args.cdp_port <= 65535:
            parser.error("--run requires --state-dir and a valid --cdp-port")
        return _run_app(args.state_dir.resolve(), args.cdp_port)
    parser.error("Choose --preflight, --tree-pid, --pids-alive, or --run")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
