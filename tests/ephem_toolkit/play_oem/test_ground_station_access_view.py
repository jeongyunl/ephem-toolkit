"""Headless Ground Station Access figure and interaction checks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from pyproj import Transformer

from ephem_toolkit.play_oem import station_access
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.ground_track import GroundTrackSource
from ephem_toolkit.play_oem.station_access import StationAccessCache
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


def test_access_timeline_draws_pass_updates_cursor_and_seeks() -> None:
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

    view._draw_timeline()
    view.update(60.0)
    canvas.draw()

    assert len(view._axes.patches) == 1
    cursor_line = next(
        line for line in view._axes.lines if line.get_gid() == "playback-cursor"
    )
    assert cursor_line.get_xdata()[0] == 1.0
    view._on_timeline_click(
        SimpleNamespace(inaxes=view._axes, xdata=0.5)
    )
    assert sought == [30.0]

    view.close()


def test_empty_station_timeline_has_empty_state_and_no_access_rows() -> None:
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

    view._draw_timeline()
    canvas.draw()

    assert not view._axes.patches
    assert view._axes.texts[0].get_text() == "No ground stations configured"


def test_multiple_access_views_share_prepared_station_history(monkeypatch) -> None:
    source, cursor = _access_source()
    station = GroundStation("station", "Site", 0.0, 0.0, 0.0, 0)
    cache = StationAccessCache()
    prepare_calls = []

    def prepare(source_arg, cursor_arg, station_arg, _position_cache):
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
