"""Tests for the static speed and altitude plot view."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import PathPatch

from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import StoreViewContext
from ephem_toolkit.play_oem.views.speed_altitude import SpeedAltitudeView


def test_speed_altitude_view_builds_labeled_static_series_and_cursor() -> None:
    series = compute_orbit_series(
        [100.0, 160.0, 220.0],
        [
            np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
            np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
            np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
        ],
        TimeUnit.MINUTES,
    )
    view = SpeedAltitudeView(start_time_s=100.0)

    figure = view.build(series, TimeUnit.MINUTES)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()

    assert len(figure.axes) == 2
    assert figure.axes[0].get_ylabel() == "Speed (km/s)"
    assert figure.axes[1].get_ylabel() == "Altitude (km)"
    assert figure.axes[1].get_xlabel() == "Time from Start (minutes)"
    np.testing.assert_array_equal(figure.axes[0].lines[1].get_xdata(), [0.0, 0.0])

    original_speed_x = figure.axes[0].lines[0].get_xdata().copy()
    original_speed_y = figure.axes[0].lines[0].get_ydata().copy()
    view.update(100.0)
    np.testing.assert_array_equal(figure.axes[0].lines[1].get_xdata(), [0.0, 0.0])
    view.update(160.0)
    np.testing.assert_array_equal(figure.axes[0].lines[1].get_xdata(), [1.0, 1.0])
    view.update(220.0)
    np.testing.assert_array_equal(figure.axes[0].lines[1].get_xdata(), [2.0, 2.0])
    np.testing.assert_array_equal(figure.axes[0].lines[0].get_xdata(), original_speed_x)
    np.testing.assert_array_equal(figure.axes[0].lines[0].get_ydata(), original_speed_y)

    view.close()
    assert not figure.axes
    with pytest.raises(RuntimeError, match="not been built"):
        view.update(160.0)


def _store_context(*, complete: bool) -> StoreViewContext:
    timestamps_s = np.array([100.0, 160.0, 220.0, 280.0])
    states_m = np.array(
        [
            [7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0],
            [0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0],
            [-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0],
            [0.0, -7_000_000.0, 0.0, 7_500.0, 0.0, 0.0],
        ]
    )
    store = OemDataStore()
    epoch = store.begin(len(timestamps_s))
    reservation = store.reserve(len(timestamps_s))
    reservation.raw[:, 0] = timestamps_s
    reservation.raw[:, 1:7] = states_m
    reservation.segment_ids[:] = [0, 0, 1, 1]
    store.commit(reservation, len(timestamps_s))
    if complete:
        store.mark_complete(epoch, (), ())

    snapshot = store.snapshot()
    store.series(snapshot, (100.0, 280.0), groups=("kinematics",), wait=True)
    return StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(100.0, 280.0),
        coverage=(100.0, 280.0),
    )


def test_speed_altitude_store_view_shares_query_buffers_and_preserves_segments() -> None:
    context = _store_context(complete=True)
    view = SpeedAltitudeView(start_time_s=100.0)
    figure = view.build_from_store(context)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()

    query = view._store_query
    assert query is not None
    group = query.value[0]
    assert len(group.segment_bounds) == 2
    assert len(view._store_patches[0]) == 2
    assert all(isinstance(patch, PathPatch) for patch in view._store_patches[0])
    for patch in view._store_patches[0]:
        assert np.shares_memory(patch.get_path().vertices, group.values)
    for patch in view._store_patches[1]:
        assert np.shares_memory(patch.get_path().vertices, group.values)

    vertices = view._store_patches[0][0].get_path().vertices
    display = view._store_patches[0][0].get_transform().transform(vertices)
    data_coordinates = figure.axes[0].transData.inverted().transform(display)
    np.testing.assert_allclose(
        data_coordinates[:, 0],
        (vertices[:, 0] - 100.0) / 60.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(data_coordinates[:, 1], vertices[:, 1] / 1000.0)
    assert figure.axes[0].get_ylabel() == "Speed (km/s)"
    assert figure.axes[1].get_ylabel() == "Altitude (km)"

    view.set_time_range(ResolvedTimeRange(160.0, 280.0), (100.0, 280.0))
    assert view._store_context is not None
    assert view._store_context.plot_range == ResolvedTimeRange(160.0, 280.0)
    view.update(220.0)
    np.testing.assert_array_equal(view.cursor_artists[0].get_xdata(), [2.0, 2.0])
    assert view.cursor_artists[0].get_visible()

    assert context.store._tier_interest["series"] == 1
    view.close()
    assert "series" not in context.store._tier_interest


def test_speed_altitude_store_view_handles_empty_and_partial_coverage() -> None:
    empty_store = OemDataStore()
    empty_store.begin(1)
    empty_context = StoreViewContext.capture(
        empty_store,
        time_unit=TimeUnit.MINUTES,
        plot_range=None,
        coverage=(100.0, 100.0),
    )
    empty_view = SpeedAltitudeView(start_time_s=100.0)
    empty_figure = empty_view.build_from_store(empty_context)
    FigureCanvasAgg(empty_figure).draw()
    assert empty_view._store_query is not None
    assert empty_view._store_query.coverage.requested_s is None
    assert not empty_view._store_query.value
    assert not empty_view._store_patches[0]
    assert all(artist.get_visible() for artist in empty_view._store_empty_artists or ())
    empty_view.close()

    partial_context = _store_context(complete=False)
    partial_context = partial_context.with_range(
        ResolvedTimeRange(100.0, 400.0), (100.0, 400.0)
    )
    partial_context.series("kinematics", wait=True)
    partial_view = SpeedAltitudeView(start_time_s=100.0)
    partial_figure = partial_view.build_from_store(partial_context)
    FigureCanvasAgg(partial_figure).draw()
    assert partial_view._store_query is not None
    assert not partial_view._store_query.coverage.complete
    assert partial_view._store_patches[0]
    partial_view.close()
