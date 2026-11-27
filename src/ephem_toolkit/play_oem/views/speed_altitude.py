"""Speed and altitude time-series playback view."""

from __future__ import annotations

import numpy as np
import wx
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.text import Text
from matplotlib.transforms import Affine2D

from .. import time_unit
from ..matplotlib_helpers import create_figure, style_axes
from ..oem_data_store import ColumnGroupView, StoreQuery
from ..time_range import ResolvedTimeRange
from .data_view_base import (
    StoreViewContext,
)
from .orbit_time_series import OrbitTimeSeriesView
from .plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    set_shared_x_limits,
    time_bounds_to_axis,
)

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 6.0)
"""Default speed/altitude figure size in inches."""


class SpeedAltitudeView(OrbitTimeSeriesView):
    """Plot speed and altitude histories with a shared time cursor."""

    name: str = "speed-altitude"
    label: str = "Speed / Altitude"
    group: str = "overview"

    @property
    def cursor_artists(self) -> tuple[Line2D, ...]:
        return self._cursor_artists or ()

    def __init__(
        self,
        start_time_s: float,
        *,
        panel: wx.Window | None = None,
        on_seek: object = None,
    ) -> None:
        """Create a speed/altitude view anchored at an OEM start time.

        Parameters
        ----------
        start_time_s : float
            Absolute OEM start time in TT seconds since J2000.
        """
        super().__init__(start_time_s, panel=panel, on_seek=on_seek)
        self._store_query: StoreQuery[tuple[ColumnGroupView, ...]] | None = None
        self._store_patches: tuple[
            tuple[PathPatch | Line2D, ...], tuple[PathPatch | Line2D, ...]
        ] = ((), ())
        self._store_empty_artists: tuple[Text, Text] | None = None


    def build_from_store(self, context: StoreViewContext) -> Figure | wx.Window:
        """Build from a range-limited store query."""
        if self._figure is not None:
            raise RuntimeError("speed/altitude view has already been built")
        figure, speed_axes, altitude_axes = self._create_figure(context.time_unit)
        self._cursor_artists = self._make_cursor_artists(speed_axes, altitude_axes)
        self._store_empty_artists = (
            speed_axes.text(
                0.5,
                0.5,
                "No samples in plot range",
                ha="center",
                va="center",
                transform=speed_axes.transAxes,
            ),
            altitude_axes.text(
                0.5,
                0.5,
                "No samples in plot range",
                ha="center",
                va="center",
                transform=altitude_axes.transAxes,
            ),
        )
        self._apply_store_context(context, rescale_y=True)
        return self._present_figure(
            figure,
            start_time_s=float(context.coverage[0]),
            display_time_unit=context.time_unit,
        )

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh from a newer snapshot while retaining the current figure."""
        if self._store_context is None:
            raise RuntimeError("speed/altitude view was not built from a store")
        self._apply_store_context(context, rescale_y=True)

    def _create_figure(
        self, display_time_unit: time_unit.TimeUnit
    ) -> tuple[Figure, Axes, Axes]:
        figure = create_figure(FIGURE_SIZE_INCHES)
        speed_axes, altitude_axes = figure.subplots(2, 1, sharex=True)
        speed_axes.set_ylabel("Speed (km/s)")
        altitude_axes.set_ylabel("Altitude (km)")
        altitude_axes.set_xlabel(display_time_unit.get_axis_label())
        speed_axes.grid(True)
        altitude_axes.grid(True)
        style_axes(speed_axes, altitude_axes)
        self._figure = figure
        self._time_unit_divisor_s = display_time_unit.get_divisor_s()
        return figure, speed_axes, altitude_axes

    def _make_cursor_artists(
        self, speed_axes: Axes, altitude_axes: Axes
    ) -> tuple[Line2D, Line2D]:
        return (
            speed_axes.axvline(
                0.0,
                color=CURSOR_LINE_COLOR,
                linestyle="--",
                label="_child0",
            ),
            altitude_axes.axvline(
                0.0,
                color=CURSOR_LINE_COLOR,
                linestyle="--",
                label="_child0",
            ),
        )

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool
    ) -> None:
        self._begin_store_context_update(context, axis_indexes=(1,))
        self._remove_store_patches()

        query = context.series("kinematics", max_samples=MAX_DISPLAY_POINTS_PER_SEGMENT)
        self._store_query = query
        groups = query.value
        speed_patches, altitude_patches = self._add_store_patches(
            groups, self._figure.axes[0], self._figure.axes[1], context
        )
        self._store_patches = (speed_patches, altitude_patches)
        has_samples = bool(speed_patches or altitude_patches)
        if self._store_empty_artists is not None:
            for empty_artist in self._store_empty_artists:
                empty_artist.set_visible(not has_samples)

        limits = time_bounds_to_axis(
            context.plot_range,
            context.coverage,
            self._store_start_time_s,
            self._time_unit_divisor_s,
        )
        set_shared_x_limits(tuple(self._figure.axes), limits)
        if rescale_y and query is not None:
            self._rescale_store_axes(groups)

    def _add_store_patches(
        self,
        groups: tuple[ColumnGroupView, ...],
        speed_axes: Axes,
        altitude_axes: Axes,
        context: StoreViewContext,
    ) -> tuple[tuple[PathPatch | Line2D, ...], tuple[PathPatch | Line2D, ...]]:
        speed_artists: list[PathPatch | Line2D] = []
        altitude_artists: list[PathPatch | Line2D] = []
        for group in groups:
            for span in group.segment_bounds:
                rows = slice(span.first, span.stop)
                speed = group.pair("t", "speed_m_s", rows)
                altitude = group.pair("t", "altitude_m", rows)
                if speed.shape[0] == 0:
                    continue
                speed_artists.append(
                    self._add_store_path(speed_axes, speed, context, scale_y=0.001)
                )
                altitude_artists.append(
                    self._add_store_path(
                        altitude_axes, altitude, context, scale_y=0.001
                    )
                )
        return tuple(speed_artists), tuple(altitude_artists)

    def _add_store_path(
        self,
        axes: Axes,
        values: np.ndarray,
        context: StoreViewContext,
        *,
        scale_y: float,
    ) -> PathPatch | Line2D:
        transform = (
            Affine2D.from_values(
                1.0 / context.time_unit.get_divisor_s(),
                0.0,
                0.0,
                scale_y,
                -self._store_start_time_s / context.time_unit.get_divisor_s(),
                0.0,
            )
            + axes.transData
        )
        if values.shape[0] == 1:
            artist = Line2D(
                values[:, 0],
                values[:, 1],
                marker=".",
                linestyle="None",
                color="C0",
            )
            artist.set_transform(transform)
            axes.add_line(artist)
            return artist
        patch = PathPatch(Path(values, readonly=True), fill=False, color="C0")
        patch.set_transform(transform)
        axes.add_patch(patch)
        return patch

    def _remove_store_patches(self) -> None:
        for artists in self._store_patches:
            for artist in artists:
                artist.remove()
        self._store_patches = ((), ())
        self._store_query = None

    def _rescale_store_axes(self, groups: tuple[ColumnGroupView, ...]) -> None:
        if not groups or self._figure is None:
            return
        for axis_index, column in enumerate(("speed_m_s", "altitude_m")):
            column_index = groups[0].columns.index(column)
            lower = min(
                float(np.min(group.values[:, column_index])) for group in groups
            )
            upper = max(
                float(np.max(group.values[:, column_index])) for group in groups
            )
            lower *= 0.001
            upper *= 0.001
            padding = max((upper - lower) * 0.05, abs(upper) * 0.005, 0.001)
            self._figure.axes[axis_index].set_ylim(lower - padding, upper + padding)

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if self._store_context is None:
            raise RuntimeError("speed/altitude view was not built from a store")
        self._apply_store_context(
            self._store_context_for_range(bounds, coverage),
            rescale_y=False,
        )


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
        super().update(time_s)

    def close(self) -> None:
        """Release the figure and cursor artists."""
        self._close_time_series_wx()
        self._close_store_series_plot()
        self._store_query = None
        self._store_patches = ((), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None


__all__ = ["SpeedAltitudeView"]
