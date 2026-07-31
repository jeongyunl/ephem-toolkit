"""Coordinate conversion utilities for AER (Azimuth-Elevation-Range) frames.

Provides functions for converting between ECEF (Earth-Centered Earth-Fixed) and
AER (Azimuth-Elevation-Range) coordinate systems.

The AER coordinate system is a spherical coordinate system centered at a
reference point on the Earth's surface:
- Azimuth: Angle measured clockwise from North (0° = North, 90° = East)
- Elevation: Angle above the local horizontal plane (0° = horizon, 90° = zenith)
- Range: Distance from the reference point to the target

References:
    WGS-84 Earth Gravitational Model
    "Department of Defense World Geodetic System 1984"
"""

from __future__ import annotations

import numpy as np

import common.wgs as wgs

# ===================================================================
# ECEF to AER conversion
# ===================================================================


def ecef_to_aer(
    ecef_position: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ECEF position to AER coordinates relative to a reference point.

    Transforms a position vector from Earth-Centered Earth-Fixed (ECEF) coordinates
    to Azimuth-Elevation-Range (AER) coordinates relative to a reference point
    specified in geodetic coordinates (latitude, longitude, altitude).

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
        Position vector(s) in AER coordinates [azimuth, elevation, range].
        - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
        - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
        - range: Distance in meters
        - Shape (3,): If input is single position vector
        - Shape (N, 3): If input is batch of N position vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point at equator, prime meridian, sea level
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # Point 1000m east of reference
    >>> ecef_pos = np.array([6378136.3, 1000.0, 0.0])
    >>> aer_pos = ecef_to_aer(ecef_pos, ref_lla)
    """
    # First convert ECEF to ENU
    enu_position: np.ndarray = wgs.ecef_to_enu(ecef_position, reference_lla)

    # Convert ENU to AER
    return enu_to_aer(enu_position)


def ecef_to_aer_velocity(
    ecef_position: np.ndarray,
    ecef_velocity: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ECEF velocity to AER rate coordinates relative to a reference point.

    Transforms a velocity vector from Earth-Centered Earth-Fixed (ECEF) coordinates
    to AER rate coordinates (azimuth rate, elevation rate, range rate). This requires
    both position and velocity since the transformation depends on the current position.

    Parameters
    ----------
    ecef_position : np.ndarray
        Position vector in ECEF coordinates [x, y, z] in meters.
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    ecef_velocity : np.ndarray
        Velocity vector in ECEF coordinates [vx, vy, vz] in m/s.
        - Shape (3,): Single velocity vector
        - Shape (N, 3): Batch of N velocity vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all positions if batch)

    Returns
    -------
    np.ndarray
        Velocity vector(s) in AER rate coordinates [az_rate, el_rate, range_rate].
        - az_rate: Azimuth rate in rad/s
        - el_rate: Elevation rate in rad/s
        - range_rate: Range rate in m/s
        - Shape (3,): If input is single velocity vector
        - Shape (N, 3): If input is batch of N velocity vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point at equator, prime meridian
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # Position and velocity
    >>> ecef_pos = np.array([6378136.3, 1000.0, 0.0])
    >>> ecef_vel = np.array([0.0, 100.0, 0.0])
    >>> aer_vel = ecef_to_aer_velocity(ecef_pos, ecef_vel, ref_lla)
    """
    # Convert position and velocity to ENU
    enu_position: np.ndarray = wgs.ecef_to_enu(ecef_position, reference_lla)
    enu_velocity: np.ndarray = wgs.ecef_to_enu_velocity(ecef_velocity, reference_lla)

    # Convert ENU to AER rates
    return enu_to_aer_velocity(enu_position, enu_velocity)


def ecef_to_aer_state(
    ecef_state: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert ECEF state vector to AER coordinates relative to a reference point.

    Transforms a state vector (position and velocity) from Earth-Centered Earth-Fixed
    (ECEF) coordinates to AER (Azimuth-Elevation-Range) coordinates and rates relative
    to a reference point specified in geodetic coordinates.

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
        State vector(s) in AER coordinates [az, el, r, az_rate, el_rate, r_rate].
        - Position [az, el, r]: azimuth (rad), elevation (rad), range (m)
        - Velocity [az_rate, el_rate, r_rate]: rates in rad/s, rad/s, m/s
        - Shape (6,): If input is single state vector
        - Shape (N, 6): If input is batch of N state vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Reference point
    >>> ref_lla = np.array([0.0, 0.0, 0.0])
    >>> # State vector in ECEF
    >>> ecef_state = np.array([6378136.3, 1000.0, 0.0, 0.0, 100.0, 0.0])
    >>> aer_state = ecef_to_aer_state(ecef_state, ref_lla)
    """
    ecef_state_arr: np.ndarray = np.asarray(ecef_state, dtype=float)

    # Determine if input is single or batch
    if ecef_state_arr.ndim == 1:
        if ecef_state_arr.shape != (6,):
            raise ValueError(
                f"ECEF state must have shape (6,), got {ecef_state_arr.shape}"
            )
        single_input: bool = True
        ecef_positions: np.ndarray = ecef_state_arr[0:3]
        ecef_velocities: np.ndarray = ecef_state_arr[3:6]
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
    aer_positions: np.ndarray = ecef_to_aer(ecef_positions, reference_lla)
    aer_velocities: np.ndarray = ecef_to_aer_velocity(
        ecef_positions, ecef_velocities, reference_lla
    )

    # Ensure proper shape for concatenation
    if single_input:
        aer_positions = aer_positions.reshape(1, 3)
        aer_velocities = aer_velocities.reshape(1, 3)

    # Combine position and velocity
    aer_states: np.ndarray = np.column_stack([aer_positions, aer_velocities])

    # Return single vector if input was single
    return aer_states[0] if single_input else aer_states


# ===================================================================
# AER to ECEF conversion
# ===================================================================


def aer_to_ecef(
    aer_position: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert AER position to ECEF coordinates.

    Transforms a position vector from Azimuth-Elevation-Range (AER) coordinates to
    Earth-Centered Earth-Fixed (ECEF) coordinates using a reference point specified
    in geodetic coordinates.

    Parameters
    ----------
    aer_position : np.ndarray
        Position vector in AER coordinates [azimuth, elevation, range].
        - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
        - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
        - range: Distance in meters
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
    >>> # Point at azimuth 90° (East), elevation 0°, range 1000m
    >>> aer_pos = np.array([np.pi/2, 0.0, 1000.0])
    >>> ecef_pos = aer_to_ecef(aer_pos, ref_lla)
    """
    # First convert AER to ENU
    enu_position: np.ndarray = aer_to_enu(aer_position)

    # Convert ENU to ECEF
    return wgs.enu_to_ecef(enu_position, reference_lla)


def aer_to_ecef_velocity(
    aer_position: np.ndarray,
    aer_velocity: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert AER rate coordinates to ECEF velocity.

    Transforms a velocity vector from AER rate coordinates (azimuth rate, elevation
    rate, range rate) to Earth-Centered Earth-Fixed (ECEF) coordinates. This requires
    both position and velocity since the transformation depends on the current position.

    Parameters
    ----------
    aer_position : np.ndarray
        Position vector in AER coordinates [azimuth, elevation, range].
        - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
        - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
        - range: Distance in meters
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    aer_velocity : np.ndarray
        Velocity vector in AER rate coordinates [az_rate, el_rate, range_rate].
        - az_rate: Azimuth rate in rad/s
        - el_rate: Elevation rate in rad/s
        - range_rate: Range rate in m/s
        - Shape (3,): Single velocity vector
        - Shape (N, 3): Batch of N velocity vectors
    reference_lla : np.ndarray
        Reference point in geodetic coordinates [lat, lon, alt].
        - lat: Latitude in radians
        - lon: Longitude in radians
        - alt: Altitude above WGS-84 ellipsoid in meters
        Shape (3,): Single reference point (used for all positions if batch)

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
    >>> # Position and velocity in AER
    >>> aer_pos = np.array([np.pi/2, 0.0, 1000.0])
    >>> aer_vel = np.array([0.0, 0.0, 100.0])
    >>> ecef_vel = aer_to_ecef_velocity(aer_pos, aer_vel, ref_lla)
    """
    # Convert AER to ENU
    enu_position: np.ndarray = aer_to_enu(aer_position)
    enu_velocity: np.ndarray = aer_to_enu_velocity(aer_position, aer_velocity)

    # Convert ENU velocity to ECEF
    return wgs.enu_to_ecef_velocity(enu_velocity, reference_lla)


def aer_to_ecef_state(
    aer_state: np.ndarray,
    reference_lla: np.ndarray,
) -> np.ndarray:
    """Convert AER state vector to ECEF coordinates.

    Transforms a state vector (position and velocity) from AER (Azimuth-Elevation-Range)
    coordinates to Earth-Centered Earth-Fixed (ECEF) coordinates using a reference
    point specified in geodetic coordinates.

    Parameters
    ----------
    aer_state : np.ndarray
        State vector in AER coordinates [az, el, r, az_rate, el_rate, r_rate].
        - Position [az, el, r]: azimuth (rad), elevation (rad), range (m)
        - Velocity [az_rate, el_rate, r_rate]: rates in rad/s, rad/s, m/s
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
    >>> # State vector in AER
    >>> aer_state = np.array([np.pi/2, 0.0, 1000.0, 0.0, 0.0, 100.0])
    >>> ecef_state = aer_to_ecef_state(aer_state, ref_lla)
    """
    aer_state_arr: np.ndarray = np.asarray(aer_state, dtype=float)

    # Determine if input is single or batch
    if aer_state_arr.ndim == 1:
        if aer_state_arr.shape != (6,):
            raise ValueError(
                f"AER state must have shape (6,), got {aer_state_arr.shape}"
            )
        single_input: bool = True
        aer_positions: np.ndarray = aer_state_arr[0:3]
        aer_velocities: np.ndarray = aer_state_arr[3:6]
    elif aer_state_arr.ndim == 2:
        if aer_state_arr.shape[1] != 6:
            raise ValueError(
                f"AER states must have shape (N, 6), got {aer_state_arr.shape}"
            )
        single_input = False
        aer_positions = aer_state_arr[:, 0:3]
        aer_velocities = aer_state_arr[:, 3:6]
    else:
        raise ValueError(f"AER state must be 1D or 2D array, got {aer_state_arr.ndim}D")

    # Convert position and velocity separately
    ecef_positions: np.ndarray = aer_to_ecef(aer_positions, reference_lla)
    ecef_velocities: np.ndarray = aer_to_ecef_velocity(
        aer_positions, aer_velocities, reference_lla
    )

    # Ensure proper shape for concatenation
    if single_input:
        ecef_positions = ecef_positions.reshape(1, 3)
        ecef_velocities = ecef_velocities.reshape(1, 3)

    # Combine position and velocity
    ecef_states: np.ndarray = np.column_stack([ecef_positions, ecef_velocities])

    # Return single vector if input was single
    return ecef_states[0] if single_input else ecef_states


# ===================================================================
# ENU to AER conversion
# ===================================================================


def enu_to_aer(enu_position: np.ndarray) -> np.ndarray:
    """Convert ENU position to AER coordinates.

    Transforms a position vector from East-North-Up (ENU) coordinates to
    Azimuth-Elevation-Range (AER) coordinates.

    Parameters
    ----------
    enu_position : np.ndarray
        Position vector in ENU coordinates [east, north, up] in meters.
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors

    Returns
    -------
    np.ndarray
        Position vector(s) in AER coordinates [azimuth, elevation, range].
        - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
        - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
        - range: Distance in meters
        - Shape (3,): If input is single position vector
        - Shape (N, 3): If input is batch of N position vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Point 1000m east, 0m north, 0m up
    >>> enu_pos = np.array([1000.0, 0.0, 0.0])
    >>> aer_pos = enu_to_aer(enu_pos)
    >>> # Should give azimuth = π/2 (90°), elevation = 0, range = 1000
    """
    enu_arr: np.ndarray = np.asarray(enu_position, dtype=float)

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

    # Extract ENU components
    east: np.ndarray = enu_arr[:, 0]
    north: np.ndarray = enu_arr[:, 1]
    up: np.ndarray = enu_arr[:, 2]

    # Compute range (slant distance)
    range_val: np.ndarray = np.sqrt(east**2 + north**2 + up**2)

    # Compute horizontal distance
    horizontal_range: np.ndarray = np.sqrt(east**2 + north**2)

    # Compute azimuth (measured clockwise from North)
    # atan2(east, north) gives angle from North axis
    azimuth: np.ndarray = np.arctan2(east, north)

    # Ensure azimuth is in [0, 2π)
    azimuth = np.mod(azimuth, 2.0 * np.pi)

    # Compute elevation (angle above horizontal plane)
    elevation: np.ndarray = np.arctan2(up, horizontal_range)

    # Handle case where horizontal_range is zero (directly overhead or at origin)
    # In this case, azimuth is undefined, but we set it to 0 by convention
    at_zenith_or_origin: np.ndarray = horizontal_range < 1e-10
    if np.any(at_zenith_or_origin):
        azimuth[at_zenith_or_origin] = 0.0
        # Elevation is ±π/2 depending on sign of up
        elevation[at_zenith_or_origin] = np.sign(up[at_zenith_or_origin]) * np.pi / 2.0

    aer: np.ndarray = np.column_stack([azimuth, elevation, range_val])

    # Return single vector if input was single
    return aer[0] if single_input else aer


def enu_to_aer_velocity(
    enu_position: np.ndarray,
    enu_velocity: np.ndarray,
) -> np.ndarray:
    """Convert ENU velocity to AER rate coordinates.

    Transforms a velocity vector from East-North-Up (ENU) coordinates to AER rate
    coordinates (azimuth rate, elevation rate, range rate). This requires both
    position and velocity since the transformation depends on the current position.

    Parameters
    ----------
    enu_position : np.ndarray
        Position vector in ENU coordinates [east, north, up] in meters.
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    enu_velocity : np.ndarray
        Velocity vector in ENU coordinates [v_east, v_north, v_up] in m/s.
        - Shape (3,): Single velocity vector
        - Shape (N, 3): Batch of N velocity vectors

    Returns
    -------
    np.ndarray
        Velocity vector(s) in AER rate coordinates [az_rate, el_rate, range_rate].
        - az_rate: Azimuth rate in rad/s
        - el_rate: Elevation rate in rad/s
        - range_rate: Range rate in m/s
        - Shape (3,): If input is single velocity vector
        - Shape (N, 3): If input is batch of N velocity vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Position 1000m east
    >>> enu_pos = np.array([1000.0, 0.0, 0.0])
    >>> # Velocity 100 m/s north
    >>> enu_vel = np.array([0.0, 100.0, 0.0])
    >>> aer_vel = enu_to_aer_velocity(enu_pos, enu_vel)
    """
    enu_pos_arr: np.ndarray = np.asarray(enu_position, dtype=float)
    enu_vel_arr: np.ndarray = np.asarray(enu_velocity, dtype=float)

    # Determine if input is single or batch
    if enu_pos_arr.ndim == 1:
        if enu_pos_arr.shape != (3,):
            raise ValueError(
                f"ENU position must have shape (3,), got {enu_pos_arr.shape}"
            )
        enu_pos_arr = enu_pos_arr.reshape(1, 3)
        single_input: bool = True
    elif enu_pos_arr.ndim == 2:
        if enu_pos_arr.shape[1] != 3:
            raise ValueError(
                f"ENU positions must have shape (N, 3), got {enu_pos_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"ENU position must be 1D or 2D array, got {enu_pos_arr.ndim}D"
        )

    if enu_vel_arr.ndim == 1:
        if enu_vel_arr.shape != (3,):
            raise ValueError(
                f"ENU velocity must have shape (3,), got {enu_vel_arr.shape}"
            )
        enu_vel_arr = enu_vel_arr.reshape(1, 3)
    elif enu_vel_arr.ndim == 2:
        if enu_vel_arr.shape[1] != 3:
            raise ValueError(
                f"ENU velocities must have shape (N, 3), got {enu_vel_arr.shape}"
            )
    else:
        raise ValueError(
            f"ENU velocity must be 1D or 2D array, got {enu_vel_arr.ndim}D"
        )

    # Extract ENU components
    east: np.ndarray = enu_pos_arr[:, 0]
    north: np.ndarray = enu_pos_arr[:, 1]
    up: np.ndarray = enu_pos_arr[:, 2]

    v_east: np.ndarray = enu_vel_arr[:, 0]
    v_north: np.ndarray = enu_vel_arr[:, 1]
    v_up: np.ndarray = enu_vel_arr[:, 2]

    # Compute range and horizontal range
    range_val: np.ndarray = np.sqrt(east**2 + north**2 + up**2)
    horizontal_range: np.ndarray = np.sqrt(east**2 + north**2)

    # Compute range rate (radial velocity)
    # range_rate = d(range)/dt = (e*ve + n*vn + u*vu) / range
    range_rate: np.ndarray = (east * v_east + north * v_north + up * v_up) / (
        range_val + 1e-10
    )

    # Compute azimuth rate
    # az_rate = d(atan2(e, n))/dt = (n*ve - e*vn) / (e^2 + n^2)
    azimuth_rate: np.ndarray = (north * v_east - east * v_north) / (
        horizontal_range**2 + 1e-10
    )

    # Compute elevation rate
    # el_rate = d(atan2(u, h))/dt where h = sqrt(e^2 + n^2)
    # el_rate = (h*vu - u*h_rate) / (h^2 + u^2)
    # where h_rate = (e*ve + n*vn) / h
    horizontal_rate: np.ndarray = (east * v_east + north * v_north) / (
        horizontal_range + 1e-10
    )
    elevation_rate: np.ndarray = (horizontal_range * v_up - up * horizontal_rate) / (
        range_val**2 + 1e-10
    )

    # Handle singularities (at origin or zenith/nadir)
    small_range: np.ndarray = range_val < 1e-10
    if np.any(small_range):
        range_rate[small_range] = 0.0
        azimuth_rate[small_range] = 0.0
        elevation_rate[small_range] = 0.0

    aer_velocity: np.ndarray = np.column_stack(
        [azimuth_rate, elevation_rate, range_rate]
    )

    # Return single vector if input was single
    return aer_velocity[0] if single_input else aer_velocity


# ===================================================================
# AER to ENU conversion
# ===================================================================


def aer_to_enu(aer_position: np.ndarray) -> np.ndarray:
    """Convert AER position to ENU coordinates.

    Transforms a position vector from Azimuth-Elevation-Range (AER) coordinates to
    East-North-Up (ENU) coordinates.

    Parameters
    ----------
    aer_position : np.ndarray
        Position vector in AER coordinates [azimuth, elevation, range].
        - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
        - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
        - range: Distance in meters
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors

    Returns
    -------
    np.ndarray
        Position vector(s) in ENU coordinates [east, north, up] in meters.
        - Shape (3,): If input is single position vector
        - Shape (N, 3): If input is batch of N position vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Point at azimuth 90° (East), elevation 0°, range 1000m
    >>> aer_pos = np.array([np.pi/2, 0.0, 1000.0])
    >>> enu_pos = aer_to_enu(aer_pos)
    >>> # Should give approximately [1000.0, 0.0, 0.0]
    """
    aer_arr: np.ndarray = np.asarray(aer_position, dtype=float)

    # Determine if input is single or batch
    if aer_arr.ndim == 1:
        if aer_arr.shape != (3,):
            raise ValueError(f"AER position must have shape (3,), got {aer_arr.shape}")
        aer_arr = aer_arr.reshape(1, 3)
        single_input: bool = True
    elif aer_arr.ndim == 2:
        if aer_arr.shape[1] != 3:
            raise ValueError(
                f"AER positions must have shape (N, 3), got {aer_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(f"AER position must be 1D or 2D array, got {aer_arr.ndim}D")

    # Extract AER components
    azimuth: np.ndarray = aer_arr[:, 0]
    elevation: np.ndarray = aer_arr[:, 1]
    range_val: np.ndarray = aer_arr[:, 2]

    # Compute horizontal range
    horizontal_range: np.ndarray = range_val * np.cos(elevation)

    # Compute ENU components
    east: np.ndarray = horizontal_range * np.sin(azimuth)
    north: np.ndarray = horizontal_range * np.cos(azimuth)
    up: np.ndarray = range_val * np.sin(elevation)

    enu: np.ndarray = np.column_stack([east, north, up])

    # Return single vector if input was single
    return enu[0] if single_input else enu


def aer_to_enu_velocity(
    aer_position: np.ndarray,
    aer_velocity: np.ndarray,
) -> np.ndarray:
    """Convert AER rate coordinates to ENU velocity.

    Transforms a velocity vector from AER rate coordinates (azimuth rate, elevation
    rate, range rate) to East-North-Up (ENU) coordinates. This requires both position
    and velocity since the transformation depends on the current position.

    Parameters
    ----------
    aer_position : np.ndarray
        Position vector in AER coordinates [azimuth, elevation, range].
        - azimuth: Azimuth angle in radians (0 = North, π/2 = East)
        - elevation: Elevation angle in radians (0 = horizon, π/2 = zenith)
        - range: Distance in meters
        - Shape (3,): Single position vector
        - Shape (N, 3): Batch of N position vectors
    aer_velocity : np.ndarray
        Velocity vector in AER rate coordinates [az_rate, el_rate, range_rate].
        - az_rate: Azimuth rate in rad/s
        - el_rate: Elevation rate in rad/s
        - range_rate: Range rate in m/s
        - Shape (3,): Single velocity vector
        - Shape (N, 3): Batch of N velocity vectors

    Returns
    -------
    np.ndarray
        Velocity vector(s) in ENU coordinates [v_east, v_north, v_up] in m/s.
        - Shape (3,): If input is single velocity vector
        - Shape (N, 3): If input is batch of N velocity vectors

    Examples
    --------
    >>> import numpy as np
    >>> # Position at azimuth 90° (East), elevation 0°, range 1000m
    >>> aer_pos = np.array([np.pi/2, 0.0, 1000.0])
    >>> # Range rate 100 m/s
    >>> aer_vel = np.array([0.0, 0.0, 100.0])
    >>> enu_vel = aer_to_enu_velocity(aer_pos, aer_vel)
    """
    aer_pos_arr: np.ndarray = np.asarray(aer_position, dtype=float)
    aer_vel_arr: np.ndarray = np.asarray(aer_velocity, dtype=float)

    # Determine if input is single or batch
    if aer_pos_arr.ndim == 1:
        if aer_pos_arr.shape != (3,):
            raise ValueError(
                f"AER position must have shape (3,), got {aer_pos_arr.shape}"
            )
        aer_pos_arr = aer_pos_arr.reshape(1, 3)
        single_input: bool = True
    elif aer_pos_arr.ndim == 2:
        if aer_pos_arr.shape[1] != 3:
            raise ValueError(
                f"AER positions must have shape (N, 3), got {aer_pos_arr.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"AER position must be 1D or 2D array, got {aer_pos_arr.ndim}D"
        )

    if aer_vel_arr.ndim == 1:
        if aer_vel_arr.shape != (3,):
            raise ValueError(
                f"AER velocity must have shape (3,), got {aer_vel_arr.shape}"
            )
        aer_vel_arr = aer_vel_arr.reshape(1, 3)
    elif aer_vel_arr.ndim == 2:
        if aer_vel_arr.shape[1] != 3:
            raise ValueError(
                f"AER velocities must have shape (N, 3), got {aer_vel_arr.shape}"
            )
    else:
        raise ValueError(
            f"AER velocity must be 1D or 2D array, got {aer_vel_arr.ndim}D"
        )

    # Extract AER components
    azimuth: np.ndarray = aer_pos_arr[:, 0]
    elevation: np.ndarray = aer_pos_arr[:, 1]
    range_val: np.ndarray = aer_pos_arr[:, 2]

    az_rate: np.ndarray = aer_vel_arr[:, 0]
    el_rate: np.ndarray = aer_vel_arr[:, 1]
    range_rate: np.ndarray = aer_vel_arr[:, 2]

    # Precompute trigonometric values
    sin_az: np.ndarray = np.sin(azimuth)
    cos_az: np.ndarray = np.cos(azimuth)
    sin_el: np.ndarray = np.sin(elevation)
    cos_el: np.ndarray = np.cos(elevation)

    # Compute horizontal range and its rate
    horizontal_range: np.ndarray = range_val * cos_el
    horizontal_rate: np.ndarray = range_rate * cos_el - range_val * sin_el * el_rate

    # Compute ENU velocity components
    # east = h * sin(az), so v_east = h_rate * sin(az) + h * cos(az) * az_rate
    v_east: np.ndarray = horizontal_rate * sin_az + horizontal_range * cos_az * az_rate

    # north = h * cos(az), so v_north = h_rate * cos(az) - h * sin(az) * az_rate
    v_north: np.ndarray = horizontal_rate * cos_az - horizontal_range * sin_az * az_rate

    # up = r * sin(el), so v_up = range_rate * sin(el) + r * cos(el) * el_rate
    v_up: np.ndarray = range_rate * sin_el + range_val * cos_el * el_rate

    enu_velocity: np.ndarray = np.column_stack([v_east, v_north, v_up])

    # Return single vector if input was single
    return enu_velocity[0] if single_input else enu_velocity
