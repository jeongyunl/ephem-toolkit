"""Plot helpers that preserve OEM segment boundaries."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

from ..time_range import ResolvedTimeRange

MAX_DISPLAY_POINTS_PER_SEGMENT = 2000
MAX_MATPLOTLIB_3D_DISPLAY_POINTS = 500




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


def bounded_sample_indices(
    sample_count: int,
    maximum: int = MAX_DISPLAY_POINTS_PER_SEGMENT,
) -> np.ndarray:
    """Choose evenly spaced rows with an allocation bounded by ``maximum``."""
    if sample_count < 0:
        raise ValueError("sample_count must be non-negative")
    if maximum < 1:
        raise ValueError("maximum must be positive")
    display_count = min(sample_count, maximum)
    if display_count == sample_count:
        return np.arange(display_count)
    return np.linspace(
        0, sample_count - 1, num=display_count, dtype=np.intp
    )


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
