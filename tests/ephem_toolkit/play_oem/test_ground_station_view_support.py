"""Tests for unified Ground Station mixin and renderer support."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.station_analysis import (
    StationAnalysisContext,
)
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import GroundStationAnalysisMixin
from ephem_toolkit.play_oem.views.ground_station import (
    ANALYSIS_PANEL_MODES,
    AzimuthProfileRenderer,
    ElevationProfileRenderer,
    GroundStationAccessRenderer,
    GroundStationView,
    RangeProfileRenderer,
    StationStatusRenderer,
)


class _GroundStationSupport(GroundStationAnalysisMixin):
    pass


def test_ground_station_analysis_mixin_synchronizes_station_selection() -> None:
    north = GroundStation("north", "North", 0.0, 0.0, 0.0)
    south = GroundStation("south", "South", 1.0, 1.0, 0.0)
    context = StationAnalysisContext()
    context.select_station("north")
    support = _GroundStationSupport()
    support._initialize_ground_station_analysis(
        (north, south),
        context,
        oem_loaded=True,
    )

    assert support.selected_station_id == "north"
    assert support._selected_ground_station() is north

    context.select_station("south")
    assert support.selected_station_id == "south"
    assert support._selected_ground_station() is south

    support._set_ground_station_stations((north,))
    assert support.selected_station_id == "north"
    support._close_ground_station_analysis()


@pytest.mark.parametrize(
    ("panel_mode", "renderer_type"),
    [
        ("station-status", StationStatusRenderer),
        ("elevation-profile", ElevationProfileRenderer),
        ("azimuth-profile", AzimuthProfileRenderer),
        ("range-profile", RangeProfileRenderer),
        ("ground-station-access", GroundStationAccessRenderer),
    ],
)
def test_ground_station_view_dispatches_each_panel_mode(
    panel_mode: str,
    renderer_type: type[Any],
) -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    context = StationAnalysisContext()
    view = GroundStationView(
        cast(Any, None),
        panel_mode,
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=context,
    )

    renderer = view._create_renderer()

    assert view.name == panel_mode
    assert view.selected_station_id == "north"
    assert isinstance(renderer, renderer_type)
    assert view.seek_on_click is (panel_mode != "station-status")
    view.close()


def test_ground_station_view_rejects_unknown_panel_mode() -> None:
    with pytest.raises(ValueError, match="unknown Ground Station panel mode"):
        GroundStationView(
            cast(Any, None),
            "unknown",
            cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
            [],
            TimeUnit.MINUTES,
            "Test object",
            oem_loaded=True,
            on_station_manager=lambda: None,
        )


def test_ground_station_analysis_modes_are_complete() -> None:
    assert ANALYSIS_PANEL_MODES == frozenset(
        (
            "station-status",
            "elevation-profile",
            "azimuth-profile",
            "range-profile",
        )
    )
