"""Store-backed history views must retain store-owned coordinate buffers."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import PathPatch
from matplotlib.path import Path

from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.angular_velocity import AngularVelocityView
from ephem_toolkit.play_oem.views.base import StoreViewBinding, StoreViewContext
from ephem_toolkit.play_oem.views.direction_change import DirectionChangeView
from ephem_toolkit.play_oem.views.distance import GeocentricDistanceView
from ephem_toolkit.play_oem.views.rtn import RtnDeltaView


def _store_context(
    plot_range: ResolvedTimeRange | None = ResolvedTimeRange(100.0, 280.0),
) -> StoreViewContext:
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
    snapshot = store.snapshot()
    store.series(
        snapshot,
        (100.0, 280.0),
        groups=("rtn", "direction-rates", "kinematics", "distance-delta"),
        wait=True,
    )
    return StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=plot_range,
        coverage=(100.0, 280.0),
    )


def _assert_store_paths(
    artists: tuple[object, ...],
    groups,
    axes,
    *,
    time_origin_s: float = 100.0,
    time_divisor_s: float = 60.0,
    scale_y: float,
) -> None:
    assert artists
    paths = tuple(artist for artist in artists if isinstance(artist, PathPatch))
    assert len(paths) == len(artists)
    for artist in paths:
        vertices = artist.get_path().vertices
        assert any(np.shares_memory(vertices, group.values) for group in groups)
        assert artist.get_path().codes is not None
        assert artist.get_path().codes[0] == Path.MOVETO
        display = artist.get_transform().transform(vertices)
        data = axes.transData.inverted().transform(display)
        np.testing.assert_allclose(
            data[:, 0],
            (vertices[:, 0] - time_origin_s) / time_divisor_s,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            data[:, 1], vertices[:, 1] * scale_y, atol=1e-12
        )


def test_store_view_context_refresh_and_binding_lifecycle() -> None:
    store = OemDataStore()
    store.begin(2)
    first = store.reserve(1)
    first.raw[0] = [100.0, 7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]
    first.segment_ids[0] = 0
    store.commit(first, 1)

    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(100.0, 220.0),
        coverage=(100.0, 220.0),
    )
    assert context.snapshot.sample_count == 1

    second = store.reserve(1)
    second.raw[0] = [220.0, 0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]
    second.segment_ids[0] = 0
    store.commit(second, 1)
    refreshed = context.refresh()
    assert context.snapshot.sample_count == 1
    assert refreshed.snapshot.sample_count == 2

    no_range = context.with_range(None, context.coverage)
    assert no_range.snapshot is context.snapshot
    empty_query = no_range.series("kinematics")
    assert empty_query.value == ()
    assert empty_query.coverage.requested_s is None

    other_store = OemDataStore()
    other_store.begin(1)
    other_context = StoreViewContext.capture(
        other_store,
        time_unit=TimeUnit.MINUTES,
        plot_range=None,
        coverage=(100.0, 100.0),
    )
    binding = StoreViewBinding(("series",))
    binding.bind(context)
    binding.bind(refreshed)
    assert store._tier_interest["series"] == 1
    assert binding.context is refreshed
    bound_range = binding.with_range(None, context.coverage)
    assert binding.context is bound_range
    assert bound_range.snapshot is refreshed.snapshot
    binding.bind(other_context)
    assert "series" not in store._tier_interest
    assert other_store._tier_interest["series"] == 1
    binding.close()
    assert binding.context is None
    assert "series" not in other_store._tier_interest


@pytest.mark.parametrize(
    ("view_type", "query_group", "scales"),
    [
        (
            RtnDeltaView,
            "rtn",
            (0.001, 0.001, 0.001),
        ),
        (
            AngularVelocityView,
            "direction-rates",
            (180.0 / np.pi, 1.0),
        ),
        (
            DirectionChangeView,
            "direction-rates",
            (180.0 / np.pi,),
        ),
        (
            GeocentricDistanceView,
            "kinematics",
            (0.001,),
        ),
    ],
)
def test_store_history_views_use_store_owned_paths(
    view_type, query_group, scales
) -> None:
    context = _store_context()
    view = view_type(100.0, "Test spacecraft")
    figure = view.build_from_store(context)
    FigureCanvasAgg(figure).draw()

    assert view._store_query is not None
    groups = (
        view._store_query.value[query_group]
        if view_type is GeocentricDistanceView
        else view._store_query.value
    )
    assert groups
    if view_type is DirectionChangeView:
        assert len(view._store_artists[0]) == 6
        assert len(view._store_artists[1]) == 6
        for artists in view._store_artists:
            for artist in artists:
                assert isinstance(artist, PathPatch)
                assert any(
                    np.shares_memory(artist.get_path().vertices, group.values)
                    for group in groups
                )
        for axes, artists in zip(figure.axes, view._store_artists):
            _assert_store_paths(
                artists, groups, axes, scale_y=180.0 / np.pi
            )
        assert figure.axes[0].get_ylabel() == "Euler Angle (deg)"
        assert figure.axes[1].get_ylabel() == "Euler Angle Rate (deg/s)"
    elif view_type is RtnDeltaView:
        assert len(view._store_artists) == 3
        for axes, artists, scale in zip(
            figure.axes, view._store_artists, scales
        ):
            _assert_store_paths(artists, groups, axes, scale_y=scale)
        assert figure.axes[0].get_ylabel() == "Radial Delta (km)"
    elif view_type is AngularVelocityView:
        assert len(view._store_artists) == 2
        for axes, artists, scale in zip(
            figure.axes, view._store_artists, scales
        ):
            _assert_store_paths(artists, groups, axes, scale_y=scale)
        zero_breaks = [
            artist.get_path()
            for artist in view._store_artists[0]
            if np.any(artist.get_path().vertices[:, 1] == 0.0)
        ]
        assert zero_breaks
        for path in zero_breaks:
            zero_values = path.vertices[:, 1] == 0.0
            assert np.all(path.codes[zero_values] == Path.MOVETO)
            assert np.all(
                path.codes[1:][zero_values[:-1]] == Path.MOVETO
            )
        assert figure.axes[0].get_ylabel() == "Angular Velocity (deg/s)"
    else:
        distance_groups = groups
        delta_groups = view._store_query.value["distance-delta"]
        _assert_store_paths(
            view._store_artists[0],
            distance_groups,
            figure.axes[0],
            scale_y=scales[0],
        )
        _assert_store_paths(
            view._store_artists[1],
            delta_groups,
            figure.axes[1],
            scale_y=scales[0],
        )
        assert figure.axes[0].get_ylabel() == "Geocentric Distance (km)"
        assert figure.axes[1].get_ylabel() == "Geocentric Distance Delta (km)"

    original_y_limits = tuple(axes.get_ylim() for axes in figure.axes)
    view.set_time_range(ResolvedTimeRange(160.0, 220.0), context.coverage)
    assert tuple(axes.get_ylim() for axes in figure.axes) == original_y_limits
    view.update(220.0)
    assert view.cursor_artists[0].get_visible()
    assert context.store._tier_interest["series"] == 1
    view.close()
    assert "series" not in context.store._tier_interest


@pytest.mark.parametrize(
    ("view_type", "plot_range", "empty_label"),
    [
        (
            view_type,
            None,
            "Plot range does not overlap OEM coverage",
        )
        for view_type in (
            RtnDeltaView,
            AngularVelocityView,
            DirectionChangeView,
            GeocentricDistanceView,
        )
    ]
    + [
        (
            view_type,
            ResolvedTimeRange(500.0, 600.0),
            "No samples in plot range",
        )
        for view_type in (
            RtnDeltaView,
            AngularVelocityView,
            DirectionChangeView,
            GeocentricDistanceView,
        )
    ],
)
def test_store_history_views_handle_empty_ranges(
    view_type, plot_range, empty_label
) -> None:
    context = _store_context(plot_range=plot_range)
    view = view_type(100.0, "Test spacecraft")
    figure = view.build_from_store(context)
    FigureCanvasAgg(figure).draw()

    assert view._store_query is not None
    if plot_range is None:
        assert view._store_query.coverage.requested_s is None
    if view_type is GeocentricDistanceView:
        assert not any(view._store_query.value.values())
    else:
        assert not view._store_query.value
    assert all(not artists for artists in view._store_artists)
    assert all(
        artist.get_visible() for artist in view._store_empty_artists or ()
    )
    assert all(
        artist.get_text() == empty_label
        for artist in view._store_empty_artists or ()
    )
    view.close()


@pytest.mark.parametrize(
    "view_type",
    (RtnDeltaView, AngularVelocityView, DirectionChangeView, GeocentricDistanceView),
)
def test_store_history_views_report_insufficient_samples(view_type) -> None:
    store = OemDataStore()
    store.begin(1)
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(100.0, 100.0),
        coverage=(100.0, 100.0),
    )
    view = view_type(100.0, "Test spacecraft")
    figure = view.build_from_store(context)
    FigureCanvasAgg(figure).draw()

    empty_artists = view._store_empty_artists or ()
    if view_type is GeocentricDistanceView:
        assert empty_artists[0].get_text() == "No samples in plot range"
        assert empty_artists[1].get_text() == "Not enough samples"
    else:
        assert all(artist.get_text() == "Not enough samples" for artist in empty_artists)
    assert all(artist.get_visible() for artist in empty_artists)
    view.close()
