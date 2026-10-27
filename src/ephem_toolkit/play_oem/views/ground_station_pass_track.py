"""Pass-bounded Ground Track panel for Ground Station analysis."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from .. import cursor as playback_cursor
from ..ground_stations import GroundStation
from ..ground_track import (
    GroundTrackCoordinates,
    GroundTrackPreparationError,
    GroundTrackSource,
    prepare_ground_track,
    split_ground_track_runs,
)
from ..display_time import UTC_DISPLAY, format_tt
from ..series import OrbitSeries
from ..station_access import StationAccessCache
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit


class GroundStationPassTrackView:
    """Draw the selected pass subpoint path from shared Earth-fixed positions."""

    name = "pass-ground-track"

    def __init__(
        self,
        parent: wx.Window,
        source: GroundTrackSource | None,
        cursor: playback_cursor.OemCursor,
        stations: Sequence[GroundStation],
        *,
        oem_loaded: bool,
        access_cache: StationAccessCache,
        selection_context: StationAnalysisContext,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        self._parent = parent
        self._source = source
        self._cursor = cursor
        self._stations = tuple(stations)
        self._oem_loaded = oem_loaded
        self._access_cache = access_cache
        self._selection_context = selection_context
        self._display_time_zone = display_time_zone
        self._prepared_interval_key: tuple[float, float] | None = None
        self._prepared_coordinates: GroundTrackCoordinates | None = None
        self._panel: wx.Panel | None = None
        self._status: wx.StaticText | None = None
        self._figure: Figure | None = None
        self._axes: Any = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._context_unsubscribe = selection_context.subscribe(
            self._on_context_selection
        )

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        self._panel = panel
        sizer = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(panel, wx.ID_ANY, "Pass Ground Track")
        heading.SetName("Pass Ground Track heading")
        sizer.Add(heading, 0, wx.EXPAND | wx.ALL, 8)
        self._status = wx.StaticText(panel, wx.ID_ANY, "")
        self._status.SetName("Pass Ground Track status")
        sizer.Add(self._status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._figure = Figure(figsize=(8.0, 4.5), dpi=100)
        self._axes = self._figure.add_subplot(111)
        self._canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, self._figure)
        sizer.Add(self._canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self._draw()
        return panel

    def update(self, _t_s: float, /) -> None:
        pass

    def set_time_range(
        self, _bounds: ResolvedTimeRange | None, _coverage: tuple[float, float], /
    ) -> None:
        pass

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._stations = tuple(stations)
        self._draw()

    def close(self) -> None:
        self._context_unsubscribe()
        self._context_unsubscribe = lambda: None
        self._canvas = None
        self._figure = None
        self._axes = None
        self._panel = None

    def _on_context_selection(
        self, _selection: StationAnalysisSelection
    ) -> None:
        self._draw()

    def _draw(self) -> None:
        if self._axes is None:
            return
        self._axes.clear()
        self._axes.set_xlim(-180.0, 180.0)
        self._axes.set_ylim(-90.0, 90.0)
        self._axes.set_xlabel("Longitude (degrees)")
        self._axes.set_ylabel("Latitude (degrees)")
        self._axes.set_xticks(np.arange(-180.0, 181.0, 60.0))
        self._axes.set_yticks(np.arange(-90.0, 91.0, 30.0))
        self._axes.grid(True, alpha=0.25)
        selection = self._selection_context.selection
        station = next(
            (
                item
                for item in self._stations
                if item.station_id == selection.station_id
            ),
            None,
        )
        if not self._oem_loaded or self._source is None:
            self._set_status("Load an Earth-centered OEM to view a pass track.")
        elif station is None:
            self._set_status("Select a configured ground station.")
        elif selection.interval_key is None:
            self._set_status("Select a pass in Pass List to view its ground track.")
        else:
            try:
                if self._prepared_interval_key != selection.interval_key:
                    self._prepared_coordinates = prepare_ground_track(
                        self._source,
                        position_cache=self._access_cache.position_cache,
                        bounds=selection.interval_key,
                    )
                    self._prepared_interval_key = selection.interval_key
                coordinates = self._prepared_coordinates
                if coordinates is None:
                    raise RuntimeError("pass ground track preparation returned no data")
            except GroundTrackPreparationError as error:
                self._set_status(str(error))
            else:
                clipped = _clip_coordinates(coordinates, selection.interval_key)
                if clipped.timestamps_s.size == 0:
                    self._set_status("No OEM ground-track samples fall within this pass.")
                else:
                    runs = split_ground_track_runs(clipped, 0.0)
                    for index, run in enumerate(runs):
                        self._axes.plot(
                            np.rad2deg(run.longitude_relative_rad),
                            np.rad2deg(run.latitude_rad),
                            color="#2f7ebc",
                            linewidth=1.5,
                            label="Selected pass" if index == 0 else None,
                        )
                    self._axes.scatter(
                        station.longitude_deg,
                        station.latitude_deg,
                        color="#16877e",
                        edgecolors="white",
                        linewidths=0.8,
                        zorder=3,
                        label="Station",
                    )
                    self._set_status(
                        f"{station.name} · "
                        f"{format_tt(clipped.timestamps_s[0], self._display_time_zone)}–"
                        f"{format_tt(clipped.timestamps_s[-1], self._display_time_zone)}"
                    )
                    self._axes.legend(loc="best")
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _set_status(self, message: str) -> None:
        if self._status is not None:
            self._status.SetLabel(message)


def _clip_coordinates(
    coordinates: GroundTrackCoordinates,
    interval_key: tuple[float, float],
) -> GroundTrackCoordinates:
    start_s, end_s = interval_key
    selected = (coordinates.timestamps_s >= start_s) & (
        coordinates.timestamps_s <= end_s
    )
    return GroundTrackCoordinates(
        coordinates.timestamps_s[selected],
        coordinates.latitude_rad[selected],
        coordinates.longitude_rad[selected],
        coordinates.segment_ids[selected],
        coordinates.source_frame,
    )
