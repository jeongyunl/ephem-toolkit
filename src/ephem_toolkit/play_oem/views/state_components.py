"""Cartesian position and velocity component playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ..series import OrbitSeries
from ..time_unit import TimeUnit
from .raster import RasterImage, render_matplotlib_raster


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

    def render_raster(self) -> RasterImage:
        """Render the complete Matplotlib figure for legacy Tk PhotoImage display."""
        if self._figure is None or self._axes is None or self._cursor_artists is None:
            raise RuntimeError("state-components view has not been built")
        if self._elapsed_time is None:
            raise RuntimeError("state-components time data is unavailable")

        return render_matplotlib_raster(
            self._figure,
            self._axes,
            self._cursor_artists,
        )

    def close(self) -> None:
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._axes = None
        self._cursor_artists = None
        self._elapsed_time = None
