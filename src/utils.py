"""
FILE NAME: src/utils.py
GLOBAL PURPOSE:
- Expose legacy utility imports through one compatibility module.
- Re-export helpers that were split into smaller service modules.
- Preserve older import paths while the internal architecture stays modular.

KEY FUNCTIONS:
- check_for_updates: Re-export the update check helper.
- check_single_instance: Re-export the single-instance guard.

AUDIENCE & LOGIC:
Why:
This facade keeps older call sites stable while utility logic lives in dedicated service modules.
For whom:
Developers maintaining legacy imports or calling shared utility helpers from runtime code.

DEPENDENCIES:
Used by:
- launcher.py and modules that still import shared helpers from `src.utils`.
Uses:
- Local modules from `src.services`
"""

from .services import updates as _updates
from .services.single_instance import check_single_instance, remove_lockfile
from .services.updates import check_for_updates, normalize_version, parse_version, is_newer_version
from .services.urls import (
    build_dpm_url,
    build_deeplol_url,
    build_hotkey_site_url,
    build_leagueofgraphs_url,
    build_opgg_url,
    build_porofessor_url,
    build_stats_site_url,
    is_valid_riot_id,
)

requests = _updates.requests

__all__ = [
    "check_single_instance",
    "remove_lockfile",
    "check_for_updates",
    "normalize_version",
    "parse_version",
    "is_newer_version",
    "requests",
    "build_dpm_url",
    "build_deeplol_url",
    "build_hotkey_site_url",
    "build_leagueofgraphs_url",
    "build_opgg_url",
    "build_porofessor_url",
    "build_stats_site_url",
    "is_valid_riot_id",
]
