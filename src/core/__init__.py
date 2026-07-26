"""
FILE NAME: src/core/__init__.py
GLOBAL PURPOSE:
- Provide the public API for the core runtime layer.
- Re-export the main core classes used by launcher and UI modules.
- Keep import sites independent from the internal file layout of the core package.

KEY FUNCTIONS:
- None.

AUDIENCE & LOGIC:
Why:
This package facade keeps the core layer easy to import from a single location.
For whom:
Developers importing the main core runtime classes.

DEPENDENCIES:
Used by:
- launcher.py and modules importing core classes from `src.core`.
Uses:
- Local modules: src.core.datadragon, src.core.game_state, src.core.websocket
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .datadragon import DataDragon
    from .game_state import GameState
    from .websocket import WebSocketManager

__all__ = ["DataDragon", "GameState", "WebSocketManager"]


def __getattr__(name: str):
    """Load public core classes only when a caller requests them."""
    if name == "DataDragon":
        from .datadragon import DataDragon

        return DataDragon
    if name == "GameState":
        from .game_state import GameState

        return GameState
    if name == "WebSocketManager":
        from .websocket import WebSocketManager

        return WebSocketManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
