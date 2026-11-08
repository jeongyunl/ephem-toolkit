"""RTN position-delta playback view."""

from __future__ import annotations

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import series, time_unit
from ..oem_data_store import ColumnGroupView, StoreQuery
from ..time_range import ResolvedTimeRange
from .base import (
    StoreViewContext,
    StoreViewBinding,
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
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 7.0)
"""Default RTN-delta figure size in inches."""


class RtnDeltaView(TimeRangeSupport):
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
        self._histories: tuple[SegmentedPlotHistory, ...] = ()
        self._store_context: StoreViewContext | None = None
        self._store_query: StoreQuery[tuple[ColumnGroupView, ...]] | None = None
        self._store_binding = StoreViewBinding(("series",))
        self._store_artists: tuple[tuple[Artist, ...], ...] = ((), (), ())
        self._store_empty_artists: tuple[Text, ...] | None = None
        self._store_start_time_s = start_time_s

    def build_from_store(self, context: StoreViewContext) -> Figure:
        """Build from range-limited RTN columns owned by the data store."""
        if self._figure is not None:
            raise RuntimeError("RTN-delta view has already been built")
        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        axes_array = figure.subplots(3, 1, sharex=True)
        titles = (
            "Radial Position Delta vs Time",
            "Transverse Position Delta vs Time",
            "Normal Position Delta vs Time",
        )
        labels = ("Radial Delta (km)", "Transverse Delta (km)", "Normal Delta (km)")
        empty_artists: list[Text] = []
        cursor_artists: list[Line2D] = []
        for component, axes in enumerate(axes_array):
            axes.grid(True)
            axes.ticklabel_format(style="plain", axis="y")
            axes.set_ylabel(labels[component])
            axes.set_title(titles[component])
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
        axes_array[-1].set_xlabel(context.time_unit.get_axis_label())

        self._figure = figure
        self._cursor_artists = tuple(cursor_artists)
        self._store_empty_artists = tuple(empty_artists)
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._configure_time_range(
            tuple(axes_array),
            (),
            self._cursor_artists,
            context.coverage[0],
            self._time_unit_divisor_s,
        )
        self._apply_store_context(context)
        return figure

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh the RTN histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("RTN-delta view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        if self._figure is None:
            raise RuntimeError("RTN-delta view has not been built")
        self._store_binding.bind(context)
        self._store_context = context
        self._store_start_time_s = context.coverage[0]
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._range_start_time_s = self._store_start_time_s
        self._range_divisor_s = self._time_unit_divisor_s
        self._figure.axes[-1].set_xlabel(context.time_unit.get_axis_label())
        super().set_time_range(context.plot_range, context.coverage)
        for axes, artists in zip(self._figure.axes, self._store_artists):
            clear_store_series_artists(axes, artists)

        query = context.series("rtn")
        self._store_query = query
        groups = query.value
        columns = ("delta_r_m", "delta_t_m", "delta_n_m")
        artists_by_axis: list[tuple[Artist, ...]] = []
        for axes, column in zip(self._figure.axes, columns):
            artists = add_store_series_paths(
                axes,
                groups,
                column,
                self._store_start_time_s,
                self._time_unit_divisor_s,
                scale_y=0.001,
                color="C0",
                label=self._object_name,
                linewidth=2,
            )
            artists_by_axis.append(artists)
            if artists:
                axes.legend(loc="upper right")
                if rescale_y:
                    set_store_series_y_limits(
                        axes, groups, (column,), scale_y=0.001
                    )
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
        histories: list[SegmentedPlotHistory] = []

        for component, axes in enumerate(axes_array):
            axes.grid(True)
            axes.ticklabel_format(style="plain", axis="y")
            axes.set_ylabel(labels[component])
            axes.set_title(titles[component])
            if orbit_series.rtn_delta_km.size:
                histories.append(
                    SegmentedPlotHistory(
                        axes,
                        orbit_series.rtn_elapsed_time,
                        orbit_series.rtn_delta_km[:, component],
                        orbit_series.rtn_segment_ids,
                        linewidth=2,
                        label=self._object_name,
                    )
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
        self._histories = tuple(histories)
        self._configure_time_range(
            tuple(axes_array),
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
        datasets = tuple(
            (
                orbit_series.rtn_elapsed_time,
                orbit_series.rtn_delta_km[:, component],
                orbit_series.rtn_segment_ids,
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
            raise RuntimeError("RTN-delta view has not been built")
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
        self._store_artists = ((), (), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None
