"""RTN position-delta playback view."""

from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import series, time_unit
from .plotting import plot_segments

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 7.0)
"""Default RTN-delta figure size in inches."""


class RtnDeltaView:
    """Plot sample-to-sample radial, transverse, and normal position deltas."""

    name: str = "rtn"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(self, start_time_s: float, object_name: str) -> None:
        """Create an RTN-delta view anchored at an OEM start time."""
        self._start_time_s = start_time_s
        self._object_name = object_name
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, ...] | None = None
        self._time_unit_divisor_s = 1.0

    def build(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> Figure:
        """Build the RTN delta histories and synchronized cursor lines."""
        if self._figure is not None:
            raise RuntimeError("RTN-delta view has already been built")
        if (
            orbit_series.rtn_delta_km.ndim != 2
            or orbit_series.rtn_delta_km.shape[1] != 6
            or orbit_series.rtn_elapsed_time.ndim != 1
            or len(orbit_series.rtn_elapsed_time) != len(orbit_series.rtn_delta_km)
        ):
            raise ValueError("RTN delta arrays must have shapes (N-1,) and (N-1, 6)")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        axes_array = figure.subplots(3, 1, sharex=True)
        titles = (
            "Radial Position Delta vs Time",
            "Transverse Position Delta vs Time",
            "Normal Position Delta vs Time",
        )
        labels = ("Radial Delta (km)", "Transverse Delta (km)", "Normal Delta (km)")
        cursor_artists: list[Line2D] = []

        for component, axes in enumerate(axes_array):
            axes.grid(True)
            axes.ticklabel_format(style="plain", axis="y")
            axes.set_ylabel(labels[component])
            axes.set_title(titles[component])
            if orbit_series.rtn_delta_km.size:
                plot_segments(
                    axes,
                    orbit_series.rtn_elapsed_time,
                    orbit_series.rtn_delta_km[:, component],
                    orbit_series.rtn_segment_ids,
                    linewidth=2,
                    label=self._object_name,
                )
                axes.legend(loc="upper right")
            elif component == 0:
                axes.text(0.5, 0.5, "Not enough samples", ha="center", va="center")
            cursor_artists.append(
                axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--")
            )

        axes_array[-1].set_xlabel(time_unit.get_axis_label())
        self._figure = figure
        self._cursor_artists = tuple(cursor_artists)
        self._time_unit_divisor_s = time_unit.get_divisor_s()
        self.update(self._start_time_s)
        return figure

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        if self._cursor_artists is None:
            raise RuntimeError("RTN-delta view has not been built")
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
