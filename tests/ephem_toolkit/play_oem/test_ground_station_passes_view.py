"""Plot-range filtering and sky rendering for Ground Station Passes."""

from __future__ import annotations

import gc
import os
import warnings
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import pytest

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem import graph_panel
from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.station_access import (
    AccessInterval,
    LookAngleProfile,
    StationAccess,
)
from ephem_toolkit.play_oem.station_analysis import StationAnalysisContext
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import StoreViewContext
from ephem_toolkit.play_oem.views.ground_station_access import (
    GroundStationAccessView,
)
from ephem_toolkit.play_oem.views.ground_station_passes import (
    GroundStationPassListView,
    GroundStationPassesView,
    GroundStationSkyView,
    _can_fit_side_by_side,
    _utc_label,
)
from ephem_toolkit.play_oem.views import ground_station_passes as passes_view_module


@pytest.fixture(scope="module")
def wx_app() -> Iterator[Any]:
    import wx

    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx cannot connect to the available display")
    app = wx.App.Get() or wx.App(False)
    yield app
    gc.collect()


def _interval(
    start_s: float,
    end_s: float,
    *,
    clipped_at_start: bool = False,
    clipped_at_end: bool = False,
    limited_by_gap_at_start: bool = False,
    limited_by_gap_at_end: bool = False,
) -> AccessInterval:
    return AccessInterval(
        start_s,
        end_s,
        45.0,
        (start_s + end_s) / 2.0,
        500.0,
        (start_s + end_s) / 2.0,
        clipped_at_start,
        clipped_at_end,
        limited_by_gap_at_start,
        limited_by_gap_at_end,
        350.0,
        10.0,
        10.0,
        10.0,
    )


def _set_complete_store_status(view: GroundStationPassesView) -> None:
    view._store_context = cast(
        Any,
        SimpleNamespace(snapshot=SimpleNamespace(status="complete", failure=None)),
    )
    view._refresh_rows()


def _make_view(
    intervals: tuple[AccessInterval, ...],
    *,
    station: GroundStation | None = None,
    profiles: tuple[LookAngleProfile, ...] = (),
    limitation: str | None = None,
    oem_loaded: bool = True,
    selection_context: StationAnalysisContext | None = None,
) -> tuple[GroundStationPassesView, None]:
    station = station or GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    result = StationAccess(station, intervals, limitation, look_angle_profiles=profiles)
    view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=oem_loaded,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        selection_context=selection_context,
    )
    view._access_results = (result,)
    return view, None


def test_plot_range_filters_by_overlap_and_keeps_full_pass_details() -> None:
    intervals = (_interval(10.0, 20.0), _interval(40.0, 50.0), _interval(60.0, 70.0))
    view, cache = _make_view(intervals)
    prepared = view._access_results[0]

    view.set_time_range(ResolvedTimeRange(19.0, 41.0), (0.0, 100.0))

    assert view._visible_intervals == intervals[:2]
    assert view._visible_intervals[0].start_s == 10.0
    assert view._visible_intervals[0].end_s == 20.0
    assert view._visible_intervals[1].start_s == 40.0
    assert view._visible_intervals[1].end_s == 50.0
    assert view._range_label_text == (
        f"Plot Range: {_utc_label(19.0)} UTC – {_utc_label(41.0)} UTC"
    )
    assert view._access_results[0] is prepared


def test_range_changes_preserve_or_fallback_selection_without_repreparing() -> None:
    intervals = (_interval(0.0, 10.0), _interval(20.0, 30.0), _interval(40.0, 50.0))
    view, cache = _make_view(intervals)
    view._current_time_s = 25.0

    view.set_time_range(ResolvedTimeRange(0.0, 50.0), (0.0, 100.0))
    assert view._selected_interval_key == (20.0, 30.0)
    view.set_time_range(ResolvedTimeRange(20.0, 45.0), (0.0, 100.0))
    assert view._selected_interval_key == (20.0, 30.0)
    view._current_time_s = 15.0
    view.set_time_range(ResolvedTimeRange(40.0, 50.0), (0.0, 100.0))
    assert view._selected_interval_key == (40.0, 50.0)


def test_store_sky_path_bounds_profile_samples() -> None:
    times = np.arange(5001.0)
    profile = LookAngleProfile(times, times % 360.0, times % 90.0)
    view, _cache = _make_view((_interval(0.0, 5000.0),), profiles=(profile,))
    view._store_context = cast(Any, object())
    interval = view._access_results[0].intervals[0]

    sampled_times, _azimuths, _elevations = view._profile_points(profile, interval)

    assert len(sampled_times) <= 2000
    assert sampled_times[0] == interval.start_s
    assert sampled_times[-1] == interval.end_s


