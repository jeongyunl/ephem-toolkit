"""Tests for playback timeline handle geometry."""

from types import SimpleNamespace
from typing import Any, Optional, cast

import pytest
import wx

from ephem_toolkit.play_oem.time_range import EndpointMode
from ephem_toolkit.play_oem.widgets.playback_time_slider import (
    _RangeGrip as _RangeGripClass,
    _SeekGrip as _SeekGripClass,
    PlaybackTimeSlider as _PlaybackTimeSliderClass,
    _plot_grip_y,
    _plot_handle_vertices,
    _plot_tooltip_text,
    _timestamp_is_visible,
    _triangle_vertices,
)

# These tests exercise wx handlers with lightweight fakes rather than native
# widgets, so keep unbound handler calls dynamic at the test boundary.
_RangeGrip: Any = cast(Any, _RangeGripClass)
_SeekGrip: Any = cast(Any, _SeekGripClass)
PlaybackTimeSlider: Any = cast(Any, _PlaybackTimeSliderClass)


def test_plot_triangle_points_down_and_matches_playback_size() -> None:
    playback = _triangle_vertices("playback", 20, 20)
    plot = _triangle_vertices("plot", 20, 20)

    def dimensions(vertices: tuple[tuple[int, int], ...]) -> tuple[int, int]:
        xs, ys = zip(*vertices)
        return max(xs) - min(xs), max(ys) - min(ys)

    assert dimensions(plot) == (12, 8)
    assert dimensions(playback) == (12, 6)
    assert plot[0][1] == max(y for _x, y in plot)
    assert playback[0][1] == min(y for _x, y in playback)


def test_plot_handle_shape_distinguishes_each_mode() -> None:
    follow = _plot_handle_vertices("follow", 20, 20)
    offset = _plot_handle_vertices("offset", 20, 20)
    fixed = _plot_handle_vertices("fixed", 20, 20)

    assert len(follow) == 3
    assert len(offset) == len(fixed) == 4
    assert offset != fixed
    assert max(x for x, _y in offset) - min(x for x, _y in offset) == 12
    assert max(y for _x, y in offset) - min(y for _x, y in offset) == 7
    assert max(x for x, _y in fixed) - min(x for x, _y in fixed) == 10
    assert max(y for _x, y in fixed) - min(y for _x, y in fixed) == 5


@pytest.mark.parametrize(
    ("mode", "mode_label"),
    [
        ("follow", "Automatically follows playback start time"),
        ("offset", "Follows current time, keeping the same time gap"),
        ("fixed", "Stays at this time; does not follow"),
    ],
)
def test_plot_handle_tooltip_is_two_lines(mode: EndpointMode, mode_label: str) -> None:
    tooltip = _plot_tooltip_text("Plot start", "2026-05-21T04:36:45", mode)

    assert tooltip.splitlines() == [
        "Plot start: 2026-05-21T04:36:45",
        f"{mode_label} | Right-click to change",
    ]


def test_plot_grip_is_as_close_to_the_track_as_the_playback_grip() -> None:
    playback_grip_y = 39
    grip_height = 18

    for slider_height in (58, 74):
        plot_grip_y = _plot_grip_y(slider_height, playback_grip_y, grip_height)
        slider_track_y = slider_height / 2
        playback_center_y = playback_grip_y + grip_height / 2
        plot_center_y = plot_grip_y + grip_height / 2

        assert slider_track_y - plot_center_y == playback_center_y - slider_track_y


@pytest.mark.parametrize(
    ("timestamp", "visible"),
    [(-1.0, False), (0.0, True), (50.0, True), (100.0, True), (101.0, False)],
)
def test_grips_and_seek_marker_only_render_inside_visible_range(
    timestamp: float,
    visible: bool,
) -> None:
    assert _timestamp_is_visible(timestamp, (0.0, 100.0)) is visible


def test_follow_plot_handle_ignores_dragging_and_keyboard_nudging() -> None:
    grip = object()
    slider = SimpleNamespace(
        _grips={"plot_start": grip},
        _plot_mode=lambda _grip: "follow",
        _on_begin_edit=lambda: pytest.fail("Follow handle must not begin an edit"),
        _coverage=(0.0, 100.0),
    )

    PlaybackTimeSlider._drag(slider, grip, None)
    PlaybackTimeSlider._nudge(slider, grip, 1)


