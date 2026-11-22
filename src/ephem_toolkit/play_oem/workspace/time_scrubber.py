"""Zoomable, pannable time scrubber built on TimeSlider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import time

import wx

from ephem_toolkit.core import time_utils
from ephem_toolkit.play_oem import time_range

from ..tooltips import set_tooltip
from .time_slider import TimeSlider


MINIMUM_VIEWPORT_SECONDS = 10.0
WHEEL_GESTURE_LOCK_SECONDS = 0.25
TIMESCRUBBER_TRACK_HEIGHT = 74


class TimeScrubberChevronButton(wx.ToggleButton):
    """Compact toggle-styled chevron button for TimeScrubber pan controls."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        tooltip: str,
        callback: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            wx.ID_ANY,
            label,
            size=wx.Size(30, TIMESCRUBBER_TRACK_HEIGHT),
            style=wx.BU_EXACTFIT,
        )
        self._callback = callback
        self._scrollable = True
        self.SetName(tooltip)
        set_tooltip(self, tooltip)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        font = self.GetFont()
        font.SetPointSize(max(font.GetPointSize(), 18))
        self.SetFont(font)
        self.SetValue(True)
        self.Bind(wx.EVT_TOGGLEBUTTON, self._click)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_pointer_boundary)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_pointer_boundary)

    def set_scrollable(self, scrollable: bool) -> None:
        self._scrollable = scrollable
        self.Enable(scrollable)
        self.SetValue(scrollable)
        self.Refresh()

    def _on_pointer_boundary(self, event: wx.MouseEvent) -> None:
        self.Refresh()
        event.Skip()

    def _click(self, event: wx.CommandEvent) -> None:
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


def _aligned_tick_start(start_s: float, step_s: float) -> float:
    moment = time_utils.tt_s_to_datetime(start_s)
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


class TimeScrubberTickRail(wx.Control):
    """Painted adaptive major and minor ticks for a TimeScrubber."""

    def __init__(
        self,
        parent: wx.Window,
        on_wheel: Callable[[wx.MouseEvent], None] | None = None,
        on_pan: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(parent, wx.ID_ANY)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize(wx.Size(-1, 18))
        font = wx.Font(self.GetFont())
        font.SetPointSize(font.GetPointSize() + 1)
        self.SetFont(font)
        self._viewport = (0.0, 1.0)
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
        width = self.GetClientSize().width
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
        first_tick = _aligned_tick_start(start_s, step_s)
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
            dc.DrawLine(x, 0, x, 5)
            moment = time_utils.tt_s_to_datetime(timestamp)
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
            for index, (_timestamp, x, label, text_width) in enumerate(major_ticks):
                if (index - label_offset) % label_stride != 0:
                    continue
                label_left = max(left, min(x - text_width // 2, right - text_width))
                dc.DrawText(label, label_left, 5)
        if nearest_middle_tick is not None:
            self._middle_tick_s = nearest_middle_tick


class TimeScrubber(TimeSlider):
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
        self.SetName("Scrollable TimeScrubber")
        self.SetMinSize(wx.Size(480, 56))
        self.Bind(wx.EVT_LEFT_DCLICK, self._fit)
        self._apply_viewport(self._viewport)

    def set_viewport(self, viewport: tuple[float, float]) -> None:
        self._apply_viewport(viewport)

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

    def _fit(self, _event: wx.MouseEvent) -> None:
        self.fit()

    def _key_down(self, event: wx.KeyEvent) -> None:
        control_down = event.ControlDown()
        command_down = getattr(event, "CmdDown", lambda: False)()
        if control_down or command_down:
            key = event.GetKeyCode()
            unicode_key = getattr(event, "GetUnicodeKey", lambda: "")()
            character = chr(unicode_key) if isinstance(unicode_key, str) else ""
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
