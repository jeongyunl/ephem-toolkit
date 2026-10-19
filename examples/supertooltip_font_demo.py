"""Demonstrate a smaller message font with wx.lib.agw.SuperToolTip.

Run with ``python examples/supertooltip_font_demo.py`` and hover over the
button. This is a standalone check of SuperToolTip's message font control.
"""

from __future__ import annotations

import wx
from wx.lib.agw.supertooltip import SuperToolTip


class SuperToolTipFontDemo(wx.Frame):
    def __init__(self) -> None:
        super().__init__(None, title="SuperToolTip font check", size=(460, 180))
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(
            panel,
            label="Hover over the button to see the smaller tooltip message.",
        )
        button = wx.Button(panel, label="Hover here")
        tooltip = SuperToolTip(
            "This message uses a smaller font set with SetMessageFont().",
            header="SuperToolTip example",
        )
        tooltip.SetMessageFont(wx.Font(
            8,
            wx.FONTFAMILY_DEFAULT,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL,
        ))
        # wxPython truncates this delay to whole seconds; zero fails to start its timer.
        tooltip.SetStartDelay(1)
        tooltip.SetTarget(button)

        # Keep a reference for the lifetime of the target window.
        self._tooltip = tooltip

        layout.AddStretchSpacer()
        layout.Add(label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 16)
        layout.Add(button, 0, wx.ALIGN_CENTER)
        layout.AddStretchSpacer()
        panel.SetSizer(layout)
        self.Centre()


if __name__ == "__main__":
    app = wx.App(False)
    frame = SuperToolTipFontDemo()
    frame.Show()
    app.MainLoop()
