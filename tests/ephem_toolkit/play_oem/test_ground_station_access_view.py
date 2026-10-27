"""Headless Ground Station Access figure and interaction checks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from pyproj import Transformer

from ephem_toolkit.play_oem import station_access
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.ground_track import GroundTrackSource
from ephem_toolkit.play_oem.station_access import StationAccessCache
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.ground_station_access import (
    GroundStationAccessView,
)


def _access_source() -> tuple[GroundTrackSource, OemCursor]:
    transformer = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)
    x, y, z = transformer.transform(0.0, 0.0, 0.0)
    states = np.tile(
        [x + 500_000.0, y, z, 0.0, 0.0, 0.0],
        (2, 1),
    )
    source = GroundTrackSource.from_samples(
        [0.0, 120.0], states, [0, 0], "EARTH", "ITRF"
    )
    return source, OemCursor(source.timestamps_s, source.states_m)


def _figure_canvas(view: GroundStationAccessView) -> tuple[Figure, Any]:
    figure = Figure()
    canvas = FigureCanvasAgg(figure)
    view._figure = figure
    view._axes = figure.add_subplot(111)
    view._canvas = cast(Any, canvas)
    return figure, canvas


def test_elevation_graph_draws_profile_updates_cursor_and_seeks() -> None:
    source, cursor = _access_source()
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    sought: list[float] = []
    view = GroundStationAccessView(
        cast(Any, None),
        source,
        cursor,
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=sought.append,
        on_station_manager=lambda: None,
        access_cache=StationAccessCache(),
    )
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
    assert np.allclose(elevation_line.get_ydata(), 90.0)
    assert view._axes.get_ylabel() == "Elevation (degrees)"
    view._on_plot_click(
        SimpleNamespace(button=MouseButton.LEFT, inaxes=view._axes, xdata=0.5)
    )
    assert sought == [30.0]

    view.close()


def test_elevation_graph_only_plots_values_at_or_above_station_mask() -> None:
    source, cursor = _access_source()
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 10)
    view = GroundStationAccessView(
        cast(Any, None),
        source,
        cursor,
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
        access_cache=StationAccessCache(),
    )
    _figure, canvas = _figure_canvas(view)
    interval = station_access.AccessInterval(5.0, 25.0, 20.0, 15.0, 400.0, 15.0)
    profile = station_access.ElevationProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([0.0, 20.0, 20.0, 0.0]),
    )
    view._access_results = (
        station_access.StationAccess(
            station,
            (interval,),
            elevation_profiles=(profile,),
        ),
    )

    view._draw_elevation_plot()
    canvas.draw()

    elevation_line = next(
        line for line in view._axes.lines if line.get_label() == "Elevation"
    )
    assert np.allclose(elevation_line.get_ydata(), [10.0, 20.0, 20.0, 10.0])
    assert np.all(elevation_line.get_ydata() >= station.minimum_elevation_deg)
    assert view._axes.get_ylim() == (0.0, 95.0)
    view.close()


def test_timeline_x_axis_tracks_plot_range_and_empty_range() -> None:
    source, cursor = _access_source()
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    view = GroundStationAccessView(
        cast(Any, None),
        source,
        cursor,
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
        access_cache=StationAccessCache(),
    )
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


def test_empty_station_elevation_graph_has_empty_state() -> None:
    source, cursor = _access_source()
    view = GroundStationAccessView(
        cast(Any, None),
        source,
        cursor,
        [],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
        access_cache=StationAccessCache(),
    )
    _figure, canvas = _figure_canvas(view)

    view._draw_elevation_plot()
    canvas.draw()

    assert not view._axes.patches
    assert view._axes.texts[0].get_text() == "No ground stations configured"


def test_multiple_access_views_share_prepared_station_history(monkeypatch) -> None:
    source, cursor = _access_source()
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    cache = StationAccessCache()
    prepare_calls = []

    def prepare(
        source_arg,
        cursor_arg,
        station_arg,
        _position_cache,
        _bounds=None,
        _shared_positions=None,
    ):
        prepare_calls.append((source_arg, cursor_arg, station_arg))
        return station_access.StationAccess(station_arg, ())

    monkeypatch.setattr(station_access, "prepare_station_access", prepare)

    def make_view() -> GroundStationAccessView:
        return GroundStationAccessView(
            cast(Any, None),
            source,
            cursor,
            [station],
            TimeUnit.MINUTES,
            "Test object",
            oem_loaded=True,
            on_seek=lambda _time: None,
            on_station_manager=lambda: None,
            access_cache=cache,
        )

    first_view = make_view()
    second_view = make_view()

    assert len(prepare_calls) == 1
    assert first_view._access_results[0] is second_view._access_results[0]
