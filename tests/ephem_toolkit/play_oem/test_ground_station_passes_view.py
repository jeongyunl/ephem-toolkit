"""Plot-range filtering and sky rendering for Ground Station Passes."""

from __future__ import annotations

import gc
import os
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import pytest

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem import station_access
from ephem_toolkit.play_oem.station_access import (
    AccessInterval,
    LookAngleProfile,
    StationAccessCache,
    StationAccess,
)
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.ground_station_access import (
    GroundStationAccessView,
)
from ephem_toolkit.play_oem.views.ground_station_passes import (
    GroundStationPassesView,
    _utc_label,
)


@pytest.fixture(scope="module")
def wx_app() -> Iterator[Any]:
    import wx

    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx cannot connect to the available display")
    app = wx.App.Get() or wx.App(False)
    yield app
    gc.collect()


class _AccessCache:
    def __init__(self, result: StationAccess) -> None:
        self.result = result
        self.prepare_calls = 0

    def prepare(self, *_args: Any) -> StationAccess:
        self.prepare_calls += 1
        return self.result


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


def _make_view(
    intervals: tuple[AccessInterval, ...],
    *,
    station: GroundStation | None = None,
    profiles: tuple[LookAngleProfile, ...] = (),
    limitation: str | None = None,
    oem_loaded: bool = True,
) -> tuple[GroundStationPassesView, _AccessCache]:
    station = station or GroundStation("site", "Site", 0.0, 0.0, 0.0, 10)
    result = StationAccess(station, intervals, limitation, look_angle_profiles=profiles)
    cache = _AccessCache(result)
    view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, object()),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=oem_loaded,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        access_cache=cast(Any, cache),
    )
    return view, cache


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
        f"Plot Range: {_utc_label(19.0)} – {_utc_label(41.0)} UTC"
    )
    assert view._access_results[0] is prepared
    assert cache.prepare_calls == 1


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
    assert cache.prepare_calls == 1


def test_station_updates_retain_pass_selection_for_a_station_that_remains() -> None:
    intervals = (_interval(0.0, 10.0), _interval(20.0, 30.0))
    view, cache = _make_view(intervals)
    station = view._stations[0]
    view._selected_interval_key = (20.0, 30.0)

    view.set_stations([station])

    assert view.selected_station_id == station.station_id
    assert view._selected_interval_key == (20.0, 30.0)
    assert cache.prepare_calls == 2


def test_no_overlap_no_access_and_unsupported_states_are_distinct() -> None:
    view, _cache = _make_view((_interval(10.0, 20.0),))
    view.set_time_range(ResolvedTimeRange(70.0, 80.0), (0.0, 100.0))
    assert not view._visible_intervals
    assert view._status_text == (
        "No access intervals overlap the current Plot Range. "
        "Widen the shared Plot Range to see more passes."
    )

    no_access, _cache = _make_view(())
    no_access.set_time_range(ResolvedTimeRange(70.0, 80.0), (0.0, 100.0))
    assert "No access intervals in OEM coverage" in no_access._status_text

    unsupported, _cache = _make_view(
        (), limitation="Unsupported Earth-centered frame."
    )
    unsupported.set_time_range(ResolvedTimeRange(70.0, 80.0), (0.0, 100.0))
    assert unsupported._status_text == "Unsupported Earth-centered frame."

    no_effective_range, _cache = _make_view((_interval(10.0, 20.0),))
    no_effective_range.set_time_range(None, (0.0, 100.0))
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
    assert view._row_values(intervals[0])[2] == ""
    assert view._row_values(intervals[0])[5] == "Starts at OEM boundary"
    assert view._row_values(intervals[1])[2] == ""
    assert view._row_values(intervals[1])[5] == "Gap-limited end"
    assert view._row_values(_interval(10.0, 20.0))[2] == "0.2 min"


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
    cache = _AccessCache(result)
    view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, object()),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=sought.append,
        on_focus_pass=lambda start, end: focused.append((start, end)),
        on_station_manager=lambda: None,
        access_cache=cast(Any, cache),
    )
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
        None,
        cursor,
        [],
        "Test object",
        oem_loaded=False,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        access_cache=cast(Any, _AccessCache(StationAccess(
            GroundStation("unused", "Unused", 0.0, 0.0, 0.0), ()
        ))),
    )
    empty._refresh_rows()
    assert "No ground stations are configured" in empty._status_text

    station = GroundStation("available", "Available", 0.0, 0.0, 0.0)
    missing = GroundStationPassesView(
        cast(Any, None),
        None,
        cursor,
        [station],
        "Test object",
        oem_loaded=False,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        access_cache=cast(Any, _AccessCache(StationAccess(station, ()))),
        initial_station_id="removed",
    )
    missing._refresh_rows()
    assert missing.selected_station_id is None
    assert "requested station is no longer configured" in missing._status_text


def test_access_and_pass_panels_share_prepared_station_history(monkeypatch) -> None:
    station = GroundStation("site", "Site", 0.0, 0.0, 0.0)
    source = object()
    cursor = SimpleNamespace(t_start=0.0, t_end=100.0)
    cache = StationAccessCache()
    prepared = StationAccess(station, ())
    calls: list[tuple[Any, Any, GroundStation]] = []

    def prepare(source_arg, cursor_arg, station_arg, _position_cache):
        calls.append((source_arg, cursor_arg, station_arg))
        return prepared

    monkeypatch.setattr(station_access, "prepare_station_access", prepare)
    access_view = GroundStationAccessView(
        cast(Any, None),
        cast(Any, source),
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
        access_cache=cache,
    )
    passes_view = GroundStationPassesView(
        cast(Any, None),
        cast(Any, source),
        cast(Any, cursor),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        access_cache=cache,
    )

    assert len(calls) == 1
    assert access_view._access_results[0] is prepared
    assert passes_view._access_results[0] is prepared


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
        cast(Any, object()),
        cast(Any, SimpleNamespace(t_start=0.0, t_end=100.0)),
        [station],
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_focus_pass=lambda _start, _end: None,
        on_station_manager=lambda: None,
        access_cache=cast(
            Any,
            _AccessCache(
                StationAccess(
                    station, (interval,), look_angle_profiles=(profile,)
                )
            ),
        ),
    )
    try:
        content = view.build(cast(Any, None), cast(Any, None))
        frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
        frame.GetSizer().Add(content, 1, wx.EXPAND)
        frame.Show()
        wx_app.Yield()
        assert view._table is not None
        assert view._table.GetColumnCount() == 6
        assert view._layout_orientation == wx.VERTICAL
        assert view._table_panel is not None
        assert view._sky_panel is not None
        assert view._sky_panel.GetPosition().y >= (
            view._table_panel.GetPosition().y + view._table_panel.GetSize().height
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
        assert view._layout_orientation == wx.VERTICAL
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
