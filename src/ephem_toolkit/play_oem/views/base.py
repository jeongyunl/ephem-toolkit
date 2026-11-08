"""Toolkit-neutral interface for playback plot views."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Any, Protocol, cast

from matplotlib.axes import Axes
from matplotlib.artist import Artist
from matplotlib.lines import Line2D

from matplotlib.figure import Figure
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D
import numpy as np

from ..oem_data_store import (
    ColumnGroupView,
    OemDataStore,
    SeriesGroupName,
    SeriesGroups,
    StoreQuery,
    StoreSnapshot,
    TierName,
)
from ..series import OrbitSeries
from ..time_range import ResolvedTimeRange, validate_coverage
from ..time_unit import TimeUnit
from .plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    SegmentedPlotHistory,
    set_shared_x_limits,
    time_bounds_to_axis,
)

if TYPE_CHECKING:
    import wx


class View(Protocol):
    """Lifecycle shared by all playback views."""

    name: str

    def build(self, series: OrbitSeries, time_unit: TimeUnit, /) -> Figure | wx.Window:
        """Build the view content and its initial cursor state."""
        ...

    def update(self, t_s: float, /) -> None:
        """Move the view's cursor to an absolute OEM time."""
        ...

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        """Select displayed samples; None clears data for an empty effective range."""
        ...

    def close(self) -> None:
        """Release the view's plot resources."""
        ...


@dataclass(frozen=True)
class StoreViewContext:
    """Typed store input for a view's range-limited queries."""

    store: OemDataStore
    snapshot: StoreSnapshot
    time_unit: TimeUnit
    plot_range: ResolvedTimeRange | None
    coverage: tuple[float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.store, OemDataStore):
            raise TypeError("store must be an OemDataStore")
        if not isinstance(self.snapshot, StoreSnapshot):
            raise TypeError("snapshot must be a StoreSnapshot")
        if not isinstance(self.time_unit, TimeUnit):
            raise TypeError("time_unit must be a TimeUnit")
        object.__setattr__(self, "coverage", validate_coverage(self.coverage))

    def query_series(
        self,
        groups: Sequence[SeriesGroupName],
        *,
        max_samples: int | None = None,
    ) -> StoreQuery[SeriesGroups] | None:
        """Query only selected groups over the effective plot range."""
        if self.plot_range is None:
            return None
        return self.store.series(
            self.snapshot,
            (self.plot_range.start_s, self.plot_range.end_s),
            groups=groups,
            max_samples=max_samples,
        )

    def subscribe_tier(self, tier: TierName) -> Callable[[], None]:
        """Register this open view's interest in a derived store tier."""
        return self.store.subscribe_tier(tier)


class StoreView(Protocol):
    """Store-query view lifecycle used by the unified player."""

    name: str

    def build_from_store(self, context: StoreViewContext, /) -> Figure | wx.Window:
        """Build from a stable store snapshot and its range-limited queries."""
        ...

    def update_from_store(self, context: StoreViewContext, /) -> None:
        """Refresh from a newer snapshot or changed plot range."""
        ...


def add_store_series_paths(
    axes: Axes,
    groups: Sequence[ColumnGroupView],
    value_column: str,
    time_origin_s: float,
    time_divisor_s: float,
    *,
    scale_y: float = 1.0,
    color: str = "C0",
    label: str | None = None,
    linewidth: float = 1.5,
    mask_zero: bool = False,
    minimum_samples: int = 1,
) -> tuple[Artist, ...]:
    """Plot strided store views without copying their coordinate values."""
    artists: list[Artist] = []
    current_label = label
    for group in groups:
        for span in group.segment_bounds:
            sample_count = span.stop - span.first
            if sample_count < minimum_samples:
                continue
            stride = max(1, ceil(sample_count / MAX_DISPLAY_POINTS_PER_SEGMENT))
            points = group.pair(
                "t",
                value_column,
                slice(span.first, span.stop, stride),
            )
            transform = Affine2D.from_values(
                1.0 / time_divisor_s,
                0.0,
                0.0,
                scale_y,
                -time_origin_s / time_divisor_s,
                0.0,
            ) + axes.transData
            if mask_zero and len(points) == 1 and points[0, 1] == 0.0:
                continue
            codes = np.full(len(points), Path.LINETO, dtype=Path.code_type)
            codes[0] = Path.MOVETO
            if mask_zero:
                invalid = points[:, 1] == 0.0
                codes[invalid] = Path.MOVETO
                codes[1:][invalid[:-1]] = Path.MOVETO
            artist = PathPatch(
                Path(points, codes, readonly=True),
                facecolor="none",
                edgecolor=color,
                linewidth=linewidth,
                label=current_label or "_nolegend_",
                transform=transform,
            )
            axes.add_patch(artist)
            artists.append(artist)
            current_label = None
    return tuple(artists)


