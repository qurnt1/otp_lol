"""Audio helpers for the main window."""

import logging

import pygame

from ..config import resource_path


class AudioManager:
    """Small wrapper around pygame audio."""

    def __init__(self):
        self.sound_effect = None
        self._init_sound()

    def _init_sound(self) -> None:
        try:
            pygame.mixer.init()
            self.sound_effect = pygame.mixer.Sound(resource_path("config/son.wav"))
        except Exception as e:
            logging.debug(f"Impossible d'initialiser le son: {e}")
            self.sound_effect = None

    def play_accept_sound(self) -> None:
        if not self.sound_effect:
            return
        try:
            self.sound_effect.play()
        except Exception as e:
            logging.debug(f"Impossible de jouer le son d'accept: {e}")

    def shutdown(self) -> None:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception as e:
            logging.debug(f"Erreur arret mixer pygame: {e}")
