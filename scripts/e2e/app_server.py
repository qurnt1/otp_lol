"""Run the real FastAPI app in an isolated subprocess for Playwright."""

from __future__ import annotations

import argparse
import asyncio
import errno
import ipaddress
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--frontend-dir", required=True, type=Path)
    return parser.parse_args()


def _isolate_environment(state_dir: Path) -> tuple[Path, Path, Path]:
    profile_dir = state_dir / "profile"
    appdata_dir = profile_dir / "Roaming"
    localappdata_dir = profile_dir / "Local"
    temp_dir = state_dir / "temp"
    for path in (appdata_dir, localappdata_dir, temp_dir):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = str(appdata_dir)
    os.environ["LOCALAPPDATA"] = str(localappdata_dir)
    os.environ["TEMP"] = str(temp_dir)
    os.environ["TMP"] = str(temp_dir)
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(name, None)
    for name in ("OTP_LOL_LOG_LEVEL", "PYWEBVIEW_LOG", "OTP_LOL_ALLOW_DEV_ORIGINS"):
        os.environ.pop(name, None)
    tempfile.tempdir = None
    return appdata_dir, localappdata_dir, temp_dir


def _wait_for_health(url: str, timeout_s: float = 30.0) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with opener.open(f"{url}/api/health", timeout=1.0) as response:
                payload = json.loads(response.read())
                if response.status == 200 and payload.get("ok") is True:
                    return
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            last_error = error
        time.sleep(0.1)
    raise RuntimeError(f"The isolated FastAPI server did not become healthy: {last_error}")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def _capture_api_shutdown_state(api_server: Any, api_thread: threading.Thread) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"thread": {"name": api_thread.name, "ident": api_thread.ident}}
    try:
        server = getattr(api_server, "_server", None)
        state = getattr(server, "server_state", None)
        snapshot["uvicorn"] = {
            "available": state is not None,
            "connections": len(state.connections) if state is not None else 0,
            "tasks": len(state.tasks) if state is not None else 0,
            "server_id": id(server) if server is not None else None,
            "started": getattr(server, "started", None),
            "should_exit": getattr(server, "should_exit", None),
            "force_exit": getattr(server, "force_exit", None),
        }
        lifespan = getattr(server, "lifespan", None)
        if lifespan is not None:
            snapshot["uvicorn"]["lifespan"] = {
                "shutdown_event_set": lifespan.shutdown_event.is_set(),
                "shutdown_queue_size": lifespan.receive_queue.qsize(),
                "shutdown_failed": lifespan.shutdown_failed,
                "error_occurred": lifespan.error_occurred,
            }
        snapshot["uvicorn"]["servers"] = [
            {
                "serving": listener.is_serving(),
                "socket_count": len(listener.sockets or ()),
                "client_count": len(getattr(listener, "_clients", ()) or ()),
                "waiter_count": len(getattr(listener, "_waiters", ()) or ()),
                "clients": [
                    {
                        "transport": type(client).__name__,
                        "closing": client.is_closing(),
                        "peer": client.get_extra_info("peername"),
                    }
                    for client in (getattr(listener, "_clients", ()) or ())
                ],
            }
            for listener in (getattr(server, "servers", ()) or ())
        ]
    except Exception as error:  # noqa: BLE001 - diagnostic snapshots must not mask cleanup.
        snapshot["uvicorn_error"] = type(error).__name__

    try:
        context = api_server.application.state.context
        api_loop = getattr(context, "_async_loop", None)
        snapshot["api_loop"] = {
            "available": api_loop is not None,
            "running": api_loop.is_running() if api_loop is not None else False,
            "closed": api_loop.is_closed() if api_loop is not None else True,
        }
        if api_loop is not None and api_loop.is_running():
            async def capture_tasks() -> list[dict[str, Any]]:
                def describe_await_chain(coroutine: Any) -> list[dict[str, Any]]:
                    chain = []
                    current = coroutine
                    for _ in range(12):
                        frame = getattr(current, "cr_frame", None)
                        if frame is None:
                            frame = getattr(current, "gi_frame", None)
                        chain.append({
                            "coroutine": getattr(current, "__qualname__", type(current).__name__),
                            "frame": {
                                "file": Path(frame.f_code.co_filename).name,
                                "line": frame.f_lineno,
                                "function": frame.f_code.co_name,
                            } if frame is not None else None,
                        })
                        current = getattr(current, "cr_await", None) or getattr(current, "gi_yieldfrom", None)
                        if current is None:
                            break
                    return chain

                current = asyncio.current_task()
                return [
                    {
                        "name": task.get_name(),
                        "coroutine": getattr(task.get_coro(), "__qualname__", type(task.get_coro()).__name__),
                        "await_chain": describe_await_chain(task.get_coro()),
                        "stack": [
                            {"file": Path(frame.f_code.co_filename).name, "line": frame.f_lineno, "function": frame.f_code.co_name}
                            for frame in task.get_stack(limit=8)
                        ],
                    }
                    for task in asyncio.all_tasks(api_loop)
                    if task is not current
                ]

            future = asyncio.run_coroutine_threadsafe(capture_tasks(), api_loop)
            try:
                snapshot["api_loop"]["tasks"] = future.result(timeout=0.5)
            except TimeoutError:
                future.cancel()
                snapshot["api_loop"]["tasks_error"] = "snapshot_timeout"
    except Exception as error:  # noqa: BLE001 - diagnostic snapshots must not mask cleanup.
        snapshot["api_loop_error"] = type(error).__name__

    try:
        frame = sys._current_frames().get(api_thread.ident) if api_thread.ident is not None else None
        snapshot["thread"]["stack"] = [
            {"file": Path(item.filename).name, "line": item.lineno, "function": item.name}
            for item in traceback.extract_stack(frame, limit=30)
        ] if frame is not None else []
    except Exception as error:  # noqa: BLE001 - diagnostics must not mask cleanup.
        snapshot["thread"]["stack_error"] = type(error).__name__
    return snapshot


