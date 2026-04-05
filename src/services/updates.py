"""Update checking helpers."""

import logging
from typing import Optional

import requests
from packaging.version import InvalidVersion, Version

from src.config import CURRENT_VERSION, GITHUB_RELEASES_API


def check_for_updates() -> Optional[str]:
    """Check GitHub Releases for a newer version."""
    try:
        logging.info("[Update] Vérification via GitHub Releases API...")

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MainLoL-UpdateChecker",
        }

        resp = requests.get(GITHUB_RELEASES_API, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            tag_name = data.get("tag_name", "")
            remote_version = normalize_version(tag_name)

            logging.info(f"[Update] Version en ligne: {remote_version}, locale: {CURRENT_VERSION}")

            if remote_version and is_newer_version(remote_version, CURRENT_VERSION):
                return remote_version

        elif resp.status_code == 404:
            logging.warning("[Update] Aucune release trouvée sur le repo")
        else:
            logging.warning(f"[Update] Réponse API: {resp.status_code}")

    except requests.RequestException as e:
        logging.warning(f"[Update] Erreur réseau: {e}")
    except Exception as e:
        logging.error(f"[Update] Erreur inattendue: {e}")

    return None


def normalize_version(version: str) -> str:
    """Normalize a version like v6.1 to 6.1."""
    return (version or "").strip().lstrip("vV")


def parse_version(version: str) -> Version:
    """Parse a comparable semantic version object."""
    normalized = normalize_version(version)
    if not normalized:
        raise InvalidVersion("Version vide")
    return Version(normalized)


def is_newer_version(remote_version: str, current_version: str) -> bool:
    """Return True only if the remote version is strictly newer."""
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except InvalidVersion as e:
        logging.warning(f"[Update] Version invalide ignorée: {e}")
        return False