@pytest.mark.parametrize(
    ("pointer_y", "expected"),
    [(35, True), (29, True), (28, False), (41, True), (42, False)],
)
def test_timeline_tooltip_hotspot_is_limited_to_track_band(
    pointer_y: int, expected: bool
) -> None:
    slider = SimpleNamespace(
        GetClientSize=lambda: SimpleNamespace(height=74),
    )

    assert (
        PlaybackTimeSlider.is_pointer_over_timeline_track(
            slider, SimpleNamespace(y=pointer_y)
        )
        is expected
    )


def test_track_highlight_follows_hover_and_seek_drag() -> None:
    refreshes: list[bool] = []
    seek_grip = object()
    slider = SimpleNamespace(
        _pointer_over_track=False,
        _drag_source=None,
        _seek_grip=seek_grip,
        Refresh=lambda: refreshes.append(True),
    )
    highlighted = PlaybackTimeSlider._track_is_highlighted.__get__

    assert not highlighted(slider)
    PlaybackTimeSlider._set_track_hover(slider, True)
    assert highlighted(slider)
    PlaybackTimeSlider._set_track_hover(slider, False)
    assert not highlighted(slider)

    slider._drag_source = seek_grip
    assert highlighted(slider)
    slider._drag_source = slider
    assert highlighted(slider)
    slider._drag_source = object()
    assert not highlighted(slider)
    assert len(refreshes) == 2


def test_playback_connector_highlights_only_between_handles() -> None:
    slider = SimpleNamespace(
        _pointer_position=SimpleNamespace(x=50, y=54),
        _drag_source=None,
        _playback_handles=(20.0, 80.0),
        _slider_bounds=(0.0, 100.0),
        GetClientSize=lambda: SimpleNamespace(height=74),
        _x_for=lambda value: int(value),
        _pointer_between_playback_handles=lambda position: (
            PlaybackTimeSlider._pointer_between_playback_handles(slider, position)
        ),
    )

    assert PlaybackTimeSlider._playback_connector_hovered.__get__(slider)

    slider._pointer_position = SimpleNamespace(x=15, y=54)
    assert not PlaybackTimeSlider._playback_connector_hovered.__get__(slider)
    slider._pointer_position = SimpleNamespace(x=50, y=45)
    assert not PlaybackTimeSlider._playback_connector_hovered.__get__(slider)
    slider._pointer_position = SimpleNamespace(x=50, y=54)
    slider._drag_source = object()
    assert not PlaybackTimeSlider._playback_connector_hovered.__get__(slider)


@pytest.mark.parametrize(
    ("handles", "visible", "pointer", "expected"),
    [
        ((-50.0, 50.0), (0.0, 100.0), (30, 54), True),
        ((50.0, 150.0), (0.0, 100.0), (70, 54), True),
        ((-50.0, -10.0), (0.0, 100.0), (10, 54), False),
        ((110.0, 150.0), (0.0, 100.0), (90, 54), False),
    ],
)
def test_playback_connector_intersects_partially_visible_range(
    handles: tuple[float, float],
    visible: tuple[float, float],
    pointer: tuple[int, int],
    expected: bool,
) -> None:
    slider = SimpleNamespace(
        _pointer_position=SimpleNamespace(x=pointer[0], y=pointer[1]),
        _drag_source=None,
        _range_drag_origin=None,
        _playback_handles=handles,
        _slider_bounds=visible,
        GetClientSize=lambda: SimpleNamespace(height=74, width=100),
        _x_for=lambda value: (
            10 + round(
                min(max((value - visible[0]) / (visible[1] - visible[0]), 0.0), 1.0)
                * 80
            )
        ),
    )

    assert (
        PlaybackTimeSlider._pointer_between_playback_handles(
            slider, slider._pointer_position
        )
        is expected
    )


