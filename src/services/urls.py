"""External website URL builders."""

import urllib.parse


def build_opgg_url(region: str, riot_id: str) -> str:
    """Build the OP.GG URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    return f"https://www.op.gg/lol/summoners/{region}/{urllib.parse.quote(url_name)}"


def build_porofessor_url(region: str, riot_id: str) -> str:
    """Build the Porofessor URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    return f"https://porofessor.gg/fr/live/{region}/{urllib.parse.quote(url_name)}"


def _normalize_riot_id_for_url(riot_id: str) -> str:
    """Convert GameName#Tag into GameName-Tag for external URLs."""
    riot_id = riot_id or ""
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            return f"{left}-{right}"
    return riot_id
