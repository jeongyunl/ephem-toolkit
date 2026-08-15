"""Natural cubic spline interpolator for ordered scalar and vector data."""

from __future__ import annotations

import numpy as np
from typing_extensions import override

from .interpolator import Interpolator

DEFAULT_CUBIC_SPLINE_DEGREE: int = 3
"""Degree used by the natural cubic spline implementation."""


class CubicSplineInterpolator(Interpolator):
    """Natural cubic spline interpolator for scalar or vector-valued data.

    The implementation stores a local polynomial for each interval of the form
    a + b (x - x_i) + c (x - x_i)^2 + d (x - x_i)^3 and solves the natural-spline
    conditions c_0 = c_n = 0 on the full data range. The spline coefficients are
    built once per data update and then reused for repeated evaluations.
    """

    def __init__(
        self,
        dimension: int = 1,
        degree: int = DEFAULT_CUBIC_SPLINE_DEGREE,
        boundary_mode: str = "centered",
        boundary_window_extension: int = 0,
    ) -> None:
        """Initialize a natural cubic spline interpolator.

        Parameters
        ----------
        dimension : int, optional
            Number of dependent components in each sample vector.
        degree : int, optional
            Cubic spline degree. The implementation is fixed to degree 3 and
            validates that the requested degree matches the natural cubic spline.
        boundary_mode : str, optional
            Accepted for API compatibility with other interpolators. Unused by the
            global spline fit.
        boundary_window_extension : int, optional
            Accepted for API compatibility with other interpolators. Unused by the
            global spline fit.
        """
        if degree != DEFAULT_CUBIC_SPLINE_DEGREE:
            raise ValueError(
                "CubicSplineInterpolator only supports cubic splines (degree=3)"
            )

        boundary_mode = str(boundary_mode).lower()
        if boundary_mode not in {"centered", "widen", "edge", "compact"}:
            raise ValueError(
                "boundary_mode must be one of: 'centered', 'widen', 'edge', 'compact'"
            )
        if boundary_window_extension < 0:
            raise ValueError("boundary_window_extension must be non-negative")

        super().__init__(dimension)
        self.degree: int = DEFAULT_CUBIC_SPLINE_DEGREE
        self.required_points: int = 2
        self.window_size: int = 2
        self.boundary_mode: str = boundary_mode
        self.boundary_window_extension: int = int(boundary_window_extension)

        self._coefficients: list[np.ndarray] | None = None
        self._independent_cache: np.ndarray | None = None

    @override
    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Append a new ordered sample pair and invalidate cached coefficients."""
        super().add_data_point(independent_value, dependent_data)
        self._invalidate_cache()

    @override
    def reset_state(self) -> None:
        """Reset transient state while preserving buffered samples."""
        super().reset_state()
        self._invalidate_cache()

    @override
    def clear_storage(self) -> None:
        """Remove stored samples and spline coefficients."""
        super().clear_storage()
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Discard cached interval coefficients."""
        self._coefficients = None
        self._independent_cache = None

    def _build_coefficients(self) -> None:
        """Assemble the cubic-spline coefficients for each interval and component."""
        sample_count = len(self.independent_values)
        if sample_count < 2:
            self._coefficients = []
            self._independent_cache = np.asarray(self.independent_values, dtype=float)
            return

        x_values = np.asarray(self.independent_values, dtype=float)
        y_values = np.asarray(self.dependent_values, dtype=float)
        self._independent_cache = x_values

        if sample_count == 2:
            interval_width = x_values[1] - x_values[0]
            if interval_width == 0.0:
                raise ValueError("independent values must be strictly increasing")

            coefficients: list[np.ndarray] = []
            for component_index in range(self.dependent_dimension):
                y0 = y_values[0, component_index]
                y1 = y_values[1, component_index]
                slope = (y1 - y0) / interval_width
                coefficients.append(
                    np.asarray(
                        [
                            [y0, slope, 0.0, 0.0],
                            [y1, slope, 0.0, 0.0],
                        ],
                        dtype=float,
                    )
                )
            self._coefficients = coefficients
            return

        interval_widths = np.diff(x_values)
        if np.any(interval_widths <= 0.0):
            raise ValueError("independent values must be strictly increasing")

        coefficients: list[np.ndarray] = []
        for component_index in range(self.dependent_dimension):
            y_component = y_values[:, component_index]
            second_derivatives = np.zeros(sample_count, dtype=float)

            if sample_count > 2:
                system_size = sample_count - 2
                system_matrix = np.zeros((system_size, system_size), dtype=float)
                rhs = np.zeros(system_size, dtype=float)

                for i in range(system_size):
                    system_matrix[i, i] = 2.0 * (
                        interval_widths[i] + interval_widths[i + 1]
                    )
                    if i > 0:
                        system_matrix[i, i - 1] = interval_widths[i]
                    if i < system_size - 1:
                        system_matrix[i, i + 1] = interval_widths[i + 1]

                    rhs[i] = 3.0 * (
                        (y_component[i + 2] - y_component[i + 1]) / interval_widths[i + 1]
                        - (y_component[i + 1] - y_component[i]) / interval_widths[i]
                    )

                second_derivatives[1:-1] = np.linalg.solve(system_matrix, rhs)

            interval_coefficients = np.zeros((sample_count - 1, 4), dtype=float)
            for interval_index in range(sample_count - 1):
                h = interval_widths[interval_index]
                left_value = y_component[interval_index]
                right_value = y_component[interval_index + 1]
                c_left = second_derivatives[interval_index]
                c_right = second_derivatives[interval_index + 1]

                b_value = (right_value - left_value) / h - h * (
                    2.0 * c_left + c_right
                ) / 3.0
                d_value = (c_right - c_left) / (3.0 * h)

                interval_coefficients[interval_index] = np.array(
                    [left_value, b_value, c_left, d_value], dtype=float
                )

            coefficients.append(interval_coefficients)

        self._coefficients = coefficients

    def _get_interval_index(self, independent_value: float) -> int:
        """Return the interval index for a query value."""
        x_values = self._independent_cache
        if x_values is None:
            x_values = np.asarray(self.independent_values, dtype=float)
            self._independent_cache = x_values

        x_count = len(x_values)
        if x_count < 2:
            return 0

        if independent_value <= x_values[0]:
            return 0
        if independent_value >= x_values[-1]:
            return x_count - 2

        interval_index = int(np.searchsorted(x_values, independent_value, side="right")) - 1
        return max(0, min(interval_index, x_count - 2))

    @override
    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Evaluate the natural cubic spline at a query point."""
        if len(self.independent_values) < 2:
            return None

        x_values = np.asarray(self.independent_values, dtype=float)
        if x_values.size == 0:
            return None

        lower_bound = float(x_values[0])
        upper_bound = float(x_values[-1])
        tolerance = 1.0e-12 * max(1.0, abs(lower_bound), abs(upper_bound))

        if independent_value < lower_bound - tolerance:
            if not self.allow_extrapolation:
                return None
            independent_value = lower_bound
        elif independent_value > upper_bound + tolerance:
            if not self.allow_extrapolation:
                return None
            independent_value = upper_bound

        if independent_value == lower_bound:
            return np.asarray(self.dependent_values[0], dtype=float).copy()
        if independent_value == upper_bound:
            return np.asarray(self.dependent_values[-1], dtype=float).copy()

        if self._coefficients is None or self._independent_cache is None:
            self._build_coefficients()

        if self._coefficients is None:
            return None

        interval_index = self._get_interval_index(independent_value)
        x_left = x_values[interval_index]
        delta_x = independent_value - x_left

        interpolated = np.empty(self.dependent_dimension, dtype=float)
        for component_index in range(self.dependent_dimension):
            coeffs = self._coefficients[component_index][interval_index]
            interpolated[component_index] = (
                coeffs[0]
                + coeffs[1] * delta_x
                + coeffs[2] * delta_x * delta_x
                + coeffs[3] * delta_x * delta_x * delta_x
            )

        return interpolated