def test_track_highlight_uses_outline_without_changing_track_fill(monkeypatch) -> None:
    highlight, transparent = object(), object()
    rectangles: list[tuple[tuple[int, ...], object, object]] = []

    class FakeDC:
        def SetBackground(self, _brush: object) -> None:
            pass

        def Clear(self) -> None:
            pass

        def SetPen(self, pen: object) -> None:
            self.pen = pen

        def SetBrush(self, brush: object) -> None:
            self.brush = brush

        def DrawRoundedRectangle(
            self, x: int, y: int, width: int, height: int, radius: int
        ) -> None:
            rectangles.append(((x, y, width, height, radius), self.pen, self.brush))

    dc = FakeDC()
    monkeypatch.setattr(wx, "AutoBufferedPaintDC", lambda _window: dc)
    monkeypatch.setattr(wx, "Brush", lambda color: ("brush", color))
    monkeypatch.setattr(wx, "Pen", lambda color, width: ("pen", color, width))
    monkeypatch.setattr(wx, "Colour", lambda color: color)
    monkeypatch.setattr(wx, "TRANSPARENT_BRUSH", transparent)
    monkeypatch.setattr(wx.SystemSettings, "GetColour", lambda _id: highlight)
    slider = SimpleNamespace(
        GetBackgroundColour=lambda: SimpleNamespace(
            Red=lambda: 0,
            Green=lambda: 0,
            Blue=lambda: 0,
        ),
        GetClientSize=lambda: (100, 74),
        _track_is_highlighted=False,
        _playback_connector_hovered=False,
        _time_slider_state_set=True,
        _playable_segment_x=lambda: None,
        _unloaded_segment_x=lambda: None,
        _now=101.0,
        _slider_bounds=(0.0, 100.0),
    )

    PlaybackTimeSlider._paint_track(slider, None)
    idle_track = rectangles[-1]
    slider._track_is_highlighted = True
    PlaybackTimeSlider._paint_track(slider, None)

    assert rectangles[-2] == idle_track
    assert rectangles[-1][1] == ("pen", highlight, 2)
    assert rectangles[-1][2] is transparent


def test_hovered_playback_connector_draws_line_between_handles(monkeypatch) -> None:
    highlight = object()
    lines = []

    class FakeDC:
        def SetBackground(self, _brush: object) -> None:
            pass

        def Clear(self) -> None:
            pass

        def SetPen(self, pen: object) -> None:
            self.pen = pen

        def SetBrush(self, _brush: object) -> None:
            pass

        def DrawRoundedRectangle(
            self, _x: int, _y: int, _width: int, _height: int, _radius: int
        ) -> None:
            pass

        def DrawLine(self, x1: int, y1: int, x2: int, y2: int) -> None:
            lines.append((x1, y1, x2, y2, self.pen))

    monkeypatch.setattr(wx, "AutoBufferedPaintDC", lambda _window: FakeDC())
    monkeypatch.setattr(wx, "Brush", lambda color: ("brush", color))
    monkeypatch.setattr(wx, "Pen", lambda color, width: ("pen", color, width))
    monkeypatch.setattr(wx, "Colour", lambda color: color)
    monkeypatch.setattr(wx.SystemSettings, "GetColour", lambda _id: highlight)
    slider = SimpleNamespace(
        GetBackgroundColour=lambda: SimpleNamespace(
            Red=lambda: 0,
            Green=lambda: 0,
            Blue=lambda: 0,
        ),
        GetClientSize=lambda: (100, 74),
        _track_is_highlighted=False,
        _playback_connector_hovered=True,
        _time_slider_state_set=True,
        _playback_handles=(20.0, 80.0),
        _x_for=lambda value: int(value),
        _playable_segment_x=lambda: None,
        _unloaded_segment_x=lambda: None,
        _now=101.0,
        _slider_bounds=(0.0, 100.0),
    )

    PlaybackTimeSlider._paint_track(slider, None)

    assert lines == [(20, 54, 80, 54, ("pen", "#197765", 2))]


