"""
FILE NAME: src/services/urls.py
GLOBAL PURPOSE:
- Build external player and in-game statistics URLs from a Riot ID and region.
- Keep provider-specific URL patterns centralized in one module.
- Normalize Riot IDs before they are sent to third-party websites.

KEY FUNCTIONS:
- is_valid_riot_id: Validate the basic `GameName#Tag` structure.
- build_stats_site_url: Build a profile page URL for the chosen provider.
- build_hotkey_site_url: Build a live-game URL for the chosen provider.
- _normalize_riot_id_for_url: Convert Riot IDs into the provider-friendly URL format.

AUDIENCE & LOGIC:
Why:
This module exists so third-party URL rules stay out of UI code and can be changed in one place.
For whom:
Developers maintaining external website integration and Riot ID normalization.

DEPENDENCIES:
Used by:
- src.desktop.webview and tests.
Uses:
- Standard library: urllib.parse
"""

import urllib.parse

from ..config.constants import REGION_LIST

ALLOWED_EXTERNAL_HOSTS = frozenset({
    "github.com",
    "op.gg",
    "porofessor.gg",
    "deeplol.gg",
    "www.deeplol.gg",
    "dpm.lol",
    "leagueofgraphs.com",
    "www.leagueofgraphs.com",
})

STATS_PROVIDERS = {
    "opgg": lambda region, riot_id: build_opgg_url(region, riot_id),
    "deeplol": lambda region, riot_id: build_deeplol_url(region, riot_id),
    "dpm": lambda region, riot_id: build_dpm_url(region, riot_id),
    "leagueofgraphs": lambda region, riot_id: build_leagueofgraphs_url(region, riot_id),
}
STATS_PROVIDER_HOME_URLS = {
    "opgg": "https://op.gg/",
    "deeplol": "https://www.deeplol.gg/",
    "dpm": "https://dpm.lol/",
    "leagueofgraphs": "https://www.leagueofgraphs.com/",
}
STATS_FRAME_ORIGINS = {
    "deeplol": "https://www.deeplol.gg",
}
LIVE_FRAME_ORIGINS: dict[str, str] = {}

HOTKEY_PROVIDERS = {
    "porofessor": (lambda region, riot_id: build_porofessor_url(region, riot_id), "https://porofessor.gg/"),
    "deeplol": (lambda region, riot_id: build_deeplol_url(region, riot_id, ingame=True), "https://www.deeplol.gg/"),
    "dpm": (lambda region, riot_id: build_dpm_url(region, riot_id, ingame=True), "https://dpm.lol/"),
    "opgg": (lambda region, riot_id: build_opgg_url(region, riot_id, ingame=True), "https://op.gg/"),
}


def is_allowed_external_url(url: str) -> bool:
    """Allow only HTTPS links to providers intentionally exposed by the app."""
    try:
        parsed = urllib.parse.urlparse(str(url or "").strip())
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return (
        parsed.scheme == "https"
        and host in ALLOWED_EXTERNAL_HOSTS
        and not parsed.username
        and not parsed.password
        and port in (None, 443)
    )


def is_valid_riot_id(riot_id: str) -> bool:
    """Return True when the Riot ID looks like GameName#TAG."""
    if not riot_id:
        return False
    value = str(riot_id).strip()
    if len(value) > 64 or value.count("#") != 1:
        return False
    left, right = value.split("#", 1)
    return bool(left.strip() and right.strip())


def build_opgg_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    """Build the OP.GG URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    base = f"https://op.gg/fr/lol/summoners/{region}/{urllib.parse.quote(url_name, safe='')}"
    return f"{base}/ingame" if ingame else base


def build_porofessor_url(region: str, riot_id: str) -> str:
    """Build the Porofessor in-game URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    return f"https://porofessor.gg/fr/live/{region}/{urllib.parse.quote(url_name, safe='')}/ranked-only"


def build_leagueofgraphs_url(region: str, riot_id: str) -> str:
    """Build the League of Graphs URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    return f"https://www.leagueofgraphs.com/fr/summoner/{region}/{urllib.parse.quote(url_name, safe='')}"


def build_deeplol_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    """Build the DeepLOL URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    base = f"https://www.deeplol.gg/summoner/{region}/{urllib.parse.quote(url_name, safe='')}"
    return f"{base}/ingame" if ingame else base


def build_dpm_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    """Build the DPM.LOL URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    base = f"https://dpm.lol/{urllib.parse.quote(url_name, safe='')}"
    return f"{base}/live" if ingame else f"{base}/"


def build_stats_site_url(site: str, region: str, riot_id: str) -> str:
    """Build the configured profile stats URL."""
    normalized_site = (site or "opgg").lower().strip()
    builder = STATS_PROVIDERS.get(normalized_site, STATS_PROVIDERS["opgg"])
    return builder(region, riot_id)


def build_stats_provider_home_url(site: str) -> str:
    """Return the fixed HTTPS homepage for a supported statistics provider."""
    normalized_site = (site or "opgg").lower().strip()
    return STATS_PROVIDER_HOME_URLS.get(normalized_site, STATS_PROVIDER_HOME_URLS["opgg"])


def build_hotkey_site_url(site: str, region: str, riot_id: str) -> str | None:
    """Build a profile or safe provider-home URL for the configured stats hotkey."""
    normalized_site = (site or "porofessor").lower().strip()
    provider = HOTKEY_PROVIDERS.get(normalized_site)
    if provider is None:
        return None
    builder, homepage = provider
    normalized_region = str(region or "").strip().lower()
    if is_valid_riot_id(riot_id) and normalized_region in REGION_LIST:
        return builder(normalized_region, riot_id)
    return homepage


def build_hotkey_provider_home_url(site: str) -> str:
    """Return the fixed HTTPS homepage for a supported live-statistics provider."""
    normalized_site = (site or "porofessor").lower().strip()
    provider = HOTKEY_PROVIDERS.get(normalized_site)
    return provider[1] if provider else HOTKEY_PROVIDERS["porofessor"][1]


def _normalize_riot_id_for_url(riot_id: str) -> str:
    """Convert GameName#Tag into GameName-Tag for external URLs."""
    riot_id = str(riot_id or "").strip()
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            return f"{left}-{right}"
    return riot_id
