"""Coordinate conversion utilities for LLA (Latitude-Longitude-Altitude) and ENU frames.

Provides functions for converting between ECEF (Earth-Centered Earth-Fixed) and
ENU (East-North-Up) coordinate systems, as well as geodetic coordinate transformations.

The ENU coordinate system is a local tangent plane coordinate system centered at a
reference point on the Earth's surface:
- East axis points to the local east
- North axis points to the local north
- Up axis points away from the Earth's center (perpendicular to the reference ellipsoid)

References:
    WGS-84 Earth Gravitational Model
    "Department of Defense World Geodetic System 1984"
"""

from __future__ import annotations

import math

import numpy as np

from .consts import EARTH_EQUATORIAL_RADIUS_M

# ===================================================================
# Constants
# ===================================================================

EARTH_FLATTENING: float = 1.0 / 298.257223563
"""Earth flattening factor (dimensionless), WGS-84."""

EARTH_ECCENTRICITY_SQUARED: float = 2.0 * EARTH_FLATTENING - EARTH_FLATTENING**2
"""Earth eccentricity squared (dimensionless), WGS-84."""


# ===================================================================
# ECEF to ENU conversion
# ===================================================================


def ecef_to_enu(
    ecef_position: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ECEF position to ENU coordinates relative to a reference point.

    Transforms a position vector from Earth-Centered Earth-Fixed (ECEF) coordinates
    to East-North-Up (ENU) coordinates relative to a reference point specified in
    geodetic coordinates (latitude, longitude, altitude).

    Parameters
    ----------
    ecef_position : np.ndarray
        Position vector in ECEF coordinates [x, y, z] in meters.
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all positions if batch)

    Returns
    -------
    np.ndarray
        Position vector(s) in ENU coordinates [east, north, up] in meters.
        - Shape (3,): If input is single position vector
        - Shape (N, 3): If input is batch of N position vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point at equator, prime meridian, sea level
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # Point 1000m east of reference
    >>> ecef_pos = np.array([6378136.3, 1000.0, 0.0])
    >>> enu_pos = ecef_to_enu(ecef_pos, ref_lla)
    """
    ecef_arr: np.ndarray = np.asarray(ecef_position, dtype=float)
    ref_lla_arr: np.ndarray = np.asarray(reference_lla, dtype=float)

    # Validate reference LLA
    if ref_lla_arr.shape != (3,):
        raise ValueError(f"Reference LLA must have shape (3,), got {ref_lla_arr.shape}")

    # Determine if input is single or batch
    if ecef_arr.ndim == 1:
        if ecef_arr.shape != (3,):
            raise ValueError(
                f"ECEF position must have shape (3,), got {ecef_arr.shape}"
            )
        ecef_arr = ecef_arr.reshape(1, 3)
        single_input: bool = True
    elif ecef_arr.ndim == 2:
        if ecef_arr.shape[1] != 3:
            raise ValueError(
                f"ECEF positions must have shape (N, 3), got {ecef_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(f"ECEF position must be 1D or 2D array, got {ecef_arr.ndim}D")

    # Extract reference geodetic coordinates
    lat: float = ref_lla_arr[0]
    lon: float = ref_lla_arr[1]
    alt: float = ref_lla_arr[2]

    # Convert reference LLA to ECEF
    reference_ecef: np.ndarray = lla_to_ecef(ref_lla_arr)

    # Compute relative ECEF position
    relative_ecef: np.ndarray = ecef_arr - reference_ecef

    # Construct ENU rotation matrix
    sin_lat: float = math.sin(lat)
    cos_lat: float = math.cos(lat)
    sin_lon: float = math.sin(lon)
    cos_lon: float = math.cos(lon)

    # ENU rotation matrix (3x3)
    # Each row represents the direction of E, N, U in ECEF coordinates
    enu_rotation_matrix: np.ndarray = np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ]
    )

    # Transform to ENU coordinates
    enu_positions: np.ndarray = relative_ecef @ enu_rotation_matrix.T

    # Return single vector if input was single
    return enu_positions[0] if single_input else enu_positions


def ecef_to_enu_velocity(
    ecef_velocity: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ECEF velocity to ENU coordinates relative to a reference point.

    Transforms a velocity vector from Earth-Centered Earth-Fixed (ECEF) coordinates
    to East-North-Up (ENU) coordinates. This is a pure rotation transformation
    (no translation component for velocities).

    Parameters
    ----------
    ecef_velocity : np.ndarray
        Velocity vector in ECEF coordinates [vx, vy, vz] in m/s.
        - Shape (3,): Single velocity vector
        - Shape (N, 3): Batch of N velocity vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all velocities if batch)

    Returns
    -------
    np.ndarray
        Velocity vector(s) in ENU coordinates [v_east, v_north, v_up] in m/s.
        - Shape (3,): If input is single velocity vector
        - Shape (N, 3): If input is batch of N velocity vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point at equator, prime meridian
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # Velocity pointing east in ECEF
    >>> ecef_vel = np.array([0.0, 100.0, 0.0])
    >>> enu_vel = ecef_to_enu_velocity(ecef_vel, ref_lla)
    """
    ecef_vel_arr: np.ndarray = np.asarray(ecef_velocity, dtype=float)
    ref_lla_arr: np.ndarray = np.asarray(reference_lla, dtype=float)

    # Validate reference LLA
    if ref_lla_arr.shape != (3,):
        raise ValueError(f"Reference LLA must have shape (3,), got {ref_lla_arr.shape}")

    # Determine if input is single or batch
    if ecef_vel_arr.ndim == 1:
        if ecef_vel_arr.shape != (3,):
            raise ValueError(
                f"ECEF velocity must have shape (3,), got {ecef_vel_arr.shape}"
            )
        ecef_vel_arr = ecef_vel_arr.reshape(1, 3)
        single_input: bool = True
    elif ecef_vel_arr.ndim == 2:
        if ecef_vel_arr.shape[1] != 3:
            raise ValueError(
                f"ECEF velocities must have shape (N, 3), got {ecef_vel_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"ECEF velocity must be 1D or 2D array, got {ecef_vel_arr.ndim}D"
        )

    # Extract reference geodetic coordinates
    lat: float = ref_lla_arr[0]
    lon: float = ref_lla_arr[1]

    # Construct ENU rotation matrix
    sin_lat: float = math.sin(lat)
    cos_lat: float = math.cos(lat)
    sin_lon: float = math.sin(lon)
    cos_lon: float = math.cos(lon)

    # ENU rotation matrix (3x3)
    enu_rotation_matrix: np.ndarray = np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ]
    )

    # Transform to ENU coordinates
    enu_velocities: np.ndarray = ecef_vel_arr @ enu_rotation_matrix.T

    # Return single vector if input was single
    return enu_velocities[0] if single_input else enu_velocities


