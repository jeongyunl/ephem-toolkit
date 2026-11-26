"""Cartesian position and velocity component playback view."""

from __future__ import annotations

from typing import cast

import numpy as np
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import series, time_unit
from ..matplotlib_helpers import create_figure, style_axes
from ..time_range import ResolvedTimeRange
from .base import (
    StoreSeriesPlotView,
    StoreViewContext,
    add_raw_state_paths,
    set_raw_state_y_limits,
    store_empty_label,
)
from .plotting import SegmentedPlotHistory, set_shared_x_limits, time_bounds_to_axis
from .registry import LegacyViewSpecMixin

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


class LegacyStateComponentsView(LegacyViewSpecMixin, StoreSeriesPlotView):
    """Plot X/Y/Z position and VX/VY/VZ velocity histories."""

    name: str = "state-components"
    label: str = "State Components"
    group: str = "state"
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
        self._initialize_store_series(start_time_s)
        self._frame_context: str = frame_context
        self._store_artists: tuple[tuple[Artist, ...], ...] = ((), (), (), (), (), ())
        self._store_empty_artists: tuple[Text, ...] | None = None

    def build_from_store(self, context: StoreViewContext) -> Figure:
        """Build from raw state columns without an OrbitSeries projection."""
        if self._figure is not None:
            raise RuntimeError("state-components view has already been built")
        figure = create_figure(FIGURE_SIZE_INCHES)
        axes_array = cast(
            np.ndarray,
            figure.subplots(
                CARTESIAN_COMPONENT_COUNT,
                STATE_COMPONENT_COLUMN_COUNT,
                sharex=True,
            ),
        )
        cursor_artists: list[Line2D] = []
        empty_artists: list[Text] = []
        component_columns = ((1, 4), (2, 5), (3, 6))
        for row, (position_column, velocity_column) in enumerate(component_columns):
            position_axes = axes_array[row, 0]
            velocity_axes = axes_array[row, 1]
            component = ("X", "Y", "Z")[row]
            position_axes.set_ylabel(f"{component} (km)")
            velocity_axes.set_ylabel(f"V{component} (km/s)")
            position_axes.grid(True)
            velocity_axes.grid(True)
            for axes in (position_axes, velocity_axes):
                empty_artists.append(
                    axes.text(
                        0.5,
                        0.5,
                        "",
                        ha="center",
                        va="center",
                        transform=axes.transAxes,
                    )
                )
                cursor_artists.append(
                    axes.axvline(
                        0.0,
                        color=CURSOR_LINE_COLOR,
                        linestyle="--",
                        animated=True,
                    )
                )
        axes_array[0, 0].set_title("Position")
        axes_array[0, 1].set_title("Velocity")
        axes_array[2, 0].set_xlabel(context.time_unit.get_axis_label())
        axes_array[2, 1].set_xlabel(context.time_unit.get_axis_label())
        figure.suptitle(f"State Components | {self._frame_context}", fontsize=12)

        self._figure = figure
        self._cursor_artists = tuple(cursor_artists)
        self._store_empty_artists = tuple(empty_artists)
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._configure_time_range(
            tuple(axes_array.flat),
            (),
            self._cursor_artists,
            context.coverage[0],
            self._time_unit_divisor_s,
        )
        self._apply_store_context(context)
        return figure

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh raw-state paths from a newer snapshot or plot range."""
        if self._store_context is None:
            raise RuntimeError("state-components view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        self._begin_store_context_update(context, axis_indexes=(4, 5))

        columns = (1, 4, 2, 5, 3, 6)
        artists_by_axis: list[tuple[Artist, ...]] = []
        for axes, column in zip(self._figure.axes, columns):
            artists = add_raw_state_paths(
                axes,
                context.snapshot,
                column,
                self._store_start_time_s,
                self._time_unit_divisor_s,
                bounds=context.plot_range,
                maximum_samples_per_segment=MAX_STATE_COMPONENT_DISPLAY_POINTS_PER_SEGMENT,
                time_sampling=context.time_sampling,
                scale_y=0.001,
                linewidth=1.5,
            )
            artists_by_axis.append(artists)
            if rescale_y:
                set_raw_state_y_limits(axes, context.snapshot, column, scale_y=0.001)
        self._store_artists = tuple(artists_by_axis)
        if self._store_empty_artists is not None:
            for empty_artist, artists in zip(
                self._store_empty_artists, self._store_artists
            ):
                empty_artist.set_text(store_empty_label(context))
                empty_artist.set_visible(not artists)

        limits = time_bounds_to_axis(
            context.plot_range,
            context.coverage,
            self._store_start_time_s,
            self._time_unit_divisor_s,
        )
        set_shared_x_limits(tuple(self._figure.axes), limits)
        self.update(self._last_cursor_time_s)
        style_axes(*self._figure.axes)

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

        figure = create_figure(FIGURE_SIZE_INCHES)
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
        figure.suptitle(f"State Components | {self._frame_context}", fontsize=12)

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
        style_axes(*figure.axes)
        return figure

    def update_data(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> bool:
        datasets = []
        for component in range(CARTESIAN_COMPONENT_COUNT):
            datasets.append(
                (
                    orbit_series.elapsed_time,
                    orbit_series.position_km[:, component],
                    orbit_series.segment_ids,
                )
            )
            datasets.append(
                (
                    orbit_series.elapsed_time,
                    orbit_series.velocity_km_s[:, component],
                    orbit_series.segment_ids,
                )
            )
        return self._update_history_data(
            datasets, self._start_time_s, time_unit.get_divisor_s()
        )

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if self._store_context is None:
            super().set_time_range(bounds, coverage)
            return
        self._apply_store_context(
            self._store_context_for_range(bounds, coverage),
            rescale_y=False,
        )

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
        self._update_store_or_legacy_cursor(time_s)

    def close(self) -> None:
        """Release the figure and cursor artists."""
        self._close_store_series_plot()
        self._store_context = None
        self._store_artists = ((), (), (), (), (), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None
