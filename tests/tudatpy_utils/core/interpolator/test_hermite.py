"""Tests for core/interpolator/hermite.py — Hermite interpolation."""

from __future__ import annotations

import numpy as np
import pytest

import core.interpolator.hermite as hermite


def test_hermite_interpolator_interpolates_linear_data() -> None:
    """Test that Hermite interpolator correctly interpolates linear data."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=2, points_wanted=2
    )
    for x in range(5):
        interpolator.add_data_point(
            float(x), np.array([float(x), float(2 * x)], dtype=float)
        )

    result: np.ndarray | None = interpolator.interpolate(2.5)
    assert result is not None
    assert result == pytest.approx([2.5, 5.0], abs=1e-10)


def test_hermite_interpolator_with_derivatives() -> None:
    """Test Hermite interpolation with derivative data."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    # Add all data points first
    for x in range(5):
        interpolator.add_data_point(float(x), np.array([float(x * x)], dtype=float))

    # Then add derivatives for f(x) = x^2, f'(x) = 2x
    for x in range(5):
        interpolator.add_derivative(float(x), np.array([float(2 * x)], dtype=float))

    result: np.ndarray | None = interpolator.interpolate(2.5)
    assert result is not None
    # f(2.5) = 6.25
    assert result[0] == pytest.approx(6.25, abs=1e-6)


def test_hermite_interpolator_cubic_polynomial() -> None:
    """Test Hermite interpolation on cubic polynomial."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=3
    )

    # f(x) = x^3 - 2x^2 + x + 1
    def f(x: float) -> float:
        return x**3 - 2 * x**2 + x + 1

    # f'(x) = 3x^2 - 4x + 1
    def df(x: float) -> float:
        return 3 * x**2 - 4 * x + 1

    # Add all data points first
    points = [0.0, 1.0, 2.0, 3.0]
    for x in points:
        interpolator.add_data_point(x, np.array([f(x)], dtype=float))

    # Then add derivatives
    for x in points:
        interpolator.add_derivative(x, np.array([df(x)], dtype=float))

    # Test interpolation at intermediate point
    result: np.ndarray | None = interpolator.interpolate(1.5)
    assert result is not None
    assert result[0] == pytest.approx(f(1.5), abs=1e-8)


def test_add_derivative_invalid_order() -> None:
    """Test that adding derivatives with invalid order raises ValueError."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))

    with pytest.raises(ValueError, match="Only first-order derivatives are supported"):
        interpolator.add_derivative(0.0, np.array([1.0], dtype=float), order=2)


def test_add_derivative_nonexistent_independent_value() -> None:
    """Test that adding derivative for nonexistent point raises ValueError."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))

    with pytest.raises(ValueError, match="Independent value .* not found in data"):
        interpolator.add_derivative(1.0, np.array([1.0], dtype=float))


def test_add_derivative_with_missing_indicator() -> None:
    """Test that derivatives with missing indicator are not added."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=2, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0, 2.0], dtype=float))

    # Use missing indicator for second element
    result: bool = interpolator.add_derivative(
        0.0, np.array([1.5, -1e100], dtype=float)
    )
    assert result is True


def test_clear_storage() -> None:
    """Test that clear_storage removes all data and derivatives."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))
    interpolator.add_derivative(0.0, np.array([2.0], dtype=float))

    interpolator.clear_storage()

    assert len(interpolator.independent_values) == 0
    assert len(interpolator.dependent_values) == 0
    assert len(interpolator.derivatives) == 0
    assert len(interpolator.q_coeffs) == 0
    assert len(interpolator.t_values) == 0


def test_inconsistent_derivative_data() -> None:
    """Test that inconsistent derivative data raises ValueError."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))
    interpolator.add_data_point(1.0, np.array([2.0], dtype=float))

    # Add derivative only for first point
    interpolator.add_derivative(0.0, np.array([1.5], dtype=float))

    # Should raise error due to inconsistent derivative data
    with pytest.raises(ValueError, match="Inconsistent derivative data"):
        interpolator.interpolate(0.5)


def test_interpolate_cartesian_state() -> None:
    """Test Cartesian state interpolation with position and velocity."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=6, points_wanted=2
    )

    # Simple linear motion: position = t, velocity = 1
    for t in range(5):
        position = np.array([float(t), float(t), float(t)], dtype=float)
        velocity = np.array([1.0, 1.0, 1.0], dtype=float)
        state = np.concatenate([position, velocity])
        interpolator.add_data_point(float(t), state)

    result: np.ndarray | None = interpolator.interpolate_cartesian_state(2.5)
    assert result is not None

    # Position should be [2.5, 2.5, 2.5]
    assert result[0:3] == pytest.approx([2.5, 2.5, 2.5], abs=1e-10)
    # Velocity should be [1.0, 1.0, 1.0]
    assert result[3:6] == pytest.approx([1.0, 1.0, 1.0], abs=1e-6)


def test_interpolate_cartesian_state_wrong_dimension() -> None:
    """Test that interpolate_cartesian_state raises error for wrong dimension."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=3, points_wanted=2
    )

    interpolator.add_data_point(0.0, np.array([1.0, 2.0, 3.0], dtype=float))

    with pytest.raises(
        ValueError, match="interpolate_cartesian_state requires dimension=6"
    ):
        interpolator.interpolate_cartesian_state(0.5)


