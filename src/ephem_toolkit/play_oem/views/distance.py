"""Geocentric-distance playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import series, time_unit
from .plotting import plot_segments

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default geocentric-distance figure size in inches."""


class GeocentricDistanceView:
    """Plot geocentric distance and sample-to-sample distance deltas."""

    name: str = "distance"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(self, start_time_s: float, object_name: str) -> None:
        """Create a geocentric-distance view anchored at an OEM start time."""
        self._start_time_s = start_time_s
        self._object_name = object_name
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, Line2D] | None = None
        self._time_unit_divisor_s = 1.0

    def build(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> Figure:
        """Build distance histories and synchronized cursor lines."""
        if self._figure is not None:
            raise RuntimeError("geocentric-distance view has already been built")
        if (
            orbit_series.elapsed_time.ndim != 1
            or orbit_series.geocentric_distance_km.ndim != 1
            or orbit_series.geocentric_distance_km.size
            != orbit_series.elapsed_time.size
        ):
            raise ValueError("geocentric-distance arrays must match elapsed_time")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        distance_axes, delta_axes = figure.subplots(2, 1, sharex=True)
        plot_segments(
            distance_axes,
            orbit_series.elapsed_time,
            orbit_series.geocentric_distance_km,
            orbit_series.segment_ids,
            linewidth=2,
            label=self._object_name,
        )
        distance_axes.set_ylabel("Geocentric Distance (km)")
        distance_axes.set_title("Geocentric Distance vs Time")
        distance_axes.grid(True)
        distance_axes.ticklabel_format(style="plain", axis="y")
        distance_axes.legend(loc="upper right")

        if orbit_series.geocentric_distance_km.size > 1:
            distance_delta_km = np.diff(orbit_series.geocentric_distance_km)
            plot_segments(
                delta_axes,
                orbit_series.elapsed_time[1:],
                distance_delta_km,
                orbit_series.rtn_segment_ids,
                linewidth=2,
                label=f"{self._object_name} delta",
            )
            delta_axes.legend(loc="upper right")
        else:
            delta_axes.text(0.5, 0.5, "Not enough samples", ha="center", va="center")
        delta_axes.set_xlabel(time_unit.get_axis_label())
        delta_axes.set_ylabel("Geocentric Distance Delta (km)")
        delta_axes.set_title("Geocentric Distance Delta vs Time")
        delta_axes.grid(True)
        delta_axes.ticklabel_format(style="plain", axis="y")

        self._figure = figure
        self._cursor_artists = (
            distance_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
            delta_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
        )
        self._time_unit_divisor_s = time_unit.get_divisor_s()
        self.update(self._start_time_s)
        return figure

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        if self._cursor_artists is None:
            raise RuntimeError("geocentric-distance view has not been built")
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
