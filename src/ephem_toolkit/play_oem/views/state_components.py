"""Cartesian position and velocity component playback view."""

from __future__ import annotations

from typing import cast

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import series, time_unit
from .base import TimeRangeSupport
from .plotting import SegmentedPlotHistory

CARTESIAN_COMPONENT_COUNT: int = 3
"""Number of Cartesian position or velocity components."""
CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (10.0, 8.0)
"""Default state-components figure size in inches."""
MAX_STATE_COMPONENT_DISPLAY_POINTS_PER_SEGMENT: int = 500
"""Display-point cap for each state-component line."""
STATE_COMPONENT_COLUMN_COUNT: int = 2
"""Number of columns for position and velocity plots."""


class StateComponentsView(TimeRangeSupport):
    """Plot X/Y/Z position and VX/VY/VZ velocity histories."""

    name: str = "state-components"
    animated_cursor_updates: bool = True

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(self, start_time_s: float, frame_context: str) -> None:
        """Create a state-components view for one frame context.

        Parameters
        ----------
        start_time_s : float
            Absolute OEM start time in TT seconds since J2000.
        frame_context : str
            Reference-frame and origin description used in the figure title.
        """
        self._start_time_s: float = start_time_s
        self._frame_context: str = frame_context
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, ...] | None = None
        self._time_unit_divisor_s: float = 1.0
        self._histories: tuple[SegmentedPlotHistory, ...] = ()

    def build(
        self,
        orbit_series: series.OrbitSeries,
        time_unit: time_unit.TimeUnit,
    ) -> Figure:
        """Build six Cartesian component histories and synchronized cursors.

        Parameters
        ----------
        orbit_series : series.OrbitSeries
            Derived position, velocity, and elapsed-time histories.
        time_unit : time_unit.TimeUnit
            Display unit used for the elapsed-time axes.

        Returns
        -------
        Figure
            Matplotlib figure containing position and velocity component plots.

        Raises
        ------
        RuntimeError
            If this view has already been built.
        ValueError
            If the series is empty or the Cartesian arrays have invalid shapes.
        """
        if self._figure is not None:
            raise RuntimeError("state-components view has already been built")
        if len(orbit_series.elapsed_time) == 0:
            raise ValueError("cannot plot an empty state-components series")
        if orbit_series.position_km.shape != (
            len(orbit_series.elapsed_time),
            CARTESIAN_COMPONENT_COUNT,
        ) or orbit_series.velocity_km_s.shape != (
            len(orbit_series.elapsed_time),
            CARTESIAN_COMPONENT_COUNT,
        ):
            raise ValueError("state component arrays must have shape (N, 3)")

        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        axes_array = cast(
            np.ndarray,
            figure.subplots(
                CARTESIAN_COMPONENT_COUNT,
                STATE_COMPONENT_COLUMN_COUNT,
                sharex=True,
            ),
        )
        cursor_artists: list[Line2D] = []
        histories: list[SegmentedPlotHistory] = []
        component_labels = ("X", "Y", "Z")

        for row, component in enumerate(component_labels):
            position_axes = axes_array[row, 0]
            velocity_axes = axes_array[row, 1]
            histories.append(
                SegmentedPlotHistory(
                    position_axes,
                    orbit_series.elapsed_time,
                    orbit_series.position_km[:, row],
                    orbit_series.segment_ids,
                    max_display_points=MAX_STATE_COMPONENT_DISPLAY_POINTS_PER_SEGMENT,
                )
            )
            histories.append(
                SegmentedPlotHistory(
                    velocity_axes,
                    orbit_series.elapsed_time,
                    orbit_series.velocity_km_s[:, row],
                    orbit_series.segment_ids,
                    max_display_points=MAX_STATE_COMPONENT_DISPLAY_POINTS_PER_SEGMENT,
                )
            )
            position_axes.set_ylabel(f"{component} (km)")
            velocity_axes.set_ylabel(f"V{component} (km/s)")
            position_axes.grid(True)
            velocity_axes.grid(True)
            cursor_artists.append(
                position_axes.axvline(
                    0.0,
                    color=CURSOR_LINE_COLOR,
                    linestyle="--",
                    animated=True,
                )
            )
            cursor_artists.append(
                velocity_axes.axvline(
                    0.0,
                    color=CURSOR_LINE_COLOR,
                    linestyle="--",
                    animated=True,
                )
            )

        axes_array[0, 0].set_title("Position")
        axes_array[0, 1].set_title("Velocity")
        axes_array[2, 0].set_xlabel(time_unit.get_axis_label())
        axes_array[2, 1].set_xlabel(time_unit.get_axis_label())
        figure.suptitle(f"State Components | {self._frame_context}")

        self._figure = figure
        self._cursor_artists = tuple(cursor_artists)
        self._time_unit_divisor_s = time_unit.get_divisor_s()
        self._histories = tuple(histories)
        self._configure_time_range(
            tuple(axes_array.flat),
            self._histories,
            self._cursor_artists,
            self._start_time_s,
            self._time_unit_divisor_s,
        )
        self.update(self._start_time_s)
        return figure

    def update(self, time_s: float) -> None:
        """Move every component cursor to an absolute OEM time.

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
            raise RuntimeError("state-components view has not been built")
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])
        self._set_cursor_visibility(time_s)

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._close_time_range()
            self._figure.clear()
        self._figure = None
        self._cursor_artists = None
