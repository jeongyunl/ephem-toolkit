"""Time-valued seek track without playback or plot range handles."""

from __future__ import annotations

from collections.abc import Callable

import wx

from ..display_time import UTC_DISPLAY, format_tt
from .track_slider import TrackSlider


class TimeSlider(TrackSlider):
    """Seek slider whose values map onto a time interval."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        minimum: int = 0,
        maximum: int = 10_000,
        timeline_tooltip_at: Callable[[float], str] | None = None,
    ) -> None:
        tooltip_at = timeline_tooltip_at or self._default_timeline_tooltip_at
        super().__init__(
            parent,
            minimum=minimum,
            maximum=maximum,
            tooltip_at=tooltip_at,
        )
        self.SetName("Time slider")
        self._slider_bounds = (0.0, 1.0)
        self._now = 0.0
        self._display_time_zone = UTC_DISPLAY

    @property
    def _time_slider_state_set(self) -> bool:
        """Compatibility name for time-based subclasses of this control."""
        return self._value_is_set

    def SetValue(self, value: int) -> None:
        super().SetValue(value)
        start, end = self._slider_bounds
        if end > start:
            self._now = start + self._value_fraction() * (end - start)

    def set_time_bounds(self, bounds: tuple[float, float], now_s: float) -> None:
        """Set the time interval represented by the track and its current time."""
        self._slider_bounds = bounds
        self._now = min(max(now_s, bounds[0]), bounds[1])
        if bounds[1] > bounds[0]:
            fraction = (self._now - bounds[0]) / (bounds[1] - bounds[0])
            value = round(
                self._minimum + fraction * (self._maximum - self._minimum)
            )
            self.SetValue(value)
        else:
            self.SetValue(self._minimum)

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        if self._pointer_position is not None:
            self._track_tooltip.SetMessage(
                self._tooltip_at(self._pointer_fraction())
            )

    def is_pointer_over_timeline_track(self, position: wx.Point) -> bool:
        """Keep the time-slider name for callers that inspect the track area."""
        return self.is_pointer_over_track(position)

    def _x_for(self, timestamp: float) -> int:
        start, end = self._slider_bounds
        fraction = 0.0 if end <= start else (timestamp - start) / (end - start)
        return self._x_for_fraction(fraction)

    def _draw_seek_marker(self, dc: wx.DC, height: int) -> None:
        if not self._value_is_set or not (
            self._slider_bounds[0] <= self._now <= self._slider_bounds[1]
        ):
            return
        highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        dc.SetPen(wx.Pen(highlight, 2))
        dc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        dc.DrawCircle(self._x_for(self._now), height // 2 - 2, 6)

    def _default_timeline_tooltip_at(self, fraction: float) -> str:
        start, end = self._slider_bounds
        timestamp = start + min(max(fraction, 0.0), 1.0) * (end - start)
        try:
            return format_tt(
                timestamp,
                self._display_time_zone,
                fractional_second_places=0,
            )
        except (AttributeError, TypeError, OverflowError, ValueError):
            return ""