def ecef_to_enu_state(
    ecef_state: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ECEF state vector to ENU coordinates relative to a reference point.

    Transforms a state vector (position and velocity) from Earth-Centered Earth-Fixed
    (ECEF) coordinates to East-North-Up (ENU) coordinates relative to a reference
    point specified in geodetic coordinates.

    Parameters
    ----------
    ecef_state : np.ndarray
        State vector in ECEF coordinates [x, y, z, vx, vy, vz].
        - Position [x, y, z] in meters
        - Velocity [vx, vy, vz] in m/s
        - Shape (6,): Single state vector
        - Shape (N, 6): Batch of N state vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all states if batch)

    Returns
    -------
    np.ndarray
        State vector(s) in ENU coordinates [e, n, u, ve, vn, vu].
        - Position [e, n, u] in meters
        - Velocity [ve, vn, vu] in m/s
        - Shape (6,): If input is single state vector
        - Shape (N, 6): If input is batch of N state vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # State vector in ECEF
    >>> ecef_state = np.array([6378136.3, 1000.0, 0.0, 0.0, 100.0, 0.0])
    >>> enu_state = ecef_to_enu_state(ecef_state, ref_lla)
    """
    ecef_state_arr: np.ndarray = np.asarray(ecef_state, dtype=float)

    # Determine if input is single or batch
    if ecef_state_arr.ndim == 1:
        if ecef_state_arr.shape != (6,):
            raise ValueError(
                f"ECEF state must have shape (6,), got {ecef_state_arr.shape}"
            )
        single_input: bool = True
        ecef_positions: np.ndarray = ecef_state_arr[0:3].reshape(1, 3)
        ecef_velocities: np.ndarray = ecef_state_arr[3:6].reshape(1, 3)
    elif ecef_state_arr.ndim == 2:
        if ecef_state_arr.shape[1] != 6:
            raise ValueError(
                f"ECEF states must have shape (N, 6), got {ecef_state_arr.shape}"
            )
        single_input = False
        ecef_positions = ecef_state_arr[:, 0:3]
        ecef_velocities = ecef_state_arr[:, 3:6]
    else:
        raise ValueError(
            f"ECEF state must be 1D or 2D array, got {ecef_state_arr.ndim}D"
        )

    # Convert position and velocity separately
    enu_positions: np.ndarray = ecef_to_enu(ecef_positions, reference_lla)
    enu_velocities: np.ndarray = ecef_to_enu_velocity(ecef_velocities, reference_lla)

    # Ensure proper shape for concatenation
    if single_input:
        enu_positions = enu_positions.reshape(1, 3)
        enu_velocities = enu_velocities.reshape(1, 3)

    # Combine position and velocity
    enu_states: np.ndarray = np.column_stack([enu_positions, enu_velocities])

    # Return single vector if input was single
    return enu_states[0] if single_input else enu_states


# ===================================================================
# ENU to ECEF conversion
# ===================================================================


def enu_to_ecef(
    enu_position: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ENU position to ECEF coordinates.

    Transforms a position vector from East-North-Up (ENU) coordinates to
    Earth-Centered Earth-Fixed (ECEF) coordinates using a reference point
    specified in geodetic coordinates.

    Parameters
    ----------
    enu_position : np.ndarray
        Position vector in ENU coordinates [east, north, up] in meters.
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all positions if batch)

    Returns
    -------
    np.ndarray
        Position vector(s) in ECEF coordinates [x, y, z] in meters.
        - Shape (3,): If input is single position vector
        - Shape (N, 3): If input is batch of N position vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point at equator, prime meridian, sea level
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # Point 1000m east, 500m north, 100m up from reference
    >>> enu_pos = np.array([1000.0, 500.0, 100.0])
    >>> ecef_pos = enu_to_ecef(enu_pos, ref_lla)
    """
    enu_arr: np.ndarray = np.asarray(enu_position, dtype=float)
    ref_lla_arr: np.ndarray = np.asarray(reference_lla, dtype=float)

    # Validate reference LLA
    if ref_lla_arr.shape != (3,):
        raise ValueError(f"Reference LLA must have shape (3,), got {ref_lla_arr.shape}")

    # Determine if input is single or batch
    if enu_arr.ndim == 1:
        if enu_arr.shape != (3,):
            raise ValueError(f"ENU position must have shape (3,), got {enu_arr.shape}")
        enu_arr = enu_arr.reshape(1, 3)
        single_input: bool = True
    elif enu_arr.ndim == 2:
        if enu_arr.shape[1] != 3:
            raise ValueError(
                f"ENU positions must have shape (N, 3), got {enu_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(f"ENU position must be 1D or 2D array, got {enu_arr.ndim}D")

    # Extract reference geodetic coordinates
    lat: float = ref_lla_arr[0]
    lon: float = ref_lla_arr[1]

    # Convert reference LLA to ECEF
    reference_ecef: np.ndarray = lla_to_ecef(ref_lla_arr)

    # Construct ENU rotation matrix
    sin_lat: float = math.sin(lat)
    cos_lat: float = math.cos(lat)
    sin_lon: float = math.sin(lon)
    cos_lon: float = math.cos(lon)

    # ENU rotation matrix (3x3)
    enu_rotation_matrix: np.ndarray = np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ]
    )

    # Transform from ENU to relative ECEF (inverse rotation)
    relative_ecef: np.ndarray = enu_arr @ enu_rotation_matrix

    # Add reference ECEF position
    ecef_positions: np.ndarray = relative_ecef + reference_ecef

    # Return single vector if input was single
    return ecef_positions[0] if single_input else ecef_positions


