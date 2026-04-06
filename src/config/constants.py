"""Static constants for MAIN LOL."""

from typing import Any, Dict

APP_NAME: str = "MAIN LOL"
APP_BUILD_NAME: str = "OTP LOL"
GITHUB_REPO_NAME: str = "qurnt1/main_lol_2"
CURRENT_VERSION: str = "7.0"
GITHUB_REPO_URL: str = f"https://github.com/{GITHUB_REPO_NAME}"
GITHUB_RELEASES_API: str = f"https://api.github.com/repos/{GITHUB_REPO_NAME}/releases/latest"

URL_DD_VERSIONS: str = "https://ddragon.leagueoflegends.com/api/versions.json"
URL_DD_CHAMPIONS: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
URL_DD_SUMMONERS: str = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json"
URL_DD_IMG_CHAMP: str = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{filename}"
URL_DD_IMG_SPELL: str = "https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{filename}"
URL_DD_SPLASH: str = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champion}_0.jpg"

EP_SESSION: str = "/lol-champ-select/v1/session"
EP_SESSION_TIMER: str = "/lol-champ-select/v1/session/timer"
EP_SESSION_LEGACY: str = "/lol-champ-select-legacy/v1/session"
EP_GAMEFLOW: str = "/lol-gameflow/v1/gameflow-phase"
EP_READY_CHECK: str = "/lol-matchmaking/v1/ready-check"
EP_PICKABLE: str = "/lol-champ-select/v1/pickable-champion-ids"
EP_CURRENT_SUMMONER: str = "/lol-summoner/v1/current-summoner"
EP_CHAT_ME: str = "/lol-chat/v1/me"
EP_LOGIN: str = "/lol-login/v1/session"

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

ROLE_PROFILE_ORDER: list[str] = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

ROLE_PROFILE_LABELS: Dict[str, str] = {
    "GLOBAL": "Global",
    "TOP": "Top",
    "JUNGLE": "Jungle",
    "MIDDLE": "Mid",
    "BOTTOM": "ADC",
    "UTILITY": "Support",
}

ROLE_PROFILE_ICON_FILES: Dict[str, str] = {
    "GLOBAL": "config/images/roles/global.png",
    "TOP": "config/images/roles/top.png",
    "JUNGLE": "config/images/roles/jungle.png",
    "MIDDLE": "config/images/roles/middle.png",
    "BOTTOM": "config/images/roles/bottom.png",
    "UTILITY": "config/images/roles/utility.png",
}

APP_IMAGE_FILES: Dict[str, str] = {
    "icon_webp": "config/images/app/garen.webp",
    "icon_ico": "config/images/app/garen.ico",
    "gear": "config/images/app/gear.png",
    "gear_light": "config/images/app/gear_light.png",
    "gear_dark": "config/images/app/gear_dark.png",
}

WEBSITE_LOGO_FILES: Dict[str, str] = {
    "opgg": "config/images/websites/opgg.png",
    "deeplol": "config/images/websites/deeplol.png",
    "porofessor": "config/images/websites/porofessor.png",
    "leagueofgraphs": "config/images/websites/leagueofgraphs.png",
}

STATS_SITE_LABELS: Dict[str, str] = {
    "opgg": "OP.GG",
    "deeplol": "DeepLOL",
    "leagueofgraphs": "League of Graphs",
}

STATS_SITE_ORDER: list[str] = ["opgg", "deeplol", "leagueofgraphs"]

HOTKEY_SITE_LABELS: Dict[str, str] = {
    "porofessor": "Porofessor",
    "deeplol": "DeepLOL",
    "opgg": "OP.GG",
}

HOTKEY_SITE_ORDER: list[str] = ["porofessor", "deeplol", "opgg"]

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
