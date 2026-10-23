"""Wx-hosted Ground Track map view."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import wx
from matplotlib import image as matplotlib_image
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
from .compact_controls import compact_controls
from .plotting import decimate_indices

PROJECTION_SPECS = {
    "Equirectangular": ("eqc", {}),
    "Robinson": ("robin", {}),
}
PROJECTION_NAMES = tuple(PROJECTION_SPECS)
DEFAULT_PROJECTION = "Robinson"
DEFAULT_CENTER_LONGITUDE_DEG = 0.0
BACKGROUND_CHOICES = ("Shaded relief", "Satellite imagery", "Political map")
BACKGROUND_FILES = {
    "Shaded relief": "earth_relief.jpg",
    "Satellite imagery": "earth_satellite.jpg",
    "Political map": "earth_map.jpg",
}
BACKGROUND_RENDER_SIZE = (1080, 540)


class GroundTrackToolbar(NavigationToolbar2WxAgg):
    """Rotate the map during pan without translating its horizontal viewport."""

    def __init__(
        self, canvas: FigureCanvasWxAgg, on_pan: Callable[[float, float], None]
    ):
        self._map_canvas: FigureCanvasWxAgg = canvas
        self._on_pan = on_pan
        self._pan_pointer: tuple[float, float] | None = None
        self._pan_motion_id: int | None = None
        super().__init__(canvas)

    def press_pan(self, event: Any) -> None:
        if event.button != 1 or event.inaxes is None:
            return
        self.push_current()
        self._pan_pointer = (event.x, event.y)
        self._pan_motion_id = self._map_canvas.mpl_connect(
            "motion_notify_event", self.drag_pan
        )

    def drag_pan(self, event: Any) -> None:
        if self._pan_pointer is None or event.x is None or event.y is None:
            return
        previous_x, previous_y = self._pan_pointer
        self._pan_pointer = (event.x, event.y)
        self._on_pan(event.x - previous_x, event.y - previous_y)

    def release_pan(self, event: Any) -> None:
        if self._pan_motion_id is not None:
            self._map_canvas.mpl_disconnect(self._pan_motion_id)
            self._pan_motion_id = None
            self.push_current()
        self._pan_pointer = None


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
        # Keep center +/- 180 degrees on opposite map edges. PROJ otherwise
        # wraps both seam longitudes to the same x coordinate for nonzero centers.
        over=True,
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
        self.background_style = BACKGROUND_CHOICES[0]
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
        self._last_time_s: float | None = None
        self._last_footprints: GroundFootprints | None = None

    def build(self, _series: OrbitSeries, _time_unit: TimeUnit, /) -> wx.Window:
        panel = wx.Panel(self._parent, wx.ID_ANY)
        panel.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)
        self._panel = panel
        self._figure = Figure(figsize=(9.0, 5.0), dpi=100)
        self._axes = self._figure.add_subplot(111)
        self._canvas = FigureCanvasWxAgg(panel, wx.ID_ANY, self._figure)
        self._canvas.SetMinSize(wx.Size(900, 500))
        toolbar = GroundTrackToolbar(self._canvas, self._pan_map)
        toolbar.Realize()
        toolbar.Hide()
        controls_panel = wx.ScrolledWindow(
            panel, wx.ID_ANY, style=wx.HSCROLL | wx.TAB_TRAVERSAL
        )
        controls_panel.SetName("Ground Track controls")
        controls_panel.SetScrollRate(10, 0)
        projection = wx.Choice(controls_panel, choices=list(PROJECTION_NAMES))
        projection.SetStringSelection(self.projection_name)
        background = wx.Choice(controls_panel, choices=list(BACKGROUND_CHOICES))
        background.SetStringSelection(self.background_style)
        background.SetName("Ground Track background")
        center = wx.SpinCtrlDouble(
            controls_panel, min=-180.0, max=180.0, initial=0.0, inc=1.0
        )
        center.SetDigits(1)
        minimum = wx.SpinCtrl(
            controls_panel, min=0, max=90, initial=self.minimum_elevation_deg
        )
        minimum.SetName("Minimum elevation in degrees")
        compact_controls((projection, background, center, minimum))
        self._center_control = center
        self._minimum_control = minimum
        controls = wx.BoxSizer(wx.HORIZONTAL)
        controls.Add(
            wx.StaticText(controls_panel, label="Projection"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(projection, 0, wx.RIGHT, 8)
        controls.Add(
            wx.StaticText(controls_panel, label="Background"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(background, 0, wx.RIGHT, 8)
        controls.Add(
            wx.StaticText(controls_panel, label="Center longitude (°E)"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(center, 0, wx.RIGHT, 8)
        controls.Add(
            wx.StaticText(controls_panel, label="Minimum elevation (°)"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4,
        )
        controls.Add(minimum, 0)
        navigation = wx.BoxSizer(wx.HORIZONTAL)
        home = wx.Button(controls_panel, label="Home", style=wx.BU_EXACTFIT)
        zoom_in = wx.Button(controls_panel, label="+", style=wx.BU_EXACTFIT)
        zoom_out = wx.Button(controls_panel, label="−", style=wx.BU_EXACTFIT)
        pan = wx.ToggleButton(controls_panel, label="Pan", style=wx.BU_EXACTFIT)
        compact_controls((home, zoom_in, zoom_out, pan))
        for button in (home, zoom_in, zoom_out, pan):
            button.SetMinSize(
                wx.Size(max(button.FromDIP(24), button.GetBestSize().width), -1)
            )
            navigation.Add(button, 0, wx.RIGHT, 4)
        controls_sizer = wx.BoxSizer(wx.VERTICAL)
        controls_sizer.Add(controls, 0, wx.LEFT | wx.RIGHT | wx.TOP, 2)
        controls_sizer.AddSpacer(2)
        controls_sizer.Add(navigation, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 2)
        controls_panel.SetSizer(controls_sizer)
        controls_panel.SetMinSize(
            wx.Size(
                1,
                controls_sizer.CalcMin().height
                + wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y),
            )
        )
        controls_panel.FitInside()
        self._coordinate_readout = wx.StaticText(panel, wx.ID_ANY, "Lat —  ·  Lon —")
        self._coordinate_readout.SetName("Ground Track current coordinates")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(controls_panel, 0, wx.EXPAND)
        map_row = wx.BoxSizer(wx.HORIZONTAL)
        map_row.Add(self._canvas, 1, wx.EXPAND)
        sizer.Add(map_row, 1, wx.EXPAND)
        sizer.Add(
            self._coordinate_readout,
            0,
            wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            6,
        )
        panel.SetSizer(sizer)
        projection.Bind(wx.EVT_CHOICE, self._on_projection_choice)
        background.Bind(wx.EVT_CHOICE, self._on_background_choice)
        center.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_center_control)
        center.Bind(wx.EVT_TEXT_ENTER, self._on_center_control)
        minimum.Bind(wx.EVT_SPINCTRL, self._on_minimum_control)
        home.Bind(wx.EVT_BUTTON, lambda _event: self._reset_extent())
        zoom_in.Bind(wx.EVT_BUTTON, lambda _event: self._zoom(0.7))
        zoom_out.Bind(wx.EVT_BUTTON, lambda _event: self._zoom(1.0 / 0.7))
        pan.Bind(wx.EVT_TOGGLEBUTTON, lambda _event: toolbar.pan())
        self._canvas.mpl_connect("button_release_event", self._on_navigation_release)
        self._axes.callbacks.connect("xlim_changed", self._on_limits_changed)
        # Keep the map's height when the window narrows; scroll instead of
        # shrinking it. The controls row does not dictate the canvas width.
        panel.SetMinSize(sizer.CalcMin())

        def fit_controls(event: wx.SizeEvent | None = None) -> None:
            if event is not None:
                event.Skip()
            if not controls_panel:
                return
            # GTK's compact sizes settle after creation. Discard the original
            # best sizes before measuring the two rows again.
            for child in controls_panel.GetChildren():
                child.InvalidateBestSize()
            required = controls_sizer.CalcMin()
            height = required.height
            if required.width > controls_panel.GetClientSize().width:
                height += wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y)
            if controls_panel.GetMinSize().height == height:
                return
            controls_panel.SetMinSize(wx.Size(1, height))
            controls_panel.FitInside()
            panel.SetMinSize(sizer.CalcMin())
            panel.Layout()
            if isinstance(self._parent, wx.ScrolledWindow):
                self._parent.FitInside()

        controls_panel.Bind(wx.EVT_SIZE, fit_controls)
        wx.CallAfter(fit_controls)
        self._draw_map()
        return panel

    def _draw_map(self) -> None:
        if self._figure is None or self._axes is None:
            return
        axes = self._axes
        current_time_s = self._last_time_s
        self._last_time_s = None
        # Clearing and rebuilding the axes changes its limits several times.
        # Those are implementation details of the redraw, not map navigation;
        # do not let the x-limit callback reinterpret them as a new center.
        self._syncing_limits = True
        axes.clear()
        self._track_artists.clear()
        self._projection = _make_projection(
            self.projection_name, self.center_longitude_deg
        )
        axes.set_aspect("equal", adjustable="box", anchor="C")
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
        self._draw_background(axes, world_x, pole_y)
        self._syncing_limits = False

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
        self._figure.subplots_adjust(left=0.08, right=0.98, bottom=0.15, top=0.95)
        if current_time_s is not None:
            self.update(current_time_s)

    def _draw_background(
        self, axes: Any, world_x: np.ndarray, pole_y: np.ndarray
    ) -> None:
        """Reproject the selected global equirectangular image into the map axes."""
        from pathlib import Path

        filename = BACKGROUND_FILES[self.background_style]
        source = matplotlib_image.imread(
            str(Path(__file__).parent.parent / "assets" / filename)
        )
        if np.issubdtype(source.dtype, np.integer):
            source = source.astype(np.float32) / np.iinfo(source.dtype).max
        width, height = BACKGROUND_RENDER_SIZE
        x = np.linspace(float(world_x.min()), float(world_x.max()), width)
        y = np.linspace(float(np.min(pole_y)), float(np.max(pole_y)), height)
        projected_x, projected_y = np.meshgrid(x, y)
        longitude, latitude = self._projection(projected_x, projected_y, inverse=True)
        roundtrip_x, roundtrip_y = self._projection(longitude, latitude)
        x_tolerance = (x[-1] - x[0]) / (width - 1)
        y_tolerance = (y[-1] - y[0]) / (height - 1)
        valid = (
            np.isfinite(longitude)
            & np.isfinite(latitude)
            & (latitude >= -90.0)
            & (latitude <= 90.0)
            & (np.abs(roundtrip_x - projected_x) <= x_tolerance)
            & (np.abs(roundtrip_y - projected_y) <= y_tolerance)
        )
        safe_longitude = np.where(valid, longitude, 0.0)
        safe_latitude = np.where(valid, latitude, 0.0)
        source_columns = np.mod(safe_longitude + 180.0, 360.0) * (
            source.shape[1] / 360.0
        )
        source_rows = (90.0 - safe_latitude) * (source.shape[0] / 180.0)
        columns = np.clip(source_columns.astype(int), 0, source.shape[1] - 1)
        rows = np.clip(source_rows.astype(int), 0, source.shape[0] - 1)
        rendered = source[rows, columns]
        if rendered.shape[2] == 3:
            rendered = np.dstack((rendered, np.ones(valid.shape)))
        rendered[~valid, 3] = 0.0
        axes.imshow(
            rendered,
            extent=(
                float(world_x.min()),
                float(world_x.max()),
                float(np.min(pole_y)),
                float(np.max(pole_y)),
            ),
            origin="lower",
            interpolation="bilinear",
            aspect="equal",
            zorder=-1,
        )

    def _on_background_choice(self, event: wx.CommandEvent) -> None:
        self.background_style = event.GetString()
        self._draw_map()
        if self._canvas is not None:
            self._canvas.draw_idle()

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

    def _on_limits_changed(self, _axes: Any) -> None:
        self._sync_center_from_extent()

    def _pan_map(self, dx_pixels: float, dy_pixels: float) -> None:
        if self._axes is None or self._projection is None:
            return
        xlim, ylim = self._axes.get_xlim(), self._axes.get_ylim()
        width, height = self._axes.bbox.width, self._axes.bbox.height
        if width <= 0 or height <= 0:
            return
        xspan = xlim[1] - xlim[0]
        longitude, _ = self._projection(-dx_pixels * xspan / width, 0.0, inverse=True)
        self.center_longitude_deg = _normalized_longitude(float(longitude))
        yspan = ylim[1] - ylim[0]
        _, pole_y = self._projection(
            [self.center_longitude_deg, self.center_longitude_deg], [-90.0, 90.0]
        )
        south, north = float(min(pole_y)), float(max(pole_y))
        if yspan >= (north - south) * (1.0 - 1.0e-10):
            ycenter = (south + north) * 0.5
        else:
            ycenter = float(
                np.clip(
                    sum(ylim) * 0.5 - dy_pixels * yspan / height,
                    south + yspan * 0.5,
                    north - yspan * 0.5,
                )
            )
        self._draw_map()
        self._syncing_limits = True
        try:
            self._axes.set_xlim(-xspan * 0.5, xspan * 0.5)
            self._axes.set_ylim(ycenter - yspan * 0.5, ycenter + yspan * 0.5)
        finally:
            self._syncing_limits = False
        if self._center_control is not None:
            self._center_control.SetValue(self.center_longitude_deg)
        self._update_scrollbars()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _on_navigation_release(self, _event: Any) -> None:
        self._sync_center_from_extent()

    def _sync_center_from_extent(self) -> None:
        if self._syncing_limits or self._axes is None or self._projection is None:
            return
        midpoint = sum(self._axes.get_xlim()) * 0.5
        longitude, _ = self._projection(midpoint, 0.0, inverse=True)
        center_longitude_deg = _normalized_longitude(float(longitude))
        center_delta_deg = _normalized_longitude(
            center_longitude_deg - self.center_longitude_deg
        )
        if abs(center_delta_deg) > 1.0e-7:
            xlim = self._axes.get_xlim()
            ylim = self._axes.get_ylim()
            xspan = abs(xlim[1] - xlim[0])
            self.center_longitude_deg = center_longitude_deg
            self._draw_map()
            # The new projection places its central meridian at x=0. Keep the
            # current zoom and vertical view while recentering on the new lon_0.
            self._syncing_limits = True
            self._axes.set_xlim(-xspan * 0.5, xspan * 0.5)
            self._axes.set_ylim(ylim)
            self._syncing_limits = False
        if self._center_control is not None:
            self._center_control.SetValue(self.center_longitude_deg)
        self._update_scrollbars()
        if self._canvas is not None:
            self._canvas.draw_idle()

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
