"""Canonical provider metadata and URL builders shared by app layers."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    id: str
    label: str
    logo_filename: str
    homepage_url: str
    allowed_hosts: tuple[str, ...]
    profile_builder: Callable[[str, str], str] | None = None
    live_builder: Callable[[str, str], str] | None = None
    profile_order: int | None = None
    live_order: int | None = None


def _normalize_riot_id_for_url(riot_id: str) -> str:
    riot_id = str(riot_id or "").strip()
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        left, right = left.strip(), right.strip()
        if left and right:
            return f"{left}-{right}"
    return riot_id


def build_opgg_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    url_name = urllib.parse.quote(_normalize_riot_id_for_url(riot_id), safe="")
    base = f"https://op.gg/fr/lol/summoners/{region}/{url_name}"
    return f"{base}/ingame" if ingame else base


def build_porofessor_url(region: str, riot_id: str) -> str:
    url_name = urllib.parse.quote(_normalize_riot_id_for_url(riot_id), safe="")
    return f"https://porofessor.gg/fr/live/{region}/{url_name}/ranked-only"


def build_leagueofgraphs_url(region: str, riot_id: str) -> str:
    url_name = urllib.parse.quote(_normalize_riot_id_for_url(riot_id), safe="")
    return f"https://www.leagueofgraphs.com/fr/summoner/{region}/{url_name}"


def build_deeplol_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    url_name = urllib.parse.quote(_normalize_riot_id_for_url(riot_id), safe="")
    base = f"https://www.deeplol.gg/summoner/{region}/{url_name}"
    return f"{base}/ingame" if ingame else base


def build_dpm_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    url_name = urllib.parse.quote(_normalize_riot_id_for_url(riot_id), safe="")
    base = f"https://dpm.lol/{url_name}"
    return f"{base}/live" if ingame else f"{base}/"


PROVIDER_REGISTRY = {
    "opgg": ProviderDefinition(
        "opgg", "OP.GG", "opgg.png", "https://op.gg/", ("op.gg",),
        profile_builder=build_opgg_url,
        live_builder=lambda region, riot_id: build_opgg_url(region, riot_id, ingame=True),
        profile_order=0,
        live_order=3,
    ),
    "deeplol": ProviderDefinition(
        "deeplol", "DeepLOL", "deeplol.png", "https://www.deeplol.gg/",
        ("deeplol.gg", "www.deeplol.gg"),
        profile_builder=build_deeplol_url,
        live_builder=lambda region, riot_id: build_deeplol_url(region, riot_id, ingame=True),
        profile_order=1,
        live_order=1,
    ),
    "dpm": ProviderDefinition(
        "dpm", "DPM.LOL", "dpm-lol.png", "https://dpm.lol/", ("dpm.lol",),
        profile_builder=build_dpm_url,
        live_builder=lambda region, riot_id: build_dpm_url(region, riot_id, ingame=True),
        profile_order=2,
        live_order=2,
    ),
    "leagueofgraphs": ProviderDefinition(
        "leagueofgraphs", "League of Graphs", "leagueofgraphs.png",
        "https://www.leagueofgraphs.com/", ("leagueofgraphs.com", "www.leagueofgraphs.com"),
        profile_builder=build_leagueofgraphs_url,
        profile_order=3,
    ),
    "porofessor": ProviderDefinition(
        "porofessor", "Porofessor", "porofessor.png", "https://porofessor.gg/", ("porofessor.gg",),
        live_builder=build_porofessor_url,
        live_order=0,
    ),
}

STATS_PROVIDER_IDS = tuple(
    provider.id
    for provider in sorted(
        (provider for provider in PROVIDER_REGISTRY.values() if provider.profile_builder),
        key=lambda provider: provider.profile_order,
    )
)
LIVE_PROVIDER_IDS = tuple(
    provider.id
    for provider in sorted(
        (provider for provider in PROVIDER_REGISTRY.values() if provider.live_builder),
        key=lambda provider: provider.live_order,
    )
)
STATS_PROVIDERS = {provider_id: PROVIDER_REGISTRY[provider_id].profile_builder for provider_id in STATS_PROVIDER_IDS}
STATS_PROVIDER_HOME_URLS = {
    provider_id: PROVIDER_REGISTRY[provider_id].homepage_url for provider_id in STATS_PROVIDER_IDS
}
HOTKEY_PROVIDERS = {
    provider_id: (PROVIDER_REGISTRY[provider_id].live_builder, PROVIDER_REGISTRY[provider_id].homepage_url)
    for provider_id in LIVE_PROVIDER_IDS
}
PROVIDER_LOGO_FILES = {provider.id: provider.logo_filename for provider in PROVIDER_REGISTRY.values()}
ALLOWED_EXTERNAL_HOSTS = frozenset(
    host for provider in PROVIDER_REGISTRY.values() for host in provider.allowed_hosts
)
STATS_SITE_LABELS = {provider_id: PROVIDER_REGISTRY[provider_id].label for provider_id in STATS_PROVIDER_IDS}
STATS_SITE_ORDER = list(STATS_PROVIDER_IDS)
HOTKEY_SITE_LABELS = {provider_id: PROVIDER_REGISTRY[provider_id].label for provider_id in LIVE_PROVIDER_IDS}
HOTKEY_SITE_ORDER = list(LIVE_PROVIDER_IDS)
