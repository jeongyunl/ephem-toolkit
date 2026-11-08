"""Direction-change playback view."""

from __future__ import annotations

from math import pi

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import series, time_unit
from ..oem_data_store import ColumnGroupView, StoreQuery
from ..time_range import ResolvedTimeRange
from .base import (
    StoreViewBinding,
    StoreViewContext,
    TimeRangeSupport,
    add_store_series_paths,
    clear_store_series_artists,
    set_store_series_y_limits,
    store_empty_label,
)
from .plotting import (
    SegmentedPlotHistory,
    set_shared_x_limits,
    time_bounds_to_axis,
)

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default direction-change figure size in inches."""


class DirectionChangeView(TimeRangeSupport):
    """Plot Euler-style direction angles and their rates."""

    name: str = "direction-change"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(self, start_time_s: float, object_name: str) -> None:
        """Create a direction-change view anchored at an OEM start time."""
        self._start_time_s = start_time_s
        self._object_name = object_name
        self._figure: Figure | None = None
        self._cursor_artists: tuple[Line2D, Line2D] | None = None
        self._time_unit_divisor_s = 1.0
        self._histories: tuple[SegmentedPlotHistory, ...] = ()
        self._store_context: StoreViewContext | None = None
        self._store_query: StoreQuery[tuple[ColumnGroupView, ...]] | None = None
        self._store_binding = StoreViewBinding(("series",))
        self._store_artists: tuple[tuple[Artist, ...], tuple[Artist, ...]] = (
            (),
            (),
        )
        self._store_empty_artists: tuple[Text, Text] | None = None
        self._store_start_time_s = start_time_s

    def build_from_store(self, context: StoreViewContext) -> Figure:
        """Build from range-limited direction-rate columns owned by the store."""
        if self._figure is not None:
            raise RuntimeError("direction-change view has already been built")
        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        angle_axes, rate_axes = figure.subplots(2, 1, sharex=True)
        angle_axes.grid(True)
        angle_axes.ticklabel_format(style="plain", axis="y")
        rate_axes.grid(True)
        rate_axes.ticklabel_format(style="plain", axis="y")
        angle_axes.set_xlabel(context.time_unit.get_axis_label())
        angle_axes.set_ylabel("Euler Angle (deg)")
        angle_axes.set_title("Euler-Angle Direction Change vs Time")
        rate_axes.set_xlabel(context.time_unit.get_axis_label())
        rate_axes.set_ylabel("Euler Angle Rate (deg/s)")
        rate_axes.set_title("Euler-Angle Rate vs Time")
        empty_artists = (
            angle_axes.text(
                0.5,
                0.5,
                "",
                ha="center",
                va="center",
                transform=angle_axes.transAxes,
            ),
            rate_axes.text(
                0.5,
                0.5,
                "",
                ha="center",
                va="center",
                transform=rate_axes.transAxes,
            ),
        )

        self._figure = figure
        self._cursor_artists = (
            angle_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
            rate_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
        )
        self._store_empty_artists = empty_artists
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._configure_time_range(
            (angle_axes, rate_axes),
            (),
            self._cursor_artists,
            context.coverage[0],
            self._time_unit_divisor_s,
        )
        self._apply_store_context(context)
        return figure

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh direction histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("direction-change view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        if self._figure is None:
            raise RuntimeError("direction-change view has not been built")
        self._store_binding.bind(context)
        self._store_context = context
        self._store_start_time_s = context.coverage[0]
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._range_start_time_s = self._store_start_time_s
        self._range_divisor_s = self._time_unit_divisor_s
        for axes in self._figure.axes:
            axes.set_xlabel(context.time_unit.get_axis_label())
        super().set_time_range(context.plot_range, context.coverage)
        for axes, artists in zip(self._figure.axes, self._store_artists):
            clear_store_series_artists(axes, artists)

        query = context.series("direction-rates")
        self._store_query = query
        groups = query.value
        angle_columns = ("roll_rad", "pitch_rad", "yaw_rad")
        rate_columns = (
            "roll_rate_rad_s",
            "pitch_rate_rad_s",
            "yaw_rate_rad_s",
        )
        angle_artists: list[Artist] = []
        rate_artists: list[Artist] = []
        angle_scale = 180.0 / pi
        for component, column in enumerate(angle_columns):
            angle_artists.extend(
                add_store_series_paths(
                    self._figure.axes[0],
                    groups,
                    column,
                    self._store_start_time_s,
                    self._time_unit_divisor_s,
                    scale_y=angle_scale,
                    color=f"C{component}",
                    label=f"{self._object_name} {column.split('_')[0]}",
                    linewidth=2,
                )
            )
        for component, column in enumerate(rate_columns):
            rate_artists.extend(
                add_store_series_paths(
                    self._figure.axes[1],
                    groups,
                    column,
                    self._store_start_time_s,
                    self._time_unit_divisor_s,
                    scale_y=angle_scale,
                    color=f"C{component}",
                    label=f"{self._object_name} {column.split('_')[0]} rate",
                    linewidth=2,
                )
            )
        self._store_artists = (tuple(angle_artists), tuple(rate_artists))
        for axes, artists in zip(self._figure.axes, self._store_artists):
            if artists:
                axes.legend(loc="upper right")
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
        if rescale_y:
            set_store_series_y_limits(
                self._figure.axes[0],
                groups,
                angle_columns,
                scale_y=angle_scale,
            )
            set_store_series_y_limits(
                self._figure.axes[1],
                groups,
                rate_columns,
                scale_y=angle_scale,
            )

        limits = time_bounds_to_axis(
            context.plot_range,
            context.coverage,
            self._store_start_time_s,
            self._time_unit_divisor_s,
        )
        set_shared_x_limits(tuple(self._figure.axes), limits)
        self.update(self._last_cursor_time_s)

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
        histories: list[SegmentedPlotHistory] = []

        if orbit_series.euler_angles_deg.size:
            for component, label in enumerate(("roll", "pitch", "yaw")):
                histories.append(
                    SegmentedPlotHistory(
                        angle_axes,
                        orbit_series.elapsed_time,
                        orbit_series.euler_angles_deg[:, component],
                        orbit_series.segment_ids,
                        linewidth=2,
                        label=f"{self._object_name} {label}",
                    )
                )
            angle_axes.legend(loc="upper right")
        else:
            angle_axes.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

        if orbit_series.euler_angle_rates_deg_s.size:
            for component, label in enumerate(("roll", "pitch", "yaw")):
                histories.append(
                    SegmentedPlotHistory(
                        rate_axes,
                        orbit_series.elapsed_time,
                        orbit_series.euler_angle_rates_deg_s[:, component],
                        orbit_series.segment_ids,
                        linewidth=2,
                        label=f"{self._object_name} {label} rate",
                    )
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
        self._histories = tuple(histories)
        self._configure_time_range(
            (angle_axes, rate_axes),
            self._histories,
            self._cursor_artists,
            self._start_time_s,
            self._time_unit_divisor_s,
        )
        self.update(self._start_time_s)
        return figure

    def update_data(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> bool:
        datasets = []
        if orbit_series.euler_angles_deg.size:
            datasets.extend(
                (
                    orbit_series.elapsed_time,
                    orbit_series.euler_angles_deg[:, component],
                    orbit_series.segment_ids,
                )
                for component in range(3)
            )
        if orbit_series.euler_angle_rates_deg_s.size:
            datasets.extend(
                (
                    orbit_series.elapsed_time,
                    orbit_series.euler_angle_rates_deg_s[:, component],
                    orbit_series.segment_ids,
                )
                for component in range(3)
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
            self._store_binding.with_range(bounds, coverage),
            rescale_y=False,
        )

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        if self._cursor_artists is None:
            raise RuntimeError("direction-change view has not been built")
        if self._store_context is not None:
            self._last_cursor_time_s = time_s
            elapsed_time_axis = (
                time_s - self._store_start_time_s
            ) / self._time_unit_divisor_s
            for cursor_artist in self._cursor_artists:
                cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])
            bounds = self._store_context.plot_range
            visible = bounds is not None and bounds.start_s <= time_s <= bounds.end_s
            for cursor_artist in self._cursor_artists:
                cursor_artist.set_visible(visible)
            return
        elapsed_time_axis = (time_s - self._start_time_s) / self._time_unit_divisor_s
        for cursor_artist in self._cursor_artists:
            cursor_artist.set_xdata([elapsed_time_axis, elapsed_time_axis])
        self._set_cursor_visibility(time_s)

    def close(self) -> None:
        """Release the figure and cursor artists."""
        if self._figure is not None:
            self._close_time_range()
            self._figure.clear()
        self._store_binding.close()
        self._store_context = None
        self._store_query = None
        self._store_artists = ((), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None