def add_raw_state_paths(
    axes: Axes,
    snapshot: StoreSnapshot,
    value_column: int,
    time_origin_s: float,
    time_divisor_s: float,
    *,
    bounds: ResolvedTimeRange | None,
    maximum_samples_per_segment: int,
    scale_y: float,
    color: str = "C0",
    linewidth: float = 1.5,
) -> tuple[Artist, ...]:
    """Plot strided raw-state columns while keeping path vertices store-backed."""
    if not 1 <= value_column < snapshot.raw.shape[1]:
        raise ValueError("state column must be between 1 and 6")
    if maximum_samples_per_segment < 1:
        raise ValueError("maximum_samples_per_segment must be positive")
    if bounds is None or snapshot.sample_count == 0:
        return ()

    times = snapshot.raw[:, 0]
    range_start = int(np.searchsorted(times, bounds.start_s, side="left"))
    range_stop = int(np.searchsorted(times, bounds.end_s, side="right"))
    artists: list[Artist] = []
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(int(segment_start), range_start)
        stop = min(int(segment_stop), range_stop)
        sample_count = stop - first
        if sample_count <= 0:
            continue
        stride = max(1, ceil(sample_count / maximum_samples_per_segment))
        column_stride = value_column
        points = snapshot.raw[
            first:stop:stride, 0 : value_column + 1 : column_stride
        ]
        codes = np.full(len(points), Path.LINETO, dtype=Path.code_type)
        codes[0] = Path.MOVETO
        transform = Affine2D.from_values(
            1.0 / time_divisor_s,
            0.0,
            0.0,
            scale_y,
            -time_origin_s / time_divisor_s,
            0.0,
        ) + axes.transData
        artist = PathPatch(
            Path(points, codes, readonly=True),
            facecolor="none",
            edgecolor=color,
            linewidth=linewidth,
            transform=transform,
        )
        axes.add_patch(artist)
        artists.append(artist)
    return tuple(artists)


def clear_store_series_artists(axes: Axes, artists: Sequence[Artist]) -> None:
    for artist in artists:
        artist.remove()
    legend = axes.get_legend()
    if legend is not None:
        legend.remove()


def store_empty_label(
    context: StoreViewContext, *, not_enough_samples: bool = False
) -> str:
    if context.plot_range is None:
        return "Plot range does not overlap OEM coverage"
    if not_enough_samples:
        return "Not enough samples"
    return "No samples in plot range"


def set_store_series_y_limits(
    axes: Axes,
    groups: Sequence[ColumnGroupView],
    value_columns: Sequence[str],
    *,
    scale_y: float = 1.0,
) -> None:
    lower = float("inf")
    upper = float("-inf")
    for group in groups:
        for column in value_columns:
            values = group.values[:, group.columns.index(column)]
            column_lower = float(np.fmin.reduce(values, initial=np.inf))
            column_upper = float(np.fmax.reduce(values, initial=-np.inf))
            if not np.isfinite(column_lower) or not np.isfinite(column_upper):
                continue
            lower = min(lower, column_lower * scale_y)
            upper = max(upper, column_upper * scale_y)
    if lower == float("inf"):
        return
    padding = max((upper - lower) * 0.05, abs(upper) * 0.005, 0.001)
    axes.set_ylim(lower - padding, upper + padding)


def set_raw_state_y_limits(
    axes: Axes,
    snapshot: StoreSnapshot,
    value_column: int,
    *,
    scale_y: float,
) -> None:
    if snapshot.sample_count == 0:
        return
    values = snapshot.raw[:, value_column]
    lower = float(np.min(values)) * scale_y
    upper = float(np.max(values)) * scale_y
    padding = max((upper - lower) * 0.05, abs(upper) * 0.005, 0.001)
    axes.set_ylim(lower - padding, upper + padding)


