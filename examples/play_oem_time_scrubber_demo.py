"""Compact TimeScrubber demo.

Run with::

    PYTHONPATH=src python examples/play_oem_time_scrubber_demo.py

This demo follows the horizontal TimeScrubber layout:

- a default full-coverage TimeScrubber;
- a range-limited TimeScrubber with a narrower visible interval;
- compact left/right pan controls shared with `play-oem`;
- live tick labels and a current-time marker;
- vertical wheel zooms around the pointer; horizontal wheel pans the visible viewport;
- double-click or the keyboard fit command to restore full OEM coverage.

The shared ``TimeScrubberWidget`` supplies the pan controls, tick rail, range handles,
seek thumb, and viewport behavior used by ``play-oem``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import wx

from ephem_toolkit.core import time_utils
from ephem_toolkit.core.app_utils import activate_application
from ephem_toolkit.play_oem import time_range
from ephem_toolkit.play_oem.display_time import format_tt
from ephem_toolkit.play_oem.workspace.time_scrubber import (
    TimeScrubberWidget,
)


COVERAGE = (
    time_utils.datetime_to_tt_s(
        datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)
    ),
    time_utils.datetime_to_tt_s(
        datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)
    ),
)
PLAYBACK = (
    time_utils.datetime_to_tt_s(
        datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)
    ),
    time_utils.datetime_to_tt_s(
        datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc)
    ),
)
NOW = time_utils.datetime_to_tt_s(
    datetime(2026, 10, 13, 0, 0, tzinfo=timezone.utc)
)


def bring_frame_forward(frame: wx.Frame) -> None:
    """Raise and activate a top-level frame after the wx event loop opens it."""
    frame.Show()
    frame.Iconize(False)
    frame.Raise()
    frame.SetFocus()
    activate_application()

    wx.CallAfter(frame.Raise)


class TimeScrubberCard(wx.Panel):
    """One compact TimeScrubber instance, modeled after the supplied screenshot."""

    def __init__(
        self,
        parent: wx.Window,
        title: str,
        initial_viewport: tuple[float, float],
        on_state,
    ) -> None:
        super().__init__(parent)
        self._on_state = on_state
        self._viewport = initial_viewport
        self._demo_playback = PLAYBACK
        self._demo_now = NOW
        self._plot_rule = time_range.PlotTimeRange(
            True,
            time_range.TimeRangeEndpoint(
                "fixed",
                time_utils.datetime_to_tt_s(
                    datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
                ),
            ),
            time_range.TimeRangeEndpoint(
                "fixed",
                time_utils.datetime_to_tt_s(
                    datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)
                ),
            ),
        )
        layout = wx.BoxSizer(wx.VERTICAL)
        title_text = wx.StaticText(self, label=title)
        title_font = title_text.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title_text.SetFont(title_font)
        layout.Add(title_text, 0, wx.BOTTOM, 10)

        self.current_label = wx.StaticText(
            self,
            label=format_tt(NOW, "UTC", fractional_second_places=0),
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        current_font = self.current_label.GetFont()
        current_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.current_label.SetFont(current_font)
        layout.Add(
            self.current_label,
            0,
            wx.ALIGN_CENTRE_HORIZONTAL | wx.BOTTOM,
            4,
        )

        self.scrubber = TimeScrubberWidget(
            self,
            coverage=COVERAGE,
            playback=self._demo_playback,
            plot_rule=self._plot_rule,
            now_s=self._demo_now,
            viewport=initial_viewport,
            on_playback=self._on_playback,
            on_plot_endpoint=self._on_plot_endpoint,
            on_plot_endpoint_mode=lambda _name, _mode: None,
            on_begin_edit=lambda: None,
            on_range_dragging=lambda _dragging: None,
            on_viewport=self._set_viewport,
        )
        self.slider = self.scrubber.slider
        self.ticks = self.scrubber.tick_rail
        self.slider.Bind(wx.EVT_SLIDER, self._on_slider)
        layout.Add(self.scrubber, 0, wx.EXPAND)
        layout.Add(
            wx.StaticText(
                self,
                label="Vertical wheel: zoom  •  Horizontal wheel: pan  •  Double-click: full OEM",
                style=wx.ALIGN_CENTRE_HORIZONTAL,
            ),
            0,
            wx.EXPAND | wx.TOP,
            8,
        )

        self.SetSizer(layout)
        self.Layout()

    def _set_viewport(self, viewport: tuple[float, float]) -> None:
        self._viewport = viewport
        self._on_state(viewport)

    def _on_slider(self, event: wx.CommandEvent) -> None:
        fraction = event.GetInt() / 10_000
        start_s, end_s = self._viewport
        timestamp = start_s + fraction * (end_s - start_s)
        timestamp = min(max(timestamp, PLAYBACK[0]), PLAYBACK[1])
        self.slider.seek_to_fraction(fraction)
        self.current_label.SetLabel(
            format_tt(timestamp, "UTC", fractional_second_places=0)
        )
        event.Skip()

    def _on_playback(self, start_s: float, end_s: float) -> None:
        self._demo_playback = (
            min(max(start_s, COVERAGE[0]), COVERAGE[1]),
            min(max(end_s, COVERAGE[0]), COVERAGE[1]),
        )
        self.slider.set_state(playback=self._demo_playback)

    def _on_plot_endpoint(self, name: str, value_s: float) -> None:
        endpoint = time_range.TimeRangeEndpoint("fixed", value_s)
        if name == "start":
            self._plot_rule = time_range.PlotTimeRange(
                True,
                endpoint,
                self._plot_rule.end,
            )
        else:
            self._plot_rule = time_range.PlotTimeRange(
                True,
                self._plot_rule.start,
                endpoint,
            )
        self.slider.set_state(plot_rule=self._plot_rule)

class TimeScrubberDemoFrame(wx.Frame):
    def __init__(self) -> None:
        super().__init__(
            None,
            title="TimeScrubber",
            size=(820, 570),
        )

        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        heading = wx.StaticText(panel, label="TimeScrubber")
        heading_font = heading.GetFont()
        heading_font.MakeBold()
        heading_font.SetPointSize(max(18, heading_font.GetPointSize() + 8))
        heading.SetFont(heading_font)
        layout.Add(heading, 0, wx.ALL, 18)

        self.default_card = wx.Panel(panel)
        self.default_card.SetBackgroundColour(wx.Colour("#ffffff"))
        default_layout = wx.BoxSizer(wx.VERTICAL)
        default_layout.Add(
            TimeScrubberCard(
                self.default_card,
                "Default",
                COVERAGE,
                lambda _viewport: None,
            ),
            1,
            wx.EXPAND | wx.ALL,
            14,
        )
        self.default_card.SetSizer(default_layout)
        layout.Add(self.default_card, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 18)

        layout.AddSpacer(14)

        self.limited_card = wx.Panel(panel)
        self.limited_card.SetBackgroundColour(wx.Colour("#ffffff"))
        limited_layout = wx.BoxSizer(wx.VERTICAL)
        range_viewport = (
            time_utils.datetime_to_tt_s(
                datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)
            ),
            time_utils.datetime_to_tt_s(
                datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)
            ),
        )
        limited_layout.Add(
            TimeScrubberCard(
                self.limited_card,
                "Range-Limited",
                range_viewport,
                lambda _viewport: None,
            ),
            1,
            wx.EXPAND | wx.ALL,
            14,
        )
        self.limited_card.SetSizer(limited_layout)
        layout.Add(self.limited_card, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 18)

        panel.SetSizer(layout)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Centre()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        """Handle viewport commands regardless of which demo control has focus."""
        control_down = event.ControlDown()
        command_down = getattr(event, "CmdDown", lambda: False)()
        if not (control_down or command_down):
            event.Skip()
            return

        key = event.GetKeyCode()
        unicode_key = ""
        if hasattr(event, "GetUnicodeKey"):
            unicode_key = event.GetUnicodeKey()
            if isinstance(unicode_key, int):
                unicode_key = chr(unicode_key) if 32 <= unicode_key <= 126 else ""
        character = unicode_key or (
            chr(key) if isinstance(key, int) and 32 <= key <= 126 else ""
        )

        cards = (
            getattr(self, "default_card", None),
            getattr(self, "limited_card", None),
        )
        sliders = []
        for panel in cards:
            if panel is None:
                continue
            card = panel.GetSizer().GetChildren()[0].GetWindow()
            sliders.append(card.slider)

        if key in (ord("0"),) or character == "0":
            for slider in sliders:
                slider.fit()
        elif key in (ord("+"), ord("="), wx.WXK_ADD) or character in ("+", "="):
            for slider in sliders:
                slider.zoom_in()
        elif key in (ord("-"), wx.WXK_SUBTRACT) or character == "-":
            for slider in sliders:
                slider.zoom_out()
        else:
            event.Skip()
            return


if __name__ == "__main__":
    app = wx.App(False)
    frame = TimeScrubberDemoFrame()
    app.SetTopWindow(frame)
    bring_frame_forward(frame)
    app.MainLoop()