def _install_socket_egress_guard(lcu_port: int):
    """Block public sockets and allow only the API and fake LCU transports."""
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_socketpair = socket.socketpair
    socketpair_context = threading.local()
    guard_probe_context = threading.local()
    allowed_ports = {lcu_port}

    def loopback_host(host: Any) -> bool:
        if host is None:
            return True
        normalized = host.decode() if isinstance(host, bytes) else str(host)
        if normalized.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(normalized.split("%", 1)[0]).is_loopback
        except ValueError:
            return False

    def block(target: Any, port: Any, operation: str) -> None:
        if getattr(guard_probe_context, "active", False):
            return
        _emit(
            {
                "type": "socket-egress-blocked",
                "operation": operation,
                "host": str(target),
                "port": port,
            }
        )

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if not loopback_host(host):
            block(host, port, "dns")
            raise socket.gaierror(errno.EACCES, "E2E harness blocks non-loopback name resolution")
        return original_getaddrinfo(host, port, *args, **kwargs)

    def is_allowed_target(address: Any) -> tuple[bool, str, int | None]:
        if not isinstance(address, tuple) or len(address) < 2:
            return True, "local-socket", None
        host, port = address[0], address[1]
        is_loopback = loopback_host(host)
        try:
            target_port = int(port)
        except (TypeError, ValueError):
            target_port = None
        allowed = is_loopback and target_port in allowed_ports
        return allowed, str(host), target_port

    def guarded_connect(sock, address):
        if getattr(socketpair_context, "active", False):
            return original_connect(sock, address)
        allowed, host, port = is_allowed_target(address)
        if not allowed:
            block(host, port, "connect")
            raise OSError(errno.EACCES, "E2E harness blocks non-allowlisted socket targets")
        _emit({"type": "socket-connect-allowed", "host": host, "port": port})
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if getattr(socketpair_context, "active", False):
            return original_connect_ex(sock, address)
        allowed, host, port = is_allowed_target(address)
        if not allowed:
            block(host, port, "connect_ex")
            return errno.EACCES
        _emit({"type": "socket-connect-allowed", "host": host, "port": port})
        return original_connect_ex(sock, address)

    def guarded_sendto(sock, data, *args, **kwargs):
        if getattr(socketpair_context, "active", False):
            return original_sendto(sock, data, *args, **kwargs)
        address = args[-1] if args else kwargs.get("address")
        allowed, host, port = is_allowed_target(address)
        if not allowed:
            block(host, port, "sendto")
            raise OSError(errno.EACCES, "E2E harness blocks non-allowlisted socket targets")
        _emit({"type": "socket-sendto-allowed", "host": host, "port": port})
        return original_sendto(sock, data, *args, **kwargs)

    def guarded_socketpair(*args, **kwargs):
        socketpair_context.active = True
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            socketpair_context.active = False

    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.socket.sendto = guarded_sendto
    socket.socketpair = guarded_socketpair

    probe_target = ("203.0.113.1", 9)

    def expect_blocked(operation: str, attempt) -> None:
        guard_probe_context.active = True
        try:
            try:
                result = attempt()
            except OSError as error:
                if operation == "connect_ex" or error.errno != errno.EACCES:
                    raise
            else:
                if operation != "connect_ex" or result != errno.EACCES:
                    raise RuntimeError(f"The E2E socket guard did not block {operation}.")
        finally:
            guard_probe_context.active = False

    expect_blocked("connect", lambda: guarded_connect(None, probe_target))
    expect_blocked("connect_ex", lambda: guarded_connect_ex(None, probe_target))
    expect_blocked("sendto", lambda: guarded_sendto(None, b"e2e", probe_target))
    socket_guard_proof = ["connect", "connect_ex", "sendto"]
    _emit({"type": "socket-egress-guard-verified", "operations": socket_guard_proof})

    def allow_loopback_port(port: int) -> None:
        allowed_ports.add(port)

    return allow_loopback_port, socket_guard_proof


