"""Check native wx tooltip updates over a horizontal timeline slider.

Run with ``python examples/play_oem_timeline_tooltip.py`` and move the pointer
across the slider. The label confirms that motion events are being received;
the native tooltip should show the same time after its normal hover delay.

Use ``--refresh-ms 33`` to reproduce the application's periodic slider writes,
then add ``--skip-unchanged`` to compare without redundant native updates.
Use ``PYTHONPATH=src python examples/play_oem_timeline_tooltip.py --workspace
--refresh-ms 33`` to exercise the actual workspace, including transport updates.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import wx

SLIDER_MAX = 10_000
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SPAN = timedelta(days=30)


class TimelineTooltipDemo(wx.Frame):
    """Minimal slider with a dynamic native tooltip and visible hover readout."""

    def __init__(self, refresh_ms: int = 0, skip_unchanged: bool = False) -> None:
        super().__init__(None, title="Timeline tooltip check", size=(640, 160))
        self._skip_unchanged = skip_unchanged
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        self.slider = wx.Slider(
            panel, wx.ID_ANY, 0, 0, SLIDER_MAX, style=wx.SL_HORIZONTAL
        )
        self.readout = wx.StaticText(
            panel, wx.ID_ANY, "Move the pointer over the slider"
        )
        self.tooltip = wx.ToolTip(self._time_at(0.0))
        wx.ToolTip.Enable(True)
        self.slider.SetToolTip(self.tooltip)
        self.slider.Bind(wx.EVT_MOTION, self._on_motion)
        layout.Add(self.slider, 0, wx.EXPAND | wx.ALL, 20)
        layout.Add(self.readout, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        panel.SetSizer(layout)
        self.Centre()
        if refresh_ms > 0:
            self._timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_refresh, self._timer)
            self._timer.Start(refresh_ms)

    def _on_refresh(self, _event: wx.TimerEvent) -> None:
        value = self.slider.GetValue()
        if not self._skip_unchanged:
            self.slider.SetValue(value)

    @staticmethod
    def _time_at(fraction: float) -> str:
        moment = START + fraction * SPAN
        return moment.isoformat(timespec="seconds").replace("+00:00", "Z")

    def _on_motion(self, event: wx.MouseEvent) -> None:
        width = self.slider.GetClientSize().GetWidth()
        if width > 0:
            fraction = min(max(event.GetX() / width, 0.0), 1.0)
            display_time = self._time_at(fraction)
            self.tooltip.SetTip(display_time)
            self.readout.SetLabel(f"Pointer time: {display_time}")
        event.Skip()


class WorkspaceTooltipDemo(wx.Frame):
    """Exercise the actual timeline and transport controls without orbit data."""

    def __init__(self, refresh_ms: int) -> None:
        from ephem_toolkit.play_oem.workspace import Workspace

        super().__init__(None, title="Workspace tooltip check", size=(1100, 700))
        self.workspace = Workspace(
            self,
            lambda _fraction: None,
            timeline_enabled=True,
            timeline_start_utc=TimelineTooltipDemo._time_at(0.0),
            timeline_end_utc=TimelineTooltipDemo._time_at(1.0),
            timeline_tooltip_at=TimelineTooltipDemo._time_at,
        )
        self._on_refresh(None)
        if refresh_ms > 0:
            self._timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_refresh, self._timer)
            self._timer.Start(refresh_ms)
        self.Centre()

    def _on_refresh(self, _event: wx.TimerEvent | None) -> None:
        self.workspace.update_timeline(0.5, TimelineTooltipDemo._time_at(0.5))
        self.workspace.update_transport_state(False, 1.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-ms", type=int, default=0)
    parser.add_argument("--skip-unchanged", action="store_true")
    parser.add_argument("--workspace", action="store_true")
    args = parser.parse_args()
    app = wx.App(False)
    if args.workspace:
        window = WorkspaceTooltipDemo(args.refresh_ms)
    else:
        window = TimelineTooltipDemo(args.refresh_ms, args.skip_unchanged)
    window.Show()
    app.MainLoop()
