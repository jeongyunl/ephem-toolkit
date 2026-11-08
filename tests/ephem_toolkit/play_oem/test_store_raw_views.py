"""Store-backed raw state and 3D view tests."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import PathPatch

from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import StoreViewContext
from ephem_toolkit.play_oem.views.state_components import StateComponentsView
from ephem_toolkit.play_oem.views.trajectory3d import Trajectory3DView


def _store_context() -> StoreViewContext:
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
    store.mark_complete(epoch, (), ())
    return StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(100.0, 280.0),
        coverage=(100.0, 280.0),
    )


def test_state_components_paths_share_raw_columns_and_update_ranges() -> None:
    context = _store_context()
    view = StateComponentsView(100.0, "GCRF / Earth")
    figure = view.build_from_store(context)
    FigureCanvasAgg(figure).draw()

    assert len(figure.axes) == 6
    for axes in figure.axes:
        paths = [artist for artist in axes.patches if isinstance(artist, PathPatch)]
        assert len(paths) == 2
        assert all(
            np.shares_memory(path.get_path().vertices, context.snapshot.raw)
            for path in paths
        )

    position_x = figure.axes[0]
    first_path = next(
        artist
        for artist in position_x.patches
        if isinstance(artist, PathPatch)
    )
    display = first_path.get_transform().transform(first_path.get_path().vertices)
    data = position_x.transData.inverted().transform(display)
    np.testing.assert_allclose(data[:, 0], [0.0, 1.0], atol=1e-12)
    np.testing.assert_allclose(data[:, 1], [7000.0, 0.0], atol=1e-10)

    original_y_limits = tuple(axes.get_ylim() for axes in figure.axes)
    view.set_time_range(ResolvedTimeRange(160.0, 220.0), context.coverage)
    view.update(160.0)
    assert tuple(axes.get_ylim() for axes in figure.axes) == original_y_limits
    assert view.cursor_artists[0].get_visible()
    view.set_time_range(None, context.coverage)
    assert all(not axes.patches for axes in figure.axes)
    assert all(not artist.get_visible() for artist in view.cursor_artists)
    view.close()


def test_trajectory3d_store_paths_are_bounded_and_range_updates_keep_camera() -> None:
    context = _store_context()
    view = Trajectory3DView(None, "ISS", "EME2000 / Earth")
    figure = view.build_from_store(context)
    FigureCanvasAgg(figure).draw()

    assert view._store_positions_m is not None
    assert np.shares_memory(view._store_positions_m, context.snapshot.raw)
    assert len(view._orbit_artists) == 2
    for _, artist in view._orbit_artists:
        coordinates = artist.get_data_3d()
        assert len(coordinates[0]) == 2
        assert len(coordinates[1]) == 2
        assert len(coordinates[2]) == 2

    axes = figure.axes[0]
    original_limits = (axes.get_xlim(), axes.get_ylim(), axes.get_zlim())
    view.set_time_range(ResolvedTimeRange(160.0, 220.0), context.coverage)
    view.update(160.0)
    assert (axes.get_xlim(), axes.get_ylim(), axes.get_zlim()) == original_limits
    assert view._cursor_artist is not None and view._cursor_artist.get_visible()
    assert view._start_artist is not None and not view._start_artist.get_visible()
    assert view._end_artist is not None and not view._end_artist.get_visible()
    assert [len(line.get_data_3d()[0]) for _, line in view._orbit_artists] == [1, 1]

    view.set_time_range(None, context.coverage)
    assert not view._orbit_artists
    assert view._cursor_artist is not None and not view._cursor_artist.get_visible()
    view.close()
