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
from ..ground_track import split_ground_track_runs
from ..oem_data_store import GroundTrackGroups
from ..display_time import UTC_DISPLAY, format_tt
from ..series import OrbitSeries
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit
from .base import StoreViewBinding, StoreViewContext
from .plotting import bounded_sample_indices


class GroundStationPassTrackView:
    """Draw the selected pass subpoint path from shared Earth-fixed positions."""

    name = "pass-ground-track"

    def __init__(
        self,
        parent: wx.Window,
        cursor: playback_cursor.OemCursor,
        stations: Sequence[GroundStation],
        *,
        oem_loaded: bool,
        selection_context: StationAnalysisContext,
        display_time_zone: str = UTC_DISPLAY,
    ) -> None:
        self._parent = parent
        self._cursor = cursor
        self._stations = tuple(stations)
        self._oem_loaded = oem_loaded
        self._selection_context = selection_context
        self._display_time_zone = display_time_zone
        self._prepared_interval_key: tuple[float, float] | None = None
        self._store_context: StoreViewContext | None = None
        self._store_binding = StoreViewBinding(("ground-track", "earth-fixed"))
        self._panel: wx.Panel | None = None
        self._status: wx.StaticText | None = None
        self._figure: Figure | None = None
        self._axes: Any = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._context_unsubscribe = selection_context.subscribe(
            self._on_context_selection
        )

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        return self._build_panel()

    def build_from_store(self, context: StoreViewContext, /) -> wx.Window:
        """Build from the selected pass's range-bound store query."""
        self._store_binding.bind(context)
        self._store_context = context
        return self._build_panel()

    def update_from_store(self, context: StoreViewContext, /) -> None:
        """Refresh the selected pass against a newer store snapshot."""
        if self._store_context is None:
            raise RuntimeError("Pass Ground Track view was not built from a store")
        self._store_binding.bind(context)
        self._store_context = context
        self._draw()

    def _build_panel(self) -> wx.Window:
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
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if self._store_context is not None:
            self._store_context = self._store_binding.with_range(bounds, coverage)
            self._draw()

    def set_stations(self, stations: Sequence[GroundStation]) -> None:
        self._stations = tuple(stations)
        self._draw()

    def close(self) -> None:
        self._context_unsubscribe()
        self._context_unsubscribe = lambda: None
        self._store_binding.close()
        self._store_context = None
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
        if not self._oem_loaded or self._store_context is None:
            self._set_status("Load an Earth-centered OEM to view a pass track.")
        elif station is None:
            self._set_status("Select a configured ground station.")
        elif selection.interval_key is None:
            self._set_status("Select a pass in Pass List to view its ground track.")
        else:
            if self._store_context is not None:
                pass_range = ResolvedTimeRange(*selection.interval_key)
                query_context = self._store_context.with_range(
                    pass_range, self._store_context.coverage
                )
                query = query_context.ground_track()
                if not query.value:
                    self._set_status(
                        "Ground-track data is loading."
                        if not query.coverage.complete
                        else "No OEM ground-track samples fall within this pass."
                    )
                else:
                    self._draw_store_track(
                        query.value,
                        station,
                        complete=query.coverage.complete,
                    )
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _draw_store_track(
        self,
        groups: GroundTrackGroups,
        station: GroundStation,
        *,
        complete: bool,
    ) -> None:
        first_time_s: float | None = None
        last_time_s: float | None = None
        first_line = True
        for group in groups:
            time_index = group.columns.index("t")
            longitude_index = group.columns.index("longitude")
            latitude_index = group.columns.index("latitude")
            for span in group.segment_bounds:
                values = group.values[span.first : span.stop]
                indices = bounded_sample_indices(len(values))
                if not len(indices):
                    continue
                first_time_s = (
                    float(values[0, time_index])
                    if first_time_s is None
                    else first_time_s
                )
                last_time_s = float(values[-1, time_index])
                self._axes.plot(
                    np.rad2deg(values[indices, longitude_index]),
                    np.rad2deg(values[indices, latitude_index]),
                    color="#2f7ebc",
                    linewidth=1.5,
                    label="Selected pass" if first_line else None,
                )
                first_line = False
        self._axes.scatter(
            station.longitude_deg,
            station.latitude_deg,
            color="#16877e",
            edgecolors="white",
            linewidths=0.8,
            zorder=3,
            label="Station",
        )
        self._axes.legend(loc="best")
        status = station.name
        if first_time_s is not None and last_time_s is not None:
            status += (
                f" · {format_tt(first_time_s, self._display_time_zone)}–"
                f"{format_tt(last_time_s, self._display_time_zone)}"
            )
        if not complete:
            status += " · Partial coverage"
        self._set_status(status)

    def _set_status(self, message: str) -> None:
        if self._status is not None:
            self._status.SetLabel(message)