@pytest.mark.parametrize(
    (
        "clipped_at_start",
        "limited_by_gap_at_start",
        "clipped_at_end",
        "limited_by_gap_at_end",
        "expected_start_elevation",
        "expected_end_elevation",
    ),
    [
        (False, False, False, False, 10.0, 10.0),
        (True, False, False, False, 5.0, 10.0),
        (False, True, False, False, 5.0, 10.0),
        (False, False, True, False, 10.0, 6.0),
        (False, False, False, True, 10.0, 6.0),
    ],
)
def test_pass_endpoint_angles_respect_mask_and_boundary_limits(
    clipped_at_start: bool,
    limited_by_gap_at_start: bool,
    clipped_at_end: bool,
    limited_by_gap_at_end: bool,
    expected_start_elevation: float,
    expected_end_elevation: float,
) -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = AccessInterval(
        0.0,
        20.0,
        30.0,
        10.0,
        500.0,
        10.0,
        clipped_at_start=clipped_at_start,
        clipped_at_end=clipped_at_end,
        limited_by_gap_at_start=limited_by_gap_at_start,
        limited_by_gap_at_end=limited_by_gap_at_end,
        start_azimuth_deg=350.0,
        start_elevation_deg=5.0,
        end_azimuth_deg=10.0,
        end_elevation_deg=6.0,
    )
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0]),
        np.asarray([350.0, 0.0, 10.0]),
        np.asarray([5.0, 30.0, 6.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))

    times, azimuths, elevations = view._profile_points(profile, interval)
    result = view._access_results[0]

    assert times[[0, -1]].tolist() == [interval.start_s, interval.end_s]
    np.testing.assert_allclose(
        azimuths[[0, -1]], [350.0, 10.0]
    )
    np.testing.assert_allclose(
        elevations[[0, -1]],
        [expected_start_elevation, expected_end_elevation],
    )
    assert view._look_angle_at(result, interval, interval.start_s) == (
        350.0,
        expected_start_elevation,
    )
    assert view._look_angle_at(result, interval, interval.end_s) == (
        10.0,
        expected_end_elevation,
    )


def test_pass_endpoint_helpers_keep_distinct_profile_coverage_rules() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = AccessInterval(
        0.0,
        20.0,
        30.0,
        10.0,
        500.0,
        10.0,
        start_azimuth_deg=350.0,
        start_elevation_deg=5.0,
        end_azimuth_deg=10.0,
        end_elevation_deg=6.0,
    )
    profile = LookAngleProfile(
        np.asarray([5.0, 10.0, 15.0]),
        np.asarray([355.0, 0.0, 5.0]),
        np.asarray([20.0, 30.0, 20.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))

    times, _azimuths, _elevations = view._profile_points(profile, interval)
    result = view._access_results[0]

    assert times.tolist() == [5.0, 10.0, 15.0]
    assert view._look_angle_at(result, interval, interval.start_s) == (350.0, 10.0)
    assert view._look_angle_at(result, interval, interval.end_s) == (10.0, 10.0)


def test_pass_endpoint_helpers_fall_back_when_boundary_angles_are_missing() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = AccessInterval(0.0, 20.0, 30.0, 10.0, 500.0, 10.0)
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0]),
        np.asarray([350.0, 0.0, 10.0]),
        np.asarray([5.0, 30.0, 6.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))

    times, azimuths, elevations = view._profile_points(profile, interval)
    result = view._access_results[0]

    assert times[[0, -1]].tolist() == [interval.start_s, interval.end_s]
    np.testing.assert_allclose(azimuths[[0, -1]], [350.0, 10.0])
    np.testing.assert_allclose(elevations[[0, -1]], [5.0, 6.0])
    assert view._look_angle_at(result, interval, interval.start_s) == (350.0, 5.0)
    assert view._look_angle_at(result, interval, interval.end_s) == (10.0, 6.0)


def test_pass_endpoint_lookup_preserves_time_tolerance() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = _interval(0.0, 20.0)
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0]),
        np.asarray([350.0, 0.0, 10.0]),
        np.asarray([5.0, 30.0, 6.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))
    result = view._access_results[0]

    assert view._look_angle_at(result, interval, 0.5e-9) == (350.0, 10.0)
    assert view._look_angle_at(result, interval, 1.5e-9)[1] < 10.0


