"""Configuration package for OTP LOL."""

from . import paths as _paths
from . import settings as _settings
from .constants import (
    APP_IMAGE_FILES,
    APP_BUILD_NAME,
    APP_NAME,
    CURRENT_VERSION,
    GITHUB_DOWNLOAD_ZIP_URL,
    EP_CHAT_ME,
    EP_CURRENT_SUMMONER,
    EP_GAMEFLOW,
    EP_LOGIN,
    EP_PICKABLE,
    EP_READY_CHECK,
    EP_SESSION,
    EP_SESSION_LEGACY,
    EP_SESSION_TIMER,
    GITHUB_RELEASES_API,
    GITHUB_REPO_NAME,
    GITHUB_REPO_URL,
    GITHUB_REPO_API,
    HOTKEY_SITE_LABELS,
    HOTKEY_SITE_ORDER,
    PHASE_DISPLAY_MAP,
    PLATFORM_TO_REGION,
    PICK_SLOT_LABELS,
    PICK_SLOT_ORDER,
    REGION_LIST,
    ROLE_PROFILE_ICON_FILES,
    ROLE_PROFILE_LABELS,
    ROLE_PROFILE_ORDER,
    STATS_SITE_LABELS,
    STATS_SITE_ORDER,
    THEME_LABELS,
    THEME_ORDER,
    THEME_PALETTE,
    WEBSITE_LOGO_FILES,
    SUMMONER_SPELL_LIST,
    SUMMONER_SPELL_MAP,
    URL_DD_CHAMPIONS,
    URL_DD_IMG_CHAMP,
    URL_DD_IMG_SPELL,
    URL_DD_CHAMPION_DETAIL,
    URL_DD_SKIN_SPLASH,
    URL_CDRAGON_ASSET_PREFIX,
    URL_CDRAGON_CHAMPION_DETAIL,
    URL_PHASE_RUSH_ICON,
    URL_DD_SPLASH,
    URL_DD_SUMMONERS,
    URL_DD_VERSIONS,
)
from .logging_config import LOG_FILE_PATH
from .paths import (
    DDRAGON_CACHE_FILE,
    HISTORY_PATH,
    ICONS_CACHE_DIR,
    LOCKFILE_PATH,
    PARAMETERS_PATH,
    SPELLS_CACHE_DIR,
    SKINS_CACHE_DIR,
    get_appdata_path,
    resource_path,
)
from .settings import DEFAULT_PARAMS, FIRST_LAUNCH_PARAMS


def _sync_runtime_paths() -> None:
    _paths.PARAMETERS_PATH = PARAMETERS_PATH
    _settings.PARAMETERS_PATH = PARAMETERS_PATH
    _paths.HISTORY_PATH = HISTORY_PATH
    _paths.LOCKFILE_PATH = LOCKFILE_PATH
    _settings.ICONS_CACHE_DIR = ICONS_CACHE_DIR
    _settings.SPELLS_CACHE_DIR = SPELLS_CACHE_DIR
    _settings.SKINS_CACHE_DIR = SKINS_CACHE_DIR


def load_parameters():
    _sync_runtime_paths()
    return _settings.load_parameters()


def save_parameters(params):
    _sync_runtime_paths()
    return _settings.save_parameters(params)


def export_parameters_to_file(path, params):
    _sync_runtime_paths()
    return _settings.export_parameters_to_file(path, params)


def import_parameters_from_file(path):
    _sync_runtime_paths()
    return _settings.import_parameters_from_file(path)


def get_cache_dirs():
    _sync_runtime_paths()
    return _settings.get_cache_dirs()


__all__ = [
    "APP_NAME",
    "APP_BUILD_NAME",
    "APP_IMAGE_FILES",
    "GITHUB_REPO_NAME",
    "CURRENT_VERSION",
    "GITHUB_REPO_URL",
    "GITHUB_DOWNLOAD_ZIP_URL",
    "GITHUB_RELEASES_API",
    "URL_DD_VERSIONS",
    "URL_DD_CHAMPIONS",
    "URL_DD_SUMMONERS",
    "URL_DD_IMG_CHAMP",
    "URL_DD_IMG_SPELL",
    "URL_DD_CHAMPION_DETAIL",
    "URL_DD_SKIN_SPLASH",
    "URL_CDRAGON_CHAMPION_DETAIL",
    "URL_CDRAGON_ASSET_PREFIX",
    "URL_PHASE_RUSH_ICON",
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
    "PICK_SLOT_ORDER",
    "PICK_SLOT_LABELS",
    "PHASE_DISPLAY_MAP",
    "ROLE_PROFILE_ORDER",
    "ROLE_PROFILE_LABELS",
    "ROLE_PROFILE_ICON_FILES",
    "WEBSITE_LOGO_FILES",
    "STATS_SITE_LABELS",
    "STATS_SITE_ORDER",
    "HOTKEY_SITE_LABELS",
    "HOTKEY_SITE_ORDER",
    "THEME_LABELS",
    "THEME_ORDER",
    "THEME_PALETTE",
    "resource_path",
    "get_appdata_path",
    "PARAMETERS_PATH",
    "HISTORY_PATH",
    "LOCKFILE_PATH",
    "DDRAGON_CACHE_FILE",
    "ICONS_CACHE_DIR",
    "SPELLS_CACHE_DIR",
    "SKINS_CACHE_DIR",
    "DEFAULT_PARAMS",
    "FIRST_LAUNCH_PARAMS",
    "load_parameters",
    "save_parameters",
    "export_parameters_to_file",
    "import_parameters_from_file",
    "get_cache_dirs",
    "LOG_FILE_PATH",
]
