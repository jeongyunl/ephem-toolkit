"""Preview fractional-second markup in play-oem timestamp controls.

Run with ``python examples/play_oem_timestamp_markup_demo.py``.
"""

from __future__ import annotations

import wx
from wx.lib.agw.supertooltip import SuperToolTip

from ephem_toolkit.play_oem.timestamp_markup import set_timestamp_label

TIMESTAMP = "2026-10-19T19:41:40.501Z"


class TimestampMarkupDemo(wx.Frame):
    def __init__(self) -> None:
        super().__init__(None, title="Timestamp markup preview", size=(760, 380))
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        layout.Add(
            wx.StaticText(panel, label="Start UTC (StaticText; smaller fraction)"),
            0,
            wx.TOP,
            12,
        )
        self.start_label = wx.StaticText(panel, label="")
        set_timestamp_label(self.start_label, TIMESTAMP)
        layout.Add(self.start_label, 0, wx.BOTTOM, 10)

        layout.Add(
            wx.StaticText(panel, label="End UTC (StaticText; smaller fraction)"),
            0,
        )
        self.end_label = wx.StaticText(panel, label="")
        set_timestamp_label(self.end_label, TIMESTAMP)
        layout.Add(self.end_label, 0, wx.BOTTOM, 10)

        layout.Add(
            wx.StaticText(panel, label="Playback UTC readout (multiline StaticText)"),
            0,
        )
        self.playback_label = wx.StaticText(panel, label="")
        set_timestamp_label(self.playback_label, f"Elapsed: 12.345 s\nUTC: {TIMESTAMP}")
        layout.Add(self.playback_label, 0, wx.BOTTOM, 10)

        layout.Add(
            wx.StaticText(panel, label="Editable timeline time (uniform font)"),
            0,
        )
        self.time_entry = wx.TextCtrl(panel, value=TIMESTAMP)
        layout.Add(self.time_entry, 0, wx.EXPAND | wx.BOTTOM, 10)

        layout.Add(
            wx.StaticText(panel, label="SuperToolTip (uniform font; hover below)"),
            0,
        )
        self.tooltip_target = wx.Button(
            panel, label="Hover to preview timestamp tooltip"
        )
        self._tooltip = SuperToolTip(f"Current UTC: {TIMESTAMP}")
        self._tooltip.SetStartDelay(1)
        self._tooltip.SetTarget(self.tooltip_target)
        layout.Add(self.tooltip_target, 0, wx.BOTTOM, 10)

        panel.SetSizer(layout)
        self.Centre()


if __name__ == "__main__":
    app = wx.App(False)
    frame = TimestampMarkupDemo()
    frame.Show()
    app.MainLoop()
