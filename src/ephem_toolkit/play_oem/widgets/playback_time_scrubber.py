"""Zoomable, pannable time scrubber built on PlaybackTimeSlider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import time

import wx

from ephem_toolkit.core import time_utils
from ephem_toolkit.play_oem import time_range

from ..display_time import LOCAL_DISPLAY, UTC_DISPLAY
from .tooltips import set_tooltip
from .playback_time_slider import PlaybackTimeSlider


MINIMUM_VIEWPORT_SECONDS = 10.0
WHEEL_GESTURE_LOCK_SECONDS = 0.25
DEFAULT_CHEVRON_WIDTH = 28
DEFAULT_CHEVRON_HEIGHT = 70


class ChevronButton(wx.Control):
    """Compact, keyboard-accessible chevron control that invokes a callback."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        tooltip: str,
        callback: Callable[[], None],
        *,
        width: int = DEFAULT_CHEVRON_WIDTH,
        height: int = DEFAULT_CHEVRON_HEIGHT,
    ) -> None:
        super().__init__(
            parent,
            wx.ID_ANY,
            size=wx.Size(width, height),
            style=wx.BORDER_THEME | wx.WANTS_CHARS,
        )
        self.SetMinSize(
            self.FromDIP(wx.Size(width, height))
        )
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCanFocus(True)
        self._label = label
        self._callback = callback
        self._scrollable = True
        self._value = True
        self._hovered = False
        self._pressed = False
        self.SetName(tooltip)
        set_tooltip(self, tooltip)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._left_down)
        self.Bind(wx.EVT_LEFT_UP, self._left_up)
        self.Bind(wx.EVT_KEY_DOWN, self._key_down)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_pointer_boundary)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_pointer_boundary)

    def SetValue(self, value: bool) -> None:
        self._value = value
        self.Refresh()

    def GetValue(self) -> bool:
        return self._value

    def set_scrollable(self, scrollable: bool) -> None:
        self._scrollable = scrollable
        self.Enable(scrollable)
        self.SetValue(scrollable)
        self.Refresh()

    def _on_pointer_boundary(self, event: wx.MouseEvent) -> None:
        get_event_type = getattr(event, "GetEventType", lambda: None)
        enter_event_type = getattr(wx.EVT_ENTER_WINDOW, "typeId", None)
        if enter_event_type is not None:
            self._hovered = get_event_type() == enter_event_type
        self.Refresh()
        event.Skip()

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        width, height = self.GetClientSize()
        enabled = self.IsEnabled()
        idle = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
        active = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        if self._pressed:
            face = active
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT)
        elif self._hovered:
            face = wx.Colour(
                (idle.Red() + active.Red()) // 2,
                (idle.Green() + active.Green()) // 2,
                (idle.Blue() + active.Blue()) // 2,
            )
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
        else:
            face = idle
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
        if not enabled:
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(face))
        dc.DrawRectangle(0, 0, width, height)
        font = dc.GetFont()
        font.SetPointSize(max(font.GetPointSize(), 16))
        dc.SetFont(font)
        dc.SetTextForeground(foreground)
        text_width, text_height = dc.GetTextExtent(self._label)
        dc.DrawText(
            self._label,
            (width - text_width) // 2,
            (height - text_height) // 2,
        )

    def _left_down(self, event: wx.MouseEvent) -> None:
        if self._scrollable:
            self._pressed = True
            if not self.HasCapture():
                self.CaptureMouse()
            self.Refresh()
        event.Skip(False)

    def _left_up(self, event: wx.MouseEvent) -> None:
        was_pressed = self._pressed
        self._pressed = False
        if self.HasCapture():
            self.ReleaseMouse()
        position = event.GetPosition()
        inside = 0 <= position.x < self.GetClientSize().width and (
            0 <= position.y < self.GetClientSize().height
        )
        self.Refresh()
        if was_pressed and inside and self._scrollable:
            self._click(event)
        else:
            event.Skip(False)

    def _key_down(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._click(event)
        else:
            event.Skip()

    def _click(self, event: wx.Event) -> None:
        self.SetValue(self._scrollable)
        if self._scrollable:
            self._callback()
        event.Skip(False)


def _consume_vertical_wheel_notches(
    accumulator: int,
    rotation: int,
    wheel_delta: int,
) -> tuple[int, int]:
    accumulator += rotation
    wheel_delta = max(1, wheel_delta)
    threshold = wheel_delta * 2
    if abs(accumulator) < threshold:
        return accumulator, 0
    notches = max(-2, min(2, accumulator // threshold))
    return 0, notches


def _clamp_viewport(
    start_s: float,
    end_s: float,
    coverage: tuple[float, float],
) -> tuple[float, float]:
    coverage_start, coverage_end = coverage
    width = max(MINIMUM_VIEWPORT_SECONDS, end_s - start_s)
    width = min(width, coverage_end - coverage_start)
    start_s = min(max(start_s, coverage_start), coverage_end - width)
    return start_s, start_s + width


def _datetime_in_display_zone(
    timestamp_s: float,
    display_time_zone: str,
) -> datetime:
    moment = time_utils.tt_s_to_datetime(timestamp_s)
    if display_time_zone == LOCAL_DISPLAY:
        return moment.astimezone()
    return moment


def _aligned_tick_start(
    start_s: float,
    step_s: float,
    display_time_zone: str = UTC_DISPLAY,
) -> float:
    moment = _datetime_in_display_zone(start_s, display_time_zone)
    if step_s >= 86400.0:
        midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
        if step_s == 604800.0:
            midnight -= timedelta(days=midnight.weekday())
        elif step_s == 2592000.0:
            midnight = midnight.replace(day=1)
        else:
            midnight_s = time_utils.datetime_to_tt_s(midnight)
            day_step = int(step_s / 86400.0)
            if day_step > 1:
                elapsed_days = int(midnight_s // 86400.0)
                midnight_s -= (elapsed_days % day_step) * 86400.0
                midnight = time_utils.tt_s_to_datetime(midnight_s)
        aligned = time_utils.datetime_to_tt_s(midnight)
    elif step_s >= 3600.0:
        hours = int(step_s / 3600.0)
        if hours not in (1, 3, 6, 12, 24):
            hours = 1
        aligned_moment = moment.replace(
            hour=(moment.hour // hours) * hours,
            minute=0,
            second=0,
            microsecond=0,
        )
        aligned = time_utils.datetime_to_tt_s(aligned_moment)
    elif step_s >= 60.0:
        minutes = int(step_s / 60.0)
        aligned_moment = moment.replace(
            minute=(moment.minute // minutes) * minutes,
            second=0,
            microsecond=0,
        )
        aligned = time_utils.datetime_to_tt_s(aligned_moment)
    else:
        seconds = int(step_s)
        aligned_moment = moment.replace(
            second=(moment.second // seconds) * seconds,
            microsecond=0,
        )
        aligned = time_utils.datetime_to_tt_s(aligned_moment)
    if aligned < start_s:
        aligned += step_s
    return aligned


class TimeTickRail(wx.Control):
    """Paint adaptive time ticks and optionally forward wheel and pan input."""

    def __init__(
        self,
        parent: wx.Window,
        on_wheel: Callable[[wx.MouseEvent], None] | None = None,
        on_pan: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize(wx.Size(-1, 20))
        font = wx.Font(self.GetFont())
        font.SetPointSize(max(8, font.GetPointSize() - 1))
        self.SetFont(font)
        self._viewport = (0.0, 1.0)
        self._display_time_zone = UTC_DISPLAY
        self._middle_tick_s: float | None = None
        self._on_wheel = on_wheel
        self._on_pan = on_pan
        self._drag_start_x: int | None = None
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Bind(wx.EVT_PAINT, self._paint)
        self.Bind(wx.EVT_MOUSEWHEEL, self._mouse_wheel)
        self.Bind(wx.EVT_LEFT_DOWN, self._left_down)
        self.Bind(wx.EVT_LEFT_UP, self._left_up)
        self.Bind(wx.EVT_MOTION, self._motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._capture_lost)

    def set_viewport(self, viewport: tuple[float, float]) -> None:
        self._viewport = viewport
        self.Refresh()

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        self._middle_tick_s = None
        self.Refresh()

    def set_wheel_handler(
        self,
        on_wheel: Callable[[wx.MouseEvent], None] | None,
    ) -> None:
        self._on_wheel = on_wheel

    def set_pan_handler(
        self,
        on_pan: Callable[[float], None] | None,
    ) -> None:
        self._on_pan = on_pan

    def _mouse_wheel(self, event: wx.MouseEvent) -> None:
        if self._on_wheel is not None:
            self._on_wheel(event)
        event.Skip(False)

    def _left_down(self, event: wx.MouseEvent) -> None:
        self._drag_start_x = event.GetX()
        if not self.HasCapture():
            self.CaptureMouse()
        event.Skip(False)

    def _left_up(self, event: wx.MouseEvent) -> None:
        self._drag_start_x = None
        if self.HasCapture():
            self.ReleaseMouse()
        event.Skip(False)

    def _capture_lost(self, _event: wx.MouseCaptureLostEvent) -> None:
        self._drag_start_x = None

    def _motion(self, event: wx.MouseEvent) -> None:
        if (
            self._drag_start_x is None
            or not event.Dragging()
            or not event.LeftIsDown()
            or self._on_pan is None
        ):
            event.Skip(False)
            return
        x = event.GetX()
        delta_x = x - self._drag_start_x
        self._drag_start_x = x
        usable_width = max(1, self.GetClientSize().width - 20)
        fraction = -delta_x / usable_width
        if abs(fraction) > 1e-6:
            self._on_pan(fraction)
        event.Skip(False)

    def _paint(self, _event: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        width, height = self.GetClientSize()
        if width <= 20:
            return
        left, right = 10, width - 10
        dc.SetPen(wx.Pen(wx.Colour("#bfc8d4"), 1))
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(wx.Colour("#607188"))
        start_s, end_s = self._viewport
        duration_s = max(1.0, end_s - start_s)
        target_ticks = max(2, round((right - left) / 60.0))
        desired_step = duration_s / target_ticks
        candidates = (
            1.0, 2.0, 5.0, 10.0, 20.0, 30.0,
            60.0, 120.0, 300.0, 600.0, 900.0, 1800.0,
            3600.0, 10800.0, 21600.0, 43200.0,
            86400.0, 172800.0, 259200.0, 604800.0,
            1209600.0, 2592000.0,
        )
        step_s = next(
            (candidate for candidate in candidates if candidate >= desired_step),
            candidates[-1],
        )
        first_tick = _aligned_tick_start(
            start_s,
            step_s,
            self._display_time_zone,
        )
        if self._middle_tick_s is not None:
            anchor_s = self._middle_tick_s
            if start_s <= anchor_s <= end_s:
                offset = round((anchor_s - first_tick) / step_s)
                anchored_tick = first_tick + offset * step_s
                while anchored_tick > end_s:
                    anchored_tick -= step_s
                while anchored_tick < start_s:
                    anchored_tick += step_s
                first_tick = anchored_tick
                while first_tick - step_s >= start_s:
                    first_tick -= step_s
        major_x_step = (step_s / duration_s) * (right - left)
        subdivisions = 5 if major_x_step >= 50.0 else 2 if major_x_step >= 24.0 else 0
        if subdivisions:
            timestamp = first_tick - step_s
            while timestamp <= end_s:
                for division in range(1, subdivisions):
                    minor_s = timestamp + step_s * division / subdivisions
                    if minor_s < start_s or minor_s > end_s:
                        continue
                    fraction = (minor_s - start_s) / duration_s
                    x = round(left + fraction * (right - left))
                    dc.DrawLine(x, 0, x, 1)
                timestamp += step_s
        timestamp = first_tick
        middle_s = (start_s + end_s) / 2.0
        nearest_middle_tick: float | None = None
        nearest_middle_distance = float("inf")
        major_ticks: list[tuple[float, int, str, int]] = []
        while timestamp <= end_s:
            distance = abs(timestamp - middle_s)
            if distance < nearest_middle_distance:
                nearest_middle_distance = distance
                nearest_middle_tick = timestamp
            fraction = (timestamp - start_s) / duration_s
            x = round(left + fraction * (right - left))
            dc.DrawLine(x, 0, x, 3)
            moment = _datetime_in_display_zone(timestamp, self._display_time_zone)
            hour = moment.hour
            if step_s >= 86400.0:
                label = moment.strftime("%Y-%m-%d")
            elif step_s >= 3600.0:
                label = f"{hour:02d}:00"
            elif step_s >= 60.0:
                label = f"{hour:02d}:{moment.minute:02d}"
            else:
                label = f"{hour:02d}:{moment.minute:02d}:{moment.second:02d}"
            text_width = dc.GetTextExtent(label).width
            major_ticks.append((timestamp, x, label, text_width))
            timestamp += step_s
        if major_ticks:
            widest = max(item[3] for item in major_ticks)
            label_stride = max(
                1,
                int((widest + 8.0 + major_x_step - 1.0) // major_x_step),
            )
            label_offset = 0
            if nearest_middle_tick is not None:
                for index, (timestamp, _x, _label, _width) in enumerate(major_ticks):
                    if timestamp == nearest_middle_tick:
                        label_offset = index % label_stride
                        break
            dc.SetClippingRegion(left, 0, right - left, height)
            for index, (_timestamp, x, label, text_width) in enumerate(major_ticks):
                if (index - label_offset) % label_stride != 0:
                    continue
                text_height = dc.GetTextExtent(label).height
                label_y = max(1, min(5, height - text_height - 3))
                dc.DrawText(label, x - text_width // 2, label_y)
            dc.DestroyClippingRegion()
        if nearest_middle_tick is not None:
            self._middle_tick_s = nearest_middle_tick


class PlaybackTimeScrubber(PlaybackTimeSlider):
    """Advanced zoomable, pannable time range control."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        coverage: tuple[float, float],
        playback: tuple[float, float],
        plot_rule: time_range.PlotTimeRange,
        now_s: float,
        viewport: tuple[float, float] | None = None,
        playback_handles: tuple[float, float] | None = None,
        on_playback: Callable[[float, float], None],
        on_plot_endpoint: Callable[[str, float], None],
        on_plot_endpoint_mode: Callable[[str, time_range.EndpointMode], None] | None = None,
        on_begin_edit: Callable[[], None] | None = None,
        on_range_dragging: Callable[[bool], None] | None = None,
        on_viewport: Callable[[tuple[float, float]], None] | None = None,
        timeline_tooltip_at: Callable[[float], str] | None = None,
    ) -> None:
        self._coverage = coverage
        self._viewport = _clamp_viewport(viewport[0], viewport[1], coverage) if viewport else coverage
        self._playback = playback
        self._plot_rule = plot_rule
        self._now = now_s
        self._playback_handles = playback_handles or playback
        self._unloaded_from_s = None
        self._on_viewport = on_viewport or (lambda _viewport: None)
        self._vertical_wheel_accumulator = 0
        self._wheel_gesture_axis: int | None = None
        self._wheel_gesture_last_at = 0.0
        self._viewport_fits_coverage = True
        super().__init__(
            parent,
            on_playback=on_playback,
            on_plot_endpoint=on_plot_endpoint,
            on_plot_endpoint_mode=on_plot_endpoint_mode or (lambda _name, _mode: None),
            on_begin_edit=on_begin_edit or (lambda: None),
            on_range_dragging=on_range_dragging,
            timeline_tooltip_at=timeline_tooltip_at,
        )
        self._coverage = coverage
        self._viewport = _clamp_viewport(
            viewport[0],
            viewport[1],
            coverage,
        ) if viewport else coverage
        self._playback = playback
        self._plot_rule = plot_rule
        self._now = now_s
        self._playback_handles = playback_handles or playback
        self._unloaded_from_s = None
        self._vertical_wheel_accumulator = 0
        self._wheel_gesture_axis: int | None = None
        self._wheel_gesture_last_at = 0.0
        self._viewport_fits_coverage = True
        self.SetName("Scrollable PlaybackTimeScrubber")
        self.SetMinSize(wx.Size(480, 50))
        self._apply_viewport(self._viewport)

    def set_viewport(self, viewport: tuple[float, float]) -> None:
        self._apply_viewport(viewport)

    @property
    def viewport(self) -> tuple[float, float]:
        """Return the visible TT interval."""
        return self._viewport

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
        preserve_full_coverage = self._viewport_fits_coverage
        self._coverage = coverage
        self._playback = playback
        self._plot_rule = plot_rule
        self._now = now_s
        if playback_handles is not None:
            self._playback_handles = playback_handles
        elif not hasattr(self, "_playback_handles"):
            self._playback_handles = playback
        self._unloaded_from_s = unloaded_from_s
        requested_viewport = (
            coverage
            if preserve_full_coverage
            else (slider_bounds or coverage)
        )
        self._viewport = _clamp_viewport(
            requested_viewport[0],
            requested_viewport[1],
            coverage,
        )
        super().set_ranges(
            coverage,
            playback,
            plot_rule,
            now_s,
            self._viewport,
            self._playback_handles,
            unloaded_from_s=unloaded_from_s,
        )
        self._viewport_fits_coverage = (
            abs(self._viewport[0] - coverage[0]) <= 1e-6
            and abs(self._viewport[1] - coverage[1]) <= 1e-6
        )
        self._on_viewport(self._viewport)

    def set_state(
        self,
        *,
        coverage: tuple[float, float] | None = None,
        playback: tuple[float, float] | None = None,
        playback_handles: tuple[float, float] | None = None,
        plot_rule: time_range.PlotTimeRange | None = None,
        now_s: float | None = None,
        viewport: tuple[float, float] | None = None,
    ) -> None:
        if coverage is not None:
            self._coverage = coverage
        if playback is not None:
            self._playback = playback
        if playback_handles is not None:
            self._playback_handles = playback_handles
        if plot_rule is not None:
            self._plot_rule = plot_rule
        if now_s is not None:
            self._now = now_s
        if coverage is not None and self._viewport_fits_coverage and viewport is None:
            viewport = coverage
        self._apply_viewport(viewport or self._viewport)

    def seek_to_fraction(self, fraction: float) -> None:
        start_s, end_s = self._viewport
        timestamp = start_s + min(max(fraction, 0.0), 1.0) * (end_s - start_s)
        timestamp = min(max(timestamp, self._playback[0]), self._playback[1])
        self._now = timestamp
        self._apply_viewport(self._viewport)

    def _apply_viewport(self, viewport: tuple[float, float]) -> None:
        self._viewport = _clamp_viewport(viewport[0], viewport[1], self._coverage)
        self._viewport_fits_coverage = (
            abs(self._viewport[0] - self._coverage[0]) <= 1e-6
            and abs(self._viewport[1] - self._coverage[1]) <= 1e-6
        )
        assert self._plot_rule is not None
        self.set_ranges(
            self._coverage,
            self._playback,
            self._plot_rule,
            self._now,
            slider_bounds=self._viewport,
            playback_handles=self._playback,
        )
        self._on_viewport(self._viewport)

    def pan(self, fraction: float) -> None:
        start_s, end_s = self._viewport
        shift = (end_s - start_s) * fraction
        self._apply_viewport(_clamp_viewport(start_s + shift, end_s + shift, self._coverage))

    def fit(self) -> None:
        self._apply_viewport(self._coverage)

    def zoom_around(self, fraction: float, factor: float) -> None:
        start_s, end_s = self._viewport
        fraction = min(max(fraction, 0.0), 1.0)
        anchor_s = start_s + fraction * (end_s - start_s)
        width_s = min(
            self._coverage[1] - self._coverage[0],
            max(MINIMUM_VIEWPORT_SECONDS, (end_s - start_s) * factor),
        )
        new_start = anchor_s - fraction * width_s
        self._apply_viewport(_clamp_viewport(new_start, new_start + width_s, self._coverage))

    def zoom_in(self, fraction: float = 0.5) -> None:
        self.zoom_around(fraction, 0.97)

    def zoom_out(self, fraction: float = 0.5) -> None:
        self.zoom_around(fraction, 1.03)

    def _mouse_wheel(self, event: wx.MouseEvent) -> None:
        rotation = event.GetWheelRotation()
        if not rotation:
            return
        now = time.monotonic()
        if (
            now - self._wheel_gesture_last_at
            > WHEEL_GESTURE_LOCK_SECONDS
        ):
            self._wheel_gesture_axis = None
            self._vertical_wheel_accumulator = 0

        axis = event.GetWheelAxis()
        if self._wheel_gesture_axis is None:
            self._wheel_gesture_axis = axis
        elif axis != self._wheel_gesture_axis:
            self._wheel_gesture_last_at = now
            return
        self._wheel_gesture_last_at = now

        if axis == wx.MOUSE_WHEEL_HORIZONTAL:
            wheel_delta = max(1, event.GetWheelDelta())
            notches = rotation / wheel_delta
            self.pan(max(-1.0, min(1.0, notches * 0.05)))
            return
        fraction = event.GetX() / max(1, self.GetClientSize().width)
        wheel_delta = max(1, event.GetWheelDelta())
        self._vertical_wheel_accumulator, notches = _consume_vertical_wheel_notches(
            self._vertical_wheel_accumulator,
            rotation,
            wheel_delta,
        )
        for _ in range(abs(notches)):
            if notches > 0:
                self.zoom_in(fraction)
            else:
                self.zoom_out(fraction)

    def _key_down(self, event: wx.KeyEvent) -> None:
        control_down = event.ControlDown()
        command_down = getattr(event, "CmdDown", lambda: False)()
        if control_down or command_down:
            key = event.GetKeyCode()
            unicode_key = getattr(event, "GetUnicodeKey", lambda: 0)()
            character = (
                chr(unicode_key)
                if isinstance(unicode_key, int) and 32 <= unicode_key <= 126
                else ""
            )
            if key == ord("0") or character == "0":
                self.fit()
            elif key in (ord("+"), ord("="), wx.WXK_ADD) or character in ("+", "="):
                self.zoom_in()
            elif key in (ord("-"), wx.WXK_SUBTRACT) or character == "-":
                self.zoom_out()
            else:
                super()._key_down(event)
            return
        super()._key_down(event)


class PlaybackTimeScrubberWidget(wx.Panel):
    """Composite time scrubber with its track, tick rail, and pan controls."""

    def __init__(
        self,
        parent: wx.Window,
        *,
        coverage: tuple[float, float],
        playback: tuple[float, float],
        plot_rule: time_range.PlotTimeRange,
        now_s: float,
        viewport: tuple[float, float] | None = None,
        playback_handles: tuple[float, float] | None = None,
        on_playback: Callable[[float, float], None],
        on_plot_endpoint: Callable[[str, float], None],
        on_plot_endpoint_mode: (
            Callable[[str, time_range.EndpointMode], None] | None
        ) = None,
        on_begin_edit: Callable[[], None] | None = None,
        on_range_dragging: Callable[[bool], None] | None = None,
        on_viewport: Callable[[tuple[float, float]], None] | None = None,
        timeline_tooltip_at: Callable[[float], str] | None = None,
        display_time_zone: str = UTC_DISPLAY,
        timeline_enabled: bool = True,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self._coverage = coverage
        self._timeline_enabled = timeline_enabled
        self._on_viewport_callback = on_viewport or (lambda _viewport: None)

        self.left_chevron = ChevronButton(
            self,
            "‹",
            "Pan earlier",
            lambda: self.slider.pan(-0.10),
        )
        self.right_chevron = ChevronButton(
            self,
            "›",
            "Pan later",
            lambda: self.slider.pan(0.10),
        )
        self.column = wx.Panel(self, wx.ID_ANY)
        self.column.SetBackgroundColour(self.GetBackgroundColour())
        column_sizer = wx.BoxSizer(wx.VERTICAL)
        self.column.SetSizer(column_sizer)
        self.tick_rail = TimeTickRail(self.column)
        self.tick_rail.set_viewport(viewport if viewport is not None else coverage)
        self.tick_rail.set_display_time_zone(display_time_zone)
        self.slider = PlaybackTimeScrubber(
            self.column,
            coverage=coverage,
            playback=playback,
            plot_rule=plot_rule,
            now_s=now_s,
            viewport=viewport,
            playback_handles=playback_handles,
            on_playback=on_playback,
            on_plot_endpoint=on_plot_endpoint,
            on_plot_endpoint_mode=on_plot_endpoint_mode,
            on_begin_edit=on_begin_edit,
            on_range_dragging=on_range_dragging,
            on_viewport=self._viewport_changed,
            timeline_tooltip_at=timeline_tooltip_at,
        )
        self.slider.set_display_time_zone(display_time_zone)
        self.slider.Enable(timeline_enabled)
        self.tick_rail.Enable(timeline_enabled)
        self.tick_rail.set_wheel_handler(self.slider._mouse_wheel)
        self.tick_rail.set_pan_handler(self.slider.pan)
        column_sizer.Add(self.slider, 1, wx.EXPAND)
        column_sizer.Add(self.tick_rail, 0, wx.EXPAND)

        layout = wx.BoxSizer(wx.HORIZONTAL)
        layout.Add(self.left_chevron, 0, wx.ALIGN_CENTER_VERTICAL)
        layout.Add(self.column, 1, wx.EXPAND)
        layout.Add(self.right_chevron, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(layout)
        self._viewport_changed(self.slider.viewport)

    def _viewport_changed(self, viewport: tuple[float, float]) -> None:
        self.tick_rail.set_viewport(viewport)
        start_s, end_s = viewport
        slider = getattr(self, "slider", None)
        coverage_start, coverage_end = getattr(slider, "_coverage", self._coverage)
        epsilon = max(1e-6, (coverage_end - coverage_start) * 1e-9)
        left_enabled = self._timeline_enabled and start_s > coverage_start + epsilon
        right_enabled = self._timeline_enabled and end_s < coverage_end - epsilon
        self.left_chevron.set_scrollable(left_enabled)
        self.right_chevron.set_scrollable(right_enabled)
        self.left_chevron.SetCursor(
            wx.Cursor(wx.CURSOR_HAND if left_enabled else wx.CURSOR_ARROW)
        )
        self.right_chevron.SetCursor(
            wx.Cursor(wx.CURSOR_HAND if right_enabled else wx.CURSOR_ARROW)
        )
        self._on_viewport_callback(viewport)

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self.slider.set_display_time_zone(display_time_zone)
        self.tick_rail.set_display_time_zone(display_time_zone)

    def set_enabled(self, enabled: bool) -> None:
        self._timeline_enabled = enabled
        self.Enable(enabled)
        self.slider.Enable(enabled)
        self.tick_rail.Enable(enabled)
        self._viewport_changed(self.slider.viewport)

