"""Cartesian position and velocity component playback view."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ..series import OrbitSeries
from ..time_unit import TimeUnit


@dataclass(frozen=True)
class RasterPanel:
    """Plot bounds and time range for one panel in the legacy Tk image."""

    plot_left: int
    plot_right: int
    plot_top: int
    plot_bottom: int
    x_start: float
    x_end: float

    def cursor_column(self, elapsed_time: float) -> int:
        if self.x_start == self.x_end:
            return (self.plot_left + self.plot_right) // 2
        fraction = (elapsed_time - self.x_start) / (self.x_end - self.x_start)
        fraction = min(max(fraction, 0.0), 1.0)
        return round(self.plot_left + fraction * (self.plot_right - self.plot_left))

    def elapsed_at(self, pixel_x: int) -> float:
        if self.plot_left == self.plot_right or self.x_start == self.x_end:
            return self.x_start
        fraction = (pixel_x - self.plot_left) / (self.plot_right - self.plot_left)
        fraction = min(max(fraction, 0.0), 1.0)
        return self.x_start + fraction * (self.x_end - self.x_start)

    def contains_plot_point(self, pixel_x: int, pixel_y: int) -> bool:
        return (
            self.plot_left <= pixel_x <= self.plot_right
            and self.plot_top <= pixel_y <= self.plot_bottom
        )


@dataclass(frozen=True)
class StateComponentsRaster:
    """Matplotlib-rendered panels and their coordinates for legacy Tk."""

    width: int
    height: int
    ppm_data: bytes
    panels: tuple[RasterPanel, ...]


class StateComponentsView:
    """Plot X/Y/Z position and VX/VY/VZ velocity histories."""

    name = "state-components"

    def __init__(self, t_start_s: float, frame_context: str) -> None:
        self._t_start_s = t_start_s
        self._frame_context = frame_context
        self._figure: Figure | None = None
        self._axes: tuple[Axes, ...] | None = None
        self._cursor_artists: tuple[Line2D, ...] | None = None
        self._time_divisor_s = 1.0
        self._elapsed_time: np.ndarray | None = None

    def build(self, series: OrbitSeries, time_unit: TimeUnit) -> Figure:
        if self._figure is not None:
            raise RuntimeError("state-components view has already been built")
        if len(series.elapsed_time) == 0:
            raise ValueError("cannot plot an empty state-components series")
        if series.position_km.shape != (
            len(series.elapsed_time),
            3,
        ) or series.velocity_km_s.shape != (len(series.elapsed_time), 3):
            raise ValueError("state component arrays must have shape (N, 3)")

        figure = Figure(figsize=(10, 8), constrained_layout=True)
        axes_array = figure.subplots(3, 2, sharex=True)
        axes = tuple(axes_array[row, column] for row in range(3) for column in range(2))
        cursor_artists: list[Line2D] = []
        component_labels = ("X", "Y", "Z")

        for row, component in enumerate(component_labels):
            position_axes = axes_array[row, 0]
            velocity_axes = axes_array[row, 1]
            position_axes.plot(series.elapsed_time, series.position_km[:, row])
            velocity_axes.plot(series.elapsed_time, series.velocity_km_s[:, row])
            position_axes.set_ylabel(f"{component} (km)")
            velocity_axes.set_ylabel(f"V{component} (km/s)")
            position_axes.grid(True)
            velocity_axes.grid(True)
            cursor_artists.append(
                position_axes.axvline(0.0, color="tab:red", linestyle="--")
            )
            cursor_artists.append(
                velocity_axes.axvline(0.0, color="tab:red", linestyle="--")
            )

        axes_array[0, 0].set_title("Position")
        axes_array[0, 1].set_title("Velocity")
        axes_array[2, 0].set_xlabel(time_unit.get_axis_label())
        axes_array[2, 1].set_xlabel(time_unit.get_axis_label())
        figure.suptitle(f"State Components | {self._frame_context}")

        self._figure = figure
        self._axes = axes
        self._cursor_artists = tuple(cursor_artists)
        self._time_divisor_s = time_unit.get_divisor_s()
        self._elapsed_time = series.elapsed_time
        self.update(self._t_start_s)
        return figure

    def update(self, t_s: float) -> None:
        if self._cursor_artists is None:
            raise RuntimeError("state-components view has not been built")
        elapsed_time = (t_s - self._t_start_s) / self._time_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time, elapsed_time])

    def render_raster(self) -> StateComponentsRaster:
        """Render the complete Matplotlib figure for legacy Tk PhotoImage display."""
        if self._figure is None or self._axes is None or self._cursor_artists is None:
            raise RuntimeError("state-components view has not been built")
        if self._elapsed_time is None:
            raise RuntimeError("state-components time data is unavailable")

        cursor_visibility = tuple(
            cursor_artist.get_visible() for cursor_artist in self._cursor_artists
        )
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_visible(False)
        try:
            canvas = FigureCanvasAgg(self._figure)
            canvas.draw()
            width, height = canvas.get_width_height()
            renderer = canvas.get_renderer()
            panels = tuple(
                self._raster_panel(axes, renderer, width, height) for axes in self._axes
            )
            pixels = np.asarray(canvas.buffer_rgba(), dtype=np.uint8)[:, :, :3]
            ppm_header = f"P6\n{width} {height}\n255\n".encode("ascii")
            return StateComponentsRaster(
                width,
                height,
                ppm_header + np.ascontiguousarray(pixels).tobytes(),
                panels,
            )
        finally:
            for cursor_artist, visible in zip(self._cursor_artists, cursor_visibility):
                cursor_artist.set_visible(visible)

    def close(self) -> None:
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._axes = None
        self._cursor_artists = None
        self._elapsed_time = None

    def _raster_panel(
        self, axes: Axes, renderer, width: int, height: int
    ) -> RasterPanel:
        bounds = axes.get_window_extent(renderer)
        x_start, x_end = axes.get_xlim()
        return RasterPanel(
            max(0, int(np.floor(bounds.x0))),
            min(width - 1, int(np.ceil(bounds.x1)) - 1),
            max(0, height - int(np.ceil(bounds.y1))),
            min(height - 1, height - int(np.floor(bounds.y0)) - 1),
            float(x_start),
            float(x_end),
        )
