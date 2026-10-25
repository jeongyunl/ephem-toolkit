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


def _reference_decimate_indices(values: np.ndarray, maximum: int) -> np.ndarray:
    """Per-bucket loop reference: first argmin and argmax for every column."""
    if len(values) <= maximum:
        return np.arange(len(values))
    bucket_count = max(1, (maximum - 2) // (2 * values.shape[1]))
    edges = np.linspace(0, len(values), bucket_count + 1, dtype=int)
    selected = [0]
    for left, right in zip(edges[:-1], edges[1:]):
        for column in range(values.shape[1]):
            local = values[left:right, column]
            selected.extend(
                (left + int(np.argmin(local)), left + int(np.argmax(local)))
            )
    selected.append(len(values) - 1)
    return np.unique(selected)


def test_decimation_matches_reference_for_ties_nans_and_columns() -> None:
    rng = np.random.default_rng(20251025)
    for trial in range(200):
        length = int(rng.integers(5, 4000))
        columns = int(rng.integers(1, 4))
        maximum = int(rng.integers(4, 2000))
        if trial % 3 == 0:
            values = rng.integers(0, 3, size=(length, columns)).astype(float)
        else:
            values = rng.standard_normal((length, columns))
            values[rng.random((length, columns)) < 0.05] = np.nan
        np.testing.assert_array_equal(
            decimate_indices(values, maximum),
            _reference_decimate_indices(values, maximum),
        )


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