def _block_external_http(lcu_port: int) -> None:
    """Serve controlled external fixtures and fail all other egress before sockets."""
    import requests
    from ddragon_fixture import response_for_external_request
    from requests import Response

    original_request = requests.sessions.Session.request

    def request(session, method, url, **kwargs):
        parsed_url = urlsplit(str(url))
        if (
            parsed_url.scheme == "https"
            and parsed_url.hostname == "127.0.0.1"
            and parsed_url.port == lcu_port
        ):
            session.trust_env = False
            return original_request(session, method, url, **kwargs)
        fixture = response_for_external_request(method, str(url))
        if fixture is not None:
            _emit(
                {
                    "type": "network-request-fixture",
                    "method": method.upper(),
                    "scheme": parsed_url.scheme,
                    "host": parsed_url.hostname,
                    "port": parsed_url.port,
                    "path": parsed_url.path,
                    "status": fixture.status_code,
                }
            )
            return fixture
        prepared = requests.Request(method=method, url=url).prepare()
        response = Response()
        response.status_code = 503
        response.reason = "External network disabled by E2E harness"
        response.url = prepared.url
        response.request = prepared
        response.headers["Content-Type"] = "application/json"
        response._content = b'{"detail":"External network disabled by E2E harness"}'
        _emit(
            {
                "type": "network-request-blocked",
                "method": method.upper(),
                "scheme": parsed_url.scheme,
                "host": parsed_url.hostname,
                "port": parsed_url.port,
                "path": parsed_url.path,
            }
        )
        return response

    requests.sessions.Session.request = request


def _start_synthetic_league_process(port: int, token: str, state_dir: Path) -> subprocess.Popen:
    """Launch a temp executable that exits if its owning app process disappears."""
    fake_executable = state_dir / "LeagueClientUx.exe"
    shutil.copy2(sys.executable, fake_executable)
    app_pid = os.getpid()
    script = f"""import os, time
app_pid = {app_pid}
if os.name == "nt":
    import ctypes
    handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, app_pid)
    if handle:
        ctypes.windll.kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
        ctypes.windll.kernel32.CloseHandle(handle)
else:
    while True:
        try:
            os.kill(app_pid, 0)
        except OSError:
            break
        time.sleep(0.1)
"""
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    creation_flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [
            str(fake_executable),
            "-c",
            script,
            f"--app-port={port}",
            f"--remoting-auth-token={token}",
            f"--app-pid={app_pid}",
            "--install-directory=OTP-LOL-E2E",
        ],
        cwd=Path(sys.executable).parent,
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )
    return process


