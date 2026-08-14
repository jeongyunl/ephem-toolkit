"""Natural cubic spline interpolation for scalar or vector dependent data.

References:
    https://en.wikipedia.org/wiki/Spline_interpolation
"""

from __future__ import annotations

import numpy as np

from .interpolator import Interpolator

DEFAULT_CUBIC_DEGREE: int = 3
"""Default degree for cubic spline interpolation."""


class CubicSplineInterpolator(Interpolator):
    """Natural cubic spline interpolator.

    Builds a piecewise cubic spline with zero second derivatives at the ends
    of the data range. Query points are evaluated by locating the containing
    interval and evaluating the local cubic polynomial.
    """

    def __init__(self, dimension: int = 1) -> None:
        """Initialize the cubic spline interpolator.

        Parameters
        ----------
        dimension : int, optional
            Number of components in each dependent data vector. The default is 1.
        """
        super().__init__(dimension)
        self.required_points: int = 2
        """Minimum number of samples required for cubic spline interpolation."""
        self._cached_coefficients: list[np.ndarray] | None = None
        """Cached spline coefficients, invalidated on data change."""
        self._cached_point_count: int = 0
        """Point count when coefficients were last computed."""

    def reset_state(self) -> None:
        """Reset transient interpolation state while keeping buffered samples."""
        super().reset_state()
        self._cached_coefficients = None
        self._cached_point_count = 0

    def clear_storage(self) -> None:
        """Remove all data and reset the spline state."""
        super().clear_storage()
        self._cached_coefficients = None
        self._cached_point_count = 0

    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Append a new sample and invalidate cached coefficients."""
        super().add_data_point(independent_value, dependent_data)
        self._cached_coefficients = None
        self._cached_point_count = 0

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Compute the interpolated dependent vector for the given query value.

        Parameters
        ----------
        independent_value : float
            Query location at which to evaluate the spline.

        Returns
        -------
        np.ndarray | None
            Interpolated dependent data vector, or *None* if interpolation is
            not feasible for the current stored sample set.
        """
        if len(self.independent_values) < 2:
            return None

        if (
            independent_value < self.independent_values[0]
            and not self.allow_extrapolation
        ):
            if independent_value < self.independent_values[0] - 1.0e-12:
                return None
        if (
            independent_value > self.independent_values[-1]
            and not self.allow_extrapolation
        ):
            if independent_value > self.independent_values[-1] + 1.0e-12:
                return None

        independent_values_array = np.asarray(self.independent_values, dtype=float)
        if independent_value <= independent_values_array[0]:
            return np.asarray(self.dependent_values[0], dtype=float).copy()
        if independent_value >= independent_values_array[-1]:
            return np.asarray(self.dependent_values[-1], dtype=float).copy()

        coefficients = self._get_coefficients()
        interval_index = (
            np.searchsorted(independent_values_array, independent_value, side="right")
            - 1
        )
        interval_index = min(max(interval_index, 0), len(independent_values_array) - 2)

        interval_start_x = independent_values_array[interval_index]
        interval_offset = independent_value - interval_start_x

        interpolated_values = np.empty(self.dependent_dimension, dtype=float)
        for dimension_index in range(self.dependent_dimension):
            polynomial_a = coefficients[dimension_index][interval_index, 0]
            polynomial_b = coefficients[dimension_index][interval_index, 1]
            polynomial_c = coefficients[dimension_index][interval_index, 2]
            polynomial_d = coefficients[dimension_index][interval_index, 3]
            interpolated_values[dimension_index] = (
                polynomial_a
                + polynomial_b * interval_offset
                + polynomial_c * interval_offset**2
                + polynomial_d * interval_offset**3
            )

        return interpolated_values

    def _get_coefficients(self) -> list[np.ndarray]:
        """Return cached coefficients, recomputing only if data changed."""
        current_count = len(self.independent_values)
        if (
            self._cached_coefficients is None
            or self._cached_point_count != current_count
        ):
            self._cached_coefficients = self._compute_interval_coefficients()
            self._cached_point_count = current_count
        return self._cached_coefficients

    def _compute_interval_coefficients(self) -> list[np.ndarray]:
        """Return cubic coefficients for each interval and dimension.

        Coefficients are stored as [a, b, c, d] for each interval, where the
        local polynomial is expressed as a + b*(x - x_i) + c*(x - x_i)^2 +
        d*(x - x_i)^3 on the interval [x_i, x_{i+1}].
        """
        independent_values_array = np.asarray(self.independent_values, dtype=float)
        point_count = len(independent_values_array)

        if point_count < 2:
            return [
                np.zeros((0, 4), dtype=float) for _ in range(self.dependent_dimension)
            ]

        coefficients: list[np.ndarray] = []
        for dimension_index in range(self.dependent_dimension):
            dependent_values_array = np.asarray(
                [
                    self.dependent_values[index][dimension_index]
                    for index in range(point_count)
                ],
                dtype=float,
            )

            if point_count == 2:
                interval_width = (
                    independent_values_array[1] - independent_values_array[0]
                )
                slope = (
                    dependent_values_array[1] - dependent_values_array[0]
                ) / interval_width
                interval_coefficients = np.array(
                    [[dependent_values_array[0], slope, 0.0, 0.0]],
                    dtype=float,
                )
                coefficients.append(interval_coefficients)
                continue

            interval_widths = np.diff(independent_values_array)
            second_derivative = np.zeros(point_count, dtype=float)
            tri_diagonal = np.zeros((point_count - 2, point_count - 2), dtype=float)
            right_hand_side = np.zeros(point_count - 2, dtype=float)

            for i in range(point_count - 2):
                tri_diagonal[i, i] = 2.0 * (interval_widths[i] + interval_widths[i + 1])
                if i > 0:
                    tri_diagonal[i, i - 1] = interval_widths[i]
                if i < point_count - 3:
                    tri_diagonal[i, i + 1] = interval_widths[i + 1]

                right_hand_side[i] = 6.0 * (
                    (dependent_values_array[i + 2] - dependent_values_array[i + 1])
                    / interval_widths[i + 1]
                    - (dependent_values_array[i + 1] - dependent_values_array[i])
                    / interval_widths[i]
                )

            second_derivative[1:-1] = np.linalg.solve(tri_diagonal, right_hand_side)

            interval_coefficients = np.zeros((point_count - 1, 4), dtype=float)
            for interval_index in range(point_count - 1):
                interval_width = (
                    independent_values_array[interval_index + 1]
                    - independent_values_array[interval_index]
                )
                polynomial_a = dependent_values_array[interval_index]
                polynomial_b = (
                    dependent_values_array[interval_index + 1]
                    - dependent_values_array[interval_index]
                ) / interval_width - interval_width * (
                    2.0 * second_derivative[interval_index]
                    + second_derivative[interval_index + 1]
                ) / 6.0
                polynomial_c = second_derivative[interval_index] / 2.0
                polynomial_d = (
                    second_derivative[interval_index + 1]
                    - second_derivative[interval_index]
                ) / (6.0 * interval_width)
                interval_coefficients[interval_index] = np.array(
                    [polynomial_a, polynomial_b, polynomial_c, polynomial_d],
                    dtype=float,
                )

            coefficients.append(interval_coefficients)

        return coefficients
