"""Geocentric-distance playback view."""

from __future__ import annotations

import numpy as np
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import series, time_unit
from ..oem_data_store import SeriesGroups, StoreQuery
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
"""Default geocentric-distance figure size in inches."""


class GeocentricDistanceView(TimeRangeSupport):
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
        self._histories: tuple[SegmentedPlotHistory, ...] = ()
        self._store_context: StoreViewContext | None = None
        self._store_query: StoreQuery[SeriesGroups] | None = None
        self._store_binding = StoreViewBinding(("series",))
        self._store_artists: tuple[tuple[Artist, ...], tuple[Artist, ...]] = (
            (),
            (),
        )
        self._store_empty_artists: tuple[Text, Text] | None = None
        self._store_start_time_s = start_time_s

    def build_from_store(self, context: StoreViewContext) -> Figure:
        """Build from range-limited distance columns owned by the data store."""
        if self._figure is not None:
            raise RuntimeError("geocentric-distance view has already been built")
        figure = Figure(figsize=FIGURE_SIZE_INCHES, constrained_layout=True)
        distance_axes, delta_axes = figure.subplots(2, 1, sharex=True)
        distance_axes.set_ylabel("Geocentric Distance (km)")
        distance_axes.set_title("Geocentric Distance vs Time")
        distance_axes.grid(True)
        distance_axes.ticklabel_format(style="plain", axis="y")
        delta_axes.set_xlabel(context.time_unit.get_axis_label())
        delta_axes.set_ylabel("Geocentric Distance Delta (km)")
        delta_axes.set_title("Geocentric Distance Delta vs Time")
        delta_axes.grid(True)
        delta_axes.ticklabel_format(style="plain", axis="y")
        empty_artists = (
            distance_axes.text(
                0.5,
                0.5,
                "",
                ha="center",
                va="center",
                transform=distance_axes.transAxes,
            ),
            delta_axes.text(
                0.5,
                0.5,
                "",
                ha="center",
                va="center",
                transform=delta_axes.transAxes,
            ),
        )

        self._figure = figure
        self._cursor_artists = (
            distance_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
            delta_axes.axvline(0.0, color=CURSOR_LINE_COLOR, linestyle="--"),
        )
        self._store_empty_artists = empty_artists
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._configure_time_range(
            (distance_axes, delta_axes),
            (),
            self._cursor_artists,
            context.coverage[0],
            self._time_unit_divisor_s,
        )
        self._apply_store_context(context)
        return figure

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh distance histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("geocentric-distance view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        if self._figure is None:
            raise RuntimeError("geocentric-distance view has not been built")
        self._store_binding.bind(context)
        self._store_context = context
        self._store_start_time_s = context.coverage[0]
        self._time_unit_divisor_s = context.time_unit.get_divisor_s()
        self._range_start_time_s = self._store_start_time_s
        self._range_divisor_s = self._time_unit_divisor_s
        self._figure.axes[1].set_xlabel(context.time_unit.get_axis_label())
        super().set_time_range(context.plot_range, context.coverage)
        for axes, artists in zip(self._figure.axes, self._store_artists):
            clear_store_series_artists(axes, artists)

        query = context.series_groups(("kinematics", "distance-delta"))
        self._store_query = query
        kinematics = query.value["kinematics"]
        distance_deltas = query.value["distance-delta"]
        distance_artists = add_store_series_paths(
            self._figure.axes[0],
            kinematics,
            "distance_m",
            self._store_start_time_s,
            self._time_unit_divisor_s,
            scale_y=0.001,
            color="C0",
            label=self._object_name,
            linewidth=2,
        )
        delta_artists = add_store_series_paths(
            self._figure.axes[1],
            distance_deltas,
            "delta_distance_m",
            self._store_start_time_s,
            self._time_unit_divisor_s,
            scale_y=0.001,
            color="C0",
            label=f"{self._object_name} delta",
            linewidth=2,
        )
        self._store_artists = (distance_artists, delta_artists)
        if distance_artists:
            self._figure.axes[0].legend(loc="upper right")
            if rescale_y:
                set_store_series_y_limits(
                    self._figure.axes[0],
                    kinematics,
                    ("distance_m",),
                    scale_y=0.001,
                )
        if delta_artists:
            self._figure.axes[1].legend(loc="upper right")
            if rescale_y:
                set_store_series_y_limits(
                    self._figure.axes[1],
                    distance_deltas,
                    ("delta_distance_m",),
                    scale_y=0.001,
                )
        if self._store_empty_artists is not None:
            for index, (empty_artist, artists) in enumerate(
                zip(self._store_empty_artists, self._store_artists)
            ):
                empty_artist.set_text(
                    store_empty_label(
                        context,
                        not_enough_samples=(
                            index == 1 and context.snapshot.sample_count < 2
                        ),
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
        histories = [
            SegmentedPlotHistory(
                distance_axes,
                orbit_series.elapsed_time,
                orbit_series.geocentric_distance_km,
                orbit_series.segment_ids,
                linewidth=2,
                label=self._object_name,
            )
        ]
        distance_axes.set_ylabel("Geocentric Distance (km)")
        distance_axes.set_title("Geocentric Distance vs Time")
        distance_axes.grid(True)
        distance_axes.ticklabel_format(style="plain", axis="y")
        distance_axes.legend(loc="upper right")

        if orbit_series.geocentric_distance_km.size > 1:
            distance_delta_km = np.diff(orbit_series.geocentric_distance_km)
            histories.append(
                SegmentedPlotHistory(
                    delta_axes,
                    orbit_series.elapsed_time[1:],
                    distance_delta_km,
                    orbit_series.rtn_segment_ids,
                    linewidth=2,
                    label=f"{self._object_name} delta",
                )
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
        self._histories = tuple(histories)
        self._configure_time_range(
            (distance_axes, delta_axes),
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
        datasets = [
            (
                orbit_series.elapsed_time,
                orbit_series.geocentric_distance_km,
                orbit_series.segment_ids,
            )
        ]
        if orbit_series.geocentric_distance_km.size > 1:
            datasets.append(
                (
                    orbit_series.elapsed_time[1:],
                    orbit_series.geocentric_distance_km[1:]
                    - orbit_series.geocentric_distance_km[:-1],
                    orbit_series.rtn_segment_ids,
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
            self._store_binding.with_range(bounds, coverage),
            rescale_y=False,
        )

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        if self._cursor_artists is None:
            raise RuntimeError("geocentric-distance view has not been built")
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