class TimeRangeSupport:
    """Shared time-axis, range filtering, and cursor-visibility behavior."""

    # Views whose per-tick update changes only animated cursor artists.
    animated_cursor_updates: bool = False

    def _configure_time_range(
        self,
        axes: tuple[Axes, ...],
        histories: tuple[SegmentedPlotHistory, ...],
        cursor_artists: tuple[Line2D, ...],
        start_time_s: float,
        divisor_s: float,
    ) -> None:
        self._range_axes = axes
        self._range_histories = histories
        self._range_cursors = cursor_artists
        self._range_start_time_s = start_time_s
        self._range_divisor_s = divisor_s
        self._range_bounds: ResolvedTimeRange | None = None
        self._range_coverage = (start_time_s, start_time_s)
        self._last_cursor_time_s = start_time_s
        self._range_applied = False
        self._range_active = False
        self._range_changed = True
        self._setting_shared_xlim = False
        self._range_xlim_callbacks = [
            (
                axis,
                cast(Any, axis).callbacks.connect(
                    "xlim_changed", self._on_range_xlim_changed
                ),
            )
            for axis in axes
        ]
        self._full_y_limits = tuple(axis.get_ylim() for axis in axes)

    def _on_range_xlim_changed(self, _axis: Axes) -> None:
        if self._setting_shared_xlim or not self._range_active:
            return
        if not self._range_axes:
            return
        expected = time_bounds_to_axis(
            self._range_bounds,
            self._range_coverage,
            self._range_start_time_s,
            self._range_divisor_s,
        )
        self._setting_shared_xlim = True
        try:
            set_shared_x_limits(self._range_axes, expected)
        finally:
            self._setting_shared_xlim = False

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if not hasattr(self, "_range_axes"):
            return
        if bounds != self._range_bounds or coverage != self._range_coverage:
            self._range_changed = True
        self._range_bounds = bounds
        self._range_coverage = coverage
        self._range_applied = True
        self._range_active = bounds is None or (
            bounds.start_s > coverage[0] or bounds.end_s < coverage[1]
        )
        limits = time_bounds_to_axis(
            bounds, coverage, self._range_start_time_s, self._range_divisor_s
        )
        has_samples = False
        for history in self._range_histories:
            has_samples = (
                history.update(
                    None if bounds is None else limits,
                    empty_range=bounds is None,
                )
                or has_samples
            )
        self._setting_shared_xlim = True
        try:
            set_shared_x_limits(self._range_axes, limits)
        finally:
            self._setting_shared_xlim = False
        if bounds is None:
            for cursor in self._range_cursors:
                cursor.set_visible(False)
        else:
            self._set_cursor_visibility(self._last_cursor_time_s)
        # Keep the current vertical zoom. Home on the navigation toolbar returns
        # to its captured full-data limits; this explicit hook serves other UIs.

    def consume_cursor_only_update(self) -> bool:
        """Return whether the time range is unchanged since the previous call.

        Callers pair this with a cursor ``update``; a True result means the only
        change was to animated cursors, so a cached background can be reused.
        """
        range_changed = self._range_changed
        self._range_changed = False
        return self.animated_cursor_updates and not range_changed

    def restore_full_y_limits(self) -> None:
        """Restore build-time full-history Y bounds without changing shared X."""
        for axis, limits in zip(self._range_axes, self._full_y_limits):
            axis.set_ylim(*limits)

    def _update_history_data(
        self,
        datasets: Sequence[tuple[np.ndarray, np.ndarray, np.ndarray]],
        start_time_s: float,
        divisor_s: float,
    ) -> bool:
        """Replace time-series samples without rebuilding the figure."""
        if (
            not hasattr(self, "_range_histories")
            or start_time_s != self._range_start_time_s
            or divisor_s != self._range_divisor_s
            or len(datasets) != len(self._range_histories)
        ):
            return False
        if not all(
            history.can_replace_data(x, y, segment_ids)
            for history, (x, y, segment_ids) in zip(
                self._range_histories, datasets
            )
        ):
            return False

        y_limits = tuple(axis.get_ylim() for axis in self._range_axes)
        y_autoscale = tuple(axis.get_autoscaley_on() for axis in self._range_axes)
        for history, (x, y, segment_ids) in zip(self._range_histories, datasets):
            history.replace_data(x, y, segment_ids)
            if len(history.x):
                history.update((float(history.x[0]), float(history.x[-1])))
            else:
                history.update(None, empty_range=True)
        for axis, limits, autoscale in zip(
            self._range_axes, y_limits, y_autoscale
        ):
            axis.relim()
            if autoscale:
                axis.autoscale_view(scalex=False, scaley=True)
            else:
                axis.set_ylim(*limits)
        if any(y_autoscale):
            self._full_y_limits = tuple(axis.get_ylim() for axis in self._range_axes)
        current_limits = time_bounds_to_axis(
            self._range_bounds,
            self._range_coverage,
            self._range_start_time_s,
            self._range_divisor_s,
        )
        for history in self._range_histories:
            history.update(
                None if self._range_bounds is None else current_limits,
                empty_range=self._range_bounds is None,
            )
        self._range_changed = True
        return True

    def _close_time_range(self) -> None:
        for axis, callback_id in getattr(self, "_range_xlim_callbacks", ()):
            cast(Any, axis).callbacks.disconnect(callback_id)
        self._range_xlim_callbacks = []

    def _set_cursor_visibility(self, time_s: float) -> None:
        self._last_cursor_time_s = time_s
        if not self._range_applied:
            return
        visible = (
            self._range_bounds is not None
            and self._range_bounds.start_s <= time_s <= self._range_bounds.end_s
        )
        for cursor in self._range_cursors:
            cursor.set_visible(visible)
