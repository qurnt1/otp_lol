"""
FILE NAME: src/config/paths.py
GLOBAL PURPOSE:
- Resolve filesystem paths used by the application at runtime.
- Bridge local source execution and PyInstaller execution through one resource helper.
- Define stable locations for settings, history, caches, and temporary files.

KEY FUNCTIONS:
- resource_path: Resolve an asset path for source runs and packaged runs.
- get_appdata_path: Build a file path inside the user AppData folder when available.

AUDIENCE & LOGIC:
Why:
This module exists so every runtime path is built from one consistent place instead of being duplicated across the codebase.
For whom:
Developers working on filesystem access, caching, packaging, or resource loading.

DEPENDENCIES:
Used by:
- src.config, src.core, src.services, and src.ui modules that read files or write caches.
Uses:
- Standard library: os, sys, tempfile
"""

import os
import sys
import tempfile

APP_STORAGE_FOLDER = "OTP LOL"
APP_TEMP_PREFIX = "otp_lol"


def resource_path(relative_path: str) -> str:
    """Return the absolute path to a bundled resource for source and packaged runs."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(current_dir)
        base_path = os.path.dirname(src_dir)

    if relative_path.startswith("./"):
        relative_path = relative_path[2:]
    elif relative_path.startswith(".\\"):
        relative_path = relative_path[2:]

    return os.path.join(base_path, relative_path)


def get_appdata_path(filename: str) -> str:
    """Return a file path inside the application AppData folder when available."""
    app_data_dir = os.getenv("APPDATA")
    if not app_data_dir:
        return filename

    app_folder = os.path.join(app_data_dir, APP_STORAGE_FOLDER)
    if not os.path.exists(app_folder):
        try:
            os.makedirs(app_folder)
        except OSError:
            return filename

    return os.path.join(app_folder, filename)


PARAMETERS_PATH: str = get_appdata_path("parameters.json")
HISTORY_PATH: str = get_appdata_path("history.json")
LOCKFILE_PATH: str = os.path.join(tempfile.gettempdir(), f"{APP_TEMP_PREFIX}.lock")
DDRAGON_CACHE_FILE: str = os.path.join(tempfile.gettempdir(), f"{APP_TEMP_PREFIX}_ddragon_champions.json")
ICONS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), f"{APP_TEMP_PREFIX}_icons")
SPELLS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), f"{APP_TEMP_PREFIX}_spells")
SKINS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), f"{APP_TEMP_PREFIX}_skins")
