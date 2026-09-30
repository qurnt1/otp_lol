"""Small external catalog fixture for deterministic full-stack E2E flows."""

from __future__ import annotations

import json
import re
from io import BytesIO
from urllib.parse import urlsplit

from PIL import Image
from requests import Response

VERSION = "16.1.1"
CHAMPIONS = {
    "Ahri": (103, "the Nine-Tailed Fox", ["Mage", "Assassin"]),
    "Annie": (1, "the Dark Child", ["Mage", "Support"]),
    "Ashe": (22, "the Frost Archer", ["Marksman", "Support"]),
    "Garen": (86, "the Might of Demacia", ["Fighter", "Tank"]),
    "Lux": (99, "the Lady of Luminosity", ["Mage", "Support"]),
    "Teemo": (17, "the Swift Scout", ["Marksman", "Mage"]),
}
SKINS = {
    "Ahri": [(103000, 0, "default")],
    "Garen": [(86000, 0, "default"), (86001, 1, "Commando Garen"), (86013, 13, "God-King Garen")],
    "Annie": [(1000, 0, "default"), (1001, 1, "Goth Annie")],
    "Ashe": [(22000, 0, "default"), (22001, 1, "Freljord Ashe"), (22004, 4, "Queen Ashe")],
    "Lux": [(99000, 0, "default"), (99007, 7, "Star Guardian Lux"), (99010, 10, "Battle Academia Lux")],
    "Teemo": [(17000, 0, "default"), (17001, 1, "Happy Elf Teemo")],
}
_EXTERNAL_STATE = {"dataDragon": "online", "updates": "offline"}


def configure_external_state(state: dict[str, str]) -> dict[str, str]:
    unknown = set(state) - _EXTERNAL_STATE.keys()
    if unknown:
        raise ValueError(f"Unknown external fixture state: {', '.join(sorted(unknown))}.")
    valid_modes = {"dataDragon": {"online", "offline"}, "updates": {"offline", "available", "none"}}
    for name, value in state.items():
        if value not in valid_modes[name]:
            choices = ", ".join(sorted(valid_modes[name]))
            raise ValueError(f"{name} must be one of: {choices}.")
        _EXTERNAL_STATE[name] = value
    return dict(_EXTERNAL_STATE)


def _response(url: str, status: int, body: bytes, content_type: str) -> Response:
    request = Response()
    request.status_code = status
    request.url = url
    request.headers["Content-Type"] = content_type
    request._content = body
    return request


def _json(url: str, payload: object) -> Response:
    return _response(url, 200, json.dumps(payload).encode("utf-8"), "application/json")


def _image(url: str, suffix: str) -> Response:
    image = Image.new("RGB", (2, 2), color=(62, 93, 122))
    output = BytesIO()
    is_jpeg = suffix.lower().lstrip(".") in {"jpg", "jpeg"}
    image.save(output, format="JPEG" if is_jpeg else "PNG")
    content_type = "image/jpeg" if is_jpeg else "image/png"
    return _response(url, 200, output.getvalue(), content_type)


def _champion_record(slug: str) -> dict[str, object]:
    champion_id, title, tags = CHAMPIONS[slug]
    return {
        "id": slug,
        "key": str(champion_id),
        "name": slug,
        "title": title,
        "tags": tags,
        "image": {"full": f"{slug}.png"},
        "skins": [
            {"id": skin_id, "num": skin_num, "name": skin_name, "chromas": False}
            for skin_id, skin_num, skin_name in SKINS[slug]
        ],
    }


def _cdragon_champion(champion_id: int) -> dict[str, object] | None:
    slug = next(
        (name for name, (candidate, _title, _tags) in CHAMPIONS.items() if candidate == champion_id),
        None,
    )
    if slug is None:
        return None
    return {
        "id": champion_id,
        "name": slug,
        "skins": [
            {
                "id": skin_id,
                "num": skin_num,
                "name": skin_name,
                "tilePath": (
                    "/lol-game-data/assets/ASSETS/Characters/"
                    f"{slug}/Skins/skin{skin_num}/Images/{slug.lower()}_splash_centered_{skin_num}.jpg"
                ),
            }
            for skin_id, skin_num, skin_name in SKINS[slug]
        ],
    }


