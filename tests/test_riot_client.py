import json
from types import SimpleNamespace
from unittest.mock import Mock

import src.desktop.application as application_module
from src.services.riot_client import find_riot_client


def test_find_riot_client_reads_riot_install_manifest(tmp_path, monkeypatch):
    program_data = tmp_path / "ProgramData"
    install_root = tmp_path / "Riot Client"
    executable = install_root / "RiotClientServices.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    manifest = program_data / "Riot Games" / "RiotClientInstalls.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"associated_client": str(executable)}), encoding="utf-8")

    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)

    assert find_riot_client() == executable


def test_open_riot_client_uses_league_launch_arguments(tmp_path, monkeypatch):
    executable = tmp_path / "RiotClientServices.exe"
    executable.write_bytes(b"")
    calls = []

    class FakeProcess:
        @staticmethod
        def startDetached(program, arguments):
            calls.append((program, arguments))
            return (True, 42)

    monkeypatch.setattr(application_module, "QProcess", FakeProcess)
    monkeypatch.setattr(application_module, "find_riot_client", lambda: executable)
    app = SimpleNamespace(main_window=Mock())

    application_module.DesktopApplication.open_riot_client(app)

    assert calls == [
        (
            str(executable),
            ["--launch-product=league_of_legends", "--launch-patchline=live"],
        )
    ]
    app.main_window.enqueue_toast.assert_not_called()


def test_open_riot_client_reports_detached_launch_failure(tmp_path, monkeypatch):
    executable = tmp_path / "RiotClientServices.exe"
    executable.write_bytes(b"")

    class FakeProcess:
        @staticmethod
        def startDetached(_program, _arguments):
            return (False, 0)

    monkeypatch.setattr(application_module, "QProcess", FakeProcess)
    monkeypatch.setattr(application_module, "find_riot_client", lambda: executable)
    app = SimpleNamespace(main_window=Mock())

    application_module.DesktopApplication.open_riot_client(app)

    app.main_window.enqueue_toast.assert_called_once_with("Impossible de lancer Riot Client.", 3200)
