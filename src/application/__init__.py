"""Application-layer components shared by desktop entry points."""

from .controller import ApplicationController
from .settings_store import SettingsStore

__all__ = ["ApplicationController", "SettingsStore"]
