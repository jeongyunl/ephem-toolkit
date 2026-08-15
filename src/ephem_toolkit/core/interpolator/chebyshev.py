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

    def __repr__(self) -> str:
        """Return a concise summary of the interpolator configuration."""
        return (
            "ChebyshevInterpolator("
            f"dimension={self.dependent_dimension}, "
            f"degree={self.degree}, "
            f"boundary_mode={self.boundary_mode!r}, "
            f"boundary_window_extension={self.boundary_window_extension})"
        )

    def __init__(
        self,
        dimension: int = 1,
        degree: int = DEFAULT_CHEBYSHEV_DEGREE,
        boundary_mode: str = "centered",
        boundary_window_extension: int = 0,
    ) -> None:
        """Initialize the interpolator state.

        Parameters
        ----------
        dimension : int, optional
            Number of components in each dependent data vector. Default is 1.
        degree : int, optional
            Polynomial degree used for the local Chebyshev fit. Default is 5.
        boundary_mode : str, optional
            Window-selection strategy used near the domain edges.
        boundary_window_extension : int, optional
            Additional sample points used when widening or anchoring edge windows.
        """
        if degree < 1:
            raise ValueError("degree must be at least 1")

        boundary_mode = str(boundary_mode).lower()
        if boundary_mode not in {"centered", "widen", "edge", "compact"}:
            raise ValueError(
                "boundary_mode must be one of: 'centered', 'widen', 'edge', 'compact'"
            )
        if boundary_window_extension < 0:
            raise ValueError("boundary_window_extension must be non-negative")

        super().__init__(dimension)
        self.base_degree: int = int(degree)
        """Base degree restored when the data set is reset or refilled."""
        self._degree: int = int(degree)
        self.required_points: int = self._degree + 1

        self.window_size: int = max(2, self._degree + 1)
        """Number of points in the local window used for the least-squares fit."""

        self.boundary_mode: str = boundary_mode
        """Boundary-aware window selection strategy."""
        self.boundary_window_extension: int = int(boundary_window_extension)
        """Additional points used when widening or anchoring edge windows."""

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

    def _select_window(
        self, independent_values: np.ndarray, independent_value: float
    ) -> tuple[int, int, int]:
        """Select a local sample window and effective degree for a query value.

        Parameters
        ----------
        independent_values : np.ndarray
            Sorted independent-variable samples in the active dataset.
        independent_value : float
            Query value to be evaluated by the interpolator.

        Returns
        -------
        tuple[int, int, int]
            The inclusive-exclusive window bounds and the effective polynomial degree.

        Notes
        -----
        The default strategy keeps a centered local window, while the boundary
        policies expand or anchor the window at the domain edge to reduce the
        one-sided interpolation sensitivity that arises near the first and last
        sample.
        """
        sample_count = len(independent_values)
        effective_window_size = self.window_size

        if self.boundary_mode in {"widen", "edge"}:
            effective_window_size = min(
                sample_count,
                self.window_size
                + min(self.boundary_window_extension, sample_count - self.window_size),
            )
        elif self.boundary_mode == "compact":
            effective_window_size = max(
                2,
                self.window_size
                - min(self.boundary_window_extension, self.window_size - 2),
            )

        if sample_count <= effective_window_size:
            return 0, sample_count, min(self.degree, max(1, sample_count - 1))

        insertion_index = int(np.searchsorted(independent_values, independent_value))

        if self.boundary_mode == "centered":
            half_window = effective_window_size // 2
            start = insertion_index - half_window
            if start < 0:
                start = 0
            end = start + effective_window_size
            if end > sample_count:
                end = sample_count
                start = max(0, end - effective_window_size)
        elif self.boundary_mode in {"widen", "edge"}:
            if insertion_index <= effective_window_size // 2:
                start = 0
                end = min(sample_count, effective_window_size)
            elif insertion_index >= sample_count - effective_window_size // 2:
                end = sample_count
                start = max(0, sample_count - effective_window_size)
            else:
                half_window = effective_window_size // 2
                start = insertion_index - half_window
                if start < 0:
                    start = 0
                end = start + effective_window_size
                if end > sample_count:
                    end = sample_count
                    start = max(0, end - effective_window_size)
        elif self.boundary_mode == "compact":
            if insertion_index <= effective_window_size // 2:
                start = 0
                end = min(sample_count, effective_window_size)
            elif insertion_index >= sample_count - effective_window_size // 2:
                end = sample_count
                start = max(0, sample_count - effective_window_size)
            else:
                half_window = effective_window_size // 2
                start = insertion_index - half_window
                if start < 0:
                    start = 0
                end = start + effective_window_size
                if end > sample_count:
                    end = sample_count
                    start = max(0, end - effective_window_size)
        else:
            raise ValueError(f"Unsupported boundary_mode: {self.boundary_mode}")

        if end - start < 2:
            return 0, sample_count, min(self.degree, max(1, sample_count - 1))

        effective_degree = min(self.degree, max(1, end - start - 1))
        return start, end, effective_degree

    def _fit_window(
        self, window_independent_values: np.ndarray, effective_degree: int
    ) -> tuple[tuple[float, float], np.ndarray]:
        """Fit Chebyshev coefficients on a local window.

        Parameters
        ----------
        window_independent_values : np.ndarray
            Independent values for the current local sampling window.
        effective_degree : int
            Target interpolating polynomial degree for this window.

        Returns
        -------
        tuple[tuple[float, float], np.ndarray]
            The scaled domain bounds and the Chebyshev design matrix.
        """
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
        """Evaluate the local Chebyshev polynomial fit via a cached least-squares solve.

        Parameters
        ----------
        independent_value : float
            Query point at which the interpolated dependent value is evaluated.

        Returns
        -------
        np.ndarray | None
            Interpolated dependent vector at the query point, or *None* if the
            value is outside the valid interpolation domain and extrapolation is
            disabled.
        """
        if len(self.independent_values) < 2:
            return None

        independent_values = np.asarray(self.independent_values, dtype=float)
        domain_minimum = float(independent_values[0])
        domain_maximum = float(independent_values[-1])

        if independent_value < domain_minimum:
            if not self.allow_extrapolation and (
                independent_value < domain_minimum - RANGE_EXTRAPOLATION_TOLERANCE
            ):
                return None
        elif independent_value > domain_maximum:
            if not self.allow_extrapolation and (
                independent_value > domain_maximum + RANGE_EXTRAPOLATION_TOLERANCE
            ):
                return None

        window_start, window_end, effective_degree = self._select_window(
            independent_values, independent_value
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