def response_for_external_request(method: str, url: str) -> Response | None:
    """Return a fixture only for the public URLs exercised by the picker flows."""
    if method.upper() != "GET":
        return None

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.port not in {None, 443}:
        return None
    path = parsed.path
    if parsed.hostname == "api.github.com" and path == "/repos/qurnt1/otp_lol/releases/latest":
        update_mode = _EXTERNAL_STATE["updates"]
        if update_mode == "offline":
            return _response(
                url,
                503,
                b'{"detail":"Synthetic update service unavailable"}',
                "application/json",
            )
        if update_mode == "none":
            return _json(url, {"tag_name": "v0.0.0", "assets": []})
        return _json(
            url,
            {
                "tag_name": "v99.0",
                "name": "OTP LOL 99.0",
                "body": "Synthetic release for E2E update flow.",
                "html_url": "https://github.com/qurnt1/otp_lol/releases/tag/v99.0",
                "assets": [
                    {
                        "name": "OTP-LOL-Setup.exe",
                        "browser_download_url": "https://github.com/qurnt1/otp_lol/releases/download/v99.0/OTP-LOL-Setup.exe",
                    },
                    {
                        "name": "OTP-LOL-Setup.exe.sha256",
                        "browser_download_url": "https://github.com/qurnt1/otp_lol/releases/download/v99.0/OTP-LOL-Setup.exe.sha256",
                    },
                ],
            },
        )
    if (
        parsed.hostname in {"ddragon.leagueoflegends.com", "raw.communitydragon.org"}
        and _EXTERNAL_STATE["dataDragon"] == "offline"
    ):
        return _response(
            url,
            503,
            b'{"detail":"Synthetic Data Dragon outage"}',
            "application/json",
        )
    if parsed.hostname == "ddragon.leagueoflegends.com":
        if path == "/api/versions.json":
            return _json(url, [VERSION])
        if path == f"/cdn/{VERSION}/data/en_US/champion.json":
            return _json(
                url,
                {
                    "type": "champion",
                    "version": VERSION,
                    "data": {slug: _champion_record(slug) for slug in CHAMPIONS},
                },
            )
        if path == f"/cdn/{VERSION}/data/en_US/summoner.json":
            spell_data = {
                "SummonerFlash": (4, "SummonerFlash.png"),
                "SummonerTeleport": (12, "SummonerTeleport.png"),
                "SummonerDot": (14, "SummonerDot.png"),
            }
            return _json(
                url,
                {
                    "type": "summoner",
                    "version": VERSION,
                    "data": {
                        name: {"key": str(key), "image": {"full": image}}
                        for name, (key, image) in spell_data.items()
                    },
                },
            )
        detail_match = re.fullmatch(rf"/cdn/{re.escape(VERSION)}/data/en_US/champion/([^/]+)\.json", path)
        if detail_match and detail_match.group(1) in CHAMPIONS:
            slug = detail_match.group(1)
            return _json(url, {"type": "champion", "version": VERSION, "data": {slug: _champion_record(slug)}})
        if re.fullmatch(r"/cdn/(?:[\d.]+/img/(?:champion|spell)/[^/]+|img/champion/splash/[A-Za-z0-9_]+)\.(?:png|jpg|jpeg)", path):
            return _image(url, path.rsplit(".", 1)[-1])
        return None

    if parsed.hostname == "raw.communitydragon.org":
        champion_match = re.fullmatch(
            r"/latest/plugins/rcp-be-lol-game-data/global/default/v1/champions/(\d+)\.json",
            path,
        )
        if champion_match:
            payload = _cdragon_champion(int(champion_match.group(1)))
            return _json(url, payload) if payload is not None else None
        if path == "/latest/plugins/rcp-be-lol-game-data/global/default/v1/perks.json":
            perk_ids = (8005, 8008, 9101, 8014, 8106, 8120, 5008, 5011)
            return _json(
                url,
                [
                    {
                        "id": perk_id,
                        "name": f"E2E Rune {perk_id}",
                        "iconPath": f"lol-game-data/assets/v1/perk-images/{perk_id}.png",
                    }
                    for perk_id in perk_ids
                ],
            )
        if "/assets/" in path or "/v1/perk-images/" in path:
            return _image(url, path.rsplit(".", 1)[-1])

    return None
