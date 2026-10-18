"""Direction-change playback view."""

from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import series, time_unit
from .plotting import plot_segments

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default direction-change figure size in inches."""


class DirectionChangeView:
    """Plot Euler-style direction angles and their rates."""

    name: str = "direction-change"

    def __init__(self, start_time_s: float, object_name: str) -> None:
        """Create a direction-change view anchored at an OEM start time."""
        self._start_time_s = start_time_s
        self._object_name = object_name
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, Line2D] | None = None
        self._time_unit_divisor_s = 1.0

    def build(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> Figure:
        """Build direction-angle histories and synchronized cursor lines."""
        if self._figure is not None:
            raise RuntimeError("direction-change view has already been built")
        sample_count = orbit_series.elapsed_time.size
        if (
            orbit_series.elapsed_time.ndim != 1
            or orbit_series.euler_angles_deg.shape not in ((0, 3), (sample_count, 3))
            or orbit_series.euler_angle_rates_deg_s.shape
            not in ((0, 3), (sample_count, 3))
        ):
            raise ValueError("direction-change arrays must match elapsed_time")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        angle_axes, rate_axes = figure.subplots(2, 1, sharex=True)
        angle_axes.grid(True)
        angle_axes.ticklabel_format(style="plain", axis="y")
        rate_axes.grid(True)
        rate_axes.ticklabel_format(style="plain", axis="y")

        if orbit_series.euler_angles_deg.size:
            for component, label in enumerate(("roll", "pitch", "yaw")):
                plot_segments(
                    angle_axes,
                    orbit_series.elapsed_time,
                    orbit_series.euler_angles_deg[:, component],
                    orbit_series.segment_ids,
                    linewidth=2,
                    label=f"{self._object_name} {label}",
                )
            angle_axes.legend(loc="upper right")
        else:
            angle_axes.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

        if orbit_series.euler_angle_rates_deg_s.size:
            for component, label in enumerate(("roll", "pitch", "yaw")):
                plot_segments(
                    rate_axes,
                    orbit_series.elapsed_time,
                    orbit_series.euler_angle_rates_deg_s[:, component],
                    orbit_series.segment_ids,
                    linewidth=2,
                    label=f"{self._object_name} {label} rate",
                )
            rate_axes.legend(loc="upper right")
        else:
            rate_axes.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

        angle_axes.set_xlabel(time_unit.get_axis_label())
        angle_axes.set_ylabel("Euler Angle (deg)")
        angle_axes.set_title("Euler-Angle Direction Change vs Time")
        rate_axes.set_xlabel(time_unit.get_axis_label())
        rate_axes.set_ylabel("Euler Angle Rate (deg/s)")
        rate_axes.set_title("Euler-Angle Rate vs Time")

        self._figure = figure
        self._cursor_artists = (
            angle_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
            rate_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
        )
        self._time_unit_divisor_s = time_unit.get_divisor_s()
        self.update(self._start_time_s)
        return figure

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        if self._cursor_artists is None:
            raise RuntimeError("direction-change view has not been built")
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
