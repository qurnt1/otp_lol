"""Build frontend asset URLs scoped to the loaded Data Dragon version."""

from urllib.parse import quote


def versioned_asset_url(path: str, version: str | None) -> str:
    if not version:
        return path
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}v={quote(str(version), safe='')}"
