"""
Champion role resolution for the champion picker.

Data Dragon exposes champion class tags, not reliable lane positions. This
module keeps lane-position logic separate from UI code so the picker can use a
curated local dataset first and fall back to class-tag heuristics when needed.
"""

import json
import logging
import re
import unicodedata
from functools import lru_cache
from typing import Any, Dict, Iterable, List

from ..config import resource_path

ROLE_THRESHOLD = 0.10
ROLE_DATA_PATH = "config/champion_roles.json"

FALLBACK_TAG_ROLE_SCORES: Dict[str, Dict[str, float]] = {
    "Marksman": {"BOTTOM": 0.75},
    "Support": {"UTILITY": 0.75},
    "Mage": {"MIDDLE": 0.55, "UTILITY": 0.20},
    "Assassin": {"MIDDLE": 0.55, "JUNGLE": 0.30},
    "Fighter": {"TOP": 0.55, "JUNGLE": 0.35},
    "Tank": {"TOP": 0.45, "JUNGLE": 0.30, "UTILITY": 0.25},
}


def _normalize_champion_key(value: Any) -> str:
    """Normalize champion names for stable lookups across Riot display variants."""
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", text)


@lru_cache(maxsize=1)
def _load_role_payload() -> Dict[str, Any]:
    """Load the bundled champion role dataset."""
    path = resource_path(ROLE_DATA_PATH)
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict):
            return payload
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Unable to load champion role data from %s: %s", path, exc)
    return {}


@lru_cache(maxsize=1)
def _get_role_entries_by_key() -> Dict[str, Dict[str, Any]]:
    """Return champion role entries indexed by normalized champion name."""
    payload = _load_role_payload()
    champions = payload.get("champions", {})
    if not isinstance(champions, dict):
        return {}
    entries: Dict[str, Dict[str, Any]] = {}
    for champion_name, entry in champions.items():
        if not isinstance(entry, dict):
            continue
        key = _normalize_champion_key(champion_name)
        if key:
            entries[key] = entry
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                alias_key = _normalize_champion_key(alias)
                if alias_key:
                    entries[alias_key] = entry
    return entries


def _normalize_positions(raw_positions: Any) -> Dict[str, float]:
    """Normalize and clamp role scores from role data."""
    if not isinstance(raw_positions, dict):
        return {}
    positions: Dict[str, float] = {}
    allowed_roles = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
    for role, raw_score in raw_positions.items():
        normalized_role = str(role or "").upper()
        if normalized_role not in allowed_roles:
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        positions[normalized_role] = max(0.0, min(score, 1.0))
    return positions


def fallback_positions_from_tags(tags: Iterable[str]) -> Dict[str, float]:
    """Build approximate role scores from Data Dragon class tags."""
    scores: Dict[str, float] = {}
    for tag in tags:
        for role, value in FALLBACK_TAG_ROLE_SCORES.get(str(tag), {}).items():
            scores[role] = scores.get(role, 0.0) + value
    return {role: min(score, 1.0) for role, score in scores.items()}


def get_champion_positions(dd: Any, champion_name: str) -> Dict[str, float]:
    """Return lane-position scores for a champion, using fallback tags if needed."""
    entry = _get_role_entries_by_key().get(_normalize_champion_key(champion_name))
    positions = _normalize_positions(entry.get("positions")) if entry else {}
    if positions:
        return positions
    try:
        tags = dd.get_champion_tags(champion_name)
    except Exception:
        tags = []
    return fallback_positions_from_tags(tags)


def role_score(dd: Any, champion_name: str, role: str) -> float:
    """Return a champion's score for a selected role."""
    normalized_role = str(role or "GLOBAL").upper()
    if normalized_role == "GLOBAL":
        return 1.0
    return get_champion_positions(dd, champion_name).get(normalized_role, 0.0)


def champion_matches_role(dd: Any, champion_name: str, role: str, *, threshold: float = ROLE_THRESHOLD) -> bool:
    """Return whether a champion should appear in a role filter."""
    normalized_role = str(role or "GLOBAL").upper()
    if normalized_role == "GLOBAL":
        return True
    return role_score(dd, champion_name, normalized_role) >= threshold


def sort_champions_for_role(champions: Iterable[str], dd: Any, role: str) -> List[str]:
    """Sort champions by role relevance first, then by name."""
    normalized_role = str(role or "GLOBAL").upper()
    if normalized_role == "GLOBAL":
        return sorted(champions)
    return sorted(champions, key=lambda champion: (-role_score(dd, champion, normalized_role), champion))
