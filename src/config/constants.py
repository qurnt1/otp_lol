"""
FILE NAME: src/config/constants.py
GLOBAL PURPOSE:
- Store static application constants and labels in one place.
- Centralize endpoint strings, UI labels, asset paths, and routing maps.
- Provide immutable reference data shared across runtime modules.

KEY FUNCTIONS:
- None.

AUDIENCE & LOGIC:
Why:
This module keeps repeated literals out of business logic so configuration drift and label mismatches are easier to avoid.
For whom:
Developers maintaining shared constants for networking, UI labels, assets, and settings defaults.

DEPENDENCIES:
Used by:
- Most modules under `src.config`, `src.core`, `src.services`, and `src.ui`.
Uses:
- Standard library typing helpers.
"""

from typing import Dict

APP_NAME: str = "OTP LOL"
APP_BUILD_NAME: str = "OTP LOL"
GITHUB_REPO_NAME: str = "qurnt1/otp_lol"
CURRENT_VERSION: str = "11.0"
GITHUB_REPO_URL: str = f"https://github.com/{GITHUB_REPO_NAME}"
GITHUB_DOWNLOAD_ZIP_URL: str = f"{GITHUB_REPO_URL}/archive/refs/heads/main.zip"
GITHUB_RELEASES_API: str = f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/latest"
GITHUB_REPO_API = f"https://api.github.com/repos/{GITHUB_REPO_NAME}"

URL_DD_VERSIONS: str = "https://ddragon.leagueoflegends.com/api/versions.json"
URL_DD_CHAMPIONS: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
URL_DD_SUMMONERS: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json"
URL_DD_IMG_CHAMP: str = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"
URL_DD_IMG_SPELL: str = "https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{filename}"
URL_DD_CHAMPION_DETAIL: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion/{champion}.json"
URL_DD_SKIN_SPLASH: str = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champion}_{skin_num}.jpg"
URL_CDRAGON_CHAMPION_DETAIL: str = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champions/{champion_id}.json"
)
URL_CDRAGON_ASSET_PREFIX: str = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
)
URL_PHASE_RUSH_ICON: str = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
    "v1/perk-images/styles/runesicon.png"
)
URL_PERK_ICON_PREFIX: str = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default"

EP_SESSION: str = "/lol-champ-select/v1/session"
EP_SESSION_TIMER: str = "/lol-champ-select/v1/session/timer"
EP_SESSION_LEGACY: str = "/lol-champ-select-legacy/v1/session"
EP_GAMEFLOW: str = "/lol-gameflow/v1/gameflow-phase"
EP_READY_CHECK: str = "/lol-matchmaking/v1/ready-check"
EP_PICKABLE: str = "/lol-champ-select/v1/pickable-champion-ids"
EP_CURRENT_SUMMONER: str = "/lol-summoner/v1/current-summoner"
EP_CHAT_ME: str = "/lol-chat/v1/me"
EP_LOGIN: str = "/lol-login/v1/session"
EP_PERKS_PAGES: str = "/lol-perks/v1/pages"
EP_PERKS_STYLES: str = "/lol-perks/v1/styles"
EP_PERKS_INVENTORY: str = "/lol-perks/v1/inventory"
EP_CS_RUNE_PAGE: str = "/lol-champ-select/v1/session/rune-page"
EP_PERKS_CURRENT_PAGE: str = "/lol-perks/v1/currentpage"

REGION_LIST: list[str] = ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"]

SUMMONER_SPELL_MAP: Dict[str, int] = {
    "Barrier": 21, "Cleanse": 1, "Exhaust": 3, "Flash": 4, "Ghost": 6,
    "Heal": 7, "Ignite": 14, "Smite": 11, "Teleport": 12, "(None)": 0
}

SUMMONER_SPELL_LIST: list[str] = sorted(list(SUMMONER_SPELL_MAP.keys()))

