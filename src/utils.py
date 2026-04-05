"""Backward-compatible utility facade."""

from .services import updates as _updates
from .services.platform import enable_high_dpi
from .services.single_instance import check_single_instance, remove_lockfile
from .services.updates import check_for_updates, normalize_version, parse_version, is_newer_version
from .services.urls import (
    build_deeplol_url,
    build_hotkey_site_url,
    build_ingame_stats_url,
    build_leagueofgraphs_url,
    build_opgg_url,
    build_player_stats_url,
    build_porofessor_url,
    build_stats_site_url,
    is_valid_riot_id,
)

requests = _updates.requests

__all__ = [
    "enable_high_dpi",
    "check_single_instance",
    "remove_lockfile",
    "check_for_updates",
    "normalize_version",
    "parse_version",
    "is_newer_version",
    "requests",
    "build_deeplol_url",
    "build_hotkey_site_url",
    "build_ingame_stats_url",
    "build_leagueofgraphs_url",
    "build_opgg_url",
    "build_player_stats_url",
    "build_porofessor_url",
    "build_stats_site_url",
    "is_valid_riot_id",
]
