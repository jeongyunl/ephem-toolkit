"""Base interpolation support for ordered sample storage.

This module defines the shared `Interpolator` API used by the sliding-window
polynomial interpolators in this package.

References:
    https://en.wikipedia.org/wiki/Interpolation
"""

from __future__ import annotations

from threading import RLock

import numpy as np

from .interpolation_spec import InterpolationSpec

MINIMUM_REQUIRED_POINTS: int = 2
"""Minimum number of data points required to perform interpolation."""

INITIAL_PREVIOUS_INDEPENDENT_VALUE: float = float("-inf")
"""Sentinel value before any independent values have been stored."""


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

        self.previous_independent_value: float = INITIAL_PREVIOUS_INDEPENDENT_VALUE
        """Most recently stored independent value; enforces monotonic ordering."""
        self._stateless = False
        """Whether this instance evaluates caller-owned views instead of storing samples."""
        self._stateless_spec: InterpolationSpec | None = None
        self._stateless_lock = RLock()

    @property
    def stateless(self) -> bool:
        """Whether this instance accepts view-based evaluation."""
        return self._stateless

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
        if self.stateless:
            raise RuntimeError(
                "stateless interpolators accept data through interpolate_view"
            )
        assert (
            independent_value > self.previous_independent_value
        ), "independent_value must monotonically increase"

        self.previous_independent_value = independent_value
        self.independent_values.append(independent_value)

        self.dependent_values.append(dependent_data[: self.dependent_dimension])
        self._on_samples_changed()

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
        if self.stateless:
            raise RuntimeError(
                "stateless interpolators accept data through interpolate_view"
            )
        if dependent_data is not None:
            if isinstance(data, dict):
                raise ValueError(
                    "When dependent_data is provided, data must be a list or array of independent values"
                )
            if len(data) != len(dependent_data):
                raise ValueError(
                    f"Length mismatch: data has {len(data)} elements but dependent_data has {len(dependent_data)} elements"
                )
            independent_values = list(data)
            dependent_values = list(dependent_data)
        elif isinstance(data, dict):
            independent_values, dependent_values = zip(*sorted(data.items()))
            independent_values = list(independent_values)
            dependent_values = list(dependent_values)
        elif isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], tuple):
                independent_values, dependent_values = zip(*data)
                independent_values = list(independent_values)
                dependent_values = list(dependent_values)
            else:
                raise ValueError(
                    "When data is a list of independent values, dependent_data must be provided"
                )
        else:
            raise ValueError(
                "data must be a dict, list of tuples, or list of floats with dependent_data"
            )

        self._replace_data(independent_values, dependent_values)

    def _replace_data(
        self,
        independent_values: list[float],
        dependent_values: list[np.ndarray],
    ) -> None:
        """Replace stored samples and notify subclasses of the data change."""
        self.independent_values = independent_values
        self.dependent_values = dependent_values
        if self.independent_values:
            self.previous_independent_value = self.independent_values[-1]
        self._on_samples_changed()

    def _on_data_changed(self) -> None:
        """Invalidate caches derived from any interpolation input."""

    def _on_samples_changed(self) -> None:
        """Notify subclasses that the buffered sample set changed."""
        self._on_data_changed()

    def reset_state(self) -> None:
        """Reset sequential bookkeeping while keeping the buffered samples intact."""
        self.previous_independent_value = INITIAL_PREVIOUS_INDEPENDENT_VALUE

    def clear_storage(self) -> None:
        """Remove all stored samples and reset the internal state."""
        if self.independent_values:
            self.independent_values.clear()

        if self.dependent_values:
            self.dependent_values.clear()

        self.reset_state()
        self._on_samples_changed()

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

    def _enable_stateless_mode(
        self,
        spec: InterpolationSpec | None,
        is_cartesian_state: bool,
    ) -> None:
        if (
            isinstance(self.dependent_dimension, bool)
            or not isinstance(self.dependent_dimension, int)
            or self.dependent_dimension < 1
        ):
            raise ValueError("dimension must be a positive integer")
        if is_cartesian_state and self.dependent_dimension != 6:
            raise ValueError("dimension must be 6 when is_cartesian_state is True")
        if self.independent_values or self.dependent_values:
            raise RuntimeError("stateless mode must be enabled before setting data")
        if spec is not None:
            degree = spec.degree
            if (
                isinstance(degree, bool)
                or not isinstance(degree, int)
                or degree < 1
            ):
                raise ValueError("interpolation degree must be a positive integer")
            spec = InterpolationSpec(spec.interp_type, degree=degree)
        elif is_cartesian_state:
            raise ValueError("linear interpolation cannot use Cartesian-state Hermite mode")

        self._stateless = True
        self._stateless_spec = spec

    def interpolate_view(
        self,
        independent_values: np.ndarray,
        dependent_values: np.ndarray,
        independent_value: float,
        segment_ids: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """Interpolate caller-owned views without retaining their samples.

        This method is available on instances created with
        ``InterpolatorFactory.create(..., stateless=True)``. Polynomial support
        rows are loaded into this existing interpolator for the duration of the
        call and cleared before returning.
        """
        if not self.stateless:
            raise RuntimeError("interpolate_view requires stateless mode")
        with self._stateless_lock:
            return self._interpolate_view_locked(
                independent_values,
                dependent_values,
                independent_value,
                segment_ids,
            )

    def _interpolate_view_locked(
        self,
        independent_values: np.ndarray,
        dependent_values: np.ndarray,
        independent_value: float,
        segment_ids: np.ndarray | None,
    ) -> np.ndarray | None:
        if independent_values.ndim != 1:
            raise ValueError("independent_values must be one-dimensional")
        if dependent_values.shape != (independent_values.size, self.dependent_dimension):
            raise ValueError(
                "dependent_values must have shape "
                "(len(independent_values), dimension)"
            )
        if segment_ids is not None and segment_ids.shape != independent_values.shape:
            raise ValueError("segment_ids must have shape (len(independent_values),)")
        if isinstance(independent_value, bool):
            raise ValueError("independent value must be a finite number")
        try:
            query_value = float(independent_value)
        except (TypeError, ValueError) as error:
            raise ValueError("independent value must be a finite number") from error
        if not np.isfinite(query_value):
            raise ValueError("independent value must be a finite number")
        if independent_values.size == 0:
            return None

        upper_index = int(np.searchsorted(independent_values, query_value))
        if (
            upper_index < independent_values.size
            and independent_values[upper_index] == query_value
        ):
            return np.asarray(
                memoryview(dependent_values[upper_index]).toreadonly()
            )
        if upper_index == 0 or upper_index == independent_values.size:
            return None

        lower_index = upper_index - 1
        segment_start = 0
        segment_stop = independent_values.size
        if segment_ids is not None:
            segment_id = segment_ids[lower_index]
            if segment_id != segment_ids[upper_index]:
                return None
            segment_start = int(np.searchsorted(segment_ids, segment_id, side="left"))
            segment_stop = int(np.searchsorted(segment_ids, segment_id, side="right"))

        if self._stateless_spec is None:
            lower_value = independent_values[lower_index]
            upper_value = independent_values[upper_index]
            fraction = (query_value - lower_value) / (upper_value - lower_value)
            return dependent_values[lower_index] + fraction * (
                dependent_values[upper_index] - dependent_values[lower_index]
            )

        segment_sample_count = segment_stop - segment_start
        support_count = min(
            segment_sample_count, max(MINIMUM_REQUIRED_POINTS, self.required_points)
        )
        local_upper_index = upper_index - segment_start
        support_start = max(
            0,
            min(
                local_upper_index - support_count // 2,
                segment_sample_count - support_count,
            ),
        )
        support_stop = support_start + support_count
        absolute_start = segment_start + support_start
        absolute_stop = segment_start + support_stop

        self.clear_storage()
        try:
            self._replace_data(
                [
                    float(value)
                    for value in independent_values[absolute_start:absolute_stop]
                ],
                [
                    dependent_values[index]
                    for index in range(absolute_start, absolute_stop)
                ],
            )
            interpolated = self.interpolate(query_value)
            if interpolated is None:
                return None
            result = np.asarray(interpolated, dtype=float)
            if result.shape != (self.dependent_dimension,) or not np.all(
                np.isfinite(result)
            ):
                raise ValueError("interpolator returned an invalid dependent vector")
            return result.copy()
        finally:
            self.clear_storage()
