"""Speed and altitude time-series playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ..series import OrbitSeries
from ..time_unit import TimeUnit
from .raster import RasterImage, render_matplotlib_raster


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

    def render_raster(self) -> RasterImage:
        """Render the Matplotlib figure as a PPM image for classic Tk."""
        if (
            self._figure is None
            or self._cursor_artists is None
            or self._elapsed_time is None
        ):
            raise RuntimeError("speed/altitude view has not been built")
        if len(self._elapsed_time) == 0:
            raise RuntimeError("cannot render an empty speed/altitude series")
        return render_matplotlib_raster(
            self._figure,
            self._figure.axes,
            self._cursor_artists,
        )

    def close(self) -> None:
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
        self._elapsed_time = None
        self._speed_values = None
        self._altitude_values = None
