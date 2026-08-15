"""Data structures for OEM comparison operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

import ephem_toolkit.core.interpolator as interpolator

from .types import StatePair


@dataclass
class TransformationStageInput:
    """Data prepared by the pipeline for fitting one transformation stage."""

    state_pairs: list[StatePair]
    """Reference/comparison state pairs prepared for fitting."""

    reference_interpolator: interpolator.Interpolator | None
    """Optional interpolator for reference states."""

    comparison_interpolator: interpolator.Interpolator | None
    """Optional interpolator for comparison states."""

    def resolve_state_pairs(self) -> list[StatePair]:
        """Resolve fitting pairs using the configured interpolators.

        Returns
        -------
        list[StatePair]
            State pairs successfully resolved at comparable epochs.
        """
        from .comparison import resolve_state_pair

        resolved_state_pairs: list[StatePair] = []
        for reference_state, comparison_state in self.state_pairs:
            try:
                resolved_state_pairs.append(
                    resolve_state_pair(
                        reference_state,
                        comparison_state,
                        self.reference_interpolator,
                        self.comparison_interpolator,
                    )
                )
            except ValueError:
                continue
        return resolved_state_pairs


@dataclass
class ComparisonResult:
    """Named results returned by :func:`compare_states`."""

    reference_epoch: datetime
    """Reference state epoch."""

    comparison_epoch: datetime
    """Comparison state epoch."""

    time_diff_s: float | None
    """Comparison epoch minus reference epoch, when no interpolation is used."""

    position_diff_km: np.ndarray
    """Comparison minus reference position (km)."""

    position_diff_magnitude_km: float
    """Magnitude of the position difference (km)."""

    velocity_diff_km_s: np.ndarray
    """Comparison minus reference velocity (km/s)."""

    velocity_diff_magnitude_km_s: float
    """Magnitude of the velocity difference (km/s)."""

    rtn_position_km: np.ndarray
    """Comparison minus reference position in the reference RTN frame (km)."""

    rtn_velocity_km_s: np.ndarray
    """Comparison minus reference velocity in the reference RTN frame (km/s)."""
