"""Tests for playback timeline handle geometry."""

from types import SimpleNamespace
from typing import Optional

import pytest

from ephem_toolkit.play_oem.time_range import EndpointMode
from ephem_toolkit.play_oem.workspace.time_slider import (
    _SeekGrip,
    TimeSlider,
    _plot_grip_y,
    _plot_handle_vertices,
    _plot_tooltip_text,
    _timestamp_is_visible,
    _triangle_vertices,
)


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
        ("follow", "Follow playback"),
        ("offset", "Playback offset"),
        ("fixed", "Fixed time"),
    ],
)
def test_plot_handle_tooltip_is_two_lines(mode: EndpointMode, mode_label: str) -> None:
    tooltip = _plot_tooltip_text("Plot start", "2026-05-21T04:36:45", mode)

    assert tooltip.splitlines() == [
        "Plot start: 2026-05-21T04:36:45",
        f"{mode_label} | Right-click for mode",
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

    TimeSlider._drag(slider, grip, None)
    TimeSlider._nudge(slider, grip, 1)


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
        TimeSlider.is_pointer_over_timeline_track(
            slider, SimpleNamespace(y=pointer_y)
        )
        is expected
    )


def test_playable_track_segment_uses_metadata_bounds_as_slider_scale() -> None:
    slider = SimpleNamespace(
        _coverage=(0.0, 100.0),
        _slider_bounds=(0.0, 200.0),
        _playback=(25.0, 75.0),
        GetClientSize=lambda: SimpleNamespace(width=100),
    )
    slider._x_for = lambda value: TimeSlider._x_for(slider, value)

    assert TimeSlider._playable_segment_x(slider) == (20, 40)


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
    slider._x_for = lambda value: TimeSlider._x_for(slider, value)

    assert TimeSlider._playable_segment_x(slider) == expected


def test_unloaded_track_segment_uses_metadata_bounds_as_slider_scale() -> None:
    slider = SimpleNamespace(
        _slider_bounds=(0.0, 200.0),
        _unloaded_from_s=100.0,
        GetClientSize=lambda: SimpleNamespace(width=100),
    )
    slider._x_for = lambda value: TimeSlider._x_for(slider, value)

    assert TimeSlider._unloaded_segment_x(slider) == (50, 90)


def test_seek_grip_reports_drag_end_and_capture_loss() -> None:
    dragging: list[bool] = []
    slider = SimpleNamespace(
        IsEnabled=lambda: True,
        SetFocus=lambda: None,
        _on_range_dragging=dragging.append,
        _seek_from_grip=lambda _grip, _point: None,
    )
    grip = SimpleNamespace(
        slider=slider,
        _dragging=False,
        HasCapture=lambda: False,
        CaptureMouse=lambda: None,
    )
    event = SimpleNamespace(GetPosition=lambda: None, Skip=lambda: None)

    _SeekGrip._down(grip, event)
    _SeekGrip._up(grip, event)
    _SeekGrip._down(grip, event)
    _SeekGrip._capture_lost(grip, event)

    assert dragging == [True, False, True, False]


def test_track_scrubbing_reports_drag_end_and_capture_loss() -> None:
    dragging: list[bool] = []
    slider = SimpleNamespace(
        IsEnabled=lambda: True,
        SetFocus=lambda: None,
        _on_range_dragging=dragging.append,
        _value_at_x=lambda x: x,
        _set_value_from_user=lambda _value: None,
        _dragging=False,
        HasCapture=lambda: False,
        CaptureMouse=lambda: None,
    )
    event = SimpleNamespace(GetX=lambda: 50, Skip=lambda: None)

    TimeSlider._left_down(slider, event)
    TimeSlider._left_up(slider, event)
    TimeSlider._left_down(slider, event)
    TimeSlider._capture_lost(slider, event)

    assert dragging == [True, False, True, False]


def test_slider_seek_position_uses_metadata_domain() -> None:
    slider = SimpleNamespace(
        _slider_bounds=(0.0, 200.0),
        GetClientSize=lambda: SimpleNamespace(width=100),
    )

    assert TimeSlider._timestamp_at(slider, 50) == 100.0


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

    assert TimeSlider._value_at_x(slider, x) == expected
