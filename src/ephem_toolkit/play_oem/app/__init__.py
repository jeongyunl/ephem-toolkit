"""Play-oem wx application package."""

from .player_app import PlayerApp
from .player_app_support import (
    DEFAULT_TICK_INTERVAL_MS,
    ELAPSED_TIME_DECIMAL_PLACES,
    EMPTY_DATA_VIEW_LABEL,
    EMPTY_DATA_VIEW,
    PLAYER_FRAME_MIN_SIZE,
    PLAYER_FRAME_SIZE,
)

__all__ = [
    "DEFAULT_TICK_INTERVAL_MS",
    "ELAPSED_TIME_DECIMAL_PLACES",
    "EMPTY_DATA_VIEW_LABEL",
    "EMPTY_DATA_VIEW",
    "PLAYER_FRAME_MIN_SIZE",
    "PLAYER_FRAME_SIZE",
    "PlayerApp",
]