def test_hermite_interpolator_multidimensional() -> None:
    """Test Hermite interpolation with multiple dimensions."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=3, points_wanted=2
    )

    # Add data points
    for x in range(5):
        data = np.array([float(x), float(x * x), float(2 * x)], dtype=float)
        interpolator.add_data_point(float(x), data)

    result: np.ndarray | None = interpolator.interpolate(2.5)
    assert result is not None
    assert result[0] == pytest.approx(2.5, abs=1e-10)
    assert result[1] == pytest.approx(6.25, abs=1e-6)
    assert result[2] == pytest.approx(5.0, abs=1e-10)


def test_hermite_interpolator_single_point() -> None:
    """Test Hermite interpolation with single data point."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=1
    )

    interpolator.add_data_point(1.0, np.array([5.0], dtype=float))

    result: np.ndarray | None = interpolator.interpolate(1.0)
    assert result is not None
    assert result[0] == pytest.approx(5.0, abs=1e-10)


def test_evaluate_polynomial_derivative() -> None:
    """Test polynomial derivative evaluation."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    # Add all data points first
    points = [0.0, 1.0, 2.0]
    for x in points:
        interpolator.add_data_point(x, np.array([x * x], dtype=float))

    # Then add derivatives for f(x) = x^2, f'(x) = 2x
    for x in points:
        interpolator.add_derivative(x, np.array([2 * x], dtype=float))

    # Build coefficients
    interpolator._build_q_coefficients()

    # Evaluate derivative at x = 1.5
    derivative: np.ndarray = interpolator._evaluate_polynomial_derivative(1.5)

    # f'(1.5) = 3.0
    assert derivative[0] == pytest.approx(3.0, abs=1e-6)


def test_derivative_independent_term() -> None:
    """Test derivative independent term calculation."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    interpolator.t_values = [[0.0, 1.0, 2.0]]

    # Order 0 or 1 should return 1.0
    result: float = interpolator._evaluate_derivative_independent_term(1.5, 0, 0)
    assert result == 1.0

    result = interpolator._evaluate_derivative_independent_term(1.5, 1, 0)
    assert result == 1.0

    # Order 2 should compute sum of products
    result = interpolator._evaluate_derivative_independent_term(1.5, 2, 0)
    # (1.5 - 1.0) + (1.5 - 0.0) = 0.5 + 1.5 = 2.0
    assert result == pytest.approx(2.0, abs=1e-10)


def test_set_derivative_data_dict_format() -> None:
    """Test set_derivative_data with dictionary input."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    for x in range(4):
        interpolator.add_data_point(float(x), np.array([float(x * x)], dtype=float))

    deriv_dict: dict[float, np.ndarray] = {
        float(x): np.array([float(2 * x)], dtype=float) for x in range(4)
    }
    interpolator.set_derivative_data(deriv_dict)

    result: np.ndarray | None = interpolator.interpolate(1.5)
    assert result is not None
    assert result[0] == pytest.approx(2.25, abs=1e-6)


def test_set_derivative_data_list_of_tuples_format() -> None:
    """Test set_derivative_data with list of tuples input."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    for x in range(4):
        interpolator.add_data_point(float(x), np.array([float(x * x)], dtype=float))

    deriv_tuples: list[tuple[float, np.ndarray]] = [
        (float(x), np.array([float(2 * x)], dtype=float)) for x in range(4)
    ]
    interpolator.set_derivative_data(deriv_tuples)

    result: np.ndarray | None = interpolator.interpolate(1.5)
    assert result is not None
    assert result[0] == pytest.approx(2.25, abs=1e-6)


def test_set_derivative_data_two_list_format() -> None:
    """Test set_derivative_data with separate independent and derivative lists."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )

    for x in range(4):
        interpolator.add_data_point(float(x), np.array([float(x * x)], dtype=float))

    indep_vals: list[float] = [float(x) for x in range(4)]
    deriv_vals: list[np.ndarray] = [
        np.array([float(2 * x)], dtype=float) for x in range(4)
    ]
    interpolator.set_derivative_data(indep_vals, derivative_data=deriv_vals)

    result: np.ndarray | None = interpolator.interpolate(1.5)
    assert result is not None
    assert result[0] == pytest.approx(2.25, abs=1e-6)


def test_set_derivative_data_invalid_order() -> None:
    """Test set_derivative_data raises ValueError for unsupported order."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))

    with pytest.raises(ValueError, match="Only first-order derivatives are supported"):
        interpolator.set_derivative_data({0.0: np.array([1.0])}, order=2)


def test_set_derivative_data_length_mismatch() -> None:
    """Test set_derivative_data raises ValueError on length mismatch."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))
    interpolator.add_data_point(1.0, np.array([2.0], dtype=float))

    with pytest.raises(ValueError, match="Length mismatch"):
        interpolator.set_derivative_data([0.0, 1.0], derivative_data=[np.array([1.0])])


def test_set_derivative_data_missing_derivative_data_arg() -> None:
    """Test set_derivative_data raises ValueError when derivative_data not provided for float list."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))

    with pytest.raises(
        ValueError,
        match="When data is a list of independent values, derivative_data must be provided",
    ):
        interpolator.set_derivative_data([0.0])


def test_set_derivative_data_nonexistent_independent_value() -> None:
    """Test set_derivative_data raises ValueError for unknown independent value."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))

    with pytest.raises(ValueError, match="Independent value .* not found in data"):
        interpolator.set_derivative_data({5.0: np.array([1.0])})


def test_set_derivative_data_dict_with_derivative_data_arg() -> None:
    """Test set_derivative_data raises ValueError when dict used with derivative_data."""
    interpolator: hermite.HermiteInterpolator = hermite.HermiteInterpolator(
        dimension=1, points_wanted=2
    )
    interpolator.add_data_point(0.0, np.array([1.0], dtype=float))

    with pytest.raises(
        ValueError,
        match="When derivative_data is provided, data must be a list or array",
    ):
        interpolator.set_derivative_data(
            {0.0: np.array([1.0])}, derivative_data=[np.array([1.0])]
        )
