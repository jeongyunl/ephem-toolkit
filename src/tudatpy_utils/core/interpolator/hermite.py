"""Hermite interpolator using divided differences with derivative data.

Implements Hermite-Newton interpolation following the divided difference
approach. Supports first-order derivative data for improved accuracy.

References:
    https://en.wikipedia.org/wiki/Hermite_interpolation
    https://en.wikipedia.org/wiki/Divided_differences
"""

from __future__ import annotations

import numpy as np

from .interpolator import Interpolator


class HermiteInterpolator(Interpolator):
    """Hermite interpolator supporting derivative data.

    Uses divided differences to build polynomial coefficients that incorporate
    both function values and first derivatives. All points must have consistent
    derivative availability (either all have derivatives or none do).
    """

    def __init__(self, dimension: int = 1, points_wanted: int = 2) -> None:
        """Initialize Hermite interpolator.

        Parameters
        ----------
        dimension : int
            Number of components in each dependent data vector.
        points_wanted : int
            Number of data points to use for interpolation.
        """
        super().__init__(dimension)
        self.points_wanted: int = points_wanted

        self.derivatives: list[list[list[float]]] = []
        """Derivative data: derivatives[element][point][order]."""

        self.q_coeffs: list[list[float]] = []
        """Hermite polynomial coefficients for each dimension."""

        self.t_values: list[list[float]] = []
        """Independent values expanded for derivative data."""

    def add_derivative(
        self, independent_value: float, derivative_data: np.ndarray, order: int = 1
    ) -> bool:
        """Add derivative data for a specific independent value.

        Parameters
        ----------
        independent_value : float
            Independent variable value for this derivative.
        derivative_data : np.ndarray
            First derivative values. Use value < -9.99999e99 to indicate
            no derivative available for that element.
        order : int
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
        if order != 1:
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
        derivative_index = order - 1

        for i in range(self.dependent_dimension):
            if derivative_data[i] > -9.99999e99:
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
        data: (
            dict[float, np.ndarray]
            | list[tuple[float, np.ndarray]]
            | list[float]
            | np.ndarray
        ),
        derivative_data: list[np.ndarray] | None = None,
        order: int = 1,
    ) -> None:
        """Replace all stored derivatives with the contents of *data*.

        Accepts three input formats:
        - Dictionary mapping independent values to derivative vectors (sorted by key)
        - List of (independent_value, derivative_data) tuples (assumed sorted)
        - List/array of independent values with separate *derivative_data* list (assumed sorted and equal length)

        Parameters
        ----------
        data : dict[float, np.ndarray] | list[tuple[float, np.ndarray]] | list[float] | np.ndarray
            Either:
            - A mapping of independent variable values to derivative data vectors.
            - A list of (independent_value, derivative_data) tuples.
            - A list or array of independent variable values (requires *derivative_data*).

            If a dictionary is provided, it is sorted by key before storage.
            If a list of tuples is provided, it is assumed to be already sorted.
            If a list/array of floats is provided, *derivative_data* must also be provided,
            and both are assumed to be already sorted and of equal length.
        derivative_data : list[np.ndarray] | None, optional
            List of derivative data vectors, required only when *data* is a list/array
            of independent values. Must be the same length as *data*.
        order : int
            Derivative order (only 1 is currently supported).

        Raises
        ------
        ValueError
            If *data* is a list of floats but *derivative_data* is not provided,
            or if the lengths of *data* and *derivative_data* don't match,
            or if order != 1, or if independent values don't match stored data.
        """
        if order != 1:
            raise ValueError("Only first-order derivatives are supported")

        independent_vals = []
        deriv_vals = []

        if derivative_data is not None:
            if isinstance(data, dict):
                raise ValueError(
                    "When derivative_data is provided, data must be a list or array of independent values"
                )
            if len(data) != len(derivative_data):
                raise ValueError(
                    f"Length mismatch: data has {len(data)} elements but derivative_data has {len(derivative_data)} elements"
                )
            independent_vals = list(data)
            deriv_vals = list(derivative_data)
        elif isinstance(data, dict):
            independent_vals, deriv_vals = zip(*sorted(data.items()))
            independent_vals = list(independent_vals)
            deriv_vals = list(deriv_vals)
        elif isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], tuple):
                independent_vals, deriv_vals = zip(*data)
                independent_vals = list(independent_vals)
                deriv_vals = list(deriv_vals)
            else:
                raise ValueError(
                    "When data is a list of independent values, derivative_data must be provided"
                )
        else:
            raise ValueError(
                "data must be a dict, list of tuples, or list of floats with derivative_data"
            )
        self.derivatives = [
            [[] for _ in range(len(self.independent_values))]
            for _ in range(self.dependent_dimension)
        ]
        derivative_index = order - 1
        for indep_val, deriv_val in zip(independent_vals, deriv_vals):
            try:
                index = self.independent_values.index(indep_val)
            except ValueError:
                raise ValueError(f"Independent value {indep_val} not found in data")

            for i in range(self.dependent_dimension):
                if deriv_val[i] > -9.99999e99:
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
            derivative_size = (
                len(self.derivatives[i][0])
                if self.derivatives and self.derivatives[i]
                else 0
            )
            x = []
            prev_col = []

            for m in range(point_count):
                if derivative_size > 0 and len(self.derivatives[i][m]) == 0:
                    raise ValueError(
                        "Inconsistent derivative data: some points have derivatives, others don't"
                    )

                for n in range(derivative_size + 1):
                    x.append(self.independent_values[m])
                    prev_col.append(self.dependent_values[m][i])

            order = point_count * (derivative_size + 1) - 1
            q_i = [prev_col[0]]
            point = 0
            t_index = 1

            for t in range(order):
                tableau = []
                for j in range(len(prev_col) - 1):
                    if x[j + t_index] != x[j]:
                        deriv = (prev_col[j + 1] - prev_col[j]) / (
                            x[j + t_index] - x[j]
                        )
                        point += 1
                    else:
                        deriv = self.derivatives[i][point][0]

                    tableau.append(deriv)

                q_i.append(tableau[0])
                prev_col = tableau
                t_index += 1

            self.q_coeffs.append(q_i)
            self.t_values.append(x)

        return True

    def _evaluate_polynomial(self, independent_value: float) -> np.ndarray:
        """Evaluate Hermite polynomial at given independent value.

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

    def interpolate_value(self, independent_value: float) -> np.ndarray | None:
        """Interpolate dependent values at given independent value.

        Parameters
        ----------
        independent_value : float
            Value at which to interpolate.

        Returns
        -------
        np.ndarray | None
            Interpolated values, or None on failure.
        """
        if not self._build_q_coefficients():
            return None
        return self._evaluate_polynomial(independent_value)

    def interpolate_cartesian_state(
        self, independent_value: float
    ) -> np.ndarray | None:
        """Interpolate 6D Cartesian state (position + velocity).

        For 6-element states, computes position via polynomial evaluation
        and velocity via polynomial derivative of position components.

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

        if not self._build_q_coefficients():
            return None

        results = self._evaluate_polynomial(independent_value)
        derivative = self._evaluate_polynomial_derivative(independent_value)

        results[3:6] = derivative[0:3]

        return results