def test_pass_endpoint_lookup_does_not_apply_mask_without_a_station(
    monkeypatch,
) -> None:
    interval = AccessInterval(
        0.0,
        20.0,
        30.0,
        10.0,
        500.0,
        10.0,
        start_azimuth_deg=350.0,
        start_elevation_deg=5.0,
        end_azimuth_deg=10.0,
        end_elevation_deg=6.0,
    )
    view, _cache = _make_view((interval,))
    monkeypatch.setattr(view, "_selected_station", lambda: None)
    result = view._access_results[0]

    assert view._profile_points(
        LookAngleProfile(
            np.asarray([0.0, 20.0]),
            np.asarray([350.0, 10.0]),
            np.asarray([5.0, 6.0]),
        ),
        interval,
    )[0].size == 0
    assert view._look_angle_at(result, interval, interval.start_s) == (350.0, 5.0)


def test_store_pass_view_uses_leased_station_access() -> None:
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
    epoch = store.begin(3)
    reservation = store.reserve(3)
    reservation.raw[:, 0] = [0.0, 60.0, 120.0]
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = 0
    store.commit(reservation, 3)
    store.mark_complete(
        epoch, (), (("CENTER_NAME", "EARTH"), ("REF_FRAME", "ITRF"))
    )
    station = GroundStation("equator", "Equator", 0.0, 0.0, 0.0, 10)
    bounds = ResolvedTimeRange(0.0, 120.0)
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=bounds,
        coverage=(0.0, 120.0),
    )
    store.station_access(context.snapshot, station, (0.0, 120.0), wait=True)
    view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        limit_to_range=True,
        initial_range=bounds,
    )
    view._build_panel = lambda: cast(Any, None)

    try:
        view.build_from_store(context)

        query = view._store_queries[station.station_id]
        result = view._result_for(station.station_id)
        assert result is not None
        profile = result.look_angle_profiles[0]
        group = query.value.profiles[0].group
        assert query.coverage.complete
        assert np.shares_memory(profile.times_s, group.values)
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
def test_store_pass_view_reports_terminal_load_state(
    terminal_state: str, expected_message: str
) -> None:
    store = OemDataStore()
    epoch = store.begin(1)
    if terminal_state == "failed":
        store.mark_failed(epoch, RuntimeError("reader broke"))
    else:
        assert store.cancel_if_epoch(epoch)
    context = StoreViewContext.capture(
        store,
        time_unit=TimeUnit.MINUTES,
        plot_range=ResolvedTimeRange(0.0, 100.0),
        coverage=(0.0, 100.0),
    )
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0)
    view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        limit_to_range=True,
        initial_range=context.plot_range,
    )
    view._build_panel = lambda: cast(Any, None)

    try:
        view.build_from_store(context)
        view._update_status(station, view._result_for(station.station_id))

        assert view._status_text == expected_message
    finally:
        view.close()
        assert "station-access" not in store._tier_interest
        store.close()


def test_pass_view_tracks_shared_stack_selection_and_unsubscribes_on_close() -> None:
    context = StationAnalysisContext()
    interval = _interval(10.0, 20.0)
    view, _cache = _make_view((interval,), selection_context=context)

    context.select_interval((10.0, 20.0))

    assert view._selected_interval_key == (10.0, 20.0)
    view.close()
    context.select_interval(None)
    assert view._selected_interval_key == (10.0, 20.0)


def test_deferred_layout_callback_is_ignored_after_view_close(monkeypatch) -> None:
    view, _cache = _make_view(())
    callbacks = []
    monkeypatch.setattr(passes_view_module.wx, "CallAfter", callbacks.append)

    class _Event:
        skipped = False

        def Skip(self) -> None:
            self.skipped = True

    class _DeletedWindow:
        def __getattr__(self, _name: str):
            raise AssertionError("deferred callback touched a closed wx window")

    view._analysis_panel = cast(Any, _DeletedWindow())
    view._analysis_sizer = cast(Any, _DeletedWindow())
    view._table_panel = cast(Any, _DeletedWindow())
    view._sky_panel = cast(Any, _DeletedWindow())
    event = _Event()

    view._on_panel_size(cast(Any, event))
    view.close()
    callbacks[0]()

    assert event.skipped