@pytest.mark.parametrize(
    ("control_down", "command_down", "expected_seeks"),
    [
        (False, False, []),
        (True, False, [6250, 7000]),
        (False, True, [6250, 7000]),
    ],
)
def test_dragging_playback_connector_moves_range_without_resizing(
    control_down: bool,
    command_down: bool,
    expected_seeks: list[int],
) -> None:
    class SliderHarness(SimpleNamespace):
        @property
        def _playback_connector_hovered(self) -> bool:
            return PlaybackTimeSlider._playback_connector_hovered.__get__(self)

    ranges: list[tuple[float, float]] = []
    seeks: list[int] = []
    drag_states: list[bool] = []
    slider = SliderHarness(
        IsEnabled=lambda: True,
        SetFocus=lambda: None,
        GetClientSize=lambda: SimpleNamespace(width=100, height=74),
        _drag_source=None,
        _pointer_position=None,
        _range_drag_origin=None,
        _now=50.0,
        _playback_handles=(20.0, 80.0),
        _coverage=(0.0, 100.0),
        _slider_bounds=(0.0, 100.0),
        _x_for=lambda timestamp: 10 + round(timestamp * 0.8),
        _seek_grip=SimpleNamespace(Refresh=lambda: None),
        _on_playback=lambda start, end: ranges.append((start, end)),
        _on_begin_edit=lambda: None,
        _on_range_dragging=drag_states.append,
        _set_pointer_position=lambda position: (
            PlaybackTimeSlider._set_pointer_position(slider, position)
        ),
        _pointer_between_playback_handles=lambda position: (
            PlaybackTimeSlider._pointer_between_playback_handles(slider, position)
        ),
        _set_track_hover=lambda _hovered: None,
        _begin_pointer_drag=lambda source: PlaybackTimeSlider._begin_pointer_drag(
            slider, source
        ),
        _end_pointer_drag=lambda source: PlaybackTimeSlider._end_pointer_drag(
            slider, source
        ),
        _timestamp_at=lambda x: PlaybackTimeSlider._timestamp_at(slider, x),
        _move_playback_range=lambda x, *, move_seek: (
            PlaybackTimeSlider._move_playback_range(slider, x, move_seek=move_seek)
        ),
        _range_drag_modifier_changed=lambda move_seek, seek_start_s=None: (
            PlaybackTimeSlider._range_drag_modifier_changed(
                slider, move_seek, seek_start_s
            )
        ),
        _minimum=0,
        _maximum=10_000,
        _value_at_x=lambda x: PlaybackTimeSlider._value_at_x(slider, x),
        _set_value_from_user=seeks.append,
        is_pointer_over_timeline_track=lambda _position: False,
        HasCapture=lambda: False,
        CaptureMouse=lambda: None,
        _on_playback_handles_changed=lambda: None,
        Refresh=lambda: None,
    )
    def motion_event(x: int) -> SimpleNamespace:
        return SimpleNamespace(
            GetPosition=lambda: SimpleNamespace(x=x, y=54),
            GetX=lambda: x,
            Dragging=lambda: True,
            LeftIsDown=lambda: True,
            ControlDown=lambda: control_down,
            CmdDown=lambda: command_down,
            Skip=lambda: None,
        )

    event = SimpleNamespace(
        GetPosition=lambda: SimpleNamespace(x=50, y=54),
        GetX=lambda: 50,
        ControlDown=lambda: control_down,
        CmdDown=lambda: command_down,
        Skip=lambda: None,
    )
    PlaybackTimeSlider._left_down(slider, event)
    PlaybackTimeSlider._motion(slider, motion_event(60))
    PlaybackTimeSlider._motion(slider, motion_event(95))
    PlaybackTimeSlider._left_up(slider, event)

    assert ranges == [(32.5, 92.5), (40.0, 100.0)]
    assert seeks == expected_seeks
    assert all(end - start == 60.0 for start, end in ranges)
    assert drag_states == [True, False]
    assert slider._range_drag_origin is None


def test_toggling_modifier_during_range_drag_does_not_jump_seek() -> None:
    seeks = []
    ranges = []

    def set_value(value: int) -> None:
        if value == slider._value:
            return
        slider._value = value
        slider._now = value / 100.0
        seeks.append(value)

    slider = SimpleNamespace(
        _range_drag_origin=(50.0, 20.0, 80.0),
        _range_seek_origin=None,
        _now=50.0,
        _coverage=(0.0, 100.0),
        _slider_bounds=(0.0, 100.0),
        _minimum=0,
        _maximum=10_000,
        _value=5000,
        _playback=(20.0, 80.0),
        _playback_handles=(20.0, 80.0),
        _seek_grip=SimpleNamespace(Refresh=lambda: None),
        _range_drag_modifier_changed=lambda move_seek, seek_start_s=None: (
            PlaybackTimeSlider._range_drag_modifier_changed(
                slider, move_seek, seek_start_s
            )
        ),
        _timestamp_at=lambda x: PlaybackTimeSlider._timestamp_at(slider, x),
        _x_for=lambda time_s: PlaybackTimeSlider._x_for(slider, time_s),
        _value_at_x=lambda x: PlaybackTimeSlider._value_at_x(slider, x),
        GetClientSize=lambda: SimpleNamespace(width=100),
        _on_playback=lambda start, end: ranges.append((start, end)),
        _set_value_from_user=set_value,
    )

    PlaybackTimeSlider._move_playback_range(slider, 60, move_seek=False)
    PlaybackTimeSlider._move_playback_range(slider, 60, move_seek=True)
    PlaybackTimeSlider._move_playback_range(slider, 65, move_seek=True)
    PlaybackTimeSlider._move_playback_range(slider, 65, move_seek=False)
    PlaybackTimeSlider._move_playback_range(slider, 65, move_seek=True)
    PlaybackTimeSlider._move_playback_range(slider, 70, move_seek=True)

    assert seeks == [5625, 5750]
    assert ranges == [
        (32.5, 92.5),
        (32.5, 92.5),
        (38.75, 98.75),
        (38.75, 98.75),
        (38.75, 98.75),
        (40.0, 100.0),
    ]