def enu_to_ecef_velocity(
    enu_velocity: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ENU velocity to ECEF coordinates.

    Transforms a velocity vector from East-North-Up (ENU) coordinates to
    Earth-Centered Earth-Fixed (ECEF) coordinates. This is a pure rotation
    transformation (no translation component for velocities).

    Parameters
    ----------
    enu_velocity : np.ndarray
        Velocity vector in ENU coordinates [v_east, v_north, v_up] in m/s.
        - Shape (3,): Single velocity vector
        - Shape (N, 3): Batch of N velocity vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all velocities if batch)

    Returns
    -------
    np.ndarray
        Velocity vector(s) in ECEF coordinates [vx, vy, vz] in m/s.
        - Shape (3,): If input is single velocity vector
        - Shape (N, 3): If input is batch of N velocity vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point at equator, prime meridian
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # Velocity pointing east
    >>> enu_vel = np.array([100.0, 0.0, 0.0])
    >>> ecef_vel = enu_to_ecef_velocity(enu_vel, ref_lla)
    """
    enu_vel_arr: np.ndarray = np.asarray(enu_velocity, dtype=float)
    ref_lla_arr: np.ndarray = np.asarray(reference_lla, dtype=float)

    # Validate reference LLA
    if ref_lla_arr.shape != (3,):
        raise ValueError(f"Reference LLA must have shape (3,), got {ref_lla_arr.shape}")

    # Determine if input is single or batch
    if enu_vel_arr.ndim == 1:
        if enu_vel_arr.shape != (3,):
            raise ValueError(
                f"ENU velocity must have shape (3,), got {enu_vel_arr.shape}"
            )
        enu_vel_arr = enu_vel_arr.reshape(1, 3)
        single_input: bool = True
    elif enu_vel_arr.ndim == 2:
        if enu_vel_arr.shape[1] != 3:
            raise ValueError(
                f"ENU velocities must have shape (N, 3), got {enu_vel_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"ENU velocity must be 1D or 2D array, got {enu_vel_arr.ndim}D"
        )

    # Extract reference geodetic coordinates
    lat: float = ref_lla_arr[0]
    lon: float = ref_lla_arr[1]

    # Construct ENU rotation matrix
    sin_lat: float = math.sin(lat)
    cos_lat: float = math.cos(lat)
    sin_lon: float = math.sin(lon)
    cos_lon: float = math.cos(lon)

    # ENU rotation matrix (3x3)
    enu_rotation_matrix: np.ndarray = np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ]
    )

    # Transform from ENU to ECEF (inverse rotation)
    ecef_velocities: np.ndarray = enu_vel_arr @ enu_rotation_matrix

    # Return single vector if input was single
    return ecef_velocities[0] if single_input else ecef_velocities


def enu_to_ecef_state(
    enu_state: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ENU state vector to ECEF coordinates.

    Transforms a state vector (position and velocity) from East-North-Up (ENU)
    coordinates to Earth-Centered Earth-Fixed (ECEF) coordinates using a reference
    point specified in geodetic coordinates.

    Parameters
    ----------
    enu_state : np.ndarray
        State vector in ENU coordinates [e, n, u, ve, vn, vu].
        - Position [e, n, u] in meters
        - Velocity [ve, vn, vu] in m/s
        - Shape (6,): Single state vector
        - Shape (N, 6): Batch of N state vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all states if batch)

    Returns
    -------
    np.ndarray
        State vector(s) in ECEF coordinates [x, y, z, vx, vy, vz].
        - Position [x, y, z] in meters
        - Velocity [vx, vy, vz] in m/s
        - Shape (6,): If input is single state vector
        - Shape (N, 6): If input is batch of N state vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # State vector in ENU
    >>> enu_state = np.array([1000.0, 500.0, 100.0, 10.0, 5.0, 1.0])
    >>> ecef_state = enu_to_ecef_state(enu_state, ref_lla)
    """
    enu_state_arr: np.ndarray = np.asarray(enu_state, dtype=float)

    # Determine if input is single or batch
    if enu_state_arr.ndim == 1:
        if enu_state_arr.shape != (6,):
            raise ValueError(
                f"ENU state must have shape (6,), got {enu_state_arr.shape}"
            )
        single_input: bool = True
        enu_positions: np.ndarray = enu_state_arr[0:3].reshape(1, 3)
        enu_velocities: np.ndarray = enu_state_arr[3:6].reshape(1, 3)
    elif enu_state_arr.ndim == 2:
        if enu_state_arr.shape[1] != 6:
            raise ValueError(
                f"ENU states must have shape (N, 6), got {enu_state_arr.shape}"
            )
        single_input = False
        enu_positions = enu_state_arr[:, 0:3]
        enu_velocities = enu_state_arr[:, 3:6]
    else:
        raise ValueError(f"ENU state must be 1D or 2D array, got {enu_state_arr.ndim}D")

    # Convert position and velocity separately
    ecef_positions: np.ndarray = enu_to_ecef(enu_positions, reference_lla)
    ecef_velocities: np.ndarray = enu_to_ecef_velocity(enu_velocities, reference_lla)

    # Ensure proper shape for concatenation
    if single_input:
        ecef_positions = ecef_positions.reshape(1, 3)
        ecef_velocities = ecef_velocities.reshape(1, 3)

    # Combine position and velocity
    ecef_states: np.ndarray = np.column_stack([ecef_positions, ecef_velocities])

    # Return single vector if input was single
    return ecef_states[0] if single_input else ecef_states


