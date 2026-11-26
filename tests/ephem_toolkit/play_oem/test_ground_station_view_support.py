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
    renderer._store_context = SimpleNamespace(
        station_metrics_at=lambda _station, _time: SimpleNamespace(
            elevation_deg=34.25
        )
    )
    statuses: list[str] = []
    renderer._status_label = SimpleNamespace(
        SetLabel=lambda text: statuses.append(text)
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
    renderer._store_context = SimpleNamespace(
        station_metrics_at=lambda _station, _time: SimpleNamespace(
            azimuth_deg=123.4
        )
    )
    statuses: list[str] = []
    renderer._status_label = SimpleNamespace(
        SetLabel=lambda text: statuses.append(text)
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
    renderer._store_context = SimpleNamespace(
        station_metrics_at=lambda _station, _time: SimpleNamespace(
            slant_range_km=987.65
        )
    )
    statuses: list[str] = []
    renderer._status_label = SimpleNamespace(
        SetLabel=lambda text: statuses.append(text)
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
    factory._open_station_analysis_panel(
        "elevation-profile",
        "elevation-profile",
        "elevation",
        "middle",
        False,
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
    factory._open_station_analysis_panel(
        "azimuth-profile",
        "azimuth-profile",
        "azimuth",
        "middle",
        False,
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
    factory._open_station_analysis_panel(
        "range-profile",
        "range-profile",
        "range",
        "middle",
        False,
    )

    creator = captured["creator"]
    assert callable(creator)
    view = creator(cast(Any, None))
    assert isinstance(view, GroundStationView)
    assert view.name == "range-profile"
    assert isinstance(view._create_renderer(), RangeProfileRenderer)
    view.close()


def test_station_status_renderer_uses_updated_implementation() -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 10)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "station-status",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
    )

    renderer = view._create_renderer()

    assert isinstance(renderer, StationStatusRenderer)
    assert not hasattr(renderer, "delegate")
    assert renderer.panel_mode == "station-status"
    assert renderer.seek_on_click is False
    assert view.seek_on_click is False
    view.close()


def test_station_status_updates_current_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 10)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "station-status",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
    )
    renderer = view._create_renderer()
    assert isinstance(renderer, StationStatusRenderer)
    monkeypatch.setattr(
        "ephem_toolkit.play_oem.views.ground_station.store_load_status_message",
        lambda _context: None,
    )
    renderer._store_context = SimpleNamespace(
        station_metrics_at=lambda _station, _time: SimpleNamespace(
            access=True,
            azimuth_deg=123.4,
            elevation_deg=45.7,
            slant_range_km=987.65,
        )
    )
    metrics: list[str] = []
    statuses: list[str] = []
    renderer._metrics_label = SimpleNamespace(
        SetLabel=lambda text: metrics.append(text)
    )
    renderer._status_label = SimpleNamespace(
        SetLabel=lambda text: statuses.append(text)
    )
    renderer._time_series_status_label = renderer._status_label

    renderer.update(60.0)

    expected = (
        "North · mask 10°\n"
        "Access · Azimuth 123.4° · Elevation 45.7° · Slant range 987.6 km"
    )
    assert metrics[-1] == expected
    assert statuses[-1] == expected
    view.close()


@pytest.mark.skipif(
    not hasattr(wx, "App") or not wx.App.IsDisplayAvailable(),
    reason="wx display is not available",
)
def test_station_status_builds_floating_controls_and_minimum_panel() -> None:
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, size=(1000, 700))
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    context = StationAnalysisContext()
    view = GroundStationView(
        frame,
        "station-status",
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
        assert isinstance(renderer, StationStatusRenderer)
        assert renderer._panel is panel
        assert renderer._settings_panel is not None
        assert renderer._status_panel is not None
        assert renderer._status_panel.IsExpanded()
        assert renderer._status_label is not None
        assert renderer._status_label.GetName() == "Station Status status text"
        assert renderer._metrics_label is not None
        assert renderer._metrics_label.GetName() == "Current station metrics"
        settings_handle = renderer._settings_panel.FindWindowByName(
            "Station Status settings handle label"
        )
        status_handle = renderer._status_panel.FindWindowByName(
            "Station Status status handle label"
        )
        assert settings_handle.GetLabel() == "≡"
        assert status_handle.GetLabel() == "≡"
        assert renderer._station_choice is not None
        assert panel.GetMinSize().width >= 64
        assert panel.GetMinSize().height >= 64
    finally:
        view.close()
        frame.Destroy()


def test_station_status_factory_uses_ground_station_view() -> None:
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
    factory._open_station_analysis_panel(
        "station-status",
        "station-status",
        "station",
        "middle",
        False,
    )

    creator = captured["creator"]
    assert callable(creator)
    view = creator(cast(Any, None))
    assert isinstance(view, GroundStationView)
    assert view.name == "station-status"
    assert isinstance(view._create_renderer(), StationStatusRenderer)
    view.close()


def test_ground_station_access_renderer_uses_updated_implementation() -> None:
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    cursor = SimpleNamespace(t_start=0.0, t_end=120.0)
    view = GroundStationView(
        cast(Any, None),
        "ground-station-access",
        cast(Any, cursor),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
        selection_context=StationAnalysisContext(),
        limit_to_range=True,
    )

    renderer = view._create_renderer()

    assert isinstance(renderer, GroundStationAccessRenderer)
    assert not hasattr(renderer, "delegate")
    assert renderer.panel_mode == "ground-station-access"
    assert renderer.seek_on_click is True
    assert view.seek_on_click is True
    view.close()


@pytest.mark.skipif(
    not hasattr(wx, "App") or not wx.App.IsDisplayAvailable(),
    reason="wx display is not available",
)
def test_ground_station_access_builds_floating_controls_and_minimum_canvas() -> None:
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, size=(1000, 700))
    station = GroundStation("north", "North", 0.0, 0.0, 0.0)
    context = StationAnalysisContext()
    view = GroundStationView(
        frame,
        "ground-station-access",
        cast(Any, SimpleNamespace(t_start=0.0, t_end=120.0)),
        [station],
        TimeUnit.MINUTES,
        "Test object",
        oem_loaded=True,
        on_seek=lambda _time: None,
        on_station_manager=lambda: None,
        selection_context=context,
        limit_to_range=True,
        initial_range=None,
    )

    try:
        panel = view.build(cast(Any, None), TimeUnit.MINUTES)
        renderer = view._renderer
        frame.Show()
        app.Yield()
        assert isinstance(renderer, GroundStationAccessRenderer)
        assert renderer._panel is panel
        assert renderer._settings_panel is not None
        assert renderer._status_panel is not None
        assert renderer._status_panel.IsExpanded()
        assert renderer._status_label is not None
        assert renderer._status_label.GetName() == "Ground station access status"
        assert renderer._legend_panel is not None
        assert renderer._legend_panel.GetName() == "Ground Station Access legend"
        settings_handle = renderer._settings_panel.FindWindowByName(
            "Ground Station Access settings handle label"
        )
        status_handle = renderer._status_panel.FindWindowByName(
            "Ground Station Access status handle label"
        )
        legend_handle = renderer._legend_panel.FindWindowByName(
            "Ground Station Access legend handle label"
        )
        assert settings_handle.GetLabel() == "≡"
        assert status_handle.GetLabel() == "≡"
        assert legend_handle.GetLabel() == "≡"
        assert renderer._station_choice is not None
        assert renderer._metrics_label is not None
        assert renderer._pass_label is not None
        assert renderer._canvas is not None
        assert renderer._canvas.GetMinSize().width >= 64
        assert renderer._canvas.GetMinSize().height >= 64
        assert panel.GetMinSize().width >= 64
        assert panel.GetMinSize().height >= 64
    finally:
        view.close()
        frame.Destroy()


def test_ground_station_access_factory_uses_ground_station_view() -> None:
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

        def _seek_from_ground_station_timeline(self, _time):
            pass

        def _open_view(self, name, creator, **kwargs):
            captured["name"] = name
            captured["creator"] = creator
            captured["kwargs"] = kwargs

        def _resolved_plot_range(self):
            return None

    factory = Factory()
    factory._open_station_analysis_panel(
        "ground-station-access",
        "ground-station-access",
        "access",
        "middle",
        False,
    )

    creator = captured["creator"]
    assert callable(creator)
    view = creator(cast(Any, None))
    assert isinstance(view, GroundStationView)
    assert view.name == "ground-station-access"
    assert isinstance(view._create_renderer(), GroundStationAccessRenderer)
    view.close()
