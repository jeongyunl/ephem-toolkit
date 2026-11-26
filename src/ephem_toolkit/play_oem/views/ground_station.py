"""Unified Ground Station view support and panel renderer dispatch."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

import wx
from matplotlib.figure import Figure

from .. import cursor as playback_cursor
from ..display_time import UTC_DISPLAY
from ..ground_stations import GroundStation
from ..oem_data_store import TierName
from ..series import OrbitSeries
from ..station_analysis import StationAnalysisContext
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit
from .base import (
    GroundStationAnalysisMixin,
    StoreTimeSeriesView,
    StoreViewContext,
)
from .legacy_ground_station_access import LegacyGroundStationAccessView
from .legacy_ground_station_analysis import LegacyGroundStationAnalysisView
from .time_series_support import TimeSeriesWxPanelMixin


ANALYSIS_PANEL_MODES = frozenset(
    ("station-status", "elevation-profile", "azimuth-profile", "range-profile")
)
GROUND_STATION_PANEL_MODES = ANALYSIS_PANEL_MODES | {"ground-station-access"}


class GroundStationPanelRenderer(Protocol):
    """Lifecycle contract for one unified Ground Station panel mode."""

    panel_mode: str

    def build(
        self,
        series: OrbitSeries,
        time_unit: TimeUnit,
    ) -> wx.Window:
        ...

    def build_from_store(self, context: StoreViewContext) -> wx.Window:
        ...

    def update_from_store(self, context: StoreViewContext) -> None:
        ...

    def update(self, time_s: float) -> None:
        ...

    def set_time_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> None:
        ...

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        ...

    def close(self) -> None:
        ...


GroundStationRenderer = GroundStationPanelRenderer


class GroundStationProfileRenderer:
    """Adapt a Legacy analysis panel behind the unified renderer protocol."""

    def __init__(
        self,
        parent: wx.Window,
        panel_mode: str,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        selection_context: StationAnalysisContext,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        if panel_mode not in ANALYSIS_PANEL_MODES:
            raise ValueError(f"unknown analysis panel mode: {panel_mode!r}")
        self.panel_mode = panel_mode
        self.delegate = LegacyGroundStationAnalysisView(
            parent,
            panel_mode,
            cursor,
            stations,
            time_unit,
            object_name,
            oem_loaded=oem_loaded,
            on_station_manager=on_station_manager,
            selection_context=selection_context,
            initial_range=initial_range,
            display_time_zone=display_time_zone,
        )

    def build(
        self,
        series: OrbitSeries,
        time_unit: TimeUnit,
    ) -> wx.Window:
        return self.delegate.build(series, time_unit)

    def build_from_store(self, context: StoreViewContext) -> wx.Window:
        return self.delegate.build_from_store(context)

    def update_from_store(self, context: StoreViewContext) -> None:
        self.delegate.update_from_store(context)

    def update(self, time_s: float) -> None:
        self.delegate.update(time_s)

    def set_time_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> None:
        self.delegate.set_time_range(bounds, coverage)

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self.delegate.set_stations(stations)

    def close(self) -> None:
        self.delegate.close()


class StationStatusRenderer(GroundStationProfileRenderer):
    """Station Status renderer specialization."""

    def __init__(
        self,
        parent: wx.Window,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        selection_context: StationAnalysisContext,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        super().__init__(
            parent,
            "station-status",
            cursor,
            stations,
            time_unit,
            object_name,
            oem_loaded=oem_loaded,
            on_station_manager=on_station_manager,
            selection_context=selection_context,
            initial_range=initial_range,
            display_time_zone=display_time_zone,
        )


class ElevationProfileRenderer(GroundStationProfileRenderer):
    """Elevation Profile renderer specialization."""

    def __init__(
        self,
        parent: wx.Window,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        selection_context: StationAnalysisContext,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        super().__init__(
            parent,
            "elevation-profile",
            cursor,
            stations,
            time_unit,
            object_name,
            oem_loaded=oem_loaded,
            on_station_manager=on_station_manager,
            selection_context=selection_context,
            initial_range=initial_range,
            display_time_zone=display_time_zone,
        )


class AzimuthProfileRenderer(GroundStationProfileRenderer):
    """Azimuth Profile renderer specialization."""

    def __init__(
        self,
        parent: wx.Window,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        selection_context: StationAnalysisContext,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        super().__init__(
            parent,
            "azimuth-profile",
            cursor,
            stations,
            time_unit,
            object_name,
            oem_loaded=oem_loaded,
            on_station_manager=on_station_manager,
            selection_context=selection_context,
            initial_range=initial_range,
            display_time_zone=display_time_zone,
        )


class RangeProfileRenderer(GroundStationProfileRenderer):
    """Range Profile renderer specialization."""

    def __init__(
        self,
        parent: wx.Window,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        selection_context: StationAnalysisContext,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        super().__init__(
            parent,
            "range-profile",
            cursor,
            stations,
            time_unit,
            object_name,
            oem_loaded=oem_loaded,
            on_station_manager=on_station_manager,
            selection_context=selection_context,
            initial_range=initial_range,
            display_time_zone=display_time_zone,
        )


class GroundStationAccessRenderer:
    """Adapt the Legacy Ground Station Access elevation/dashboard panel."""

    panel_mode = "ground-station-access"

    def __init__(
        self,
        parent: wx.Window,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_seek: Callable[[float], None],
        on_station_manager: Callable[[], None],
        selection_context: StationAnalysisContext | None,
        limit_to_range: bool,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        self.delegate = LegacyGroundStationAccessView(
            parent,
            cursor,
            stations,
            time_unit,
            object_name,
            oem_loaded=oem_loaded,
            on_seek=on_seek,
            on_station_manager=on_station_manager,
            selection_context=selection_context,
            limit_to_range=limit_to_range,
            initial_range=initial_range,
            display_time_zone=display_time_zone,
        )

    def build(
        self,
        series: OrbitSeries,
        time_unit: TimeUnit,
    ) -> wx.Window:
        return self.delegate.build(series, time_unit)

    def build_from_store(self, context: StoreViewContext) -> wx.Window:
        return self.delegate.build_from_store(context)

    def update_from_store(self, context: StoreViewContext) -> None:
        self.delegate.update_from_store(context)

    def update(self, time_s: float) -> None:
        self.delegate.update(time_s)

    def set_time_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> None:
        self.delegate.set_time_range(bounds, coverage)

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self.delegate.set_stations(stations)

    def close(self) -> None:
        self.delegate.close()


class GroundStationView(
    GroundStationAnalysisMixin,
    TimeSeriesWxPanelMixin,
    StoreTimeSeriesView,
):
    """Unify Ground Station panel modes behind shared store and wx support."""

    renderer_types: dict[str, type[GroundStationProfileRenderer] | type[GroundStationAccessRenderer]] = {
        "station-status": StationStatusRenderer,
        "elevation-profile": ElevationProfileRenderer,
        "azimuth-profile": AzimuthProfileRenderer,
        "range-profile": RangeProfileRenderer,
        "ground-station-access": GroundStationAccessRenderer,
    }

    def __init__(
        self,
        parent: wx.Window,
        panel_mode: str,
        cursor: playback_cursor.StoreCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        on_seek: Callable[[float], None] | None = None,
        selection_context: StationAnalysisContext | None = None,
        limit_to_range: bool = False,
        initial_range: ResolvedTimeRange | None = None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        if panel_mode not in GROUND_STATION_PANEL_MODES:
            raise ValueError(f"unknown Ground Station panel mode: {panel_mode!r}")

        self.name = panel_mode
        self._parent = parent
        self._panel_mode = panel_mode
        self._cursor = cursor
        self._time_unit = time_unit
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_station_manager = on_station_manager
        self._on_seek = on_seek or (lambda _time: None)
        self._limit_to_range = limit_to_range
        self._display_time_zone = display_time_zone
        self._time_range = initial_range
        self._current_time_s = cursor.t_start
        self.seek_on_click = panel_mode != "station-status"

        tiers: Sequence[TierName] = (
            ()
            if panel_mode == "station-status"
            else ("station-access",)
        )
        self._initialize_store_time_series(
            cursor.t_start,
            tiers=tiers,
        )
        self._initialize_ground_station_analysis(
            stations,
            selection_context,
            oem_loaded=oem_loaded,
            tiers=tiers,
        )
        self._initialize_time_series_wx()

        self._renderer: GroundStationPanelRenderer | None = None
        self._panel: wx.Window | None = None

    def _create_renderer(self) -> GroundStationPanelRenderer:
        if self._renderer is not None:
            return self._renderer
        if self._panel_mode in ANALYSIS_PANEL_MODES:
            context = self._selection_context
            if context is None:
                context = StationAnalysisContext()
                self._selection_context = context
            renderer = self._make_analysis_renderer(context)
        else:
            renderer = GroundStationAccessRenderer(
                self._parent,
                self._cursor,
                self._stations,
                self._time_unit,
                self._object_name,
                oem_loaded=self._oem_loaded,
                on_seek=self._on_seek,
                on_station_manager=self._on_station_manager,
                selection_context=self._selection_context,
                limit_to_range=self._limit_to_range,
                initial_range=self._time_range,
                display_time_zone=self._display_time_zone,
            )
        self._renderer = renderer
        return renderer

    def _make_analysis_renderer(
        self,
        selection_context: StationAnalysisContext,
    ) -> GroundStationProfileRenderer:
        renderer_types = {
            "station-status": StationStatusRenderer,
            "elevation-profile": ElevationProfileRenderer,
            "azimuth-profile": AzimuthProfileRenderer,
            "range-profile": RangeProfileRenderer,
        }
        renderer_type = renderer_types[self._panel_mode]
        return renderer_type(
            self._parent,
            self._cursor,
            self._stations,
            self._time_unit,
            self._object_name,
            oem_loaded=self._oem_loaded,
            on_station_manager=self._on_station_manager,
            selection_context=selection_context,
            initial_range=self._time_range,
            display_time_zone=self._display_time_zone,
        )

    def _ensure_renderer(self) -> GroundStationPanelRenderer:
        return self._create_renderer()

    def build(
        self,
        series: OrbitSeries,
        time_unit: TimeUnit,
    ) -> wx.Window:
        self._panel = self._ensure_renderer().build(series, time_unit)
        return self._panel

    def build_from_store(self, context: StoreViewContext) -> wx.Window:
        self._prepare_station_store_context(context)
        self._time_range = context.plot_range
        self._prepare_ground_station_access()
        self._panel = self._ensure_renderer().build_from_store(context)
        return self._panel

    def update_from_store(self, context: StoreViewContext) -> None:
        self._begin_station_store_update(context, "Ground Station")
        self._time_range = context.plot_range
        self._prepare_ground_station_access()
        if self._renderer is not None:
            self._renderer.update_from_store(context)

    def update(self, time_s: float) -> None:
        self._current_time_s = time_s
        if self._renderer is not None:
            self._renderer.update(time_s)

    def set_time_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> None:
        self._time_range = bounds
        if self._store_context is not None:
            self._store_context = self._station_store_context_for_range(
                bounds, coverage
            )
        if self._renderer is not None:
            self._renderer.set_time_range(bounds, coverage)

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._set_ground_station_stations(stations)
        self._prepare_ground_station_access()
        if self._renderer is not None:
            self._renderer.set_stations(stations)

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        setter = getattr(self._renderer, "delegate", None)
        if setter is not None:
            delegate_setter = getattr(setter, "set_display_time_zone", None)
            if callable(delegate_setter):
                delegate_setter(display_time_zone)
        self.update(self._current_time_s)

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self._close_ground_station_analysis()
        self._close_time_series_wx()
        self._panel = None
