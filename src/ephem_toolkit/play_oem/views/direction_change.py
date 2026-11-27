"""Direction-change playback view."""

from __future__ import annotations

from math import pi

import wx
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .. import time_unit
from ..matplotlib_helpers import create_figure, style_axes
from ..oem_data_store import ColumnGroupView, StoreQuery
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
"""Default direction-change figure size in inches."""


class DirectionChangeView(OrbitTimeSeriesView):
    """Plot Euler-style direction angles and their rates."""

    name: str = "direction-change"
    label: str = "Direction Change"
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
        """Create a direction-change view anchored at an OEM start time."""
        super().__init__(start_time_s, panel=panel, on_seek=on_seek)
        self._object_name = object_name
        self._store_query: StoreQuery[tuple[ColumnGroupView, ...]] | None = None
        self._store_artists: tuple[tuple[Artist, ...], tuple[Artist, ...]] = (
            (),
            (),
        )
        self._store_empty_artists: tuple[Text, Text] | None = None

    def build_from_store(self, context: StoreViewContext) -> Figure | wx.Window:
        """Build from range-limited direction-rate columns owned by the store."""
        if self._figure is not None:
            raise RuntimeError("direction-change view has already been built")
        figure = create_figure(FIGURE_SIZE_INCHES)
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
        return self._present_figure(
            figure,
            start_time_s=float(context.coverage[0]),
            display_time_unit=context.time_unit,
        )

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh direction histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("direction-change view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        self._begin_store_context_update(context)

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
        style_axes(*self._figure.axes)



    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if self._store_context is None:
            raise RuntimeError("direction-change view was not built from a store")
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


__all__ = ["DirectionChangeView"]
