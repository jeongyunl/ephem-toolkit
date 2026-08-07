from __future__ import annotations

import numpy as np
import tudatpy.astro.element_conversion as element_conversion
from tudatpy.interface import spice

import common.spice_utils as spice_utils

_did_load_spice_kernels: bool = False
"""Whether the required SPICE kernels have already been loaded."""

_has_compute_state_rotation_matrix_between_frames: bool = hasattr(
    spice, "compute_state_rotation_matrix_between_frames"
)


def teme_to_j2000(epoch_tdb_s: float, teme_state: np.ndarray) -> np.ndarray:
    """Convert a TEME Cartesian state to the J2000 frame.

    Parameters
    ----------
    epoch_tdb_s : float
        TDB seconds since the J2000 epoch, used to evaluate the rotation.
    teme_state : np.ndarray
        Six-component TEME state vector. The first three components are
        position and the last three are velocity.

    Returns
    -------
    np.ndarray
        Six-component vector in J2000 coordinates.

    Notes
    -----
    Position and velocity are each multiplied by the epoch-dependent TEME
    rotation. This helper does not include the rotation-matrix derivative
    term required for a full time-dependent frame state transformation.
    """
    j2000_state: np.ndarray = np.zeros(6, dtype=float)
    rotation_to_j2000: np.ndarray = element_conversion.teme_to_j2000(epoch_tdb_s)
    j2000_state[0:3] = teme_state[0:3] @ rotation_to_j2000
    j2000_state[3:6] = teme_state[3:6] @ rotation_to_j2000
    return j2000_state


def j2000_to_teme(epoch_tdb_s: float, j2000_state: np.ndarray) -> np.ndarray:
    """Convert a J2000 Cartesian state to the TEME frame.

    Parameters
    ----------
    epoch_tdb_s : float
        TDB seconds since the J2000 epoch, used to evaluate the rotation.
    j2000_state : np.ndarray
        Six-component J2000 state vector. The first three components are
        position and the last three are velocity.

    Returns
    -------
    np.ndarray
        Six-component vector in TEME coordinates.

    Notes
    -----
    Position and velocity are each multiplied by the transpose of the
    epoch-dependent TEME-to-J2000 rotation. This helper does not include the
    rotation-matrix derivative term required for a full time-dependent frame
    state transformation.
    """
    teme_state: np.ndarray = np.zeros(6, dtype=float)
    rotation_to_teme: np.ndarray = np.transpose(
        element_conversion.teme_to_j2000(epoch_tdb_s)
    )
    teme_state[0:3] = j2000_state[0:3] @ rotation_to_teme
    teme_state[3:6] = j2000_state[3:6] @ rotation_to_teme
    return teme_state


def spice_convert_frame(
    base_frame: str,
    target_frame: str,
    epoch_tdb_s: float,
    input_state_m: np.ndarray,
) -> np.ndarray:
    """Convert a state vector from one SPICE frame to another.

    Uses SPICE rotation matrices and their time derivatives to build a
    6-by-6 state conversion matrix that correctly transforms both position
    and velocity, accounting for the rotating-frame transport term.

    Parameters
    ----------
    base_frame : str
        Name of the source SPICE frame (e.g. ``"J2000"``).
    target_frame : str
        Name of the destination SPICE frame (e.g. ``"ITRF93"``).
    epoch_tdb_s : float
        Epoch in ephemeris time (TDB seconds since J2000).
    input_state_m : np.ndarray
        State vector ``[x, y, z, vx, vy, vz]`` (6,) in metres and m/s in
        *base_frame*.

    Returns
    -------
    np.ndarray
        6-element state vector ``[x, y, z, vx, vy, vz]`` in metres and m/s
        in *target_frame*.
    """

    global _did_load_spice_kernels

    if not _did_load_spice_kernels:
        spice_utils.load_kernel("naif0012.tls")  # Leap seconds kernel file
        spice_utils.load_kernel(
            "earth_200101_990825_predict.bpc"
        )  # Earth rotation prediction (covers Jan 2001 to Aug 2099)
        _did_load_spice_kernels = True

    if _has_compute_state_rotation_matrix_between_frames:
        state_conversion_matrix: np.ndarray = np.asarray(
            spice.compute_state_rotation_matrix_between_frames(
                base_frame, target_frame, epoch_tdb_s
            )
        )
    else:
        rotation_matrix: np.ndarray = spice.compute_rotation_matrix_between_frames(
            base_frame, target_frame, epoch_tdb_s
        )
        rotation_matrix_derivative: np.ndarray = (
            spice.compute_rotation_matrix_derivative_between_frames(
                base_frame, target_frame, epoch_tdb_s
            )
        )

        state_conversion_matrix = np.zeros((6, 6))
        state_conversion_matrix[0:3, 0:3] = rotation_matrix
        state_conversion_matrix[3:6, 0:3] = rotation_matrix_derivative
        state_conversion_matrix[3:6, 3:6] = rotation_matrix

    return state_conversion_matrix @ np.asarray(input_state_m)
