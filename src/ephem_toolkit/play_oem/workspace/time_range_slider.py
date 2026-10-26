"""Native playback slider with four keyboard and pointer range grips."""

from __future__ import annotations

from collections.abc import Callable

import wx

from .. import time_range
from ..tooltips import set_tooltip, suppress_tooltips
from ..display_time import UTC_DISPLAY, format_tt


def _triangle_vertices(
    kind: str, center_x: int, center_y: int
) -> tuple[tuple[int, int], ...]:
    if kind == "playback":
        return (
            (center_x, center_y - 5),
            (center_x + 6, center_y + 3),
            (center_x - 6, center_y + 3),
        )
    return (
        (center_x, center_y + 3),
        (center_x + 6, center_y - 5),
        (center_x - 6, center_y - 5),
    )


def _plot_handle_vertices(
    mode: time_range.EndpointMode, center_x: int, center_y: int
) -> tuple[tuple[int, int], ...]:
    if mode == "follow":
        return _triangle_vertices("plot", center_x, center_y)
    if mode == "offset":
        return (
            (center_x, center_y - 5),
            (center_x + 6, center_y),
            (center_x, center_y + 4),
            (center_x - 6, center_y),
        )
    return (
        (center_x - 5, center_y - 4),
        (center_x + 5, center_y - 4),
        (center_x + 5, center_y + 3),
        (center_x - 5, center_y + 3),
    )


def _plot_tooltip_text(name: str, timestamp: str, mode: time_range.EndpointMode) -> str:
    mode_label = {
        "follow": "Follow playback",
        "fixed": "Fixed time",
        "offset": "Playback offset",
    }[mode]
    return f"{name}: {timestamp}\n{mode_label} | Right-click for mode"


def _plot_grip_y(slider_height: int, playback_grip_y: int, grip_height: int) -> int:
    """Mirror the plot grip across the slider track from the playback grip."""
    return slider_height - playback_grip_y - grip_height


class _RangeGrip(wx.Control):
    def __init__(
        self,
        parent: wx.Window,
        slider: TimeRangeSlider,
        name: str,
        kind: str,
        color: str,
    ) -> None:
        super().__init__(parent, wx.ID_ANY, style=wx.WANTS_CHARS | wx.TAB_TRAVERSAL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.slider = slider
        self.kind = kind
        self.color = wx.Colour(color)
        self.SetName(name)
        self.SetCanFocus(True)
        self.SetMinSize(wx.Size(18, 18))
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._down)
        self.Bind(wx.EVT_LEFT_DCLICK, self._double_click)
        self.Bind(wx.EVT_RIGHT_DOWN, self._right_down)
        self.Bind(wx.EVT_LEFT_UP, self._up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)
        self.Bind(wx.EVT_CHAR, self._key)
        self._dragging = False

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        cx, cy = w // 2, h // 2
        dc.SetPen(wx.Pen(self.color, 2))
        if self.kind == "playback":
            dc.SetBrush(wx.Brush(self.color))
            vertices = _triangle_vertices(self.kind, cx, cy)
        else:
            dc.SetBrush(wx.Brush(self.GetParent().GetBackgroundColour()))
            vertices = _plot_handle_vertices(self.slider._plot_mode(self), cx, cy)
        dc.DrawPolygon([wx.Point(x, y) for x, y in vertices])
        if self.HasFocus():
            dc.SetPen(
                wx.Pen(
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT),
                    1,
                    wx.PENSTYLE_DOT,
                )
            )
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(1, 1, w - 3, h - 3)

    def _down(self, event: wx.MouseEvent) -> None:
        self.SetFocus()
        if self.kind == "plot" and self.slider._plot_mode(self) == "follow":
            return
        self._dragging = True
        if not self.HasCapture():
            self.CaptureMouse()
        self.slider._drag(self, event.GetPosition())

    def _double_click(self, event: wx.MouseEvent) -> None:
        if self.kind == "playback":
            self.slider._snap_playback_handle(self)
        else:
            event.Skip()

    def _right_down(self, event: wx.MouseEvent) -> None:
        if self.kind == "plot":
            with suppress_tooltips():
                self.slider._show_plot_mode_menu(self, event.GetPosition())
        else:
            event.Skip()

    def _up(self, _event: wx.MouseEvent) -> None:
        self._dragging = False
        if self.HasCapture():
            self.ReleaseMouse()

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        self._dragging = False
        event.Skip()

    def _motion(self, event: wx.MouseEvent) -> None:
        if self._dragging and event.Dragging() and event.LeftIsDown():
            self.slider._drag(self, event.GetPosition())

    def _key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (
            wx.WXK_LEFT,
            wx.WXK_RIGHT,
            wx.WXK_PAGEUP,
            wx.WXK_PAGEDOWN,
        ):
            self.slider._nudge(
                self,
                -1 if event.GetKeyCode() in (wx.WXK_LEFT, wx.WXK_PAGEDOWN) else 1,
            )
        else:
            event.Skip()


