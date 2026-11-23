"""Reusable rounded toggle buttons using the active system color theme."""

from __future__ import annotations

import wx
from wx.lib.platebtn import (
    PB_STYLE_DEFAULT,
    PB_STYLE_TOGGLE,
    PLATE_HIGHLIGHT,
    PLATE_NORMAL,
    PLATE_PRESSED,
    PlateButton,
)


class ThemedToggleButton(PlateButton):
    """Rounded toggle button with neutral idle, hover, and selected colors."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        *,
        id: int = wx.ID_ANY,
        idle_color: wx.Colour | None = None,
        hover_color: wx.Colour | None = None,
        active_color: wx.Colour | None = None,
        label_color: wx.Colour | None = None,
        active_label_color: wx.Colour | None = None,
    ) -> None:
        super().__init__(
            parent,
            id,
            label,
            style=PB_STYLE_DEFAULT | PB_STYLE_TOGGLE,
        )
        self._idle_color_override = idle_color
        self._hover_color_override = hover_color
        self._active_color_override = active_color
        self._label_color_override = label_color
        self._active_label_color_override = active_label_color
        self._hovered = False
        self._set_palette()
        # Replace PlateButton's transparent-label painter with a filled,
        # rounded treatment that remains distinct from the workspace surface.
        self.Unbind(wx.EVT_PAINT)
        self.Bind(wx.EVT_PAINT, self._paint_button)
        self.Unbind(wx.EVT_ENTER_WINDOW)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Unbind(wx.EVT_LEAVE_WINDOW)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self._on_system_colours_changed)

    def _set_palette(self) -> None:
        self._idle_color = self._idle_color_override or wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_BTNFACE
        )
        parent_color = self.GetParent().GetBackgroundColour()
        if self._idle_color_override is None:
            idle_luminance = self._color_luminance(self._idle_color)
            parent_luminance = self._color_luminance(parent_color)
            if abs(idle_luminance - parent_luminance) < 28:
                adjustment = -28 if parent_luminance >= 128 else 28
                red, green, blue = (
                    min(255, max(0, channel + adjustment))
                    for channel in (
                        self._idle_color.Red(),
                        self._idle_color.Green(),
                        self._idle_color.Blue(),
                    )
                )
                self._idle_color = wx.Colour(red, green, blue)

        self._active_color = (
            self._active_color_override
            or wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        )
        self._hover_color = self._hover_color_override or wx.Colour(
            (self._idle_color.Red() + self._active_color.Red()) // 2,
            (self._idle_color.Green() + self._active_color.Green()) // 2,
            (self._idle_color.Blue() + self._active_color.Blue()) // 2,
        )
        self._label_color = self._label_color_override or wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_BTNTEXT
        )
        self._active_label_color = (
            self._active_label_color_override
            or wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT)
        )

    @staticmethod
    def _color_luminance(color: wx.Colour) -> float:
        return (
            color.Red() * 0.299
            + color.Green() * 0.587
            + color.Blue() * 0.114
        )

    def SetValue(self, value: bool) -> None:
        """Set the selected state without emitting a toggle event."""
        self._pressed = bool(value)
        if self._pressed:
            self._SetState(PLATE_PRESSED)
        else:
            self._SetState(PLATE_HIGHLIGHT if self._hovered else PLATE_NORMAL)

    def GetValue(self) -> bool:
        """Return whether the button is selected."""
        return self._pressed

    def _on_enter(self, _event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()

    def _on_leave(self, _event: wx.MouseEvent) -> None:
        self._hovered = False
        self.Refresh()

    def _on_system_colours_changed(self, event: wx.SysColourChangedEvent) -> None:
        self._set_palette()
        self.Refresh()
        event.Skip()

    def _paint_button(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDCFactory(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        width, height = self.GetClientSize()
        if width <= 0 or height <= 0:
            return
        selected = self._pressed
        background = (
            self._active_color
            if selected
            else self._hover_color
            if self._hovered
            else self._idle_color
        )
        foreground = (
            self._active_label_color if selected else self._label_color
        )
        if not self.IsEnabled():
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        dc.SetPen(wx.Pen(background))
        dc.SetBrush(wx.Brush(background))
        radius = min(6, height // 2)
        dc.DrawRoundedRectangle(0, 0, width, height, radius)
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(foreground)
        label_width, label_height = dc.GetTextExtent(self.GetLabel())
        dc.DrawText(
            self.GetLabel(),
            (width - label_width) // 2,
            (height - label_height) // 2,
        )
        if self.HasFocus():
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetPen(wx.Pen(self._active_color, 1))
            dc.DrawRoundedRectangle(
                1, 1, max(0, width - 2), max(0, height - 2), max(0, radius - 1)
            )
