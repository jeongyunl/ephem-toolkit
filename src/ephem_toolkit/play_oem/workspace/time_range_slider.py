"""Native playback slider with four keyboard and pointer range grips."""

from __future__ import annotations

from collections.abc import Callable

import wx

from .. import time_range
from ..tooltips import set_tooltip
from ephem_toolkit.core import time_utils


def _triangle_vertices(
    kind: str, center_x: int, center_y: int
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    if kind == "playback":
        return (
            (center_x, center_y - 6),
            (center_x + 6, center_y + 5),
            (center_x - 6, center_y + 5),
        )
    return (
        (center_x, center_y + 5),
        (center_x + 6, center_y - 6),
        (center_x - 6, center_y - 6),
    )


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
            vertices = _triangle_vertices(self.kind, cx, cy)
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
        self._dragging = True
        if not self.HasCapture():
            self.CaptureMouse()
        self.slider._drag(self, event.GetPosition())

    def _double_click(self, event: wx.MouseEvent) -> None:
        if self.kind == "playback":
            self.slider._snap_playback_handle(self)
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


class TimeRangeSlider(wx.Slider):
    """A wx.Slider retaining its native seek thumb and adding four range grips."""

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
        on_begin_edit: Callable[[], None],
    ) -> None:
        super().__init__(parent, wx.ID_ANY, 0, 0, 10_000, style=wx.SL_HORIZONTAL)
        self.SetName("Playback timeline and time range handles")
        # Leave a small handle-to-track gap without pushing transport controls down.
        self.SetMinSize(wx.Size(-1, max(58, self.GetBestSize().height + 20)))
        self._on_playback = on_playback
        self._on_plot_endpoint = on_plot_endpoint
        self._on_begin_edit = on_begin_edit
        self._coverage = (0.0, 1.0)
        self._playback = (0.0, 1.0)
        self._plot_rule: time_range.PlotTimeRange | None = None
        self._now = 0.0
        self._grips: dict[str, _RangeGrip] = {}
        for key, name, kind, color in self._KINDS:
            # GTK native sliders are not reliable child-window hosts. Keep the
            # grips as siblings in the slider's parent and position them over it.
            grip = _RangeGrip(self.GetParent(), self, name, kind, color)
            self._grips[key] = grip
        self.Bind(wx.EVT_SIZE, self._on_size)

    def set_ranges(
        self,
        coverage: tuple[float, float],
        playback: tuple[float, float],
        plot_rule: time_range.PlotTimeRange,
        now_s: float,
    ) -> None:
        self._coverage, self._playback = coverage, playback
        self._plot_rule, self._now = plot_rule, now_s
        self._position_grips()

    def _time_for(self, key: str) -> float:
        if key.startswith("playback"):
            return self._playback[0 if key.endswith("start") else 1]
        assert self._plot_rule is not None
        endpoint = (
            self._plot_rule.start if key.endswith("start") else self._plot_rule.end
        )
        return endpoint.value_s + (self._now if endpoint.mode == "offset" else 0.0)

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
        if not self._grips:
            if _event is not None:
                _event.Skip()
            return
        width = height = 18
        playback_grip_y = 43
        # Keep the two handle rows equally spaced around the native slider track.
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
                if is_playback:
                    mode = "fixed UTC"
                else:
                    assert self._plot_rule is not None
                    endpoint = (
                        self._plot_rule.start
                        if key.endswith("start")
                        else self._plot_rule.end
                    )
                    mode = (
                        "fixed UTC" if endpoint.mode == "fixed" else "playback offset"
                    )
                utc = time_utils.datetime_to_iso8601(
                    time_utils.tt_s_to_datetime(self._time_for(key)),
                    fractional_second_places=0,
                )
                if is_playback:
                    bound = "start" if key.endswith("start") else "end"
                    tooltip = f"Playback {bound}: {utc} UTC"
                else:
                    tooltip = f"{grip.GetName()}: {utc} UTC ({mode})"
                set_tooltip(grip, tooltip)
            except (AttributeError, TypeError, OverflowError, ValueError):
                set_tooltip(grip, grip.GetName())
        if _event is not None:
            _event.Skip()

    def _timestamp_at(self, local_x: int) -> float:
        width = self.GetClientSize().width
        fraction = min(max((local_x - 10) / max(1, width - 20), 0.0), 1.0)
        return self._coverage[0] + fraction * (self._coverage[1] - self._coverage[0])

    def _drag(self, grip: _RangeGrip, point: wx.Point) -> None:
        self._on_begin_edit()
        local = grip.ClientToScreen(point)
        target = self._timestamp_at(self.ScreenToClient(local).x)
        key = next(k for k, item in self._grips.items() if item is grip)
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
