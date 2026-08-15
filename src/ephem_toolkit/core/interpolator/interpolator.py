"""Base interpolation support for ordered sample storage.

This module defines the shared `Interpolator` API used by the sliding-window
polynomial interpolators in this package.

References:
    https://en.wikipedia.org/wiki/Interpolation
"""

from __future__ import annotations

import numpy as np

MINIMUM_REQUIRED_POINTS: int = 2
"""Minimum number of data points required to perform interpolation."""


class Interpolator:
    """Base interpolator supporting ordered sample storage and subclass hooks.

    Stores monotonically increasing independent values and their corresponding
    dependent vectors. Subclasses implement the actual interpolation strategy.
    """

    def __init__(self, dimension: int = 1) -> None:
        """Initialize the interpolator with a given dependent-vector dimension.

        Parameters
        ----------
        dimension : int
            Number of components in each dependent data vector.
        """
        self.force_interpolation: bool = True
        """Force interpolation to be attempted even when exact samples are available."""
        self.allow_extrapolation: bool = False
        """Allow extrapolation beyond the stored independent-variable domain."""

        self.independent_values: list[float] = []
        """Ordered independent-variable values used for interpolation."""
        self.dependent_values: list[np.ndarray] = []
        """Dependent vectors corresponding to each stored sample."""
        self.dependent_dimension: int = dimension
        """Dimension of each dependent vector."""

        self.required_points: int = MINIMUM_REQUIRED_POINTS
        """Minimum number of samples required by most interpolators."""

        self.previous_independent_value: float = float("-inf")
        """Most recently stored independent value; enforces monotonic ordering."""

    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Store a new sample pair for later interpolation.

        Parameters
        ----------
        independent_value : float
            Independent value for the new sample.
        dependent_data : np.ndarray
            Dependent data vector associated with the sample. Only the first
            `dependent_dimension` components are retained.
        """
        assert (
            independent_value > self.previous_independent_value
        ), "independent_value must monotonically increase"

        self.previous_independent_value = independent_value
        self.independent_values.append(independent_value)

        self.dependent_values.append(dependent_data[: self.dependent_dimension])

    def set_data(
        self,
        data: (
            dict[float, np.ndarray]
            | list[tuple[float, np.ndarray]]
            | list[float]
            | np.ndarray
        ),
        dependent_data: list[np.ndarray] | None = None,
    ) -> None:
        """Replace the stored samples with the provided data.

        Parameters
        ----------
        data : dict[float, np.ndarray] | list[tuple[float, np.ndarray]] | list[float] | np.ndarray
            The new sample data. Accepted forms are a dictionary keyed by
            independent values, a list of `(independent_value, dependent_value)`
            tuples, or a list/array of independent values together with
            `dependent_data`.
        dependent_data : list[np.ndarray] | None, optional
            Dependent vectors paired with `data` when `data` is a list or array of
            independent values. This is required when the input is a plain list of
            independent values.

        Raises
        ------
        ValueError
            If the provided structure is invalid or the supplied lengths do not
            match.
        """
        if dependent_data is not None:
            if isinstance(data, dict):
                raise ValueError(
                    "When dependent_data is provided, data must be a list or array of independent values"
                )
            if len(data) != len(dependent_data):
                raise ValueError(
                    f"Length mismatch: data has {len(data)} elements but dependent_data has {len(dependent_data)} elements"
                )
            self.independent_values = list(data)
            self.dependent_values = list(dependent_data)
        elif isinstance(data, dict):
            self.independent_values, self.dependent_values = zip(*sorted(data.items()))
            self.independent_values = list(self.independent_values)
            self.dependent_values = list(self.dependent_values)
        elif isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], tuple):
                self.independent_values, self.dependent_values = zip(*data)
                self.independent_values = list(self.independent_values)
                self.dependent_values = list(self.dependent_values)
            else:
                raise ValueError(
                    "When data is a list of independent values, dependent_data must be provided"
                )
        else:
            raise ValueError(
                "data must be a dict, list of tuples, or list of floats with dependent_data"
            )

        if len(self.independent_values) > 0:
            self.previous_independent_value = self.independent_values[-1]

    def reset_state(self) -> None:
        """Reset sequential bookkeeping while keeping the buffered samples intact."""
        self.previous_independent_value = float("-inf")

    def clear_storage(self) -> None:
        """Remove all stored samples and reset the internal state."""
        if self.independent_values:
            self.independent_values.clear()

        if self.dependent_values:
            self.dependent_values.clear()

        self.reset_state()

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Compute interpolated dependent data at the requested independent value.

        This base implementation is a placeholder and is intended to be overridden
        by concrete interpolator subclasses.

        Parameters
        ----------
        independent_value : float
            Independent value to evaluate.

        Returns
        -------
        np.ndarray | None
            Interpolated dependent values, or `None` when no subclass implementation
            is available.
        """
        return None
