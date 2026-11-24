"""Show the play-oem time controls in class hierarchy order.

Run with::

    PYTHONPATH=src python examples/play_oem_time_scrubber_demo.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import wx

from ephem_toolkit.core import time_utils
from ephem_toolkit.core.app_utils import activate_application
from ephem_toolkit.play_oem import time_range
from ephem_toolkit.play_oem.widgets.playback_time_scrubber import (
    PlaybackTimeScrubber,
    PlaybackTimeScrubberWidget,
)
from ephem_toolkit.play_oem.widgets.playback_time_slider import PlaybackTimeSlider
from ephem_toolkit.play_oem.widgets.track_slider import TrackSlider
from ephem_toolkit.play_oem.widgets.time_slider import TimeSlider


COVERAGE = (
    time_utils.datetime_to_tt_s(datetime(2026, 9, 23, tzinfo=timezone.utc)),
    time_utils.datetime_to_tt_s(datetime(2026, 10, 23, tzinfo=timezone.utc)),
)
PLAYBACK = (
    time_utils.datetime_to_tt_s(datetime(2026, 9, 25, tzinfo=timezone.utc)),
    time_utils.datetime_to_tt_s(datetime(2026, 10, 21, tzinfo=timezone.utc)),
)
NOW = time_utils.datetime_to_tt_s(datetime(2026, 10, 13, tzinfo=timezone.utc))
PLOT_RULE = time_range.PlotTimeRange(
    True,
    time_range.TimeRangeEndpoint("fixed", PLAYBACK[0] + 3 * 86_400),
    time_range.TimeRangeEndpoint("fixed", PLAYBACK[1] - 3 * 86_400),
)


def slider_value(timestamp: float, bounds: tuple[float, float]) -> int:
    """Map a timestamp into the sliders' normalized value range."""
    start, end = bounds
    fraction = 0.0 if end <= start else (timestamp - start) / (end - start)
    return round(min(max(fraction, 0.0), 1.0) * 10_000)


def bring_frame_forward(frame: wx.Frame) -> None:
    """Raise and activate a top-level frame after the wx event loop opens it."""
    frame.Show()
    frame.Iconize(False)
    frame.Raise()
    frame.SetFocus()
    activate_application()
    wx.CallAfter(frame.Raise)


class TimeControlsDemoFrame(wx.Frame):
    """Display each time control vertically from base to most specialized."""

    def __init__(self) -> None:
        super().__init__(None, title="Playback time controls", size=(900, 560))
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.AddSpacer(14)

        track_slider = TrackSlider(panel)
        track_slider.SetValue(slider_value(NOW, COVERAGE))
        self._add_control(layout, panel, "TrackSlider", track_slider)

        time_slider = TimeSlider(panel)
        time_slider.set_time_bounds(COVERAGE, NOW)
        self._add_control(layout, panel, "TimeSlider", time_slider)

        playback_slider = PlaybackTimeSlider(
            panel,
            on_playback=lambda _start, _end: None,
            on_plot_endpoint=lambda _name, _value: None,
            on_plot_endpoint_mode=lambda _name, _mode: None,
            on_begin_edit=lambda: None,
        )
        playback_slider.set_ranges(COVERAGE, PLAYBACK, PLOT_RULE, NOW)
        playback_slider.SetValue(slider_value(NOW, COVERAGE))
        self._add_control(layout, panel, "PlaybackTimeSlider", playback_slider)

        playback_scrubber = PlaybackTimeScrubber(
            panel,
            coverage=COVERAGE,
            playback=PLAYBACK,
            plot_rule=PLOT_RULE,
            now_s=NOW,
            viewport=COVERAGE,
            on_playback=lambda _start, _end: None,
            on_plot_endpoint=lambda _name, _value: None,
        )
        playback_scrubber.SetValue(slider_value(NOW, COVERAGE))
        self._add_control(layout, panel, "PlaybackTimeScrubber", playback_scrubber)

        scrubber_widget = PlaybackTimeScrubberWidget(
            panel,
            coverage=COVERAGE,
            playback=PLAYBACK,
            plot_rule=PLOT_RULE,
            now_s=NOW,
            viewport=COVERAGE,
            on_playback=lambda _start, _end: None,
            on_plot_endpoint=lambda _name, _value: None,
        )
        scrubber_widget.slider.SetValue(slider_value(NOW, COVERAGE))
        self._add_control(
            layout,
            panel,
            "PlaybackTimeScrubberWidget",
            scrubber_widget,
        )

        layout.AddSpacer(14)
        panel.SetSizer(layout)
        layout.SetSizeHints(panel)
        frame_layout = wx.BoxSizer(wx.VERTICAL)
        frame_layout.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_layout)
        frame_layout.Fit(self)
        frame_layout.SetSizeHints(self)
        self.Centre()

    @staticmethod
    def _add_control(
        layout: wx.BoxSizer,
        parent: wx.Window,
        class_name: str,
        control: wx.Window,
    ) -> None:
        caption = wx.StaticText(parent, label=class_name)
        layout.Add(caption, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        layout.Add(control, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)


if __name__ == "__main__":
    app = wx.App(False)
    frame = TimeControlsDemoFrame()
    app.SetTopWindow(frame)
    bring_frame_forward(frame)
    app.MainLoop()
