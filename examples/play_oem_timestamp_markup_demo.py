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
            wx.StaticText(
                panel,
                label="Current UTC (click the value to edit; press Enter to apply)",
            ),
            0,
        )
        current_utc_row = wx.BoxSizer(wx.HORIZONTAL)
        self.current_utc_prefix = wx.StaticText(panel, label="Current UTC:")
        current_utc_row.Add(
            self.current_utc_prefix, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4
        )
        self.current_utc_host = wx.Panel(panel)
        self.current_utc_label = wx.StaticText(self.current_utc_host, label="")
        set_timestamp_label(self.current_utc_label, TIMESTAMP)
        self.current_utc_label.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.current_utc_label.Bind(wx.EVT_LEFT_UP, self._begin_edit)
        self.current_utc_entry = wx.TextCtrl(
            self.current_utc_host, value=TIMESTAMP, style=wx.TE_PROCESS_ENTER
        )
        self.current_utc_entry.Hide()
        self.current_utc_entry.Bind(wx.EVT_TEXT_ENTER, self._finish_edit)
        self.current_utc_entry.Bind(wx.EVT_KILL_FOCUS, self._finish_edit)
        label_size = self.current_utc_label.GetBestSize()
        entry_size = self.current_utc_entry.GetBestSize()
        self.current_utc_host.SetMinSize(
            (
                max(label_size.width, entry_size.width),
                max(label_size.height, entry_size.height),
            )
        )
        self.current_utc_host.Bind(wx.EVT_SIZE, self._size_current_utc_controls)
        current_utc_row.Add(self.current_utc_host, 0, wx.TOP, 10)
        layout.Add(current_utc_row, 0, wx.BOTTOM, 10)

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

    def _begin_edit(self, _event: wx.MouseEvent) -> None:
        self.current_utc_label.Hide()
        self.current_utc_entry.Show()
        self.current_utc_entry.SetFocus()
        self.current_utc_entry.SelectAll()
        self.Layout()

    def _size_current_utc_controls(self, event: wx.SizeEvent) -> None:
        size = self.current_utc_host.GetClientSize()
        entry_height = min(size.height, self.current_utc_entry.GetBestSize().height)
        entry_y = size.height - entry_height
        self.current_utc_label.SetPosition((0, 0))
        self.current_utc_entry.SetPosition((0, entry_y))
        self.current_utc_label.SetSize(size)
        self.current_utc_entry.SetSize((size.width, entry_height))
        event.Skip()

    def _finish_edit(self, event: wx.Event) -> None:
        if self.current_utc_entry.IsShown():
            timestamp = self.current_utc_entry.GetValue()
            set_timestamp_label(self.current_utc_label, timestamp)
            self.current_utc_entry.Hide()
            self.current_utc_label.Show()
            self.Layout()
        event.Skip()


if __name__ == "__main__":
    app = wx.App(False)
    frame = TimestampMarkupDemo()
    frame.Show()
    app.MainLoop()
