"""Chebyshev polynomial interpolator for scalar or vector dependent data.

Provides :class:`ChebyshevInterpolator`, which fits a local window of stored
samples in a Chebyshev basis around each query point and evaluates the
resulting polynomial. This is a local (piecewise) interpolant: using a single
global fit over a wide data range is numerically unstable, so each query uses
a nearby window of ``degree + 1`` samples instead.

References:
    https://en.wikipedia.org/wiki/Chebyshev_polynomials
"""

from __future__ import annotations

import numpy as np

from .interpolator import MINIMUM_REQUIRED_POINTS, Interpolator

DEFAULT_CHEBYSHEV_DEGREE: int = 5
"""Default polynomial degree for Chebyshev interpolation."""

RANGE_EXTRAPOLATION_TOLERANCE: float = 1.0e-12
"""Tolerance used when accepting values that are marginally outside the data range."""

BOUNDARY_DEGREE_BOOST: int = 2
"""Extra points/degree used at the edges of the stored data.

Windows near the boundary are one-sided and therefore more prone to
oscillation (Runge's phenomenon) than a centered interior window. When extra
samples are available on the accessible side, the window is widened by up to
this many points to improve boundary accuracy and stability.
"""


class ChebyshevInterpolator(Interpolator):
    """Chebyshev polynomial interpolator for vector-valued dependent data.

    Uses a local window of neighboring samples around each query point,
    converts that window to a Chebyshev basis, and evaluates the fitted
    polynomial at the requested independent value.
    """

    def __init__(
        self, dimension: int = 1, degree: int = DEFAULT_CHEBYSHEV_DEGREE
    ) -> None:
        """Initialize the interpolator with a dependent-vector dimension and degree.

        Parameters
        ----------
        dimension : int, optional
            Number of components in each dependent data vector.
        degree : int, optional
            Polynomial degree used for the local Chebyshev fit.
        """
        super().__init__(dimension)

        self.degree: int = degree
        """Current interpolation polynomial degree."""
        self.base_degree: int = degree
        """Base degree restored when the sample set changes."""
        self.required_points: int = degree + 1
        """Required points for a degree-N Chebyshev polynomial is N + 1."""

    def reset_state(self) -> None:
        """Reset transient interpolation state while keeping stored samples."""
        super().reset_state()

    def clear_storage(self) -> None:
        """Clear stored sample data and reset the interpolation state."""
        super().clear_storage()

    @staticmethod
    def _closest_index(independent_values: np.ndarray, independent_value: float) -> int:
        """Return the index of the stored sample nearest to *independent_value*.

        Parameters
        ----------
        independent_values : np.ndarray
            Sorted array of stored independent variable values.
        independent_value : float
            Query location to locate within *independent_values*.

        Returns
        -------
        int
            Index of the nearest stored sample.
        """
        insertion_index = int(np.searchsorted(independent_values, independent_value))
        if insertion_index <= 0:
            return 0
        if insertion_index >= len(independent_values):
            return len(independent_values) - 1

        left_index = insertion_index - 1
        right_index = insertion_index
        left_distance = independent_value - independent_values[left_index]
        right_distance = independent_values[right_index] - independent_value
        return left_index if left_distance <= right_distance else right_index

    def _select_window(
        self, independent_values: np.ndarray, independent_value: float, degree: int
    ) -> tuple[int, int, int]:
        """Select the local sample window and effective degree for a query.

        The window is centered on the sample nearest to *independent_value*.
        When the centered window would run past the stored data (i.e. the
        query lies near a boundary), the window is shifted to stay in range
        and, if extra samples are available on the accessible side, widened
        by up to :data:`BOUNDARY_DEGREE_BOOST` points to reduce the
        oscillation typical of one-sided polynomial fits.

        Parameters
        ----------
        independent_values : np.ndarray
            Sorted array of stored independent variable values.
        independent_value : float
            Query location to build a window around.
        degree : int
            Requested polynomial degree for the fit.

        Returns
        -------
        tuple[int, int, int]
            ``(window_start, window_end, effective_degree)`` indices (inclusive)
            into *independent_values*.
        """
        number_of_samples = len(independent_values)
        required_sample_count = degree + 1
        closest_index = self._closest_index(independent_values, independent_value)

        if required_sample_count % 2 == 0:
            window_start = closest_index - required_sample_count // 2
            if independent_values[closest_index] < independent_value:
                window_start += 1
        else:
            window_start = closest_index - (required_sample_count - 1) // 2

        window_start = max(
            0, min(window_start, number_of_samples - required_sample_count)
        )
        window_end = window_start + degree

        is_boundary_window = window_start == 0 or window_end == number_of_samples - 1
        effective_degree = degree
        if is_boundary_window and number_of_samples > required_sample_count:
            available_extra_samples = number_of_samples - required_sample_count
            boundary_extension = min(BOUNDARY_DEGREE_BOOST, available_extra_samples)
            effective_degree = degree + boundary_extension
            if window_start == 0:
                window_end = effective_degree
            else:
                window_start = number_of_samples - 1 - effective_degree
                window_end = number_of_samples - 1

        return window_start, window_end, effective_degree

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Evaluate the Chebyshev interpolant at a query point.

        Parameters
        ----------
        independent_value : float
            Query location at which to evaluate the interpolant.

        Returns
        -------
        np.ndarray | None
            Interpolated dependent data vector, or *None* when the query falls
            outside the stored range and extrapolation is disabled.
        """
        if len(self.independent_values) < MINIMUM_REQUIRED_POINTS:
            return None

        if (
            independent_value < self.independent_values[0]
            and not self.allow_extrapolation
        ):
            if (
                independent_value
                < self.independent_values[0] - RANGE_EXTRAPOLATION_TOLERANCE
            ):
                return None

        if (
            independent_value > self.independent_values[-1]
            and not self.allow_extrapolation
        ):
            if (
                independent_value
                > self.independent_values[-1] + RANGE_EXTRAPOLATION_TOLERANCE
            ):
                return None

        dependent_values = np.asarray(self.dependent_values, dtype=float)
        independent_values = np.asarray(self.independent_values, dtype=float)

        current_degree = min(self.degree, len(independent_values) - 1)
        if current_degree < 1:
            closest_index = self._closest_index(independent_values, independent_value)
            return dependent_values[closest_index].copy()

        window_start, window_end, effective_degree = self._select_window(
            independent_values, independent_value, current_degree
        )
        window_independent_values = independent_values[window_start : window_end + 1]
        window_dependent_values = dependent_values[window_start : window_end + 1]

        minimum_independent_value = float(np.min(window_independent_values))
        maximum_independent_value = float(np.max(window_independent_values))
        if maximum_independent_value == minimum_independent_value:
            return window_dependent_values[0].copy()

        scaled_independent_values = (
            2.0
            * (window_independent_values - minimum_independent_value)
            / (maximum_independent_value - minimum_independent_value)
            - 1.0
        )
        scaled_query_value = (
            2.0
            * (independent_value - minimum_independent_value)
            / (maximum_independent_value - minimum_independent_value)
            - 1.0
        )

        interpolated_values = np.empty(self.dependent_dimension, dtype=float)
        for dimension_index in range(self.dependent_dimension):
            chebyshev_coefficients = np.polynomial.chebyshev.chebfit(
                scaled_independent_values,
                window_dependent_values[:, dimension_index],
                deg=effective_degree,
            )
            interpolated_values[dimension_index] = np.polynomial.chebyshev.chebval(
                scaled_query_value,
                chebyshev_coefficients,
            )

        return interpolated_values
