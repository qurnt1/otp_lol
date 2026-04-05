"""Static constants for MAIN LOL."""

from typing import Any, Dict

APP_NAME: str = "MAIN LOL"
APP_BUILD_NAME: str = "OTP LOL"
GITHUB_REPO_NAME: str = "qurnt1/main_lol_2"
CURRENT_VERSION: str = "6.1"
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
    "Heal": 7, "Ignite": 14, "Smite": 11, "Teleport": 12, "(Aucun)": 0
}

SUMMONER_SPELL_LIST: list[str] = sorted(list(SUMMONER_SPELL_MAP.keys()))

PLATFORM_TO_REGION: Dict[str, str] = {
    "euw1": "euw", "eun1": "eune", "na1": "na", "kr": "kr",
    "jp1": "jp", "br1": "br", "la1": "lan", "la2": "las",
    "oc1": "oce", "tr1": "tr", "ru": "ru"
}

PHASE_DISPLAY_MAP: Dict[str, str] = {
    "Lobby": "Au Salon (Lobby)",
    "Matchmaking": "Recherche de partie...",
    "ReadyCheck": "Partie trouvée !",
    "ChampSelect": "Sélection des champions",
    "InProgress": "Partie en cours",
    "EndOfGame": "Fin de partie",
    "WaitingForStats": "En attente des stats",
    "PreEndOfGame": "Nexus détruit",
    "None": "Inactif"
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
