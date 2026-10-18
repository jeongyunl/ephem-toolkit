"""Plot helpers that preserve OEM segment boundaries."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D


def plot_segments(
    axes: Axes,
    x: np.ndarray,
    y: np.ndarray,
    segment_ids: Sequence[int],
    **kwargs: object,
) -> list[Line2D]:
    """Plot contiguous segment runs separately, omitting invalid boundary samples."""
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
        artists.extend(axes.plot(x[start:stop], y[start:stop], **kwargs))
        start = stop
    return artists
