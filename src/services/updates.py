"""Update checking helpers."""

import base64
import logging
import re
from typing import Any, Dict, Optional

import requests
from packaging.version import InvalidVersion, Version

from src.config import CURRENT_VERSION, GITHUB_REPO_API


def fetch_remote_readme() -> Optional[str]:
    """Return the remote README text from GitHub, or None on failure."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MainLoL-UpdateChecker",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    resp = requests.get(f"{GITHUB_REPO_API}/readme", headers=headers, timeout=10)

    if resp.status_code == 200:
        data = resp.json()
        content = data.get("content", "")
        encoding = data.get("encoding", "")
        if encoding == "base64" and content:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        logging.warning("[Update] README content missing or unsupported encoding")
        return None

    if resp.status_code == 404:
        logging.warning("[Update] README not found in the repository")
    else:
        logging.warning(f"[Update] API response: {resp.status_code}")
    return None


def check_for_updates() -> Optional[Dict[str, str]]:
    """Return remote update info when the README advertises a newer version."""
    try:
        logging.info("[Update] Checking README version...")
        readme_text = fetch_remote_readme()
        if not readme_text:
            return None

        remote_version = extract_version_from_readme(readme_text)
        logging.info(f"[Update] Remote version: {remote_version}, local: {CURRENT_VERSION}")

        if remote_version and is_newer_version(remote_version, CURRENT_VERSION):
            return {
                "version": remote_version,
                "highlights": extract_highlights_section(readme_text, remote_version),
            }

    except requests.RequestException as e:
        logging.warning(f"[Update] Network error: {e}")
    except Exception as e:
        logging.error(f"[Update] Unexpected error: {e}")

    return None


def extract_version_from_readme(readme_text: str) -> Optional[str]:
    """Extract version from a shields.io badge or Version Highlights header."""
    if not readme_text:
        return None

    patterns = [
        r"shields\.io/badge/version-([0-9]+(?:\.[0-9]+)*)-",
        r"shields\.io/badge/version-v?([0-9]+(?:\.[0-9]+)*)-",
        r"(?im)^##\s+Version\s+([0-9]+(?:\.[0-9]+)*)\s+Highlights\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, readme_text, re.IGNORECASE)
        if match:
            return normalize_version(match.group(1))

    logging.warning("[Update] No version marker found in README")
    return None


def extract_highlights_section(readme_text: str, version: str) -> str:
    """Return the markdown body of the matching Version Highlights section."""
    normalized_version = normalize_version(version)
    if not readme_text or not normalized_version:
        return ""

    pattern = re.compile(
        rf"(?ims)^##\s+Version\s+{re.escape(normalized_version)}\s+Highlights\s*$\n(?P<body>.*?)(?=^\s*##\s+\S|\Z)"
    )
    match = pattern.search(readme_text)
    if not match:
        logging.warning("[Update] No highlights section found for version %s", normalized_version)
        return ""
    return match.group("body").strip()


def format_highlights_for_popup(markdown_text: str) -> str:
    """Format a README highlights block into readable plain text for the popup."""
    if not markdown_text.strip():
        return "Release notes are not available for this version yet."

    lines: list[str] = []
    previous_blank = False
    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if lines and not previous_blank:
                lines.append("")
            previous_blank = True
            continue

        cleaned = stripped.replace("`", "")
        if cleaned.startswith("- "):
            cleaned = f"• {cleaned[2:]}"
        lines.append(cleaned)
        previous_blank = False

    return "\n".join(lines).strip() or "Release notes are not available for this version yet."


def normalize_version(version: str) -> str:
    """Normalize a version like v10.0 to 10.0."""
    return (version or "").strip().lstrip("vV")


def parse_version(version: str) -> Version:
    """Parse a comparable semantic version object."""
    normalized = normalize_version(version)
    if not normalized:
        raise InvalidVersion("Empty version")
    return Version(normalized)


def is_newer_version(remote_version: str, current_version: str) -> bool:
    """Return True only if the remote version is strictly newer."""
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except InvalidVersion as e:
        logging.warning(f"[Update] Invalid version ignored: {e}")
        return False