def _verify_process_discovery_and_isolate_driver(
    process: subprocess.Popen, expected_token: str, expected_port: int
) -> tuple[dict[str, Any], dict[str, int | None]]:
    """Prove OS discovery without connecting, then expose only this PID to the driver."""
    import lcu_driver.connector as connector_module
    import lcu_driver.utils as lcu_utils
    from lcu_driver.connection import Connection

    synthetic_pid = process.pid
    discovered = next(
        (
            candidate
            for candidate in connector_module._return_ux_process()
            if candidate.pid == synthetic_pid
        ),
        None,
    )
    if discovered is None:
        raise RuntimeError("The unfiltered production process scanner did not find the synthetic League process.")

    parsed_connection = Connection(None, discovered)
    if (
        parsed_connection._lcu_pid != synthetic_pid
        or parsed_connection._port != expected_port
        or parsed_connection._auth_key != expected_token
        or parsed_connection._pid != os.getpid()
        or parsed_connection._installation_path != "OTP-LOL-E2E"
    ):
        raise RuntimeError("The production LCU process argument parser returned unexpected synthetic arguments.")

    original_process_iter = lcu_utils.process_iter
    process_filter_state = {"pid": synthetic_pid}

    def isolated_process_iter(*args: Any, **kwargs: Any):
        allowed_pid = process_filter_state["pid"]
        if allowed_pid is None:
            return iter(())
        return (
            candidate
            for candidate in original_process_iter(*args, **kwargs)
            if candidate.pid == allowed_pid
        )

    lcu_utils.process_iter = isolated_process_iter
    proof = {
        "syntheticPid": synthetic_pid,
        "parsedPort": parsed_connection._port,
        "parsedAppPid": parsed_connection._pid,
        "parsedInstallDirectory": parsed_connection._installation_path,
        "networkOpened": False,
        "driverProcessFilter": "synthetic PID only",
        "filterSymbol": "lcu_driver.utils.process_iter",
    }
    _emit({"type": "process-discovery-verified", **proof})
    return proof, process_filter_state


def _verify_isolated_runtime_paths(
    appdata_dir: Path, localappdata_dir: Path, temp_dir: Path
) -> dict[str, Any]:
    from src.config.logging_config import LOG_FILE_PATH
    from src.config.paths import (
        ACCOUNT_CACHE_DIR,
        DDRAGON_CACHE_FILE,
        HISTORY_PATH,
        ICONS_CACHE_DIR,
        LCU_CACHE_DIR,
        LEGACY_PARAMETERS_JSON_PATH,
        LOCKFILE_PATH,
        PARAMETERS_JSON_PATH,
        PARAMETERS_PATH,
        RUNES_CACHE_DIR,
        SKINS_CACHE_DIR,
        SPELLS_CACHE_DIR,
        WEBVIEW_STORAGE_DIR,
    )

    app_paths = {
        "parameters": PARAMETERS_PATH,
        "legacyParameters": PARAMETERS_JSON_PATH,
        "history": HISTORY_PATH,
        "webview": WEBVIEW_STORAGE_DIR,
        "lcuCache": LCU_CACHE_DIR,
        "accountCache": ACCOUNT_CACHE_DIR,
        "logs": LOG_FILE_PATH,
    }
    if LEGACY_PARAMETERS_JSON_PATH is not None:
        app_paths["legacyMainParameters"] = LEGACY_PARAMETERS_JSON_PATH
    temp_paths = {
        "lockfile": LOCKFILE_PATH,
        "dataDragon": DDRAGON_CACHE_FILE,
        "icons": ICONS_CACHE_DIR,
        "spells": SPELLS_CACHE_DIR,
        "skins": SKINS_CACHE_DIR,
        "runes": RUNES_CACHE_DIR,
    }

    def ensure_within(paths: dict[str, str], root: Path, group: str) -> None:
        resolved_root = root.resolve()
        for name, path in paths.items():
            resolved_path = Path(path).resolve()
            if not resolved_path.is_relative_to(resolved_root):
                raise RuntimeError(f"Resolved {group} path '{name}' escaped the E2E profile.")

    ensure_within(app_paths, appdata_dir, "APPDATA")
    ensure_within(temp_paths, temp_dir, "TEMP")
    expected_environment = {
        "APPDATA": appdata_dir,
        "LOCALAPPDATA": localappdata_dir,
        "TEMP": temp_dir,
        "TMP": temp_dir,
    }
    for name, expected_path in expected_environment.items():
        actual_path = Path(os.environ[name]).resolve()
        if actual_path != expected_path.resolve():
            raise RuntimeError(f"{name} does not resolve to the isolated E2E profile.")
    resolved_roots = {
        "state": str(appdata_dir.parent.parent.resolve()),
        "appData": str(appdata_dir.resolve()),
        "localAppData": str(localappdata_dir.resolve()),
        "temp": str(temp_dir.resolve()),
    }
    return {
        "appDataPathNames": list(app_paths),
        "localAppDataIsolated": True,
        "tempPathNames": list(temp_paths),
        "resolvedRoots": resolved_roots,
        "resolvedPaths": {
            "appData": {
                name: str(Path(path).resolve()) for name, path in app_paths.items()
            },
            "temp": {
                name: str(Path(path).resolve()) for name, path in temp_paths.items()
            },
        },
    }


