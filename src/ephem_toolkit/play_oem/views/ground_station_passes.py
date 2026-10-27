"""Plot-range-filtered pass table and sky-oriented station view."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import math
from typing import Any

import numpy as np
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ..display_time import UTC_DISPLAY, format_tt

from .. import cursor as playback_cursor
from ..ground_stations import GroundStation
from ..ground_track import GroundTrackSource, GroundTrackPreparationError
from ..series import OrbitSeries
from ..station_access import (
    AccessInterval,
    LookAngleProfile,
    StationAccess,
    StationAccessCache,
)
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit

_TABLE_COLUMN_WIDTHS = (190, 90, 150, 155, 155)
_TABLE_PANEL_MIN_WIDTH = sum(_TABLE_COLUMN_WIDTHS)
_SKY_PANEL_MIN_WIDTH = 320


def _can_fit_side_by_side(available_width: int, minimum_width: int) -> bool:
    return available_width >= minimum_width


def _interval_key(interval: AccessInterval) -> tuple[float, float]:
    return interval.start_s, interval.end_s


def _coverage_label(interval: AccessInterval) -> str:
    labels = []
    if interval.clipped_at_start:
        labels.append("Starts at OEM boundary")
    if interval.clipped_at_end:
        labels.append("Ends at OEM boundary")
    if interval.limited_by_gap_at_start:
        labels.append("Gap-limited start")
    if interval.limited_by_gap_at_end:
        labels.append("Gap-limited end")
    return "; ".join(labels) if labels else "Complete"


def _utc_label(time_s: float) -> str:
    """Retain the fixed-UTC formatter used by older callers and tests."""
    return format_tt(
        time_s, UTC_DISPLAY, fractional_second_places=0
    ).removesuffix(" UTC")


class GroundStationPassesView:
    """Inspect cached pass details and their topocentric sky paths."""

    name = "ground-station-passes"
    heading = "Ground Station Passes"

    def __init__(
        self,
        parent: wx.Window,
        source: GroundTrackSource | None,
        cursor: playback_cursor.OemCursor,
        stations: Sequence[GroundStation],
        object_name: str,
        *,
        oem_loaded: bool,
        on_seek: Callable[[float], None],
        on_focus_pass: Callable[[float, float], None],
        on_station_manager: Callable[[], None],
        access_cache: StationAccessCache,
        selection_context: StationAnalysisContext | None = None,
        limit_to_range: bool = False,
        initial_range: ResolvedTimeRange | None = None,
        initial_station_id: str | None = None,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        self._parent = parent
        self._source = source
        self._cursor = cursor
        self._stations = tuple(stations)
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._on_seek = on_seek
        self._on_focus_pass = on_focus_pass
        self._on_station_manager = on_station_manager
        self._access_cache = access_cache
        self._selection_context = selection_context
        self._limit_to_range = limit_to_range
        self._prepare_range = initial_range
        self._display_time_zone = display_time_zone
        self._current_time_s = cursor.t_start
        context_station_id = (
            selection_context.selection.station_id
            if selection_context is not None
            else None
        )
        requested_station_id = initial_station_id or context_station_id
        self._selected_station_id = (
            requested_station_id
            if any(
                station.station_id == requested_station_id for station in stations
            )
            else (
                None
                if requested_station_id is not None
                else (self._stations[0].station_id if self._stations else None)
            )
        )
        self._missing_initial_station = (
            requested_station_id is not None and self._selected_station_id is None
        )
        self._selected_interval_key = (
            selection_context.selection.interval_key
            if selection_context is not None
            and selection_context.selection.station_id == self._selected_station_id
            else None
        )
        self._visible_intervals: tuple[AccessInterval, ...] = ()
        self._access_results: tuple[StationAccess, ...] = ()
        self._time_range_bounds: ResolvedTimeRange | None = None
        self._time_range_applied = False
        self._range_label_text = ""
        self._coverage_readout_text = ""
        self._status_text = ""
        self._sky_summary_text = ""
        self._panel: wx.Panel | None = None
        self._analysis_panel: wx.Panel | None = None
        self._analysis_sizer: wx.BoxSizer | None = None
        self._table_panel: wx.Panel | None = None
        self._sky_panel: wx.Panel | None = None
        self._table: wx.ListCtrl | None = None
        self._station_choice: wx.Choice | None = None
        self._range_label: wx.StaticText | None = None
        self._coverage_label: wx.StaticText | None = None
        self._status_label: wx.StaticText | None = None
        self._sky_summary: wx.StaticText | None = None
        self._focus_button: wx.Button | None = None
        self._seek_button: wx.Button | None = None
        self._figure: Figure | None = None
        self._axes: Any = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._playback_marker: Any = None
        self._refreshing_rows = False
        self._layout_orientation: int | None = None
        self._context_unsubscribe: Callable[[], None] = lambda: None
        self._prepare_access()
        if selection_context is not None:
            self._context_unsubscribe = selection_context.subscribe(
                self._on_context_selection
            )
            if self._selected_station_id != context_station_id:
                selection_context.select_station(self._selected_station_id)

    @property
    def selected_station_id(self) -> str | None:
        """Stable station identity selected in this panel."""
        return self._selected_station_id

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        self._panel = panel
        root = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(
            panel, wx.ID_ANY, f"{self.heading} — {self._object_name}"
        )
        heading.SetName(f"{self.heading} heading")
        root.Add(heading, 0, wx.EXPAND | wx.ALL, 8)

        controls = wx.BoxSizer(wx.HORIZONTAL)
        controls.Add(
            wx.StaticText(panel, wx.ID_ANY, "Station"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6,
        )
        self._station_choice = wx.Choice(panel, wx.ID_ANY)
        self._station_choice.SetName(f"{self.heading} station")
        self._station_choice.Bind(wx.EVT_CHOICE, self._on_station_selected)
        controls.Add(self._station_choice, 1, wx.EXPAND | wx.RIGHT, 8)
        manage = wx.Button(panel, wx.ID_ANY, "Manage Ground Stations")
        manage.SetName("Manage ground stations from passes")
        manage.Bind(wx.EVT_BUTTON, lambda _event: self._on_station_manager())
        controls.Add(manage, 0)
        root.Add(controls, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self._range_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._range_label.SetName(f"{self.heading} Plot Range")
        root.Add(self._range_label, 0, wx.EXPAND | wx.ALL, 8)
        self._coverage_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._coverage_label.SetName(f"{self.heading} OEM coverage")
        root.Add(self._coverage_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._status_label = wx.StaticText(panel, wx.ID_ANY, "")
        self._status_label.SetName(f"{self.heading} status")
        root.Add(self._status_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._analysis_panel = wx.Panel(panel, wx.ID_ANY)
        self._analysis_sizer = wx.BoxSizer(wx.VERTICAL)
        self._analysis_panel.SetSizer(self._analysis_sizer)
        self._table_panel = self._build_table_panel(self._analysis_panel)
        self._sky_panel = self._build_sky_panel(self._analysis_panel)
        root.Add(self._analysis_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(root)
        self._refresh_station_choice()
        self._update_coverage_readout()
        self._refresh_rows()
        self._update_analysis_layout()
        panel.Bind(wx.EVT_SIZE, self._on_panel_size)
        self.update(self._current_time_s)
        return panel

    def _build_table_panel(self, parent: wx.Window) -> wx.Panel:
        panel = wx.Panel(parent, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._table = wx.ListCtrl(
            panel,
            wx.ID_ANY,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.LC_VRULES,
        )
        self._table.SetName(f"{self.heading} table")
        self._table.InsertColumn(0, "Pass · UTC")
        self._table.InsertColumn(1, "Duration")
        self._table.InsertColumn(2, "Peak elevation")
        self._table.InsertColumn(3, "Minimum range")
        self._table.InsertColumn(4, "Coverage")
        for column, width in enumerate(_TABLE_COLUMN_WIDTHS):
            self._table.SetColumnWidth(column, panel.FromDIP(width))
        self._table.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_interval_selected)
        sizer.Add(self._table, 1, wx.EXPAND | wx.ALL, 2)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        self._focus_button = wx.Button(panel, wx.ID_ANY, "Focus pass")
        self._focus_button.SetName("Focus selected pass")
        self._focus_button.Bind(
            wx.EVT_BUTTON, lambda _event: self._focus_selected_pass()
        )
        self._focus_button.Enable(False)
        self._seek_button = wx.Button(panel, wx.ID_ANY, "Seek to peak")
        self._seek_button.SetName("Seek playback to selected pass peak")
        self._seek_button.Bind(wx.EVT_BUTTON, lambda _event: self._seek_to_peak())
        self._seek_button.Enable(False)
        actions.Add(self._focus_button, 0, wx.RIGHT, 6)
        actions.Add(self._seek_button, 0)
        sizer.Add(actions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 2)
        panel.SetSizer(sizer)
        panel.SetMinSize(panel.FromDIP(wx.Size(_TABLE_PANEL_MIN_WIDTH, 160)))
        return panel

    def _build_sky_panel(self, parent: wx.Window) -> wx.Panel:
        panel = wx.Panel(parent, wx.ID_ANY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._figure = Figure(figsize=(5.0, 4.5), dpi=100)
        self._axes = self._figure.add_subplot(111, projection="polar")
        self._canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, self._figure)
        self._canvas.SetMinSize(panel.FromDIP(wx.Size(300, 330)))
        self._sky_summary = wx.StaticText(panel, wx.ID_ANY, "")
        self._sky_summary.SetName("Selected pass sky plot summary")
        self._sky_summary.Wrap(panel.FromDIP(420))
        sizer.Add(self._canvas, 1, wx.EXPAND | wx.ALL, 2)
        sizer.Add(self._sky_summary, 0, wx.EXPAND | wx.ALL, 6)
        panel.SetSizer(sizer)
        panel.SetMinSize(panel.FromDIP(wx.Size(_SKY_PANEL_MIN_WIDTH, 400)))
        panel.Bind(wx.EVT_SIZE, self._on_sky_panel_size)
        return panel

    def _on_panel_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        wx.CallAfter(self._update_analysis_layout)

    def _on_sky_panel_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        wx.CallAfter(self._wrap_sky_summary)

    def _wrap_sky_summary(self) -> None:
        if self._sky_summary is None or self._sky_panel is None:
            return
        width = self._sky_panel.GetClientSize().width - self._sky_panel.FromDIP(12)
        if width > 0:
            self._sky_summary.Wrap(width)

    def _update_analysis_layout(self) -> None:
        if (
            self._analysis_panel is None
            or self._analysis_sizer is None
            or self._table_panel is None
            or self._sky_panel is None
        ):
            return
        minimum_width = self._analysis_panel.FromDIP(
            wx.Size(_TABLE_PANEL_MIN_WIDTH + _SKY_PANEL_MIN_WIDTH + 12, 1)
        ).width
        orientation = (
            wx.HORIZONTAL
            if _can_fit_side_by_side(
                self._analysis_panel.GetClientSize().width, minimum_width
            )
            else wx.VERTICAL
        )
        if orientation == self._layout_orientation:
            self._wrap_sky_summary()
            return
        self._layout_orientation = orientation
        self._analysis_sizer.Clear(False)
        self._analysis_sizer.SetOrientation(orientation)
        if orientation == wx.HORIZONTAL:
            self._analysis_sizer.Add(self._table_panel, 3, wx.EXPAND | wx.ALL, 2)
            self._analysis_sizer.Add(self._sky_panel, 2, wx.EXPAND | wx.ALL, 2)
        else:
            self._analysis_sizer.Add(self._table_panel, 1, wx.EXPAND | wx.ALL, 2)
            self._analysis_sizer.Add(self._sky_panel, 2, wx.EXPAND | wx.ALL, 2)
        self._analysis_panel.Layout()
        self._wrap_sky_summary()

    def _prepare_access(self) -> None:
        if not self._oem_loaded or self._source is None:
            self._access_results = ()
            return
        results = []
        bounds = None
        if self._limit_to_range:
            if self._prepare_range is None:
                self._access_results = tuple(
                    StationAccess(station, ()) for station in self._stations
                )
                return
            bounds = (self._prepare_range.start_s, self._prepare_range.end_s)
        for station in self._stations:
            try:
                results.append(
                    self._access_cache.prepare(
                        self._source, self._cursor, station, bounds
                    )
                )
            except GroundTrackPreparationError as error:
                results.append(StationAccess(station, (), str(error)))
        self._access_results = tuple(results)

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

    def _selected_interval(self) -> AccessInterval | None:
        if self._selected_interval_key is None:
            return None
        return next(
            (
                interval
                for interval in self._visible_intervals
                if _interval_key(interval) == self._selected_interval_key
            ),
            None,
        )

    def _refresh_rows(self) -> None:
        station = self._selected_station()
        result = self._result_for(station.station_id) if station is not None else None
        intervals = result.intervals if result is not None else ()
        if self._time_range_applied:
            bounds = self._time_range_bounds
            visible = (
                ()
                if bounds is None
                else tuple(
                    interval
                    for interval in intervals
                    if interval.start_s <= bounds.end_s
                    and interval.end_s >= bounds.start_s
                )
            )
        else:
            visible = tuple(intervals)
        previous_key = self._selected_interval_key
        self._visible_intervals = visible
        if not any(_interval_key(item) == previous_key for item in visible):
            active = next(
                (
                    item
                    for item in visible
                    if item.start_s <= self._current_time_s <= item.end_s
                ),
                None,
            )
            upcoming = next(
                (item for item in visible if item.start_s >= self._current_time_s),
                None,
            )
            selected = active or upcoming or (visible[0] if visible else None)
            self._selected_interval_key = (
                _interval_key(selected) if selected is not None else None
            )
        self._update_range_label()
        self._update_status(station, result)
        self._render_rows()
        self._draw_sky_plot()

    def _update_range_label(self) -> None:
        bounds = self._time_range_bounds
        if not self._time_range_applied:
            bounds = ResolvedTimeRange(self._cursor.t_start, self._cursor.t_end)
        if bounds is None:
            label = "Plot Range: no effective range overlaps OEM coverage"
        else:
            label = (
                f"Plot Range: {self._time_label(bounds.start_s)} – "
                f"{self._time_label(bounds.end_s)}"
            )
        self._range_label_text = label
        if self._range_label is not None:
            self._range_label.SetLabel(label)

    def _update_coverage_readout(self) -> None:
        if not self._oem_loaded or self._source is None:
            label = "OEM coverage: unavailable"
        else:
            label = (
                f"OEM coverage: {self._time_label(self._cursor.t_start)} – "
                f"{self._time_label(self._cursor.t_end)}"
            )
        self._coverage_readout_text = label
        if self._coverage_label is not None:
            self._coverage_label.SetLabel(label)

    def _update_status(
        self, station: GroundStation | None, result: StationAccess | None
    ) -> None:
        if station is None:
            if self._stations:
                message = (
                    "The requested station is no longer configured. "
                    "Select another station to inspect passes."
                    if self._missing_initial_station
                    else "Select a ground station to inspect passes."
                )
            else:
                message = "No ground stations are configured. Add a station to inspect passes."
        elif not self._oem_loaded or self._source is None:
            message = "Load an Earth-centered OEM to inspect station passes."
        elif result is None:
            message = "Pass history is unavailable."
        elif result.limitation:
            message = result.limitation
        elif not result.intervals:
            message = "No access intervals in OEM coverage meet this station's mask."
        elif self._time_range_applied and self._time_range_bounds is None:
            message = "The current Plot Range does not overlap OEM coverage."
        elif not self._visible_intervals:
            message = (
                "No access intervals overlap the current Plot Range. "
                "Widen the shared Plot Range to see more passes."
            )
        else:
            count = len(self._visible_intervals)
            message = (
                f"{count} access interval{'s' if count != 1 else ''} in Plot Range."
            )
        self._status_text = message
        if self._status_label is not None:
            self._status_label.SetLabel(message)

    def _render_rows(self) -> None:
        table = self._table
        if table is None:
            self._update_actions()
            return
        self._refreshing_rows = True
        try:
            table.DeleteAllItems()
            for row, interval in enumerate(self._visible_intervals):
                values = self._row_values(interval)
                item = table.InsertItem(row, values[0])
                for column, value in enumerate(values[1:], start=1):
                    table.SetItem(item, column, value)
                if _interval_key(interval) == self._selected_interval_key:
                    table.SetItemState(
                        item, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED
                    )
                    table.EnsureVisible(item)
        finally:
            self._refreshing_rows = False
        self._update_actions()

    def _row_values(self, interval: AccessInterval) -> tuple[str, ...]:
        uncertain_boundary = (
            interval.clipped_at_start
            or interval.clipped_at_end
            or interval.limited_by_gap_at_start
            or interval.limited_by_gap_at_end
        )
        duration = (
            ""
            if uncertain_boundary
            else f"{(interval.end_s - interval.start_s) / 60.0:.1f} min"
        )
        return (
            (
                f"{self._time_label(interval.start_s)} – "
                f"{self._time_label(interval.end_s)}"
            ),
            duration,
            f"{interval.peak_elevation_deg:.1f}° at "
            f"{self._time_label(interval.peak_time_s)}",
            f"{interval.minimum_range_km:.1f} km at "
            f"{self._time_label(interval.minimum_range_time_s)}",
            _coverage_label(interval),
        )

    def _update_actions(self) -> None:
        interval = self._selected_interval()
        if self._focus_button is not None:
            self._focus_button.Enable(
                interval is not None
                and math.isfinite(interval.start_s)
                and math.isfinite(interval.end_s)
            )
        if self._seek_button is not None:
            self._seek_button.Enable(
                interval is not None and math.isfinite(interval.peak_time_s)
            )

    def _on_station_selected(self, _event: wx.CommandEvent) -> None:
        if self._station_choice is None:
            return
        index = self._station_choice.GetSelection()
        if 0 <= index < len(self._stations):
            self.select_station_by_id(self._stations[index].station_id)

    def select_station_by_id(self, station_id: str) -> None:
        if not any(station.station_id == station_id for station in self._stations):
            return
        self._selected_station_id = station_id
        if self._station_choice is not None:
            index = next(
                i
                for i, item in enumerate(self._stations)
                if item.station_id == station_id
            )
            self._station_choice.SetSelection(index)
        self._missing_initial_station = False
        self._selected_interval_key = None
        if self._selection_context is not None:
            self._selection_context.select_station(station_id)
        self._refresh_rows()

    def _on_interval_selected(self, event: wx.ListEvent) -> None:
        if self._refreshing_rows:
            return
        row = event.GetIndex()
        if 0 <= row < len(self._visible_intervals):
            self._selected_interval_key = _interval_key(self._visible_intervals[row])
            if self._selection_context is not None:
                self._selection_context.select_interval(self._selected_interval_key)
            self._draw_sky_plot()
            self._update_actions()

    def _on_context_selection(
        self, selection: StationAnalysisSelection
    ) -> None:
        station_id = selection.station_id
        if station_id is not None and not any(
            station.station_id == station_id for station in self._stations
        ):
            return
        if (
            station_id == self._selected_station_id
            and selection.interval_key == self._selected_interval_key
        ):
            return
        station_changed = station_id != self._selected_station_id
        self._selected_station_id = station_id
        self._selected_interval_key = selection.interval_key
        if station_changed:
            self._missing_initial_station = False
            self._refresh_station_choice()
        self._refresh_rows()

    def _focus_selected_pass(self) -> None:
        interval = self._selected_interval()
        if interval is not None:
            self._on_focus_pass(interval.start_s, interval.end_s)

    def _seek_to_peak(self) -> None:
        interval = self._selected_interval()
        if interval is not None and math.isfinite(interval.peak_time_s):
            self._on_seek(interval.peak_time_s)

    def _profile_points(
        self, profile: LookAngleProfile, interval: AccessInterval
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        station = self._selected_station()
        if station is None:
            empty = np.asarray([], dtype=float)
            return empty, empty, empty
        points = {
            float(time_s): (float(azimuth), float(elevation))
            for time_s, azimuth, elevation in zip(
                profile.times_s, profile.azimuths_deg, profile.elevations_deg
            )
            if interval.start_s <= time_s <= interval.end_s
        }
        if (
            interval.start_azimuth_deg is not None
            and interval.start_elevation_deg is not None
            and profile.times_s[0] <= interval.start_s <= profile.times_s[-1]
        ):
            elevation = interval.start_elevation_deg
            if not interval.clipped_at_start and not interval.limited_by_gap_at_start:
                elevation = max(station.minimum_elevation_deg, elevation)
            points[interval.start_s] = (interval.start_azimuth_deg, elevation)
        if (
            interval.end_azimuth_deg is not None
            and interval.end_elevation_deg is not None
            and profile.times_s[0] <= interval.end_s <= profile.times_s[-1]
        ):
            elevation = interval.end_elevation_deg
            if not interval.clipped_at_end and not interval.limited_by_gap_at_end:
                elevation = max(station.minimum_elevation_deg, elevation)
            points[interval.end_s] = (interval.end_azimuth_deg, elevation)
        times = np.asarray(sorted(points), dtype=float)
        azimuths = np.asarray([points[t][0] for t in times], dtype=float)
        elevations = np.asarray([points[t][1] for t in times], dtype=float)
        return times, azimuths, elevations

    def _look_angle_at(
        self, result: StationAccess, interval: AccessInterval, time_s: float
    ) -> tuple[float, float] | None:
        if abs(time_s - interval.start_s) < 1e-9:
            if (
                interval.start_azimuth_deg is not None
                and interval.start_elevation_deg is not None
            ):
                elevation = interval.start_elevation_deg
                station = self._selected_station()
                if (
                    station is not None
                    and not interval.clipped_at_start
                    and not interval.limited_by_gap_at_start
                ):
                    elevation = max(station.minimum_elevation_deg, elevation)
                return interval.start_azimuth_deg, elevation
        if abs(time_s - interval.end_s) < 1e-9:
            if (
                interval.end_azimuth_deg is not None
                and interval.end_elevation_deg is not None
            ):
                elevation = interval.end_elevation_deg
                station = self._selected_station()
                if (
                    station is not None
                    and not interval.clipped_at_end
                    and not interval.limited_by_gap_at_end
                ):
                    elevation = max(station.minimum_elevation_deg, elevation)
                return interval.end_azimuth_deg, elevation
        for profile in result.look_angle_profiles:
            times = profile.times_s
            if times.size == 0 or not times[0] <= time_s <= times[-1]:
                continue
            right = int(np.searchsorted(times, time_s, side="left"))
            if right < times.size and times[right] == time_s:
                left = right
            else:
                left = right - 1
            if not 0 <= left < times.size or not 0 <= right < times.size:
                continue
            if not (
                np.isfinite(profile.azimuths_deg[[left, right]]).all()
                and np.isfinite(profile.elevations_deg[[left, right]]).all()
            ):
                return None
            if left == right:
                return (
                    float(profile.azimuths_deg[left]),
                    float(profile.elevations_deg[left]),
                )
            azimuth_pair = np.unwrap(np.deg2rad(profile.azimuths_deg[[left, right]]))
            fraction = (time_s - times[left]) / (times[right] - times[left])
            azimuth = np.rad2deg(
                azimuth_pair[0] + fraction * (azimuth_pair[1] - azimuth_pair[0])
            )
            elevation = float(
                np.interp(
                    time_s,
                    times[[left, right]],
                    profile.elevations_deg[[left, right]],
                )
            )
            return float(azimuth % 360.0), elevation
        return None

    def _draw_sky_plot(self) -> None:
        axes = self._axes
        figure = self._figure
        if axes is None or figure is None:
            return
        axes.clear()
        axes.set_theta_zero_location("N")
        axes.set_theta_direction(-1)
        axes.set_ylim(0.0, 90.0)
        axes.set_yticks((0.0, 30.0, 60.0, 90.0))
        axes.set_yticklabels(("90°", "60°", "30°", "0°"))
        axes.set_thetagrids((0, 90, 180, 270), ("N", "E", "S", "W"))
        axes.grid(True, alpha=0.45)
        station = self._selected_station()
        result = self._result_for(station.station_id) if station is not None else None
        interval = self._selected_interval()
        if station is not None:
            mask_radius = 90.0 - station.minimum_elevation_deg
            theta = np.linspace(0.0, 2.0 * np.pi, 361)
            axes.plot(
                theta,
                np.full_like(theta, mask_radius),
                color="#c74343",
                linestyle="--",
                linewidth=1.4,
                label=f"{station.minimum_elevation_deg}° mask",
            )
            axes.set_title(f"{station.name} sky view")
        self._playback_marker = None
        if interval is not None and result is not None and station is not None:
            plotted = False
            for profile in result.look_angle_profiles:
                if (
                    profile.times_s.size == 0
                    or profile.times_s[-1] < interval.start_s
                    or profile.times_s[0] > interval.end_s
                ):
                    continue
                times, azimuths, elevations = self._profile_points(profile, interval)
                valid = (
                    np.isfinite(times)
                    & np.isfinite(azimuths)
                    & np.isfinite(elevations)
                    & (elevations >= station.minimum_elevation_deg - 1e-8)
                )
                indices = np.flatnonzero(valid)
                for run in np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1):
                    if not run.size:
                        continue
                    unwrapped_azimuth = np.unwrap(np.deg2rad(azimuths[run]))
                    axes.plot(
                        unwrapped_azimuth,
                        90.0 - elevations[run],
                        color="#247a9b",
                        linewidth=2.0,
                        label="Selected pass" if not plotted else "_nolegend_",
                    )
                    plotted = True
            for time_s, marker, label, color in (
                (
                    interval.start_s,
                    "^",
                    "Pass start",
                    "#167d5a",
                ),
                (
                    interval.peak_time_s,
                    "*",
                    "Peak elevation",
                    "#d18a18",
                ),
                (
                    interval.end_s,
                    "v",
                    "Pass end",
                    "#a54444",
                ),
            ):
                look_angle = self._look_angle_at(result, interval, time_s)
                if look_angle is None or not np.isfinite(look_angle).all():
                    continue
                if look_angle[1] < station.minimum_elevation_deg - 1e-8:
                    continue
                axes.plot(
                    np.deg2rad(look_angle[0]),
                    90.0 - look_angle[1],
                    marker=marker,
                    color=color,
                    linestyle="none",
                    markersize=9,
                    label=label,
                )
            (self._playback_marker,) = axes.plot(
                [],
                [],
                marker="o",
                markersize=8,
                markerfacecolor="#e74d69",
                markeredgecolor="white",
                linestyle="none",
                label="Playback time",
                zorder=8,
            )
            if not plotted:
                axes.text(
                    0.5,
                    0.5,
                    "Selected pass sky path unavailable",
                    ha="center",
                    va="center",
                    transform=axes.transAxes,
                )
        elif station is None:
            axes.text(
                0.5,
                0.5,
                "Add or select a ground station to inspect passes.",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
        elif not self._oem_loaded:
            axes.text(
                0.5,
                0.5,
                "Load an Earth-centered OEM to view the sky plot.",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
        elif result is not None and result.limitation:
            axes.text(
                0.5,
                0.5,
                result.limitation,
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
        elif interval is None:
            axes.text(
                0.5,
                0.5,
                "Select a pass to view its sky path.",
                ha="center",
                va="center",
                transform=axes.transAxes,
            )
        if axes.get_legend_handles_labels()[0]:
            legend = axes.legend(
                loc="upper center",
                bbox_to_anchor=(0.5, -0.04),
                ncol=2,
                fontsize="small",
            )
            legend.set_in_layout(False)
            figure.tight_layout(rect=(0.0, 0.18, 1.0, 1.0))
        else:
            figure.tight_layout()
        self._update_playback_marker()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _update_playback_marker(self) -> None:
        if self._playback_marker is not None:
            self._playback_marker.set_data([], [])
        interval = self._selected_interval()
        result = (
            self._result_for(self._selected_station_id)
            if self._selected_station_id is not None
            else None
        )
        station = self._selected_station()
        status = "No pass selected."
        if interval is not None and result is not None and station is not None:
            status = (
                f"{station.name} · {self._time_label(interval.start_s)} – "
                f"{self._time_label(interval.end_s)} · mask "
                f"{station.minimum_elevation_deg}° · peak "
                f"{interval.peak_elevation_deg:.1f}° at "
                f"{self._time_label(interval.peak_time_s)}"
            )
            if interval.start_s <= self._current_time_s <= interval.end_s:
                look_angle = self._look_angle_at(result, interval, self._current_time_s)
                if (
                    look_angle is not None
                    and look_angle[1] >= station.minimum_elevation_deg
                ):
                    status += " · Playhead within selected pass."
                    if self._playback_marker is not None:
                        self._playback_marker.set_data(
                            [np.deg2rad(look_angle[0])],
                            [90.0 - look_angle[1]],
                        )
                else:
                    status += " · Playhead look angle unavailable."
            else:
                status += " · Playhead outside selected pass."
        if self._sky_summary is not None:
            self._sky_summary_text = status
            self._sky_summary.SetLabel(status)
        else:
            self._sky_summary_text = status
        if self._canvas is not None:
            self._canvas.draw_idle()

    def update(self, t_s: float, /) -> None:
        self._current_time_s = t_s
        self._update_playback_marker()

    def set_display_time_zone(self, display_time_zone: str) -> None:
        self._display_time_zone = display_time_zone
        self._update_coverage_readout()
        self._refresh_rows()
        self._update_playback_marker()

    def _time_label(self, time_s: float) -> str:
        return format_tt(
            time_s, self._display_time_zone, fractional_second_places=0
        )

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, _coverage: tuple[float, float], /
    ) -> None:
        if self._time_range_applied and bounds == self._time_range_bounds:
            return
        self._time_range_bounds = bounds
        self._time_range_applied = True
        if self._limit_to_range and bounds != self._prepare_range:
            self._prepare_range = bounds
            self._prepare_access()
        self._refresh_rows()

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        """Refresh station definitions while retaining the selected ID when possible."""
        selected = self._selected_station_id
        self._stations = tuple(stations)
        selection_retained = any(
            station.station_id == selected for station in self._stations
        )
        self._selected_station_id = (
            selected
            if selection_retained
            else (self._stations[0].station_id if self._stations else None)
        )
        self._missing_initial_station = False
        self._prepare_access()
        self._refresh_station_choice()
        if not selection_retained:
            self._selected_interval_key = None
        self._refresh_rows()

    def set_oem(
        self,
        source: GroundTrackSource | None,
        cursor: playback_cursor.OemCursor,
        object_name: str,
        *,
        oem_loaded: bool,
    ) -> None:
        """Refresh pass data after an OEM is replaced."""
        self._source = source
        self._cursor = cursor
        self._object_name = object_name
        self._oem_loaded = oem_loaded
        self._current_time_s = cursor.t_start
        self._time_range_bounds = None
        self._time_range_applied = False
        self._selected_interval_key = None
        self._prepare_access()
        self._update_coverage_readout()
        self._refresh_rows()

    def close(self) -> None:
        self._context_unsubscribe()
        self._context_unsubscribe = lambda: None
        self._canvas = None
        self._figure = None
        self._axes = None
        self._panel = None


class GroundStationPassListView(GroundStationPassesView):
    """Show the pass table without embedding its linked Sky View."""

    name = "pass-list"
    heading = "Pass List"

    def _update_analysis_layout(self) -> None:
        if self._analysis_panel is None or self._analysis_sizer is None:
            return
        if self._table_panel is None or self._sky_panel is None:
            return
        self._sky_panel.Hide()
        self._table_panel.Show()
        self._analysis_sizer.Clear(False)
        self._analysis_sizer.SetOrientation(wx.VERTICAL)
        self._analysis_sizer.Add(self._table_panel, 1, wx.EXPAND | wx.ALL, 2)
        self._analysis_panel.Layout()

    def _draw_sky_plot(self) -> None:
        return


class GroundStationSkyView(GroundStationPassesView):
    """Show the selected-pass polar plot without embedding its list."""

    name = "sky-view"
    heading = "Sky View"

    def _update_analysis_layout(self) -> None:
        if self._analysis_panel is None or self._analysis_sizer is None:
            return
        if self._sky_panel is None or self._table_panel is None:
            return
        self._table_panel.Hide()
        self._sky_panel.Show()
        self._analysis_sizer.Clear(False)
        self._analysis_sizer.SetOrientation(wx.VERTICAL)
        self._analysis_sizer.Add(self._sky_panel, 1, wx.EXPAND | wx.ALL, 2)
        self._analysis_panel.Layout()
