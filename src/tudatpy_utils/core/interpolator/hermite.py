"""Hermite interpolator using divided differences with derivative data.

Implements Hermite-Newton interpolation following the divided difference
approach. Supports first-order derivative data for improved accuracy.

References:
    https://en.wikipedia.org/wiki/Hermite_interpolation
    https://en.wikipedia.org/wiki/Divided_differences
"""

from __future__ import annotations

import bisect

import numpy as np

from .interpolator import Interpolator

DEFAULT_HERMITE_DEGREE: int = 5
"""Default polynomial degree for Hermite interpolation."""

DERIVATIVE_UNAVAILABLE_SENTINEL: float = -9.99999e99
"""Sentinel value indicating no derivative data available for an element."""


class SlidingWindowHermiteInterpolator(Interpolator):
    """Sliding-window Hermite interpolator with caching and Cartesian state optimization.

    Uses local sliding windows with divided differences for efficient high-order
    interpolation. Caches coefficients per window. Optimized for Cartesian state
    vectors [x,y,z,vx,vy,vz] by treating velocity as position derivatives, but
    supports general-purpose interpolation as well.
    """

    def __init__(
        self,
        dimension: int = 1,
        degree: int = DEFAULT_HERMITE_DEGREE,
        is_cartesian_state: bool = False,
    ) -> None:
        """Initialize high-order sliding-window Hermite interpolator.

        Parameters
        ----------
        dimension : int
            Number of components in each dependent data vector
        degree : int
            Interpolation polynomial degree
        is_cartesian_state : bool
            If True, optimizes for 6D Cartesian state [x,y,z,vx,vy,vz]

        Raises
        ------
        ValueError
            If is_cartesian_state is True but dimension is not 6
        """
        if is_cartesian_state and dimension != 6:
            raise ValueError("dimension must be 6 when is_cartesian_state is True")

        super().__init__(dimension)
        self.required_points = max(2, degree + 1)

        self.window_size: int = max(2, degree + 1)
        """Number of points in the local window. Hermite interpolation needs at least degree + 1 samples when derivative data are absent."""

        self.is_cartesian_state: bool = is_cartesian_state
        """If True, optimizes for Cartesian state vectors."""

        self.derivatives: list[list[list[float]]] = []
        """Derivative data: derivatives[element][point][order]."""

        self.q_coeffs: list[list[float]] = []
        self.t_values: list[list[float]] = []

        # Cache for last window to avoid recomputation
        self._cache_window_start: int = -1
        self._cache_q_coeffs: list[list[float]] = []
        self._cache_t_values: list[list[float]] = []

    def add_derivative(
        self,
        independent_value: float,
        derivative_data: np.ndarray,
        derivative_order: int = 1,
    ) -> bool:
        """Add derivative data for a specific independent value.

        Parameters
        ----------
        independent_value : float
            Independent variable value for this derivative.
        derivative_data : np.ndarray
            First derivative values.
        derivative_order : int
            Derivative order (only 1 is currently supported).

        Returns
        -------
        bool
            True if at least one derivative was added.

        Raises
        ------
        ValueError
            If order != 1 or independent_value not found in data.
        """
        if derivative_order != 1:
            raise ValueError("Only first-order derivatives are supported")

        if not self.derivatives:
            self.derivatives = [
                [[] for _ in range(len(self.independent_values))]
                for _ in range(self.dependent_dimension)
            ]

        try:
            index = self.independent_values.index(independent_value)
        except ValueError:
            raise ValueError(f"Independent value {independent_value} not found in data")

        added = False
        derivative_index = derivative_order - 1

        for i in range(self.dependent_dimension):
            if len(self.derivatives[i][index]) > derivative_index:
                self.derivatives[i][index][derivative_index] = derivative_data[i]
                added = True
            elif len(self.derivatives[i][index]) == derivative_index:
                self.derivatives[i][index].append(derivative_data[i])
                added = True

        self._invalidate_cache()
        return added

    def set_derivative_data(
        self,
        derivative_data: list[np.ndarray] | None = None,
        derivative_order: int = 1,
    ) -> None:
        """Replace all stored derivatives with the provided derivative data.

        Parameters
        ----------
        derivative_data : list[np.ndarray] | None, optional
            List of derivative data vectors. Must match number of independent values.
        derivative_order : int
            Derivative order (only 1 is currently supported).

        Raises
        ------
        ValueError
            If derivative_order != 1, or length mismatch.
        """
        if derivative_order != 1:
            raise ValueError("Only first-order derivatives are supported")

        if derivative_data is not None:
            if len(derivative_data) != len(self.independent_values):
                raise ValueError(
                    f"Length mismatch: derivative_data has {len(derivative_data)} elements "
                    f"but there are {len(self.independent_values)} independent values"
                )

            self.derivatives = [
                [[] for _ in range(len(self.independent_values))]
                for _ in range(self.dependent_dimension)
            ]
            derivative_index = derivative_order - 1

            for index, deriv_val in enumerate(derivative_data):
                for i in range(self.dependent_dimension):
                    if len(self.derivatives[i][index]) == derivative_index:
                        self.derivatives[i][index].append(deriv_val[i])
                    elif len(self.derivatives[i][index]) > derivative_index:
                        self.derivatives[i][index][derivative_index] = deriv_val[i]

        self._invalidate_cache()

    def clear_storage(self) -> None:
        """Remove all stored samples, derivatives, and reset state."""
        self.derivatives.clear()
        self.q_coeffs.clear()
        self.t_values.clear()
        self._invalidate_cache()
        super().clear_storage()

    def _invalidate_cache(self) -> None:
        """Invalidate cached window coefficients."""
        self._cache_window_start = -1
        self._cache_q_coeffs.clear()
        self._cache_t_values.clear()

    def _select_window(
        self, independent_value: float
    ) -> tuple[int, list[float], list[np.ndarray], list[list[list[float]]] | None]:
        """Select sliding window around query value.

        Parameters
        ----------
        independent_value : float
            Query point around which to center the window.

        Returns
        -------
        tuple
            (window_start_index, independent_values, dependent_values, derivatives_or_None)
        """
        n = len(self.independent_values)
        if n <= self.window_size:
            local_derivs = self.derivatives if self.derivatives else None
            return 0, self.independent_values, self.dependent_values, local_derivs

        idx = bisect.bisect_left(self.independent_values, independent_value)

        half = self.window_size // 2
        start = idx - half
        if start < 0:
            start = 0
        end = start + self.window_size
        if end > n:
            end = n
            start = end - self.window_size

        local_indep = self.independent_values[start:end]
        local_dep = self.dependent_values[start:end]

        local_derivs = None
        if self.derivatives:
            local_derivs = [
                self.derivatives[dim][start:end]
                for dim in range(self.dependent_dimension)
            ]

        return start, local_indep, local_dep, local_derivs

    def _build_divided_differences(
        self,
        indep: list[float],
        dep: list[np.ndarray],
        derivs: list[list[list[float]]] | None,
        dimension: int,
    ) -> tuple[list[list[float]], list[list[float]]]:
        """Build divided difference coefficients for specified dimensions.

        Parameters
        ----------
        indep : list[float]
            Independent values for the window.
        dep : list[np.ndarray]
            Dependent values for the window.
        derivs : list[list[list[float]]] | None
            Derivative data for the window, or None.
        dimension : int
            Number of dimensions to process.

        Returns
        -------
        tuple
            (q_coeffs, t_values) for each dimension.
        """
        q_coeffs = []
        t_values = []
        point_count = len(indep)

        for i in range(dimension):
            if derivs is not None and derivs[i]:
                counts = [len(point_derivs) for point_derivs in derivs[i]]
                positive_counts = [count for count in counts if count > 0]
                if positive_counts and (
                    any(count == 0 for count in counts)
                    or any(count != positive_counts[0] for count in positive_counts)
                ):
                    raise ValueError("Inconsistent derivative data")

            derivative_size = (
                len(derivs[i][0]) if derivs and derivs[i] and derivs[i][0] else 0
            )
            expanded_indep = []
            prev_col = []

            for m in range(point_count):
                for n in range(derivative_size + 1):
                    expanded_indep.append(indep[m])
                    prev_col.append(dep[m][i])

            order = point_count * (derivative_size + 1) - 1
            divided_diff_coeffs = [prev_col[0]]
            point = 0
            t_index = 1

            for t in range(order):
                tableau = []
                for j in range(len(prev_col) - 1):
                    if expanded_indep[j + t_index] != expanded_indep[j]:
                        deriv = (prev_col[j + 1] - prev_col[j]) / (
                            expanded_indep[j + t_index] - expanded_indep[j]
                        )
                        point += 1
                    else:
                        deriv = derivs[i][point][0]

                    tableau.append(deriv)

                divided_diff_coeffs.append(tableau[0])
                prev_col = tableau
                t_index += 1

            q_coeffs.append(divided_diff_coeffs)
            t_values.append(expanded_indep)

        return q_coeffs, t_values

    def _evaluate_newton_polynomial(
        self,
        independent_value: float,
        q_coeffs: list[list[float]],
        t_values: list[list[float]],
        dimension: int,
    ) -> np.ndarray:
        """Evaluate Newton polynomial.

        Parameters
        ----------
        independent_value : float
            Value at which to evaluate.
        q_coeffs : list[list[float]]
            Divided difference coefficients.
        t_values : list[list[float]]
            Expanded independent values.
        dimension : int
            Number of dimensions.

        Returns
        -------
        np.ndarray
            Interpolated values.
        """
        results = np.zeros(dimension)

        for i in range(dimension):
            term_product = 1.0
            results[i] = 0.0

            for j in range(len(q_coeffs[i])):
                if j > 0:
                    term_product *= independent_value - t_values[i][j - 1]
                results[i] += q_coeffs[i][j] * term_product

        return results

    def _evaluate_newton_polynomial_derivative(
        self,
        independent_value: float,
        q_coeffs: list[list[float]],
        t_values: list[list[float]],
        dimension: int,
    ) -> np.ndarray:
        """Evaluate derivative of Newton polynomial.

        Parameters
        ----------
        independent_value : float
            Value at which to evaluate derivative.
        q_coeffs : list[list[float]]
            Divided difference coefficients.
        t_values : list[list[float]]
            Expanded independent values.
        dimension : int
            Number of dimensions.

        Returns
        -------
        np.ndarray
            Derivative values.
        """
        results = np.zeros(dimension)

        for i in range(dimension):
            for j in range(1, len(q_coeffs[i])):
                term_sum = 0.0
                for k in range(j):
                    product = 1.0
                    for m in range(j):
                        if m != k:
                            product *= independent_value - t_values[i][m]
                    term_sum += product

                results[i] += q_coeffs[i][j] * term_sum

        return results

    def _build_q_coefficients(self) -> list[list[float]]:
        """Build and cache the divided-difference coefficients for the active window."""
        if not self.independent_values:
            self.q_coeffs = []
            self.t_values = []
            return self.q_coeffs

        window_start, local_indep, local_dep, local_derivs = self._select_window(
            self.independent_values[-1]
        )
        self.q_coeffs, self.t_values = self._build_divided_differences(
            local_indep, local_dep, local_derivs, self.dependent_dimension
        )
        self._cache_window_start = window_start
        self._cache_q_coeffs = self.q_coeffs
        self._cache_t_values = self.t_values
        return self.q_coeffs

    def _evaluate_polynomial_derivative(self, independent_value: float) -> np.ndarray:
        """Evaluate the derivative of the interpolating polynomial at a query point."""
        if not self.q_coeffs:
            self._build_q_coefficients()
        return self._evaluate_newton_polynomial_derivative(
            independent_value,
            self.q_coeffs,
            self.t_values,
            self.dependent_dimension,
        )

    def _evaluate_derivative_independent_term(
        self, independent_value: float, order: int, dimension_index: int
    ) -> float:
        """Compute the derivative-independent term used in Newton-Hermite derivatives."""
        if order <= 1:
            return 1.0

        term_sum = 0.0
        for k in range(order):
            product = 1.0
            for m in range(order):
                if m != k:
                    product *= independent_value - self.t_values[dimension_index][m]
            term_sum += product
        return term_sum

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Interpolate dependent values at given independent value.

        Uses sliding window for high-order interpolation with caching.

        Parameters
        ----------
        independent_value : float
            Value at which to interpolate.

        Returns
        -------
        np.ndarray | None
            Interpolated values, or None on failure.
        """
        if self.is_cartesian_state:
            return self.interpolate_cartesian_state(independent_value)

        if len(self.independent_values) < 1:
            return None

        window_start, local_indep, local_dep, local_derivs = self._select_window(
            independent_value
        )

        # Use cache if window hasn't changed
        if window_start != self._cache_window_start:
            self._cache_q_coeffs, self._cache_t_values = (
                self._build_divided_differences(
                    local_indep, local_dep, local_derivs, self.dependent_dimension
                )
            )
            self._cache_window_start = window_start

        return self._evaluate_newton_polynomial(
            independent_value,
            self._cache_q_coeffs,
            self._cache_t_values,
            self.dependent_dimension,
        )

    def interpolate_cartesian_state(
        self, independent_value: float
    ) -> np.ndarray | None:
        """Interpolate 6D Cartesian state with optimization.

        Treats velocity [vx,vy,vz] as derivatives of position [x,y,z] for
        improved accuracy. Position computed via polynomial evaluation,
        velocity via polynomial derivative.

        Parameters
        ----------
        independent_value : float
            Value at which to interpolate.

        Returns
        -------
        np.ndarray | None
            6-element state [x, y, z, vx, vy, vz], or None on failure.

        Raises
        ------
        ValueError
            If dimension is not 6.
        """
        if self.dependent_dimension != 6:
            raise ValueError("interpolate_cartesian_state requires dimension=6")

        if len(self.independent_values) < 1:
            return None

        window_start, local_indep, local_dep, _ = self._select_window(independent_value)

        # Extract position and velocity components
        point_count = len(local_indep)
        pos_dep = [dep_vec[0:3] for dep_vec in local_dep]
        vel_derivs: list[list[list[float]]] = [
            [[local_dep[pt][3 + dim]] for pt in range(point_count)] for dim in range(3)
        ]

        # Use cache if window hasn't changed
        if window_start != self._cache_window_start:
            self._cache_q_coeffs, self._cache_t_values = (
                self._build_divided_differences(local_indep, pos_dep, vel_derivs, 3)
            )
            self._cache_window_start = window_start

        position = self._evaluate_newton_polynomial(
            independent_value, self._cache_q_coeffs, self._cache_t_values, 3
        )
        velocity = self._evaluate_newton_polynomial_derivative(
            independent_value, self._cache_q_coeffs, self._cache_t_values, 3
        )

        results = np.zeros(6)
        results[0:3] = position
        results[3:6] = velocity

        return results
