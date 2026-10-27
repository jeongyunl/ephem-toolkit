"""Focused Ground Station status, interval, and time-profile panels."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import wx
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.ticker import FuncFormatter
from matplotlib.figure import Figure

from ..display_time import UTC_DISPLAY, format_tt
from .. import cursor as playback_cursor
from ..ground_stations import GroundStation
from ..ground_track import (
    GroundTrackPreparationError,
    GroundTrackSource,
)
from ..series import OrbitSeries
from ..station_access import (
    AccessInterval,
    StationAccess,
    StationAccessCache,
    current_station_metrics,
)
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit

_PROFILE_TYPES = frozenset(("elevation-profile", "azimuth-profile", "range-profile"))


class GroundStationAnalysisView:
    """Render one focused Ground Station panel from shared prepared history."""

    def __init__(
        self,
        parent: wx.Window,
        panel_type: str,
        source: GroundTrackSource | None,
        cursor: playback_cursor.OemCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_station_manager: Callable[[], None],
        access_cache: StationAccessCache,
        selection_context: StationAnalysisContext,
        initial_range: ResolvedTimeRange | None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        if panel_type not in _PROFILE_TYPES | {"station-status", "pass-strip"}:
            raise ValueError(f"unknown Ground Station panel type: {panel_type!r}")
        self.name = panel_type
        self._parent = parent
        self._panel_type = panel_type
        self._source = source
        self._cursor = cursor
        self._stations = tuple(stations)
        self._time_unit = time_unit
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_station_manager = on_station_manager
        self._access_cache = access_cache
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
        self._panel: wx.Panel | None = None
        self._station_choice: wx.Choice | None = None
        self._mask_filter_control: wx.CheckBox | None = None
        self._mask_filter_enabled = True
        self._status_label: wx.StaticText | None = None
        self._metrics_label: wx.StaticText | None = None
        self._figure: Figure | None = None
        self._axes: Any = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._playback_marker: Any = None
        self._selection_callback_id: int | None = None
        self._context_unsubscribe = selection_context.subscribe(
            self._on_context_selection
        )
        self._prepare_access()
        if self._selected_station_id != selected_id:
            selection_context.select_station(self._selected_station_id)

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
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
            self._figure = Figure(figsize=(8.0, 4.0), dpi=100)
            self._axes = self._figure.add_subplot(111)
            self._canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, self._figure)
            self._playback_marker = self._axes.axvline(
                self._axis_time(self._current_time_s),
                color="#df4d66",
                linewidth=1.2,
                label="Playback",
            )
            root.Add(self._canvas, 1, wx.EXPAND | wx.ALL, 8)
            if self._panel_type == "pass-strip":
                setattr(self._axes, "_play_oem_seek_enabled", False)
                self._selection_callback_id = self._canvas.mpl_connect(
                    "button_press_event", self._on_strip_click
                )
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
        self, bounds: ResolvedTimeRange | None, _coverage: tuple[float, float], /
    ) -> None:
        if bounds == self._time_range:
            return
        self._time_range = bounds
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
        if (
            self._canvas is not None
            and self._selection_callback_id is not None
        ):
            self._canvas.mpl_disconnect(self._selection_callback_id)
        self._context_unsubscribe = lambda: None
        self._canvas = None
        self._figure = None
        self._axes = None
        self._panel = None

    def _on_context_selection(
        self, selection: StationAnalysisSelection
    ) -> None:
        station_id = selection.station_id
        if station_id is not None and not any(
            station.station_id == station_id for station in self._stations
        ):
            return
        station_changed = station_id != self._selected_station_id
        if not station_changed and self._panel_type != "pass-strip":
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
        if (
            self._panel_type == "station-status"
            or not self._oem_loaded
            or self._source is None
            or self._time_range is None
        ):
            return
        bounds = (self._time_range.start_s, self._time_range.end_s)
        for station in self._stations:
            try:
                self._results[station.station_id] = self._access_cache.prepare(
                    self._source, self._cursor, station, bounds
                )
            except GroundTrackPreparationError as error:
                self._results[station.station_id] = StationAccess(
                    station, (), str(error)
                )

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
        if self._panel_type == "pass-strip":
            setattr(self._axes, "_play_oem_seek_enabled", False)
        self._update_status_text()
        station = self._selected_station()
        if station is not None and self._oem_loaded:
            result = self._results.get(station.station_id)
            if result is not None:
                if self._panel_type == "pass-strip":
                    self._draw_pass_strip(result)
                elif self._panel_type in _PROFILE_TYPES:
                    self._draw_profile(result, station)
        self._axes.set_xlabel("UTC")
        self._axes.xaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _position: format_tt(
                    self._cursor.t_start
                    + value * self._time_unit.get_divisor_s(),
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
        if self._panel_type == "pass-strip":
            self._axes.set_yticks([])
            self._axes.set_ylabel("Access intervals")
        self._axes.grid(True, alpha=0.25)
        handles, labels = self._axes.get_legend_handles_labels()
        if handles:
            self._axes.legend(loc="best")
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _draw_profile(self, result: StationAccess, station: GroundStation) -> None:
        if self._axes is None:
            return
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
            times = profile.times_s
            if self._time_range is None:
                continue
            selected = (times >= self._time_range.start_s) & (
                times <= self._time_range.end_s
            )
            times = times[selected]
            indices = np.flatnonzero(selected)
            if not len(indices):
                continue
            if self._panel_type == "elevation-profile":
                values = profile.elevations_deg[indices]
                self._axes.axhline(
                    station.minimum_elevation_deg,
                    color="#c74343",
                    linestyle="--",
                    linewidth=1.0,
                    label="Station mask",
                )
            elif self._panel_type == "azimuth-profile":
                values = profile.azimuths_deg[indices]
                values = np.asarray(values, dtype=float).copy()
                breaks = np.flatnonzero(np.abs(np.diff(values)) > 180.0) + 1
                values[breaks] = np.nan
            else:
                if profile.slant_ranges_km is None:
                    continue
                values = profile.slant_ranges_km[indices]
            values = np.asarray(values, dtype=float).copy()
            if self._mask_filter_enabled:
                below_mask = (
                    profile.elevations_deg[indices] < station.minimum_elevation_deg
                )
                values[below_mask] = np.nan
            self._axes.plot(
                self._axis_times(times),
                values,
                linewidth=1.3,
                label=f"{station.name} · segment",
            )

    def _draw_pass_strip(self, result: StationAccess) -> None:
        if self._axes is None:
            return
        intervals = self._visible_intervals(result)
        self._axes.set_ylim(0.0, 1.0)
        seen_boundary_labels: set[str] = set()
        for index, interval in enumerate(intervals):
            color = (
                "#d6e8ff"
                if _interval_key(interval)
                == self._selection_context.selection.interval_key
                else "#e8f3ff"
            )
            self._axes.broken_barh(
                [(self._axis_time(interval.start_s), self._axis_duration(interval))],
                (0.25, 0.5),
                facecolors=color,
                edgecolors="#77a8e8",
                label="Access interval" if index == 0 else None,
            )
            boundary_markers = (
                (
                    interval.start_s,
                    interval.clipped_at_start,
                    interval.limited_by_gap_at_start,
                ),
                (
                    interval.end_s,
                    interval.clipped_at_end,
                    interval.limited_by_gap_at_end,
                ),
            )
            for epoch, clipped, gap_limited in boundary_markers:
                if self._time_range is None or not (
                    self._time_range.start_s <= epoch <= self._time_range.end_s
                ):
                    continue
                if clipped or gap_limited:
                    boundary_label = "OEM boundary" if clipped else "Segment gap"
                    self._axes.axvline(
                        self._axis_time(epoch),
                        color="#a45b20" if clipped else "#7a5195",
                        linestyle=":" if clipped else "--",
                        linewidth=1.0,
                        label=(
                            boundary_label
                            if boundary_label not in seen_boundary_labels
                            else None
                        ),
                    )
                    seen_boundary_labels.add(boundary_label)

    def _on_strip_click(self, event: Any) -> None:
        if (
            event.button != MouseButton.LEFT
            or event.inaxes is not self._axes
            or event.xdata is None
        ):
            return
        station = self._selected_station()
        result = self._results.get(station.station_id) if station else None
        if result is None:
            return
        epoch = self._cursor.t_start + event.xdata * self._time_unit.get_divisor_s()
        interval = next(
            (
                item
                for item in self._visible_intervals(result)
                if item.start_s <= epoch <= item.end_s
            ),
            None,
        )
        self._selection_context.select_interval(
            None if interval is None else _interval_key(interval)
        )
        self._draw()

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
        if station is None:
            message = "No ground stations are configured. Add a station to continue."
        elif not self._oem_loaded or self._source is None:
            message = "Load an Earth-centered OEM to view station analysis."
        elif self._time_range is None and self._panel_type != "station-status":
            message = "The current Plot Range does not overlap OEM coverage."
        else:
            result = self._results.get(station.station_id)
            message = (
                result.limitation
                if result is not None and result.limitation
                else ""
            )
            if self._panel_type == "pass-strip" and result is not None:
                intervals = self._visible_intervals(result)
                if not intervals and not result.intervals:
                    message = "No access intervals in OEM coverage meet this station's mask."
                elif not intervals:
                    message = "No access intervals overlap the current Plot Range."
            elif self._panel_type in _PROFILE_TYPES and result is not None:
                if not result.look_angle_profiles and not message:
                    message = "No station profile samples are available in this range."
        if self._status_label is not None:
            self._status_label.SetLabel(message)

    def _update_status_metrics(self) -> None:
        self._update_status_text()
        station = self._selected_station()
        if station is None or not self._oem_loaded or self._source is None:
            metrics_text = ""
        else:
            try:
                metrics = current_station_metrics(
                    station,
                    self._cursor,
                    self._current_time_s,
                    self._source,
                    self._access_cache.position_cache,
                )
            except GroundTrackPreparationError as error:
                if self._status_label is not None:
                    self._status_label.SetLabel(str(error))
                metrics = None
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
            "pass-strip": "Pass Strip",
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


def _interval_key(interval: AccessInterval) -> tuple[float, float]:
    return interval.start_s, interval.end_s
