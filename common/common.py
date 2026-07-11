"""Common utilities shared across frame-conversion and propagation scripts.

Provides a SPICE kernel path resolver (:func:`get_spice_kernel_path`),
CCSDS keyword-value parsing (:func:`parse_key_value_line`),
an RTN frame transformation (:func:`transform_to_rtn`), and angle
utilities (:func:`wrap_angle_rad`, :func:`unwrap_angles_rad`,
:func:`circular_mean_angle_rad`, :func:`angle_difference_rad`,
:func:`circular_blend_angle_rad`).

Time-related functions (time conversion, ISO 8601 parsing, duration
parsing) live in :mod:`common.time_utils`.

References:
    ISO 8601 "Date and time representations".
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np

# ===================================================================
# Module-level state
# ===================================================================

_SPICE_CACHE_FILE: Path = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "tudatpy-utils"
    / "spice_kernel_path"
)
"""XDG cache file path for resolved SPICE kernel directory."""


# ===================================================================
# SPICE kernel path resolution
# ===================================================================


def get_spice_kernel_path() -> str:
    """Return the Tudatpy SPICE kernel path using an XDG-style cache file.

    Returns
    -------
    str
        Path to the SPICE kernel directory.
    """
    try:
        cached_path: str = _SPICE_CACHE_FILE.read_text(encoding="utf-8").strip()
        if cached_path and Path(cached_path).is_dir():
            return cached_path
    except OSError:
        pass

    from tudatpy import data

    resolved_path: str = data.get_spice_kernel_path()

    try:
        _SPICE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SPICE_CACHE_FILE.write_text(resolved_path, encoding="utf-8")
    except OSError:
        # Cache writes are best effort; continue with the resolved path.
        pass

    return resolved_path


# ===================================================================
# CCSDS keyword-value parsing
# ===================================================================


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    """Return (key, value) from ``KEY = VALUE`` lines, or *None*.

    This is a shared utility used by OEM and OMM parsers for reading
    CCSDS keyword-value formatted files.

    Parameters
    ----------
    line : str
        A single line of text to parse.

    Returns
    -------
    tuple[str, str] | None
        A ``(key, value)`` tuple with whitespace stripped from both parts,
        or ``None`` if the line does not contain an ``=`` character.

    Examples
    --------
    >>> parse_key_value_line("OBJECT_NAME = ISS")
    ('OBJECT_NAME', 'ISS')
    >>> parse_key_value_line("some line without equals") is None
    True
    """
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    return key.strip(), value.strip()


# ===================================================================
# RTN frame transformation
# ===================================================================


def transform_to_rtn(
    state: np.ndarray, reference_state: np.ndarray | None = None
) -> np.ndarray:
    """Calculate relative position and velocity in the RTN frame.

    Computes the relative state vector(s) between objects and transforms to the RTN
    (Radial-Transverse-Normal) frame of the reference object using 6-element ECI
    state vectors [x, y, z, vx, vy, vz].

    Supports both single and batch processing of state vectors.

    Parameters
    ----------
    state : np.ndarray
        Target object state vector(s) [x, y, z, vx, vy, vz].
        - Shape (6,): Single state vector
        - Shape (N, 6): Batch of N state vectors
    reference_state : np.ndarray | None
        Reference object state vector for RTN frame definition.
        - Shape (6,): Single reference state (used for all targets if batch)
        - Shape (N, 6): Batch of N reference states (one per target)
        Defaults to [0, 0, 0, 0, 0, 0] if None.

    Returns
    -------
    np.ndarray
        Relative state vector(s) in RTN coordinates [r, t, n, vr, vt, vn].
        - Shape (6,): If input is single state vector
        - Shape (N, 6): If input is batch of N state vectors
    """
    state_arr: np.ndarray = np.asarray(state, dtype=float)

    # Determine if input is single or batch
    if state_arr.ndim == 1:
        if state_arr.shape != (6,):
            raise ValueError(
                f"State vector must have shape (6,), got {state_arr.shape}"
            )
        state_arr = state_arr.reshape(1, 6)
        single_input: bool = True
    elif state_arr.ndim == 2:
        if state_arr.shape[1] != 6:
            raise ValueError(
                f"State vectors must have shape (N, 6), got {state_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(f"State vector must be 1D or 2D array, got {state_arr.ndim}D")

    # Handle reference state
    if reference_state is None:
        reference_state_arr: np.ndarray = np.zeros((state_arr.shape[0], 6), dtype=float)
    else:
        reference_state_arr = np.asarray(reference_state, dtype=float)
        if reference_state_arr.ndim == 1:
            if reference_state_arr.shape != (6,):
                raise ValueError(
                    f"Reference state must have shape (6,), got {reference_state_arr.shape}"
                )
            # Broadcast single reference state to all targets
            reference_state_arr = np.tile(reference_state_arr, (state_arr.shape[0], 1))
        elif reference_state_arr.ndim == 2:
            if reference_state_arr.shape[1] != 6:
                raise ValueError(
                    f"Reference states must have shape (N, 6), got {reference_state_arr.shape}"
                )
            if reference_state_arr.shape[0] != state_arr.shape[0]:
                raise ValueError(
                    f"Number of reference states ({reference_state_arr.shape[0]}) "
                    f"must match number of target states ({state_arr.shape[0]})"
                )
        else:
            raise ValueError(
                f"Reference state must be 1D or 2D array, got {reference_state_arr.ndim}D"
            )

    # 1. Extract positions and velocities: shape (N, 3)
    reference_positions: np.ndarray = reference_state_arr[:, 0:3]
    reference_velocities: np.ndarray = reference_state_arr[:, 3:6]
    target_positions: np.ndarray = state_arr[:, 0:3]
    target_velocities: np.ndarray = state_arr[:, 3:6]

    # 2. Compute inertial differences: shape (N, 3)
    inertial_positions: np.ndarray = target_positions - reference_positions
    inertial_velocities: np.ndarray = target_velocities - reference_velocities

    # 3. Compute RTN unit basis vectors
    # Radial unit vector: shape (N, 3)
    reference_position_magnitudes: np.ndarray = np.linalg.norm(
        reference_positions, axis=1
    )  # shape (N,)
    radial_unit_vectors: np.ndarray = np.zeros_like(reference_positions)
    np.divide(
        reference_positions,
        reference_position_magnitudes[:, np.newaxis],
        out=radial_unit_vectors,
        where=reference_position_magnitudes[:, np.newaxis] != 0.0,
    )

    # Normal unit vector (from angular momentum): shape (N, 3)
    angular_momentum_vectors: np.ndarray = np.cross(
        reference_positions, reference_velocities
    )  # shape (N, 3)
    angular_momentum_magnitudes: np.ndarray = np.linalg.norm(
        angular_momentum_vectors, axis=1
    )  # shape (N,)
    normal_unit_vectors: np.ndarray = np.zeros_like(angular_momentum_vectors)
    valid_normals: np.ndarray = angular_momentum_magnitudes > 0.0
    np.divide(
        angular_momentum_vectors,
        angular_momentum_magnitudes[:, np.newaxis],
        out=normal_unit_vectors,
        where=valid_normals[:, np.newaxis],
    )

    # Transverse unit vector: shape (N, 3)
    transverse_unit_vectors: np.ndarray = np.cross(
        normal_unit_vectors, radial_unit_vectors
    )

    # 4. Assemble RTN transformation matrices: shape (N, 3, 3)
    # Each row of the matrix is a basis vector
    rtn_transformation_matrices: np.ndarray = np.stack(
        [radial_unit_vectors, transverse_unit_vectors, normal_unit_vectors], axis=1
    )

    # 5. Compute relative position vector in RTN: shape (N, 3)
    # For each orbit i: rtn_pos[i] = rtn_matrix[i] @ inertial_pos[i]
    rtn_positions: np.ndarray = np.einsum(
        "nij,nj->ni", rtn_transformation_matrices, inertial_positions
    )

    # 6. Compute relative velocity vector in RTN (Transport Theorem): shape (N, 3)
    angular_velocity_z: np.ndarray = np.zeros(state_arr.shape[0])
    np.divide(
        angular_momentum_magnitudes,
        reference_position_magnitudes**2,
        out=angular_velocity_z,
        where=reference_position_magnitudes > 0.0,
    )  # shape (N,)
    angular_velocity_rtn: np.ndarray = np.column_stack(
        [np.zeros(state_arr.shape[0]), np.zeros(state_arr.shape[0]), angular_velocity_z]
    )  # shape (N, 3)

    rtn_velocities_rotational: np.ndarray = np.einsum(
        "nij,nj->ni", rtn_transformation_matrices, inertial_velocities
    )  # shape (N, 3)
    rtn_velocities: np.ndarray = rtn_velocities_rotational - np.cross(
        angular_velocity_rtn, rtn_positions
    )  # shape (N, 3)

    # 7. Package back into 6-element relative state vectors: shape (N, 6)
    result: np.ndarray = np.column_stack([rtn_positions, rtn_velocities])

    # Return single vector if input was single
    return result[0] if single_input else result


# ===================================================================
# Angle utilities
# ===================================================================


def wrap_angle_rad(angle: float) -> float:
    """Wrap angle to [0, 2π) range.

    Parameters
    ----------
    angle : float
        Angle in radians.

    Returns
    -------
    float
        Wrapped angle in [0, 2π).
    """
    wrapped: float = math.fmod(angle, 2.0 * math.pi)
    if wrapped < 0.0:
        wrapped += 2.0 * math.pi
    return wrapped


def unwrap_angles_rad(angles: list[float]) -> list[float]:
    """Unwrap angle sequence to remove 2π discontinuities.

    Parameters
    ----------
    angles : list[float]
        Sequence of angles in radians.

    Returns
    -------
    list[float]
        Unwrapped angle sequence.
    """
    if not angles:
        return []

    unwrapped: list[float] = [angles[0]]
    offset: float = 0.0
    previous: float = angles[0]

    for angle in angles[1:]:
        delta: float = angle - previous
        if delta > math.pi:
            offset -= 2.0 * math.pi
        elif delta < -math.pi:
            offset += 2.0 * math.pi

        unwrapped.append(angle + offset)
        previous = angle

    return unwrapped


def circular_mean_angle_rad(angles: list[float]) -> float:
    """Return circular mean angle in [0, 2π).

    Parameters
    ----------
    angles : list[float]
        Sequence of angles in radians.

    Returns
    -------
    float
        Circular mean angle in [0, 2π).
    """
    if not angles:
        return 0.0

    sin_sum: float = sum(math.sin(angle) for angle in angles)
    cos_sum: float = sum(math.cos(angle) for angle in angles)
    if abs(sin_sum) < 1e-15 and abs(cos_sum) < 1e-15:
        return wrap_angle_rad(angles[0])

    return wrap_angle_rad(math.atan2(sin_sum, cos_sum))


def angle_difference_rad(target: float, reference: float) -> float:
    """Return signed wrapped angle difference target-reference in [-π, π].

    Parameters
    ----------
    target : float
        Target angle in radians.
    reference : float
        Reference angle in radians.

    Returns
    -------
    float
        Angle difference in [-π, π].
    """
    delta: float = wrap_angle_rad(target - reference)
    if delta > math.pi:
        delta -= 2.0 * math.pi
    return delta


def circular_blend_angle_rad(
    primary_angle: float, correction_angle: float, correction_weight: float
) -> float:
    """Blend angles along the shortest arc.

    Parameters
    ----------
    primary_angle : float
        Primary angle in radians.
    correction_angle : float
        Correction angle in radians.
    correction_weight : float
        Weight for correction angle (0 to 1).

    Returns
    -------
    float
        Blended angle in radians.
    """
    return wrap_angle_rad(
        primary_angle
        + correction_weight * angle_difference_rad(correction_angle, primary_angle)
    )
