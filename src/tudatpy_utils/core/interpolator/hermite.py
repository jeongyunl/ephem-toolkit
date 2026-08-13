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


class HermiteInterpolator(Interpolator):
    """Hermite interpolator supporting derivative data.

    Uses divided differences to build polynomial coefficients that incorporate
    both function values and first derivatives. All points must have consistent
    derivative availability (either all have derivatives or none do).
    """

    def __init__(
        self,
        dimension: int = 1,
        degree: int = DEFAULT_HERMITE_DEGREE,
        is_cartesian_state: bool = False,
    ) -> None:
        """Initialize Hermite interpolator.

        Parameters
        ----------
        dimension : int
            Number of components in each dependent data vector
        degree : int
            Interpolation polynomial degree
        is_cartesian_state : bool
            If True, data represents Cartesian state and interpolate() will use interpolate_cartesian_state()

        Raises
        ------
        ValueError
            If is_cartesian_state is True but dimension is not 6
        """
        if is_cartesian_state and dimension != 6:
            raise ValueError("dimension must be 6 when is_cartesian_state is True")

        super().__init__(dimension)

        self.required_points: int = degree + 1
        """Required points for a degree-N polynomial is N+1."""

        self.is_cartesian_state: bool = is_cartesian_state
        """If True, interpolate() delegates to interpolate_cartesian_state()."""

        self.derivatives: list[list[list[float]]] = []
        """Derivative data: derivatives[element][point][order]."""

        self.q_coeffs: list[list[float]] = []
        """Hermite polynomial coefficients for each dimension."""

        self.t_values: list[list[float]] = []
        """Independent values expanded for derivative data."""

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
            First derivative values. Use value < DERIVATIVE_UNAVAILABLE_SENTINEL to indicate
            no derivative available for that element.
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

        # Initialize derivative structure if not already present
        if not self.derivatives:
            self.derivatives = [
                [[] for _ in range(len(self.independent_values))]
                for _ in range(self.dependent_dimension)
            ]

        # Find index of the independent value
        try:
            index = self.independent_values.index(independent_value)
        except ValueError:
            raise ValueError(f"Independent value {independent_value} not found in data")

        added = False
        derivative_index = derivative_order - 1

        for i in range(self.dependent_dimension):
            if derivative_data[i] > DERIVATIVE_UNAVAILABLE_SENTINEL:
                if len(self.derivatives[i][index]) > derivative_index:
                    self.derivatives[i][index][derivative_index] = derivative_data[i]
                    added = True
                elif len(self.derivatives[i][index]) == derivative_index:
                    self.derivatives[i][index].append(derivative_data[i])
                    added = True
                else:
                    raise ValueError(
                        "Derivatives must be added in order starting from first derivative"
                    )

        return added

    def set_derivative_data(
        self,
        derivative_data: list[np.ndarray] | None = None,
        derivative_order: int = 1,
    ) -> None:
        """Replace all stored derivatives with the provided derivative data.

        Must be called after :meth:`Interpolator.set_data` or after adding
        data points, since it requires ``independent_values`` to already be
        populated.

        Parameters
        ----------
        derivative_data : list[np.ndarray] | None, optional
            List of derivative data vectors. Must be the same length as the
            number of independent values. If None, no derivatives are set.
        derivative_order : int
            Derivative order (only 1 is currently supported).

        Raises
        ------
        ValueError
            If derivative_order != 1, or if the length of derivative_data
            does not match the number of independent values.
        """
        if derivative_order != 1:
            raise ValueError("Only first-order derivatives are supported")

        # Then set derivative data if provided
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
                    if deriv_val[i] > DERIVATIVE_UNAVAILABLE_SENTINEL:
                        if len(self.derivatives[i][index]) == derivative_index:
                            self.derivatives[i][index].append(deriv_val[i])
                        elif len(self.derivatives[i][index]) > derivative_index:
                            self.derivatives[i][index][derivative_index] = deriv_val[i]
                        else:
                            raise ValueError(
                                "Derivatives must be added in order starting from first derivative"
                            )

    def clear_storage(self) -> None:
        """Remove all stored samples, derivatives, and reset state."""
        self.derivatives.clear()
        self.q_coeffs.clear()
        self.t_values.clear()
        super().clear_storage()

    def _build_q_coefficients(self) -> bool:
        """Build divided difference coefficients for Hermite polynomial.

        Returns
        -------
        bool
            True on success.

        Raises
        ------
        ValueError
            If derivative data is inconsistent across points.
        """
        self.q_coeffs = []
        self.t_values = []

        point_count = len(self.independent_values)

        for i in range(self.dependent_dimension):
            # Determine how many derivatives are available per point
            derivative_size = (
                len(self.derivatives[i][0])
                if self.derivatives and self.derivatives[i]
                else 0
            )
            # Expanded independent values (repeated for derivative data)
            expanded_indep_values = []
            # Initial column of divided difference table
            prev_col = []

            for m in range(point_count):
                if derivative_size > 0 and len(self.derivatives[i][m]) == 0:
                    raise ValueError(
                        "Inconsistent derivative data: some points have derivatives, others don't"
                    )

                # Repeat each independent value (derivative_size + 1) times
                for n in range(derivative_size + 1):
                    expanded_indep_values.append(self.independent_values[m])
                    prev_col.append(self.dependent_values[m][i])

            # Total polynomial order for Hermite interpolation
            order = point_count * (derivative_size + 1) - 1
            # Divided difference coefficients for this dimension
            divided_diff_coeffs = [prev_col[0]]
            point = 0
            t_index = 1

            # Build divided difference table iteratively
            for t in range(order):
                tableau = []
                for j in range(len(prev_col) - 1):
                    # Standard divided difference when independent values differ
                    if expanded_indep_values[j + t_index] != expanded_indep_values[j]:
                        deriv = (prev_col[j + 1] - prev_col[j]) / (
                            expanded_indep_values[j + t_index]
                            - expanded_indep_values[j]
                        )
                        point += 1
                    else:
                        # Use derivative data when independent values are equal
                        deriv = self.derivatives[i][point][0]

                    tableau.append(deriv)

                divided_diff_coeffs.append(tableau[0])
                prev_col = tableau
                t_index += 1

            self.q_coeffs.append(divided_diff_coeffs)
            self.t_values.append(expanded_indep_values)

        return True

    def _evaluate_polynomial(self, independent_value: float) -> np.ndarray:
        """Evaluate Hermite polynomial at given independent value.

        Uses Newton form: P(x) = q[0] + q[1](x-t[0]) + q[2](x-t[0])(x-t[1]) + ...

        Parameters
        ----------
        independent_value : float
            Value at which to evaluate the polynomial.

        Returns
        -------
        np.ndarray
            Interpolated dependent values.
        """
        results = np.zeros(self.dependent_dimension)

        for i in range(self.dependent_dimension):
            term_product = 1.0
            results[i] = 0.0

            for j in range(len(self.q_coeffs[i])):
                if j > 0:
                    # Accumulate product (x - t[0])(x - t[1])...(x - t[j-1])
                    term_product *= independent_value - self.t_values[i][j - 1]
                results[i] += self.q_coeffs[i][j] * term_product

        return results

    def _evaluate_polynomial_derivative(self, independent_value: float) -> np.ndarray:
        """Evaluate derivative of Hermite polynomial.

        Parameters
        ----------
        independent_value : float
            Value at which to evaluate the derivative.

        Returns
        -------
        np.ndarray
            Derivative values.
        """
        results = np.zeros(self.dependent_dimension)

        for i in range(self.dependent_dimension):
            for j in range(1, len(self.q_coeffs[i])):
                term_product = self._evaluate_derivative_independent_term(
                    independent_value, j, i
                )
                results[i] += self.q_coeffs[i][j] * term_product

        return results

    def _evaluate_derivative_independent_term(
        self, independent_value: float, order: int, element: int
    ) -> float:
        """Compute independent variable term for polynomial derivative.

        Parameters
        ----------
        independent_value : float
            Independent value.
        order : int
            Order of the Q coefficient.
        element : int
            Element index being evaluated.

        Returns
        -------
        float
            Coefficient for the polynomial term.
        """
        if order <= 1:
            return 1.0

        term_sum = 0.0
        for i in range(order):
            product = 1.0
            for j in range(order):
                if j != i:
                    product *= independent_value - self.t_values[element][j]
            term_sum += product

        return term_sum

    def _select_local_window(
        self, independent_value: float
    ) -> tuple[list[float], list[np.ndarray], list[list[list[float]]] | None]:
        """Select a local window of points around the query value.

        Chooses ``required_points`` contiguous samples centered near the query
        point, similar to how the Lagrange interpolator selects its window.

        Parameters
        ----------
        independent_value : float
            Query point around which to center the window.

        Returns
        -------
        tuple
            (independent_values, dependent_values, derivatives_or_None) for the
            local window.
        """
        n = len(self.independent_values)
        if n <= self.required_points:
            # Use all points if we don't have more than needed
            local_derivs = self.derivatives if self.derivatives else None
            return self.independent_values, self.dependent_values, local_derivs

        # Find insertion point for the query value
        idx = bisect.bisect_left(self.independent_values, independent_value)

        # Center the window around the query point
        half = self.required_points // 2
        start = idx - half
        if start < 0:
            start = 0
        end = start + self.required_points
        if end > n:
            end = n
            start = end - self.required_points

        local_indep = self.independent_values[start:end]
        local_dep = self.dependent_values[start:end]

        local_derivs = None
        if self.derivatives:
            local_derivs = [
                self.derivatives[dim][start:end]
                for dim in range(self.dependent_dimension)
            ]

        return local_indep, local_dep, local_derivs

    def _build_q_coefficients_local(
        self,
        indep: list[float],
        dep: list[np.ndarray],
        derivs: list[list[list[float]]] | None,
    ) -> bool:
        """Build divided difference coefficients for a local window of points.

        Parameters
        ----------
        indep : list[float]
            Independent values for the local window.
        dep : list[np.ndarray]
            Dependent values for the local window.
        derivs : list[list[list[float]]] | None
            Derivative data for the local window, or None.

        Returns
        -------
        bool
            True on success.
        """
        self.q_coeffs = []
        self.t_values = []

        point_count = len(indep)

        for i in range(self.dependent_dimension):
            # Determine how many derivatives are available per point
            derivative_size = (
                len(derivs[i][0]) if derivs and derivs[i] and derivs[i][0] else 0
            )
            # Expanded independent values (repeated for derivative data)
            expanded_indep_values = []
            # Initial column of divided difference table
            prev_col = []

            for m in range(point_count):
                if derivative_size > 0 and len(derivs[i][m]) == 0:
                    raise ValueError(
                        "Inconsistent derivative data: some points have derivatives, others don't"
                    )

                # Repeat each independent value (derivative_size + 1) times
                for n in range(derivative_size + 1):
                    expanded_indep_values.append(indep[m])
                    prev_col.append(dep[m][i])

            # Total polynomial order for Hermite interpolation
            order = point_count * (derivative_size + 1) - 1
            # Divided difference coefficients for this dimension
            divided_diff_coeffs = [prev_col[0]]
            point = 0
            t_index = 1

            # Build divided difference table iteratively
            for t in range(order):
                tableau = []
                for j in range(len(prev_col) - 1):
                    # Standard divided difference when independent values differ
                    if expanded_indep_values[j + t_index] != expanded_indep_values[j]:
                        deriv = (prev_col[j + 1] - prev_col[j]) / (
                            expanded_indep_values[j + t_index]
                            - expanded_indep_values[j]
                        )
                        point += 1
                    else:
                        # Use derivative data when independent values are equal
                        deriv = derivs[i][point][0]

                    tableau.append(deriv)

                divided_diff_coeffs.append(tableau[0])
                prev_col = tableau
                t_index += 1

            self.q_coeffs.append(divided_diff_coeffs)
            self.t_values.append(expanded_indep_values)

        return True

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Interpolate dependent values at given independent value.

        Uses a local window of points around the query value for efficiency.

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

        local_indep, local_dep, local_derivs = self._select_local_window(
            independent_value
        )
        if not self._build_q_coefficients_local(local_indep, local_dep, local_derivs):
            return None
        return self._evaluate_polynomial(independent_value)

    def interpolate_cartesian_state(
        self, independent_value: float
    ) -> np.ndarray | None:
        """Interpolate 6D Cartesian state (position + velocity).

        For 6-element states [x, y, z, vx, vy, vz], the velocity components
        are used as first-derivative data for the position components in the
        Hermite divided difference table. Position is computed via polynomial
        evaluation and velocity via the polynomial derivative.

        Uses a local window of points around the query value for efficiency.

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

        local_indep, local_dep, local_derivs = self._select_local_window(
            independent_value
        )

        # Build a 3-dimension Hermite interpolation using position as values
        # and velocity as first-derivative data
        point_count = len(local_indep)
        pos_dep = [dep_vec[0:3] for dep_vec in local_dep]
        vel_derivs: list[list[list[float]]] = [
            [[local_dep[pt][3 + dim]] for pt in range(point_count)] for dim in range(3)
        ]

        # Temporarily override dependent_dimension for the 3-component build
        orig_dim = self.dependent_dimension
        self.dependent_dimension = 3
        try:
            if not self._build_q_coefficients_local(local_indep, pos_dep, vel_derivs):
                return None

            position = self._evaluate_polynomial(independent_value)
            velocity = self._evaluate_polynomial_derivative(independent_value)
        finally:
            self.dependent_dimension = orig_dim

        results = np.zeros(6)
        results[0:3] = position
        results[3:6] = velocity

        return results
