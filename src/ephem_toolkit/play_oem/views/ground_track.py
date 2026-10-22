"""Wx-hosted Ground Track map view."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import wx
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg,
    NavigationToolbar2WxAgg,
)
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import cursor as playback_cursor
from ..ground_footprints import (
    DEFAULT_AZIMUTH_COUNT,
    GroundFootprintBoundary,
    GroundFootprints,
    compute_ground_footprints,
)
from ..ground_track import (
    EARTH_RADIUS_AUTHALIC_M,
    GroundTrackCoordinates,
    GroundTrackPreparationError,
    GroundTrackSource,
    GroundTrackRun,
    _ecef_to_wgs84_geodetic,
    split_ground_track_runs,
    state_position_to_itrf_m,
)
from ..series import OrbitSeries
from ..time_unit import TimeUnit
from .plotting import decimate_indices

PROJECTION_SPECS = {
    "Equirectangular": ("eqc", {}),
    "Robinson": ("robin", {}),
    "Winkel Tripel": ("wintri", {"lat_1": 50.467}),
}
PROJECTION_NAMES = tuple(PROJECTION_SPECS)
DEFAULT_PROJECTION = "Robinson"
DEFAULT_CENTER_LONGITUDE_DEG = 0.0
FOOTPRINT_REFRESH_INTERVAL_S = 0.1


def _make_projection(name: str, center_longitude_deg: float) -> Any:
    """Create the selected spherical projection with its central meridian."""
    from pyproj import Proj

    if name not in PROJECTION_SPECS:
        raise ValueError(f"Unknown Ground Track projection: {name!r}")
    projection_name, parameters = PROJECTION_SPECS[name]
    return Proj(
        proj=projection_name,
        lon_0=center_longitude_deg,
        R=EARTH_RADIUS_AUTHALIC_M,
        **parameters,
    )


def _normalized_longitude(longitude_deg: float) -> float:
    return ((longitude_deg + 180.0) % 360.0) - 180.0


def _longitude_label(longitude_deg: float) -> str:
    value = _normalized_longitude(longitude_deg)
    if abs(abs(value) - 180.0) < 1.0e-8:
        return "180°"
    if abs(value) < 1.0e-8:
        return "0°"
    return f"{abs(value):.0f}° {'E' if value > 0.0 else 'W'}"


def _latitude_label(latitude_deg: float) -> str:
    if abs(latitude_deg) < 1.0e-8:
        return "0°"
    return f"{abs(latitude_deg):.0f}° {'N' if latitude_deg > 0.0 else 'S'}"


def _project_run(
    projection: Any, run: GroundTrackRun, center_longitude_deg: float
) -> np.ndarray:
    longitude_deg = np.rad2deg(run.longitude_relative_rad) + center_longitude_deg
    latitude_deg = np.rad2deg(run.latitude_rad)
    x, y = projection(longitude_deg, latitude_deg, errcheck=True)
    return np.column_stack((x, y))


def _boundary_runs(
    boundary: GroundFootprintBoundary, center_longitude_deg: float
) -> tuple[GroundTrackRun, ...]:
    if boundary.collapsed:
        return split_ground_track_runs(
            GroundTrackCoordinates(
                np.asarray([0.0]),
                boundary.latitude_rad,
                boundary.longitude_rad,
                np.asarray([0]),
                "ITRF",
            ),
            center_longitude_deg,
        )
    count = len(boundary.latitude_rad)
    coordinates = GroundTrackCoordinates(
        np.arange(count + 1, dtype=float),
        np.concatenate((boundary.latitude_rad, boundary.latitude_rad[:1])),
        np.concatenate((boundary.longitude_rad, boundary.longitude_rad[:1])),
        np.zeros(count + 1, dtype=int),
        "ITRF",
    )
    return split_ground_track_runs(coordinates, center_longitude_deg)


class GroundTrackView:
    """Map projection, track, current marker and coverage in a wx panel."""

    name = "ground-track"

    def __init__(
        self,
        parent: wx.Window,
        source: GroundTrackSource | None,
        coordinates: GroundTrackCoordinates | None,
        cursor: playback_cursor.OemCursor,
        object_name: str,
        *,
        error_message: str | None = None,
        minimum_elevation_deg: int = 10,
        on_minimum_elevation: Any = None,
    ) -> None:
        self._parent = parent
        self._source = source
        self._coordinates = coordinates
        self._cursor = cursor
        self._object_name = object_name
        self._error_message = error_message
        self.minimum_elevation_deg = minimum_elevation_deg
        self._on_minimum_elevation = on_minimum_elevation
        self.projection_name = DEFAULT_PROJECTION
        self.center_longitude_deg = DEFAULT_CENTER_LONGITUDE_DEG
        self._panel: wx.Panel | None = None
        self._canvas: FigureCanvasWxAgg | None = None
        self._figure: Figure | None = None
        self._axes: Any = None
        self._projection: Any = None
        self._track_artists: list[Any] = []
        self._marker: Line2D | None = None
        self._horizon_artist: LineCollection | None = None
        self._minimum_artist: LineCollection | None = None
        self._minimum_point_artist: Line2D | None = None
        self._coordinate_readout: wx.StaticText | None = None
        self._center_control: wx.SpinCtrlDouble | None = None
        self._minimum_control: wx.SpinCtrl | None = None
        self._horizontal_scroll: wx.ScrollBar | None = None
        self._vertical_scroll: wx.ScrollBar | None = None
        self._on_minimum_elevation: Any = None
        self._syncing_limits = False
        self._last_footprint_refresh_s = 0.0
        self._last_footprint_position: tuple[float, float, float] | None = None
        self._last_time_s: float | None = None
        self._last_footprints: GroundFootprints | None = None

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        self._panel = panel
        self._figure = Figure(figsize=(10.0, 5.0), dpi=100)
        self._axes = self._figure.add_subplot(111)
        self._canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, self._figure)
        toolbar = NavigationToolbar2WxAgg(self._canvas)
        toolbar.Realize()
        projection = wx.Choice(panel, choices=list(PROJECTION_NAMES))
        projection.SetStringSelection(self.projection_name)
        center = wx.SpinCtrlDouble(panel, min=-180.0, max=180.0, initial=0.0, inc=1.0)
        center.SetDigits(1)
        minimum = wx.SpinCtrl(panel, min=0, max=90, initial=self.minimum_elevation_deg)
        minimum.SetName("Minimum elevation in degrees")
        self._center_control = center
        self._minimum_control = minimum
        controls = wx.BoxSizer(wx.HORIZONTAL)
        controls.Add(
            wx.StaticText(panel, label="Projection"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(projection, 0, wx.RIGHT, 12)
        controls.Add(
            wx.StaticText(panel, label="Center longitude (°E)"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(center, 0, wx.RIGHT, 12)
        controls.Add(
            wx.StaticText(panel, label="Minimum elevation (°)"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(minimum, 0)
        navigation = wx.BoxSizer(wx.HORIZONTAL)
        home = wx.Button(panel, label="Home")
        zoom_in = wx.Button(panel, label="+")
        zoom_out = wx.Button(panel, label="−")
        pan = wx.ToggleButton(panel, label="Pan")
        for button in (home, zoom_in, zoom_out, pan):
            navigation.Add(button, 0, wx.RIGHT, 4)
        self._coordinate_readout = wx.StaticText(panel, wx.ID_ANY, "Lat —  ·  Lon —")
        self._coordinate_readout.SetName("Ground Track current coordinates")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(toolbar, 0, wx.EXPAND)
        sizer.Add(controls, 0, wx.ALL, 6)
        sizer.Add(navigation, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        map_row = wx.BoxSizer(wx.HORIZONTAL)
        self._vertical_scroll = wx.ScrollBar(panel, style=wx.SB_VERTICAL)
        self._horizontal_scroll = wx.ScrollBar(panel, style=wx.SB_HORIZONTAL)
        map_row.Add(self._canvas, 1, wx.EXPAND)
        map_row.Add(self._vertical_scroll, 0, wx.EXPAND)
        sizer.Add(map_row, 1, wx.EXPAND)
        sizer.Add(self._horizontal_scroll, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        sizer.Add(
            self._coordinate_readout,
            0,
            wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            6,
        )
        panel.SetSizer(sizer)
        projection.Bind(wx.EVT_CHOICE, self._on_projection_choice)
        center.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_center_control)
        center.Bind(wx.EVT_TEXT_ENTER, self._on_center_control)
        minimum.Bind(wx.EVT_SPINCTRL, self._on_minimum_control)
        home.Bind(wx.EVT_BUTTON, lambda _event: self._reset_extent())
        zoom_in.Bind(wx.EVT_BUTTON, lambda _event: self._zoom(0.7))
        zoom_out.Bind(wx.EVT_BUTTON, lambda _event: self._zoom(1.0 / 0.7))
        pan.Bind(wx.EVT_TOGGLEBUTTON, lambda _event: toolbar.pan())
        self._canvas.mpl_connect("scroll_event", self._on_scroll)
        self._axes.callbacks.connect("xlim_changed", self._on_limits_changed)
        self._horizontal_scroll.Bind(
            wx.EVT_SCROLL_THUMBTRACK, self._on_horizontal_scroll
        )
        self._horizontal_scroll.Bind(wx.EVT_SCROLL_LINEUP, self._on_horizontal_scroll)
        self._horizontal_scroll.Bind(wx.EVT_SCROLL_LINEDOWN, self._on_horizontal_scroll)
        self._vertical_scroll.Bind(wx.EVT_SCROLL_THUMBTRACK, self._on_vertical_scroll)
        self._vertical_scroll.Bind(wx.EVT_SCROLL_LINEUP, self._on_vertical_scroll)
        self._vertical_scroll.Bind(wx.EVT_SCROLL_LINEDOWN, self._on_vertical_scroll)
        panel.SetMinSize(wx.Size(640, 340))
        self._draw_map()
        return panel

    def _draw_map(self) -> None:
        if self._figure is None or self._axes is None:
            return
        axes = self._axes
        axes.clear()
        self._track_artists.clear()
        self._projection = _make_projection(
            self.projection_name, self.center_longitude_deg
        )
        axes.set_aspect("equal", adjustable="box")
        axes.set_xlabel("Longitude (deg)")
        axes.set_ylabel("Geodetic latitude (deg)")
        axes.set_title(f"{self._object_name} · Ground Track")
        axes.grid(False)

        relative_ticks = np.array([-180.0, -90.0, 0.0, 90.0, 180.0])
        tick_longitudes = self.center_longitude_deg + relative_ticks
        tick_x, _ = self._projection(
            tick_longitudes, np.zeros_like(tick_longitudes), errcheck=True
        )
        axes.set_xticks(tick_x)
        axes.set_xticklabels([_longitude_label(value) for value in tick_longitudes])
        latitude_ticks = np.array([-90.0, -60.0, -30.0, 0.0, 30.0, 60.0, 90.0])
        _, tick_y = self._projection(
            np.full_like(latitude_ticks, self.center_longitude_deg),
            latitude_ticks,
            errcheck=True,
        )
        axes.set_yticks(tick_y)
        axes.set_yticklabels([_latitude_label(value) for value in latitude_ticks])

        graticule_latitudes = np.linspace(-90.0, 90.0, 181)
        graticule_longitudes = np.linspace(-180.0, 180.0, 361)
        for relative_lon in relative_ticks:
            longitude = self.center_longitude_deg + relative_lon
            x, y = self._projection(
                np.full_like(graticule_latitudes, longitude),
                graticule_latitudes,
                errcheck=True,
            )
            axes.plot(x, y, color="#cbd6e2", linewidth=0.7, zorder=0)
        for latitude in latitude_ticks[1:-1]:
            x, y = self._projection(
                self.center_longitude_deg + graticule_longitudes,
                np.full_like(graticule_longitudes, latitude),
                errcheck=True,
            )
            axes.plot(x, y, color="#cbd6e2", linewidth=0.7, zorder=0)

        world_x = np.asarray(tick_x, dtype=float)
        pole_x, pole_y = self._projection(
            np.array([self.center_longitude_deg, self.center_longitude_deg]),
            np.array([-90.0, 90.0]),
            errcheck=True,
        )
        axes.set_xlim(float(world_x.min()), float(world_x.max()))
        axes.set_ylim(float(np.min(pole_y)), float(np.max(pole_y)))
        axes.margins(0.0)

        if self._coordinates is None:
            message = (
                self._error_message
                or "Load an Earth-centered OEM to view its ground track."
            )
            axes.set_axis_off()
            axes.text(
                0.5,
                0.5,
                message,
                ha="center",
                va="center",
                wrap=True,
                transform=axes.transAxes,
            )
            self._figure.subplots_adjust(left=0.04, right=0.98, bottom=0.08, top=0.9)
            return

        runs = split_ground_track_runs(self._coordinates, self.center_longitude_deg)
        for run in runs:
            xy = _project_run(self._projection, run, self.center_longitude_deg)
            indices = decimate_indices(xy)
            (line,) = axes.plot(
                xy[indices, 0],
                xy[indices, 1],
                color="#3b5ccc",
                linewidth=1.8,
                solid_capstyle="round",
                zorder=3,
            )
            self._track_artists.append(line)

        self._marker = Line2D(
            [],
            [],
            linestyle="none",
            marker="o",
            markersize=9,
            markerfacecolor="#e74d69",
            markeredgecolor="white",
            markeredgewidth=1.8,
            zorder=6,
        )
        axes.add_line(self._marker)
        self._horizon_artist = LineCollection(
            [], colors=["#dd762d"], linewidths=1.5, linestyles="dashed", zorder=4
        )
        self._minimum_artist = LineCollection(
            [], colors=["#16877e"], linewidths=1.8, zorder=5
        )
        self._minimum_point_artist = Line2D(
            [],
            [],
            linestyle="none",
            marker="s",
            markersize=5,
            markerfacecolor="#16877e",
            markeredgecolor="white",
            zorder=5,
        )
        axes.add_collection(self._horizon_artist)
        axes.add_collection(self._minimum_artist)
        axes.add_line(self._minimum_point_artist)
        handles = [
            Line2D([], [], color="#3b5ccc", linewidth=1.8, label="Ground track"),
            Line2D(
                [],
                [],
                color="#dd762d",
                linewidth=1.5,
                linestyle="--",
                label="0° horizon",
            ),
            Line2D(
                [],
                [],
                color="#e74d69",
                marker="o",
                linestyle="none",
                label="Current subpoint",
            ),
        ]
        if self.minimum_elevation_deg == 0:
            handles[1].set_label("0° horizon / minimum elevation")
        else:
            handles.insert(
                2,
                Line2D(
                    [],
                    [],
                    color="#16877e",
                    linewidth=1.8,
                    marker="s" if self.minimum_elevation_deg == 90 else "",
                    linestyle="none" if self.minimum_elevation_deg == 90 else "-",
                    label=f"{self.minimum_elevation_deg}° minimum elevation",
                ),
            )
        self._figure.legend(
            handles=handles,
            loc="lower center",
            ncol=4,
            frameon=False,
            bbox_to_anchor=(0.5, 0.01),
        )
        self._figure.subplots_adjust(left=0.1, right=0.98, bottom=0.18, top=0.9)

    def _on_projection_choice(self, event: wx.CommandEvent) -> None:
        self.projection_name = event.GetString()
        self._draw_map()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _on_center_control(self, _event: wx.CommandEvent) -> None:
        if self._center_control is None:
            return
        self.center_longitude_deg = _normalized_longitude(
            self._center_control.GetValue()
        )
        self._center_control.SetValue(self.center_longitude_deg)
        self._draw_map()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _on_minimum_control(self, event: wx.CommandEvent) -> None:
        self.set_minimum_elevation(event.GetInt())
        if self._on_minimum_elevation is not None:
            self._on_minimum_elevation(self.minimum_elevation_deg)

    def set_minimum_elevation(self, value: int) -> None:
        previous_xlim = self._axes.get_xlim() if self._axes is not None else None
        previous_ylim = self._axes.get_ylim() if self._axes is not None else None
        self.minimum_elevation_deg = int(value)
        if self._minimum_control is not None:
            self._minimum_control.SetValue(self.minimum_elevation_deg)
        self._last_footprint_position = None
        self._last_footprints = None
        if self._axes is not None:
            self._draw_map()
            if previous_xlim is not None and previous_ylim is not None:
                self._axes.set_xlim(previous_xlim)
                self._axes.set_ylim(previous_ylim)
            if self._canvas is not None:
                self._canvas.draw_idle()

    def _reset_extent(self) -> None:
        self._draw_map()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _zoom(
        self, factor: float, x: float | None = None, y: float | None = None
    ) -> None:
        if self._axes is None:
            return
        xlim, ylim = self._axes.get_xlim(), self._axes.get_ylim()
        x = (xlim[0] + xlim[1]) * 0.5 if x is None else x
        y = (ylim[0] + ylim[1]) * 0.5 if y is None else y
        self._axes.set_xlim(x + (xlim[0] - x) * factor, x + (xlim[1] - x) * factor)
        self._axes.set_ylim(y + (ylim[0] - y) * factor, y + (ylim[1] - y) * factor)
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _on_scroll(self, event: Any) -> None:
        if (
            event.inaxes is self._axes
            and event.xdata is not None
            and event.ydata is not None
        ):
            self._zoom(0.8 if event.button == "up" else 1.25, event.xdata, event.ydata)

    def _on_limits_changed(self, _axes: Any) -> None:
        if self._syncing_limits or self._axes is None or self._projection is None:
            return
        midpoint = sum(self._axes.get_xlim()) * 0.5
        longitude, _ = self._projection(midpoint, 0.0, inverse=True)
        self.center_longitude_deg = _normalized_longitude(float(longitude))
        if self._center_control is not None:
            self._center_control.SetValue(self.center_longitude_deg)
        self._update_scrollbars()

    def _update_scrollbars(self) -> None:
        if (
            self._axes is None
            or self._horizontal_scroll is None
            or self._vertical_scroll is None
        ):
            return
        world_x = (
            abs(float(self._projection(180.0, 0.0)[0])) if self._projection else 1.0
        )
        world_y = (
            abs(float(self._projection(0.0, 90.0)[1])) if self._projection else 1.0
        )
        x0, x1 = sorted(self._axes.get_xlim())
        y0, y1 = sorted(self._axes.get_ylim())
        xspan, yspan = x1 - x0, y1 - y0
        xoverflow = max(0.0, 2 * world_x - xspan)
        yoverflow = max(0.0, 2 * world_y - yspan)
        xpos = 0 if xoverflow == 0 else round((x0 + world_x) / xoverflow * 920)
        ypos = 0 if yoverflow == 0 else round((world_y - y1) / yoverflow * 920)
        self._horizontal_scroll.SetScrollbar(max(0, min(920, xpos)), 80, 1000, 80)
        self._vertical_scroll.SetScrollbar(max(0, min(920, ypos)), 80, 1000, 80)
        self._horizontal_scroll.Enable(xoverflow > 0)
        self._vertical_scroll.Enable(yoverflow > 0)

    def _on_horizontal_scroll(self, event: wx.ScrollEvent) -> None:
        if self._axes is None:
            return
        low, high = sorted(self._axes.get_xlim())
        span = high - low
        world_x = abs(float(self._projection(180.0, 0.0)[0]))
        overflow = max(0.0, 2 * world_x - span)
        center = -world_x + overflow * event.GetPosition() / 920 + span * 0.5
        self._axes.set_xlim(center - span * 0.5, center + span * 0.5)
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _on_vertical_scroll(self, event: wx.ScrollEvent) -> None:
        if self._axes is None:
            return
        low, high = sorted(self._axes.get_ylim())
        span = high - low
        world_y = abs(float(self._projection(0.0, 90.0)[1]))
        overflow = max(0.0, 2 * world_y - span)
        center = -world_y + overflow * (920 - event.GetPosition()) / 920 + span * 0.5
        self._axes.set_ylim(center - span * 0.5, center + span * 0.5)
        if self._canvas is not None:
            self._canvas.draw_idle()

    @staticmethod
    def _boundary_segments(
        projection: Any,
        boundary: GroundFootprintBoundary | None,
        center_longitude_deg: float,
    ) -> list[np.ndarray]:
        if boundary is None:
            return []
        segments: list[np.ndarray] = []
        for run in _boundary_runs(boundary, center_longitude_deg):
            if boundary.collapsed:
                longitude_deg = (
                    np.rad2deg(run.longitude_relative_rad) + center_longitude_deg
                )
                x, y = projection(longitude_deg, np.rad2deg(run.latitude_rad))
                segments.append(np.column_stack((x, y)))
                continue
            segments.append(_project_run(projection, run, center_longitude_deg))
        return segments

    def _hide_dynamic_position(self, message: str) -> None:
        if self._marker is not None:
            self._marker.set_data([], [])
        if self._horizon_artist is not None:
            self._horizon_artist.set_segments([])
        if self._minimum_artist is not None:
            self._minimum_artist.set_segments([])
        if self._minimum_point_artist is not None:
            self._minimum_point_artist.set_data([], [])
        if self._coordinate_readout is not None:
            self._coordinate_readout.SetLabel(message)

    def update(self, t_s: float, /) -> None:
        if (
            self._coordinates is None
            or self._source is None
            or self._axes is None
            or self._projection is None
            or self._canvas is None
        ):
            return
        if self._last_time_s == t_s:
            return
        self._last_time_s = t_s
        state = self._cursor.lookup(t_s)
        if state.state_m is None:
            self._hide_dynamic_position("Current position unavailable")
            self._canvas.draw_idle()
            return
        try:
            position_itrf_m = state_position_to_itrf_m(
                state.state_m, self._source.frame_name, t_s
            )
            geodetic = _ecef_to_wgs84_geodetic(position_itrf_m.reshape(1, 3))[0]
        except (GroundTrackPreparationError, ValueError, RuntimeError) as error:
            self._hide_dynamic_position(f"Current position unavailable: {error}")
            self._canvas.draw_idle()
            return
        latitude_rad, longitude_rad, altitude_m = geodetic
        if not np.isfinite(geodetic).all() or altitude_m < 0.0:
            self._hide_dynamic_position("Current position unavailable")
            self._canvas.draw_idle()
            return

        relative_lon_deg = _normalized_longitude(
            float(np.rad2deg(longitude_rad)) - self.center_longitude_deg
        )
        current_lon_deg = relative_lon_deg + self.center_longitude_deg
        marker_x, marker_y = self._projection(
            current_lon_deg, float(np.rad2deg(latitude_rad)), errcheck=True
        )
        if self._marker is not None:
            self._marker.set_data([marker_x], [marker_y])
        if self._coordinate_readout is not None:
            self._coordinate_readout.SetLabel(
                f"Lat {_latitude_label(float(np.rad2deg(latitude_rad)))}  ·  "
                f"Lon {_longitude_label(float(np.rad2deg(longitude_rad)))}"
            )

        now = time.monotonic()
        position_key: tuple[float, float, float] = (
            float(position_itrf_m[0]),
            float(position_itrf_m[1]),
            float(position_itrf_m[2]),
        )
        refresh_footprint = (
            self._last_footprints is None
            or position_key != self._last_footprint_position
            and now - self._last_footprint_refresh_s >= FOOTPRINT_REFRESH_INTERVAL_S
        )
        if refresh_footprint:
            try:
                self._last_footprints = compute_ground_footprints(
                    position_itrf_m,
                    self.minimum_elevation_deg,
                    azimuth_count=DEFAULT_AZIMUTH_COUNT,
                )
            except (ValueError, RuntimeError) as error:
                self._hide_dynamic_position(f"Coverage unavailable: {error}")
                self._canvas.draw_idle()
                return
            self._last_footprint_position = position_key
            self._last_footprint_refresh_s = now
        if self._last_footprints is not None:
            if self._horizon_artist is not None:
                self._horizon_artist.set_segments(
                    self._boundary_segments(
                        self._projection,
                        self._last_footprints.horizon,
                        self.center_longitude_deg,
                    )
                )
            if self._minimum_artist is not None:
                minimum_boundary = self._last_footprints.minimum_elevation
                self._minimum_artist.set_segments(
                    self._boundary_segments(
                        self._projection,
                        (
                            None
                            if minimum_boundary is not None
                            and minimum_boundary.collapsed
                            else minimum_boundary
                        ),
                        self.center_longitude_deg,
                    )
                )
                if minimum_boundary is not None and minimum_boundary.collapsed:
                    point_lon = (
                        _normalized_longitude(
                            float(np.rad2deg(minimum_boundary.longitude_rad[0]))
                            - self.center_longitude_deg
                        )
                        + self.center_longitude_deg
                    )
                    point_x, point_y = self._projection(
                        point_lon, float(np.rad2deg(minimum_boundary.latitude_rad[0]))
                    )
                    if self._minimum_point_artist is not None:
                        self._minimum_point_artist.set_data([point_x], [point_y])
                elif self._minimum_point_artist is not None:
                    self._minimum_point_artist.set_data([], [])
        self._canvas.draw_idle()

    def close(self) -> None:
        self._canvas = None
        self._panel = None
        self._figure = None
        self._axes = None
        self._track_artists.clear()
        self._marker = None
        self._horizon_artist = None
        self._minimum_artist = None
        self._minimum_point_artist = None
        self._coordinate_readout = None
