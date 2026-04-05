"""Configuration package for MAIN LOL."""

from . import paths as _paths
from . import settings as _settings
from .constants import (
    APP_NAME,
    APP_BUILD_NAME,
    GITHUB_REPO_NAME,
    CURRENT_VERSION,
    GITHUB_REPO_URL,
    GITHUB_RELEASES_API,
    URL_DD_VERSIONS,
    URL_DD_CHAMPIONS,
    URL_DD_SUMMONERS,
    URL_DD_IMG_CHAMP,
    URL_DD_IMG_SPELL,
    URL_DD_SPLASH,
    EP_SESSION,
    EP_SESSION_TIMER,
    EP_SESSION_LEGACY,
    EP_GAMEFLOW,
    EP_READY_CHECK,
    EP_PICKABLE,
    EP_CURRENT_SUMMONER,
    EP_CHAT_ME,
    EP_LOGIN,
    REGION_LIST,
    SUMMONER_SPELL_MAP,
    SUMMONER_SPELL_LIST,
    PLATFORM_TO_REGION,
    PHASE_DISPLAY_MAP,
    ROLE_PROFILE_ORDER,
    ROLE_PROFILE_LABELS,
    ROLE_PROFILE_ICON_FILES,
)
from .paths import (
    resource_path,
    get_appdata_path,
    PARAMETERS_PATH,
    LOCKFILE_PATH,
    DDRAGON_CACHE_FILE,
    ICONS_CACHE_DIR,
    SPELLS_CACHE_DIR,
)
from .settings import DEFAULT_PARAMS
from .logging_config import LOG_FILE_PATH


def _sync_runtime_paths() -> None:
    _paths.PARAMETERS_PATH = PARAMETERS_PATH
    _settings.PARAMETERS_PATH = PARAMETERS_PATH
    _paths.LOCKFILE_PATH = LOCKFILE_PATH
    _settings.ICONS_CACHE_DIR = ICONS_CACHE_DIR
    _settings.SPELLS_CACHE_DIR = SPELLS_CACHE_DIR


def load_parameters():
    _sync_runtime_paths()
    return _settings.load_parameters()


def save_parameters(params):
    _sync_runtime_paths()
    return _settings.save_parameters(params)


def get_cache_dirs():
    _sync_runtime_paths()
    return _settings.get_cache_dirs()

__all__ = [
    "APP_NAME",
    "APP_BUILD_NAME",
    "GITHUB_REPO_NAME",
    "CURRENT_VERSION",
    "GITHUB_REPO_URL",
    "GITHUB_RELEASES_API",
    "URL_DD_VERSIONS",
    "URL_DD_CHAMPIONS",
    "URL_DD_SUMMONERS",
    "URL_DD_IMG_CHAMP",
    "URL_DD_IMG_SPELL",
    "URL_DD_SPLASH",
    "EP_SESSION",
    "EP_SESSION_TIMER",
    "EP_SESSION_LEGACY",
    "EP_GAMEFLOW",
    "EP_READY_CHECK",
    "EP_PICKABLE",
    "EP_CURRENT_SUMMONER",
    "EP_CHAT_ME",
    "EP_LOGIN",
    "REGION_LIST",
    "SUMMONER_SPELL_MAP",
    "SUMMONER_SPELL_LIST",
    "PLATFORM_TO_REGION",
    "PHASE_DISPLAY_MAP",
    "ROLE_PROFILE_ORDER",
    "ROLE_PROFILE_LABELS",
    "ROLE_PROFILE_ICON_FILES",
    "resource_path",
    "get_appdata_path",
    "PARAMETERS_PATH",
    "LOCKFILE_PATH",
    "DDRAGON_CACHE_FILE",
    "ICONS_CACHE_DIR",
    "SPELLS_CACHE_DIR",
    "DEFAULT_PARAMS",
    "load_parameters",
    "save_parameters",
    "get_cache_dirs",
    "LOG_FILE_PATH",
]
