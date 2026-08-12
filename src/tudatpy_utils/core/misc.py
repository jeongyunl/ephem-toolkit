"""Common utilities shared across frame-conversion and propagation scripts.

CCSDS keyword-value parsing (:func:`parse_key_value_line`),
an RTN frame transformation (:func:`transform_to_rtn`), and angle
utilities (:func:`wrap_angle_rad`, :func:`unwrap_angles_rad`,
:func:`circular_mean_angle_rad`, :func:`angle_difference_rad`,
:func:`circular_blend_angle_rad`).

Time-related functions (time conversion, ISO 8601 parsing, duration
parsing) live in :mod:`core.time_utils`.

References:
    ISO 8601 "Date and time representations".
    https://en.wikipedia.org/wiki/Local_tangent_plane_coordinates (RTN frame)
"""

from __future__ import annotations

import math

import numpy as np

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

    References
    ----------
    https://public.ccsds.org/Pubs/502x0b3e1.pdf (CCSDS 502.0-B-3 OEM)
    https://public.ccsds.org/Pubs/502x0b2c1e2.pdf (CCSDS 502.0-B-2 OMM)
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

    References
    ----------
    https://en.wikipedia.org/wiki/Local_tangent_plane_coordinates
    https://en.wikipedia.org/wiki/Orbital_coordinate_systems#Radial-Transverse-Normal_(RTN)
    """
    state_array: np.ndarray = np.asarray(state, dtype=float)

    # Determine if input is single or batch
    if state_array.ndim == 1:
        if state_array.shape != (6,):
            raise ValueError(
                f"State vector must have shape (6,), got {state_array.shape}"
            )
        state_array = state_array.reshape(1, 6)
        single_input: bool = True
    elif state_array.ndim == 2:
        if state_array.shape[1] != 6:
            raise ValueError(
                f"State vectors must have shape (N, 6), got {state_array.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"State vector must be 1D or 2D array, got {state_array.ndim}D"
        )

    # Handle reference state
    if reference_state is None:
        reference_state_array: np.ndarray = np.zeros(
            (state_array.shape[0], 6), dtype=float
        )
    else:
        reference_state_array = np.asarray(reference_state, dtype=float)
        if reference_state_array.ndim == 1:
            if reference_state_array.shape != (6,):
                raise ValueError(
                    "Reference state must have shape (6,), "
                    f"got {reference_state_array.shape}"
                )
            # Broadcast single reference state to all targets
            reference_state_array = np.tile(
                reference_state_array, (state_array.shape[0], 1)
            )
        elif reference_state_array.ndim == 2:
            if reference_state_array.shape[1] != 6:
                raise ValueError(
                    "Reference states must have shape (N, 6), "
                    f"got {reference_state_array.shape}"
                )
            if reference_state_array.shape[0] != state_array.shape[0]:
                raise ValueError(
                    f"Number of reference states ({reference_state_array.shape[0]}) "
                    f"must match number of target states ({state_array.shape[0]})"
                )
        else:
            raise ValueError(
                "Reference state must be 1D or 2D array, "
                f"got {reference_state_array.ndim}D"
            )

    # 1. Extract positions and velocities: shape (N, 3)
    reference_positions: np.ndarray = reference_state_array[:, 0:3]
    reference_velocities: np.ndarray = reference_state_array[:, 3:6]
    target_positions: np.ndarray = state_array[:, 0:3]
    target_velocities: np.ndarray = state_array[:, 3:6]

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
    # https://en.wikipedia.org/wiki/Specific_angular_momentum
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
    # For each orbit i: rtn_positions[i] = rtn_matrix[i] @ inertial_positions[i]
    rtn_positions: np.ndarray = np.einsum(
        "nij,nj->ni", rtn_transformation_matrices, inertial_positions
    )

    # 6. Compute relative velocity vector in RTN (Transport Theorem): shape (N, 3)
    # https://en.wikipedia.org/wiki/Rotating_reference_frame#Time_derivatives_in_the_two_frames
    angular_velocity_rad_per_s: np.ndarray = np.zeros(state_array.shape[0])
    np.divide(
        angular_momentum_magnitudes,
        reference_position_magnitudes**2,
        out=angular_velocity_rad_per_s,
        where=reference_position_magnitudes > 0.0,
    )  # shape (N,)
    angular_velocity_rtn: np.ndarray = np.column_stack(
        [
            np.zeros(state_array.shape[0]),
            np.zeros(state_array.shape[0]),
            angular_velocity_rad_per_s,
        ]
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

    References
    ----------
    https://en.wikipedia.org/wiki/Wrapping_(graphics)#Wrapping_of_angles
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

    References
    ----------
    https://en.wikipedia.org/wiki/Unwrapped_phase
    https://numpy.org/doc/stable/reference/generated/numpy.unwrap.html
    """
    if not angles:
        return []

    unwrapped: list[float] = [angles[0]]
    offset: float = 0.0
    previous: float = angles[0]

    for angle in angles[1:]:
        difference_rad: float = angle - previous
        if difference_rad > math.pi:
            offset -= 2.0 * math.pi
        elif difference_rad < -math.pi:
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

    References
    ----------
    https://en.wikipedia.org/wiki/Circular_mean
    https://en.wikipedia.org/wiki/Mean_of_circular_quantities
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

    References
    ----------
    https://en.wikipedia.org/wiki/Mean_of_circular_quantities#Computation
    """
    difference_rad: float = wrap_angle_rad(target - reference)
    if difference_rad > math.pi:
        difference_rad -= 2.0 * math.pi
    return difference_rad


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

    References
    ----------
    https://en.wikipedia.org/wiki/Slerp#Quaternion_Slerp
    https://en.wikipedia.org/wiki/Linear_interpolation#Interpolation_of_angles
    """
    return wrap_angle_rad(
        primary_angle
        + correction_weight * angle_difference_rad(correction_angle, primary_angle)
    )


def rotation_matrix_to_euler_angles(rotation_matrix: np.ndarray) -> np.ndarray:
    """Convert a rotation matrix to ZYX Euler angles (intrinsic rotations).

    Parameters
    ----------
    rotation_matrix : numpy.ndarray
        Three-by-three rotation matrix.

    Returns
    -------
    numpy.ndarray
        Euler angles [yaw, pitch, roll] in degrees (ZYX convention).

    References
    ----------
    https://en.wikipedia.org/wiki/Euler_angles#Rotation_matrix
    https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles
    """
    # Extract Euler angles from rotation matrix using ZYX convention
    # R = Rz(yaw) * Ry(pitch) * Rx(roll)

    # Check for gimbal lock
    # https://en.wikipedia.org/wiki/Gimbal_lock
    sin_pitch: float = -rotation_matrix[2, 0]

    if abs(sin_pitch) >= 1.0:
        # Gimbal lock case
        pitch_rad: float = np.copysign(np.pi / 2.0, sin_pitch)
        if sin_pitch < 0:  # pitch = -90 degrees
            yaw_rad: float = np.arctan2(rotation_matrix[0, 1], rotation_matrix[1, 1])
            roll_rad: float = 0.0
        else:  # pitch = +90 degrees
            yaw_rad = np.arctan2(-rotation_matrix[0, 1], rotation_matrix[1, 1])
            roll_rad = 0.0
    else:
        # Normal case
        pitch_rad = np.arcsin(-rotation_matrix[2, 0])
        yaw_rad = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        roll_rad = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])

    # Convert to degrees for output
    euler_angles_deg: np.ndarray = np.degrees([yaw_rad, pitch_rad, roll_rad])
    return euler_angles_deg
