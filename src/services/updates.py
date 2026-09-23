"""
FILE NAME: src/services/updates.py
GLOBAL PURPOSE:
- Check whether the latest GitHub Release is newer than the running application.
- Expose release notes and download metadata to the update popup.
- Keep legacy README parsing helpers available for compatibility and tests.

KEY FUNCTIONS:
- fetch_latest_release: Download the latest GitHub Release metadata.
- check_for_updates: Return update metadata when the remote version is newer.
- extract_version_from_readme: Find the advertised version inside README content.
- format_highlights_for_popup: Convert markdown highlights into readable plain text.

AUDIENCE & LOGIC:
Why:
This module exists so update detection stays consistent and independent from UI presentation code.
For whom:
Developers maintaining release detection, semantic version comparison, and update notes formatting.

DEPENDENCIES:
Used by:
- launcher_web.py and tests.
Uses:
- Standard library: base64, logging, re, typing
- Third-party libraries: packaging, requests
- Local modules: src.config
"""

import base64
import logging
import re
from typing import Dict, Optional

import requests
from packaging.version import InvalidVersion, Version

from src.config import CURRENT_VERSION, GITHUB_REPO_API, GITHUB_REPO_URL


_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "OTP-LOL-UpdateChecker",
    "X-GitHub-Api-Version": "2022-11-28",
}
RELEASE_EXECUTABLE_NAME = "OTP-LOL-Setup.exe"
RELEASE_CHECKSUM_NAME = "OTP-LOL-Setup.exe.sha256"


def fetch_remote_readme() -> Optional[str]:
    """Return the remote README text from GitHub, or None on failure."""
    resp = requests.get(f"{GITHUB_REPO_API}/readme", headers=_GITHUB_HEADERS, timeout=10)

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
        logging.warning("[Update] API response: %s", resp.status_code)
    return None


def fetch_latest_release() -> Optional[Dict[str, object]]:
    """Return the latest GitHub Release payload, or None when unavailable."""
    response = requests.get(
        f"{GITHUB_REPO_API}/releases/latest",
        headers=_GITHUB_HEADERS,
        timeout=10,
    )
    if response.status_code != 200:
        logging.warning("[Update] Latest release API response: %s", response.status_code)
        return None
    payload = response.json()
    if not isinstance(payload, dict):
        logging.warning("[Update] Latest release payload is not an object")
        return None
    return payload


def _extract_release_version(release: Dict[str, object]) -> Optional[str]:
    """Extract a valid semantic version from a release tag, then its name."""
    for value in (release.get("tag_name"), release.get("name")):
        match = re.search(r"(?<!\d)v?(\d+(?:\.\d+){1,2})(?!\d)", str(value or ""), re.IGNORECASE)
        if not match:
            continue
        version = normalize_version(match.group(1))
        try:
            parse_version(version)
        except InvalidVersion:
            continue
        return version
    return None


def check_for_updates() -> Optional[Dict[str, str]]:
    """Return release metadata when GitHub advertises a newer version."""
    try:
        logging.info("[Update] Checking latest GitHub Release...")
        release = fetch_latest_release()
        if not release:
            return None

        remote_version = _extract_release_version(release)
        logging.info("[Update] Remote version: %s, local: %s", remote_version, CURRENT_VERSION)

        if remote_version and is_newer_version(remote_version, CURRENT_VERSION):
            assets = release.get("assets")
            executable = next(
                (
                    asset
                    for asset in assets
                    if isinstance(asset, dict) and asset.get("name") == RELEASE_EXECUTABLE_NAME
                ),
                {},
            ) if isinstance(assets, list) else {}
            checksum = next(
                (
                    asset
                    for asset in assets
                    if isinstance(asset, dict) and asset.get("name") == RELEASE_CHECKSUM_NAME
                ),
                {},
            ) if isinstance(assets, list) else {}
            asset_url = str(executable.get("browser_download_url") or "")
            checksum_url = str(checksum.get("browser_download_url") or "")
            if not asset_url or not checksum_url:
                logging.warning("[Update] Release is missing the executable or SHA-256 asset")
                return None
            return {
                "version": remote_version,
                "highlights": str(release.get("body") or "").strip(),
                "release_url": str(release.get("html_url") or f"{GITHUB_REPO_URL}/releases/latest"),
                "asset_name": RELEASE_EXECUTABLE_NAME,
                "asset_url": asset_url,
                "checksum_name": RELEASE_CHECKSUM_NAME,
                "checksum_url": checksum_url,
            }

    except requests.RequestException as e:
        logging.warning("[Update] Network error: %s", e)
    except Exception as e:
        logging.error("[Update] Unexpected error: %s", e)

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
        logging.warning("[Update] Invalid version ignored: %s", e)
        return False