class _SeekGrip(wx.Control):
    """Input target for the central current-time marker."""

    def __init__(self, parent: wx.Window, slider: TimeRangeSlider) -> None:
        super().__init__(parent, wx.ID_ANY, style=wx.WANTS_CHARS | wx.TAB_TRAVERSAL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.slider = slider
        self.SetName("Current playback time marker")
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._down)
        self.Bind(wx.EVT_LEFT_UP, self._up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)
        self._dragging = False

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        background = self.slider.GetBackgroundColour()
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        width, height = self.GetClientSize()
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT), 2))
        dc.SetBrush(wx.Brush(background))
        dc.DrawCircle(width // 2, height // 2, 6)

    def _down(self, event: wx.MouseEvent) -> None:
        if not self.slider.IsEnabled():
            return
        self.slider.SetFocus()
        self._dragging = True
        if not self.HasCapture():
            self.CaptureMouse()
        self.slider._seek_from_grip(self, event.GetPosition())

    def _up(self, _event: wx.MouseEvent) -> None:
        self._dragging = False
        if self.HasCapture():
            self.ReleaseMouse()

    def _motion(self, event: wx.MouseEvent) -> None:
        if (
            self.slider.IsEnabled()
            and self._dragging
            and event.Dragging()
            and event.LeftIsDown()
        ):
            self.slider._seek_from_grip(self, event.GetPosition())
        event.Skip()

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        self._dragging = False
        event.Skip()


class TimeRangeSlider(wx.Control):
    """A portable painted seek slider with playback and plot range grips."""

    _KINDS = (
        ("playback_start", "Playback start", "playback", "#197765"),
        ("plot_start", "Plot start", "plot", "#2864c8"),
        ("playback_end", "Playback end", "playback", "#197765"),
        ("plot_end", "Plot end", "plot", "#2864c8"),
    )

    def __init__(
        self,
        parent: wx.Window,
        *,
        on_playback: Callable[[float, float], None],
        on_plot_endpoint: Callable[[str, float], None],
        on_plot_endpoint_mode: Callable[[str, time_range.EndpointMode], None],
        on_begin_edit: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            wx.ID_ANY,
            style=wx.WANTS_CHARS | wx.TAB_TRAVERSAL,
        )
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCanFocus(True)
        self.SetName("Playback timeline and time range handles")
        self._minimum = 0
        self._maximum = 10_000
        self._value = 0
        # Leave a small handle-to-track gap without pushing playback controls down.
        self.SetMinSize(wx.Size(-1, max(58, self.GetBestSize().height + 20)))
        self._on_playback = on_playback
        self._on_plot_endpoint = on_plot_endpoint
        self._on_plot_endpoint_mode = on_plot_endpoint_mode
        self._on_begin_edit = on_begin_edit
        self._coverage = (0.0, 1.0)
        self._playback = (0.0, 1.0)
        self._plot_rule: time_range.PlotTimeRange | None = None
        self._display_time_zone = UTC_DISPLAY
        self._now = 0.0
        self._grips: dict[str, _RangeGrip] = {}
        self._seek_grip = _SeekGrip(self.GetParent(), self)
        self._seek_grip.Hide()
        self._dragging = False
        self.Bind(wx.EVT_PAINT, self._paint_track)
        self.Bind(wx.EVT_LEFT_DOWN, self._left_down)
        self.Bind(wx.EVT_LEFT_UP, self._left_up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)
        self.Bind(wx.EVT_KEY_DOWN, self._key_down)
        self.Bind(wx.EVT_MOUSEWHEEL, self._mouse_wheel)
        self.Bind(wx.EVT_SET_FOCUS, self._focus_changed)
        self.Bind(wx.EVT_KILL_FOCUS, self._focus_changed)
        for key, name, kind, color in self._KINDS:
            # Sibling grips layer consistently across wx ports.
            grip = _RangeGrip(self.GetParent(), self, name, kind, color)
            grip.Hide()
            self._grips[key] = grip
        self._seek_grip.Raise()
        self.Bind(wx.EVT_SIZE, self._on_size)

    @property
    def minimum(self) -> int:
        return self._minimum

    @property
    def maximum(self) -> int:
        return self._maximum

    def SetRange(self, minimum: int, maximum: int) -> None:
        self._minimum, self._maximum = minimum, max(minimum, maximum)
        self.SetValue(self._value)

    def GetMin(self) -> int:
        return self._minimum

    def GetMax(self) -> int:
        return self._maximum

    def GetValue(self) -> int:
        return self._value

    def SetValue(self, value: int) -> None:
        self._value = min(max(int(value), self._minimum), self._maximum)
        self.Refresh()

    def _paint_track(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        background = self.GetBackgroundColour()
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        width, height = self.GetClientSize()
        if width <= 20 or height <= 0:
            return

        left, right = 10, width - 10
        center_y = height // 2
        background_luminance = (
            background.Red() * 0.299
            + background.Green() * 0.587
            + background.Blue() * 0.114
        )
        track_color = (
            wx.Colour("#55585d") if background_luminance < 128 else wx.Colour("#c9cdd2")
        )
        dc.SetPen(wx.Pen(track_color, 1))
        dc.SetBrush(wx.Brush(track_color))
        dc.DrawRoundedRectangle(left, center_y - 4, right - left, 8, 4)

        playback_start_x, playback_end_x = self._playable_segment_x()
        range_left, range_right = sorted((playback_start_x, playback_end_x))
        range_width = max(4, range_right - range_left)
        playback_color = wx.Colour("#197765")
        dc.SetPen(wx.Pen(playback_color, 1))
        dc.SetBrush(wx.Brush(playback_color))
        dc.DrawRoundedRectangle(range_left, center_y - 4, range_width, 8, 4)

        progress_x = self._x_for(self._now)
        highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        dc.SetPen(wx.Pen(highlight, 2))
        dc.DrawLine(left, center_y, progress_x, center_y)
        dc.SetPen(wx.Pen(highlight, 2))
        dc.SetBrush(wx.Brush(background))
        dc.DrawCircle(progress_x, center_y, 6)

    def _playable_segment_x(self) -> tuple[int, int]:
        return self._x_for(self._playback[0]), self._x_for(self._playback[1])

    def _value_at_x(self, x: int) -> int:
        width = self.GetClientSize().width
        fraction = min(max((x - 10) / max(1, width - 20), 0.0), 1.0)
        return round(self._minimum + fraction * (self._maximum - self._minimum))

    def _seek_from_grip(self, grip: _SeekGrip, point: wx.Point) -> None:
        screen_point = grip.ClientToScreen(point)
        self._set_value_from_user(self._value_at_x(self.ScreenToClient(screen_point).x))

    def _set_value_from_user(self, value: int) -> None:
        checked_value = min(max(value, self._minimum), self._maximum)
        if checked_value == self._value:
            return
        self.SetValue(checked_value)
        event = wx.CommandEvent(wx.EVT_SLIDER.typeId, self.GetId())
        event.SetInt(checked_value)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

    def _left_down(self, event: wx.MouseEvent) -> None:
        if not self.IsEnabled():
            return
        self.SetFocus()
        self._dragging = True
        if not self.HasCapture():
            self.CaptureMouse()
        self._set_value_from_user(self._value_at_x(event.GetX()))

    def _left_up(self, _event: wx.MouseEvent) -> None:
        self._dragging = False
        if self.HasCapture():
            self.ReleaseMouse()

    def _motion(self, event: wx.MouseEvent) -> None:
        if self._dragging and event.Dragging() and event.LeftIsDown():
            self._set_value_from_user(self._value_at_x(event.GetX()))
        event.Skip()

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        self._dragging = False
        event.Skip()

    def _mouse_wheel(self, event: wx.MouseEvent) -> None:
        rotation = event.GetWheelRotation()
        if rotation:
            direction = 1 if rotation > 0 else -1
            self._set_value_from_user(self._value + direction * 100)

    def _key_down(self, event: wx.KeyEvent) -> None:
        key = event.GetKeyCode()
        if key in (wx.WXK_LEFT, wx.WXK_RIGHT):
            direction = -1 if key == wx.WXK_LEFT else 1
            self._set_value_from_user(self._value + direction * 100)
        elif key in (wx.WXK_PAGEUP, wx.WXK_PAGEDOWN):
            direction = 1 if key == wx.WXK_PAGEUP else -1
            self._set_value_from_user(self._value + direction * 1000)
        elif key == wx.WXK_HOME:
            self._set_value_from_user(self._minimum)
        elif key == wx.WXK_END:
            self._set_value_from_user(self._maximum)
        else:
            event.Skip()

    def _focus_changed(self, event: wx.FocusEvent) -> None:
        self.Refresh()
        event.Skip()

    def set_ranges(
        self,
        coverage: tuple[float, float],
        playback: tuple[float, float],
        plot_rule: time_range.PlotTimeRange,
        now_s: float,
    ) -> None:
        self._coverage, self._playback = coverage, playback
        self._plot_rule, self._now = plot_rule, now_s
        self.Refresh()
        self._position_grips()
        for key, grip in self._grips.items():
            if key.startswith("plot"):
                grip.Refresh()

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        self._position_grips()

    def _time_for(self, key: str) -> float:
        if key.startswith("playback"):
            return self._playback[0 if key.endswith("start") else 1]
        assert self._plot_rule is not None
        endpoint = (
            self._plot_rule.start if key.endswith("start") else self._plot_rule.end
        )
        if endpoint.mode == "follow":
            return self._playback[0 if key.endswith("start") else 1]
        return endpoint.value_s + (self._now if endpoint.mode == "offset" else 0.0)

    def _plot_mode(self, grip: _RangeGrip) -> time_range.EndpointMode:
        key = next(key for key, item in self._grips.items() if item is grip)
        assert self._plot_rule is not None
        endpoint = (
            self._plot_rule.start if key.endswith("start") else self._plot_rule.end
        )
        return endpoint.mode

    def is_pointer_over_timeline_track(self, position: wx.Point) -> bool:
        """Restrict the slider tooltip hotspot to the narrow central track band."""
        track_center_y = self.GetClientSize().height / 2
        return abs(position.y - track_center_y) <= 6

    def _show_plot_mode_menu(self, grip: _RangeGrip, position: wx.Point) -> None:
        key = next(key for key, item in self._grips.items() if item is grip)
        name = "start" if key.endswith("start") else "end"
        assert self._plot_rule is not None
        endpoint = self._plot_rule.start if name == "start" else self._plot_rule.end
        labels: tuple[tuple[str, time_range.EndpointMode], ...] = (
            ("Follow playback", "follow"),
            ("Offset from playback", "offset"),
            ("Fixed timepoint", "fixed"),
        )
        menu = wx.Menu()
        try:

            def mode_handler(
                selected_mode: time_range.EndpointMode,
            ) -> Callable[[wx.CommandEvent], None]:
                return lambda _event: self._on_plot_endpoint_mode(name, selected_mode)

            for label, mode in labels:
                item = menu.AppendRadioItem(wx.ID_ANY, label)
                item.Check(endpoint.mode == mode)
                menu.Bind(
                    wx.EVT_MENU,
                    mode_handler(mode),
                    id=item.GetId(),
                )
            grip.PopupMenu(menu, position)
        finally:
            menu.Destroy()

    def _x_for(self, timestamp: float) -> int:
        start, end = self._coverage
        width = self.GetClientSize().width
        fraction = (
            0.0
            if end <= start
            else min(max((timestamp - start) / (end - start), 0.0), 1.0)
        )
        return 10 + round(fraction * max(0, width - 20))

    def _position_grips(self, _event: wx.Event | None = None) -> None:
        if not self._grips or self._plot_rule is None:
            if _event is not None:
                _event.Skip()
            return
        width = height = 18
        # Keep endpoint hitboxes clear of the seek marker and mirror them around
        # the track so each handle has a separate mouse target.
        playback_grip_y = self.GetClientSize().height // 2 + 9
        centers: list[tuple[str, int]] = [
            (key, self._x_for(self._time_for(key))) for key in self._grips
        ]
        # Spread coincident handles within each row; each retains its own target.
        by_x: dict[tuple[str, int], list[str]] = {}
        for key, x in centers:
            row = "plot" if key.startswith("plot") else "playback"
            by_x.setdefault((row, x), []).append(key)
        positions: dict[str, int] = {}
        for (_row, x), keys in by_x.items():
            offsets = [round((i - (len(keys) - 1) / 2) * 15) for i in range(len(keys))]
            positions.update({key: x + offset for key, offset in zip(keys, offsets)})
        for key, grip in self._grips.items():
            if key.startswith("plot") and (
                self._plot_rule is None or not self._plot_rule.enabled
            ):
                grip.Hide()
                continue
            grip.Show()
            slider_position = self.GetPosition()
            grip_y = (
                _plot_grip_y(self.GetClientSize().height, playback_grip_y, height)
                if key.startswith("plot")
                else playback_grip_y
            )
            grip.SetSize((width, height))
            grip_x = positions[key] - grip.GetSize().width // 2
            grip.SetPosition(
                (
                    slider_position.x
                    + max(0, min(self.GetClientSize().width - width, grip_x)),
                    slider_position.y + grip_y,
                )
            )
            try:
                is_playback = key.startswith("playback")
                timestamp = format_tt(
                    self._time_for(key), self._display_time_zone,
                    fractional_second_places=0,
                )
                if is_playback:
                    bound = "start" if key.endswith("start") else "end"
                    tooltip = f"Playback {bound}: {timestamp}"
                else:
                    assert self._plot_rule is not None
                    endpoint = (
                        self._plot_rule.start
                        if key.endswith("start")
                        else self._plot_rule.end
                    )
                    tooltip = _plot_tooltip_text(
                        grip.GetName(), timestamp, endpoint.mode
                    )
                set_tooltip(grip, tooltip)
            except (AttributeError, TypeError, OverflowError, ValueError):
                set_tooltip(grip, grip.GetName())
        seek_grip_size = 16
        self._seek_grip.SetSize((seek_grip_size, seek_grip_size))
        self._seek_grip.SetPosition(
            (
                self.GetPosition().x + self._x_for(self._now) - seek_grip_size // 2,
                self.GetPosition().y
                + self.GetClientSize().height // 2
                - seek_grip_size // 2,
            )
        )
        self._seek_grip.Show()
        if _event is not None:
            _event.Skip()

    def _timestamp_at(self, local_x: int) -> float:
        width = self.GetClientSize().width
        fraction = min(max((local_x - 10) / max(1, width - 20), 0.0), 1.0)
        return self._coverage[0] + fraction * (self._coverage[1] - self._coverage[0])

    def _drag(self, grip: _RangeGrip, point: wx.Point) -> None:
        key = next(k for k, item in self._grips.items() if item is grip)
        if key.startswith("plot") and self._plot_mode(grip) == "follow":
            return
        self._on_begin_edit()
        local = grip.ClientToScreen(point)
        target = self._timestamp_at(self.ScreenToClient(local).x)
        if key.startswith("plot"):
            self._on_plot_endpoint("start" if key.endswith("start") else "end", target)
        else:
            start, end = self._playback
            if key.endswith("start"):
                start = min(target, end)
            else:
                end = max(target, start)
            self._on_playback(start, end)

    def _snap_playback_handle(self, grip: _RangeGrip) -> None:
        """Snap a playback endpoint to its corresponding OEM coverage bound."""
        self._on_begin_edit()
        start, end = self._playback
        key = next(key for key, item in self._grips.items() if item is grip)
        if key.endswith("start"):
            start = self._coverage[0]
        else:
            end = self._coverage[1]
        self._on_playback(start, end)

    def _nudge(self, grip: _RangeGrip, direction: int) -> None:
        key = next(k for k, item in self._grips.items() if item is grip)
        if key.startswith("plot") and self._plot_mode(grip) == "follow":
            return
        step = (self._coverage[1] - self._coverage[0]) / 1000.0 or 1.0
        target = min(
            max(self._time_for(key) + direction * step, self._coverage[0]),
            self._coverage[1],
        )
        self._on_begin_edit()
        if key.startswith("plot"):
            self._on_plot_endpoint("start" if key.endswith("start") else "end", target)
        else:
            start, end = self._playback
            self._on_playback(
                min(target, end) if key.endswith("start") else start,
                end if key.endswith("start") else max(target, start),
            )

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._position_grips()
        event.Skip()