# ===================================================================
# Geodetic coordinate conversions
# ===================================================================


def lla_to_ecef(lla: np.ndarray) -> np.ndarray:
    """Convert geodetic coordinates (LLA) to ECEF coordinates.

    Transforms geodetic coordinates (latitude, longitude, altitude) to
    Earth-Centered Earth-Fixed (ECEF) Cartesian coordinates using the
    WGS-84 ellipsoid model.

    Parameters
    ----------
    lla : np.ndarray
        Geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        - Shape (3,): Single coordinate
        - Shape (N, 3): Batch of N coordinates

    Returns
    -------
    np.ndarray
        Position vector(s) in ECEF coordinates [x, y, z] in meters.
        - Shape (3,): If input is single coordinate
        - Shape (N, 3): If input is batch of N coordinates

    Examples
    --------
    >>> import numpy as np
    >>> # Point at equator, prime meridian, sea level
    >>> lla = np.array([0.0, 0.0, 0.0])
    >>> ecef = lla_to_ecef(lla)
    >>> # Should be approximately [6378136.3, 0.0, 0.0]
    """
    lla_arr: np.ndarray = np.asarray(lla, dtype=float)

    # Determine if input is single or batch
    if lla_arr.ndim == 1:
        if lla_arr.shape != (3,):
            raise ValueError(f"LLA must have shape (3,), got {lla_arr.shape}")
        lla_arr = lla_arr.reshape(1, 3)
        single_input: bool = True
    elif lla_arr.ndim == 2:
        if lla_arr.shape[1] != 3:
            raise ValueError(f"LLA must have shape (N, 3), got {lla_arr.shape}")
        single_input = False
    else:
        raise ValueError(f"LLA must be 1D or 2D array, got {lla_arr.ndim}D")

    # Extract coordinates
    lat: np.ndarray = lla_arr[:, 0]
    lon: np.ndarray = lla_arr[:, 1]
    alt: np.ndarray = lla_arr[:, 2]

    # Compute prime vertical radius of curvature
    sin_lat: np.ndarray = np.sin(lat)
    cos_lat: np.ndarray = np.cos(lat)
    sin_lon: np.ndarray = np.sin(lon)
    cos_lon: np.ndarray = np.cos(lon)

    N: np.ndarray = EARTH_EQUATORIAL_RADIUS_M / np.sqrt(
        1.0 - EARTH_ECCENTRICITY_SQUARED * sin_lat**2
    )

    # Compute ECEF coordinates
    x: np.ndarray = (N + alt) * cos_lat * cos_lon
    y: np.ndarray = (N + alt) * cos_lat * sin_lon
    z: np.ndarray = (N * (1.0 - EARTH_ECCENTRICITY_SQUARED) + alt) * sin_lat

    ecef: np.ndarray = np.column_stack([x, y, z])

    # Return single vector if input was single
    return ecef[0] if single_input else ecef


