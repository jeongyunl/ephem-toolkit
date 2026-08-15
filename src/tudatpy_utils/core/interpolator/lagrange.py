from __future__ import annotations

import numpy as np
from typing_extensions import override

from .interpolator import Interpolator

DEFAULT_LAGRANGE_DEGREE: int = 7
BOUNDARY_WINDOW_REDUCTION: int = 2
"""Number of support points removed from edge windows to tame one-sided oscillation."""


class LagrangeInterpolator(Interpolator):
    """Sliding-window Lagrange interpolator for scalar or vector data."""

    def __init__(
        self, dimension: int = 1, degree: int = DEFAULT_LAGRANGE_DEGREE
    ) -> None:
        """Initialize the interpolator with a dependent-vector dimension and degree."""
        if degree < 1:
            raise ValueError("degree must be at least 1")

        super().__init__(dimension)
        self.degree: int = int(degree)
        self.window_size: int = max(2, self.degree + 1)
        self.required_points: int = max(2, self.degree + 1)
        self._cache_window_start: int = -1
        self._cache_window_values: np.ndarray | None = None
        self._cache_window_dependent_values: np.ndarray | None = None
        self._cache_window_weights: np.ndarray | None = None

    @override
    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Append a new independently ordered sample pair."""
        super().add_data_point(independent_value, dependent_data)
        self._cache_window_start = -1
        self._cache_window_values = None
        self._cache_window_dependent_values = None
        self._cache_window_weights = None

    @override
    def reset_state(self) -> None:
        """Reset sliding-state bookkeeping while retaining stored samples."""
        super().reset_state()
        self._cache_window_start = -1
        self._cache_window_values = None
        self._cache_window_dependent_values = None
        self._cache_window_weights = None

    @override
    def clear_storage(self) -> None:
        """Clear all sample data and restore the default state."""
        super().clear_storage()
        self._cache_window_start = -1
        self._cache_window_values = None
        self._cache_window_dependent_values = None
        self._cache_window_weights = None

    def _select_window(self, independent_value: float) -> tuple[int, np.ndarray]:
        """Return the local interpolation window start and x values for a query."""
        if len(self.independent_values) == 0:
            return -1, np.empty(0, dtype=float)

        independent_values = np.asarray(self.independent_values, dtype=float)
        minimum_value = float(independent_values[0])
        maximum_value = float(independent_values[-1])

        if independent_value < minimum_value:
            if not self.allow_extrapolation:
                if independent_value < minimum_value - 1.0e-12:
                    return -1, np.empty(0, dtype=float)
            full_window_count = min(self.window_size, len(independent_values))
            compact_window_count = max(2, full_window_count - BOUNDARY_WINDOW_REDUCTION)
            return 0, independent_values[:compact_window_count]

        if independent_value > maximum_value:
            if not self.allow_extrapolation:
                if independent_value > maximum_value + 1.0e-12:
                    return -1, np.empty(0, dtype=float)
            full_window_count = min(self.window_size, len(independent_values))
            compact_window_count = max(2, full_window_count - BOUNDARY_WINDOW_REDUCTION)
            start = max(0, len(independent_values) - compact_window_count)
            return start, independent_values[start:]

        if len(independent_values) <= self.window_size:
            return 0, independent_values

        insertion_index = int(np.searchsorted(independent_values, independent_value))
        window_count = min(self.window_size, len(independent_values))
        half_window = window_count // 2

        if insertion_index <= half_window:
            compact_window_count = max(2, window_count - BOUNDARY_WINDOW_REDUCTION)
            return 0, independent_values[:compact_window_count]

        if insertion_index >= len(independent_values) - half_window:
            compact_window_count = max(2, window_count - BOUNDARY_WINDOW_REDUCTION)
            start_index = len(independent_values) - compact_window_count
            return start_index, independent_values[start_index : start_index + compact_window_count]

        start_index = insertion_index - half_window
        if start_index < 0:
            start_index = 0
        if start_index + window_count > len(independent_values):
            start_index = len(independent_values) - window_count

        return (
            max(0, start_index),
            independent_values[start_index : start_index + window_count],
        )

    @staticmethod
    def _barycentric_weights(window_independent_values: np.ndarray) -> np.ndarray:
        """Compute Lagrange barycentric weights for a window of x values."""
        weights = np.empty(len(window_independent_values), dtype=float)
        for i, x_i in enumerate(window_independent_values):
            denominator = 1.0
            for j, x_j in enumerate(window_independent_values):
                if i == j:
                    continue
                denominator *= x_i - x_j
            weights[i] = 1.0 / denominator if np.abs(denominator) > 1.0e-30 else 0.0
        return weights

    @override
    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Evaluate the local Lagrange polynomial using a cached barycentric form."""
        if len(self.independent_values) < 2:
            return None

        window_start, window_independent_values = self._select_window(independent_value)
        if window_start < 0:
            return None

        window_size = len(window_independent_values)
        if window_size == 0:
            return None

        if (
            window_start != self._cache_window_start
            or self._cache_window_values is None
        ):
            self._cache_window_start = window_start
            self._cache_window_values = window_independent_values
            self._cache_window_dependent_values = np.asarray(
                self.dependent_values[window_start : window_start + window_size],
                dtype=float,
            )
            self._cache_window_weights = self._barycentric_weights(
                window_independent_values
            )

        window_values = self._cache_window_values
        dependent_values = self._cache_window_dependent_values
        weights = self._cache_window_weights

        if independent_value == window_values[0]:
            return dependent_values[0].copy()
        if independent_value == window_values[-1]:
            return dependent_values[-1].copy()

        numerator = np.zeros(self.dependent_dimension, dtype=float)
        denominator = 0.0
        for local_index, local_independent_value in enumerate(window_values):
            diff = independent_value - local_independent_value
            if np.isclose(diff, 0.0):
                return dependent_values[local_index].copy()
            weight_term = weights[local_index] / diff
            numerator += weight_term * dependent_values[local_index]
            denominator += weight_term

        return numerator / denominator

    def _check_interpolation_feasibility(self, independent_value: float) -> int:
        """Return the start index of a feasible local interpolation window."""
        window_start, _ = self._select_window(independent_value)
        return window_start
