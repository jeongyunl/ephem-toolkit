"""Native playback slider with four keyboard and pointer range grips."""

from __future__ import annotations

from collections.abc import Callable

import wx

from .. import time_range, time_snapping
from .tooltips import (
    dismiss_tooltip,
    position_tooltip_at_pointer,
    set_tooltip,
    suppress_tooltips,
)
from ..display_time import format_tt
from .time_slider import TimeSlider


PLAYBACK_RANGE_HIT_TOLERANCE = 8


def _triangle_vertices(
    kind: str, center_x: int, center_y: int
) -> tuple[tuple[int, int], ...]:
    if kind == "playback":
        return (
            (center_x, center_y - 4),
            (center_x + 6, center_y + 2),
            (center_x - 6, center_y + 2),
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
        return (
            (center_x, center_y + 2),
            (center_x + 6, center_y - 4),
            (center_x - 6, center_y - 4),
        )
    if mode == "offset":
        return (
            (center_x, center_y - 4),
            (center_x + 6, center_y),
            (center_x, center_y + 3),
            (center_x - 6, center_y),
        )
    return (
        (center_x - 5, center_y - 3),
        (center_x + 5, center_y - 3),
        (center_x + 5, center_y + 2),
        (center_x - 5, center_y + 2),
    )


def _plot_tooltip_text(name: str, timestamp: str, mode: time_range.EndpointMode) -> str:
    if mode == "follow":
        matched_bound = "start" if name.endswith("start") else "end"
        mode_label = f"Automatically follows playback {matched_bound} time"
    elif mode == "offset":
        mode_label = "Follows current time, keeping the same time gap"
    else:
        mode_label = "Stays at this time; does not follow"
    return f"{name}: {timestamp}\n{mode_label} | Right-click to change"


def _plot_grip_y(slider_height: int, playback_grip_y: int, grip_height: int) -> int:
    """Mirror the plot grip across the slider track from the playback grip."""
    return max(0, slider_height - playback_grip_y - grip_height)


def _timestamp_is_visible(timestamp: float, visible_range: tuple[float, float]) -> bool:
    start, end = visible_range
    return start <= timestamp <= end


class _RangeGrip(wx.Control):
    def __init__(
        self,
        parent: wx.Window,
        slider: PlaybackTimeSlider,
        name: str,
        kind: str,
        color: str,
    ) -> None:
        super().__init__(
            parent,
            wx.ID_ANY,
            style=wx.BORDER_NONE | wx.WANTS_CHARS | wx.TAB_TRAVERSAL,
        )
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

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        cx, cy = w // 2, h // 2
        color = (
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
            if self.slider._drag_source is self
            else self.color
        )
        dragging = self.slider._drag_source is self
        dc.SetPen(wx.Pen(color, 3 if dragging else 2))
        if self.kind == "playback":
            dc.SetBrush(wx.Brush(color))
            vertices = _triangle_vertices(self.kind, cx, cy)
        else:
            brush_color = color if dragging else self.GetParent().GetBackgroundColour()
            dc.SetBrush(wx.Brush(brush_color))
            vertices = _plot_handle_vertices(self.slider._plot_mode(self), cx, cy)
        dc.DrawPolygon([wx.Point(x, y) for x, y in vertices])

    def _down(self, event: wx.MouseEvent) -> None:
        self.SetFocus()
        if self.kind == "plot" and self.slider._plot_mode(self) == "follow":
            return
        self.slider._begin_pointer_drag(self)
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
        self.slider._end_pointer_drag(self)

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        self.slider._end_pointer_drag(self, release_capture=False)
        event.Skip()

    def _motion(self, event: wx.MouseEvent) -> None:
        if self.slider._drag_source is self and event.Dragging() and event.LeftIsDown():
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

    def __init__(self, parent: wx.Window, slider: PlaybackTimeSlider) -> None:
        super().__init__(parent, wx.ID_ANY, style=wx.WANTS_CHARS | wx.TAB_TRAVERSAL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.slider = slider
        self.SetName("Current playback time marker")
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._down)
        self.Bind(wx.EVT_LEFT_UP, self._up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._leave)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        background = self.slider.GetBackgroundColour()
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        width, height = self.GetClientSize()
        highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        range_dragging = getattr(self.slider, "_range_drag_origin", None) is not None
        dragging = self.slider._drag_source is self or (
            self.slider._drag_source is self.slider
            and (
                not range_dragging
                or getattr(self.slider, "_range_seek_origin", None) is not None
            )
        )
        dc.SetPen(wx.Pen(highlight, 3 if dragging else 2))
        dc.SetBrush(wx.Brush(highlight if dragging else background))
        dc.DrawCircle(width // 2, height // 2, 7 if dragging else 6)

    def _down(self, event: wx.MouseEvent) -> None:
        if not self.slider.IsEnabled():
            return
        self.slider.SetFocus()
        # Capture on the slider so drag coordinates stay in the slider's
        # client space across wx ports, especially GTK.
        capture_window = self.slider
        if not hasattr(capture_window, "CaptureMouse"):
            capture_window = self
        self.slider._begin_pointer_drag(capture_window)
        if not capture_window.HasCapture():
            capture_window.CaptureMouse()
        self.slider._position_seek_tooltip(event.GetPosition())

    def _up(self, _event: wx.MouseEvent) -> None:
        source = self.slider if self.slider._drag_source is self.slider else self
        self.slider._end_pointer_drag(source)

    def _motion(self, event: wx.MouseEvent) -> None:
        if not self.slider.IsEnabled():
            dismiss_tooltip(self)
        elif self.slider._drag_source is self:
            self.slider._seek_from_grip(self, event.GetPosition())
            self.slider._position_seek_tooltip(event.GetPosition())
        elif not self.slider.is_dragging:
            self.slider._position_seek_tooltip(event.GetPosition())
        event.Skip()

    def _leave(self, event: wx.MouseEvent) -> None:
        dismiss_tooltip(self)
        event.Skip()

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        source = self.slider if self.slider._drag_source is self.slider else self
        self.slider._end_pointer_drag(source, release_capture=False)
        event.Skip()


class PlaybackTimeSlider(TimeSlider):
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
        on_range_dragging: Callable[[bool], None] | None = None,
        timeline_tooltip_at: Callable[[float], str] | None = None,
    ) -> None:
        super().__init__(parent, timeline_tooltip_at=timeline_tooltip_at)
        self.SetName("Playback timeline and time range handles")
        self._on_playback = on_playback
        self._on_plot_endpoint = on_plot_endpoint
        self._on_plot_endpoint_mode = on_plot_endpoint_mode
        self._on_begin_edit = on_begin_edit
        self._on_range_dragging = on_range_dragging or (lambda _dragging: None)
        self._coverage = (0.0, 1.0)
        self._slider_bounds = self._coverage
        self._playback = (0.0, 1.0)
        self._playback_handles = self._playback
        self._unloaded_from_s: float | None = None
        self._plot_rule: time_range.PlotTimeRange | None = None
        self._now = 0.0
        self._drag_source: wx.Window | None = None
        self._range_drag_origin: tuple[float, float, float] | None = None
        self._range_seek_origin: tuple[float, float] | None = None
        self._ranges_ready = False
        self._grips: dict[str, _RangeGrip] = {}
        self._seek_grip = _SeekGrip(self.GetParent(), self)
        self._seek_grip.Hide()
        for event_type in (
            wx.EVT_PAINT,
            wx.EVT_LEFT_DOWN,
            wx.EVT_LEFT_UP,
            wx.EVT_MOTION,
            wx.EVT_MOUSE_CAPTURE_LOST,
            wx.EVT_MOUSEWHEEL,
            wx.EVT_KEY_DOWN,
        ):
            self.Unbind(event_type)
        self.Bind(wx.EVT_PAINT, self._paint_track)
        self.Bind(wx.EVT_LEFT_DOWN, self._left_down)
        self.Bind(wx.EVT_LEFT_UP, self._left_up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)
        self.Bind(wx.EVT_KEY_DOWN, self._key_down)
        self.Bind(wx.EVT_KEY_UP, self._key_up)
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
    def is_dragging(self) -> bool:
        return self._drag_source is not None

    @property
    def _track_is_highlighted(self) -> bool:
        return self._pointer_over_track or self._drag_source in (
            self,
            self._seek_grip,
        )

    @property
    def _playback_connector_hovered(self) -> bool:
        return self._pointer_between_playback_handles(self._pointer_position)

    def _pointer_between_playback_handles(self, position: wx.Point | None) -> bool:
        range_drag_origin = getattr(self, "_range_drag_origin", None)
        if position is None or (
            self._drag_source is not None and range_drag_origin is None
        ):
            return False
        if range_drag_origin is not None:
            return self._drag_source is self
        segment = PlaybackTimeSlider._playback_handle_segment_x(self)
        if segment is None:
            return False
        start_x, end_x = sorted(segment)
        connector_y = self.GetClientSize().height // 2 + 17
        return (
            start_x < position.x < end_x
            and abs(position.y - connector_y) <= PLAYBACK_RANGE_HIT_TOLERANCE
        )

    def _set_pointer_position(self, position: wx.Point | None) -> None:
        was_between_handles = self._playback_connector_hovered
        self._pointer_position = position
        if was_between_handles != self._playback_connector_hovered:
            self.Refresh()

    def hide_tooltips(self) -> None:
        """Hide the track and seek marker tooltips."""
        dismiss_tooltip(self)
        dismiss_tooltip(self._seek_grip)

    def _position_seek_tooltip(self, position: wx.Point) -> None:
        tooltip = getattr(self._seek_grip, "_play_oem_tooltip", None)
        if tooltip is not None:
            position_tooltip_at_pointer(
                tooltip,
                self._seek_grip,
                position,
                above_track=True,
            )

    def _begin_pointer_drag(self, source: wx.Window) -> None:
        self._drag_source = source
        dismiss_tooltip(self)
        if source is not self:
            dismiss_tooltip(source)
        source.Refresh()
        if source is self:
            self._seek_grip.Refresh()
        elif source is self._seek_grip:
            self.Refresh()
        self._on_range_dragging(True)

    def _end_pointer_drag(
        self,
        source: wx.Window,
        *,
        release_capture: bool = True,
    ) -> None:
        was_dragging = self._drag_source is source
        if was_dragging:
            self._drag_source = None
            source.Refresh()
            if source is self:
                self._seek_grip.Refresh()
            elif source is self._seek_grip:
                self.Refresh()
        if release_capture and source.HasCapture():
            source.ReleaseMouse()
        if was_dragging:
            self._on_range_dragging(False)

    def _paint_track(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        background = self.GetBackgroundColour()
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        width, height = self.GetClientSize()
        if width <= 20 or height <= 0:
            return

        center_y = height // 2 - 2
        self._draw_track(dc, width, height)

        playable_segment = self._playable_segment_x()
        if self._ranges_ready and playable_segment is not None:
            playback_start_x, playback_end_x = playable_segment
            range_left, range_right = sorted((playback_start_x, playback_end_x))
            range_width = max(4, range_right - range_left)
            playback_color = wx.Colour("#197765")
            dc.SetPen(wx.Pen(playback_color, 1))
            dc.SetBrush(wx.Brush(playback_color))
            dc.DrawRoundedRectangle(range_left, center_y - 5, range_width, 10, 5)

        unloaded_segment = self._unloaded_segment_x()
        if unloaded_segment is not None:
            unloaded_left, unloaded_right = unloaded_segment
            if unloaded_right > unloaded_left:
                unloaded_color = wx.Colour("#b36b00")
                dc.SetPen(wx.Pen(unloaded_color, 1))
                dc.SetBrush(wx.Brush(unloaded_color))
                dc.DrawRoundedRectangle(
                    unloaded_left,
                    center_y - 5,
                    unloaded_right - unloaded_left,
                    10,
                    5,
                )

        if self._playback_connector_hovered:
            segment = PlaybackTimeSlider._playback_handle_segment_x(self)
            dc.SetPen(wx.Pen(wx.Colour("#197765"), 2))
            connector_y = height // 2 + 17
            if segment is not None:
                start_x, end_x = sorted(segment)
                dc.DrawLine(start_x, connector_y, end_x, connector_y)

        self._draw_track_highlight(dc, width, height)
        self._draw_seek_marker(dc, height)

    def _playable_segment_x(self) -> tuple[int, int] | None:
        visible_start, visible_end = self._slider_bounds
        playback_start, playback_end = sorted(self._playback)
        clipped_start = max(playback_start, visible_start)
        clipped_end = min(playback_end, visible_end)
        if clipped_start > clipped_end:
            return None
        return self._x_for(clipped_start), self._x_for(clipped_end)

    def _playback_handle_segment_x(self) -> tuple[int, int] | None:
        visible_start, visible_end = self._slider_bounds
        handle_start, handle_end = sorted(self._playback_handles)
        clipped_start = max(handle_start, visible_start)
        clipped_end = min(handle_end, visible_end)
        if clipped_start > clipped_end:
            return None
        return self._x_for(clipped_start), self._x_for(clipped_end)

    def _unloaded_segment_x(self) -> tuple[int, int] | None:
        if self._unloaded_from_s is None:
            return None
        return self._x_for(self._unloaded_from_s), self._x_for(self._slider_bounds[1])

    def _seek_from_grip(self, grip: _SeekGrip, point: wx.Point) -> None:
        screen_point = grip.ClientToScreen(point)
        self._set_value_from_user(self._value_at_x(self.ScreenToClient(screen_point).x))

    def _left_down(self, event: wx.MouseEvent) -> None:
        if not self.IsEnabled():
            return
        position = event.GetPosition()
        if self._pointer_between_playback_handles(position):
            self._set_pointer_position(position)
            self.SetFocus()
            command_down = getattr(event, "CmdDown", lambda: False)()
            control_down = getattr(event, "ControlDown", lambda: False)()
            move_seek = control_down or command_down
            pointer_time_s = self._timestamp_at(event.GetX())
            start_s, end_s = self._playback_handles
            self._range_drag_origin = (
                pointer_time_s,
                start_s,
                end_s,
            )
            self._range_seek_origin = (start_s, self._now) if move_seek else None
            if move_seek:
                self._seek_grip.Refresh()
            self._on_begin_edit()
            self._begin_pointer_drag(self)
            if not self.HasCapture():
                self.CaptureMouse()
            return
        if not self.is_pointer_over_timeline_track(event.GetPosition()):
            event.Skip()
            return
        self._set_track_hover(True)
        self.SetFocus()
        self._begin_pointer_drag(self)
        if not self.HasCapture():
            self.CaptureMouse()
        self._set_value_from_user(self._value_at_x(event.GetX()))

    def _left_up(self, _event: wx.MouseEvent) -> None:
        self._range_drag_origin = None
        self._range_seek_origin = None
        self._end_pointer_drag(self)

    def _motion(self, event: wx.MouseEvent) -> None:
        position = event.GetPosition()
        self._update_pointer_state(position)
        if (
            self._drag_source is self
            and self._range_drag_origin is not None
        ):
            command_down = getattr(event, "CmdDown", lambda: False)()
            self._move_playback_range(
                event.GetX(),
                move_seek=event.ControlDown() or command_down,
            )
        elif (
            self._drag_source is self
        ):
            self._set_value_from_user(self._value_at_x(event.GetX()))
        event.Skip()

    def _capture_lost(self, event: wx.MouseCaptureLostEvent) -> None:
        self._range_drag_origin = None
        self._range_seek_origin = None
        self._end_pointer_drag(self, release_capture=False)
        event.Skip()

    def _range_drag_modifier_changed(
        self, move_seek: bool, seek_start_s: float | None = None
    ) -> None:
        if (
            self._range_drag_origin is None
            or (self._range_seek_origin is not None) == move_seek
        ):
            return
        if move_seek:
            if seek_start_s is None:
                seek_start_s = self._playback_handles[0]
            self._range_seek_origin = (seek_start_s, self._now)
        else:
            self._range_seek_origin = None
        self._seek_grip.Refresh()

    def _move_playback_range(self, local_x: int, *, move_seek: bool) -> None:
        if self._range_drag_origin is None:
            return
        pointer_start_s, start_s, end_s = self._range_drag_origin
        duration_s = end_s - start_s
        pointer_time_s = self._timestamp_at(local_x)
        delta_s = pointer_time_s - pointer_start_s
        start_s = min(
            max(start_s + delta_s, self._coverage[0]),
            self._coverage[1] - duration_s,
        )
        end_s = start_s + duration_s
        start_s = time_snapping.snap_tt_s_to_utc_half_second(start_s)
        end_s = time_snapping.snap_tt_s_to_utc_half_second(end_s)
        start_s = min(max(start_s, self._coverage[0]), self._coverage[1])
        end_s = min(max(end_s, start_s), self._coverage[1])
        self._range_drag_modifier_changed(move_seek, start_s)
        current_time_s: float | None = None
        if move_seek:
            seek_origin = self._range_seek_origin
            assert seek_origin is not None
            seek_start_s, seek_time_s = seek_origin
            current_time_s = seek_time_s + start_s - seek_start_s
            current_time_s = min(max(current_time_s, start_s), end_s)
        self._on_playback(start_s, end_s)
        if current_time_s is not None:
            self._set_value_from_user(
                self._value_at_x(self._x_for(current_time_s))
            )

    def _mouse_wheel(self, event: wx.MouseEvent) -> None:
        rotation = event.GetWheelRotation()
        if rotation:
            direction = 1 if rotation > 0 else -1
            self._set_value_from_user(self._value + direction * 100)

    def _key_down(self, event: wx.KeyEvent) -> None:
        self._range_drag_modifier_changed(event.ControlDown() or event.CmdDown())
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

    def _key_up(self, event: wx.KeyEvent) -> None:
        self._range_drag_modifier_changed(event.ControlDown() or event.CmdDown())
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
        slider_bounds: tuple[float, float] | None = None,
        playback_handles: tuple[float, float] | None = None,
        *,
        unloaded_from_s: float | None = None,
    ) -> None:
        self._coverage, self._playback = coverage, playback
        self._slider_bounds = slider_bounds or coverage
        self._playback_handles = playback_handles or playback
        self._unloaded_from_s = unloaded_from_s
        self._plot_rule, self._now = plot_rule, now_s
        slider_start, slider_end = self._slider_bounds
        playback_start, playback_end = self._playback_handles
        coverage_start, coverage_end = coverage
        self._ranges_ready = (
            unloaded_from_s is None
            and coverage_end > coverage_start
            and slider_end > slider_start
            and playback_end >= playback_start
        )
        self.Refresh()
        self._position_grips()
        for key, grip in self._grips.items():
            if key.startswith("plot"):
                grip.Refresh()

    def SetValue(self, value: int) -> None:
        super().SetValue(value)
        self._position_grips()

    def set_display_time_zone(self, display_time_zone: str) -> None:
        super().set_display_time_zone(display_time_zone)
        self._display_time_zone = display_time_zone
        self._position_grips()

    def _time_for(self, key: str) -> float:
        if key.startswith("playback"):
            return self._playback_handles[0 if key.endswith("start") else 1]
        assert self._plot_rule is not None
        endpoint = (
            self._plot_rule.start if key.endswith("start") else self._plot_rule.end
        )
        if endpoint.mode == "follow":
            return self._playback_handles[0 if key.endswith("start") else 1]
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
        track_center_y = self.GetClientSize().height / 2 - 2
        return abs(position.y - track_center_y) <= 6

    def _show_plot_mode_menu(self, grip: _RangeGrip, position: wx.Point) -> None:
        key = next(key for key, item in self._grips.items() if item is grip)
        name = "start" if key.endswith("start") else "end"
        assert self._plot_rule is not None
        endpoint = self._plot_rule.start if name == "start" else self._plot_rule.end
        matched_bound = "start" if name == "start" else "end"
        labels: tuple[tuple[str, time_range.EndpointMode], ...] = (
            (f"Follow playback {matched_bound}", "follow"),
            ("Follow current time (same gap)", "offset"),
            ("Stay fixed", "fixed"),
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

    def _position_grips(self, _event: wx.Event | None = None) -> None:
        if not getattr(self, "_ranges_ready", False):
            for grip in self._grips.values():
                grip.Hide()
            self._seek_grip.Hide()
            if _event is not None:
                _event.Skip()
            return
        if not self._grips or self._plot_rule is None:
            if _event is not None:
                _event.Skip()
            return
        width = 18
        playback_grip_height = 18
        plot_grip_height = 14
        # Keep endpoint hitboxes clear of the seek marker and on separate rows.
        playback_grip_y = self.GetClientSize().height // 2 + 7
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
            timestamp = self._time_for(key)
            if not _timestamp_is_visible(timestamp, self._slider_bounds):
                grip.Hide()
                continue
            grip.Show()
            slider_position = self.GetPosition()
            is_plot_grip = key.startswith("plot")
            grip_height = plot_grip_height if is_plot_grip else playback_grip_height
            grip_y = 0 if is_plot_grip else playback_grip_y
            grip.SetSize((width, grip_height))
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
        new_seek_position = wx.Point(
            self.GetPosition().x + self._x_for(self._now) - seek_grip_size // 2,
            self.GetPosition().y
            + self.GetClientSize().height // 2
            - 2
            - seek_grip_size // 2,
        )
        old_seek_position = self._seek_grip.GetPosition()
        if self._seek_grip.IsShown() and old_seek_position != new_seek_position:
            old_rect = wx.Rect(
                old_seek_position.x,
                old_seek_position.y,
                seek_grip_size,
                seek_grip_size,
            )
            parent = self.GetParent()
            if parent is not None:
                parent.RefreshRect(old_rect, eraseBackground=True)
            slider_position = self.GetPosition()
            self.RefreshRect(
                wx.Rect(
                    old_seek_position.x - slider_position.x,
                    old_seek_position.y - slider_position.y,
                    seek_grip_size,
                    seek_grip_size,
                ),
                eraseBackground=True,
            )
        self._seek_grip.SetPosition(new_seek_position)
        self._seek_grip.Refresh()
        if self._time_slider_state_set and _timestamp_is_visible(
            self._now, self._slider_bounds
        ):
            self._seek_grip.Show()
            # Range grips are sibling windows and may overlap the seek marker.
            # Keep the seek target on top after all of them are repositioned.
            self._seek_grip.Raise()
            try:
                timestamp = format_tt(
                    self._now,
                    self._display_time_zone,
                    fractional_second_places=0,
                )
                set_tooltip(self._seek_grip, timestamp)
            except (AttributeError, TypeError, OverflowError, ValueError):
                set_tooltip(self._seek_grip, self._seek_grip.GetName())
        else:
            self._seek_grip.Hide()
        if _event is not None:
            _event.Skip()

    def _timestamp_at(self, local_x: int) -> float:
        width = self.GetClientSize().width
        fraction = min(max((local_x - 10) / max(1, width - 20), 0.0), 1.0)
        return self._slider_bounds[0] + fraction * (
            self._slider_bounds[1] - self._slider_bounds[0]
        )

    def _drag(self, grip: _RangeGrip, point: wx.Point) -> None:
        key = next(k for k, item in self._grips.items() if item is grip)
        if key.startswith("plot") and self._plot_mode(grip) == "follow":
            return
        self._on_begin_edit()
        local = grip.ClientToScreen(point)
        target = time_snapping.snap_tt_s_to_utc_half_second(
            self._timestamp_at(self.ScreenToClient(local).x)
        )
        if key.startswith("plot"):
            self._on_plot_endpoint("start" if key.endswith("start") else "end", target)
        else:
            target = min(max(target, self._coverage[0]), self._coverage[1])
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
            start = time_snapping.snap_tt_s_to_utc_half_second(self._coverage[0])
            start = min(max(start, self._coverage[0]), self._coverage[1])
        else:
            end = time_snapping.snap_tt_s_to_utc_half_second(self._coverage[1])
            end = min(max(end, self._coverage[0]), self._coverage[1])
        self._on_playback(start, end)

    def _nudge(self, grip: _RangeGrip, direction: int) -> None:
        key = next(k for k, item in self._grips.items() if item is grip)
        if key.startswith("plot") and self._plot_mode(grip) == "follow":
            return
        step = (self._slider_bounds[1] - self._slider_bounds[0]) / 1000.0 or 1.0
        target = min(
            max(self._time_for(key) + direction * step, self._coverage[0]),
            self._coverage[1],
        )
        target = time_snapping.snap_tt_s_to_utc_half_second(target)
        target = min(max(target, self._coverage[0]), self._coverage[1])
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
