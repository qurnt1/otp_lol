"""Safety guards loaded only by the duplicate-launcher E2E subprocess."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import sys
import webbrowser
from pathlib import Path

import psutil


def _no_process_discovery(*_args, **_kwargs):
    return iter(())


psutil.process_iter = _no_process_discovery

import lcu_driver.utils as lcu_utils
from lcu_driver.connection import Connection

lcu_utils.process_iter = _no_process_discovery


async def _block_lcu_connection(_connection):
    raise RuntimeError("Duplicate-launcher E2E process cannot access League.")


Connection.init = _block_lcu_connection


def _is_loopback(host):
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


_getaddrinfo = socket.getaddrinfo
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_sendto = socket.socket.sendto


def _guard_getaddrinfo(host, *args, **kwargs):
    if not _is_loopback(host):
        raise socket.gaierror(socket.EAI_FAIL, "External DNS is blocked by the native E2E harness.")
    return _getaddrinfo(host, *args, **kwargs)


def _guard_connect(connection, address):
    if connection.family in {socket.AF_INET, socket.AF_INET6} and not _is_loopback(address[0]):
        raise OSError("External sockets are blocked by the native E2E harness.")
    return _connect(connection, address)


def _guard_connect_ex(connection, address):
    if connection.family in {socket.AF_INET, socket.AF_INET6} and not _is_loopback(address[0]):
        return getattr(socket, "EHOSTUNREACH", 10065)
    return _connect_ex(connection, address)


def _guard_sendto(connection, data, *args):
    address = args[-1] if args else None
    if (
        connection.family in {socket.AF_INET, socket.AF_INET6}
        and isinstance(address, tuple)
        and address
        and not _is_loopback(address[0])
    ):
        raise OSError("External sockets are blocked by the native E2E harness.")
    return _sendto(connection, data, *args)


socket.getaddrinfo = _guard_getaddrinfo
socket.socket.connect = _guard_connect
socket.socket.connect_ex = _guard_connect_ex
socket.socket.sendto = _guard_sendto


def _block_shell(*_args, **_kwargs):
    raise OSError("Shell actions are blocked by the native E2E harness.")


webbrowser.open = _block_shell
if hasattr(os, "startfile"):
    os.startfile = _block_shell

evidence_path = os.environ.get("OTP_LOL_NATIVE_E2E_GUARD_EVIDENCE")
if evidence_path:
    Path(evidence_path).write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "processDiscoveryFiltered": True,
                "lcuConnectionGuarded": True,
                "pythonNetworkGuarded": True,
                "shellActionsSuppressed": True,
                "loadedBeforeLauncher": "launcher_web.py" not in sys.modules,
            }
        ),
        encoding="utf-8",
    )
