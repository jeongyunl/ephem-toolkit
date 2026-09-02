"""Core comparison functions for OEM state vectors."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

import numpy as np

from ephem_toolkit.core import misc
import ephem_toolkit.core.interpolator as interpolator
from ephem_toolkit.core.ccsds import oem
from ephem_toolkit.core import time_utils

from .data_structures import ComparisonResult
from .types import State, StatePair
from .debug import debug_print_time_range


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
        ``(timestamp, state_m)`` pairs where *timestamp* is TT seconds since J2000 and
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
    debug_print_time_range(
        f"read_states: {len(oem_data.states)} states, time range",
        oem_data.states[0][0],
        oem_data.states[-1][0],
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
    reference_interpolator: interpolator.Interpolator,
    comparison_interpolator: interpolator.Interpolator,
) -> StatePair:
    """Resolve one state pair to concrete vectors at comparable epochs.

    Both interpolators evaluate their respective histories so that the
    returned pair shares a common timestamp.

    Parameters
    ----------
    reference_oem : State
        Reference ``(timestamp, state_m)`` tuple from the OEM state history.
    comparison_oem : State
        Comparison ``(timestamp, state_m)`` tuple from the OEM state history.
    reference_interpolator : Interpolator
        Interpolator built from the reference OEM.  The reference state is
        evaluated at the comparison epoch.
    comparison_interpolator : Interpolator
        Interpolator built from the comparison OEM.  The comparison state is
        evaluated at the reference epoch.

    Returns
    -------
    StatePair
        Tuple of ``((timestamp, reference_state_m), (timestamp, comparison_state_m))``
        where both timestamps are identical.

    Raises
    ------
    ValueError
        If the target epoch is outside the interpolation range.
    """
    reference_timestamp: float = reference_oem[0]

    comparison_interpolated: np.ndarray | None = comparison_interpolator.interpolate(
        reference_timestamp
    )
    if comparison_interpolated is None:
        reference_epoch = time_utils.tt_s_to_datetime(reference_timestamp)
        raise ValueError(
            "Reference epoch "
            f"{time_utils.datetime_to_iso8601(reference_epoch)} is outside "
            "the comparison OEM interpolation range"
        )

    reference_interpolated: np.ndarray | None = reference_interpolator.interpolate(
        reference_timestamp
    )
    if reference_interpolated is None:
        epoch_dt = time_utils.tt_s_to_datetime(reference_timestamp)
        raise ValueError(
            "Comparison epoch "
            f"{time_utils.datetime_to_iso8601(epoch_dt)} is outside "
            "the reference OEM interpolation range"
        )

    return (
        (reference_timestamp, reference_interpolated),
        (reference_timestamp, comparison_interpolated),
    )


def compare_states(
    reference_oem: State,
    comparison_oem: State,
    reference_interpolator: interpolator.Interpolator,
    comparison_interpolator: interpolator.Interpolator,
    comparison_rotation_matrix: np.ndarray | None = None,
) -> ComparisonResult:
    """Compare two OEM-like states and return differences.

    Parameters
    ----------
    reference_oem : State
        Reference ``(timestamp, state_m)`` tuple from the OEM state history.
    comparison_oem : State
        Comparison ``(timestamp, state_m)`` tuple from the OEM state history.
    reference_interpolator : Interpolator
        Interpolator built from the reference OEM.  The reference state is
        evaluated at the comparison epoch.
    comparison_interpolator : Interpolator
        Interpolator built from the comparison OEM.  The comparison state is
        evaluated at the reference epoch.
    comparison_rotation_matrix : np.ndarray | None, optional
        Rotation applied to the comparison position and velocity before calculating
        differences.

    Returns
    -------
    ComparisonResult
        Comparison result containing epochs, position difference in km,
        and velocity difference in km/s.
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

    if comparison_rotation_matrix is not None:
        comparison_state_m = rotate_state(
            comparison_state_m, comparison_rotation_matrix
        )

    reference_epoch = time_utils.tt_s_to_datetime(reference_timestamp)
    comparison_epoch = time_utils.tt_s_to_datetime(comparison_timestamp)

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
        time_diff_s=None,
        position_diff_km=position_diff_km,
        position_diff_magnitude_km=position_diff_magnitude_km,
        velocity_diff_km_s=velocity_diff_km_s,
        velocity_diff_magnitude_km_s=velocity_diff_magnitude_km_s,
        rtn_position_km=rtn_position_km,
        rtn_velocity_km_s=rtn_velocity_km_s,
    )
