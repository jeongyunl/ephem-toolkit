"""Tests for core/interpolator/chebyshev.py — Chebyshev interpolation."""

from __future__ import annotations

import random

import numpy as np
import pytest

import core.interpolator.chebyshev as chebyshev


def test_chebyshev_interpolator_interpolates_linear_data() -> None:
    """Test that Chebyshev interpolator correctly interpolates linear data."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=2, degree=7
    )
    for x in range(10):
        interpolator.add_data_point(
            float(x), np.array([float(x), float(x)], dtype=float)
        )

    estimated: np.ndarray | None = interpolator.interpolate(4.5)
    assert estimated == pytest.approx([4.5, 4.5])


def test_chebyshev_interpolator_adjusts_degree_for_short_data() -> None:
    """Test interpolation when fewer samples than the requested degree exist."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=2, degree=7
    )
    for x in range(5):
        interpolator.add_data_point(
            float(x), np.array([float(x), float(2 * x)], dtype=float)
        )

    estimated: np.ndarray | None = interpolator.interpolate(2.5)
    assert estimated == pytest.approx([2.5, 5.0])


def test_chebyshev_interpolator_respects_independent_variable_range() -> None:
    """Test that Chebyshev interpolation respects data range bounds."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=5
    )
    for x in range(6):
        interpolator.add_data_point(float(x), np.array([float(x)], dtype=float))

    start_time: float = 0.0
    end_time: float = 5.0

    assert interpolator.interpolate(start_time - 0.1) is None
    assert interpolator.interpolate(start_time) == pytest.approx([0.0])
    assert interpolator.interpolate(2.5) == pytest.approx([2.5])
    assert interpolator.interpolate(end_time) == pytest.approx([5.0])
    assert interpolator.interpolate(end_time + 0.1) is None


def test_chebyshev_interpolator_uses_local_window_for_accuracy() -> None:
    """Chebyshev interpolation should behave like a local polynomial fit."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=5
    )

    x_values = np.linspace(0.0, 10.0, 41)
    y_values = np.sin(x_values)
    for x_value, y_value in zip(x_values, y_values):
        interpolator.add_data_point(float(x_value), np.array([float(y_value)]))

    estimated = interpolator.interpolate(0.35)
    assert estimated is not None
    assert estimated[0] == pytest.approx(np.sin(0.35), abs=1e-5)


def test_chebyshev_interpolator_boundary_accuracy_matches_interior() -> None:
    """Boundary windows should be widened so their accuracy stays comparable to interior windows."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=5
    )

    x_values = np.linspace(0.0, 10.0, 41)
    y_values = np.sin(x_values)
    for x_value, y_value in zip(x_values, y_values):
        interpolator.add_data_point(float(x_value), np.array([float(y_value)]))

    # Without the boundary window widening, a plain one-sided degree-5 fit at
    # the very start of the data has an error on the order of 1e-3 for this
    # function; the widened window should keep it much tighter.
    near_start_estimate = interpolator.interpolate(0.35)
    near_end_estimate = interpolator.interpolate(9.65)

    assert near_start_estimate is not None
    assert near_end_estimate is not None
    assert near_start_estimate[0] == pytest.approx(np.sin(0.35), abs=1e-6)
    assert near_end_estimate[0] == pytest.approx(np.sin(9.65), abs=1e-6)


def test_chebyshev_select_window_widens_at_boundary() -> None:
    """The boundary window should use extra available points, not just degree + 1."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=5
    )
    independent_values = np.arange(41, dtype=float)

    start, end, effective_degree = interpolator._select_window(
        independent_values, 0.5, degree=5
    )
    assert start == 0
    assert effective_degree == 5 + chebyshev.BOUNDARY_DEGREE_BOOST
    assert end == effective_degree

    start, end, effective_degree = interpolator._select_window(
        independent_values, 39.5, degree=5
    )
    assert end == 40
    assert effective_degree == 5 + chebyshev.BOUNDARY_DEGREE_BOOST
    assert start == 40 - effective_degree


def test_chebyshev_select_window_stays_minimal_in_interior() -> None:
    """Interior windows should use exactly degree + 1 points (no widening)."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=5
    )
    independent_values = np.arange(41, dtype=float)

    start, end, effective_degree = interpolator._select_window(
        independent_values, 20.0, degree=5
    )
    assert effective_degree == 5
    assert end - start == 5


def test_chebyshev_interpolator_degree_zero_returns_nearest_point() -> None:
    """A degenerate degree-0 fit should return the nearest stored sample."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=1
    )
    interpolator.add_data_point(0.0, np.array([10.0]))
    interpolator.add_data_point(1.0, np.array([20.0]))
    interpolator.degree = 0

    estimated = interpolator.interpolate(0.9)
    assert estimated is not None
    assert estimated[0] == pytest.approx(20.0)


def test_chebyshev_interpolator_deterministic_under_shuffled_queries() -> None:
    """Repeated interpolation at the same points should be independent of query order."""
    interpolator: chebyshev.ChebyshevInterpolator = chebyshev.ChebyshevInterpolator(
        dimension=1, degree=5
    )

    x_values = np.linspace(0.0, 10.0, 41)
    y_values = np.sin(x_values)
    for x_value, y_value in zip(x_values, y_values):
        interpolator.add_data_point(float(x_value), np.array([float(y_value)]))

    query_values = np.linspace(0.1, 9.9, 50)
    reference_results = {q: interpolator.interpolate(q) for q in query_values}

    shuffled_queries = list(query_values)
    random.shuffle(shuffled_queries)
    for q in shuffled_queries:
        np.testing.assert_allclose(
            interpolator.interpolate(q), reference_results[q], rtol=1e-12, atol=1e-12
        )
