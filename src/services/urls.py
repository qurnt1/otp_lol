"""External website URL builders."""

import urllib.parse


def is_valid_riot_id(riot_id: str) -> bool:
    """Return True when the Riot ID looks like GameName#TAG."""
    if not riot_id:
        return False
    value = str(riot_id).strip()
    if "#" not in value:
        return False
    left, right = value.split("#", 1)
    return bool(left.strip() and right.strip())


def build_opgg_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    """Build the OP.GG URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    base = f"https://op.gg/fr/lol/summoners/{region}/{urllib.parse.quote(url_name)}"
    return f"{base}/ingame" if ingame else base


def build_porofessor_url(region: str, riot_id: str) -> str:
    """Build the Porofessor in-game URL for a player."""
    url_name = _normalize_riot_id_for_porofessor(riot_id)
    return f"https://porofessor.gg/fr/live/{region}/{urllib.parse.quote(url_name)}/ranked-only"


def build_leagueofgraphs_url(region: str, riot_id: str) -> str:
    """Build the League of Graphs URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    return f"https://www.leagueofgraphs.com/fr/summoner/{region}/{urllib.parse.quote(url_name)}"


def build_deeplol_url(region: str, riot_id: str, *, ingame: bool = False) -> str:
    """Build the DeepLOL URL for a player."""
    url_name = _normalize_riot_id_for_url(riot_id)
    base = f"https://www.deeplol.gg/summoner/{region}/{urllib.parse.quote(url_name)}"
    return f"{base}/ingame" if ingame else base


def build_player_stats_url(site: str, region: str, riot_id: str) -> str:
    """Build a non in-game stats URL based on the chosen provider."""
    normalized_site = (site or "opgg").lower().strip()
    builders = {
        "opgg": lambda reg, rid: build_opgg_url(reg, rid, ingame=False),
        "deeplol": lambda reg, rid: build_deeplol_url(reg, rid, ingame=False),
        "leagueofgraphs": build_leagueofgraphs_url,
    }
    builder = builders.get(normalized_site, builders["opgg"])
    return builder(region, riot_id)


def build_ingame_stats_url(site: str, region: str, riot_id: str) -> str:
    """Build an in-game stats URL based on the chosen provider."""
    normalized_site = (site or "porofessor").lower().strip()
    builders = {
        "porofessor": build_porofessor_url,
        "deeplol": lambda reg, rid: build_deeplol_url(reg, rid, ingame=True),
        "opgg": lambda reg, rid: build_opgg_url(reg, rid, ingame=True),
    }
    builder = builders.get(normalized_site, builders["porofessor"])
    return builder(region, riot_id)


def build_stats_site_url(site: str, region: str, riot_id: str) -> str:
    """Backward-compatible alias for player stats URLs."""
    return build_player_stats_url(site, region, riot_id)


def build_hotkey_site_url(site: str, region: str, riot_id: str) -> str:
    """Backward-compatible alias for in-game stats URLs."""
    return build_ingame_stats_url(site, region, riot_id)


def _normalize_riot_id_for_url(riot_id: str) -> str:
    """Convert GameName#Tag into GameName-Tag for external URLs."""
    riot_id = str(riot_id or "").strip()
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            return f"{left}-{right}"
    return riot_id


def _normalize_riot_id_for_porofessor(riot_id: str) -> str:
    """Convert GameName#Tag into the Porofessor live URL format."""
    riot_id = str(riot_id or "").strip()
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            return f"{left}-{right.lower()}"
    return riot_id
