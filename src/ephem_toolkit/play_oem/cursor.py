"""Direction-independent state lookup for OEM playback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

import numpy as np

from ephem_toolkit.core import wgs
from ephem_toolkit.core.interpolator import factory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.core.interpolator.interpolator import Interpolator

KILOMETERS_PER_METER = 0.001


class CursorStatus(str, Enum):
    """Resolution status for a cursor time."""

    EXACT_SAMPLE = "exact_sample"
    INTERPOLATED = "interpolated"
    OUT_OF_RANGE = "out_of_range"
    UNAVAILABLE = "unavailable"
    GAP = "gap"


@dataclass(frozen=True)
class CursorState:
    """State and derived values resolved at one OEM timeline time."""

    t: float
    state_m: np.ndarray | None
    r_km: np.ndarray | None
    v_kms: np.ndarray | None
    speed: float | None
    altitude: float | None
    distance: float | None
    status: CursorStatus
    segment_id: int | None = None


class OemCursor:
    """Resolve a state at any time without relying on query direction."""

    def __init__(
        self,
        timestamps_s: Sequence[float],
        states_m: Sequence[np.ndarray],
        *,
        interpolation: str | None = None,
        interpolation_degree: int | None = None,
        segment_ids: Sequence[int] | None = None,
    ) -> None:
        """Prepare ordered OEM states and optional OEM interpolation metadata."""
        self._timestamps_s = np.asarray(timestamps_s, dtype=float)
        self._states_m = np.asarray(states_m, dtype=float)
        if self._timestamps_s.ndim != 1 or self._timestamps_s.size == 0:
            raise ValueError(
                "timestamps_s must be a non-empty one-dimensional sequence"
            )
        if self._states_m.shape != (self._timestamps_s.size, 6):
            raise ValueError("states_m must have shape (len(timestamps_s), 6)")
        if not np.all(np.isfinite(self._timestamps_s)):
            raise ValueError("timestamps_s must contain only finite values")
        if not np.all(np.isfinite(self._states_m)):
            raise ValueError("states_m must contain only finite values")
        if np.any(np.diff(self._timestamps_s) <= 0.0):
            raise ValueError("timestamps_s must be strictly increasing")

        self._timestamps_s = self._timestamps_s.copy()
        self._states_m = self._states_m.copy()
        self._segment_ids = np.asarray(
            segment_ids if segment_ids is not None else np.zeros(len(self._timestamps_s)),
            dtype=int,
        )
        if self._segment_ids.shape != self._timestamps_s.shape:
            raise ValueError("segment_ids must have shape (len(timestamps_s),)")
        if np.any(np.diff(self._segment_ids) < 0):
            raise ValueError("segment_ids must be non-decreasing")
        self._interpolators = self._create_interpolators(
            interpolation, interpolation_degree
        )

    def set_interpolation(
        self, interpolation: str | None, interpolation_degree: int | None
    ) -> None:
        """Replace the interpolation strategy used for subsequent lookups."""
        self._interpolators = self._create_interpolators(
            interpolation, interpolation_degree
        )

    @property
    def t_start(self) -> float:
        return float(self._timestamps_s[0])

    @property
    def t_end(self) -> float:
        return float(self._timestamps_s[-1])

    def lookup(self, t: float) -> CursorState:
        """Return an exact, interpolated, or unavailable state at ``t``."""
        query_time = self._validate_query_time(t)
        if query_time < self.t_start or query_time > self.t_end:
            return self._unavailable(query_time, CursorStatus.OUT_OF_RANGE)

        sample_index = int(np.searchsorted(self._timestamps_s, query_time))
        if (
            sample_index < self._timestamps_s.size
            and self._timestamps_s[sample_index] == query_time
        ):
            state_m = self._states_m[sample_index].copy()
            status = CursorStatus.EXACT_SAMPLE
            segment_id = int(self._segment_ids[sample_index])
        else:
            lower_index = sample_index - 1
            segment_id = int(self._segment_ids[lower_index])
            if segment_id != self._segment_ids[sample_index]:
                return self._unavailable(query_time, CursorStatus.GAP)
            state_m = self._interpolate_state(query_time, sample_index, segment_id)
            if state_m is None:
                return self._unavailable(query_time, CursorStatus.UNAVAILABLE)
            status = CursorStatus.INTERPOLATED

        position_km = state_m[:3] * KILOMETERS_PER_METER
        velocity_km_s = state_m[3:] * KILOMETERS_PER_METER
        return CursorState(
            t=query_time,
            state_m=state_m,
            r_km=position_km,
            v_kms=velocity_km_s,
            speed=float(np.linalg.norm(velocity_km_s)),
            altitude=float(wgs.ecef_to_lla(state_m[:3])[2] * KILOMETERS_PER_METER),
            distance=float(np.linalg.norm(position_km)),
            status=status,
            segment_id=segment_id,
        )

    def _interpolate_state(
        self, query_time: float, upper_index: int, segment_id: int
    ) -> np.ndarray | None:
        if self._timestamps_s.size < 2:
            return None

        interpolator = self._interpolators.get(segment_id)
        if interpolator is not None:
            state = interpolator.interpolate(query_time)
            if state is None:
                return None
            state_array = np.asarray(state, dtype=float)
            if state_array.shape != (6,) or not np.all(np.isfinite(state_array)):
                raise ValueError("interpolator returned an invalid Cartesian state")
            return state_array.copy()

        lower_index = upper_index - 1
        lower_time = self._timestamps_s[lower_index]
        upper_time = self._timestamps_s[upper_index]
        fraction = (query_time - lower_time) / (upper_time - lower_time)
        return self._states_m[lower_index] + fraction * (
            self._states_m[upper_index] - self._states_m[lower_index]
        )

    def _create_interpolators(
        self, interpolation: str | None, interpolation_degree: int | None
    ) -> dict[int, Interpolator]:
        if interpolation_degree is not None and (
            isinstance(interpolation_degree, bool)
            or not isinstance(interpolation_degree, int)
            or interpolation_degree < 0
        ):
            raise ValueError("interpolation_degree must be a non-negative integer")

        interpolation_name = (interpolation or "").strip().lower()
        if not interpolation_name or interpolation_name == "linear":
            return {}
        try:
            interpolation_type = InterpolationType(interpolation_name)
        except ValueError as error:
            raise ValueError(
                f"Unsupported OEM interpolation type: {interpolation!r}"
            ) from error

        degree = interpolation_degree or None
        spec = InterpolationSpec(interpolation_type, degree=degree)
        interpolators: dict[int, Interpolator] = {}
        for segment_id in np.unique(self._segment_ids):
            mask = self._segment_ids == segment_id
            if np.count_nonzero(mask) < 2:
                continue
            interpolators[int(segment_id)] = factory.InterpolatorFactory.create(
                spec=spec,
                dimension=6,
                is_cartesian_state=True,
                data=list(
                    zip(self._timestamps_s[mask].tolist(), self._states_m[mask])
                ),
            )
        return interpolators

    def _unavailable(self, t: float, status: CursorStatus) -> CursorState:
        return CursorState(
            t=t,
            state_m=None,
            r_km=None,
            v_kms=None,
            speed=None,
            altitude=None,
            distance=None,
            status=status,
        )

    @staticmethod
    def _validate_query_time(t: float) -> float:
        if isinstance(t, bool):
            raise ValueError("query time must be a finite number")
        try:
            query_time = float(t)
        except (TypeError, ValueError) as error:
            raise ValueError("query time must be a finite number") from error
        if not math.isfinite(query_time):
            raise ValueError("query time must be a finite number")
        return query_time
