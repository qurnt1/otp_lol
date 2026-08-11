"""Locate the installed Riot Client launcher on Windows."""

import json
import os
from pathlib import Path
from typing import Iterable


def _candidate_install_files() -> Iterable[Path]:
    for root in (
        os.environ.get("PROGRAMDATA"),
        os.environ.get("LOCALAPPDATA"),
    ):
        if root:
            yield Path(root) / "Riot Games" / "RiotClientInstalls.json"


def find_riot_client() -> Path | None:
    """Return the Riot Client executable from Riot's install manifest or defaults."""
    for manifest_path in _candidate_install_files():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for value in payload.values() if isinstance(payload, dict) else ():
            if isinstance(value, str):
                candidate = Path(value)
                if candidate.name.lower() == "riotclientservices.exe" and candidate.is_file():
                    return candidate

    fallback_roots = (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
        "C:\\Riot Games",
    )
    for root in fallback_roots:
        if not root:
            continue
        candidate = Path(root) / "Riot Games" / "Riot Client" / "RiotClientServices.exe"
        if candidate.is_file():
            return candidate
        candidate = Path(root) / "Riot Client" / "RiotClientServices.exe"
        if candidate.is_file():
            return candidate
    return None
