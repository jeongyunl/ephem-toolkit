"""Angular-velocity playback view."""

from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import series, time_unit
from .plotting import plot_segments

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default angular-velocity figure size in inches."""


class AngularVelocityView:
    """Plot angular-rate histories in degrees and radians per second."""

    name: str = "angular-velocity"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(self, start_time_s: float, object_name: str) -> None:
        """Create an angular-velocity view anchored at an OEM start time."""
        self._start_time_s = start_time_s
        self._object_name = object_name
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, Line2D] | None = None
        self._time_unit_divisor_s = 1.0

    def build(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> Figure:
        """Build the angular-rate histories and synchronized cursor lines."""
        if self._figure is not None:
            raise RuntimeError("angular-velocity view has already been built")
        if (
            orbit_series.elapsed_time.ndim != 1
            or orbit_series.angular_velocity_deg_s.ndim != 1
            or orbit_series.angular_velocity_rad_s.ndim != 1
            or any(
                values.size not in (0, orbit_series.elapsed_time.size)
                for values in (
                    orbit_series.angular_velocity_deg_s,
                    orbit_series.angular_velocity_rad_s,
                )
            )
        ):
            raise ValueError("angular-velocity arrays must match elapsed_time")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        axes_array = figure.subplots(2, 1, sharex=True)
        rates = (
            (
                orbit_series.angular_velocity_deg_s,
                "Angular Velocity (deg/s)",
                "Angular Velocity / Attitude Rate vs Time",
            ),
            (
                orbit_series.angular_velocity_rad_s,
                "Angular Velocity (rad/s)",
                "Angular Velocity / Attitude Rate (rad/s)",
            ),
        )
        cursor_artists: list[Line2D] = []

        for axes, (values, y_label, title) in zip(axes_array, rates):
            axes.grid(True)
            axes.ticklabel_format(style="plain", axis="y")
            axes.set_xlabel(time_unit.get_axis_label())
            axes.set_ylabel(y_label)
            axes.set_title(title)
            if values.size > 1:
                valid_mask = values != 0.0
                rate_lines = plot_segments(
                    axes,
                    orbit_series.elapsed_time[valid_mask],
                    values[valid_mask],
                    orbit_series.segment_ids[valid_mask],
                    linewidth=2,
                    label=f"{self._object_name} angular rate",
                )
                if not rate_lines:
                    axes.plot(
                        [], [], linewidth=2, label=f"{self._object_name} angular rate"
                    )
                axes.legend(loc="upper right")
            else:
                axes.text(0.5, 0.5, "Not enough samples", ha="center", va="center")
            cursor_artists.append(
                axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--")
            )

        self._figure = figure
        self._cursor_artists = (cursor_artists[0], cursor_artists[1])
        self._time_unit_divisor_s = time_unit.get_divisor_s()
        self.update(self._start_time_s)
        return figure

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        if self._cursor_artists is None:
            raise RuntimeError("angular-velocity view has not been built")
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