def test_focused_pass_list_and_sky_views_share_interval_selection() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = _interval(10.0, 20.0)
    context = StationAnalysisContext()
    context.select_station(station.station_id)
    options = dict(
        parent=cast(Any, None),
        cursor=cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        stations=[station],
        object_name="Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        selection_context=context,
    )
    pass_list = GroundStationPassListView(**options)
    sky_view = GroundStationSkyView(**options)
    for view in (pass_list, sky_view):
        view._access_results = (StationAccess(station, (interval,)),)
        view._refresh_rows()

    context.select_interval((10.0, 20.0))

    assert pass_list._selected_interval_key == (10.0, 20.0)
    assert sky_view._selected_interval_key == (10.0, 20.0)
    pass_list.close()
    sky_view.close()


def test_station_updates_retain_pass_selection_for_a_station_that_remains() -> None:
    intervals = (_interval(0.0, 10.0), _interval(20.0, 30.0))
    view, cache = _make_view(intervals)
    station = view._stations[0]
    view._selected_interval_key = (20.0, 30.0)

    view.set_stations([station])

    assert view.selected_station_id == station.station_id
    assert view._selected_interval_key is None


def test_no_overlap_no_access_and_unsupported_states_are_distinct() -> None:
    view, _cache = _make_view((_interval(10.0, 20.0),))
    view.set_time_range(ResolvedTimeRange(70.0, 80.0), (0.0, 100.0))
    assert not view._visible_intervals
    _set_complete_store_status(view)
    assert view._status_text == (
        "No access intervals overlap the current Plot Range. "
        "Widen the shared Plot Range to see more passes."
    )

    no_access, _cache = _make_view(())
    no_access.set_time_range(ResolvedTimeRange(70.0, 80.0), (0.0, 100.0))
    _set_complete_store_status(no_access)
    assert "No access intervals in OEM coverage" in no_access._status_text

    unsupported, _cache = _make_view(
        (), limitation="Unsupported Earth-centered frame."
    )
    unsupported.set_time_range(ResolvedTimeRange(70.0, 80.0), (0.0, 100.0))
    _set_complete_store_status(unsupported)
    assert unsupported._status_text == "Unsupported Earth-centered frame."

    no_effective_range, _cache = _make_view((_interval(10.0, 20.0),))
    no_effective_range.set_time_range(None, (0.0, 100.0))
    _set_complete_store_status(no_effective_range)
    assert no_effective_range._range_label_text == (
        "Plot Range: no effective range overlaps OEM coverage"
    )
    assert "does not overlap OEM coverage" in no_effective_range._status_text


def test_coverage_and_gap_limited_rows_do_not_claim_known_duration() -> None:
    intervals = (
        _interval(0.0, 10.0, clipped_at_start=True),
        _interval(20.0, 30.0, limited_by_gap_at_end=True),
    )
    view, _cache = _make_view(intervals)
    view._refresh_rows()

    assert view._visible_intervals == intervals
    assert view._row_values(intervals[0])[1] == ""
    assert view._row_values(intervals[0])[4] == "Starts at OEM boundary"
    assert view._row_values(intervals[1])[1] == ""
    assert view._row_values(intervals[1])[4] == "Gap-limited end"
    assert view._row_values(_interval(10.0, 20.0))[1] == "0.2 min"


def test_pass_study_switches_layout_only_when_both_minimum_widths_fit() -> None:
    assert not _can_fit_side_by_side(1_000, 1_040)
    assert _can_fit_side_by_side(1_040, 1_040)


