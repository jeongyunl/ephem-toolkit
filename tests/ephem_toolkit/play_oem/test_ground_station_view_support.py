"""Tests for unified Ground Station mixin and renderer support."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import wx
from matplotlib.figure import Figure

from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.station_access import LookAngleProfile, StationAccess
from ephem_toolkit.play_oem.station_analysis import (
    StationAnalysisContext,
)
from ephem_toolkit.play_oem.time_range import ResolvedTimeRange
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.base import (
    GroundStationAnalysisMixin,
    StoreViewContext,
)
from ephem_toolkit.play_oem.views.ground_station import (
    ANALYSIS_PANEL_MODES,
    AzimuthProfileRenderer,
    ElevationProfileRenderer,
    GroundStationView,
    RangeProfileRenderer,
)
from ephem_toolkit.play_oem.app.player_app_state import PlayerAppState
from ephem_toolkit.play_oem.app.player_view_factory import PlayerViewFactoryMixin


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
        ("elevation-profile", ElevationProfileRenderer),
        ("azimuth-profile", AzimuthProfileRenderer),
        ("range-profile", RangeProfileRenderer),
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
    assert view.seek_on_click
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
            "elevation-profile",
            "azimuth-profile",
            "range-profile",
        )
    )


def test_elevation_profile_status_reports_live_elevation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "elevation-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(0.0, 120.0),
    )
    renderer = view._create_renderer()
    assert isinstance(renderer, ElevationProfileRenderer)
    monkeypatch.setattr(
        "ephem_toolkit.play_oem.views.ground_station.store_load_status_message",
        lambda _context: None,
    )
    renderer._store_context = cast(
        StoreViewContext,
        SimpleNamespace(
            station_metrics_at=lambda _station, _time: SimpleNamespace(
                elevation_deg=34.25
            )
        ),
    )
    statuses: list[str] = []
    renderer._status_label = cast(
        wx.StaticText,
        SimpleNamespace(SetLabel=lambda text: statuses.append(text)),
    )
    renderer._time_series_status_label = renderer._status_label

    renderer.update(60.0)

    assert statuses[-1] == "North · Elevation 34.2°"
    view.close()


@pytest.mark.skipif(
    not hasattr(wx, "App") or not wx.App.IsDisplayAvailable(),
    reason="wx display is not available",
)
def test_elevation_profile_builds_floating_controls_and_minimum_canvas() -> None:
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, size=(1000, 700))
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    context = StationAnalysisContext()
    view = GroundStationView(
        frame,
        "elevation-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=context,
        initial_range=None,
    )

    try:
        panel = view.build(cast(Any, None), TimeUnit.MINUTES)
        renderer = view._renderer
        frame.Show()
        app.Yield()
        assert isinstance(renderer, ElevationProfileRenderer)
        assert renderer._panel is panel
        assert renderer._settings_panel is not None
        assert renderer._status_panel is not None
        assert renderer._status_panel.IsExpanded()
        assert renderer._status_label is not None
        assert renderer._status_label.GetName() == "Elevation Profile status text"
        assert renderer._legend_panel is not None
        assert renderer._legend_panel.GetName() == "Elevation Profile legend"
        settings_handle = renderer._settings_panel.FindWindowByName(
            "Elevation Profile settings handle label"
        )
        status_handle = renderer._status_panel.FindWindowByName(
            "Elevation Profile status handle label"
        )
        legend_handle = renderer._legend_panel.FindWindowByName(
            "Elevation Profile legend handle label"
        )
        assert settings_handle.GetLabel() == "≡"
        assert status_handle.GetLabel() == "≡"
        assert legend_handle.GetLabel() == "≡"
        assert renderer._station_choice is not None
        assert renderer._mask_filter_control is not None
        assert renderer._canvas is not None
        assert renderer._canvas.GetMinSize().width >= 64
        assert renderer._canvas.GetMinSize().height >= 64
        assert panel.GetMinSize().width >= 64
        assert panel.GetMinSize().height >= 64
    finally:
        view.close()
        frame.Destroy()


def test_elevation_profile_renderer_uses_updated_implementation() -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "elevation-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
    )

    renderer = view._create_renderer()

    assert isinstance(renderer, ElevationProfileRenderer)
    assert not hasattr(renderer, "delegate")
    assert renderer.panel_mode == "elevation-profile"
    assert renderer.seek_on_click is True
    view.close()


def test_azimuth_profile_status_reports_live_azimuth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "azimuth-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(0.0, 120.0),
    )
    renderer = view._create_renderer()
    assert isinstance(renderer, AzimuthProfileRenderer)
    monkeypatch.setattr(
        "ephem_toolkit.play_oem.views.ground_station.store_load_status_message",
        lambda _context: None,
    )
    renderer._store_context = cast(
        StoreViewContext,
        SimpleNamespace(
            station_metrics_at=lambda _station, _time: SimpleNamespace(
                azimuth_deg=123.4
            )
        ),
    )
    statuses: list[str] = []
    renderer._status_label = cast(
        wx.StaticText,
        SimpleNamespace(SetLabel=lambda text: statuses.append(text)),
    )
    renderer._time_series_status_label = renderer._status_label

    renderer.update(60.0)

    assert statuses[-1] == "North · Azimuth 123.4°"
    view.close()


def test_azimuth_profile_renderer_uses_updated_implementation() -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "azimuth-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
    )

    renderer = view._create_renderer()

    assert isinstance(renderer, AzimuthProfileRenderer)
    assert not hasattr(renderer, "delegate")
    assert renderer.panel_mode == "azimuth-profile"
    assert renderer.panel_label == "Azimuth Profile"
    assert renderer.y_label == "Azimuth (degrees)"
    assert renderer.y_limits == (0.0, 360.0)
    assert renderer.seek_on_click is True
    view.close()


def test_range_profile_status_reports_live_slant_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "range-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(0.0, 120.0),
    )
    renderer = view._create_renderer()
    assert isinstance(renderer, RangeProfileRenderer)
    monkeypatch.setattr(
        "ephem_toolkit.play_oem.views.ground_station.store_load_status_message",
        lambda _context: None,
    )
    renderer._store_context = cast(
        StoreViewContext,
        SimpleNamespace(
            station_metrics_at=lambda _station, _time: SimpleNamespace(
                slant_range_km=987.65
            )
        ),
    )
    statuses: list[str] = []
    renderer._status_label = cast(
        wx.StaticText,
        SimpleNamespace(SetLabel=lambda text: statuses.append(text)),
    )
    renderer._time_series_status_label = renderer._status_label

    renderer.update(60.0)

    assert statuses[-1] == "North · Slant range 987.6 km"
    view.close()


def test_range_profile_renderer_draws_mask_filtered_slant_ranges() -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0, 10)
    cursor = SimpleNamespace(t_start=0.0, t_end=30.0)
    view = GroundStationView(
        cast(Any, None),
        "range-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        initial_range=ResolvedTimeRange(0.0, 30.0),
    )
    renderer = view._create_renderer()
    assert isinstance(renderer, RangeProfileRenderer)
    renderer._figure = Figure()
    renderer._axes = renderer._figure.add_subplot(111)
    renderer._time_range = ResolvedTimeRange(0.0, 30.0)
    profile = LookAngleProfile(
        np.asarray([0.0, 10.0, 20.0, 30.0]),
        np.asarray([0.0, 90.0, 180.0, 270.0]),
        np.asarray([9.0, 10.0, 5.0, 20.0]),
        np.asarray([100.0, 90.0, 80.0, 70.0]),
    )
    renderer._draw_profile(
        StationAccess(station, (), look_angle_profiles=(profile,)),
        station,
    )

    line = renderer._axes.lines[-1]
    values = line.get_ydata()
    assert np.isnan(values).any()
    assert np.isfinite(values).any()
    finite_values = values[np.isfinite(values)]
    assert finite_values.min() >= 70.0
    assert finite_values.max() <= 100.0
    view.close()


def test_range_profile_renderer_uses_updated_implementation() -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "range-profile",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
    )

    renderer = view._create_renderer()

    assert isinstance(renderer, RangeProfileRenderer)
    assert not hasattr(renderer, "delegate")
    assert renderer.panel_mode == "range-profile"
    assert renderer.panel_label == "Range Profile"
    assert renderer.y_label == "Slant range (km)"
    assert renderer.y_limits is None
    assert renderer.status_metric == "Slant range"
    assert renderer.seek_on_click is True
    view.close()


def test_elevation_factory_uses_ground_station_view() -> None:
    context = StationAnalysisContext()
    captured: dict[str, object] = {}

    class Factory(PlayerViewFactoryMixin):
        cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
        time_unit = TimeUnit.MINUTES
        object_name = "Test object"
        _ground_stations = ()
        _oem_loaded = True
        _display_time_zone = "UTC"
        _station_analysis_contexts = {"middle": context}
        workspace = SimpleNamespace(select_ground_stations=lambda: None)

        def _open_view(self, name, creator, **kwargs):
            captured["name"] = name
            captured["creator"] = creator
            captured["kwargs"] = kwargs

        def _resolved_plot_range(self):
            return None

    factory = Factory()
    cast(PlayerAppState, factory).open_elevation_profile_view(
        panel_id="elevation", stack="middle", force_replace=False
    )

    creator = captured["creator"]
    assert callable(creator)
    view = creator(cast(Any, None))
    assert isinstance(view, GroundStationView)
    assert view.name == "elevation-profile"
    assert isinstance(view._create_renderer(), ElevationProfileRenderer)
    view.close()


@pytest.mark.skipif(
    not hasattr(wx, "App") or not wx.App.IsDisplayAvailable(),
    reason="wx display is not available",
)
def test_azimuth_profile_builds_floating_controls_and_minimum_canvas() -> None:
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, size=(1000, 700))
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    context = StationAnalysisContext()
    view = GroundStationView(
        frame,
        "azimuth-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=context,
        initial_range=None,
    )

    try:
        panel = view.build(cast(Any, None), TimeUnit.MINUTES)
        renderer = view._renderer
        frame.Show()
        app.Yield()
        assert isinstance(renderer, AzimuthProfileRenderer)
        assert renderer._panel is panel
        assert renderer._settings_panel is not None
        assert renderer._status_panel is not None
        assert renderer._status_panel.IsExpanded()
        assert renderer._status_label is not None
        assert renderer._status_label.GetName() == "Azimuth Profile status text"
        assert renderer._legend_panel is not None
        assert renderer._legend_panel.GetName() == "Azimuth Profile legend"
        settings_handle = renderer._settings_panel.FindWindowByName(
            "Azimuth Profile settings handle label"
        )
        status_handle = renderer._status_panel.FindWindowByName(
            "Azimuth Profile status handle label"
        )
        legend_handle = renderer._legend_panel.FindWindowByName(
            "Azimuth Profile legend handle label"
        )
        assert settings_handle.GetLabel() == "≡"
        assert status_handle.GetLabel() == "≡"
        assert legend_handle.GetLabel() == "≡"
        assert renderer._station_choice is not None
        assert renderer._mask_filter_control is not None
        assert renderer._canvas is not None
        assert renderer._canvas.GetMinSize().width >= 64
        assert renderer._canvas.GetMinSize().height >= 64
        assert panel.GetMinSize().width >= 64
        assert panel.GetMinSize().height >= 64
    finally:
        view.close()
        frame.Destroy()


def test_azimuth_factory_uses_ground_station_view() -> None:
    context = StationAnalysisContext()
    captured: dict[str, object] = {}

    class Factory(PlayerViewFactoryMixin):
        cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
        time_unit = TimeUnit.MINUTES
        object_name = "Test object"
        _ground_stations = ()
        _oem_loaded = True
        _display_time_zone = "UTC"
        _station_analysis_contexts = {"middle": context}
        workspace = SimpleNamespace(select_ground_stations=lambda: None)

        def _open_view(self, name, creator, **kwargs):
            captured["name"] = name
            captured["creator"] = creator
            captured["kwargs"] = kwargs

        def _resolved_plot_range(self):
            return None

    factory = Factory()
    cast(PlayerAppState, factory).open_azimuth_profile_view(
        panel_id="azimuth", stack="middle", force_replace=False
    )

    creator = captured["creator"]
    assert callable(creator)
    view = creator(cast(Any, None))
    assert isinstance(view, GroundStationView)
    assert view.name == "azimuth-profile"
    assert isinstance(view._create_renderer(), AzimuthProfileRenderer)
    view.close()


@pytest.mark.skipif(
    not hasattr(wx, "App") or not wx.App.IsDisplayAvailable(),
    reason="wx display is not available",
)
def test_range_profile_builds_floating_controls_and_minimum_canvas() -> None:
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, size=(1000, 700))
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    context = StationAnalysisContext()
    view = GroundStationView(
        frame,
        "range-profile",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=context,
        initial_range=None,
    )

    try:
        panel = view.build(cast(Any, None), TimeUnit.MINUTES)
        renderer = view._renderer
        frame.Show()
        app.Yield()
        assert isinstance(renderer, RangeProfileRenderer)
        assert renderer._panel is panel
        assert renderer._settings_panel is not None
        assert renderer._status_panel is not None
        assert renderer._status_panel.IsExpanded()
        assert renderer._status_label is not None
        assert renderer._status_label.GetName() == "Range Profile status text"
        assert renderer._legend_panel is not None
        assert renderer._legend_panel.GetName() == "Range Profile legend"
        settings_handle = renderer._settings_panel.FindWindowByName(
            "Range Profile settings handle label"
        )
        status_handle = renderer._status_panel.FindWindowByName(
            "Range Profile status handle label"
        )
        legend_handle = renderer._legend_panel.FindWindowByName(
            "Range Profile legend handle label"
        )
        assert settings_handle.GetLabel() == "≡"
        assert status_handle.GetLabel() == "≡"
        assert legend_handle.GetLabel() == "≡"
        assert renderer._station_choice is not None
        assert renderer._mask_filter_control is not None
        assert renderer._canvas is not None
        assert renderer._canvas.GetMinSize().width >= 64
        assert renderer._canvas.GetMinSize().height >= 64
        assert panel.GetMinSize().width >= 64
        assert panel.GetMinSize().height >= 64
    finally:
        view.close()
        frame.Destroy()


def test_range_factory_uses_ground_station_view() -> None:
    context = StationAnalysisContext()
    captured: dict[str, object] = {}

    class Factory(PlayerViewFactoryMixin):
        cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
        time_unit = TimeUnit.MINUTES
        object_name = "Test object"
        _ground_stations = ()
        _oem_loaded = True
        _display_time_zone = "UTC"
        _station_analysis_contexts = {"middle": context}
        workspace = SimpleNamespace(select_ground_stations=lambda: None)

        def _open_view(self, name, creator, **kwargs):
            captured["name"] = name
            captured["creator"] = creator
            captured["kwargs"] = kwargs

        def _resolved_plot_range(self):
            return None

    factory = Factory()
    cast(PlayerAppState, factory).open_range_profile_view(
        panel_id="range", stack="middle", force_replace=False
    )

    creator = captured["creator"]
    assert callable(creator)
    view = creator(cast(Any, None))
    assert isinstance(view, GroundStationView)
    assert view.name == "range-profile"
    assert isinstance(view._create_renderer(), RangeProfileRenderer)
    view.close()