PLATFORM_TO_REGION: Dict[str, str] = {
    "euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr",
    "jp1": "jp", "br1": "br", "la1": "lan", "la2": "las",
    "oc1": "oce", "tr1": "tr", "ru": "ru"
}

PHASE_DISPLAY_MAP: Dict[str, str] = {
    "Lobby": "In Lobby",
    "Matchmaking": "Searching for a match...",
    "ReadyCheck": "Match found!",
    "ChampSelect": "Champion select",
    "InProgress": "Game in progress",
    "EndOfGame": "End of game",
    "WaitingForStats": "Waiting for stats",
    "PreEndOfGame": "Nexus destroyed",
    "None": "Inactive"
}

PICK_SLOT_ORDER: list[str] = ["pick_1", "pick_2", "pick_3"]
PICK_SLOT_LABELS: Dict[str, str] = {
    "pick_1": "Pick 1",
    "pick_2": "Pick 2",
    "pick_3": "Pick 3",
}

PRESET_ENABLED_QUEUE_IDS: set[int] = {
    400,  # Normal Draft
    430,  # Normal Blind
    420,  # Ranked Solo/Duo
    440,  # Ranked Flex
    490,  # Quickplay
}

QUEUE_ID_LABELS: Dict[int, str] = {
    0: "Practice Tool",
    450: "ARAM",
    900: "URF",
    1700: "Arena",
    1710: "Arena (Hextech)",
}

APP_IMAGE_FILES: Dict[str, str] = {
    "icon_webp": "config/images/app/garen.webp",
    "icon_ico": "config/images/app/garen.ico",
    "gear": "config/images/app/gear.png",
    "gear_light": "config/images/app/gear_light.png",
    "gear_dark": "config/images/app/gear_dark.png",
    "question_mark_white_mode": "config/images/app/question-mark-white_mode.png",
    "question_mark_black_mode": "config/images/app/question-mark-black_mode.png",
}

WEBSITE_LOGO_FILES: Dict[str, str] = {
    "opgg": "config/images/websites/opgg.png",
    "deeplol": "config/images/websites/deeplol.png",
    "dpm": "config/images/websites/dpm-lol.png",
    "porofessor": "config/images/websites/porofessor.png",
    "leagueofgraphs": "config/images/websites/leagueofgraphs.png",
}

STATS_SITE_LABELS: Dict[str, str] = {
    "opgg": "OP.GG",
    "deeplol": "DeepLOL",
    "dpm": "DPM.LOL",
    "leagueofgraphs": "League of Graphs",
}

STATS_SITE_ORDER: list[str] = ["opgg", "deeplol", "dpm", "leagueofgraphs"]

HOTKEY_SITE_LABELS: Dict[str, str] = {
    "porofessor": "Porofessor",
    "deeplol": "DeepLOL",
    "dpm": "DPM.LOL",
    "opgg": "OP.GG",
}

HOTKEY_SITE_ORDER: list[str] = ["porofessor", "deeplol", "dpm", "opgg"]

THEME_LABELS: Dict[str, str] = {
    "darkly": "Dark",
    "flatly": "Light",
}

THEME_ORDER: list[str] = ["darkly", "flatly"]

THEME_PALETTE: Dict[str, Dict[str, str]] = {
    "darkly": {
        "window_bg": "#2b2b2b",
        "surface_bg": "#2b2b2b",
        "text": "#f5f5f5",
        "muted": "#8f8f8f",
        "history_time": "#8fa1b3",
        "history_info": "#7ec8ff",
        "history_success": "#79d17d",
        "history_warning": "#f7c35f",
        "history_error": "#ff8a8a",
        "history_detail": "#c3c3c3",
    },
    "flatly": {
        "window_bg": "#f8f9fa",
        "surface_bg": "#f8f9fa",
        "text": "#1f1f1f",
        "muted": "#6b7280",
        "history_time": "#5c7c99",
        "history_info": "#2d7dd2",
        "history_success": "#2e8b57",
        "history_warning": "#c27c0e",
        "history_error": "#c0392b",
        "history_detail": "#4b5563",
    },
}
