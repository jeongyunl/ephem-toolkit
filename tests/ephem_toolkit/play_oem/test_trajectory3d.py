"""Tests for the Matplotlib 3D trajectory playback view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.data_view_base import StoreViewContext
from ephem_toolkit.play_oem.views.trajectory3d import Trajectory3DView
from ephem_toolkit.play_oem.views.trajectory3d.selection import select_segmented_positions
from tests.ephem_toolkit.play_oem.cursor_helpers import (
    append_store_samples,
    make_store_cursor,
)


def make_orbit():
    times_s = [100.0, 160.0, 220.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
    ]
    store, cursor = make_store_cursor(times_s, states_m)
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(100.0, 220.0),
        coverage=(100.0, 220.0),
    )
    return compute_orbit_series(times_s, states_m, TimeUnit.MINUTES), store, cursor, context


def test_trajectory_view_builds_contextual_3d_orbit_and_updates_marker() -> None:
    series, _store, cursor, context = make_orbit()
    view = Trajectory3DView(cursor, "ISS", "EME2000 / Earth")

    figure = view.build_from_store(context)
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
    assert view._orbit_artists
    np.testing.assert_array_equal(
        view._store_positions_m[:, 0] / 1000.0,
        series.position_km[:, 0],
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
    series, _store, cursor, context = make_orbit()
    view = Trajectory3DView(cursor, "ISS", "EME2000 / Earth")
    figure = view.build_from_store(context)
    try:
        axes = figure.axes[0]
        original_limits = (axes.get_xlim(), axes.get_ylim(), axes.get_zlim())
        view.set_time_range(ResolvedTimeRange(160.0, 160.0), (100.0, 220.0))
        view.update(160.0)
        assert len(view._orbit_artists) == 1
        np.testing.assert_array_equal(
            view._orbit_artists[0][1].get_data_3d()[0],
            [0.0],
        )
        np.testing.assert_array_equal(
            view._orbit_artists[0][1].get_data_3d()[1],
            [7_000_000.0],
        )
        assert not view._start_artist.get_visible()
        assert not view._end_artist.get_visible()
        assert view._cursor_artist.get_visible()
        assert (axes.get_xlim(), axes.get_ylim(), axes.get_zlim()) == original_limits

        view.set_time_range(None, (100.0, 220.0))
        assert not view._orbit_artists
        assert not view._cursor_artist.get_visible()
        assert not view._start_artist.get_visible()
        assert not view._end_artist.get_visible()
    finally:
        view.close()


def test_trajectory_data_update_preserves_figure_and_orbit_artist() -> None:
    orbit, store, cursor, context = make_orbit()
    view = Trajectory3DView(cursor, "ISS", "EME2000 / Earth")
    figure = view.build_from_store(context)
    axes = figure.axes[0]
    orbit_artist_count = len(view._orbit_artists)
    appended_state = np.array([0.0, -7_000_000.0, 0.0, 7_500.0, 0.0, 0.0])
    append_store_samples(store, cursor, [280.0], [appended_state], [0])
    updated = compute_orbit_series(
        [100.0, 160.0, 220.0, 280.0],
        [
            np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
            np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
            np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
            appended_state,
        ],
        TimeUnit.MINUTES,
    )

    try:
        view.update_from_store(context.refresh())
        view.set_time_range(ResolvedTimeRange(100.0, 280.0), (100.0, 280.0))

        assert view._figure is figure
        assert len(view._orbit_artists) >= orbit_artist_count
        np.testing.assert_array_equal(
            view._store_positions_m[:, 0] / 1000.0,
            updated.position_km[:, 0],
        )
        np.testing.assert_array_equal(view._end_artist._offsets3d[0], [0.0])
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
