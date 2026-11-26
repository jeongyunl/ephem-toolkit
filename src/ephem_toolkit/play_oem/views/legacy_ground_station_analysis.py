"""Focused Ground Station status, interval, and time-profile panels."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from .. import cursor as playback_cursor
from ..display_time import UTC_DISPLAY, format_tt
from ..graph_panel import GRAPH_PANEL_MIN_SIZE
from ..ground_stations import GroundStation
from ..matplotlib_helpers import create_figure, style_axes
from ..oem_data_store import StationAccessView, StoreQuery
from ..series import OrbitSeries
from ..station_access import (
    AccessInterval,
    StationAccess,
)
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit
from ..widgets import (
    FloatingPanel,
    MatplotlibPanel,
    PanelCorner,
    PanelInteraction,
)
from .compact_controls import compact_controls
from .base import (
    StoreStationViewSupport,
    StoreViewContext,
    station_access_from_store,
    store_load_status_message,
)
from .plotting import MAX_DISPLAY_POINTS_PER_SEGMENT

_PROFILE_TYPES = frozenset(("elevation-profile", "azimuth-profile", "range-profile"))


class LegacyGroundStationAnalysisView(StoreStationViewSupport):
    """Render one focused Ground Station panel from shared prepared history."""

    def __init__(
        self,
        parent: wx.Window,
        panel_type: str,
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
        if panel_type not in _PROFILE_TYPES | {"station-status"}:
            raise ValueError(f"unknown Ground Station panel type: {panel_type!r}")
        self.name = panel_type
        self._parent = parent
        self._panel_type = panel_type
        self._cursor = cursor
        self._stations = tuple(stations)
        self._time_unit = time_unit
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_station_manager = on_station_manager
        self._selection_context = selection_context
        self._display_time_zone = display_time_zone
        self._time_range = initial_range
        self._current_time_s = cursor.t_start
        selected_id = selection_context.selection.station_id
        self._selected_station_id = (
            selected_id
            if any(station.station_id == selected_id for station in stations)
            else (self._stations[0].station_id if self._stations else None)
        )
        self._results: dict[str, StationAccess] = {}
        self._initialize_station_store(
            () if panel_type == "station-status" else ("station-access",)
        )
        self._store_queries: dict[str, StoreQuery[StationAccessView]] = {}
        self._panel: wx.Panel | None = None
        self._settings_panel: FloatingPanel | None = None
        self._status_panel: FloatingPanel | None = None
        self._station_choice: wx.Choice | None = None
        self._mask_filter_control: wx.CheckBox | None = None
        self._mask_filter_enabled = True
        self._status_label: wx.StaticText | None = None
        self._metrics_label: wx.StaticText | None = None
        self._figure: Figure | None = None
        self._axes: Any = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._plot_panel: MatplotlibPanel | None = None
        self._playback_marker: Any = None
        self._selection_callback_id: int | None = None
        self._context_unsubscribe = selection_context.subscribe(
            self._on_context_selection
        )
        self._prepare_access()
        if self._selected_station_id != selected_id:
            selection_context.select_station(self._selected_station_id)

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        return self._build_panel()

    def build_from_store(self, context: StoreViewContext, /) -> wx.Window:
        """Build from bound station queries and point metrics."""
        self._prepare_station_store_context(context)
        self._time_range = context.plot_range
        self._prepare_access()
        return self._build_panel()

    def update_from_store(self, context: StoreViewContext, /) -> None:
        """Refresh station results from a newer snapshot or range."""
        self._begin_station_store_update(context, "Ground Station")
        self._time_range = context.plot_range
        self._prepare_access()
        self._draw()
        self.update(self._current_time_s)

    def _build_panel(self) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        self._panel = panel
        root = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(
            panel, wx.ID_ANY, f"{self._panel_label()} — {self._object_name}"
        )
        heading.SetName(f"{self._panel_label()} heading")
        root.Add(heading, 0, wx.EXPAND | wx.ALL, 8)

        controls = wx.BoxSizer(wx.HORIZONTAL)
        controls.Add(
            wx.StaticText(panel, wx.ID_ANY, "Station"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6,
        )
        self._station_choice = wx.Choice(panel, wx.ID_ANY)
        self._station_choice.SetName(f"{self._panel_label()} station")
        self._station_choice.Bind(wx.EVT_CHOICE, self._on_station_selected)
        controls.Add(self._station_choice, 1, wx.EXPAND | wx.RIGHT, 8)
        manage = wx.Button(panel, wx.ID_ANY, "Manage Ground Stations")
        manage.SetName(f"Manage stations from {self._panel_label()}")
        manage.Bind(wx.EVT_BUTTON, lambda _event: self._on_station_manager())
        controls.Add(manage, 0)
        root.Add(controls, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        if self._panel_type in _PROFILE_TYPES:
            self._mask_filter_control = wx.CheckBox(
                panel,
                wx.ID_ANY,
                "Show only above minimum elevation",
            )
            self._mask_filter_control.SetName(
                f"{self._panel_label()} above-mask filter"
            )
            self._mask_filter_control.SetValue(self._mask_filter_enabled)
            self._mask_filter_control.Bind(
                wx.EVT_CHECKBOX, self._on_mask_filter_toggled
            )
            root.Add(
                self._mask_filter_control,
                0,
                wx.LEFT | wx.RIGHT | wx.TOP,
                8,
            )

        self._status_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._status_label.SetName(f"{self._panel_label()} status")
        root.Add(self._status_label, 0, wx.EXPAND | wx.ALL, 8)

        if self._panel_type == "station-status":
            self._metrics_label = wx.StaticText(panel, wx.ID_ANY, "")
            self._metrics_label.SetName("Current station metrics")
            root.Add(self._metrics_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        else:
            self._figure = create_figure((8.0, 4.5))
            self._axes = self._figure.add_subplot(111)
            plot_panel = MatplotlibPanel(
                panel,
                self._figure,
                preserve_aspect_ratio=False,
            )
            self._plot_panel = plot_panel
            self._canvas = plot_panel.canvas
            self._playback_marker = self._axes.axvline(
                self._axis_time(self._current_time_s),
                color="#df4d66",
                linewidth=1.2,
                label="Playback",
            )
            root.Add(plot_panel, 1, wx.EXPAND)
        panel.SetSizer(root)
        self._refresh_station_choice()
        self._draw()
        self.update(self._current_time_s)
        return panel

    def update(self, t_s: float, /) -> None:
        self._current_time_s = t_s
        if self._panel_type == "station-status":
            self._update_status_metrics()
        if self._playback_marker is not None:
            x = self._axis_time(t_s)
            self._playback_marker.set_xdata([x, x])
            if self._canvas is not None:
                self._canvas.draw_idle()

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if bounds == self._time_range:
            return
        self._time_range = bounds
        if self._store_context is not None:
            self._store_context = self._station_store_context_for_range(
                bounds, coverage
            )
        self._prepare_access()
        self._draw()

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._stations = tuple(stations)
        selected_id = self._selection_context.selection.station_id
        self._selected_station_id = (
            selected_id
            if any(station.station_id == selected_id for station in stations)
            else (self._stations[0].station_id if self._stations else None)
        )
        self._prepare_access()
        self._refresh_station_choice()
        self._draw()
        self.update(self._current_time_s)
        self._selection_context.select_station(self._selected_station_id)

    def close(self) -> None:
        self._context_unsubscribe()
        if self._canvas is not None and self._selection_callback_id is not None:
            self._canvas.mpl_disconnect(self._selection_callback_id)
        self._context_unsubscribe = lambda: None
        self._close_station_store()
        self._store_queries.clear()
        self._canvas = None
        self._figure = None
        self._plot_panel = None
        self._axes = None
        self._panel = None

    def _on_context_selection(self, selection: StationAnalysisSelection) -> None:
        station_id = selection.station_id
        if station_id is not None and not any(
            station.station_id == station_id for station in self._stations
        ):
            return
        station_changed = station_id != self._selected_station_id
        if not station_changed:
            return
        if station_changed:
            self._selected_station_id = station_id
            self._refresh_station_choice()
            self._draw()
            self.update(self._current_time_s)
        else:
            self._draw()

    def _on_station_selected(self, _event: wx.CommandEvent) -> None:
        if self._station_choice is None:
            return
        index = self._station_choice.GetSelection()
        if 0 <= index < len(self._stations):
            self._selected_station_id = self._stations[index].station_id
            self._selection_context.select_station(self._selected_station_id)
            self._draw()
            self.update(self._current_time_s)

    def _on_mask_filter_toggled(self, _event: wx.CommandEvent) -> None:
        if self._mask_filter_control is None:
            return
        self._mask_filter_enabled = self._mask_filter_control.GetValue()
        self._draw()

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
        if self._panel_type == "station-status" or not self._oem_loaded:
            return
        if self._store_context is not None:
            for station in self._stations:
                query = self._store_context.station_access(station)
                self._store_queries[station.station_id] = query
                self._results[station.station_id] = station_access_from_store(
                    query.value
                )
            return

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
        station = self._selected_station()
        if station is not None and self._oem_loaded:
            result = self._results.get(station.station_id)
            if result is not None:
                if self._panel_type in _PROFILE_TYPES:
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
        self._axes.set_xlim(*self._axis_bounds())
        if self._panel_type == "elevation-profile":
            self._axes.set_ylim(0.0, 95.0)
            self._axes.set_ylabel("Elevation (degrees)")
        elif self._panel_type == "azimuth-profile":
            self._axes.set_ylim(0.0, 360.0)
            self._axes.set_ylabel("Azimuth (degrees)")
        elif self._panel_type == "range-profile":
            self._axes.set_ylabel("Slant range (km)")
        self._axes.grid(True, alpha=0.25)
        handles, labels = self._axes.get_legend_handles_labels()
        if handles:
            self._axes.legend(loc="best")
        style_axes(self._axes)
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _draw_profile(self, result: StationAccess, station: GroundStation) -> None:
        if self._axes is None:
            return
        sampler = self._station_time_sampling()
        if self._panel_type == "elevation-profile":
            intervals = self._visible_intervals(result)
            for index, interval in enumerate(intervals):
                self._axes.axvspan(
                    self._axis_time(interval.start_s),
                    self._axis_time(interval.end_s),
                    color="#d6e8ff",
                    alpha=0.45,
                    label="Access interval" if index == 0 else None,
                )
        for profile in result.look_angle_profiles:
            if self._time_range is None:
                continue
            profile_times = profile.times_s
            if self._store_context is not None:
                first = int(
                    np.searchsorted(
                        profile_times, self._time_range.start_s, side="left"
                    )
                )
                stop = int(
                    np.searchsorted(profile_times, self._time_range.end_s, side="right")
                )
                if first >= stop:
                    continue
                selection: slice | np.ndarray = slice(first, stop)
            else:
                selected = (profile_times >= self._time_range.start_s) & (
                    profile_times <= self._time_range.end_s
                )
                selection = np.flatnonzero(selected)
                if not len(selection):
                    continue
            times = profile_times[selection]
            if not len(times):
                continue
            if self._panel_type == "elevation-profile":
                values = profile.elevations_deg[selection]
                self._axes.axhline(
                    station.minimum_elevation_deg,
                    color="#c74343",
                    linestyle="--",
                    linewidth=1.0,
                    label="Station mask",
                )
            elif self._panel_type == "azimuth-profile":
                values = profile.azimuths_deg[selection]
                values = np.asarray(values, dtype=float).copy()
                breaks = np.flatnonzero(np.abs(np.diff(values)) > 180.0) + 1
                values[breaks] = np.nan
            else:
                if profile.slant_ranges_km is None:
                    continue
                values = profile.slant_ranges_km[selection]
            values = np.asarray(values, dtype=float).copy()
            elevations = np.asarray(profile.elevations_deg[selection], dtype=float)
            if self._mask_filter_enabled:
                source_values = np.column_stack((values, elevations))
            else:
                source_values = values
            finite_times = np.flatnonzero(np.isfinite(times))
            if not finite_times.size:
                continue
            display_times, display_values = sampler.sample(
                times,
                source_values,
                bounds_s=(
                    float(times[finite_times[0]]),
                    float(times[finite_times[-1]]),
                ),
                max_samples=MAX_DISPLAY_POINTS_PER_SEGMENT,
            )
            if self._mask_filter_enabled and display_values.ndim == 2:
                below_mask = display_values[:, 1] < station.minimum_elevation_deg
                display_values[below_mask, 0] = np.nan
                display_values = display_values[:, 0]
            self._axes.plot(
                self._axis_times(display_times),
                display_values,
                linewidth=1.3,
                label=f"{station.name} · segment",
            )

    def _visible_intervals(self, result: StationAccess) -> tuple[AccessInterval, ...]:
        if self._time_range is None:
            return ()
        return tuple(
            interval
            for interval in result.intervals
            if interval.start_s <= self._time_range.end_s
            and interval.end_s >= self._time_range.start_s
        )

    def _update_status_text(self) -> None:
        station = self._selected_station()
        load_status = store_load_status_message(self._store_context)
        if station is None:
            message = "No ground stations are configured. Add a station to continue."
        elif not self._oem_loaded or self._store_context is None:
            message = "Load an Earth-centered OEM to view station analysis."
        elif load_status is not None:
            message = load_status
        elif self._time_range is None and self._panel_type != "station-status":
            message = "The current Plot Range does not overlap OEM coverage."
        else:
            result = self._results.get(station.station_id)
            query = self._store_queries.get(station.station_id)
            message = (
                result.limitation if result is not None and result.limitation else ""
            )
            if query is not None and not query.coverage.complete and not message:
                has_ready_data = bool(
                    result is not None
                    and (result.intervals or result.look_angle_profiles)
                )
                message = (
                    "Station data is partially available."
                    if has_ready_data
                    else "Station data is loading."
                )
            elif self._panel_type in _PROFILE_TYPES and result is not None:
                if not result.look_angle_profiles and not message:
                    message = "No station profile samples are available in this range."
        if self._status_label is not None:
            self._status_label.SetLabel(message)

    def _update_status_metrics(self) -> None:
        self._update_status_text()
        station = self._selected_station()
        if station is None or not self._oem_loaded or self._store_context is None:
            metrics_text = ""
        else:
            metrics = self._store_context.station_metrics_at(
                station, self._current_time_s
            )
            metrics_text = (
                "Current OEM state unavailable (outside coverage or in a segment gap)."
                if metrics is None
                else (
                    f"{station.name} · mask {station.minimum_elevation_deg}°\n"
                    f"{'Access' if metrics.access else 'No access'} · "
                    f"Azimuth {metrics.azimuth_deg:.1f}° · "
                    f"Elevation {metrics.elevation_deg:.1f}° · "
                    f"Slant range {metrics.slant_range_km:.1f} km"
                )
            )
        if self._metrics_label is not None:
            self._metrics_label.SetLabel(metrics_text)

    def _selected_station(self) -> GroundStation | None:
        return next(
            (
                station
                for station in self._stations
                if station.station_id == self._selected_station_id
            ),
            None,
        )

    def _panel_label(self) -> str:
        return {
            "station-status": "Station Status",
            "elevation-profile": "Elevation Profile",
            "azimuth-profile": "Azimuth Profile",
            "range-profile": "Range Profile",
        }[self._panel_type]

    def _axis_time(self, time_s: float) -> float:
        return (time_s - self._cursor.t_start) / self._time_unit.get_divisor_s()

    def _axis_times(self, times_s: np.ndarray) -> np.ndarray:
        return (times_s - self._cursor.t_start) / self._time_unit.get_divisor_s()

    def _axis_bounds(self) -> tuple[float, float]:
        bounds = self._time_range
        if bounds is None:
            center = self._axis_time(self._current_time_s)
            return center - 0.5, center + 0.5
        start = bounds.start_s
        end = bounds.end_s
        if start == end:
            center = self._axis_time(start)
            return center - 0.5, center + 0.5
        return self._axis_time(start), self._axis_time(end)

    def _axis_duration(self, interval: AccessInterval) -> float:
        return self._axis_time(interval.end_s) - self._axis_time(interval.start_s)