def test_modifier_key_events_immediately_update_seek_grip_highlight() -> None:
    refreshes = []
    slider = SimpleNamespace(
        _range_drag_origin=(50.0, 32.5, 92.5),
        _range_seek_origin=None,
        _playback_handles=(32.5, 92.5),
        _now=50.0,
        _seek_grip=SimpleNamespace(Refresh=lambda: refreshes.append(True)),
        _range_drag_modifier_changed=lambda move_seek, seek_start_s=None: (
            PlaybackTimeSlider._range_drag_modifier_changed(
                slider, move_seek, seek_start_s
            )
        ),
    )

    def key_event(*, control_down: bool, command_down: bool = False):
        return SimpleNamespace(
            GetKeyCode=lambda: wx.WXK_CONTROL,
            ControlDown=lambda: control_down,
            CmdDown=lambda: command_down,
            Skip=lambda: None,
        )

    PlaybackTimeSlider._key_down(slider, key_event(control_down=True))
    assert slider._range_seek_origin is not None
    assert slider._range_seek_origin == (32.5, 50.0)
    assert refreshes == [True]

    PlaybackTimeSlider._key_up(slider, key_event(control_down=False))
    assert slider._range_seek_origin is None
    assert slider._range_seek_origin is None
    assert refreshes == [True, True]

    PlaybackTimeSlider._key_down(slider, key_event(control_down=False, command_down=True))
    assert slider._range_seek_origin is not None
    assert slider._range_seek_origin == (32.5, 50.0)
    PlaybackTimeSlider._key_up(
        slider, key_event(control_down=False, command_down=False)
    )
    assert slider._range_seek_origin is None
    assert slider._range_seek_origin is None
    assert refreshes == [True, True, True, True]


def test_playable_track_segment_uses_metadata_bounds_as_slider_scale() -> None:
    slider = SimpleNamespace(
        _coverage=(0.0, 100.0),
        _slider_bounds=(0.0, 200.0),
        _playback=(25.0, 75.0),
        GetClientSize=lambda: SimpleNamespace(width=100),
    )
    slider._x_for = lambda value: PlaybackTimeSlider._x_for(slider, value)

    assert PlaybackTimeSlider._playable_segment_x(slider) == (20, 40)


@pytest.mark.parametrize(
    ("playback", "visible", "expected"),
    [
        ((25.0, 75.0), (0.0, 100.0), (30, 70)),
        ((25.0, 75.0), (50.0, 100.0), (10, 50)),
        ((25.0, 75.0), (100.0, 200.0), None),
        ((125.0, 175.0), (0.0, 200.0), (60, 80)),
    ],
)
def test_playable_track_segment_is_clipped_to_visible_range(
    playback: tuple[float, float],
    visible: tuple[float, float],
    expected: Optional[tuple[int, int]],
) -> None:
    slider = SimpleNamespace(
        _coverage=visible,
        _slider_bounds=visible,
        _playback=playback,
        GetClientSize=lambda: SimpleNamespace(width=100),
    )
    slider._x_for = lambda value: PlaybackTimeSlider._x_for(slider, value)

    assert PlaybackTimeSlider._playable_segment_x(slider) == expected


def test_unloaded_track_segment_uses_metadata_bounds_as_slider_scale() -> None:
    slider = SimpleNamespace(
        _slider_bounds=(0.0, 200.0),
        _unloaded_from_s=100.0,
        GetClientSize=lambda: SimpleNamespace(width=100),
    )
    slider._x_for = lambda value: PlaybackTimeSlider._x_for(slider, value)

    assert PlaybackTimeSlider._unloaded_segment_x(slider) == (50, 90)