def _stop_synthetic_league_process(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if process.poll() is None:
        raise RuntimeError("The synthetic League process did not stop.")


async def _run(state_dir: Path, frontend_dir: Path) -> None:
    appdata_dir, localappdata_dir, temp_dir = _isolate_environment(state_dir)
    frontend_index = frontend_dir / "index.html"
    if not frontend_index.is_file():
        raise RuntimeError(f"Built frontend index is missing: {frontend_index}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    from ddragon_fixture import configure_external_state
    from fake_lcu import FakeLcuServer

    fake_lcu: FakeLcuServer | None = None
    league_process: subprocess.Popen | None = None
    api_server: Any = None
    process_filter_state: dict[str, int | None] | None = None
    try:
        fake_lcu = FakeLcuServer(state_dir)
        lcu_port = await fake_lcu.start()
        allow_loopback_port, socket_guard_proof = _install_socket_egress_guard(lcu_port)
        _block_external_http(lcu_port)
        league_process = _start_synthetic_league_process(
            lcu_port, fake_lcu.TOKEN, state_dir
        )
        _emit({"type": "synthetic-league-started", "pid": league_process.pid})
        process_discovery, process_filter_state = _verify_process_discovery_and_isolate_driver(
            league_process, fake_lcu.TOKEN, lcu_port
        )

        from src.api.app import ApplicationContext, create_app
        from src.desktop.server import EmbeddedApiServer

        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setStream(sys.stderr)
        path_isolation = _verify_isolated_runtime_paths(
            appdata_dir, localappdata_dir, temp_dir
        )
        context = ApplicationContext.from_system()
        original_event_observer = context.runtime.manager.diagnostic_event_callback

        def report_lcu_event(topic: str, event_type: str, payload: Any) -> None:
            if original_event_observer is not None:
                original_event_observer(topic, event_type, payload)
            _emit(
                {
                    "type": "lcu-websocket-event",
                    "topic": topic,
                    "eventType": event_type,
                    "data": payload,
                }
            )

        context.runtime.manager.diagnostic_event_callback = report_lcu_event
        app = create_app(context, frontend_dir=frontend_dir)
        api_server = EmbeddedApiServer(app, host="127.0.0.1", port=0)
        api_server.start()
        allow_loopback_port(api_server.port)
        base_url = f"http://127.0.0.1:{api_server.port}"
        await asyncio.to_thread(_wait_for_health, base_url)
        _emit(
            {
                "type": "ready",
                "url": base_url,
                "pid": os.getpid(),
                "stateDir": str(state_dir.resolve()),
                "appDataDir": str(appdata_dir.resolve()),
                "tempDir": str(temp_dir.resolve()),
                "lcuUrl": f"https://127.0.0.1:{lcu_port}",
                "syntheticLeaguePid": league_process.pid,
                "processDiscovery": process_discovery,
                "pathIsolation": path_isolation,
                "lcuDiscovery": "unfiltered production scan/argument parsing verified without connecting; Connector process_iter is then filtered to the synthetic PID",
                "networkBoundary": f"requests to https://127.0.0.1:{lcu_port} use the fake LCU; known third-party catalog requests receive local fixtures; all other requests return offline HTTP 503 without opening sockets",
                "socketBoundary": f"non-loopback DNS, connect, connect_ex and sendto blocked; local TCP restricted to ports {lcu_port} and {api_server.port}",
                "socketGuardProof": socket_guard_proof,
            }
        )

        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            try:
                command = json.loads(line)
            except json.JSONDecodeError:
                _emit({"type": "command-error", "error": "invalid_json"})
                continue
            if command.get("command") == "stop":
                _emit({"type": "stopping"})
                break
            if command.get("command") == "event":
                event_id = command.get("id")
                uri = command.get("uri")
                data = command.get("data")
                if not isinstance(uri, str) or not uri.startswith("/"):
                    _emit({"type": "command-error", "id": event_id, "error": "invalid_uri"})
                    continue
                await fake_lcu.emit(uri, data)
                _emit({"type": "event-sent", "id": event_id, "uri": uri})
                continue
            if command.get("command") == "state":
                state = command.get("state")
                if not isinstance(state, dict):
                    _emit({"type": "command-error", "id": command.get("id"), "error": "invalid_state"})
                    continue
                try:
                    fake_lcu.configure(state)
                except ValueError as error:
                    _emit({"type": "command-error", "id": command.get("id"), "error": str(error)})
                    continue
                _emit({"type": "state-updated", "id": command.get("id")})
                continue
            if command.get("command") == "lcu-state":
                _emit({"type": "lcu-state", "id": command.get("id"), "state": fake_lcu.snapshot()})
                continue
            if command.get("command") == "external-state":
                state = command.get("state")
                if not isinstance(state, dict):
                    _emit({"type": "command-error", "id": command.get("id"), "error": "invalid_state"})
                    continue
                try:
                    effective_state = configure_external_state(state)
                except ValueError as error:
                    _emit({"type": "command-error", "id": command.get("id"), "error": str(error)})
                    continue
                _emit({"type": "external-state-updated", "id": command.get("id"), "state": effective_state})
                continue
            if command.get("command") == "lcu-connection":
                event_id = command.get("id")
                online = command.get("online")
                if not isinstance(online, bool):
                    _emit({"type": "command-error", "id": event_id, "error": "online_must_be_boolean"})
                    continue
                if process_filter_state is None:
                    _emit({"type": "command-error", "id": event_id, "error": "driver_filter_not_ready"})
                    continue

                current_pid = process_filter_state["pid"]
                if online:
                    if league_process is not None and league_process.poll() is None:
                        _emit(
                            {
                                "type": "lcu-connection-state",
                                "id": event_id,
                                "online": True,
                                "pid": league_process.pid,
                                "alreadyInState": current_pid == league_process.pid,
                            }
                        )
                        continue
                    try:
                        league_process = _start_synthetic_league_process(
                            lcu_port, fake_lcu.TOKEN, state_dir
                        )
                    except Exception as error:  # noqa: BLE001 - report control-channel failures to the test.
                        _emit({"type": "command-error", "id": event_id, "error": f"synthetic_process_start:{error}"})
                        continue
                    process_filter_state["pid"] = league_process.pid
                    _emit({"type": "synthetic-league-started", "pid": league_process.pid})
                    _emit(
                        {
                            "type": "lcu-connection-state",
                            "id": event_id,
                            "online": True,
                            "pid": league_process.pid,
                            "alreadyInState": False,
                        }
                    )
                    continue

                if current_pid is None or league_process is None:
                    process_filter_state["pid"] = None
                    _emit(
                        {
                            "type": "lcu-connection-state",
                            "id": event_id,
                            "online": False,
                            "pid": None,
                            "alreadyInState": True,
                        }
                    )
                    continue

                process_filter_state["pid"] = None
                try:
                    closed_websockets = await fake_lcu.disconnect_websockets()
                except Exception as error:  # noqa: BLE001 - stop the client even when WS close reports an error.
                    closed_websockets = 0
                    disconnect_error = error
                else:
                    disconnect_error = None

                stopped_process = league_process
                try:
                    _stop_synthetic_league_process(stopped_process)
                except Exception as error:  # noqa: BLE001 - keep the PID filter aligned with a live process.
                    if stopped_process.poll() is None:
                        process_filter_state["pid"] = stopped_process.pid
                    _emit({"type": "command-error", "id": event_id, "error": f"synthetic_process_stop:{error}"})
                    continue

                league_process = None
                _emit(
                    {
                        "type": "synthetic-league-stopped",
                        "pid": stopped_process.pid,
                        "returnCode": stopped_process.returncode,
                    }
                )
                if disconnect_error is not None:
                    _emit({"type": "command-error", "id": event_id, "error": f"websocket_disconnect:{disconnect_error}"})
                    continue
                _emit(
                    {
                        "type": "lcu-connection-state",
                        "id": event_id,
                        "online": False,
                        "pid": None,
                        "closedWebsockets": closed_websockets,
                        "alreadyInState": False,
                    }
                )
                continue
            _emit({"type": "command-error", "error": "unknown_command"})
    finally:
        had_active_error = sys.exc_info()[0] is not None
        cleanup_errors: list[str] = []
        api_thread_still_alive_after_initial_join = False
        api_shutdown_diagnostics: dict[str, Any] | None = None
        cleanup_phase_seconds: dict[str, float] = {}
        cleanup_started = time.monotonic()
        if api_server is not None:
            api_thread = api_server._thread
            phase_started = time.monotonic()
            try:
                await asyncio.to_thread(api_server.stop)
            except Exception as error:  # noqa: BLE001 - attempt every remaining cleanup.
                cleanup_errors.append(f"api-server-stop:{type(error).__name__}:{error}")
            finally:
                cleanup_phase_seconds["api_server_stop"] = round(time.monotonic() - phase_started, 3)
            if api_thread is not None and api_thread.is_alive():
                phase_started = time.monotonic()
                await asyncio.to_thread(api_thread.join, timeout=5)
                cleanup_phase_seconds["api_thread_join_initial"] = round(
                    time.monotonic() - phase_started, 3
                )
                api_thread_still_alive_after_initial_join = api_thread.is_alive()
        phase_started = time.monotonic()
        try:
            _stop_synthetic_league_process(league_process)
        except Exception as error:  # noqa: BLE001 - attempt every remaining cleanup.
            cleanup_errors.append(f"synthetic-league-stop:{type(error).__name__}:{error}")
        finally:
            cleanup_phase_seconds["synthetic_league_stop"] = round(time.monotonic() - phase_started, 3)
        if league_process is not None:
            if league_process.poll() is not None:
                _emit({"type": "synthetic-league-stopped", "pid": league_process.pid, "returnCode": league_process.returncode})
            else:
                _emit({"type": "cleanup-warning", "resource": "synthetic-league-process-still-alive", "pid": league_process.pid})
        if fake_lcu is not None:
            phase_started = time.monotonic()
            try:
                await fake_lcu.stop()
            except Exception as error:  # noqa: BLE001 - attempt every remaining cleanup.
                cleanup_errors.append(f"fake-lcu-stop:{type(error).__name__}:{error}")
            finally:
                cleanup_phase_seconds["fake_lcu_stop"] = round(time.monotonic() - phase_started, 3)
        if api_thread_still_alive_after_initial_join:
            phase_started = time.monotonic()
            await asyncio.to_thread(api_thread.join, timeout=5)
            cleanup_phase_seconds["api_thread_join_final"] = round(time.monotonic() - phase_started, 3)
            if api_thread.is_alive():
                cleanup_errors.append("api-server-thread-still-alive")
                api_shutdown_diagnostics = _capture_api_shutdown_state(api_server, api_thread)
        cleanup_phase_seconds["total_before_report"] = round(time.monotonic() - cleanup_started, 3)
        for error in cleanup_errors:
            warning: dict[str, Any] = {"type": "cleanup-warning", "resource": error}
            if error == "api-server-thread-still-alive":
                warning["phase_seconds"] = cleanup_phase_seconds
                warning["api_shutdown"] = api_shutdown_diagnostics
            _emit(warning)
        if cleanup_errors and not had_active_error:
            raise RuntimeError("E2E resource cleanup failed: " + "; ".join(cleanup_errors))


async def main() -> int:
    args = _parse_args()
    args.state_dir = args.state_dir.resolve()
    args.frontend_dir = args.frontend_dir.resolve()
    try:
        await _run(args.state_dir, args.frontend_dir)
    except Exception as error:
        _emit({"type": "startup-error", "error": f"{type(error).__name__}: {error}"})
        logger.exception("Full-stack E2E server failed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
