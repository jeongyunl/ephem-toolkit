"""Headless Ground Station Access figure and interaction checks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.station_access import (
    AccessInterval,
    ElevationProfile,
    StationAccess,
)
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.ground_station_access import (
    GroundStationAccessView,
)
from tests.ephem_toolkit.play_oem.cursor_helpers import make_store_cursor


def _access_view(stations: list[GroundStation]) -> GroundStationAccessView:
    _, cursor = make_store_cursor([0.0, 120.0], np.zeros((2, 6)))
    return GroundStationAccessView(
        cast(Any, None),
        cursor,
        stations,
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
    )


def _figure_canvas(view: GroundStationAccessView) -> tuple[Figure, Any]:
    figure = Figure()
    canvas = FigureCanvasAgg(figure)
    view._figure = figure
    view._axes = figure.add_subplot(111)
    view._canvas = cast(Any, canvas)
    return figure, canvas


def _profile_access(station: GroundStation) -> StationAccess:
    interval = AccessInterval(5.0, 25.0, 20.0, 15.0, 400.0, 15.0)
    profile = ElevationProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([0.0, 20.0, 20.0, 0.0]),
    )
    return StationAccess(station, (interval,), elevation_profiles=(profile,))


def _plotted_elevation_lines(view: GroundStationAccessView) -> list[Any]:
    return [
        line
        for line in view._axes.lines
        if line.get_label() in ("Elevation", "_nolegend_")
    ]


def _pass_summary_view(
    station: GroundStation,
    intervals: tuple[AccessInterval, ...] = (),
    *,
    current_time_s: float = 0.0,
    limitation: str | None = None,
) -> GroundStationAccessView:
    view = _access_view([station])
    view._current_time_s = current_time_s
    view._access_results = (
        StationAccess(station, intervals, limitation=limitation),
    )
    return view


def test_elevation_graph_draws_profile_updates_cursor_and_seeks() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    view = _access_view([station])
    sought: list[float] = []
    view._on_seek = sought.append
    view._access_results = (_profile_access(station),)
    _figure, canvas = _figure_canvas(view)

    view._draw_elevation_plot()
    view.update(60.0)
    canvas.draw()

    assert len(view._axes.patches) == 1
    cursor_line = next(
        line for line in view._axes.lines if line.get_gid() == "playback-cursor"
    )
    assert cursor_line.get_xdata()[0] == 1.0
    elevation_line = next(
        line for line in view._axes.lines if line.get_label() == "Elevation"
    )
    assert np.allclose(elevation_line.get_ydata(), [0.0, 20.0, 20.0, 0.0])
    assert view._axes.get_ylabel() == "Elevation (degrees)"
    view._on_plot_click(
        SimpleNamespace(button=MouseButton.LEFT, inaxes=view._axes, xdata=0.5)
    )
    assert sought == [30.0]
    view.close()


def test_elevation_graph_only_plots_values_at_or_above_station_mask() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 10)
    view = _access_view([station])
    view._access_results = (_profile_access(station),)
    _figure, canvas = _figure_canvas(view)

    view._draw_elevation_plot()
    canvas.draw()

    elevation_line = next(
        line for line in view._axes.lines if line.get_label() == "Elevation"
    )
    assert np.allclose(elevation_line.get_ydata(), [10.0, 20.0, 20.0, 10.0])
    assert np.all(elevation_line.get_ydata() >= station.minimum_elevation_deg)
    assert view._axes.get_ylim() == (0.0, 95.0)
    view.close()


def test_elevation_graph_does_not_bridge_nonfinite_profile_samples() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    interval = AccessInterval(0.0, 80.0, 20.0, 0.0, 500.0, 0.0)
    profile = ElevationProfile(
        np.asarray([0.0, 10.0, np.nan, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]),
        np.asarray([20.0, 20.0, 20.0, 20.0, 20.0, np.nan, 20.0, 20.0, 20.0]),
    )
    view = _access_view([station])
    view._access_results = (
        StationAccess(station, (interval,), elevation_profiles=(profile,)),
    )
    _figure, canvas = _figure_canvas(view)

    view._draw_elevation_plot()
    canvas.draw()

    lines = _plotted_elevation_lines(view)
    assert len(lines) == 3
    expected_x = ([0.0, 1.0 / 6.0], [0.5, 2.0 / 3.0], [1.0, 7.0 / 6.0, 4.0 / 3.0])
    expected_y = ([0.0, 20.0], [20.0, 20.0], [20.0, 20.0, 0.0])
    for line, x_values, y_values in zip(lines, expected_x, expected_y):
        assert np.allclose(line.get_xdata(), x_values)
        assert np.allclose(line.get_ydata(), y_values)
    view.close()


def test_elevation_graph_splits_visible_runs_below_station_mask() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 10)
    interval = AccessInterval(0.0, 40.0, 20.0, 10.0, 500.0, 10.0)
    profile = ElevationProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0, 40.0]),
        np.asarray([20.0, 20.0, 5.0, 20.0, 20.0]),
    )
    view = _access_view([station])
    view._access_results = (
        StationAccess(station, (interval,), elevation_profiles=(profile,)),
    )
    _figure, canvas = _figure_canvas(view)

    view._draw_elevation_plot()
    canvas.draw()

    lines = _plotted_elevation_lines(view)
    assert len(lines) == 2
    assert np.allclose(lines[0].get_xdata(), [0.0, 1.0 / 6.0])
    assert np.allclose(lines[0].get_ydata(), [10.0, 20.0])
    assert np.allclose(lines[1].get_xdata(), [0.5, 2.0 / 3.0])
    assert np.allclose(lines[1].get_ydata(), [20.0, 10.0])
    view.close()


def test_interval_annotation_precedence_and_legend_deduplication() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 10)
    intervals = (
        AccessInterval(1.0, 3.0, 20.0, 2.0, 2.0, 10.0),
        AccessInterval(5.0, 7.0, 20.0, 6.0, 2.0, 10.0, clipped_at_start=True),
        AccessInterval(
            9.0,
            11.0,
            20.0,
            10.0,
            2.0,
            10.0,
            limited_by_gap_at_start=True,
        ),
        AccessInterval(
            13.0,
            15.0,
            20.0,
            14.0,
            2.0,
            10.0,
            clipped_at_end=True,
            limited_by_gap_at_start=True,
        ),
        AccessInterval(
            17.0,
            19.0,
            20.0,
            18.0,
            2.0,
            10.0,
            limited_by_gap_at_end=True,
        ),
    )
    profile = ElevationProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([20.0, 20.0, 20.0, 20.0]),
    )
    view = _access_view([station])
    view._access_results = (
        StationAccess(station, intervals, elevation_profiles=(profile,)),
    )
    _figure_canvas(view)

    view._draw_elevation_plot()

    assert len(view._axes.patches) == 5
    assert [patch.get_hatch() for patch in view._axes.patches] == [
        None,
        "//",
        "xx",
        "xx",
        "xx",
    ]
    assert [patch.get_label() for patch in view._axes.patches] == [
        "Access interval",
        "Coverage-limited access",
        "Gap-limited access",
        "_nolegend_",
        "_nolegend_",
    ]
    view.close()


def test_timeline_x_axis_tracks_plot_range_and_empty_range() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    view = _access_view([station])
    view._access_results = (_profile_access(station),)
    _figure, canvas = _figure_canvas(view)
    view._draw_elevation_plot()

    prepared_result = view._access_results[0]
    view.set_time_range(ResolvedTimeRange(30.0, 90.0), (0.0, 120.0))
    assert np.allclose(view._axes.get_xlim(), (0.5, 1.5))
    assert view._access_results[0] is prepared_result

    view.update(100.0)
    cursor_line = next(
        line for line in view._axes.lines if line.get_gid() == "playback-cursor"
    )
    assert not cursor_line.get_visible()
    assert np.allclose(view._axes.get_xlim(), (0.5, 1.5))

    view.set_time_range(None, (0.0, 120.0))
    assert np.allclose(view._axes.get_xlim(), (0.0, 2.0))
    assert not view._axes.patches
    assert any(
        text.get_text().strip() == "No data in Plot Range"
        for text in view._axes.texts
    )

    view.set_time_range(ResolvedTimeRange(0.0, 120.0), (0.0, 120.0))
    assert len(view._axes.patches) == 1
    canvas.draw()
    view.close()


def test_elevation_plot_status_messages_preserve_precedence_and_styling() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    no_stations = _access_view([])
    no_stations._oem_loaded = False
    unloaded_oem = _access_view([station])
    unloaded_oem._oem_loaded = False
    no_range = _access_view([station])
    no_range._selected_station_id = None
    no_range._time_range_applied = True
    no_selection = _access_view([station])
    no_selection._selected_station_id = None
    unavailable_profile = _access_view([station])
    limited_profile = _access_view([station])
    limited_profile._access_results = (
        StationAccess(station, (), limitation="Unsupported Earth-centered frame."),
    )

    cases = (
        (no_stations, "No ground stations configured", False),
        (
            unloaded_oem,
            "Load an Earth-centered OEM to view elevation",
            False,
        ),
        (no_range, "No data in Plot Range", True),
        (
            no_selection,
            "Select a ground station to view elevation",
            True,
        ),
        (
            unavailable_profile,
            "Elevation profile unavailable",
            True,
        ),
        (
            limited_profile,
            "Unsupported Earth-centered frame.",
            True,
        ),
    )

    for view, expected_message, axes_on in cases:
        _figure, canvas = _figure_canvas(view)
        view._draw_elevation_plot()
        canvas.draw()

        assert not view._axes.patches
        assert len(view._axes.texts) == 1
        text = view._axes.texts[0]
        assert text.get_text() == expected_message
        assert text.get_position() == (0.5, 0.5)
        assert text.get_ha() == "center"
        assert text.get_va() == "center"
        assert text.get_transform() is view._axes.transAxes
        assert view._axes.axison is axes_on
        view.close()


def test_pass_summary_handles_missing_results_limitations_and_no_intervals() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    view = _access_view([station])

    assert view._pass_summary(station) == ""
    view.close()

    limitation = "Unsupported Earth-centered frame."
    interval = AccessInterval(10.0, 20.0, 45.0, 15.0, 500.0, 18.0)
    view = _pass_summary_view(
        station,
        (interval,),
        limitation=limitation,
    )
    assert view._pass_summary(station) == limitation
    view.close()

    view = _pass_summary_view(station)
    assert view._pass_summary(station) == (
        "Previous pass: none in OEM coverage\n"
        "Next pass: none in OEM coverage"
    )
    view.close()


def test_pass_summary_selects_latest_previous_and_first_upcoming() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    earlier = AccessInterval(5.0, 15.0, 50.0, 10.0, 600.0, 8.0)
    previous = AccessInterval(
        20.0,
        30.0,
        66.5,
        26.0,
        450.2,
        24.0,
        clipped_at_start=True,
        clipped_at_end=True,
    )
    upcoming = AccessInterval(
        70.0,
        100.0,
        72.5,
        88.0,
        321.6,
        75.0,
        clipped_at_start=True,
        clipped_at_end=True,
    )
    later = AccessInterval(110.0, 130.0, 60.0, 120.0, 520.0, 115.0)
    view = _pass_summary_view(
        station,
        (earlier, previous, upcoming, later),
        current_time_s=60.0,
    )

    expected_previous = (
        f"Previous/active: {view._time_label(20.0)} – {view._time_label(30.0)} "
        f"(0.2 min, peak 66.5° at {view._time_label(26.0)}, "
        "minimum range 450.2 km)"
        " · in progress at coverage start · continues beyond coverage"
    )
    expected_next = (
        f"Next: {view._time_label(70.0)} – {view._time_label(100.0)} "
        f"(0.5 min, peak 72.5° at {view._time_label(88.0)}, "
        "minimum range 321.6 km)"
        " · in progress at coverage start · continues beyond coverage"
    )
    assert view._pass_summary(station) == f"{expected_previous}\n{expected_next}"
    view.close()


def test_pass_summary_treats_both_active_interval_endpoints_as_inclusive() -> None:
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    previous = AccessInterval(10.0, 20.0, 40.0, 15.0, 500.0, 18.0)
    active_intervals = (
        AccessInterval(60.0, 90.0, 75.0, 70.0, 300.0, 65.0),
        AccessInterval(30.0, 60.0, 65.0, 50.0, 350.0, 45.0),
    )

    for active in active_intervals:
        view = _pass_summary_view(
            station,
            (previous, active),
            current_time_s=60.0,
        )
        expected_active = (
            f"Previous/active: {view._time_label(active.start_s)} – "
            f"{view._time_label(active.end_s)} "
            f"({(active.end_s - active.start_s) / 60.0:.1f} min, "
            f"peak {active.peak_elevation_deg:.1f}° at "
            f"{view._time_label(active.peak_time_s)}, "
            f"minimum range {active.minimum_range_km:.1f} km)"
        )
        assert view._pass_summary(station) == (
            f"{expected_active}\nNext pass: none in OEM coverage"
        )
        view.close()
