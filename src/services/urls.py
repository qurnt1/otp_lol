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
from ..domain.providers import (
    ALLOWED_EXTERNAL_HOSTS,
    HOTKEY_PROVIDERS,
    LIVE_FRAME_ORIGINS,
    LIVE_PROVIDER_IDS,
    PROVIDER_LOGO_FILES,
    PROVIDER_REGISTRY,
    STATS_FRAME_ORIGINS,
    STATS_PROVIDER_HOME_URLS,
    STATS_PROVIDER_IDS,
    STATS_PROVIDERS,
    ProviderDefinition,
    _normalize_riot_id_for_url,
    build_deeplol_url,
    build_dpm_url,
    build_leagueofgraphs_url,
    build_opgg_url,
    build_porofessor_url,
)


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


def get_provider(provider_id: str) -> ProviderDefinition | None:
    return PROVIDER_REGISTRY.get(str(provider_id or "").strip().lower())


def build_provider_url(provider_id: str, kind: str, region: str, riot_id: str) -> str | None:
    provider = get_provider(provider_id)
    normalized_region = str(region or "").strip().lower()
    if provider is None or normalized_region not in REGION_LIST or not is_valid_riot_id(riot_id):
        return None
    builder = provider.profile_builder if kind == "stats" else provider.live_builder if kind == "live" else None
    return builder(normalized_region, riot_id) if builder else None


def resolve_provider_account(params: dict, runtime) -> tuple[str, str]:
    if not params.get("summoner_name_auto_detect", True):
        return (
            str(params.get("manual_summoner_name") or "").strip(),
            str(params.get("manual_region") or "").strip().lower(),
        )
    snapshot = runtime.snapshot(params)
    if not snapshot.connected:
        return "", ""
    return str(snapshot.riot_id or "").strip(), str(snapshot.region or "").strip().lower()


def is_allowed_provider_url(provider_id: str, url: str) -> bool:
    provider = get_provider(provider_id)
    if provider is None or not is_allowed_external_url(url):
        return False
    host = urllib.parse.urlparse(url).hostname
    return bool(host and host.lower().rstrip(".") in provider.allowed_hosts)


def provider_catalog_options(kind: str) -> list[dict[str, str]]:
    provider_ids = STATS_PROVIDER_IDS if kind == "stats" else LIVE_PROVIDER_IDS if kind == "live" else ()
    return [
        {
            "id": provider_id,
            "label": PROVIDER_REGISTRY[provider_id].label,
            "logo_url": f"/api/assets/providers/{provider_id}",
        }
        for provider_id in provider_ids
    ]