def test_seek_grip_reports_drag_end_and_capture_loss() -> None:
    dragging: list[bool] = []
    refreshes: list[bool] = []
    seeks: list[object] = []
    tooltip_positions: list[object] = []
    slider = SimpleNamespace(
        IsEnabled=lambda: True,
        SetFocus=lambda: None,
        _drag_source=None,
        Refresh=lambda: None,
        _on_range_dragging=dragging.append,
        _begin_pointer_drag=lambda source: PlaybackTimeSlider._begin_pointer_drag(
            slider, source
        ),
        _end_pointer_drag=lambda source, release_capture=True: (
            PlaybackTimeSlider._end_pointer_drag(
                slider, source, release_capture=release_capture
            )
        ),
        _seek_from_grip=lambda _grip, point: seeks.append(point),
        _position_seek_tooltip=tooltip_positions.append,
    )
    grip = SimpleNamespace(
        slider=slider,
        Refresh=lambda: refreshes.append(True),
        HasCapture=lambda: False,
        CaptureMouse=lambda: None,
    )
    slider._seek_grip = grip
    event = SimpleNamespace(GetPosition=lambda: "click position", Skip=lambda: None)

    _SeekGrip._down(grip, event)
    assert PlaybackTimeSlider.is_dragging.__get__(slider)
    assert tooltip_positions == ["click position"]
    _SeekGrip._up(grip, event)
    assert not PlaybackTimeSlider.is_dragging.__get__(slider)
    assert seeks == []
    _SeekGrip._down(grip, event)
    assert tooltip_positions == ["click position", "click position"]
    motion = SimpleNamespace(
        Dragging=lambda: True,
        LeftIsDown=lambda: True,
        GetPosition=lambda: "dragged position",
        Skip=lambda: None,
    )
    _SeekGrip._motion(grip, motion)
    assert seeks == ["dragged position"]
    assert tooltip_positions == [
        "click position",
        "click position",
        "dragged position",
    ]
    _SeekGrip._capture_lost(grip, event)

    assert dragging == [True, False, True, False]
    assert not PlaybackTimeSlider.is_dragging.__get__(slider)
    assert len(refreshes) == 4


def test_range_grips_wait_until_span_and_ranges_are_ready() -> None:
    hidden = []
    grip = SimpleNamespace(Hide=lambda: hidden.append("range"))
    seek_grip = SimpleNamespace(Hide=lambda: hidden.append("seek"))
    slider = SimpleNamespace(
        _coverage=(0.0, 100.0),
        _playback=(20.0, 80.0),
        _slider_bounds=(0.0, 100.0),
        _playback_handles=(20.0, 80.0),
        _unloaded_from_s=None,
        _plot_rule=object(),
        _now=50.0,
        _ranges_ready=False,
        _grips={"playback_start": grip},
        _seek_grip=seek_grip,
        Refresh=lambda: None,
        _position_grips=lambda: None,
    )

    plot_rule = SimpleNamespace()
    PlaybackTimeSlider.set_ranges(
        slider,
        (0.0, 100.0),
        (20.0, 80.0),
        plot_rule,
        50.0,
        unloaded_from_s=25.0,
    )
    assert not slider._ranges_ready

    PlaybackTimeSlider.set_ranges(
        slider,
        (0.0, 100.0),
        (20.0, 80.0),
        plot_rule,
        50.0,
    )
    assert slider._ranges_ready


def test_unready_range_grips_hide_without_positioning(monkeypatch) -> None:
    hidden = []
    grip = SimpleNamespace(Hide=lambda: hidden.append("range"))
    seek_grip = SimpleNamespace(Hide=lambda: hidden.append("seek"))
    slider = SimpleNamespace(
        _ranges_ready=False,
        _grips={"playback_start": grip},
        _seek_grip=seek_grip,
    )

    PlaybackTimeSlider._position_grips(slider)

    assert hidden == ["range", "seek"]


