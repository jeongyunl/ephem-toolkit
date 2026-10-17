"""Speed and altitude time-series playback view."""

from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import series, time_unit

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default speed/altitude figure size in inches."""


class SpeedAltitudeView:
    """Plot speed and altitude histories with a shared time cursor."""

    name: str = "speed-altitude"

    def __init__(self, start_time_s: float) -> None:
        """Create a speed/altitude view anchored at an OEM start time.

        Parameters
        ----------
        start_time_s : float
            Absolute OEM start time in TT seconds since J2000.
        """
        self._start_time_s: float = start_time_s
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, Line2D] | None = None
        self._time_unit_divisor_s: float = 1.0

    def build(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> Figure:
        """Build the speed and altitude histories with cursor lines.

        Parameters
        ----------
        orbit_series : series.OrbitSeries
            Derived speed, altitude, and elapsed-time histories.
        time_unit : time_unit.TimeUnit
            Display unit used for the elapsed-time axis.

        Returns
        -------
        Figure
            Matplotlib figure containing the two time-series plots.

        Raises
        ------
        RuntimeError
            If this view has already been built.
        """
        if self._figure is not None:
            raise RuntimeError("speed/altitude view has already been built")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        axes_array = figure.subplots(2, 1, sharex=True)
        speed_axes = axes_array[0]
        altitude_axes = axes_array[1]
        speed_axes.plot(
            orbit_series.elapsed_time,
            orbit_series.velocity_magnitude_km_s,
        )
        altitude_axes.plot(orbit_series.elapsed_time, orbit_series.altitude_km)
        speed_axes.set_ylabel("Speed (km/s)")
        altitude_axes.set_ylabel("Altitude (km)")
        altitude_axes.set_xlabel(time_unit.get_axis_label())
        speed_axes.grid(True)
        altitude_axes.grid(True)
        self._figure = figure
        self._time_unit_divisor_s = time_unit.get_divisor_s()
        self._cursor_artists = (
            speed_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
            altitude_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
        )
        return figure

    def update(self, time_s: float) -> None:
        """Move both cursor lines to an absolute OEM time.

        Parameters
        ----------
        time_s : float
            Absolute OEM time in TT seconds since J2000.

        Raises
        ------
        RuntimeError
            If this view has not been built.
        """
        if self._cursor_artists is None:
            raise RuntimeError("speed/altitude view has not been built")
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