def ecef_to_lla(
    ecef: np.ndarray, tolerance: float = 1e-12, max_iterations: int = 10
) -> np.ndarray:
    """Convert ECEF coordinates to geodetic coordinates (LLA).

    Transforms Earth-Centered Earth-Fixed (ECEF) Cartesian coordinates to
    geodetic coordinates (latitude, longitude, altitude) using an iterative
    algorithm based on the WGS-84 ellipsoid model.

    Parameters
    ----------
    ecef : np.ndarray
        Position vector in ECEF coordinates [x, y, z] in meters.
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    tolerance : float, optional
        Convergence tolerance for latitude iteration in radians.
        Default is 1e-12 radians (~0.002 millimeters at Earth's surface).
    max_iterations : int, optional
        Maximum number of iterations for latitude convergence.
        Default is 10.

    Returns
    -------
    np.ndarray
        Geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        - Shape (3,): If input is single position vector
        - Shape (N, 3): If input is batch of N position vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Point at Earth's equatorial radius
    >>> ecef = np.array([6378136.3, 0.0, 0.0])
    >>> lla = ecef_to_lla(ecef)
    >>> # Should be approximately [0.0, 0.0, 0.0]
    """
    ecef_arr: np.ndarray = np.asarray(ecef, dtype=float)

    # Determine if input is single or batch
    if ecef_arr.ndim == 1:
        if ecef_arr.shape != (3,):
            raise ValueError(f"ECEF must have shape (3,), got {ecef_arr.shape}")
        ecef_arr = ecef_arr.reshape(1, 3)
        single_input: bool = True
    elif ecef_arr.ndim == 2:
        if ecef_arr.shape[1] != 3:
            raise ValueError(f"ECEF must have shape (N, 3), got {ecef_arr.shape}")
        single_input = False
    else:
        raise ValueError(f"ECEF must be 1D or 2D array, got {ecef_arr.ndim}D")

    # Extract coordinates
    x: np.ndarray = ecef_arr[:, 0]
    y: np.ndarray = ecef_arr[:, 1]
    z: np.ndarray = ecef_arr[:, 2]

    # Compute longitude (straightforward)
    lon: np.ndarray = np.arctan2(y, x)

    # Compute latitude iteratively
    p: np.ndarray = np.sqrt(x**2 + y**2)
    lat: np.ndarray = np.arctan2(z, p * (1.0 - EARTH_ECCENTRICITY_SQUARED))

    for _ in range(max_iterations):
        sin_lat: np.ndarray = np.sin(lat)
        N: np.ndarray = EARTH_EQUATORIAL_RADIUS_M / np.sqrt(
            1.0 - EARTH_ECCENTRICITY_SQUARED * sin_lat**2
        )
        lat_new: np.ndarray = np.arctan2(
            z + EARTH_ECCENTRICITY_SQUARED * N * sin_lat, p
        )

        # Check convergence
        if np.all(np.abs(lat_new - lat) < tolerance):
            lat = lat_new
            break

        lat = lat_new

    # Compute altitude
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    N = EARTH_EQUATORIAL_RADIUS_M / np.sqrt(
        1.0 - EARTH_ECCENTRICITY_SQUARED * sin_lat**2
    )
    alt: np.ndarray = p / cos_lat - N

    # Handle points near poles where cos(lat) ≈ 0
    near_pole: np.ndarray = np.abs(cos_lat) < 1e-10
    if np.any(near_pole):
        alt[near_pole] = np.abs(z[near_pole]) - N[near_pole] * (
            1.0 - EARTH_ECCENTRICITY_SQUARED
        )

    lla: np.ndarray = np.column_stack([lat, lon, alt])

    # Return single vector if input was single
    return lla[0] if single_input else lla
