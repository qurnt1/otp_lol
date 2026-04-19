"""Audio helpers for the main window."""

import logging
import os
import warnings

from ..config import resource_path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


class AudioManager:
    """Small wrapper around pygame audio."""

    def __init__(self):
        self.sound_effect = None
        self._pygame = None
        self._init_sound()

    def _init_sound(self) -> None:
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
            logging.debug(f"Unable to initialize sound: {e}")
            self.sound_effect = None
            self._pygame = None

    def play_accept_sound(self) -> None:
        if not self.sound_effect:
            return
        try:
            self.sound_effect.play()
        except Exception as e:
            logging.debug(f"Unable to play accept sound: {e}")

    def shutdown(self) -> None:
        try:
            if self._pygame and self._pygame.mixer.get_init():
                self._pygame.mixer.quit()
        except Exception as e:
            logging.debug(f"Error stopping pygame mixer: {e}")