def test_sky_plot_uses_clockwise_azimuth_and_cached_pass_profile() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = AccessInterval(
        0.0,
        20.0,
        30.0,
        10.0,
        500.0,
        10.0,
        start_azimuth_deg=350.0,
        start_elevation_deg=10.0,
        end_azimuth_deg=10.0,
        end_elevation_deg=10.0,
    )
    profile = LookAngleProfile(
        np.asarray([0.0, 5.0, 10.0, 15.0, 20.0]),
        np.asarray([350.0, 355.0, 0.0, 5.0, 10.0]),
        np.asarray([10.0, 20.0, 30.0, 20.0, 10.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))
    figure = Figure()
    canvas = FigureCanvasAgg(figure)
    view._figure = figure
    view._axes = figure.add_subplot(111, projection="polar")
    view._canvas = cast(Any, canvas)
    view._refresh_rows()
    view._draw_sky_plot()
    view.update(10.0)
    canvas.draw()

    assert view._axes.get_theta_direction() == -1
    assert view._axes.get_theta_offset() == np.pi / 2
    assert view._axes.lines[0].get_label() == "10° mask"
    legend = view._axes.get_legend()
    assert legend is not None
    legend_bounds = legend.get_window_extent(canvas.get_renderer())
    axes_bounds = view._axes.get_window_extent(canvas.get_renderer())
    assert legend_bounds.y1 < axes_bounds.y0
    assert axes_bounds.width >= figure.bbox.width * 0.4
    assert axes_bounds.height >= figure.bbox.height * 0.55
    path = next(line for line in view._axes.lines if line.get_label() == "Selected pass")
    assert np.all(np.diff(path.get_xdata()) > 0.0)
    np.testing.assert_allclose(path.get_ydata(), [80.0, 70.0, 60.0, 70.0, 80.0])
    assert "Playhead within selected pass" in view._sky_summary_text
    assert view._playback_marker.get_xdata() == [0.0]
    assert view._playback_marker.get_ydata() == [60.0]

    view.update(25.0)
    assert len(view._playback_marker.get_xdata()) == 0
    assert "Playhead outside selected pass" in view._sky_summary_text
    assert not view._axes.texts
    view.close()


def test_sky_plot_empty_state_messages_keep_their_precedence_and_style(
    monkeypatch,
) -> None:
    def message_for(view: GroundStationPassesView) -> str:
        figure = Figure()
        view._figure = figure
        view._axes = figure.add_subplot(111, projection="polar")
        view._refresh_rows()
        view._draw_sky_plot()
        assert len(view._axes.texts) == 1
        message = view._axes.texts[0]
        assert message.get_horizontalalignment() == "center"
        assert message.get_verticalalignment() == "center"
        assert message.get_transform() is view._axes.transAxes
        return message.get_text()

    no_station, _cache = _make_view(
        (), oem_loaded=False, limitation="Unsupported Earth-centered frame."
    )
    monkeypatch.setattr(no_station, "_selected_station", lambda: None)
    assert message_for(no_station) == "Add or select a ground station to inspect passes."

    not_loaded, _cache = _make_view(
        (), oem_loaded=False, limitation="Unsupported Earth-centered frame."
    )
    assert message_for(not_loaded) == "Load an Earth-centered OEM to view the sky plot."

    limited, _cache = _make_view(
        (), limitation="Unsupported Earth-centered frame."
    )
    assert message_for(limited) == "Unsupported Earth-centered frame."

    no_selection, _cache = _make_view(())
    assert message_for(no_selection) == "Select a pass to view its sky path."

    unavailable, _cache = _make_view((_interval(0.0, 20.0),))
    assert message_for(unavailable) == "Selected pass sky path unavailable"


def test_sky_plot_draws_at_minimum_size_without_layout_warning() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = AccessInterval(
        0.0,
        20.0,
        30.0,
        10.0,
        500.0,
        10.0,
        start_azimuth_deg=350.0,
        start_elevation_deg=10.0,
        end_azimuth_deg=10.0,
        end_elevation_deg=10.0,
    )
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0]),
        np.asarray([350.0, 0.0, 10.0]),
        np.asarray([10.0, 30.0, 10.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))
    figure = Figure(figsize=(0.64, 0.64), dpi=100)
    canvas = FigureCanvasAgg(figure)
    view._figure = figure
    view._axes = figure.add_subplot(111, projection="polar")
    view._canvas = cast(Any, canvas)
    view._refresh_rows()

    with warnings.catch_warnings(record=True) as warnings_record:
        warnings.simplefilter("always")
        view._draw_sky_plot()
        graph_panel._minimize_figure_padding(figure)
        canvas.draw()

    assert not any(
        issubclass(warning.category, UserWarning)
        and "Tight layout not applied" in str(warning.message)
        for warning in warnings_record
    )
    assert figure.subplotpars.left == 0.08
    assert figure.subplotpars.right == 0.92
    assert figure.subplotpars.bottom == 0.28
    assert figure.subplotpars.top == 0.92
    assert np.any(np.asarray(canvas.buffer_rgba())[:, :, :3] != 255)
    assert view._axes.lines
    view.close()


