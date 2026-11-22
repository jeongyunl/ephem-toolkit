"""Compact TimeScrubber demo.

Run with::

    PYTHONPATH=src python examples/play_oem_time_scrubber_demo.py

This demo follows the horizontal TimeScrubber layout:

- a default full-coverage TimeScrubber;
- a range-limited TimeScrubber with a narrower visible interval;
- compact left/right pan controls;
- live tick labels and a current-time marker;
- vertical wheel zooms around the pointer; horizontal wheel pans the visible viewport;
- double-click or the keyboard fit command to restore full OEM coverage.

The range handles, seek thumb, and all pointer/keyboard event behavior come from the
existing ``TimeSlider`` widget.
"""

from __future__ import annotations

from datetime import datetime, timezone

import wx

from ephem_toolkit.core import time_utils
from ephem_toolkit.core.app_utils import activate_application
from ephem_toolkit.play_oem import time_range
from ephem_toolkit.play_oem.display_time import format_tt
from ephem_toolkit.play_oem.workspace.time_scrubber import (
    TimeScrubber,
    TimeScrubberTickRail,
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


class ChevronButton(wx.Control):
    """Painted, high-contrast edge chevron with a real clickable hit target."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        tooltip: str,
        callback,
    ) -> None:
        super().__init__(
            parent,
            wx.ID_ANY,
            size=wx.Size(30, 52),
            style=wx.WANTS_CHARS,
        )
        self._label = label
        self._callback = callback
        self.SetName(f"Pan {tooltip}")
        self.SetToolTip(tooltip)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_LEFT_UP, self._click)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda _event: self.Refresh())
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda _event: self.Refresh())

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(wx.Colour("#fafafa")))
        dc.Clear()
        width, height = self.GetClientSize()
        enabled = self.IsEnabled()
        border_color = wx.Colour("#cfd6df") if enabled else wx.Colour("#e3e6ea")
        dc.SetBrush(wx.Brush(wx.Colour("#fafafa")))
        dc.SetPen(wx.Pen(border_color, 1))
        dc.DrawRoundedRectangle(1, 1, width - 2, height - 2, 5)
        dc.SetTextForeground(wx.Colour("#4a5564") if enabled else wx.Colour("#abb3bc"))
        font = dc.GetFont()
        font.SetPointSize(max(font.GetPointSize(), 18))
        dc.SetFont(font)
        text_width, text_height = dc.GetTextExtent(self._label)
        dc.DrawText(
            self._label,
            (width - text_width) // 2,
            (height - text_height) // 2,
        )

    def _click(self, event: wx.MouseEvent) -> None:
        if self.IsEnabled():
            self._callback()
            self.Refresh()
        event.Skip(False)


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

        rail_row = wx.BoxSizer(wx.HORIZONTAL)
        self.left_button = ChevronButton(
            self,
            "<",
            "Pan earlier",
            lambda: self._pan(-0.10),
        )

        center = wx.BoxSizer(wx.VERTICAL)
        self.current_label = wx.StaticText(
            self,
            label=format_tt(NOW, "UTC", fractional_second_places=0),
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        current_font = self.current_label.GetFont()
        current_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.current_label.SetFont(current_font)
        center.Add(self.current_label, 0, wx.ALIGN_CENTRE_HORIZONTAL | wx.BOTTOM, 4)

        self.slider = TimeScrubber(
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
        self.slider.Bind(wx.EVT_SLIDER, self._on_slider)
        center.Add(self.slider, 0, wx.EXPAND)

        self.ticks = TimeScrubberTickRail(self)
        self.ticks.set_viewport(initial_viewport)
        self.ticks.set_wheel_handler(self.slider._mouse_wheel)
        self.ticks.set_pan_handler(self.slider.pan)
        center.Add(self.ticks, 0, wx.EXPAND)

        rail_row.Add(self.left_button, 0, wx.ALIGN_CENTER_VERTICAL)
        rail_row.Add(center, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 0)

        self.right_button = ChevronButton(
            self,
            ">",
            "Pan later",
            lambda: self._pan(0.10),
        )
        rail_row.Add(self.right_button, 0, wx.ALIGN_CENTER_VERTICAL)

        layout.Add(rail_row, 0, wx.EXPAND)
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
        self._update_pan_buttons(self._viewport)
        self.Layout()

    def _set_viewport(self, viewport: tuple[float, float]) -> None:
        self._viewport = viewport
        if hasattr(self, "ticks"):
            self.ticks.set_viewport(viewport)
        self._update_pan_buttons(viewport)
        self._on_state(viewport)

    def _update_pan_buttons(self, viewport: tuple[float, float]) -> None:
        if not hasattr(self, "left_button") or not hasattr(self, "right_button"):
            return
        start_s, end_s = viewport
        coverage_start, coverage_end = COVERAGE
        epsilon = 1e-6
        self.left_button.Enable(start_s > coverage_start + epsilon)
        self.right_button.Enable(end_s < coverage_end - epsilon)
        self.left_button.SetCursor(
            wx.Cursor(wx.CURSOR_HAND if self.left_button.IsEnabled() else wx.CURSOR_ARROW)
        )
        self.right_button.SetCursor(
            wx.Cursor(wx.CURSOR_HAND if self.right_button.IsEnabled() else wx.CURSOR_ARROW)
        )

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

    def _pan(self, fraction: float) -> None:
        self.slider.pan(fraction)


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
