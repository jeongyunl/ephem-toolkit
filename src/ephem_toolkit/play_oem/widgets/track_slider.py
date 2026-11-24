"""Reusable value track control with keyboard, pointer, and hover support."""

from __future__ import annotations

from collections.abc import Callable

import wx

from ..tooltips import dismiss_tooltip, position_tooltip_at_pointer, set_tooltip


class TrackSlider(wx.Control):
    """Interactive horizontal value track with a seek marker."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        minimum: int = 0,
        maximum: int = 10_000,
        tooltip_at: Callable[[float], str] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY, style=wx.WANTS_CHARS | wx.TAB_TRAVERSAL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCanFocus(True)
        self.SetName("Slider track")
        self._minimum = minimum
        self._maximum = max(minimum, maximum)
        self._value = minimum
        self._value_is_set = False
        self._dragging = False
        self._pointer_over_track = False
        self._pointer_position: wx.Point | None = None
        self._tooltip_at = tooltip_at or self._default_tooltip_at
        self._track_tooltip = set_tooltip(self, "")
        self._track_tooltip.SetStartDelay(1)
        self.SetMinSize(wx.Size(-1, max(50, self.GetBestSize().height + 14)))
        self.Bind(wx.EVT_PAINT, self._paint_track)
        self.Bind(wx.EVT_LEFT_DOWN, self._left_down)
        self.Bind(wx.EVT_LEFT_UP, self._left_up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_ENTER_WINDOW, self._pointer_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._pointer_leave)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)
        self.Bind(wx.EVT_MOUSEWHEEL, self._mouse_wheel)
        self.Bind(wx.EVT_KEY_DOWN, self._key_down)

    @property
    def minimum(self) -> int:
        return self._minimum

    @property
    def maximum(self) -> int:
        return self._maximum

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def _track_is_highlighted(self) -> bool:
        return self._pointer_over_track or self._dragging

    def SetRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(minimum, maximum)
        self.SetValue(self._value)

    def GetMin(self) -> int:
        return self._minimum

    def GetMax(self) -> int:
        return self._maximum

    def GetValue(self) -> int:
        """Return the value or an unset sentinel before initialization."""
        return self._value if self._value_is_set else self._minimum - 1

    def SetValue(self, value: int) -> None:
        self._value = min(max(int(value), self._minimum), self._maximum)
        self._value_is_set = True
        self.Refresh()

    def is_pointer_over_track(self, position: wx.Point) -> bool:
        """Return whether a point is inside the track's central hover band."""
        center_y = self.GetClientSize().height / 2 - 2
        return abs(position.y - center_y) <= 6

    def _value_fraction(self) -> float:
        span = self._maximum - self._minimum
        if span <= 0:
            return 0.0
        return min(max((self._value - self._minimum) / span, 0.0), 1.0)

    def _fraction_at_x(self, x: int) -> float:
        width = self.GetClientSize().width
        return min(max((x - 10) / max(1, width - 20), 0.0), 1.0)

    def _x_for_fraction(self, fraction: float) -> int:
        width = self.GetClientSize().width
        fraction = min(max(fraction, 0.0), 1.0)
        return 10 + round(fraction * max(0, width - 20))

    def _value_at_x(self, x: int) -> int:
        fraction = self._fraction_at_x(x)
        return round(self._minimum + fraction * (self._maximum - self._minimum))

    def _set_value_from_user(self, value: int) -> None:
        checked_value = min(max(value, self._minimum), self._maximum)
        if checked_value == self._value and self._value_is_set:
            return
        self.SetValue(checked_value)
        event = wx.CommandEvent(wx.EVT_SLIDER.typeId, self.GetId())
        event.SetInt(checked_value)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

    def _default_tooltip_at(self, fraction: float) -> str:
        value = self._minimum + min(max(fraction, 0.0), 1.0) * (
            self._maximum - self._minimum
        )
        return f"{value:g}"

    def _pointer_fraction(self) -> float:
        position = self._pointer_position
        width = self.GetClientSize().width
        if position is None or width <= 0:
            return 0.0
        return min(max(position.x / width, 0.0), 1.0)

    def _set_pointer_position(self, position: wx.Point | None) -> None:
        self._pointer_position = position

    def _set_track_hover(self, hovered: bool) -> None:
        if self._pointer_over_track != hovered:
            self._pointer_over_track = hovered
            self.Refresh()

    def _update_pointer_state(self, position: wx.Point) -> None:
        self._set_pointer_position(position)
        over_track = self.is_pointer_over_track(position)
        self._set_track_hover(over_track)
        if (
            not self.IsEnabled()
            or self.is_dragging
            or not self._value_is_set
            or not over_track
        ):
            self._track_tooltip.DoHideNow()
            return
        width = self.GetClientSize().width
        if width <= 0:
            return
        fraction = min(max(position.x / width, 0.0), 1.0)
        self._track_tooltip.SetMessage(self._tooltip_at(fraction))
        position_tooltip_at_pointer(
            self._track_tooltip,
            self,
            position,
            above_track=True,
        )

    def hide_tooltips(self) -> None:
        """Hide the track tooltip."""
        dismiss_tooltip(self)

    def _draw_track(self, dc: wx.DC, width: int, height: int) -> None:
        if width <= 20 or height <= 0:
            return
        background = self.GetBackgroundColour()
        luminance = (
            background.Red() * 0.299
            + background.Green() * 0.587
            + background.Blue() * 0.114
        )
        track_color = (
            wx.Colour("#55585d") if luminance < 128 else wx.Colour("#c9cdd2")
        )
        center_y = height // 2 - 2
        dc.SetPen(wx.Pen(track_color, 1))
        dc.SetBrush(wx.Brush(track_color))
        dc.DrawRoundedRectangle(10, center_y - 5, width - 20, 10, 5)

    def _draw_track_highlight(self, dc: wx.DC, width: int, height: int) -> None:
        if not self._track_is_highlighted or width <= 20 or height <= 0:
            return
        highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        center_y = height // 2 - 2
        dc.SetPen(wx.Pen(highlight, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(10, center_y - 6, width - 20, 12, 6)

    def _draw_seek_marker(self, dc: wx.DC, height: int) -> None:
        if not self._value_is_set:
            return
        background = self.GetBackgroundColour()
        highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        dc.SetPen(wx.Pen(highlight, 2))
        dc.SetBrush(wx.Brush(background))
        dc.DrawCircle(self._x_for_fraction(self._value_fraction()), height // 2 - 2, 6)

    def _paint_track(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        width, height = self.GetClientSize()
        self._draw_track(dc, width, height)
        self._draw_track_highlight(dc, width, height)
        self._draw_seek_marker(dc, height)

    def _left_down(self, event: wx.MouseEvent) -> None:
        if not self.IsEnabled():
            return
        self.SetFocus()
        dismiss_tooltip(self)
        self._dragging = True
        self.Refresh()
        if not self.HasCapture():
            self.CaptureMouse()
        self._set_value_from_user(self._value_at_x(event.GetX()))

    def _left_up(self, _event: wx.MouseEvent) -> None:
        self._end_drag()

    def _motion(self, event: wx.MouseEvent) -> None:
        self._update_pointer_state(event.GetPosition())
        if self._dragging and event.Dragging() and event.LeftIsDown():
            self._set_value_from_user(self._value_at_x(event.GetX()))
        event.Skip()

    def _pointer_motion(self, event: wx.MouseEvent) -> None:
        self._update_pointer_state(event.GetPosition())
        event.Skip()

    def _pointer_leave(self, event: wx.MouseEvent) -> None:
        self._set_pointer_position(None)
        self._set_track_hover(False)
        self.hide_tooltips()
        event.Skip()

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        self._end_drag(release_capture=False)
        event.Skip()

    def _end_drag(self, *, release_capture: bool = True) -> None:
        self._dragging = False
        self.Refresh()
        if release_capture and self.HasCapture():
            self.ReleaseMouse()

    def _mouse_wheel(self, event: wx.MouseEvent) -> None:
        rotation = event.GetWheelRotation()
        if rotation:
            self._set_value_from_user(
                self._value + (100 if rotation > 0 else -100)
            )

    def _key_down(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key in (wx.WXK_LEFT, wx.WXK_RIGHT):
            self._set_value_from_user(
                self._value + (100 if key == wx.WXK_RIGHT else -100)
            )
        elif key == wx.WXK_HOME:
            self._set_value_from_user(self._minimum)
        elif key == wx.WXK_END:
            self._set_value_from_user(self._maximum)
        else:
            event.Skip()