def test_seek_grip_tooltip_is_a_plain_timestamp(monkeypatch) -> None:
    from ephem_toolkit.play_oem.widgets import playback_time_slider as playback_time_slider_module

    messages = []
    monkeypatch.setattr(
        playback_time_slider_module,
        "format_tt",
        lambda timestamp, _time_zone, **_kwargs: f"timestamp {timestamp:g}",
    )
    monkeypatch.setattr(
        playback_time_slider_module,
        "set_tooltip",
        lambda widget, message: messages.append((widget, message)),
    )

    class FakeGrip:
        def Show(self) -> None:
            pass

        def Hide(self) -> None:
            pass

        def SetSize(self, _size) -> None:
            pass

        def SetPosition(self, _position) -> None:
            pass

        def GetSize(self):
            return SimpleNamespace(width=18)

        def GetName(self) -> str:
            return "Current playback time marker"

    grip = FakeGrip()
    seek_grip = FakeGrip()
    slider = SimpleNamespace(
        _grips={"playback_start": grip},
        _ranges_ready=True,
        _time_slider_state_set=True,
        _plot_rule=object(),
        _playback_handles=(10.0, 90.0),
        _slider_bounds=(0.0, 100.0),
        _now=50.0,
        _display_time_zone="UTC",
        _time_for=lambda _key: 10.0,
        _x_for=lambda timestamp: int(timestamp),
        GetClientSize=lambda: SimpleNamespace(width=100, height=74),
        GetPosition=lambda: SimpleNamespace(x=0, y=0),
        _seek_grip=seek_grip,
    )

    PlaybackTimeSlider._position_grips(slider)

    assert messages[-1] == (seek_grip, "timestamp 50")


def test_seek_grip_looks_filled_and_larger_while_dragging(monkeypatch) -> None:
    highlight, background = object(), object()
    drawing: dict[str, object] = {}

    class FakeDC:
        def SetBackground(self, brush: object) -> None:
            drawing["background"] = brush

        def Clear(self) -> None:
            pass

        def SetPen(self, pen: object) -> None:
            drawing["pen"] = pen

        def SetBrush(self, brush: object) -> None:
            drawing["brush"] = brush

        def DrawCircle(self, x: int, y: int, radius: int) -> None:
            drawing["circle"] = (x, y, radius)

    monkeypatch.setattr(wx, "AutoBufferedPaintDC", lambda _window: FakeDC())
    monkeypatch.setattr(wx, "Brush", lambda color: ("brush", color))
    monkeypatch.setattr(wx, "Pen", lambda color, width: ("pen", color, width))
    monkeypatch.setattr(wx.SystemSettings, "GetColour", lambda _id: highlight)
    grip = SimpleNamespace(
        slider=SimpleNamespace(
            GetBackgroundColour=lambda: background,
            _drag_source=None,
        ),
        GetClientSize=lambda: (16, 16),
        _dragging=False,
    )

    _SeekGrip._paint(grip, None)
    assert drawing["pen"] == ("pen", highlight, 2)
    assert drawing["brush"] == ("brush", background)
    assert drawing["circle"] == (8, 8, 6)

    grip.slider._drag_source = grip
    _SeekGrip._paint(grip, None)
    assert drawing["pen"] == ("pen", highlight, 3)
    assert drawing["brush"] == ("brush", highlight)
    assert drawing["circle"] == (8, 8, 7)

    grip.slider._drag_source = grip.slider
    _SeekGrip._paint(grip, None)
    assert drawing["pen"] == ("pen", highlight, 3)
    assert drawing["brush"] == ("brush", highlight)
    assert drawing["circle"] == (8, 8, 7)

    grip.slider._range_drag_origin = (50.0, 20.0, 80.0)
    grip.slider._range_seek_origin = None
    _SeekGrip._paint(grip, None)
    assert drawing["pen"] == ("pen", highlight, 2)
    assert drawing["brush"] == ("brush", background)

    grip.slider._range_seek_origin = (20.0, 50.0)
    _SeekGrip._paint(grip, None)
    assert drawing["pen"] == ("pen", highlight, 3)
    assert drawing["brush"] == ("brush", highlight)


@pytest.mark.parametrize(
    ("kind", "color"),
    [("playback", "#197765"), ("plot", "#2864c8")],
)
def test_endpoint_grip_appearance_changes_while_dragging(
    monkeypatch, kind: str, color: str
) -> None:
    highlight, background = object(), object()
    drawing: dict[str, object] = {}

    class FakeDC:
        def SetBackground(self, brush: object) -> None:
            pass

        def Clear(self) -> None:
            pass

        def SetPen(self, pen: object) -> None:
            drawing["pen"] = pen

        def SetBrush(self, brush: object) -> None:
            drawing["brush"] = brush

        def DrawPolygon(self, _vertices: object) -> None:
            pass

    monkeypatch.setattr(wx, "AutoBufferedPaintDC", lambda _window: FakeDC())
    monkeypatch.setattr(wx, "Brush", lambda value: ("brush", value))
    monkeypatch.setattr(wx, "Pen", lambda value, width: ("pen", value, width))
    monkeypatch.setattr(wx, "Point", lambda x, y: (x, y))
    monkeypatch.setattr(wx.SystemSettings, "GetColour", lambda _id: highlight)
    grip = SimpleNamespace(
        kind=kind,
        color=color,
        slider=SimpleNamespace(
            _plot_mode=lambda _grip: "fixed",
            _drag_source=None,
        ),
        GetParent=lambda: SimpleNamespace(GetBackgroundColour=lambda: background),
        GetClientSize=lambda: (18, 18),
        HasFocus=lambda: False,
        _dragging=False,
    )

    _RangeGrip._paint(grip, None)
    idle_pen, idle_brush = drawing["pen"], drawing["brush"]
    grip.slider._drag_source = grip
    _RangeGrip._paint(grip, None)

    assert drawing["pen"] == ("pen", highlight, 3)
    assert drawing["pen"] != idle_pen
    assert drawing["brush"] == ("brush", highlight)
    assert drawing["brush"] != idle_brush


