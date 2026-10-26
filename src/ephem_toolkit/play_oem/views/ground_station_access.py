"""Ground Station Access timeline and live station readouts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

from ephem_toolkit.core import time_utils

from .. import cursor as playback_cursor
from ..ground_stations import GroundStation
from ..ground_track import GroundTrackSource, GroundTrackPreparationError
from ..series import OrbitSeries
from ..station_access import (
    AccessInterval,
    StationAccess,
    StationAccessCache,
    current_station_metrics,
)
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit


def _utc_label(time_s: float) -> str:
    return time_utils.datetime_to_iso8601(
        time_utils.tt_s_to_datetime(time_s), fractional_second_places=0
    )


class GroundStationAccessView:
    """Display multi-station access intervals and shared-clock metrics."""

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
        self._canvas.mpl_connect("button_press_event", self._on_timeline_click)
        sizer.Add(self._canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self._refresh_station_choice()
        self._draw_timeline()
        self.update(self._current_time_s)
        return panel

    def update(self, t_s: float, /) -> None:
        self._current_time_s = t_s
        if self._axes is not None and self._canvas is not None:
            cursor_x = (t_s - self._cursor.t_start) / self._time_unit.get_divisor_s()
            for line in self._axes.lines:
                if line.get_gid() == "playback-cursor":
                    line.set_xdata([cursor_x, cursor_x])
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
        self._draw_timeline()
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
        self._prepare_access()
        self._draw_timeline()
        self.update(self._current_time_s)

    def set_time_range(
        self, _bounds: ResolvedTimeRange | None, _coverage: tuple[float, float], /
    ) -> None:
        return

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

    def _draw_timeline(self) -> None:
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
                "Load an Earth-centered OEM to view access intervals",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
            axes.set_axis_off()
        else:
            axes.set_axis_on()
            divisor = self._time_unit.get_divisor_s()
            for row, station in enumerate(self._stations):
                result = self._result_for(station.station_id)
                intervals = result.intervals if result is not None else ()
                for interval in intervals:
                    self._draw_interval(row, interval, divisor)
                if not intervals:
                    message = (
                        result.limitation
                        if result is not None and result.limitation
                        else "No access in OEM coverage"
                    )
                    axes.text(
                        0.0,
                        row,
                        f"  {message}",
                        va="center",
                        ha="left",
                        fontsize="small",
                        color="#555555",
                    )
            axes.set_yticks(np.arange(len(self._stations)))
            axes.set_yticklabels([station.name for station in self._stations])
            axes.set_ylim(len(self._stations) - 0.5, -0.5)
            axes.set_xlim(
                0.0,
                max(
                    (self._cursor.t_end - self._cursor.t_start) / divisor,
                    1e-9,
                ),
            )
            axes.set_xlabel(self._time_unit.get_axis_label())
            axes.grid(axis="x", alpha=0.25)
            axes.legend(
                handles=[
                    Patch(
                        facecolor="#2f7ebc",
                        edgecolor="#1e5d8a",
                        label="Geometric access",
                    ),
                    Line2D(
                        [0], [0], color="#222222", linestyle="--", label="Playback time"
                    ),
                    Patch(
                        facecolor="#2f7ebc",
                        edgecolor="#1e5d8a",
                        hatch="//",
                        label="Coverage-limited interval",
                    ),
                ],
                loc="upper right",
                fontsize="small",
            )
            axes.axvline(
                (self._current_time_s - self._cursor.t_start) / divisor,
                color="#222222",
                linestyle="--",
                linewidth=1,
                gid="playback-cursor",
            )
        self._figure.tight_layout()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _draw_interval(
        self, row: int, interval: AccessInterval, divisor: float
    ) -> None:
        assert self._axes is not None
        left = (interval.start_s - self._cursor.t_start) / divisor
        width = max((interval.end_s - interval.start_s) / divisor, 1.0e-9)
        clipped = interval.clipped_at_start or interval.clipped_at_end
        gap_limited = interval.limited_by_gap_at_start or interval.limited_by_gap_at_end
        self._axes.barh(
            row,
            width,
            left=left,
            height=0.55,
            color="#2f7ebc",
            hatch="xx" if gap_limited else ("//" if clipped else None),
            edgecolor="#1e5d8a",
            linewidth=0.7,
        )

    def _on_timeline_click(self, event) -> None:
        if (
            event.inaxes is self._axes
            and event.xdata is not None
            and self._oem_loaded
            and self._stations
        ):
            target = (
                self._cursor.t_start + event.xdata * self._time_unit.get_divisor_s()
            )
            self._on_seek(min(self._cursor.t_end, max(self._cursor.t_start, target)))

    def _on_station_selected(self, _event: wx.CommandEvent) -> None:
        if self._station_choice is None:
            return
        index = self._station_choice.GetSelection()
        if 0 <= index < len(self._stations):
            self._selected_station_id = self._stations[index].station_id
            self.update(self._current_time_s)
            self._draw_timeline()

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
