"""Tests for display-only plot optimizations."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from ephem_toolkit.play_oem.views.plotting import (
    MAX_DISPLAY_POINTS_PER_SEGMENT,
    decimate_indices,
    plot_segments,
)


def test_decimation_caps_display_points_and_preserves_bucket_extrema() -> None:
    values = np.column_stack(
        (
            np.sin(np.linspace(0.0, 100.0, 100_000)),
            np.cos(np.linspace(0.0, 100.0, 100_000)),
            np.zeros(100_000),
        )
    )
    indices = decimate_indices(values)

    assert len(indices) <= MAX_DISPLAY_POINTS_PER_SEGMENT
    assert indices[0] == 0
    assert indices[-1] == len(values) - 1
    assert np.max(values[indices, 0]) == np.max(values[:, 0])
    assert np.min(values[indices, 1]) == np.min(values[:, 1])


def test_plot_segments_keeps_gap_and_decimates_only_display_arrays() -> None:
    x = np.arange(10_000, dtype=float)
    y = np.sin(x / 100.0)
    segment_ids = np.r_[np.zeros(5_000), np.ones(5_000)].astype(int)
    figure = Figure()
    axes = figure.subplots()

    lines = plot_segments(axes, x, y, segment_ids)

    assert len(lines) == 2
    assert all(
        len(line.get_xdata()) <= MAX_DISPLAY_POINTS_PER_SEGMENT for line in lines
    )
    assert lines[0].get_xdata()[-1] == 4_999
    assert lines[1].get_xdata()[0] == 5_000
    assert len(x) == len(y) == len(segment_ids) == 10_000


def test_plot_segments_accepts_a_tighter_display_cap_and_preserves_extrema() -> None:
    x = np.arange(5_000, dtype=float)
    y = np.sin(x / 100.0)
    figure = Figure()
    axes = figure.subplots()

    (line,) = plot_segments(
        axes,
        x,
        y,
        np.zeros(len(x), dtype=int),
        max_display_points=500,
    )

    assert len(line.get_xdata()) <= 500
    assert line.get_xdata()[0] == x[0]
    assert line.get_xdata()[-1] == x[-1]
    assert np.min(line.get_ydata()) == np.min(y)
    assert np.max(line.get_ydata()) == np.max(y)