def test_track_scrubbing_reports_drag_end_and_capture_loss() -> None:
    dragging: list[bool] = []
    refreshes: list[bool] = []
    slider = SimpleNamespace(
        IsEnabled=lambda: True,
        SetFocus=lambda: None,
        _drag_source=None,
        Refresh=lambda: None,
        _begin_pointer_drag=lambda source: PlaybackTimeSlider._begin_pointer_drag(
            slider, source
        ),
        _end_pointer_drag=lambda source, release_capture=True: (
            PlaybackTimeSlider._end_pointer_drag(
                slider, source, release_capture=release_capture
            )
        ),
        _on_range_dragging=dragging.append,
        _pointer_between_playback_handles=lambda _position: False,
        _value_at_x=lambda x: x,
        _set_value_from_user=lambda _value: None,
        _set_track_hover=lambda _hovered: None,
        _seek_grip=SimpleNamespace(Refresh=lambda: refreshes.append(True)),
        GetClientSize=lambda: SimpleNamespace(height=74),
        is_pointer_over_timeline_track=lambda position: (
            PlaybackTimeSlider.is_pointer_over_timeline_track(slider, position)
        ),
        HasCapture=lambda: False,
        CaptureMouse=lambda: None,
    )
    event = SimpleNamespace(
        GetX=lambda: 50,
        GetPosition=lambda: SimpleNamespace(y=35),
        Skip=lambda: None,
    )

    PlaybackTimeSlider._left_down(slider, event)
    assert PlaybackTimeSlider.is_dragging.__get__(slider)
    PlaybackTimeSlider._left_up(slider, event)
    assert not PlaybackTimeSlider.is_dragging.__get__(slider)
    PlaybackTimeSlider._left_down(slider, event)
    PlaybackTimeSlider._capture_lost(slider, event)

    assert dragging == [True, False, True, False]
    assert not PlaybackTimeSlider.is_dragging.__get__(slider)
    assert len(refreshes) == 4


def test_track_click_outside_track_band_does_not_start_seeking() -> None:
    calls = []
    slider = SimpleNamespace(
        IsEnabled=lambda: True,
        GetClientSize=lambda: SimpleNamespace(height=74),
        _pointer_between_playback_handles=lambda _position: False,
        is_pointer_over_timeline_track=lambda position: (
            PlaybackTimeSlider.is_pointer_over_timeline_track(slider, position)
        ),
        SetFocus=lambda: calls.append("focus"),
        _begin_pointer_drag=lambda _source: calls.append("drag"),
        _set_value_from_user=lambda _value: calls.append("seek"),
    )
    event = SimpleNamespace(
        GetPosition=lambda: SimpleNamespace(y=28),
        Skip=lambda: calls.append("skip"),
    )

    PlaybackTimeSlider._left_down(slider, event)

    assert calls == ["skip"]


def test_slider_seek_position_uses_metadata_domain() -> None:
    slider = SimpleNamespace(
        _slider_bounds=(0.0, 200.0),
        GetClientSize=lambda: SimpleNamespace(width=100),
    )

    assert PlaybackTimeSlider._timestamp_at(slider, 50) == 100.0


@pytest.mark.parametrize(
    ("x", "expected"),
    [(10, 0), (50, 5000), (90, 10_000), (0, 0), (100, 10_000)],
)
def test_custom_slider_maps_pointer_to_seek_value(x: int, expected: int) -> None:
    slider = SimpleNamespace(
        _minimum=0,
        _maximum=10_000,
        GetClientSize=lambda: SimpleNamespace(width=100),
    )

    assert PlaybackTimeSlider._value_at_x(slider, x) == expected
