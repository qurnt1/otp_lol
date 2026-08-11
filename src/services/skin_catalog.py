"""Pure skin-catalog merge and ordering rules shared by desktop pickers."""

from typing import Any, Mapping

LCU_NOT_DETECTED = "LoL client is not detected. Launch League of Legends to refresh."


def picker_lcu_status_message(kind: str) -> str:
    return f"Unable to fetch {kind}: {LCU_NOT_DETECTED}"


def merge_catalog_and_owned_skins(
    catalog_skins: list[dict[str, Any]],
    owned_skins: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge Community/Data Dragon metadata with the account ownership result."""
    owned_by_id: dict[int, dict[str, Any]] = {}
    for entry in owned_skins:
        if not isinstance(entry, dict):
            continue
        skin_id = _to_int(entry.get("skin_id"))
        if skin_id > 0:
            owned_by_id[skin_id] = dict(entry)

    merged: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for entry in catalog_skins:
        if not isinstance(entry, dict):
            continue
        skin_id = _to_int(entry.get("skin_id"))
        if skin_id <= 0 or skin_id in seen_ids:
            continue
        seen_ids.add(skin_id)
        merged_entry = dict(entry)
        for key, value in owned_by_id.get(skin_id, {}).items():
            if value not in {"", None}:
                merged_entry[key] = value
        merged_entry["owned"] = skin_id in owned_by_id or _to_int(merged_entry.get("skin_num")) == 0
        merged_entry["preview_url"] = _best_preview_url(merged_entry)
        merged.append(merged_entry)

    for skin_id, entry in owned_by_id.items():
        if skin_id in seen_ids:
            continue
        merged_entry = dict(entry)
        merged_entry["owned"] = True
        merged_entry["preview_url"] = _best_preview_url(merged_entry)
        merged.append(merged_entry)
    return merged


def sort_skins_for_display(
    skins: list[dict[str, Any]],
    *,
    mode: str,
    fixed_skin_id: int = 0,
    pool_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Move selected skins first while preserving catalog order within groups."""
    selected_ids = set(pool_ids or ()) if str(mode).lower() == "random" else set()
    prioritized: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for skin in skins:
        skin_id = _to_int(skin.get("skin_id"))
        selected = skin_id in selected_ids if str(mode).lower() == "random" else skin_id == fixed_skin_id
        (prioritized if selected else others).append(skin)
    return [*prioritized, *others]


def skin_selection_warning(skin: Mapping[str, Any], *, lcu_available: bool) -> tuple[str, str] | None:
    """Return the confirmation copy required for an unverified skin."""
    if bool(skin.get("owned")):
        return None
    if not lcu_available:
        return (
            "LoL client not detected",
            "Ownership cannot be verified because the League client is offline. Select this skin anyway?",
        )
    return (
        "Skin not detected",
        "This skin was not detected on the connected account. Select it anyway?",
    )


def confirm_unowned_skin_selection(
    skin: Mapping[str, Any],
    *,
    ask_fn: Any,
    lcu_available: bool = True,
) -> bool:
    """Apply the ownership warning through an injected confirmation function."""
    warning = skin_selection_warning(skin, lcu_available=lcu_available)
    return True if warning is None else bool(ask_fn(*warning))


def get_picker_image_url(skin: Mapping[str, Any]) -> str:
    """Choose the highest-quality image used by a visible picker row."""
    return str(
        skin.get("centered_splash_url")
        or skin.get("splash_url")
        or skin.get("tile_url")
        or skin.get("preview_url")
        or ""
    )


def _best_preview_url(entry: Mapping[str, Any]) -> str:
    return str(
        entry.get("preview_url")
        or entry.get("tile_url")
        or entry.get("centered_splash_url")
        or entry.get("uncentered_splash_url")
        or entry.get("splash_url")
        or ""
    )


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
