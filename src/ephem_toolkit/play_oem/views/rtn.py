"""RTN position-delta playback view."""

from __future__ import annotations

import wx
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text

from ..matplotlib_helpers import create_figure, style_axes
from ..oem_data_store import ColumnGroupView, StoreQuery
from ..time_range import ResolvedTimeRange
from .data_view_base import (
    StoreViewContext,
    set_store_series_y_limits,
    store_empty_label,
)
from .orbit_time_series import OrbitTimeSeriesView
from .plotting import (
    StoreArtistBinding,
    set_shared_x_limits,
    time_bounds_to_axis,
)

CURSOR_LINE_COLOR: str = "tab:red"
"""Color used for the playback cursor lines."""
FIGURE_SIZE_INCHES: tuple[float, float] = (8.0, 7.5)
"""Default RTN-delta figure size in inches."""


class RtnDeltaView(OrbitTimeSeriesView):
    """Plot sample-to-sample radial, transverse, and normal position deltas."""

    name: str = "rtn"
    label: str = "RTN Deltas"
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
        """Create an RTN-delta view anchored at an OEM start time."""
        super().__init__(start_time_s, panel=panel, on_seek=on_seek)
        self._object_name = object_name
        self._store_query: StoreQuery[tuple[ColumnGroupView, ...]] | None = None
        self._store_artists: tuple[tuple[Artist, ...], ...] = ((), (), ())
        self._store_artist_bindings = tuple(
            StoreArtistBinding() for _ in range(3)
        )
        self._store_empty_artists: tuple[Text, ...] | None = None

    def build_from_store(self, context: StoreViewContext) -> Figure | wx.Window:
        """Build from range-limited RTN columns owned by the data store."""
        if self._figure is not None:
            raise RuntimeError("RTN-delta view has already been built")
        figure = create_figure(FIGURE_SIZE_INCHES, constrained_layout=False)
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
        return self._present_figure(
            figure,
            start_time_s=float(context.coverage[0]),
            display_time_unit=context.time_unit,
        )

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh the RTN histories from a newer store snapshot or range."""
        if self._store_context is None:
            raise RuntimeError("RTN-delta view was not built from a store")
        self._apply_store_context(context)

    def _apply_store_context(
        self, context: StoreViewContext, *, rescale_y: bool = True
    ) -> None:
        self._begin_store_context_update(
            context, axis_indexes=(len(self._figure.axes) - 1,)
        )

        query = context.series("rtn")
        self._store_query = query
        groups = query.value
        columns = ("delta_r_m", "delta_t_m", "delta_n_m")
        artists_by_axis: list[tuple[Artist, ...]] = []
        for axes, column in zip(self._figure.axes, columns):
            binding = self._store_artist_bindings[len(artists_by_axis)]
            artists = binding.sync_store_series(
                axes,
                groups,
                column,
                time_origin_s=self._store_start_time_s,
                time_divisor_s=self._time_unit_divisor_s,
                scale_y=0.001,
                edgecolor="C0",
                label=self._object_name,
                linewidth=2,
            )
            artists_by_axis.append(artists)
            if artists:
                axes.legend(loc="upper right")
                if rescale_y:
                    set_store_series_y_limits(axes, groups, (column,), scale_y=0.001)
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
        self._request_store_view_redraw()



    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if self._store_context is None:
            raise RuntimeError("RTN-delta view was not built from a store")
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
        self._store_artists = ((), (), ())
        self._store_empty_artists = None
        self._figure = None
        self._cursor_artists = None


__all__ = ["RtnDeltaView"]
