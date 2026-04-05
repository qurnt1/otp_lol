"""Filesystem paths and resource helpers."""

import os
import sys
import tempfile


def resource_path(relative_path: str) -> str:
    """Return the absolute path to a resource, compatible with PyInstaller."""
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
    """Return a file path inside AppData/MainLoL."""
    app_data_dir = os.getenv("APPDATA")
    if not app_data_dir:
        return filename

    app_folder = os.path.join(app_data_dir, "MainLoL")
    if not os.path.exists(app_folder):
        try:
            os.makedirs(app_folder)
        except OSError:
            return filename

    return os.path.join(app_folder, filename)


PARAMETERS_PATH: str = get_appdata_path("parameters.json")
HISTORY_PATH: str = get_appdata_path("history.json")
LOCKFILE_PATH: str = os.path.join(tempfile.gettempdir(), "main_lol.lock")
DDRAGON_CACHE_FILE: str = os.path.join(tempfile.gettempdir(), "mainlol_ddragon_champions.json")
ICONS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), "mainlol_icons")
SPELLS_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), "mainlol_spells")
