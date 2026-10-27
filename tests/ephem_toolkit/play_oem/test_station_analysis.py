"""Tests for per-stack Ground Station selection state."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from matplotlib.figure import Figure
import numpy as np

from ephem_toolkit.play_oem.ground_stations import GroundStation
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
from ephem_toolkit.play_oem.ground_track import GroundTrackCoordinates
from ephem_toolkit.play_oem.ground_track import GroundTrackSource
from ephem_toolkit.play_oem.views import ground_station_pass_track
from ephem_toolkit.play_oem.views.ground_station_pass_track import (
    _clip_coordinates,
    GroundStationPassTrackView,
)
from ephem_toolkit.play_oem.views.ground_station_analysis import (
    GroundStationAnalysisView,
)


class _PreparedAccess:
    def __init__(self, result: StationAccess) -> None:
        self.result = result
        self.position_cache = object()
        self.prepare_calls = 0

    def prepare(self, *_args: Any) -> StationAccess:
        self.prepare_calls += 1
        return self.result


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
    cache = _PreparedAccess(result)
    view = GroundStationAnalysisView(
        cast(Any, None),
        "range-profile",
        cast(Any, object()),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        access_cache=cast(Any, cache),
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
            cast(Any, object()),
            cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
            [station],
            TimeUnit.MINUTES,
            "Test object",
            oem_loaded=True,
            on_station_manager=lambda: None,
            access_cache=cast(Any, _PreparedAccess(result)),
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
        cast(Any, object()),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        access_cache=cast(Any, _PreparedAccess(result)),
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(14.0, 21.0),
    )

    assert view._visible_intervals(result) == intervals[1:]


def test_empty_plot_range_does_not_prepare_historical_station_data() -> None:
    station = GroundStation("north", "North Site", 0.0, 0.0, 0.0)
    cache = _PreparedAccess(StationAccess(station, ()))
    view = GroundStationAnalysisView(
        cast(Any, None),
        "pass-strip",
        cast(Any, object()),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        access_cache=cast(Any, cache),
        selection_context=StationAnalysisContext(),
        initial_range=None,
    )

    assert cache.prepare_calls == 0


def test_pass_ground_track_clips_samples_to_selected_interval() -> None:
    coordinates = GroundTrackCoordinates(
        timestamps_s=np.asarray([0.0, 10.0, 20.0, 30.0]),
        latitude_rad=np.asarray([0.0, 0.1, 0.2, 0.3]),
        longitude_rad=np.asarray([0.0, 0.2, 0.4, 0.6]),
        segment_ids=np.asarray([0, 0, 1, 1]),
        source_frame="ITRF",
    )

    clipped = _clip_coordinates(coordinates, (10.0, 20.0))

    assert np.array_equal(clipped.timestamps_s, np.asarray([10.0, 20.0]))
    assert np.array_equal(clipped.segment_ids, np.asarray([0, 1]))


def test_pass_ground_track_reuses_shared_position_cache_on_interval_changes(
    monkeypatch,
) -> None:
    station = GroundStation("north", "North Site", 1.0, 2.0, 0.0)
    source = GroundTrackSource.from_samples(
        [0.0, 10.0, 20.0, 30.0],
        np.tile(np.asarray([6_378_000.0, 0.0, 0.0, 0.0, 0.0, 0.0]), (4, 1)),
        [0, 0, 0, 0],
        "EARTH",
        "ITRF",
    )
    position_cache = object()
    access_cache = _PreparedAccess(StationAccess(station, ()))
    access_cache.position_cache = position_cache
    context = StationAnalysisContext()
    context.select_station(station.station_id)
    context.select_interval((0.0, 10.0))
    view = GroundStationPassTrackView(
        cast(Any, None),
        source,
        cast(Any, SimpleNamespace(t_start=0.0, t_end=30.0)),
        [station],
        oem_loaded=True,
        access_cache=cast(Any, access_cache),
        selection_context=context,
    )
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
    calls: list[tuple[Any, tuple[float, float]]] = []

    def prepare(_source, *, position_cache, bounds):
        calls.append((position_cache, bounds))
        return GroundTrackCoordinates(
            np.asarray([0.0, 10.0, 20.0, 30.0]),
            np.asarray([0.0, 0.1, 0.2, 0.3]),
            np.asarray([0.0, 0.2, 0.4, 0.6]),
            np.asarray([0, 0, 0, 0]),
            "ITRF",
        )

    monkeypatch.setattr(ground_station_pass_track, "prepare_ground_track", prepare)
    view._draw()
    context.select_interval((10.0, 20.0))

    assert calls == [
        (position_cache, (0.0, 10.0)),
        (position_cache, (10.0, 20.0)),
    ]
    assert np.allclose(view._axes.lines[-1].get_xdata(), np.rad2deg([0.2, 0.4]))
    view.close()
