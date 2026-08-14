"""Tests for cubic spline interpolation."""

from __future__ import annotations

import numpy as np
import pytest

import core.interpolator.cubic_spline as cubic_spline


def test_cubic_spline_interpolates_linear_data() -> None:
    """A natural cubic spline should reproduce linear data exactly."""
    interpolator = cubic_spline.CubicSplineInterpolator(dimension=2)

    xs = np.array([0.0, 1.0, 2.0, 3.0], dtype=float)
    ys = np.column_stack([xs, 2.0 * xs])

    for x_value, y_value in zip(xs, ys):
        interpolator.add_data_point(float(x_value), np.asarray(y_value, dtype=float))

    estimated = interpolator.interpolate(1.5)
    assert estimated is not None
    assert estimated == pytest.approx(np.array([1.5, 3.0], dtype=float))


def test_cubic_spline_interpolates_quadratic_data() -> None:
    """A natural cubic spline should closely match quadratic data on the grid."""
    interpolator = cubic_spline.CubicSplineInterpolator(dimension=1)

    xs = np.linspace(0.0, 4.0, 9)
    ys = xs**2

    for x_value, y_value in zip(xs, ys):
        interpolator.add_data_point(
            float(x_value), np.array([float(y_value)], dtype=float)
        )

    estimated = interpolator.interpolate(2.5)
    assert estimated is not None
    assert estimated[0] == pytest.approx(6.25, rel=1e-8, abs=1e-8)

    assert interpolator.interpolate(-1.0) is None
    assert interpolator.interpolate(5.0) is None
