"""Ground Station Access elevation graph and live station readouts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import wx
from matplotlib.axes import Axes
from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
import numpy as np

from ephem_toolkit.core import time_utils

from .. import cursor as playback_cursor
from ..ground_stations import GroundStation
from ..ground_track import GroundTrackSource, GroundTrackPreparationError
from ..series import OrbitSeries
from ..station_access import (
    StationAccess,
    StationAccessCache,
    current_station_metrics,
)
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit
from .plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    decimate_indices,
    set_shared_x_limits,
    time_bounds_to_axis,
)


def _utc_label(time_s: float) -> str:
    return time_utils.datetime_to_iso8601(
        time_utils.tt_s_to_datetime(time_s), fractional_second_places=0
    )


class GroundStationAccessView:
    """Display selected-station elevation and shared-clock metrics."""

    name = "ground-station-access"

    def __init__(
        self,
        parent: wx.Window,
        source: GroundTrackSource | None,
        cursor: playback_cursor.OemCursor,
        stations: Sequence[GroundStation],
        time_unit: TimeUnit,
        object_name: str,
        *,
        oem_loaded: bool,
        on_seek: Callable[[float], None],
        on_station_manager: Callable[[], None],
        access_cache: StationAccessCache,
    ) -> None:
        self._parent = parent
        self._source = source
        self._cursor = cursor
        self._stations = tuple(stations)
        self._time_unit = time_unit
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_seek = on_seek
        self._on_station_manager = on_station_manager
        self._access_cache = access_cache
        self._current_time_s = cursor.t_start
        self._selected_station_id = (
            self._stations[0].station_id if self._stations else None
        )
        self._panel: wx.Panel | None = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._figure: Figure | None = None
        self._axes = None
        self._station_choice: wx.Choice | None = None
        self._metrics_label: wx.StaticText | None = None
        self._pass_label: wx.StaticText | None = None
        self._status_label: wx.StaticText | None = None
        self._access_results: tuple[StationAccess, ...] = ()
        self._preparation_error: str | None = None
        self._time_range_bounds: ResolvedTimeRange | None = None
        self._time_range_coverage = (cursor.t_start, cursor.t_end)
        self._time_range_applied = False
        self._prepare_access()

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        self._panel = panel
        sizer = wx.BoxSizer(wx.VERTICAL)
        header = wx.StaticText(
            panel,
            wx.ID_ANY,
            f"Ground Station Access — {self._object_name}",
        )
        header.SetName("Ground Station Access heading")
        sizer.Add(header, 0, wx.EXPAND | wx.ALL, 8)

        selection_row = wx.BoxSizer(wx.HORIZONTAL)
        selection_row.Add(
            wx.StaticText(panel, wx.ID_ANY, "Station"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6,
        )
        self._station_choice = wx.Choice(panel, wx.ID_ANY)
        self._station_choice.SetName("Selected ground station")
        self._station_choice.Bind(wx.EVT_CHOICE, self._on_station_selected)
        selection_row.Add(self._station_choice, 1, wx.EXPAND | wx.RIGHT, 8)
        manage = wx.Button(panel, wx.ID_ANY, "Manage Ground Stations")
        manage.SetName("Manage ground stations")
        manage.Bind(wx.EVT_BUTTON, lambda _event: self._on_station_manager())
        selection_row.Add(manage, 0)
        sizer.Add(selection_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self._status_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._status_label.SetName("Ground station access status")
        sizer.Add(self._status_label, 0, wx.EXPAND | wx.ALL, 8)
        self._metrics_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._metrics_label.SetName("Current ground station metrics")
        sizer.Add(self._metrics_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._pass_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._pass_label.SetName("Previous and next access passes")
        sizer.Add(self._pass_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._figure = Figure(figsize=(9.0, 4.5), dpi=100)
        self._axes = self._figure.add_subplot(1, 1, 1)
        self._canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, self._figure)
        self._canvas.mpl_connect("button_press_event", self._on_plot_click)
        sizer.Add(self._canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self._refresh_station_choice()
        self._draw_elevation_plot()
        self.update(self._current_time_s)
        return panel

    def update(self, t_s: float, /) -> None:
        self._current_time_s = t_s
        if self._axes is not None and self._canvas is not None:
            cursor_x = (t_s - self._cursor.t_start) / self._time_unit.get_divisor_s()
            for line in self._axes.lines:
                if line.get_gid() == "playback-cursor":
                    line.set_xdata([cursor_x, cursor_x])
                    line.set_visible(
                        not self._time_range_applied
                        or (
                            self._time_range_bounds is not None
                            and self._time_range_bounds.start_s
                            <= t_s
                            <= self._time_range_bounds.end_s
                        )
                    )
            self._canvas.draw_idle()
        station = self._selected_station()
        if station is None:
            self._set_labels(
                "No ground stations are configured. Add a station to calculate access.",
                "",
                "",
            )
            return
        if not self._oem_loaded:
            self._set_labels("Load an Earth-centered OEM to calculate access.", "", "")
            return
        if self._preparation_error:
            self._set_labels(
                self._preparation_error, "Current metrics unavailable.", ""
            )
            return
        station_result = self._result_for(station.station_id)
        if station_result is not None and station_result.limitation:
            self._set_labels(station_result.limitation, "", "")
        else:
            self._set_labels("", "", "")
        try:
            metrics = (
                current_station_metrics(
                    station,
                    self._cursor,
                    t_s,
                    self._source,
                    self._access_cache.position_cache,
                )
                if self._source is not None
                else None
            )
        except GroundTrackPreparationError as error:
            self._set_labels(str(error), "Current metrics unavailable.", "")
            return
        if metrics is None:
            self._set_labels(
                "Current OEM state unavailable (outside coverage or in a segment gap).",
                "Azimuth, elevation, and range are unavailable.",
                self._pass_summary(station),
            )
            return
        self._set_labels(
            "",
            (
                f"{'Access' if metrics.access else 'No access'} · "
                f"Mask {station.minimum_elevation_deg}° · "
                f"Azimuth {metrics.azimuth_deg:.1f}° · "
                f"Elevation {metrics.elevation_deg:.1f}° · "
                f"Slant range {metrics.slant_range_km:.1f} km"
            ),
            self._pass_summary(station),
        )

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        """Refresh access histories after station definitions change."""
        selected = self._selected_station_id
        self._stations = tuple(stations)
        self._selected_station_id = (
            selected
            if any(item.station_id == selected for item in stations)
            else (stations[0].station_id if stations else None)
        )
        self._prepare_access()
        self._refresh_station_choice()
        self._draw_elevation_plot()
        self.update(self._current_time_s)

    def set_oem(
        self,
        source: GroundTrackSource | None,
        cursor: playback_cursor.OemCursor,
        object_name: str,
        *,
        oem_loaded: bool,
    ) -> None:
        """Refresh prepared passes when the application loads another OEM."""
        self._source = source
        self._cursor = cursor
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._current_time_s = cursor.t_start
        self._time_range_bounds = None
        self._time_range_coverage = (cursor.t_start, cursor.t_end)
        self._time_range_applied = False
        self._prepare_access()
        self._draw_elevation_plot()
        self.update(self._current_time_s)

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        was_empty = self._time_range_applied and self._time_range_bounds is None
        self._time_range_bounds = bounds
        self._time_range_coverage = coverage
        self._time_range_applied = True
        if was_empty != (bounds is None):
            self._draw_elevation_plot()
            return
        self._apply_time_range()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def close(self) -> None:
        self._canvas = None
        self._figure = None
        self._axes = None
        self._panel = None

    def _prepare_access(self) -> None:
        if not self._oem_loaded or self._source is None:
            self._access_results = ()
            self._preparation_error = None
            return
        results = []
        self._preparation_error = None
        for station in self._stations:
            try:
                results.append(
                    self._access_cache.prepare(self._source, self._cursor, station)
                )
            except GroundTrackPreparationError as error:
                results.append(StationAccess(station, (), str(error)))
        self._access_results = tuple(results)

    def _draw_elevation_plot(self) -> None:
        if self._axes is None or self._figure is None:
            return
        axes = self._axes
        axes.clear()
        if not self._stations:
            axes.text(
                0.5,
                0.5,
                "No ground stations configured",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
            axes.set_axis_off()
        elif not self._oem_loaded:
            axes.text(
                0.5,
                0.5,
                "Load an Earth-centered OEM to view elevation",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
            axes.set_axis_off()
        else:
            axes.set_axis_on()
            divisor = self._time_unit.get_divisor_s()
            station = self._selected_station()
            result = (
                self._result_for(station.station_id) if station is not None else None
            )
            axes.set_xlim(
                0.0,
                max(
                    (self._cursor.t_end - self._cursor.t_start) / divisor,
                    1e-9,
                ),
            )
            axes.set_xlabel(self._time_unit.get_axis_label())
            axes.set_ylabel("Elevation (degrees)")
            if self._time_range_applied and self._time_range_bounds is None:
                axes.text(
                    0.5,
                    0.5,
                    "No data in Plot Range",
                    ha="center",
                    va="center",
                    transform=axes.transAxes,
                )
            elif station is None:
                axes.text(
                    0.5,
                    0.5,
                    "Select a ground station to view elevation",
                    ha="center",
                    va="center",
                    transform=axes.transAxes,
                )
            elif result is None or not (
                result.look_angle_profiles or result.elevation_profiles
            ):
                message = (
                    result.limitation
                    if result is not None and result.limitation
                    else "Elevation profile unavailable"
                )
                axes.text(
                    0.5,
                    0.5,
                    message,
                    ha="center",
                    va="center",
                    transform=axes.transAxes,
                )
            else:
                self._draw_elevation_graph(axes, station, result, divisor)
            axes.grid(axis="both", alpha=0.25)
        self._figure.tight_layout()
        self._apply_time_range()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _draw_elevation_graph(
        self,
        axes: Axes,
        station: GroundStation,
        result: StationAccess,
        divisor: float,
    ) -> None:
        axes.set_title(f"{station.name} elevation")
        has_line = False
        mask = station.minimum_elevation_deg
        profiles = result.look_angle_profiles or result.elevation_profiles
        for profile in profiles:
            times = profile.times_s
            elevations = profile.elevations_deg
            valid_indices = np.flatnonzero(np.isfinite(times) & np.isfinite(elevations))
            if not valid_indices.size:
                continue
            run_breaks = np.flatnonzero(np.diff(valid_indices) > 1) + 1
            for run_indices in np.split(valid_indices, run_breaks):
                run_times = times[run_indices]
                run_elevations = elevations[run_indices]
                for interval in result.intervals:
                    start_s = max(interval.start_s, float(run_times[0]))
                    end_s = min(interval.end_s, float(run_times[-1]))
                    if start_s > end_s:
                        continue
                    interior_start = np.searchsorted(run_times, start_s, side="right")
                    interior_end = np.searchsorted(run_times, end_s, side="left")
                    plot_times = np.concatenate(
                        (
                            np.asarray([start_s]),
                            run_times[interior_start:interior_end],
                            np.asarray([end_s]),
                        )
                    )
                    plot_elevations = np.interp(plot_times, run_times, run_elevations)
                    start_limited = (
                        interval.clipped_at_start or interval.limited_by_gap_at_start
                    )
                    end_limited = (
                        interval.clipped_at_end or interval.limited_by_gap_at_end
                    )
                    if start_s == interval.start_s and not start_limited:
                        plot_elevations[0] = mask
                    if end_s == interval.end_s and not end_limited:
                        plot_elevations[-1] = mask
                    visible_indices = np.flatnonzero(plot_elevations >= mask)
                    visible_breaks = np.flatnonzero(np.diff(visible_indices) > 1) + 1
                    for visible_run in np.split(visible_indices, visible_breaks):
                        if not visible_run.size:
                            continue
                        samples = np.column_stack(
                            (plot_times[visible_run], plot_elevations[visible_run])
                        )
                        display_indices = decimate_indices(
                            samples, MAX_DISPLAY_POINTS_PER_SEGMENT
                        )
                        axes.plot(
                            (samples[display_indices, 0] - self._cursor.t_start)
                            / divisor,
                            samples[display_indices, 1],
                            color="#2f7ebc",
                            linewidth=1.2,
                            marker="." if len(display_indices) == 1 else "None",
                            label="Elevation" if not has_line else "_nolegend_",
                        )
                        has_line = True

        axes.axhline(
            mask,
            color="#c74343",
            linestyle="--",
            linewidth=1.0,
            label=f"Minimum elevation ({mask}°)",
        )
        if has_line:
            interval_labels: set[str] = set()
            for interval in result.intervals:
                left = (interval.start_s - self._cursor.t_start) / divisor
                right = (interval.end_s - self._cursor.t_start) / divisor
                gap_limited = (
                    interval.limited_by_gap_at_start or interval.limited_by_gap_at_end
                )
                coverage_limited = interval.clipped_at_start or interval.clipped_at_end
                label = (
                    "Gap-limited access"
                    if gap_limited
                    else (
                        "Coverage-limited access"
                        if coverage_limited
                        else "Access interval"
                    )
                )
                axes.axvspan(
                    left,
                    right,
                    color="#2f7ebc",
                    alpha=0.12,
                    hatch="xx" if gap_limited else ("//" if coverage_limited else None),
                    label=label if label not in interval_labels else "_nolegend_",
                )
                interval_labels.add(label)
        else:
            axes.text(
                0.5,
                0.5,
                "No elevation at or above the minimum mask in OEM coverage",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
        axes.axvline(
            (self._current_time_s - self._cursor.t_start) / divisor,
            color="#222222",
            linestyle="--",
            linewidth=1,
            label="Playback time",
            gid="playback-cursor",
        )

        axes.set_ylim(0.0, 95.0)
        axes.legend(loc="upper right", fontsize="small")

    def _apply_time_range(self) -> None:
        if self._axes is None:
            return
        limits = time_bounds_to_axis(
            self._time_range_bounds,
            self._time_range_coverage,
            self._cursor.t_start,
            self._time_unit.get_divisor_s(),
        )
        set_shared_x_limits((self._axes,), limits)
        for line in self._axes.lines:
            if line.get_gid() == "playback-cursor":
                line.set_visible(
                    not self._time_range_applied
                    or (
                        self._time_range_bounds is not None
                        and self._time_range_bounds.start_s
                        <= self._current_time_s
                        <= self._time_range_bounds.end_s
                    )
                )

    def _on_plot_click(self, event) -> None:
        if (
            event.button != MouseButton.LEFT
            or event.inaxes is not self._axes
            or event.xdata is None
            or not self._oem_loaded
            or not self._stations
        ):
            return
        target = self._cursor.t_start + event.xdata * self._time_unit.get_divisor_s()
        self._on_seek(min(self._cursor.t_end, max(self._cursor.t_start, target)))

    def _on_station_selected(self, _event: wx.CommandEvent) -> None:
        if self._station_choice is None:
            return
        index = self._station_choice.GetSelection()
        if 0 <= index < len(self._stations):
            self._selected_station_id = self._stations[index].station_id
            self._draw_elevation_plot()
            self.update(self._current_time_s)

    def _refresh_station_choice(self) -> None:
        if self._station_choice is None:
            return
        self._station_choice.Clear()
        selected_index = 0
        for index, station in enumerate(self._stations):
            self._station_choice.Append(station.name)
            if station.station_id == self._selected_station_id:
                selected_index = index
        if self._stations:
            self._station_choice.SetSelection(selected_index)

    def _selected_station(self) -> GroundStation | None:
        return next(
            (
                station
                for station in self._stations
                if station.station_id == self._selected_station_id
            ),
            None,
        )

    def _result_for(self, station_id: str) -> StationAccess | None:
        return next(
            (
                result
                for result in self._access_results
                if result.station.station_id == station_id
            ),
            None,
        )

    def _pass_summary(self, station: GroundStation) -> str:
        result = self._result_for(station.station_id)
        if result is None:
            return ""
        if result.limitation:
            return result.limitation
        previous = [
            interval
            for interval in result.intervals
            if interval.end_s < self._current_time_s
        ]
        upcoming = [
            interval
            for interval in result.intervals
            if interval.start_s > self._current_time_s
        ]
        active = next(
            (
                interval
                for interval in result.intervals
                if interval.start_s <= self._current_time_s <= interval.end_s
            ),
            None,
        )
        previous_interval = active or (previous[-1] if previous else None)
        next_interval = upcoming[0] if upcoming else None
        previous_label = "Previous pass: none in OEM coverage"
        if previous_interval is not None:
            coverage_note = (
                " · in progress at coverage start"
                if previous_interval.clipped_at_start
                else ""
            )
            if previous_interval.clipped_at_end:
                coverage_note += " · continues beyond coverage"
            previous_label = (
                f"Previous/active: {_utc_label(previous_interval.start_s)} – "
                f"{_utc_label(previous_interval.end_s)} "
                f"({(previous_interval.end_s - previous_interval.start_s) / 60.0:.1f} min, "
                f"peak {previous_interval.peak_elevation_deg:.1f}° at "
                f"{_utc_label(previous_interval.peak_time_s)}, "
                f"minimum range {previous_interval.minimum_range_km:.1f} km)"
                f"{coverage_note}"
            )
        next_label = "Next pass: none in OEM coverage"
        if next_interval is not None:
            coverage_note = (
                " · in progress at coverage start"
                if next_interval.clipped_at_start
                else ""
            )
            if next_interval.clipped_at_end:
                coverage_note += " · continues beyond coverage"
            next_label = (
                f"Next: {_utc_label(next_interval.start_s)} – "
                f"{_utc_label(next_interval.end_s)} "
                f"({(next_interval.end_s - next_interval.start_s) / 60.0:.1f} min, "
                f"peak {next_interval.peak_elevation_deg:.1f}° at "
                f"{_utc_label(next_interval.peak_time_s)}, "
                f"minimum range {next_interval.minimum_range_km:.1f} km)"
                f"{coverage_note}"
            )
        return f"{previous_label}\n{next_label}"

    def _set_labels(self, status: str, metrics: str, passes: str) -> None:
        if self._status_label is not None:
            self._status_label.SetLabel(status)
        if self._metrics_label is not None:
            station = self._selected_station()
            if station is not None:
                metrics = (
                    f"{station.name} · {station.latitude_deg:.4f}°, "
                    f"{station.longitude_deg:.4f}° · {station.altitude_m:.1f} m "
                    f"(WGS-84 ellipsoid)\n{metrics}"
                )
            self._metrics_label.SetLabel(metrics)
        if self._pass_label is not None:
            self._pass_label.SetLabel(passes)
