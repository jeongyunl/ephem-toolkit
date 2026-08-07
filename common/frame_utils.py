from __future__ import annotations

import numpy as np
import tudatpy.astro.element_conversion as element_conversion


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
