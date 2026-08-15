"""Sliding-window Chebyshev polynomial interpolator for scalar or vector data.

Fits a local Chebyshev polynomial (in the Chebyshev basis, for numerical
stability) to a window of samples around each query point and evaluates it
using the Clenshaw recurrence. Windows near the domain boundary are widened
(rather than shrunk) so the fit becomes an overdetermined least-squares solve
there instead of an exact interpolant, which bounds boundary error without
requiring an excluded margin.

References:
    https://en.wikipedia.org/wiki/Chebyshev_polynomials
"""

from __future__ import annotations

import numpy as np
from numpy.polynomial import chebyshev as np_chebyshev
from typing_extensions import override

from .interpolator import Interpolator

DEFAULT_CHEBYSHEV_DEGREE: int = 5
RANGE_EXTRAPOLATION_TOLERANCE: float = 1.0e-12
"""Tolerance when accepting marginal out-of-range query values."""
BOUNDARY_DEGREE_BOOST: int = 2
"""Extra points used to widen boundary windows for stability."""


class ChebyshevInterpolator(Interpolator):
    """Sliding-window Chebyshev interpolator for scalar or vector data."""

    def __init__(
        self, dimension: int = 1, degree: int = DEFAULT_CHEBYSHEV_DEGREE
    ) -> None:
        """Initialize the interpolator with a dependent-vector dimension and degree."""
        if degree < 1:
            raise ValueError("degree must be at least 1")

        super().__init__(dimension)
        self.base_degree: int = int(degree)
        """Base degree restored when the data set is reset or refilled."""
        self._degree: int = int(degree)
        self.required_points: int = self._degree + 1

        self._cache_window: tuple[int, int] | None = None
        self._cache_domain: tuple[float, float] | None = None
        self._cache_coefficients: np.ndarray | None = None

    @property
    def degree(self) -> int:
        """Current interpolation polynomial degree."""
        return self._degree

    @degree.setter
    def degree(self, value: int) -> None:
        if value < 1:
            raise ValueError("degree must be at least 1")
        self._degree = int(value)
        self.required_points = self._degree + 1
        self._invalidate_cache()

    @override
    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Append a new independently ordered sample pair."""
        super().add_data_point(independent_value, dependent_data)
        self._invalidate_cache()

    @override
    def reset_state(self) -> None:
        """Reset sliding-state bookkeeping while retaining stored samples."""
        super().reset_state()
        self._degree = self.base_degree
        self.required_points = self._degree + 1
        self._invalidate_cache()

    @override
    def clear_storage(self) -> None:
        """Clear all sample data and restore the default state."""
        super().clear_storage()
        self._degree = self.base_degree
        self.required_points = self._degree + 1
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Invalidate the cached window fit."""
        self._cache_window = None
        self._cache_domain = None
        self._cache_coefficients = None

    @staticmethod
    def _select_window(
        independent_values: np.ndarray, independent_value: float, degree: int
    ) -> tuple[int, int, int]:
        """Select a local sample window and effective degree for a query value.

        Returns the half-open window ``[start, end)`` and the polynomial degree
        to fit within it. Windows near the domain boundary are widened by
        :data:`BOUNDARY_DEGREE_BOOST` extra points (keeping the same degree) so
        the fit is an overdetermined least-squares solve rather than an exact
        interpolant, which reduces boundary oscillation.
        """
        n = len(independent_values)
        base_window = degree + 1

        if n <= base_window:
            return 0, n, min(degree, max(1, n - 1))

        insertion_index = int(np.searchsorted(independent_values, independent_value))
        half_window = base_window // 2

        near_left = insertion_index <= half_window
        near_right = insertion_index >= n - half_window

        if near_left or near_right:
            window_count = min(n, base_window + BOUNDARY_DEGREE_BOOST)
            start = 0 if near_left else n - window_count
            return start, start + window_count, degree

        start = insertion_index - half_window
        start = max(0, min(start, n - base_window))
        return start, start + base_window, degree

    def _fit_window(
        self, window_independent_values: np.ndarray, effective_degree: int
    ) -> tuple[tuple[float, float], np.ndarray]:
        """Fit Chebyshev coefficients to a window, returning the domain and design matrix."""
        domain_low = float(window_independent_values[0])
        domain_high = float(window_independent_values[-1])
        if domain_high == domain_low:
            domain_high = domain_low + 1.0

        scaled_values = (2.0 * window_independent_values - (domain_high + domain_low)) / (
            domain_high - domain_low
        )
        design_matrix = np_chebyshev.chebvander(scaled_values, effective_degree)

        return (domain_low, domain_high), design_matrix

    @override
    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Evaluate the local Chebyshev polynomial fit via a cached least-squares solve."""
        if len(self.independent_values) < 2:
            return None

        independent_values = np.asarray(self.independent_values, dtype=float)
        minimum_value = float(independent_values[0])
        maximum_value = float(independent_values[-1])

        if independent_value < minimum_value:
            if not self.allow_extrapolation and (
                independent_value < minimum_value - RANGE_EXTRAPOLATION_TOLERANCE
            ):
                return None
        elif independent_value > maximum_value:
            if not self.allow_extrapolation and (
                independent_value > maximum_value + RANGE_EXTRAPOLATION_TOLERANCE
            ):
                return None

        window_start, window_end, effective_degree = self._select_window(
            independent_values, independent_value, self.degree
        )
        window_size = window_end - window_start
        if window_size < 2:
            return None

        if self._cache_window != (window_start, window_end):
            window_independent_values = independent_values[window_start:window_end]
            domain, design_matrix = self._fit_window(
                window_independent_values, effective_degree
            )
            window_dependent_values = np.asarray(
                self.dependent_values[window_start:window_end], dtype=float
            )
            coefficients, _, _, _ = np.linalg.lstsq(
                design_matrix, window_dependent_values, rcond=None
            )

            self._cache_window = (window_start, window_end)
            self._cache_domain = domain
            self._cache_coefficients = coefficients

        domain_low, domain_high = self._cache_domain
        scaled_query = (2.0 * independent_value - (domain_high + domain_low)) / (
            domain_high - domain_low
        )

        return np.atleast_1d(
            np_chebyshev.chebval(scaled_query, self._cache_coefficients)
        )
