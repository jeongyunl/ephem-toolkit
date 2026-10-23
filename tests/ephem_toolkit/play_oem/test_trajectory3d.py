"""Tests for the Matplotlib 3D trajectory playback view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.trajectory3d import Trajectory3DView
from ephem_toolkit.play_oem.views.trajectory3d.selection import select_segmented_positions


def make_orbit():
    times_s = [100.0, 160.0, 220.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
    ]
    return (
        compute_orbit_series(times_s, states_m, TimeUnit.MINUTES),
        OemCursor(times_s, states_m),
    )


def test_trajectory_view_builds_contextual_3d_orbit_and_updates_marker() -> None:
    series, cursor = make_orbit()
    view = Trajectory3DView(cursor, "ISS", "EME2000 / Earth")

    figure = view.build(series, TimeUnit.MINUTES)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()

    assert len(figure.axes) == 1
    axes = figure.axes[0]
    assert axes.name == "3d"
    assert axes.get_xlabel() == "X (km)"
    assert axes.get_ylabel() == "Y (km)"
    assert axes.get_zlabel() == "Z (km)"
    assert figure._suptitle is not None
    assert figure._suptitle.get_text() == "ISS | EME2000 / Earth"
    np.testing.assert_array_equal(
        axes.lines[0].get_data_3d()[0], series.position_km[:, 0]
    )

    state = cursor.lookup(160.0)
    view.update_cursor(state)
    assert view._cursor_artist is not None
    assert view._cursor_artist.get_visible()
    assert view._cursor_position_km == tuple(state.r_km)

    view.update_cursor(cursor.lookup(99.0))
    assert not view._cursor_artist.get_visible()
    assert view._cursor_position_km is None
    view.close()
    assert not figure.axes
    with pytest.raises(RuntimeError, match="not been built"):
        view.update(160.0)


def test_trajectory_range_filters_before_decimation_and_gates_markers() -> None:
    series, cursor = make_orbit()
    view = Trajectory3DView(cursor, "ISS", "EME2000 / Earth")
    figure = view.build(series, TimeUnit.MINUTES)
    try:
        axes = figure.axes[0]
        original_limits = (axes.get_xlim(), axes.get_ylim(), axes.get_zlim())
        view.set_time_range(ResolvedTimeRange(160.0, 160.0), (100.0, 220.0))
        view.update(160.0)
        np.testing.assert_array_equal(axes.lines[0].get_data_3d()[0], [0.0])
        np.testing.assert_array_equal(axes.lines[0].get_data_3d()[1], [7000.0])
        assert not view._start_artist.get_visible()
        assert not view._end_artist.get_visible()
        assert view._cursor_artist.get_visible()
        assert (axes.get_xlim(), axes.get_ylim(), axes.get_zlim()) == original_limits

        view.set_time_range(None, (100.0, 220.0))
        assert len(axes.lines[0].get_data_3d()[0]) == 0
        assert not view._cursor_artist.get_visible()
        assert not view._start_artist.get_visible()
        assert not view._end_artist.get_visible()
    finally:
        view.close()


def test_shared_spatial_selector_preserves_segment_ids_and_inclusive_edges() -> None:
    positions = np.arange(12, dtype=float).reshape(4, 3)
    times = np.array([0.0, 1.0, 2.0, 3.0])
    segment_ids = np.array([0, 0, 1, 1])

    selected, selected_segments = select_segmented_positions(
        positions, times, segment_ids, (1.0, 2.0)
    )

    np.testing.assert_array_equal(selected, positions[[1, 2]])
    np.testing.assert_array_equal(selected_segments, [0, 1])
    empty_positions, empty_segments = select_segmented_positions(
        positions, times, segment_ids, None
    )
    assert empty_positions.shape == (0, 3)
    assert empty_segments.shape == (0,)
