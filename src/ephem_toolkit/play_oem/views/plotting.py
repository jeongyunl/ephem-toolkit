"""Plot helpers that preserve OEM segment boundaries."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

MAX_DISPLAY_POINTS_PER_SEGMENT = 2000
MAX_MATPLOTLIB_3D_DISPLAY_POINTS = 500


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
    selected: list[int] = [0]
    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue
        for column in range(values.shape[1]):
            local = values[left:right, column]
            selected.extend(
                (left + int(np.argmin(local)), left + int(np.argmax(local)))
            )
    selected.append(len(values) - 1)
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
