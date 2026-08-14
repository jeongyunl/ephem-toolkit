"""Lagrange polynomial interpolator for scalar or vector dependent data.

Provides :class:`LagrangeInterpolator`, which selects a local polynomial
window around each query point and evaluates the classical Lagrange basis
formula to produce an interpolated dependent vector.
"""

from __future__ import annotations

import numpy as np

from .interpolator import Interpolator

RANGE_OVERSHOOT_TOLERANCE: float = 1e-8
"""Tolerance for allowing queries marginally outside the stored data range."""

MIN_DIFFERENCE_FOR_START: float = 1.0e30
"""Sentinel initial value used when searching for the minimum window bias."""

DEFAULT_LAGRANGE_DEGREE: int = 7
"""Default polynomial degree."""


class LagrangeInterpolator(Interpolator):
    """Lagrange interpolator that selects a local polynomial window for interpolation.

    Chooses a contiguous subset of stored points centered near the query and
    evaluates the classical Lagrange polynomial formula to produce an
    interpolated dependent vector.
    """

    def __init__(
        self, dimension: int = 1, degree: int = DEFAULT_LAGRANGE_DEGREE
    ) -> None:
        super().__init__(dimension)

        self.degree: int = degree
        """Current interpolation polynomial degree."""
        self.base_degree: int = degree
        """Base degree to restore when the buffer returns to full capacity."""
        self.reset_to_base_degree: bool = True
        """Reset degree to base_degree after an interpolation pass."""

        self.required_points: int = degree + 1
        """Required points for a degree-N polynomial is N+1."""

        self.candidate_window_start_index: int = 0
        """Indices used to select the interpolation window."""
        self.evaluation_start_index: int = 0
        self.candidate_window_end_index: int = 0
        self.closest_data_index: int = 0

    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Append a new sample to the base interpolator storage.

        Parameters
        ----------
        independent_value : float
            Independent variable value for the new data point.
        dependent_data : np.ndarray
            Dependent variable values for the new data point.
        """
        return super().add_data_point(independent_value, dependent_data)

    def reset_state(self) -> None:
        """Reset interpolator state while preserving stored samples."""
        super().reset_state()
        self.reset_to_base_degree = True

        self.candidate_window_start_index = 0
        self.evaluation_start_index = 0
        self.candidate_window_end_index = 0
        self.closest_data_index = 0

    def clear_storage(self) -> None:
        """Clear stored sample data and reset state for a fresh interpolation run."""
        super().clear_storage()
        self.reset_state()

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Compute the interpolated dependent vector for the requested value.

        Parameters
        ----------
        independent_value : float
            Query point at which to interpolate.

        Returns
        -------
        np.ndarray | None
            Interpolated dependent vector, or None if interpolation fails.
        """
        self._adjust_order_for_points()
        feasibility_flag: int = self._check_interpolation_feasibility(independent_value)
        if feasibility_flag != 1:
            return None

        # Choose a local set of sample points around the query point.
        if len(self.independent_values) >= self.required_points:
            if not self._is_closest_data_index_valid(independent_value):
                self._update_closest_data_index(independent_value)

            self._select_candidate_window(independent_value)
        elif not self.force_interpolation:
            return None

        # If the interpolator is allowed to refuse poor interpolations, verify
        # the query remains within the centered window.
        if not self.force_interpolation:
            if not self._is_query_centered():
                return None

        self._choose_evaluation_start_index(independent_value)

        products: np.ndarray = np.zeros(self.dependent_dimension, dtype=float)
        estimates: np.ndarray = np.zeros(self.dependent_dimension, dtype=float)

        for i in range(
            self.evaluation_start_index, self.candidate_window_end_index + 1
        ):
            # Begin each Lagrange term with the dependent value at point i.
            for dim in range(self.dependent_dimension):
                products[dim] = self.dependent_values[i][dim]

            # Build the basis polynomial L_i(x) by multiplying the ratios.
            for j in range(
                self.evaluation_start_index, self.candidate_window_end_index + 1
            ):
                if i != j:
                    for dim in range(self.dependent_dimension):
                        if (
                            self.independent_values[i] - self.independent_values[j]
                        ) == 0.0:
                            print("WARNING: Lagrange interpolation zero denominator")
                        products[dim] = (
                            products[dim]
                            * (independent_value - self.independent_values[j])
                            / (self.independent_values[i] - self.independent_values[j])
                        )

            # Accumulate the weighted contribution of the i-th basis polynomial.
            for dim in range(self.dependent_dimension):
                estimates[dim] += products[dim]

        return estimates

    def _check_interpolation_feasibility(self, independent_value: float) -> int:
        """Verify the query is within range and enough samples exist.

        Parameters
        ----------
        independent_value : float
            Query point to check for interpolation feasibility.

        Returns
        -------
        int
            1 if interpolation is feasible, -1 if insufficient points,
            -2 if below range, -3 if above range.
        """
        if len(self.independent_values) < self.required_points:
            return -1

        # If extrapolation is disabled, ensure the query stays within the stored range.
        if (independent_value < self.independent_values[0]) and (
            not self.allow_extrapolation
        ):
            if independent_value < (
                self.independent_values[0] - RANGE_OVERSHOOT_TOLERANCE
            ):
                return -2

        if (
            independent_value > self.independent_values[-1]
            and not self.allow_extrapolation
        ):
            if independent_value >= (
                self.independent_values[-1] + RANGE_OVERSHOOT_TOLERANCE
            ):
                return -3

        return 1

    def _adjust_order_for_points(self) -> bool:
        """Decrease polynomial degree when fewer samples are available than required.

        Returns
        -------
        bool
            True if degree was adjusted, False otherwise.
        """
        if (len(self.independent_values) > 1) and (
            len(self.independent_values) < self.required_points
        ):
            self.degree = len(self.independent_values) - 1
            self.required_points = self.degree + 1
            self.reset_to_base_degree = False
            return True

        return False

    def _is_closest_data_index_valid(self, independent_value: float) -> bool:
        """Return True when the current closest_data_index remains valid.

        For monotonic stored samples, the nearest sample only changes when the
        query crosses the midpoint between adjacent independent values.

        Parameters
        ----------
        independent_value : float
            Query point to validate against current closest index.

        Returns
        -------
        bool
            True if closest_data_index is still valid, False otherwise.
        """
        if not self.independent_values:
            return False

        if self.closest_data_index < 0 or self.closest_data_index >= len(
            self.independent_values
        ):
            return False

        if len(self.independent_values) == 1:
            return True

        if self.closest_data_index > 0:
            left_mid = 0.5 * (
                self.independent_values[self.closest_data_index - 1]
                + self.independent_values[self.closest_data_index]
            )
            if independent_value < left_mid:
                return False

        if self.closest_data_index < len(self.independent_values) - 1:
            right_mid = 0.5 * (
                self.independent_values[self.closest_data_index]
                + self.independent_values[self.closest_data_index + 1]
            )
            if independent_value > right_mid:
                return False

        return True

    def _update_closest_data_index(self, independent_value: float) -> None:
        """Update the closest_data_index to the sample nearest to independent_value.

        Parameters
        ----------
        independent_value : float
            Query point for which to find the nearest stored sample.
        """
        closest_data_index: int = 0
        distance_to_data_index: float = abs(
            self.independent_values[closest_data_index] - independent_value
        )
        for i in range(1, len(self.independent_values)):
            current_distance: float = abs(
                self.independent_values[i] - independent_value
            )
            if current_distance < distance_to_data_index:
                closest_data_index = i
                distance_to_data_index = current_distance

        self.closest_data_index = closest_data_index

    def _select_candidate_window(self, independent_value: float) -> None:
        """Select the contiguous point window that best surrounds the query.

        Parameters
        ----------
        independent_value : float
            Query point around which to center the interpolation window.
        """

        candidate_window_start_index: int = 0

        if self.required_points % 2 == 0:
            candidate_window_start_index = self.closest_data_index - (
                self.required_points // 2
            )
            if self.independent_values[self.closest_data_index] < independent_value:
                candidate_window_start_index += 1
        else:
            candidate_window_start_index = self.closest_data_index - (
                (self.required_points - 1) // 2
            )

        if candidate_window_start_index < 0:
            candidate_window_start_index = 0

        candidate_window_end_index: int = (
            candidate_window_start_index + self.required_points - 1
        )
        if candidate_window_end_index >= len(self.independent_values):
            candidate_window_end_index = len(self.independent_values) - 1
            candidate_window_start_index = (
                candidate_window_end_index - self.required_points + 1
            )

        self.candidate_window_start_index = candidate_window_start_index
        self.candidate_window_end_index = candidate_window_end_index

    def _is_query_centered(self) -> bool:
        """Return True when the query lies near the center of the selected window.

        Returns
        -------
        bool
            True if query is centered in the window, False otherwise.
        """
        retval: bool = False

        if (self.candidate_window_start_index >= 0) and (
            self.candidate_window_end_index < len(self.independent_values)
        ):
            if (self.closest_data_index + (self.degree / 2)) < len(
                self.independent_values
            ):
                retval = True

        return retval

    def _choose_evaluation_start_index(self, independent_value: float) -> None:
        """Pick the starting index for the interpolation window that minimizes bias.

        Parameters
        ----------
        independent_value : float
            Query point for which to optimize the window placement.
        """

        min_difference: float = MIN_DIFFERENCE_FOR_START
        q_min_index: int = 0
        q_end_index: int = min(
            self.candidate_window_start_index + self.degree - 1,
            len(self.independent_values) - self.degree - 2,
        )

        for q in range(self.candidate_window_start_index, q_end_index + 1):
            mean_independent: float = (
                self.independent_values[q + self.degree - 1]
                + self.independent_values[q]
            ) / 2
            diff: float = abs(mean_independent - independent_value)
            if diff < min_difference:
                q_min_index = q
                min_difference = diff

        start_index: int = q_min_index

        if (q_min_index + self.required_points) > (len(self.independent_values) - 1):
            start_index = len(self.independent_values) - self.degree + 1

        if start_index < 0:
            start_index = 0

        if self.candidate_window_start_index > 0:
            start_index = self.candidate_window_start_index

        self.evaluation_start_index = start_index