def test_sky_plot_breaks_at_invalid_angles_and_places_zenith_at_center() -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 0)
    interval = AccessInterval(
        0.0,
        20.0,
        90.0,
        10.0,
        200.0,
        10.0,
        start_azimuth_deg=350.0,
        start_elevation_deg=10.0,
        end_azimuth_deg=10.0,
        end_elevation_deg=10.0,
    )
    profile = LookAngleProfile(
        np.asarray([0.0, 5.0, 8.0, 10.0, 15.0, 20.0]),
        np.asarray([350.0, 355.0, np.nan, 180.0, 5.0, 10.0]),
        np.asarray([10.0, 20.0, np.nan, 90.0, 20.0, 10.0]),
    )
    view, _cache = _make_view((interval,), station=station, profiles=(profile,))
    figure = Figure()
    view._figure = figure
    view._axes = figure.add_subplot(111, projection="polar")
    view._refresh_rows()
    view._draw_sky_plot()

    paths = [
        line
        for line in view._axes.lines
        if line.get_label() in ("Selected pass", "_nolegend_")
    ]
    assert len(paths) == 2
    peak = next(line for line in view._axes.lines if line.get_label() == "Peak elevation")
    assert peak.get_ydata()[0] == 0.0


def test_pass_actions_focus_range_or_seek_only_when_invoked() -> None:
    interval = _interval(10.0, 20.0)
    focused: list[tuple[float, float]] = []
    sought: list[float] = []
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0)
    result = StationAccess(station, (interval,))
    view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=sought.append,
        on_focus_pass=lambda start, end: focused.append((start, end)),
        on_station_manager=lambda: None,
    )
    view._access_results = (result,)
    view._refresh_rows()

    assert not focused
    assert not sought
    view._focus_selected_pass()
    view._seek_to_peak()

    assert focused == [(10.0, 20.0)]
    assert sought == [15.0]


def test_empty_and_missing_station_states_are_explicit() -> None:
    cursor = cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0))
    empty = GroundStationPassesView(
        cast(Any, None),
        cursor,
        [],
        "Test object",
        oem_loaded=False,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
    )
    empty._refresh_rows()
    assert "No ground stations are configured" in empty._status_text

    station = GroundStation("available", "Available", 0.0, 0.0, 0.0)
    missing = GroundStationPassesView(
        cast(Any, None),
        cursor,
        [station],
        "Test object",
        oem_loaded=False,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        initial_station_id="removed",
    )
    missing._refresh_rows()
    assert missing.selected_station_id is None
    assert "requested station is no longer configured" in missing._status_text


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires a display-backed wx session"
)
def test_wx_pass_panel_builds_and_switches_responsive_layout(wx_app: Any) -> None:
    import wx

    frame = wx.Frame(None, size=(1500, 700))
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    interval = _interval(10.0, 30.0)
    profile = LookAngleProfile(
        np.asarray([10.0, 20.0, 30.0]),
        np.asarray([350.0, 0.0, 10.0]),
        np.asarray([10.0, 30.0, 10.0]),
    )
    view = GroundStationPassesView(
        frame,
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
    )
    view._access_results = (
        StationAccess(station, (interval,), look_angle_profiles=(profile,)),
    )
    try:
        content = view.build(cast(Any, None), cast(Any, None))
        frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
        frame.GetSizer().Add(content, 1, wx.EXPAND)
        frame.Show()
        wx_app.Yield()
        assert view._table is not None
        assert view._table.GetColumnCount() == 5
        assert view._layout_orientation == wx.HORIZONTAL
        assert view._table_panel is not None
        assert view._sky_panel is not None
        assert view._sky_panel.GetPosition().x >= (
            view._table_panel.GetPosition().x + view._table_panel.GetSize().width
        )
        assert view._table.GetClientSize().width >= sum(
            view._table.GetColumnWidth(column)
            for column in range(view._table.GetColumnCount())
        )
        assert view._canvas is not None
        view._canvas.draw()
        axes_bounds = view._axes.get_window_extent()
        assert axes_bounds.width >= view._canvas.GetSize().height * 0.55
        assert axes_bounds.height >= view._canvas.GetSize().height * 0.4
        legend = view._axes.get_legend()
        assert legend is not None
        assert legend.get_window_extent().y1 <= axes_bounds.y0

        frame.SetSize((1200, 600))
        wx_app.Yield()
        view._update_analysis_layout()
        assert view._layout_orientation == wx.HORIZONTAL
        assert view._table.GetClientSize().width >= sum(
            view._table.GetColumnWidth(column)
            for column in range(view._table.GetColumnCount())
        )
        frame.SetSize((700, 600))
        wx_app.Yield()
        view._update_analysis_layout()
        assert view._layout_orientation == wx.VERTICAL
        assert view._range_label is not None
        assert "Plot Range:" in view._range_label.GetLabel()
    finally:
        view.close()
        frame.Destroy()
        wx_app.Yield()
