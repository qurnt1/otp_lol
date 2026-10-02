"""Optional sound effects shared by desktop shells."""

from __future__ import annotations

import logging
import os
import warnings

from ..config import resource_path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


class AudioManager:
    """Wrap pygame audio so sound support remains optional and easy to clean up."""

    def __init__(self):
        self.sound_effect = None
        self._pygame = None
        self._init_sound()

    def _init_sound(self) -> None:
        """Initialize the pygame mixer and preload the ready-check sound effect."""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="pkg_resources is deprecated as an API.*",
                    category=UserWarning,
                )
                import pygame

            self._pygame = pygame
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except Exception as e:
            logging.debug("Unable to initialize sound: %s", e)
            self.sound_effect = None
            self._pygame = None

    def play_accept_sound(self) -> None:
        """Play the ready-check sound when audio initialization succeeded."""
        if not self.sound_effect:
            return
        try:
            self.sound_effect.play()
        except Exception as e:
            logging.debug("Unable to play accept sound: %s", e)

    def shutdown(self) -> None:
        """Stop the pygame mixer during application shutdown when it was initialized."""
        try:
            if self._pygame and self._pygame.mixer.get_init():
                self._pygame.mixer.quit()
        except Exception as e:
            logging.debug("Error stopping pygame mixer: %s", e)
