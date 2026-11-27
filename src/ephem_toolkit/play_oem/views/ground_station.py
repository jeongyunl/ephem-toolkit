"""Unified Ground Station view support and panel renderer dispatch."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, cast

import numpy as np
import wx
from matplotlib.axes import Axes
from matplotlib.backend_bases import MouseButton
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg

from .. import cursor as playback_cursor
from ..display_time import UTC_DISPLAY, format_tt
from ..ground_stations import GroundStation
from ..oem_data_store import StationAccessView, StoreQuery, TierName
from ..series import OrbitSeries
from ..station_access import AccessInterval, StationAccess
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit
from ..matplotlib_helpers import create_figure, style_axes
from ..widgets import (
    FloatingPanel,
    FloatingMatplotlibLegend,
    MatplotlibPanel,
    PanelCorner,
    PanelInteraction,
)
from .plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    set_shared_x_limits,
    time_bounds_to_axis,
)
from .data_view_base import (
    GroundStationAnalysisMixin,
    StoreStationViewSupport,
    StoreTimeSeriesView,
    StoreViewContext,
    station_access_from_store,
    store_load_status_message,
)
from .time_series_support import TimeSeriesWxPanelMixin


ANALYSIS_PANEL_MODES = frozenset(
    ("elevation-profile", "azimuth-profile", "range-profile")
)


class GroundStationPanelRenderer(Protocol):
    """Lifecycle contract for one unified Ground Station panel mode."""

    panel_mode: str

    def build(
        self,
        series: OrbitSeries,
        time_unit: TimeUnit,
        /,
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


class GroundStationProfileRendererBase(
    GroundStationAnalysisMixin,
    TimeSeriesWxPanelMixin,
    StoreTimeSeriesView,
):
    """Shared implementation shell for store-backed Ground Station profiles."""

    panel_mode = "elevation-profile"
    panel_label = "Elevation Profile"
    y_label = "Elevation (degrees)"
    y_limits = (0.0, 95.0)
    status_metric = "Elevation"
    status_unit = "°"
    seek_on_click = True

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
        self._parent = parent
        self._cursor = cursor
        self._time_unit = time_unit
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_station_manager = on_station_manager
        self._display_time_zone = display_time_zone
        self._time_range = initial_range
        self._coverage = (cursor.t_start, cursor.t_end)
        self._current_time_s = cursor.t_start
        self._results: dict[str, StationAccess] = {}
        self._store_queries: dict[str, StoreQuery[StationAccessView]] = {}
        self._station_choice: wx.Choice | None = None
        self._mask_filter_control: wx.CheckBox | None = None
        self._mask_filter_enabled = True
        self._status_label: wx.StaticText | None = None
        self._settings_panel: FloatingPanel | None = None
        self._status_panel: FloatingPanel | None = None
        self._legend_panel: FloatingMatplotlibLegend | None = None
        self._panel: wx.Panel | None = None
        self._axes: Axes | None = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._figure: Figure | None = None
        self._playback_marker: Line2D | None = None

        self._initialize_store_time_series(
            cursor.t_start,
            tiers=("station-access",),
        )
        self._time_series_origin_s = cursor.t_start
        self._time_series_divisor_s = time_unit.get_divisor_s()
        self._initialize_ground_station_analysis(
            stations,
            selection_context,
            oem_loaded=oem_loaded,
            tiers=("station-access",),
        )
        self._initialize_time_series_wx()

    def build(
        self,
        _series: OrbitSeries,
        time_unit: TimeUnit,
    ) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        panel.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
        panel.SetName(self.panel_label)
        panel.SetMinSize(panel.FromDIP(wx.Size(64, 64)))
        self._panel = panel

        self._figure = create_figure((9.0, 5.0), constrained_layout=False)
        self._axes = self._figure.add_subplot(111)
        plot_panel = MatplotlibPanel(
            panel,
            self._figure,
            preserve_aspect_ratio=False,
            minimum_canvas_size=(64, 64),
        )
        self._plot_panel = plot_panel
        self._canvas = plot_panel.canvas
        self._configure_time_series_axes(
            (self._axes,),
            start_time_s=self._cursor.t_start,
            time_unit=time_unit,
            seek_enabled=True,
        )

        self._create_profile_floating_controls(panel)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(plot_panel, 1, wx.EXPAND)
        panel.SetSizer(root)
        panel.Layout()
        self._refresh_station_choice()
        self._prepare_access()
        self._draw()
        self.update(self._current_time_s)
        return panel

    def build_from_store(self, context: StoreViewContext) -> wx.Window:
        self._prepare_station_store_context(context)
        self._time_range = context.plot_range
        self._coverage = context.coverage
        self._prepare_access()
        return self.build(cast(OrbitSeries, None), context.time_unit)

    def update_from_store(self, context: StoreViewContext) -> None:
        self._begin_station_store_update(context, self.panel_label)
        self._time_range = context.plot_range
        self._coverage = context.coverage
        self._prepare_access()
        self._draw()
        self.update(self._current_time_s)

    def update(self, time_s: float) -> None:
        self._current_time_s = time_s
        if self._playback_marker is not None:
            self._playback_marker.set_xdata(
                [self._axis_time(time_s), self._axis_time(time_s)]
            )
        self._update_status_text()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def set_time_range(
        self,
        bounds: ResolvedTimeRange | None,
        coverage: tuple[float, float],
    ) -> None:
        if bounds == self._time_range and coverage == self._coverage:
            return
        self._time_range = bounds
        self._coverage = coverage
        if self._station_store_context is not None:
            self._station_store_context = self._station_store_context_for_range(
                bounds,
                coverage,
            )
        self._prepare_access()
        self._draw()
        self.update(self._current_time_s)

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._set_ground_station_stations(stations)
        self._prepare_access()
        self._refresh_station_choice()
        self._draw()
        self.update(self._current_time_s)

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        self._draw()

    def close(self) -> None:
        self._close_ground_station_analysis()
        self._close_time_series_wx()
        self._results.clear()
        self._store_queries.clear()
        self._panel = None
        self._axes = None
        self._canvas = None
        self._figure = None
        self._station_choice = None
        self._mask_filter_control = None
        self._status_label = None
        self._legend_panel = None

    def _create_profile_floating_controls(self, panel: wx.Panel) -> None:
        settings = self._create_time_series_floating_panel(
            panel,
            name=f"{self.panel_label} settings",
            handle_label="≡",
            corner=PanelCorner.TOP_RIGHT,
        )
        self._settings_panel = settings
        controls = settings.GetContentWindow()
        controls.SetName(f"{self.panel_label} controls")
        station_label = wx.StaticText(controls, wx.ID_ANY, "Station")
        self._station_choice = wx.Choice(controls, wx.ID_ANY)
        self._station_choice.SetName(f"{self.panel_label} station")
        self._station_choice.Bind(wx.EVT_CHOICE, self._on_station_selected)
        manage = wx.Button(
            controls,
            wx.ID_ANY,
            "Manage Ground Stations",
        )
        manage.SetName(f"Manage stations from {self.panel_label}")
        manage.Bind(wx.EVT_BUTTON, lambda _event: self._on_station_manager())
        mask = wx.CheckBox(
            controls,
            wx.ID_ANY,
            "Show only above minimum elevation",
        )
        mask.SetName(f"{self.panel_label} above-mask filter")
        mask.SetValue(self._mask_filter_enabled)
        mask.Bind(wx.EVT_CHECKBOX, self._on_mask_filter_toggled)
        self._mask_filter_control = mask
        self._compact_time_series_controls(
            (self._station_choice, manage)
        )

        content = wx.BoxSizer(wx.HORIZONTAL)
        content.Add(station_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        content.Add(self._station_choice, 1, wx.EXPAND | wx.RIGHT, 8)
        content.Add(manage, 0, wx.RIGHT, 8)
        content.Add(mask, 0, wx.ALIGN_CENTER_VERTICAL)
        settings.SetContentSizer(content)

        status, status_label = self._create_time_series_status_panel(
            panel,
            name=f"{self.panel_label} status",
        )
        self._status_panel = status
        self._status_label = status_label

        legend = FloatingMatplotlibLegend(
            panel,
            name=f"{self.panel_label} legend",
            handle_label="≡",
            corner=PanelCorner.BOTTOM_RIGHT,
        )
        self._legend_panel = legend
        self._time_series_floating_panels.append(legend)

    def _on_ground_station_context_selection(
        self,
        selection: StationAnalysisSelection,
    ) -> None:
        super()._on_ground_station_context_selection(selection)
        self._refresh_station_choice()
        self._prepare_access()
        self._draw()
        self.update(self._current_time_s)

    def _on_station_selected(self, _event: wx.CommandEvent) -> None:
        if self._station_choice is None:
            return
        index = self._station_choice.GetSelection()
        if 0 <= index < len(self._stations):
            station_id = self._stations[index].station_id
            self._selected_station_id = station_id
            if self._selection_context is not None:
                self._selection_context.select_station(station_id)
            self._prepare_access()
            self._draw()
            self.update(self._current_time_s)

    def _on_mask_filter_toggled(self, _event: wx.CheckBox) -> None:
        if self._mask_filter_control is None:
            return
        self._mask_filter_enabled = self._mask_filter_control.GetValue()
        self._draw()
        self.update(self._current_time_s)

    def _refresh_station_choice(self) -> None:
        if self._station_choice is None:
            return
        self._station_choice.Clear()
        selected_index = wx.NOT_FOUND
        for index, station in enumerate(self._stations):
            self._station_choice.Append(station.name)
            if station.station_id == self._selected_station_id:
                selected_index = index
        self._station_choice.SetSelection(selected_index)

    def _prepare_access(self) -> None:
        self._results.clear()
        self._store_queries.clear()
        if not self._oem_loaded or self._station_store_context is None:
            return
        for station in self._stations:
            query = self._station_store_context.station_access(station)
            self._store_queries[station.station_id] = query
            self._results[station.station_id] = station_access_from_store(query.value)

    def _draw(self) -> None:
        if self._axes is None:
            self._update_status_text()
            return
        self._axes.clear()
        self._playback_marker = self._axes.axvline(
            self._axis_time(self._current_time_s),
            color="#df4d66",
            linewidth=1.2,
            label="Playback",
        )
        self._update_status_text()

        station = self._selected_ground_station()
        if station is not None and self._oem_loaded:
            result = self._results.get(station.station_id)
            if result is not None:
                self._draw_profile(result, station)

        self._axes.set_xlabel("UTC")
        self._axes.xaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _position: format_tt(
                    self._cursor.t_start + value * self._time_unit.get_divisor_s(),
                    self._display_time_zone,
                    fractional_second_places=0,
                )
            )
        )
        left, right = self._axis_bounds(self._time_range, self._coverage)
        self._axes.set_xlim(left, right)
        if self.y_limits is not None:
            self._axes.set_ylim(*self.y_limits)
        self._axes.set_ylabel(self.y_label)
        self._axes.grid(True, alpha=0.25)
        handles, _labels = self._axes.get_legend_handles_labels()
        if self._legend_panel is not None:
            self._legend_panel.set_handles(tuple(handles))
        style_axes(self._axes)
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _draw_profile(
        self,
        result: StationAccess,
        station: GroundStation,
    ) -> None:
        if self._axes is None or self._time_range is None:
            return
        if self.panel_mode == "elevation-profile":
            for index, interval in enumerate(self._visible_intervals(result)):
                self._axes.axvspan(
                    self._axis_time(interval.start_s),
                    self._axis_time(interval.end_s),
                    color="#d6e8ff",
                    alpha=0.45,
                    label="Access interval" if index == 0 else None,
                )

        sampler = self._station_time_sampling()
        for profile in result.look_angle_profiles:
            profile_times = profile.times_s
            first = int(
                np.searchsorted(profile_times, self._time_range.start_s, side="left")
            )
            stop = int(
                np.searchsorted(profile_times, self._time_range.end_s, side="right")
            )
            if first >= stop:
                continue
            times = profile_times[first:stop]
            elevations = profile.elevations_deg[first:stop]
            if not len(times):
                continue
            if self.panel_mode == "elevation-profile":
                display_times, display_values = sampler.sample(
                    times,
                    elevations,
                    bounds_s=(float(times[0]), float(times[-1])),
                    max_samples=MAX_DISPLAY_POINTS_PER_SEGMENT,
                )
                finite = np.isfinite(display_values)
                display_values = np.asarray(display_values, dtype=float).copy()
                if self._mask_filter_enabled:
                    display_values[
                        np.asarray(finite)
                        & (display_values < station.minimum_elevation_deg)
                    ] = np.nan
            elif self.panel_mode == "azimuth-profile":
                azimuths = profile.azimuths_deg[first:stop]
                source_values = (
                    np.column_stack((azimuths, elevations))
                    if self._mask_filter_enabled
                    else azimuths
                )
                display_times, display_values = sampler.sample(
                    times,
                    source_values,
                    bounds_s=(float(times[0]), float(times[-1])),
                    max_samples=MAX_DISPLAY_POINTS_PER_SEGMENT,
                )
                display_values = np.asarray(display_values)
                if display_values.ndim == 2:
                    below_mask = display_values[:, 1] < station.minimum_elevation_deg
                    display_values[below_mask, 0] = np.nan
                    display_values = display_values[:, 0]
                display_values = np.asarray(display_values, dtype=float).copy()
                breaks = np.flatnonzero(
                    np.abs(np.diff(display_values)) > 180.0
                ) + 1
                display_values[breaks] = np.nan
            else:
                ranges = profile.slant_ranges_km
                if ranges is None:
                    continue
                ranges = ranges[first:stop]
                source_values = (
                    np.column_stack((ranges, elevations))
                    if self._mask_filter_enabled
                    else ranges
                )
                display_times, display_values = sampler.sample(
                    times,
                    source_values,
                    bounds_s=(float(times[0]), float(times[-1])),
                    max_samples=MAX_DISPLAY_POINTS_PER_SEGMENT,
                )
                display_values = np.asarray(display_values)
                if display_values.ndim == 2:
                    below_mask = display_values[:, 1] < station.minimum_elevation_deg
                    display_values[below_mask, 0] = np.nan
                    display_values = display_values[:, 0]
                display_values = np.asarray(display_values, dtype=float).copy()
            self._axes.plot(
                self._axis_times(display_times),
                display_values,
                linewidth=1.3,
                label=f"{station.name} · segment",
            )
        if self.panel_mode == "elevation-profile":
            self._axes.axhline(
                station.minimum_elevation_deg,
                color="#c74343",
                linestyle="--",
                linewidth=1.0,
                label="Station mask",
            )

    def _visible_intervals(
        self,
        result: StationAccess,
    ) -> tuple[AccessInterval, ...]:
        if self._time_range is None:
            return ()
        return tuple(
            interval
            for interval in result.intervals
            if interval.start_s <= self._time_range.end_s
            and interval.end_s >= self._time_range.start_s
        )

    def _update_status_text(self) -> None:
        station = self._selected_ground_station()
        load_status = store_load_status_message(self._station_store_context)
        if station is None:
            message = "No ground stations are configured. Add a station to continue."
        elif not self._oem_loaded or self._station_store_context is None:
            message = "Load an Earth-centered OEM to view station analysis."
        elif load_status is not None:
            message = load_status
        elif self._time_range is None:
            message = "The current Plot Range does not overlap OEM coverage."
        else:
            result = self._results.get(station.station_id)
            query = self._store_queries.get(station.station_id)
            metrics = self._station_store_context.station_metrics_at(
                station,
                self._current_time_s,
            )
            if metrics is not None:
                if self.status_metric == "Azimuth":
                    value = metrics.azimuth_deg
                elif self.status_metric == "Elevation":
                    value = metrics.elevation_deg
                else:
                    value = metrics.slant_range_km
                message = (
                    f"{station.name} · {self.status_metric} "
                    f"{value:.1f}{self.status_unit}"
                )
            else:
                message = (
                    "Current OEM state unavailable "
                    "(outside coverage or in a segment gap)."
                )
            limitation = (
                result.limitation if result is not None and result.limitation else ""
            )
            if limitation:
                message = f"{message} · {limitation}"
            elif query is not None and not query.coverage.complete:
                has_ready_data = bool(
                    result is not None
                    and (result.intervals or result.look_angle_profiles)
                )
                partial_status = (
                    "Station data is partially available."
                    if has_ready_data
                    else "Station data is loading."
                )
                message = f"{message} · {partial_status}"
            elif result is not None and not result.look_angle_profiles:
                message = (
                    f"{message} · "
                    "No station profile samples are available in this range."
                )
        if self._status_label is not None:
            self._set_time_series_status(message)


class ElevationProfileRenderer(GroundStationProfileRendererBase):
    """Updated Elevation Profile renderer."""

    panel_mode = "elevation-profile"
    panel_label = "Elevation Profile"
    y_label = "Elevation (degrees)"
    y_limits = (0.0, 95.0)
    status_metric = "Elevation"
    status_unit = "°"


class AzimuthProfileRenderer(GroundStationProfileRendererBase):
    """Updated Azimuth Profile renderer."""

    panel_mode = "azimuth-profile"
    panel_label = "Azimuth Profile"
    y_label = "Azimuth (degrees)"
    y_limits = (0.0, 360.0)
    status_metric = "Azimuth"
    status_unit = "°"


class RangeProfileRenderer(GroundStationProfileRendererBase):
    """Updated Range Profile renderer."""

    panel_mode = "range-profile"
    panel_label = "Range Profile"
    y_label = "Slant range (km)"
    y_limits = None
    status_metric = "Slant range"
    status_unit = " km"


class GroundStationView(
    GroundStationAnalysisMixin,
    TimeSeriesWxPanelMixin,
    StoreTimeSeriesView,
):
    """Unify Ground Station profile panels behind shared store and wx support."""

    renderer_types: dict[
        str,
        type[GroundStationPanelRenderer],
    ] = {
        "elevation-profile": ElevationProfileRenderer,
        "azimuth-profile": AzimuthProfileRenderer,
        "range-profile": RangeProfileRenderer,
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
        selection_context: StationAnalysisContext | None = None,
        initial_range: ResolvedTimeRange | None = None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        if panel_mode not in ANALYSIS_PANEL_MODES:
            raise ValueError(f"unknown Ground Station panel mode: {panel_mode!r}")

        self.name = panel_mode
        self._parent = parent
        self._panel_mode = panel_mode
        self._cursor = cursor
        self._time_unit = time_unit
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_station_manager = on_station_manager
        self._display_time_zone = display_time_zone
        self._time_range = initial_range
        self._current_time_s = cursor.t_start
        self.seek_on_click = True

        tiers: Sequence[TierName] = ("station-access",)
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
        context = self._selection_context
        if context is None:
            context = StationAnalysisContext()
            self._selection_context = context
        renderer = self._make_analysis_renderer(context)
        self._renderer = renderer
        return renderer

    def _make_analysis_renderer(
        self,
        selection_context: StationAnalysisContext,
    ) -> GroundStationPanelRenderer:
        renderer_types = {
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
        self._panel = self._ensure_renderer().build_from_store(context)
        return self._panel

    def update_from_store(self, context: StoreViewContext) -> None:
        self._begin_station_store_update(context, "Ground Station")
        self._time_range = context.plot_range
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
        if self._station_store_context is not None:
            self._station_store_context = self._station_store_context_for_range(
                bounds, coverage
            )
        if self._renderer is not None:
            self._renderer.set_time_range(bounds, coverage)

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._set_ground_station_stations(stations)
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
