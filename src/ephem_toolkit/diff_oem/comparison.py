"""Core comparison functions for OEM state vectors."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import numpy as np

from ephem_toolkit.core import misc
import ephem_toolkit.core.interpolator as interpolator
from ephem_toolkit.core.ccsds import oem
from ephem_toolkit.core import time_utils

from .data_structures import ComparisonResult
from .types import State, StatePair

_debug: bool = False
"""Module-level debug flag, set by the CLI entry point."""


def set_debug(enabled: bool) -> None:
    """Enable or disable module-level debug logging.

    Parameters
    ----------
    enabled : bool
        Whether to enable debug output.
    """
    global _debug
    _debug = enabled


def _debug_print(message: str) -> None:
    """Print a debug message to stderr when debugging is enabled."""
    if _debug:
        print(f"[diff_oem.comparison] {message}", file=sys.stderr)


def read_states(source: TextIO | str | Path) -> list[tuple[float, np.ndarray]]:
    """Read all states from an OEM file or text stream.

    Comments and blank lines are skipped by :class:`oem.CcsdsOem`.

    Parameters
    ----------
    source : TextIO, str, or pathlib.Path
        Readable OEM stream or path to an OEM file containing state data.

    Returns
    -------
    list[tuple[float, np.ndarray]]
        ``(timestamp, state_m)`` pairs where *timestamp* is POSIX seconds and
        *state_m* is a six-element vector in meters and meters per second.

    Raises
    ------
    ValueError
        If file cannot be read or no valid state is found.
    """
    try:
        oem_data = oem.CcsdsOem.read(source)
    except OSError as error:
        raise ValueError(f"Could not read file '{source}': {error}") from error

    if not oem_data.states:
        raise ValueError(f"No valid OEM-like state found in '{source}'")
    _debug_print(
        f"read_states: {len(oem_data.states)} states, "
        f"time range "
        f"{time_utils.datetime_to_iso8601(datetime.fromtimestamp(oem_data.states[0][0], tz=timezone.utc))} .. "
        f"{time_utils.datetime_to_iso8601(datetime.fromtimestamp(oem_data.states[-1][0], tz=timezone.utc))}"
    )
    return oem_data.states


def rotate_state(state: np.ndarray, rotation_matrix: np.ndarray) -> np.ndarray:
    """Rotate position and velocity components of an SI state vector.

    Parameters
    ----------
    state : np.ndarray
        Six-element state vector ``[x, y, z, vx, vy, vz]`` in SI units (m, m/s).
    rotation_matrix : np.ndarray
        3x3 rotation matrix to apply to position and velocity components.

    Returns
    -------
    np.ndarray
        Rotated state vector with same shape and units as input.
    """
    rotated_state = state.copy()
    rotated_state[0:3] = rotation_matrix @ state[0:3]
    rotated_state[3:6] = rotation_matrix @ state[3:6]
    return rotated_state


def resolve_state_pair(
    reference_oem: State,
    comparison_oem: State,
    reference_interpolator: interpolator.Interpolator | None = None,
    comparison_interpolator: interpolator.Interpolator | None = None,
) -> StatePair:
    """Resolve one state pair to concrete vectors at comparable epochs.

    Parameters
    ----------
    reference_oem : State
        Reference ``(timestamp, state_m)`` tuple from the OEM state history.
    comparison_oem : State
        Comparison ``(timestamp, state_m)`` tuple from the OEM state history.
    reference_interpolator : Interpolator | None, optional
        Interpolator built from the reference OEM. When provided, the reference
        state is evaluated at the comparison epoch.
    comparison_interpolator : Interpolator | None, optional
        Interpolator built from the comparison OEM. When provided, the comparison
        state is evaluated at the reference epoch.

    Returns
    -------
    StatePair
        Tuple of ``((reference_timestamp, reference_state_m), (comparison_timestamp, comparison_state_m))``
        where timestamps are aligned based on interpolation settings.

    Raises
    ------
    ValueError
        If interpolation is requested but the target epoch is outside the interpolation range.
    """
    reference_timestamp: float
    reference_state_m: np.ndarray
    reference_timestamp, reference_state_m = reference_oem
    comparison_timestamp: float
    comparison_state_m: np.ndarray
    comparison_timestamp, comparison_state_m = comparison_oem

    if comparison_interpolator is not None:
        comparison_timestamp = reference_timestamp
        interpolated_state: np.ndarray | None = comparison_interpolator.interpolate(
            reference_timestamp
        )
        if interpolated_state is None:
            reference_epoch = datetime.fromtimestamp(
                reference_timestamp, tz=timezone.utc
            )
            raise ValueError(
                "Reference epoch "
                f"{time_utils.datetime_to_iso8601(reference_epoch)} is outside "
                "the comparison OEM interpolation range"
            )
        comparison_state_m = interpolated_state

    if reference_interpolator is not None:
        interpolation_timestamp = comparison_timestamp
        interpolated_state = reference_interpolator.interpolate(interpolation_timestamp)
        if interpolated_state is None:
            comparison_epoch = datetime.fromtimestamp(
                interpolation_timestamp, tz=timezone.utc
            )
            raise ValueError(
                "Comparison epoch "
                f"{time_utils.datetime_to_iso8601(comparison_epoch)} is outside "
                "the reference OEM interpolation range"
            )
        reference_timestamp = interpolation_timestamp
        reference_state_m = interpolated_state

    # _debug_print(
    #     f"resolve_state_pair: ref_epoch="
    #     f"{time_utils.datetime_to_iso8601(datetime.fromtimestamp(reference_timestamp, tz=timezone.utc))}, "
    #     f"cmp_epoch="
    #     f"{time_utils.datetime_to_iso8601(datetime.fromtimestamp(comparison_timestamp, tz=timezone.utc))}"
    # )

    return (
        (reference_timestamp, reference_state_m),
        (comparison_timestamp, comparison_state_m),
    )


def compare_states(
    reference_oem: State,
    comparison_oem: State,
    reference_interpolator: interpolator.Interpolator | None = None,
    comparison_interpolator: interpolator.Interpolator | None = None,
    comparison_rotation_matrix: np.ndarray | None = None,
) -> ComparisonResult:
    """Compare two OEM-like states and return differences.

    Parameters
    ----------
    reference_oem : State
        Reference ``(timestamp, state_m)`` tuple from the OEM state history.
    comparison_oem : State
        Comparison ``(timestamp, state_m)`` tuple from the OEM state history.
    reference_interpolator : Interpolator | None, optional
        Interpolator built from the reference OEM. When provided, the reference
        state is evaluated at the comparison epoch instead of using the supplied
        reference state's epoch and vector.
    comparison_interpolator : Interpolator | None, optional
        Interpolator built from the comparison OEM. When provided, the comparison
        state is evaluated at the reference epoch.
    comparison_rotation_matrix : np.ndarray | None, optional
        Rotation applied to the comparison position and velocity before calculating
        differences.

    Returns
    -------
    ComparisonResult
        Comparison result containing epochs, time difference in seconds,
        position difference in km, and velocity difference in km/s.
    """
    (reference_timestamp, reference_state_m), (
        comparison_timestamp,
        comparison_state_m,
    ) = resolve_state_pair(
        reference_oem,
        comparison_oem,
        reference_interpolator,
        comparison_interpolator,
    )

    # _debug_print(
    #     f"compare_states: ref_epoch="
    #     f"{time_utils.datetime_to_iso8601(datetime.fromtimestamp(reference_timestamp, tz=timezone.utc))}, "
    #     f"cmp_epoch="
    #     f"{time_utils.datetime_to_iso8601(datetime.fromtimestamp(comparison_timestamp, tz=timezone.utc))}, "
    #     f"has_rotation={'yes' if comparison_rotation_matrix is not None else 'no'}"
    # )

    if comparison_rotation_matrix is not None:
        comparison_state_m = rotate_state(
            comparison_state_m, comparison_rotation_matrix
        )

    reference_epoch = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
    comparison_epoch = datetime.fromtimestamp(comparison_timestamp, tz=timezone.utc)

    time_diff_s: float | None = None
    if reference_interpolator is None and comparison_interpolator is None:
        time_diff_s = (comparison_epoch - reference_epoch).total_seconds()

    position_diff_m: np.ndarray = comparison_state_m[0:3] - reference_state_m[0:3]
    position_diff_km: np.ndarray = position_diff_m / oem.KILOMETERS_TO_METERS
    position_diff_magnitude_km: float = float(np.linalg.norm(position_diff_km))

    velocity_diff_m_s: np.ndarray = comparison_state_m[3:6] - reference_state_m[3:6]
    velocity_diff_km_s: np.ndarray = velocity_diff_m_s / oem.KILOMETERS_TO_METERS
    velocity_diff_magnitude_km_s: float = float(np.linalg.norm(velocity_diff_km_s))

    rtn_state_m_s: np.ndarray = misc.transform_to_rtn(
        comparison_state_m, reference_state_m
    )
    rtn_position_km: np.ndarray = rtn_state_m_s[0:3] / oem.KILOMETERS_TO_METERS
    rtn_velocity_km_s: np.ndarray = rtn_state_m_s[3:6] / oem.KILOMETERS_TO_METERS

    return ComparisonResult(
        reference_epoch=reference_epoch,
        comparison_epoch=comparison_epoch,
        time_diff_s=time_diff_s,
        position_diff_km=position_diff_km,
        position_diff_magnitude_km=position_diff_magnitude_km,
        velocity_diff_km_s=velocity_diff_km_s,
        velocity_diff_magnitude_km_s=velocity_diff_magnitude_km_s,
        rtn_position_km=rtn_position_km,
        rtn_velocity_km_s=rtn_velocity_km_s,
    )
