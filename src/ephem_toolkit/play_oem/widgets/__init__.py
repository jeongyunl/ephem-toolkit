"""Reusable custom controls for the play-oem interface."""

from .floating_matplotlib_legend import FloatingMatplotlibLegend
from .floating_panel import FloatingPanel, PanelCorner, PanelInteraction
from .matplotlib_panel import MatplotlibPanel
from .playback_time_scrubber import (
    DEFAULT_CHEVRON_HEIGHT,
    DEFAULT_CHEVRON_WIDTH,
    ChevronButton,
    PlaybackTimeScrubber,
    PlaybackTimeScrubberWidget,
    TimeTickRail,
)
from .playback_time_slider import PlaybackTimeSlider
from .themed_toggle_button import ThemedToggleButton
from .time_slider import TimeSlider
from .track_slider import TrackSlider

__all__ = [
    "ChevronButton",
    "DEFAULT_CHEVRON_HEIGHT",
    "DEFAULT_CHEVRON_WIDTH",
    "ThemedToggleButton",
    "PlaybackTimeScrubber",
    "PlaybackTimeScrubberWidget",
    "PlaybackTimeSlider",
    "TrackSlider",
    "TimeSlider",
    "TimeTickRail",
    "FloatingPanel",
    "FloatingMatplotlibLegend",
    "PanelCorner",
    "PanelInteraction",
    "MatplotlibPanel",
]
