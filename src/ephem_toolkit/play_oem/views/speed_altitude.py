"""Speed and altitude time-series playback view."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ..series import OrbitSeries
from ..time_unit import TimeUnit

RASTER_WIDTH = 760
RASTER_HEIGHT = 280
RASTER_PLOT_LEFT = 58
RASTER_PLOT_RIGHT = 744
RASTER_PLOT_TOP = 20
RASTER_PLOT_BOTTOM = 252
GRID_COLOR = (220, 220, 220)
AXIS_COLOR = (45, 45, 45)
SERIES_COLOR = (31, 119, 180)


@dataclass(frozen=True)
class RasterPlot:
    """Tk-independent raster data for the legacy Tk display path."""

    width: int
    height: int
    ppm_data: bytes
    plot_left: int
    plot_right: int
    x_start: float
    x_end: float
    plot_top: int
    plot_bottom: int

    def cursor_column(self, elapsed_time: float) -> int:
        if self.x_start == self.x_end:
            return (self.plot_left + self.plot_right) // 2
        fraction = (elapsed_time - self.x_start) / (self.x_end - self.x_start)
        fraction = min(max(fraction, 0.0), 1.0)
        return round(self.plot_left + fraction * (self.plot_right - self.plot_left))


class SpeedAltitudeView:
    """Plot speed and altitude histories with a shared time cursor."""

    name = "speed-altitude"

    def __init__(self, t_start_s: float) -> None:
        self._t_start_s = t_start_s
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, Line2D] | None = None
        self._time_divisor_s = 1.0
        self._elapsed_time: np.ndarray | None = None
        self._speed_values: np.ndarray | None = None
        self._altitude_values: np.ndarray | None = None

    def build(self, series: OrbitSeries, time_unit: TimeUnit) -> Figure:
        if self._figure is not None:
            raise RuntimeError("speed/altitude view has already been built")

        figure = Figure(figsize=(8, 6), constrained_layout=True)
        axes_array = figure.subplots(2, 1, sharex=True)
        speed_axes = axes_array[0]
        altitude_axes = axes_array[1]
        speed_axes.plot(series.elapsed_time, series.velocity_magnitude_km_s)
        altitude_axes.plot(series.elapsed_time, series.altitude_km)
        speed_axes.set_ylabel("Speed (km/s)")
        altitude_axes.set_ylabel("Altitude (km)")
        altitude_axes.set_xlabel(time_unit.get_axis_label())
        speed_axes.grid(True)
        altitude_axes.grid(True)
        self._figure = figure
        self._time_divisor_s = time_unit.get_divisor_s()
        self._elapsed_time = series.elapsed_time
        self._speed_values = series.velocity_magnitude_km_s
        self._altitude_values = series.altitude_km
        self._cursor_artists = (
            speed_axes.axvline(0.0, color="tab:red", linestyle="--"),
            altitude_axes.axvline(0.0, color="tab:red", linestyle="--"),
        )
        return figure

    def update(self, t_s: float) -> None:
        if self._cursor_artists is None:
            raise RuntimeError("speed/altitude view has not been built")
        elapsed_time = (t_s - self._t_start_s) / self._time_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time, elapsed_time])

    def render_rasters(self) -> tuple[RasterPlot, RasterPlot]:
        """Render both plots, grids, axes and ticks as PPM images."""
        if (
            self._elapsed_time is None
            or self._speed_values is None
            or self._altitude_values is None
        ):
            raise RuntimeError("speed/altitude view has not been built")
        if len(self._elapsed_time) == 0:
            raise RuntimeError("cannot render an empty speed/altitude series")
        return (
            self._render_raster(self._speed_values),
            self._render_raster(self._altitude_values),
        )

    def _render_raster(self, values: np.ndarray) -> RasterPlot:
        pixels = bytearray(b"\xff" * (RASTER_WIDTH * RASTER_HEIGHT * 3))

        def draw_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
            offset = (y * RASTER_WIDTH + x) * 3
            pixels[offset : offset + 3] = bytes(color)

        def draw_line(
            x_start: int,
            y_start: int,
            x_end: int,
            y_end: int,
            color: tuple[int, int, int],
        ) -> None:
            delta_x = abs(x_end - x_start)
            step_x = 1 if x_start < x_end else -1
            delta_y = -abs(y_end - y_start)
            step_y = 1 if y_start < y_end else -1
            error = delta_x + delta_y
            while True:
                draw_pixel(x_start, y_start, color)
                if x_start == x_end and y_start == y_end:
                    break
                doubled_error = 2 * error
                if doubled_error >= delta_y:
                    error += delta_y
                    x_start += step_x
                if doubled_error <= delta_x:
                    error += delta_x
                    y_start += step_y

        x_start = float(self._elapsed_time[0])
        x_end = float(self._elapsed_time[-1])
        plot_width = RASTER_PLOT_RIGHT - RASTER_PLOT_LEFT
        for division in range(1, 5):
            x = round(RASTER_PLOT_LEFT + division * plot_width / 5)
            draw_line(x, RASTER_PLOT_TOP, x, RASTER_PLOT_BOTTOM, GRID_COLOR)
        for division in range(1, 4):
            y = round(
                RASTER_PLOT_TOP + division * (RASTER_PLOT_BOTTOM - RASTER_PLOT_TOP) / 4
            )
            draw_line(RASTER_PLOT_LEFT, y, RASTER_PLOT_RIGHT, y, GRID_COLOR)

        y_min = float(np.min(values))
        y_max = float(np.max(values))
        value_span = y_max - y_min
        padding = value_span * 0.05 if value_span else max(abs(y_min) * 0.05, 1e-3)
        y_lower = y_min - padding
        y_upper = y_max + padding
        point_limit = plot_width * 3
        indices = np.linspace(
            0, len(values) - 1, min(len(values), point_limit), dtype=int
        )
        points: list[tuple[int, int]] = []
        for index in indices:
            x_value = float(self._elapsed_time[index])
            x = (
                (RASTER_PLOT_LEFT + RASTER_PLOT_RIGHT) // 2
                if x_start == x_end
                else round(
                    RASTER_PLOT_LEFT
                    + (x_value - x_start) / (x_end - x_start) * plot_width
                )
            )
            y_value = float(values[index])
            y = round(
                RASTER_PLOT_BOTTOM
                - (y_value - y_lower)
                / (y_upper - y_lower)
                * (RASTER_PLOT_BOTTOM - RASTER_PLOT_TOP)
            )
            points.append((x, y))
        for first, second in zip(points, points[1:]):
            draw_line(first[0], first[1], second[0], second[1], SERIES_COLOR)
        if len(points) == 1:
            draw_pixel(points[0][0], points[0][1], SERIES_COLOR)

        draw_line(
            RASTER_PLOT_LEFT,
            RASTER_PLOT_TOP,
            RASTER_PLOT_LEFT,
            RASTER_PLOT_BOTTOM,
            AXIS_COLOR,
        )
        draw_line(
            RASTER_PLOT_LEFT,
            RASTER_PLOT_BOTTOM,
            RASTER_PLOT_RIGHT,
            RASTER_PLOT_BOTTOM,
            AXIS_COLOR,
        )
        for division in range(6):
            x = round(RASTER_PLOT_LEFT + division * plot_width / 5)
            draw_line(x, RASTER_PLOT_BOTTOM, x, RASTER_PLOT_BOTTOM + 5, AXIS_COLOR)
        for division in range(5):
            y = round(
                RASTER_PLOT_TOP + division * (RASTER_PLOT_BOTTOM - RASTER_PLOT_TOP) / 4
            )
            draw_line(RASTER_PLOT_LEFT - 5, y, RASTER_PLOT_LEFT, y, AXIS_COLOR)

        ppm_header = f"P6\n{RASTER_WIDTH} {RASTER_HEIGHT}\n255\n".encode("ascii")
        return RasterPlot(
            RASTER_WIDTH,
            RASTER_HEIGHT,
            ppm_header + bytes(pixels),
            RASTER_PLOT_LEFT,
            RASTER_PLOT_RIGHT,
            x_start,
            x_end,
            RASTER_PLOT_TOP,
            RASTER_PLOT_BOTTOM,
        )

    def close(self) -> None:
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
        self._elapsed_time = None
        self._speed_values = None
        self._altitude_values = None
