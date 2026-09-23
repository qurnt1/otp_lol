"""Safe CommunityDragon asset access for rune and game-data images."""

from __future__ import annotations

import logging
from io import BytesIO
from urllib.parse import quote, unquote

import requests
from PIL import Image

from ..config import URL_PERK_ICON_PREFIX

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "WEBP", "GIF"})
logger = logging.getLogger(__name__)


class CommunityDragonClient:
    """Resolve only known LCU asset paths and decode bounded image responses."""

    @staticmethod
    def asset_url(asset_path: str) -> str | None:
        normalized_path = str(asset_path or "").strip()
        if not normalized_path or len(normalized_path) > 2048:
            return None
        decoded_path = normalized_path
        for _ in range(16):
            unquoted_path = unquote(decoded_path)
            if unquoted_path == decoded_path:
                break
            decoded_path = unquoted_path
        else:
            return None
        normalized_path = decoded_path.replace("\\", "/")
        if len(normalized_path) > 2048 or any(
            ord(character) < 32 or ord(character) == 127
            for character in normalized_path
        ):
            return None
        lowered_path = normalized_path.lower()
        if (
            "://" in lowered_path
            or lowered_path.startswith("//")
            or "?" in lowered_path
            or "#" in lowered_path
        ):
            return None
        normalized_path = lowered_path.lstrip("/")
        prefix = "lol-game-data/assets/"
        if not normalized_path.startswith(prefix):
            return None
        relative_path = normalized_path[len(prefix) :]
        if not relative_path or any(
            segment in {"", ".", ".."} for segment in relative_path.split("/")
        ):
            return None
        return f"{URL_PERK_ICON_PREFIX}/{quote(relative_path, safe='/-._~')}"

    @classmethod
    def fetch_image(cls, asset_path: str) -> Image.Image | None:
        url = cls.asset_url(asset_path)
        if not url:
            return None
        try:
            response = requests.get(url, timeout=8)
            if response.status_code != 200 or len(response.content) > MAX_IMAGE_BYTES:
                return None
            headers = getattr(response, "headers", {})
            content_type = str(
                headers.get("Content-Type") or headers.get("content-type") or ""
            )
            if content_type and not content_type.lower().startswith("image/"):
                return None
            image = Image.open(BytesIO(response.content))
            if image.format not in ALLOWED_IMAGE_FORMATS:
                return None
            image.load()
            return image
        except (
            requests.RequestException,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as error:
            logger.warning(
                "CommunityDragon image download error for %s: %s", url, error
            )
            return None


__all__ = ["MAX_IMAGE_BYTES", "CommunityDragonClient"]
