from __future__ import annotations
import numpy as np

MINIMUM_REQUIRED_POINTS = 2


class Interpolator:
    """Base interpolator supporting fixed-size ordered sample storage.

    This class stores monotonically increasing independent values and the
    corresponding dependent vectors. It provides a common API for buffering
    data points and a placeholder interpolation interface for subclasses.

    Attributes:
        force_interpolation: If False, interpolation may be refused for poor data.
        allow_extrapolation: If True, allow requests outside the stored range.

        independent_values: Stored independent variable values.
        dependent_values: Stored dependent data vectors.
        dependent_dimension: Number of dependent dimensions stored per point.

        required_points: Number of points needed to perform interpolation.
        previous_independent_value: Last independent value added.
    """

    # Initialize base interpolation buffers and state
    def __init__(self, dimension: int = 1) -> None:
        self.force_interpolation = True
        self.allow_extrapolation = False

        # The ordered independent variable values used for interpolation.
        self.independent_values: list[float] = []
        # The corresponding dependent vectors for each stored sample.
        self.dependent_values: list[np.ndarray] = []
        self.dependent_dimension = dimension

        # Minimum number of samples required by most interpolators.
        self.required_points = MINIMUM_REQUIRED_POINTS

        # Track monotonicity of input samples; newer values must be greater.
        self.previous_independent_value = float("-inf")

    def add_data_point(
        self, independent_value: float, dependent_data: np.ndarray
    ) -> None:
        """Store a new sample pair for later interpolation.

        The independent values must increase monotonically, otherwise the
        ordering assumptions used by interpolation algorithms break.
        """
        assert (
            independent_value > self.previous_independent_value
        ), "independent_value must monotonically increase"

        self.previous_independent_value = independent_value
        self.independent_values.append(independent_value)

        # Slice the dependent data to the configured dependent dimension.
        self.dependent_values.append(dependent_data[: self.dependent_dimension])

    def add_point(self, independent_value: float, dependent_data: np.ndarray) -> None:
        """Alias for add_data_point to simplify external usage."""
        self.add_data_point(independent_value, dependent_data)

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

    def interpolate_value(
        self, independent_value: float
    ) -> tuple[bool, np.ndarray | None]:
        """Placeholder interpolation method to be implemented by subclasses."""
        return False, None

    def interpolate(self, independent_value: float) -> tuple[bool, np.ndarray | None]:
        """Compute interpolated dependent data for the requested independent value."""
        return self.interpolate_value(independent_value)
