"""Data structures for OEM comparison operations."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

import ephem_toolkit.core.interpolator as interpolator
import ephem_toolkit.core.time_utils as time_utils

from .types import StatePair
from .debug import debug_print, debug_print_time_range


@dataclass
class TransformationStageInput:
    """Data prepared by the pipeline for fitting one transformation stage."""

    state_pairs: list[StatePair]
    """Reference/comparison state pairs prepared for fitting."""

    reference_interpolator: interpolator.Interpolator
    """Interpolator for reference states."""

    comparison_interpolator: interpolator.Interpolator
    """Interpolator for comparison states."""

    def resolve_state_pairs(self) -> list[StatePair]:
        """Resolve fitting pairs using the configured interpolators.

        Returns
        -------
        list[StatePair]
            State pairs successfully resolved at comparable epochs.
        """
        from .comparison import resolve_state_pair

        debug_print(
            f"resolve_state_pairs: input {len(self.state_pairs)} pairs",
            "data_structures",
        )
        if self.state_pairs:
            first_ref = self.state_pairs[0][0][0]
            last_ref = self.state_pairs[-1][0][0]
            first_cmp = self.state_pairs[0][1][0]
            last_cmp = self.state_pairs[-1][1][0]
            debug_print_time_range(
                "resolve_state_pairs: input ref data time range", first_ref, last_ref
            )
            debug_print_time_range(
                "resolve_state_pairs: input cmp data time range", first_cmp, last_cmp
            )
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
        debug_print(
            f"resolve_state_pairs: resolved {len(resolved_state_pairs)} of "
            f"{len(self.state_pairs)} pairs",
            "data_structures",
        )
        if resolved_state_pairs:
            first_resolved_ref = resolved_state_pairs[0][0][0]
            last_resolved_ref = resolved_state_pairs[-1][0][0]
            first_resolved_cmp = resolved_state_pairs[0][1][0]
            last_resolved_cmp = resolved_state_pairs[-1][1][0]
            debug_print_time_range(
                "resolve_state_pairs: resolved ref data time range",
                first_resolved_ref,
                last_resolved_ref,
            )
            debug_print_time_range(
                "resolve_state_pairs: resolved cmp data time range",
                first_resolved_cmp,
                last_resolved_cmp,
            )
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
