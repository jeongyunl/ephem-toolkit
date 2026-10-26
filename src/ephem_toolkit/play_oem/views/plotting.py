"""Plot helpers that preserve OEM segment boundaries."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

from ..time_range import ResolvedTimeRange

MAX_DISPLAY_POINTS_PER_SEGMENT = 2000
MAX_MATPLOTLIB_3D_DISPLAY_POINTS = 500


class SegmentedPlotHistory:
    """Full-resolution samples with persistent, range-filtered line artists."""

    def __init__(
        self,
        axes: Axes,
        x: np.ndarray,
        y: np.ndarray,
        segment_ids: Sequence[int] | np.ndarray,
        *,
        max_display_points: int = MAX_DISPLAY_POINTS_PER_SEGMENT,
        empty_label: str = "No samples in plot range",
        **kwargs: object,
    ) -> None:
        if max_display_points < 4:
            raise ValueError("max_display_points must be at least four")
        self.axes = axes
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        self.segment_ids = np.asarray(segment_ids, dtype=int)
        if self.x.ndim != 1 or self.y.shape[0] != self.x.shape[0]:
            raise ValueError("x and y must have matching first dimensions")
        if self.segment_ids.shape != self.x.shape:
            raise ValueError("segment_ids must match x")
        if np.any(np.diff(self.x) < 0.0):
            raise ValueError("x must be ordered")
        self.max_display_points = max_display_points
        self.empty_label = empty_label
        self._runs: list[tuple[int, int, Line2D]] = []
        self._last_update_key: tuple[tuple[float, float] | None, bool] | None = None
        self._last_selected_any = False
        self._empty_text = axes.text(
            0.5, 0.5, empty_label, ha="center", va="center", transform=axes.transAxes
        )
        self._empty_text.set_visible(False)
        self._empty_range_text = axes.text(
            0.5,
            0.5,
            "Plot range does not overlap OEM coverage",
            ha="center",
            va="center",
            transform=axes.transAxes,
        )
        self._empty_range_text.set_visible(False)

        start = 0
        while start < len(self.segment_ids):
            segment_id = self.segment_ids[start]
            if segment_id < 0:
                start += 1
                continue
            stop = start + 1
            while stop < len(self.segment_ids) and self.segment_ids[stop] == segment_id:
                stop += 1
            (line,) = axes.plot([], [], **kwargs)
            self._runs.append((start, stop, line))
            start = stop
        self._full_y_limits = axes.get_ylim()
        if len(self.x):
            self.update((float(self.x[0]), float(self.x[-1])))
        else:
            self.update(None, empty_range=True)
        if self._runs:
            axes.relim()
            axes.autoscale_view(scalex=False, scaley=True)
            self._full_y_limits = axes.get_ylim()

    @property
    def artists(self) -> tuple[Line2D, ...]:
        return tuple(line for _, _, line in self._runs)

    def update(
        self,
        bounds: tuple[float, float] | None,
        *,
        empty_range: bool = False,
    ) -> bool:
        """Select samples inclusively, then decimate each valid segment run.

        Returns true when at least one source sample is selected. Passing None
        clears every data artist and shows the empty-intersection label.
        """
        # Sample arrays never change after construction, so the same bounds
        # always produce the same artists; skip the decimation work.
        update_key = (
            None if bounds is None else (float(bounds[0]), float(bounds[1])),
            empty_range,
        )
        if update_key == self._last_update_key:
            return self._last_selected_any
        if bounds is None:
            lower_index = upper_index = 0
        else:
            lower_index = int(np.searchsorted(self.x, bounds[0], side="left"))
            upper_index = int(np.searchsorted(self.x, bounds[1], side="right"))
        selected_any = False
        for run_start, run_stop, line in self._runs:
            start = max(run_start, lower_index)
            stop = min(run_stop, upper_index)
            if start >= stop:
                line.set_data([], [])
                line.set_marker("None")
                continue
            run_x = self.x[start:stop]
            run_y = self.y[start:stop]
            if len(run_x) > self.max_display_points:
                values = run_y.reshape((len(run_y), -1))
                indices = decimate_indices(values, self.max_display_points)
                run_x = run_x[indices]
                run_y = run_y[indices]
            line.set_data(run_x, run_y)
            line.set_marker("." if len(run_x) == 1 else "None")
            selected_any = True
        self._empty_text.set_visible(not selected_any and not empty_range)
        self._empty_range_text.set_visible(empty_range)
        self._last_update_key = update_key
        self._last_selected_any = selected_any
        return selected_any


def time_bounds_to_axis(
    bounds: ResolvedTimeRange | None,
    coverage: tuple[float, float],
    start_time_s: float,
    divisor_s: float,
) -> tuple[float, float]:
    """Convert absolute bounds to elapsed display units, using coverage if empty."""
    source = (
        (coverage[0], coverage[1]) if bounds is None else (bounds.start_s, bounds.end_s)
    )
    return (
        (source[0] - start_time_s) / divisor_s,
        (source[1] - start_time_s) / divisor_s,
    )


def set_shared_x_limits(axes: Sequence[Axes], limits: tuple[float, float]) -> None:
    """Set common x limits, widening singleton ranges only for visible rendering."""
    left, right = limits
    if left == right:
        left -= 0.5
        right += 0.5
    for axis in axes:
        axis.set_xlim(left, right, auto=False)


def decimate_indices(
    values: np.ndarray, maximum: int = MAX_DISPLAY_POINTS_PER_SEGMENT
) -> np.ndarray:
    """Select ordered bucket extrema from an N-by-M display-only value array."""
    if values.ndim != 2:
        raise ValueError("values must be a two-dimensional array")
    if maximum < 4:
        raise ValueError("maximum must be at least four")
    if len(values) <= maximum:
        return np.arange(len(values))
    bucket_count = max(1, (maximum - 2) // (2 * values.shape[1]))
    edges = np.linspace(0, len(values), bucket_count + 1, dtype=int)
    # Every bucket is non-empty because bucket_count is below len(values) here.
    starts = edges[:-1]
    bucket_of_row = np.repeat(np.arange(bucket_count), np.diff(edges))
    row_indices = np.arange(len(values))
    extrema: list[np.ndarray] = []
    for column in range(values.shape[1]):
        local = np.ascontiguousarray(values[:, column])
        for ufunc in (np.minimum, np.maximum):
            bucket_extreme = ufunc.reduceat(local, starts)
            # NaN never compares equal, so match NaN rows explicitly to pick the
            # first NaN as np.argmin and np.argmax do.
            at_extreme = (local == bucket_extreme[bucket_of_row]) | (
                np.isnan(local) & np.isnan(bucket_extreme)[bucket_of_row]
            )
            first_index = np.where(at_extreme, row_indices, len(values))
            extrema.append(np.minimum.reduceat(first_index, starts))
    selected = np.concatenate([[0], *extrema, [len(values) - 1]])
    return np.unique(selected)


def plot_segments(
    axes: Axes,
    x: np.ndarray,
    y: np.ndarray,
    segment_ids: Sequence[int] | np.ndarray,
    *,
    max_display_points: int = MAX_DISPLAY_POINTS_PER_SEGMENT,
    **kwargs: object,
) -> list[Line2D]:
    """Plot contiguous segment runs separately, omitting invalid boundary samples."""
    if max_display_points < 4:
        raise ValueError("max_display_points must be at least four")
    ids = np.asarray(segment_ids, dtype=int)
    if x.shape[0] != y.shape[0] or ids.shape != x.shape:
        raise ValueError("x, y, and segment_ids must have matching first dimensions")
    artists: list[Line2D] = []
    start = 0
    while start < len(ids):
        if ids[start] < 0:
            start += 1
            continue
        stop = start + 1
        while stop < len(ids) and ids[stop] == ids[start]:
            stop += 1
        run_x = x[start:stop]
        run_y = y[start:stop]
        if len(run_x) > max_display_points:
            bucket_count = max(1, (max_display_points - 2) // 2)
            edges = np.linspace(0, len(run_x), bucket_count + 1, dtype=int)
            selected: list[int] = [0]
            for left, right in zip(edges[:-1], edges[1:]):
                if right <= left:
                    continue
                local = run_y[left:right]
                selected.extend(
                    (left + int(np.argmin(local)), left + int(np.argmax(local)))
                )
            selected.append(len(run_x) - 1)
            indices = np.unique(selected)
            run_x = run_x[indices]
            run_y = run_y[indices]
        artists.extend(axes.plot(run_x, run_y, **kwargs))
        start = stop
    return artists
