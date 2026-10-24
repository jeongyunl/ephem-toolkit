"""Tests for playback timeline handle geometry."""

from ephem_toolkit.play_oem.workspace.time_range_slider import (
    _plot_grip_y,
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


def test_plot_grip_is_as_close_to_the_track_as_the_playback_grip() -> None:
    playback_grip_y = 43
    grip_height = 18

    for slider_height in (58, 74):
        plot_grip_y = _plot_grip_y(slider_height, playback_grip_y, grip_height)
        slider_track_y = slider_height / 2
        playback_center_y = playback_grip_y + grip_height / 2
        plot_center_y = plot_grip_y + grip_height / 2

        assert slider_track_y - plot_center_y == playback_center_y - slider_track_y
