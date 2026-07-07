"""Base interpolator class for ordered sample storage and interpolation.

Provides :class:`Interpolator`, a base class that buffers monotonically
increasing independent-variable samples and their corresponding dependent
vectors, and exposes a common API for subclass interpolation algorithms.
"""

from __future__ import annotations

import numpy as np

MINIMUM_REQUIRED_POINTS: int = 2
"""Minimum number of data points required to perform any interpolation."""


class Interpolator:
    """Base interpolator supporting fixed-size ordered sample storage.

    Stores monotonically increasing independent values and the corresponding
    dependent vectors. Provides a common API for buffering data points and a
    placeholder interpolation interface for subclasses.
    """

    def __init__(self, dimension: int = 1) -> None:
        """Initialise the interpolator with a given dependent-vector dimension.

        Parameters
        ----------
        dimension : int
            Number of components in each dependent data vector.
        """
        self.force_interpolation: bool = True
        self.allow_extrapolation: bool = False

        self.independent_values: list[float] = []
        """The ordered independent variable values used for interpolation."""
        self.dependent_values: list[np.ndarray] = []
        """The corresponding dependent vectors for each stored sample."""
        self.dependent_dimension: int = dimension

        self.required_points: int = MINIMUM_REQUIRED_POINTS
        """Minimum number of samples required by most interpolators."""

        self.previous_independent_value: float = float("-inf")
        """Track monotonicity of input samples; newer values must be greater."""

    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Store a new sample pair for later interpolation.

        Independent values must increase monotonically; the ordering
        assumption is enforced by an assertion.

        Parameters
        ----------
        independent_value : float
            The independent variable value for this sample.
        dependent_data : np.ndarray
            Dependent data vector; only the first ``dependent_dimension``
            components are stored.
        """
        assert (
            independent_value > self.previous_independent_value
        ), "independent_value must monotonically increase"

        self.previous_independent_value = independent_value
        self.independent_values.append(independent_value)

        # Slice the dependent data to the configured dependent dimension.
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
        """Replace all stored samples with the contents of *data*.

        Parameters
        ----------
        data : dict[float, np.ndarray] | list[tuple[float, np.ndarray]] | list[float] | np.ndarray
            Either:
            - A mapping of independent variable values to dependent data vectors.
            - A list of (independent_value, dependent_data) tuples.
            - A list or array of independent variable values (requires *dependent_data*).

            If a dictionary is provided, it is sorted by key before storage.
            If a list of tuples is provided, it is assumed to be already sorted.
            If a list/array of floats is provided, *dependent_data* must also be provided,
            and both are assumed to be already sorted and of equal length.
        dependent_data : list[np.ndarray] | None, optional
            List of dependent data vectors, required only when *data* is a list/array
            of independent values. Must be the same length as *data*.

        Raises
        ------
        ValueError
            If *data* is a list of floats but *dependent_data* is not provided,
            or if the lengths of *data* and *dependent_data* don't match.
        """
        if dependent_data is not None:
            # Two-list format: data is list/array of independent values, dependent_data is list of dependent values
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
            # Dict format: sort by key and unpack
            self.independent_values, self.dependent_values = zip(*sorted(data.items()))
            self.independent_values = list(self.independent_values)
            self.dependent_values = list(self.dependent_values)
        elif isinstance(data, list) and len(data) > 0:
            # Check if it's a list of tuples or a list of floats
            if isinstance(data[0], tuple):
                # List of tuples format: assume already sorted
                self.independent_values, self.dependent_values = zip(*data)
                self.independent_values = list(self.independent_values)
                self.dependent_values = list(self.dependent_values)
            else:
                # List of floats without dependent_data - error
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
        """Reset sequential state while keeping buffered samples intact."""
        self.previous_independent_value = float("-inf")

    def clear_storage(self) -> None:
        """Remove all stored samples and reset internal state."""
        if self.independent_values:
            self.independent_values.clear()

        if self.dependent_values:
            self.dependent_values.clear()

        self.reset_state()

    def interpolate_value(self, independent_value: float) -> np.ndarray | None:
        """Placeholder interpolation method to be implemented by subclasses."""
        return None

    def interpolate(self, independent_value: float) -> np.ndarray | None:
        """Compute interpolated dependent data for the requested independent value."""
        return self.interpolate_value(independent_value)
