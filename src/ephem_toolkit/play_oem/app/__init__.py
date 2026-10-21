"""Play-oem wx application package."""

from .controller import PlayerApp
from .support import (
    DEFAULT_TICK_INTERVAL_MS,
    ELAPSED_TIME_DECIMAL_PLACES,
    EMPTY_GRAPH_LABEL,
    EMPTY_GRAPH_VIEW,
    PLAYER_FRAME_MIN_SIZE,
    PLAYER_FRAME_SIZE,
)

__all__ = [
    "DEFAULT_TICK_INTERVAL_MS",
    "ELAPSED_TIME_DECIMAL_PLACES",
    "EMPTY_GRAPH_LABEL",
    "EMPTY_GRAPH_VIEW",
    "PLAYER_FRAME_MIN_SIZE",
    "PLAYER_FRAME_SIZE",
    "PlayerApp",
]
