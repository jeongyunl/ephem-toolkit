"""Geocentric-distance playback view."""

from __future__ import annotations

import numpy as np
import wx
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import time_unit
from ..matplotlib_helpers import create_figure, style_axes
from ..oem_data_store import SeriesGroups, StoreQuery
from ..time_range import ResolvedTimeRange
from .data_view_base import (
    StoreViewContext,
    add_store_series_paths,
    set_store_series_y_limits,
    store_empty_label,
)
from .orbit_time_series import OrbitTimeSeriesView
from .plotting import (
    set_shared_x_limits,
    time_bounds_to_axis,
)

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default geocentric-distance figure size in inches."""


class GeocentricDistanceView(OrbitTimeSeriesView):
    """Plot geocentric distance and sample-to-sample distance deltas."""

    name: str = "distance"
    label: str = "Geocentric Distance"
    group: str = "motion"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(
        self,
        start_time_s: float,
        object_name: str,
        *,
        panel: wx.Window | None = None,
        on_seek: object = None,
    ) -> None:
        """Create a geocentric-distance view anchored at an OEM start time."""
        super().__init__(start_time_s, panel=panel, on_seek=on_seek)
        self._object_name = object_name
        self._store_query: StoreQuery[SeriesGroups] | None = None
        self._store_artists: tuple[tuple[Artist, ...], tuple[Artist, ...]] = (
            (),
            (),
        )
        self._store_empty_artists: tuple[Text, Text] | None = None

    def build_from_store(self, context: StoreViewContext) -> Figure | wx.Window:
        """Build from range-limited distance columns owned by the data store."""
        if self._figure is not None:
            raise RuntimeError("geocentric-distance view has already been built")
        figure = create_figure(FIGURE_SIZE_INCHES)
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
        return self._present_figure(
            figure,
            start_time_s=float(context.coverage[0]),
            display_time_unit=context.time_unit,
        )

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh distance histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("geocentric-distance view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        self._begin_store_context_update(context)

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
        style_axes(*self._figure.axes)
        self._request_store_view_redraw()



    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if self._store_context is None:
            raise RuntimeError("geocentric-distance view was not built from a store")
        self._apply_store_context(
            self._store_context_for_range(bounds, coverage),
            rescale_y=False,
        )

    def update(self, time_s: float) -> None:
        """Move each cursor line to an absolute OEM time."""
        super().update(time_s)

    def close(self) -> None:
        """Release the figure and cursor artists."""
        self._close_time_series_wx()
        self._close_store_series_plot()
        self._store_query = None
        self._store_artists = ((), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None


__all__ = ["GeocentricDistanceView"]
