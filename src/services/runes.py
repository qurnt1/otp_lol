"""Pure helpers for rendering and persisting League rune pages."""

from typing import Any, Mapping


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def split_rune_page_perk_ids(page: Mapping[str, Any]) -> tuple[list[int], list[int], list[int]]:
    """Split selected perk ids into primary, secondary, and shard groups."""
    selected_ids = page.get("selectedPerkIds", [])
    if not isinstance(selected_ids, list):
        selected_ids = []
    normalized = [safe_int(perk_id) for perk_id in selected_ids]
    normalized = [perk_id for perk_id in normalized if perk_id > 0]
    return normalized[:4], normalized[4:6], normalized[6:9]


def find_rune_keystone_path(
    page: Mapping[str, Any],
    primary_style: Mapping[str, Any],
    data_dragon: Any | None = None,
) -> str:
    """Resolve the selected keystone icon, with style metadata as fallback."""
    selected_ids = page.get("selectedPerkIds", [])
    keystone_id = safe_int(selected_ids[0]) if isinstance(selected_ids, list) and selected_ids else 0
    perks = primary_style.get("perks", [])

    if keystone_id > 0 and data_dragon is not None:
        icon_path = str(data_dragon.get_rune_perk_icon_path(keystone_id) or "")
        if icon_path:
            return icon_path

    if isinstance(perks, list):
        for perk in perks:
            if isinstance(perk, Mapping) and safe_int(perk.get("id")) == keystone_id:
                return str(perk.get("iconPath") or "")
        if perks and isinstance(perks[0], Mapping):
            return str(perks[0].get("iconPath") or "")
    return ""


def get_rune_page_icon_paths(
    page: Mapping[str, Any],
    styles: Mapping[Any, Any],
    data_dragon: Any | None = None,
) -> tuple[str, str]:
    """Return the keystone and secondary-style icon paths for one page."""
    primary_style = styles.get(page.get("primaryStyleId"), {})
    sub_style = styles.get(page.get("subStyleId"), {})
    if not isinstance(primary_style, Mapping):
        primary_style = {}
    if not isinstance(sub_style, Mapping):
        sub_style = {}
    return (
        find_rune_keystone_path(page, primary_style, data_dragon),
        str(sub_style.get("iconPath") or ""),
    )


def strip_active_suffix(value: str) -> str:
    """Remove only the LCU active-page suffix from a rune page name."""
    return str(value or "").removesuffix(" (active)")
