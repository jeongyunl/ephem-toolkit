"""Tests for playback timeline handle geometry."""

from types import SimpleNamespace

import pytest

from ephem_toolkit.play_oem.time_range import EndpointMode
from ephem_toolkit.play_oem.workspace.time_range_slider import (
    TimeRangeSlider,
    _plot_grip_y,
    _plot_handle_vertices,
    _plot_tooltip_text,
    _triangle_vertices,
)


def test_plot_triangle_points_down_and_matches_playback_size() -> None:
    playback = _triangle_vertices("playback", 20, 20)
    plot = _triangle_vertices("plot", 20, 20)

    def dimensions(vertices: tuple[tuple[int, int], ...]) -> tuple[int, int]:
        xs, ys = zip(*vertices)
        return max(xs) - min(xs), max(ys) - min(ys)

    assert dimensions(plot) == dimensions(playback) == (12, 11)
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
    assert max(y for _x, y in offset) - min(y for _x, y in offset) == 12
    assert max(x for x, _y in fixed) - min(x for x, _y in fixed) == 10
    assert max(y for _x, y in fixed) - min(y for _x, y in fixed) == 10


@pytest.mark.parametrize(
    ("mode", "mode_label"),
    [
        ("follow", "Follow playback"),
        ("offset", "Playback offset"),
        ("fixed", "Fixed time"),
    ],
)
def test_plot_handle_tooltip_is_two_lines(
    mode: EndpointMode, mode_label: str
) -> None:
    tooltip = _plot_tooltip_text("Plot start", "2026-05-21T04:36:45", mode)

    assert tooltip.splitlines() == [
        "Plot start: 2026-05-21T04:36:45 UTC",
        f"{mode_label} | Right-click for mode",
    ]


def test_plot_grip_is_as_close_to_the_track_as_the_playback_grip() -> None:
    playback_grip_y = 43
    grip_height = 18

    for slider_height in (58, 74):
        plot_grip_y = _plot_grip_y(slider_height, playback_grip_y, grip_height)
        slider_track_y = slider_height / 2
        playback_center_y = playback_grip_y + grip_height / 2
        plot_center_y = plot_grip_y + grip_height / 2

        assert slider_track_y - plot_center_y == playback_center_y - slider_track_y


def test_follow_plot_handle_ignores_dragging_and_keyboard_nudging() -> None:
    grip = object()
    slider = SimpleNamespace(
        _grips={"plot_start": grip},
        _plot_mode=lambda _grip: "follow",
        _on_begin_edit=lambda: pytest.fail("Follow handle must not begin an edit"),
        _coverage=(0.0, 100.0),
    )

    TimeRangeSlider._drag(slider, grip, None)
    TimeRangeSlider._nudge(slider, grip, 1)


@pytest.mark.parametrize(
    ("pointer_y", "expected"),
    [(37, True), (31, True), (30, False), (43, True), (44, False)],
)
def test_timeline_tooltip_hotspot_is_limited_to_track_band(
    pointer_y: int, expected: bool
) -> None:
    slider = SimpleNamespace(
        GetClientSize=lambda: SimpleNamespace(height=74),
    )

    assert (
        TimeRangeSlider.is_pointer_over_timeline_track(
            slider, SimpleNamespace(y=pointer_y)
        )
        is expected
    )
