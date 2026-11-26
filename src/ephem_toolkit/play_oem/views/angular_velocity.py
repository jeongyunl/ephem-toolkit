"""Angular-velocity playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import series, time_unit
from ..matplotlib_helpers import create_figure, style_axes
from ..oem_data_store import ColumnGroupView, StoreQuery
from ..time_range import ResolvedTimeRange
from .base import (
    StoreSeriesPlotView,
    StoreViewContext,
    add_store_series_paths,
    set_store_series_y_limits,
    store_empty_label,
)
from .plotting import (
    SegmentedPlotHistory,
    set_shared_x_limits,
    time_bounds_to_axis,
)
from .registry import ViewSpecMixin

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default angular-velocity figure size in inches."""


class AngularVelocityView(ViewSpecMixin, StoreSeriesPlotView):
    """Plot angular-rate histories in degrees and radians per second."""

    name: str = "angular-velocity"
    label: str = "Angular Velocity"
    group: str = "motion"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(self, start_time_s: float, object_name: str) -> None:
        """Create an angular-velocity view anchored at an OEM start time."""
        self._initialize_store_series(start_time_s)
        self._object_name = object_name
        self._store_query: StoreQuery[tuple[ColumnGroupView, ...]] | None = None
        self._store_artists: tuple[tuple[Artist, ...], ...] = ((), ())
        self._store_empty_artists: tuple[Text, ...] | None = None

    def build_from_store(self, context: StoreViewContext) -> Figure:
        """Build from range-limited angular-rate columns owned by the store."""
        if self._figure is not None:
            raise RuntimeError("angular-velocity view has already been built")
        figure = create_figure(FIGURE_SIZE_INCHES)
        axes_array = figure.subplots(2, 1, sharex=True)
        rates = (
            ("Angular Velocity (deg/s)", "Angular Velocity / Attitude Rate vs Time"),
            (
                "Angular Velocity (rad/s)",
                "Angular Velocity / Attitude Rate (rad/s)",
            ),
        )
        empty_artists: list[Text] = []
        cursor_artists: list[Line2D] = []
        for axes, (y_label, title) in zip(axes_array, rates):
            axes.grid(True)
            axes.ticklabel_format(style="plain", axis="y")
            axes.set_xlabel(context.time_unit.get_axis_label())
            axes.set_ylabel(y_label)
            axes.set_title(title)
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
                axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--")
            )

        self._figure = figure
        self._cursor_artists = (cursor_artists[0], cursor_artists[1])
        self._store_empty_artists = tuple(empty_artists)
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._configure_time_range(
            (axes_array[0], axes_array[1]),
            (),
            self._cursor_artists,
            context.coverage[0],
            self._time_unit_divisor_s,
        )
        self._apply_store_context(context)
        return figure

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh angular-rate histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("angular-velocity view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        self._begin_store_context_update(context)

        query = context.series("direction-rates")
        self._store_query = query
        groups = query.value
        columns = ("angular_velocity_rad_s", "angular_velocity_rad_s")
        scales = (180.0 / np.pi, 1.0)
        artists_by_axis: list[tuple[Artist, ...]] = []
        for axes, column, scale in zip(self._figure.axes, columns, scales):
            artists = add_store_series_paths(
                axes,
                groups,
                column,
                self._store_start_time_s,
                self._time_unit_divisor_s,
                scale_y=scale,
                color="C0",
                label=f"{self._object_name} angular rate",
                linewidth=2,
                mask_zero=True,
                minimum_samples=2 if context.snapshot.sample_count < 2 else 1,
            )
            artists_by_axis.append(artists)
            if artists:
                axes.legend(loc="upper right")
                if rescale_y:
                    set_store_series_y_limits(axes, groups, (column,), scale_y=scale)
        self._store_artists = tuple(artists_by_axis)
        if self._store_empty_artists is not None:
            for empty_artist, artists in zip(
                self._store_empty_artists, self._store_artists
            ):
                empty_artist.set_text(
                    store_empty_label(
                        context,
                        not_enough_samples=context.snapshot.sample_count < 2,
                    )
                )
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

        figure = create_figure(FIGURE_SIZE_INCHES)
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
        histories: list[SegmentedPlotHistory] = []

        for axes, (values, y_label, title) in zip(axes_array, rates):
            axes.grid(True)
            axes.ticklabel_format(style="plain", axis="y")
            axes.set_xlabel(time_unit.get_axis_label())
            axes.set_ylabel(y_label)
            axes.set_title(title)
            if values.size > 1:
                valid_segments = np.where(values != 0.0, orbit_series.segment_ids, -1)
                rate_history = SegmentedPlotHistory(
                    axes,
                    orbit_series.elapsed_time,
                    values,
                    valid_segments,
                    linewidth=2,
                    label=f"{self._object_name} angular rate",
                )
                histories.append(rate_history)
                if not rate_history.artists:
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
        self._histories = tuple(histories)
        self._configure_time_range(
            (axes_array[0], axes_array[1]),
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
        for values in (
            orbit_series.angular_velocity_deg_s,
            orbit_series.angular_velocity_rad_s,
        ):
            if values.size > 1:
                datasets.append(
                    (
                        orbit_series.elapsed_time,
                        values,
                        np.where(values != 0.0, orbit_series.segment_ids, -1),
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
        """Move each cursor line to an absolute OEM time."""
        self._update_store_or_legacy_cursor(time_s)

    def close(self) -> None:
        """Release the figure and cursor artists."""
        self._close_store_series_plot()
        self._store_query = None
        self._store_artists = ((), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None
