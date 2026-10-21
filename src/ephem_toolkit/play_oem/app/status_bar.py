"""Customizable status bar for the OEM playback window."""

from __future__ import annotations

import wx


class PlaybackStatusBar(wx.Panel):
    """Show file and object identity with room for messages and custom controls."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, wx.ID_ANY)

        self.file_value = wx.StaticText(self, wx.ID_ANY, "No file loaded")
        self.object_value = wx.StaticText(self, wx.ID_ANY, "")
        self.message_value = wx.StaticText(self, wx.ID_ANY, "")
        for value in (self.file_value, self.object_value):
            font = value.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            value.SetFont(font)

        self.actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(
            wx.StaticText(self, wx.ID_ANY, "File:"),
            0,
            wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            10,
        )
        row.Add(self.file_value, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 12)
        row.Add(
            wx.StaticText(self, wx.ID_ANY, "Object:"),
            0,
            wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            12,
        )
        row.Add(self.object_value, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 6)
        row.Add(self.message_value, 1, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 12)
        row.Add(self.actions_sizer, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 8)
        row.SetMinSize((-1, 28))

        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticLine(self, wx.ID_ANY), 0, wx.EXPAND)
        layout.Add(row, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 4)
        self.SetSizer(layout)

    def set_file_name(self, file_name: str | None) -> None:
        """Update the displayed filename."""
        self.file_value.SetLabel(file_name or "No file loaded")
        self.Layout()

    def set_object(self, object_name: str, object_id: str = "") -> None:
        """Update the displayed object name and optional ID."""
        object_label = f"{object_name} ({object_id})" if object_id else object_name
        self.object_value.SetLabel(object_label)
        self.Layout()

    def set_message(self, message: str) -> None:
        """Show a transient status message without replacing file identity."""
        self.message_value.SetLabel(message)
        self.Layout()

    def add_action(self, control: wx.Window) -> None:
        """Add a button, icon control, or other widget at the right edge."""
        if control.GetParent() is not self:
            control.Reparent(self)
        self.actions_sizer.Add(control, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 4)
        self.Layout()
