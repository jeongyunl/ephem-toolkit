"""Tests for per-stack Ground Station selection state."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from matplotlib.figure import Figure
import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.oem_data_store import (
    ColumnGroupView,
    LookAngleProfileView,
    OemDataStore,
    StationAccessView,
)
from ephem_toolkit.play_oem.station_access import (
    AccessInterval,
    LookAngleProfile,
    StationAccess,
)
from ephem_toolkit.play_oem.station_analysis import (
    StationAnalysisContext,
    StationAnalysisSelection,
)
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import (
    StoreViewContext,
    station_access_from_store,
)
from ephem_toolkit.play_oem.views.ground_station_pass_track import (
    GroundStationPassTrackView,
)
from ephem_toolkit.play_oem.views.ground_station_analysis import (
    GroundStationAnalysisView,
)


def test_context_publishes_station_and_interval_selection_without_redundant_events() -> None:
    context = StationAnalysisContext()
    updates: list[StationAnalysisSelection] = []
    unsubscribe = context.subscribe(updates.append)

    context.select_station("north")
    context.select_interval((10.0, 20.0))
    context.select_interval((10.0, 20.0))
    context.select_station("south")

    assert updates == [
        StationAnalysisSelection("north"),
        StationAnalysisSelection("north", (10.0, 20.0)),
        StationAnalysisSelection("south"),
    ]
    assert context.selection == StationAnalysisSelection("south")
    unsubscribe()
    context.select_interval((30.0, 40.0))
    assert len(updates) == 3


def test_context_retains_valid_station_and_clears_stale_pass_selection() -> None:
    context = StationAnalysisContext()
    updates: list[StationAnalysisSelection] = []
    context.subscribe(updates.append)
    context.select_station("north")
    context.select_interval((10.0, 20.0))

    context.retain_stations({"north", "south"})

    assert context.selection == StationAnalysisSelection("north")
    context.select_interval((30.0, 40.0))
    context.retain_stations({"south"})
    assert context.selection == StationAnalysisSelection()
    assert updates[-1] == StationAnalysisSelection()


def test_range_profile_uses_cached_values_only_inside_plot_range() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0)
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([10.0, 20.0, 30.0, 40.0]),
        np.asarray([100.0, 90.0, 80.0, 70.0]),
    )
    result = StationAccess(station, (), look_angle_profiles=(profile,))
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(10.0, 20.0),
    )
    figure = Figure()
    view._figure = figure
    view._axes = figure.add_subplot(111)

    view._draw_profile(result, station)

    line = view._axes.lines[-1]
    assert np.array_equal(line.get_xdata(), np.asarray([10.0, 20.0]) / 60.0)
    assert np.array_equal(line.get_ydata(), np.asarray([90.0, 80.0]))


def test_store_station_profiles_share_their_backing_columns() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0)
    values = np.asarray(
        [
            [0.0, 1.0, 2.0, 3.0],
            [10.0, 11.0, 12.0, 13.0],
        ]
    )
    group = ColumnGroupView(
        values,
        ("t", "azimuth_deg", "elevation_deg", "range_km"),
        (),
    )
    adapted = station_access_from_store(
        StationAccessView(station, (LookAngleProfileView(group),), (), None)
    )
    profile = adapted.look_angle_profiles[0]

    assert np.shares_memory(profile.times_s, group.values)
    assert np.shares_memory(profile.azimuths_deg, group.values)
    assert np.shares_memory(profile.elevations_deg, group.values)
    assert np.shares_memory(profile.slant_ranges_km, group.values)


def _station_store_context(*, complete: bool) -> tuple[
    OemDataStore, StoreViewContext, GroundStation
]:
    elevations = np.asarray([0.0, 60.0, 0.0])
    states = np.column_stack(
        (
            6_378_137.0 + np.sin(np.deg2rad(elevations)) * 1_000_000.0,
            np.cos(np.deg2rad(elevations)) * 1_000_000.0,
            np.zeros(3),
            np.zeros((3, 3)),
        )
    )
    store = OemDataStore()
    epoch = store.begin(len(elevations))
    reservation = store.reserve(len(elevations))
    reservation.raw[:, 0] = [0.0, 60.0, 120.0]
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = 0
    store.commit(reservation, len(elevations))
    if complete:
        store.mark_complete(
            epoch,
            (),
            (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
        )
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(0.0, 120.0),
        coverage=(0.0, 120.0),
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0, 10)
    return store, context, station


def test_store_station_view_refreshes_pending_data_and_reuses_profile_columns() -> None:
    store, context, station = _station_store_context(complete=False)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=context.plot_range,
    )
    view._build_panel = lambda: cast(Any, None)

    try:
        view.build_from_store(context)
        assert not view._store_queries[station.station_id].coverage.complete

        store.mark_complete(
            context.snapshot.epoch,
            (),
            (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")),
        )
        refreshed = context.refresh()
        store.station_access(refreshed.snapshot, station, (0.0, 120.0), wait=True)
        view.update_from_store(refreshed)

        query = view._store_queries[station.station_id]
        profile = view._results[station.station_id].look_angle_profiles[0]
        group = query.value.profiles[0].group
        assert query.coverage.complete
        assert np.shares_memory(profile.times_s, group.values)
        assert view._store_context is not None
        assert view._store_context.snapshot.revision > context.snapshot.revision
    finally:
        view.close()
        store.close()


def test_store_station_view_reports_pending_access_coverage() -> None:
    store, context, station = _station_store_context(complete=False)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=context.plot_range,
    )
    view._build_panel = lambda: cast(Any, None)
    labels: list[str] = []
    view._status_label = SimpleNamespace(SetLabel=labels.append)

    try:
        view.build_from_store(context)
        view._update_status_text()

        assert not view._store_queries[station.station_id].coverage.complete
        assert labels[-1] == "Station data is loading."
    finally:
        view.close()
        store.close()


@pytest.mark.parametrize(
    ("terminal_state", "expected_message"),
    (
        ("failed", "OEM load failed: reader broke"),
        ("cancelled", "OEM loading was cancelled; showing available data."),
    ),
)
def test_store_station_view_reports_terminal_load_state(
    terminal_state: str, expected_message: str
) -> None:
    store, context, station = _station_store_context(complete=False)
    if terminal_state == "failed":
        store.mark_failed(context.snapshot.epoch, RuntimeError("reader broke"))
    else:
        assert store.cancel_if_epoch(context.snapshot.epoch)
    context = context.refresh()
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=context.plot_range,
    )
    view._build_panel = lambda: cast(Any, None)
    labels: list[str] = []
    view._status_label = SimpleNamespace(SetLabel=labels.append)

    try:
        view.build_from_store(context)
        view._update_status_text()

        assert view._store_context is not None
        assert view._store_context.snapshot.sample_count == 3
        assert not view._store_queries[station.station_id].coverage.complete
        assert labels[-1] == expected_message
    finally:
        view.close()
        assert "station-access" not in store._tier_interest
        store.close()


def test_store_station_view_renders_empty_access_as_empty_not_loading() -> None:
    store = OemDataStore()
    epoch = store.begin(1)
    store.mark_complete(
        epoch, (), (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    )
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(0.0, 120.0),
        coverage=(0.0, 120.0),
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0, 10)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=context.plot_range,
    )
    view._build_panel = lambda: cast(Any, None)
    labels: list[str] = []
    view._status_label = SimpleNamespace(SetLabel=labels.append)

    try:
        view.build_from_store(context)
        view._update_status_text()

        assert view._store_queries[station.station_id].coverage.complete
        assert labels[-1] == "No station profile samples are available in this range."
    finally:
        view.close()
        assert "station-access" not in store._tier_interest
        store.close()


def test_store_station_profile_keeps_multi_segment_runs_separate() -> None:
    elevations = np.asarray([0.0, 60.0, 0.0, 0.0, 60.0, 0.0])
    states = np.column_stack(
        (
            6_378_137.0 + np.sin(np.deg2rad(elevations)) * 1_000_000.0,
            np.cos(np.deg2rad(elevations)) * 1_000_000.0,
            np.zeros(6),
            np.zeros((6, 3)),
        )
    )
    times = np.asarray([0.0, 60.0, 120.0, 240.0, 300.0, 360.0])
    store = OemDataStore()
    epoch = store.begin(len(times))
    reservation = store.reserve(len(times))
    reservation.raw[:, 0] = times
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = [0, 0, 0, 1, 1, 1]
    store.commit(reservation, len(times))
    store.mark_complete(
        epoch, (), (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    )
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(0.0, 360.0),
        coverage=(0.0, 360.0),
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0, 10)
    store.station_access(context.snapshot, station, (0.0, 360.0), wait=True)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=360.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=context.plot_range,
    )
    view._build_panel = lambda: cast(Any, None)
    figure = Figure()
    view._figure = figure
    view._axes = figure.add_subplot(111)

    try:
        view.build_from_store(context)
        result = view._results[station.station_id]
        view._draw_profile(result, station)

        assert len(result.look_angle_profiles) == 2
        assert len(view._axes.lines) == 2
        assert view._axes.lines[0].get_xdata()[-1] == 2.0
        assert view._axes.lines[1].get_xdata()[0] == 4.0
    finally:
        view.close()
        assert "station-access" not in store._tier_interest
        store.close()


def test_store_profile_plot_bounds_display_samples() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0)
    times = np.arange(5001.0)
    profile = LookAngleProfile(times, times % 360.0, times % 90.0, times + 1.0)
    result = StationAccess(station, (), look_angle_profiles=(profile,))
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=5000.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(0.0, 5000.0),
    )
    view._store_context = cast(StoreViewContext, object())
    figure = Figure()
    view._figure = figure
    view._axes = figure.add_subplot(111)

    view._draw_profile(result, station)

    line = view._axes.lines[-1]
    assert len(line.get_xdata()) <= 2000
    assert line.get_xdata()[0] == 0.0
    assert line.get_xdata()[-1] == 5000.0 / 60.0


def test_time_profiles_hide_samples_below_station_elevation_mask() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0, 10)
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([0.0, 90.0, 180.0, 270.0]),
        np.asarray([9.0, 10.0, 5.0, 20.0]),
        np.asarray([100.0, 90.0, 80.0, 70.0]),
    )
    result = StationAccess(station, (), look_angle_profiles=(profile,))

    for panel_type in (
        "elevation-profile",
        "azimuth-profile",
        "range-profile",
    ):
        view = GroundStationAnalysisView(
            cast(Any, None),
            panel_type,
            cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
            [station],
            TimeUnit.MINUTES,
            "Test object",
            oem_loaded=True,
            on_station_manager=lambda: None,
            selection_context=StationAnalysisContext(),
            initial_range=ResolvedTimeRange(0.0, 30.0),
        )
        figure = Figure()
        view._figure = figure
        view._axes = figure.add_subplot(111)

        view._draw_profile(result, station)

        line = view._axes.lines[-1]
        assert view._mask_filter_enabled
        assert np.array_equal(
            line.get_xdata(), np.asarray([0.0, 10.0, 20.0, 30.0]) / 60.0
        )
        assert np.array_equal(
            np.isnan(line.get_ydata()), np.asarray([True, False, True, False])
        )
        expected_above_mask = {
            "elevation-profile": 10.0,
            "azimuth-profile": 90.0,
            "range-profile": 90.0,
        }[panel_type]
        assert line.get_ydata()[1] == expected_above_mask

        view._mask_filter_control = SimpleNamespace(GetValue=lambda: False)
        view._on_mask_filter_toggled(cast(Any, None))

        assert not view._mask_filter_enabled
        assert np.isfinite(view._axes.lines[-1].get_ydata()).all()


def test_pass_strip_filters_intervals_by_plot_range() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0)
    intervals = (
        AccessInterval(0.0, 5.0, 20.0, 2.0, 500.0, 2.0),
        AccessInterval(10.0, 15.0, 30.0, 12.0, 400.0, 12.0),
        AccessInterval(20.0, 25.0, 40.0, 22.0, 300.0, 22.0),
    )
    result = StationAccess(station, intervals)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "pass-strip",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(14.0, 21.0),
    )

    assert view._visible_intervals(result) == intervals[1:]


def test_empty_plot_range_does_not_prepare_historical_station_data() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "pass-strip",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=None,
    )

    assert view._results == {}


def test_ground_station_pass_track_uses_bound_store_queries() -> None:
    station = GroundStation("north", "North Site", 1.0, 2.0, 0.0)
    timestamps_s = np.array([0.0, 10.0, 20.0, 30.0])
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
    store.mark_complete(epoch, (), (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF")))
    snapshot = store.snapshot()
    for bounds in ((0.0, 10.0), (10.0, 20.0)):
        store.ground_track(snapshot, bounds, wait=True)
    store_context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(0.0, 30.0),
        coverage=(0.0, 30.0),
    )

    selection_context = StationAnalysisContext()
    selection_context.select_station(station.station_id)
    selection_context.select_interval((0.0, 10.0))
    view = GroundStationPassTrackView(
        cast(Any, None),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        oem_loaded=True,
        selection_context=selection_context,
    )
    view._store_binding.bind(store_context)
    view._store_context = store_context
    figure = Figure()
    view._figure = figure
    view._axes = figure.add_subplot(111)

    class _Status:
        message = ""

        def SetLabel(self, message: str) -> None:
            self.message = message

    class _Canvas:
        def draw_idle(self) -> None:
            pass

    view._status = cast(Any, _Status())
    view._canvas = cast(Any, _Canvas())
    view._draw()
    assert len(view._axes.lines) == 1
    assert view._status.message.startswith("North Site ·")

    selection_context.select_interval((10.0, 20.0))
    assert len(view._axes.lines) == 2
    assert len(view._axes.collections) == 1
    view.close()
    assert "ground-track" not in store._tier_interest
    assert "earth-fixed" not in store._tier_interest
