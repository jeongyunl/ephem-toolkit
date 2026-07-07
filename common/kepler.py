"""Convert between Cartesian state vectors and osculating Keplerian elements.

Provides :func:`cartesian_to_keplerian`, :func:`keplerian_to_cartesian`,
and :func:`tle_to_osculating_keplerian` for two-body orbital element
conversions using only NumPy.

The six classical osculating Keplerian elements use the same ordering as
tudatpy's ``element_conversion`` module:

    ======  ====  ==========================================
    Index   Name  Description
    ======  ====  ==========================================
    0       a     Semi-major axis (m)
    1       e     Eccentricity (dimensionless)
    2       i     Inclination (rad)
    3       ω     Argument of periapsis (rad)
    4       Ω     Right ascension of ascending node (rad)
    5       θ     True anomaly (rad)
    ======  ====  ==========================================

References:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 4.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Algorithm 9.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np

# ===================================================================
# Constants
# ===================================================================

MU_EARTH: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""

RE_EARTH: float = 6378137.0
"""Earth equatorial radius (m), WGS-84."""

J2_EARTH: float = 1.08262668e-3
"""Earth J2 zonal harmonic coefficient (dimensionless), WGS-84."""


# ===================================================================
# Keplerian element indices (matches tudatpy convention)
# ===================================================================

SEMI_MAJOR_AXIS_INDEX: int = 0
"""Index of the semi-major axis element in the Keplerian state vector."""

ECCENTRICITY_INDEX: int = 1
"""Index of the eccentricity element in the Keplerian state vector."""

INCLINATION_INDEX: int = 2
"""Index of the inclination element in the Keplerian state vector."""

ARGUMENT_OF_PERIAPSIS_INDEX: int = 3
"""Index of the argument of periapsis element in the Keplerian state vector."""

RAAN_INDEX: int = 4
"""Index of the right ascension of the ascending node in the Keplerian state vector."""

TRUE_ANOMALY_INDEX: int = 5
"""Index of the true anomaly element in the Keplerian state vector."""

MEAN_ANOMALY_INDEX: int = TRUE_ANOMALY_INDEX
"""Alias for :data:`TRUE_ANOMALY_INDEX`; used when the 6th element is mean anomaly."""


# ===================================================================
# Cartesian -> Keplerian
# ===================================================================


def cartesian_to_keplerian(cartesian_state_vector: np.ndarray, mu: float) -> np.ndarray:
    """Convert Cartesian state vector(s) to osculating Keplerian elements.

    Supports both single and batch processing of state vectors.

    Parameters
    ----------
    cartesian_state_vector : np.ndarray
        Cartesian state vector(s) in meters and m/s.
        - Shape (6,): Single state vector [x, y, z, vx, vy, vz]
        - Shape (N, 6): Batch of N state vectors
    mu : float
        Gravitational parameter of the central body (m³/s²).

    Returns
    -------
    np.ndarray
        Keplerian elements [a, e, i, omega, RAAN, theta].
        Angles in radians, semi-major axis in meters.
        - Shape (6,): If input is single vector
        - Shape (N, 6): If input is batch of N vectors
        Element ordering matches tudatpy convention.

    Raises
    ------
    ValueError
        If the state vector shape is invalid or if any orbit is
        degenerate (zero angular momentum).
    """
    state_vector: np.ndarray = np.asarray(cartesian_state_vector, dtype=float)

    # Determine if input is single or batch
    if state_vector.ndim == 1:
        if state_vector.shape != (6,):
            raise ValueError(
                f"State vector must have shape (6,), got {state_vector.shape}"
            )
        state_vector = state_vector.reshape(1, 6)
        single_input: bool = True
    elif state_vector.ndim == 2:
        if state_vector.shape[1] != 6:
            raise ValueError(
                f"State vectors must have shape (N, 6), got {state_vector.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"State vector must be 1D or 2D array, got {state_vector.ndim}D"
        )

    # Extract positions and velocities: shape (N, 3)
    positions: np.ndarray = state_vector[:, 0:3]
    velocities: np.ndarray = state_vector[:, 3:6]

    # Compute norms: shape (N,)
    position_norms: np.ndarray = np.linalg.norm(positions, axis=1)
    velocity_norms: np.ndarray = np.linalg.norm(velocities, axis=1)

    # Check for degenerate orbits
    if np.any(position_norms < 1e-10):
        raise ValueError("Position vector has zero magnitude — degenerate orbit.")

    # --- Specific angular momentum ---
    angular_momentum_vectors = np.cross(positions, velocities)  # shape (N, 3)
    angular_momenta = np.linalg.norm(angular_momentum_vectors, axis=1)  # shape (N,)

    if np.any(angular_momenta < 1e-10):
        raise ValueError(
            "Angular momentum is zero — rectilinear orbit, "
            "Keplerian elements are undefined."
        )

    # --- Node vector (points toward ascending node) ---
    K = np.array([0.0, 0.0, 1.0])
    node_vectors = np.cross(K, angular_momentum_vectors)  # shape (N, 3)
    node_norms = np.linalg.norm(node_vectors, axis=1)  # shape (N,)

    # --- Eccentricity vector (points toward periapsis) ---
    # e = (v²/mu - 1/r) * r - (r·v)/mu * v
    eccentricity_vectors = (velocity_norms**2 / mu - 1.0 / position_norms)[
        :, np.newaxis
    ] * positions - (np.sum(positions * velocities, axis=1) / mu)[
        :, np.newaxis
    ] * velocities  # shape (N, 3)
    eccentricities = np.linalg.norm(eccentricity_vectors, axis=1)  # shape (N,)

    # --- Specific mechanical energy ---
    energies = 0.5 * velocity_norms**2 - mu / position_norms  # shape (N,)

    # --- Semi-major axis ---
    semi_major_axes = np.full(state_vector.shape[0], np.inf, dtype=float)
    elliptic_mask = np.abs(1.0 - eccentricities) > 1e-10
    semi_major_axes[elliptic_mask] = -mu / (2.0 * energies[elliptic_mask])

    # --- Inclination ---
    inclinations = np.arccos(
        np.clip(angular_momentum_vectors[:, 2] / angular_momenta, -1.0, 1.0)
    )  # shape (N,)

    # --- Right Ascension of the Ascending Node (RAAN / Ω) ---
    raans = np.zeros(state_vector.shape[0], dtype=float)
    equatorial_mask = node_norms > 1e-10
    raans[equatorial_mask] = np.arccos(
        np.clip(
            node_vectors[equatorial_mask, 0] / node_norms[equatorial_mask], -1.0, 1.0
        )
    )
    # Quadrant check: if node_y < 0, RAAN is in [π, 2π]
    quadrant_mask = equatorial_mask & (node_vectors[:, 1] < 0.0)
    raans[quadrant_mask] = 2.0 * np.pi - raans[quadrant_mask]

    # --- Argument of Periapsis (ω) ---
    argument_of_periapsis = np.zeros(state_vector.shape[0], dtype=float)

    # Case 1: Non-equatorial, eccentric orbit
    case1_mask = (node_norms > 1e-10) & (eccentricities > 1e-10)
    if np.any(case1_mask):
        cos_arg_peri = np.sum(
            node_vectors[case1_mask] * eccentricity_vectors[case1_mask], axis=1
        ) / (node_norms[case1_mask] * eccentricities[case1_mask])
        argument_of_periapsis[case1_mask] = np.arccos(np.clip(cos_arg_peri, -1.0, 1.0))
        # Quadrant check: if e_z < 0, ω is in [π, 2π]
        quadrant_mask1 = case1_mask & (eccentricity_vectors[:, 2] < 0.0)
        argument_of_periapsis[quadrant_mask1] = (
            2.0 * np.pi - argument_of_periapsis[quadrant_mask1]
        )

    # Case 2: Equatorial, eccentric orbit
    case2_mask = (node_norms <= 1e-10) & (eccentricities > 1e-10)
    if np.any(case2_mask):
        argument_of_periapsis[case2_mask] = np.arctan2(
            eccentricity_vectors[case2_mask, 1], eccentricity_vectors[case2_mask, 0]
        )
        # Ensure ω is in [0, 2π]
        neg_mask = case2_mask & (argument_of_periapsis < 0.0)
        argument_of_periapsis[neg_mask] += 2.0 * np.pi

    # Case 3: Circular orbit — argument of periapsis is undefined, set to 0
    # (already initialized to 0)

    # --- True Anomaly (θ / ν) ---
    true_anomalies = np.zeros(state_vector.shape[0], dtype=float)

    # Case 1: Eccentric orbit
    case1_mask = eccentricities > 1e-10
    if np.any(case1_mask):
        cos_true_anom = np.sum(
            eccentricity_vectors[case1_mask] * positions[case1_mask], axis=1
        ) / (eccentricities[case1_mask] * position_norms[case1_mask])
        true_anomalies[case1_mask] = np.arccos(np.clip(cos_true_anom, -1.0, 1.0))
        # Quadrant check: if r·v < 0, spacecraft is approaching periapsis
        rv_dot = np.sum(positions[case1_mask] * velocities[case1_mask], axis=1)
        quadrant_mask1 = case1_mask & (rv_dot < 0.0)
        true_anomalies[quadrant_mask1] = 2.0 * np.pi - true_anomalies[quadrant_mask1]

    # Case 2: Circular, non-equatorial orbit
    case2_mask = (eccentricities <= 1e-10) & (node_norms > 1e-10)
    if np.any(case2_mask):
        cos_arg_lat = np.sum(
            node_vectors[case2_mask] * positions[case2_mask], axis=1
        ) / (node_norms[case2_mask] * position_norms[case2_mask])
        true_anomalies[case2_mask] = np.arccos(np.clip(cos_arg_lat, -1.0, 1.0))
        # Quadrant check: if z < 0, true anomaly is in [π, 2π]
        quadrant_mask2 = case2_mask & (positions[:, 2] < 0.0)
        true_anomalies[quadrant_mask2] = 2.0 * np.pi - true_anomalies[quadrant_mask2]

    # Case 3: Circular, equatorial orbit
    case3_mask = (eccentricities <= 1e-10) & (node_norms <= 1e-10)
    if np.any(case3_mask):
        true_anomalies[case3_mask] = np.arctan2(
            positions[case3_mask, 1], positions[case3_mask, 0]
        )
        # Ensure θ is in [0, 2π]
        neg_mask = case3_mask & (true_anomalies < 0.0)
        true_anomalies[neg_mask] += 2.0 * np.pi

    # Assemble result: shape (N, 6)
    result = np.column_stack(
        [
            semi_major_axes,
            eccentricities,
            inclinations,
            argument_of_periapsis,
            raans,
            true_anomalies,
        ]
    )

    # Return single vector if input was single
    return result[0] if single_input else result


# ===================================================================
# Keplerian -> Cartesian
# ===================================================================


def keplerian_to_cartesian(keplerian_elements: np.ndarray, mu: float) -> np.ndarray:
    """Convert Keplerian elements to Cartesian state vector(s).

    Supports both single and batch processing of Keplerian elements.

    Parameters
    ----------
    keplerian_elements : np.ndarray
        Keplerian elements [a, e, i, omega, RAAN, theta].
        Angles in radians, semi-major axis in meters.
        - Shape (6,): Single element set
        - Shape (N, 6): Batch of N element sets
        Element ordering matches tudatpy convention.
    mu : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    np.ndarray
        Cartesian state vector(s) [x, y, z, vx, vy, vz] in m and m/s.
        - Shape (6,): If input is single element set
        - Shape (N, 6): If input is batch of N element sets

    Raises
    ------
    ValueError
        If the orbit is parabolic (infinite semi-major axis) or if
        the input shape is invalid.
    """
    elements: np.ndarray = np.asarray(keplerian_elements, dtype=float)

    # Determine if input is single or batch
    if elements.ndim == 1:
        if elements.shape != (6,):
            raise ValueError(
                f"Keplerian elements must have shape (6,), got {elements.shape}"
            )
        elements = elements.reshape(1, 6)
        single_input: bool = True
    elif elements.ndim == 2:
        if elements.shape[1] != 6:
            raise ValueError(
                f"Keplerian elements must have shape (N, 6), got {elements.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"Keplerian elements must be 1D or 2D array, got {elements.ndim}D"
        )

    # Extract elements: shape (N,)
    semi_major_axes: np.ndarray = elements[:, SEMI_MAJOR_AXIS_INDEX]
    eccentricities: np.ndarray = elements[:, ECCENTRICITY_INDEX]
    inclinations: np.ndarray = elements[:, INCLINATION_INDEX]
    arguments_of_periapsis: np.ndarray = elements[:, ARGUMENT_OF_PERIAPSIS_INDEX]
    raans: np.ndarray = elements[:, RAAN_INDEX]
    true_anomalies: np.ndarray = elements[:, TRUE_ANOMALY_INDEX]

    # Check for parabolic orbits
    if np.any(np.isinf(semi_major_axes)):
        raise ValueError("Parabolic orbits not supported in inverse conversion.")

    # Semi-latus rectum: shape (N,)
    semi_latus_rectums = semi_major_axes * (1.0 - eccentricities**2)

    # Position magnitude in perifocal frame: shape (N,)
    r_mags = semi_latus_rectums / (1.0 + eccentricities * np.cos(true_anomalies))

    # Position in perifocal frame (PQW): shape (N, 3)
    positions_perifocal = np.column_stack(
        [
            r_mags * np.cos(true_anomalies),
            r_mags * np.sin(true_anomalies),
            np.zeros(elements.shape[0]),
        ]
    )

    # Velocity in perifocal frame (PQW): shape (N, 3)
    velocities_perifocal = np.column_stack(
        [
            -np.sqrt(mu / semi_latus_rectums) * np.sin(true_anomalies),
            np.sqrt(mu / semi_latus_rectums)
            * (eccentricities + np.cos(true_anomalies)),
            np.zeros(elements.shape[0]),
        ]
    )

    # Precompute trigonometric values: shape (N,)
    cos_raan = np.cos(raans)
    sin_raan = np.sin(raans)
    cos_inclination = np.cos(inclinations)
    sin_inclination = np.sin(inclinations)
    cos_argument_of_periapsis = np.cos(arguments_of_periapsis)
    sin_argument_of_periapsis = np.sin(arguments_of_periapsis)

    # Rotation matrix elements (3-1-3 Euler angles: RAAN, i, omega)
    # Build rotation matrix for each orbit: shape (N, 3, 3)
    r11 = (
        cos_raan * cos_argument_of_periapsis
        - sin_raan * sin_argument_of_periapsis * cos_inclination
    )
    r12 = (
        -cos_raan * sin_argument_of_periapsis
        - sin_raan * cos_argument_of_periapsis * cos_inclination
    )
    r13 = sin_raan * sin_inclination

    r21 = (
        sin_raan * cos_argument_of_periapsis
        + cos_raan * sin_argument_of_periapsis * cos_inclination
    )
    r22 = (
        -sin_raan * sin_argument_of_periapsis
        + cos_raan * cos_argument_of_periapsis * cos_inclination
    )
    r23 = -cos_raan * sin_inclination

    r31 = sin_argument_of_periapsis * sin_inclination
    r32 = cos_argument_of_periapsis * sin_inclination
    r33 = cos_inclination

    # Apply rotation to positions and velocities
    # For each orbit i: inertial = R @ perifocal
    positions_inertial = np.column_stack(
        [
            r11 * positions_perifocal[:, 0]
            + r12 * positions_perifocal[:, 1]
            + r13 * positions_perifocal[:, 2],
            r21 * positions_perifocal[:, 0]
            + r22 * positions_perifocal[:, 1]
            + r23 * positions_perifocal[:, 2],
            r31 * positions_perifocal[:, 0]
            + r32 * positions_perifocal[:, 1]
            + r33 * positions_perifocal[:, 2],
        ]
    )

    velocities_inertial = np.column_stack(
        [
            r11 * velocities_perifocal[:, 0]
            + r12 * velocities_perifocal[:, 1]
            + r13 * velocities_perifocal[:, 2],
            r21 * velocities_perifocal[:, 0]
            + r22 * velocities_perifocal[:, 1]
            + r23 * velocities_perifocal[:, 2],
            r31 * velocities_perifocal[:, 0]
            + r32 * velocities_perifocal[:, 1]
            + r33 * velocities_perifocal[:, 2],
        ]
    )

    # Assemble result: shape (N, 6)
    result = np.column_stack([positions_inertial, velocities_inertial])

    # Return single vector if input was single
    return result[0] if single_input else result


# ===================================================================
# Anomaly conversions
# ===================================================================


def true_to_eccentric_anomaly(true_anomaly: float, eccentricity: float) -> float:
    """Convert true anomaly to eccentric anomaly.

    Parameters
    ----------
    true_anomaly : float
        True anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).

    Returns
    -------
    float
        Eccentric anomaly E (rad) in [0, 2π).
    """
    eccentric_anomaly = 2.0 * np.arctan2(
        np.sqrt(1.0 - eccentricity) * np.sin(true_anomaly / 2.0),
        np.sqrt(1.0 + eccentricity) * np.cos(true_anomaly / 2.0),
    )
    if eccentric_anomaly < 0.0:
        eccentric_anomaly += 2.0 * np.pi
    return eccentric_anomaly


def eccentric_to_true_anomaly(eccentric_anomaly: float, eccentricity: float) -> float:
    """Convert eccentric anomaly to true anomaly.

    Parameters
    ----------
    eccentric_anomaly : float
        Eccentric anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).

    Returns
    -------
    float
        True anomaly θ (rad) in [0, 2π).
    """
    true_anomaly = 2.0 * np.arctan2(
        np.sqrt(1.0 + eccentricity) * np.sin(eccentric_anomaly / 2.0),
        np.sqrt(1.0 - eccentricity) * np.cos(eccentric_anomaly / 2.0),
    )
    if true_anomaly < 0.0:
        true_anomaly += 2.0 * np.pi
    return true_anomaly


def eccentric_to_mean_anomaly(eccentric_anomaly: float, eccentricity: float) -> float:
    """Convert eccentric anomaly to mean anomaly (Kepler's equation).

    Parameters
    ----------
    eccentric_anomaly : float
        Eccentric anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).

    Returns
    -------
    float
        Mean anomaly M (rad).
    """
    return eccentric_anomaly - eccentricity * np.sin(eccentric_anomaly)


def mean_to_eccentric_anomaly(
    mean_anomaly: float, eccentricity: float, tol: float = 1e-12, max_iter: int = 50
) -> float:
    """Solve Kepler's equation mean_anomaly = E − e·sin(E) for eccentric anomaly E.

    Uses Newton-Raphson iteration.

    Parameters
    ----------
    mean_anomaly : float
        Mean anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).
    tol : float
        Convergence tolerance.
    max_iter : int
        Maximum number of iterations.

    Returns
    -------
    float
        Eccentric anomaly E (rad).

    Raises
    ------
    RuntimeError
        If Newton-Raphson does not converge.
    """
    # Initial guess
    if eccentricity < 0.8:
        eccentric_anomaly = mean_anomaly
    else:
        eccentric_anomaly = np.pi

    for _ in range(max_iter):
        residual = (
            eccentric_anomaly - eccentricity * np.sin(eccentric_anomaly) - mean_anomaly
        )
        residual_derivative = 1.0 - eccentricity * np.cos(eccentric_anomaly)
        delta = residual / residual_derivative
        eccentric_anomaly = eccentric_anomaly - delta
        if abs(delta) < tol:
            return eccentric_anomaly

    raise RuntimeError(
        f"Kepler's equation did not converge after {max_iter} iterations "
        f"(mean_anomaly={mean_anomaly:.10f}, eccentricity={eccentricity:.10f})"
    )


def mean_to_true_anomaly(
    mean_anomaly: float, eccentricity: float, tol: float = 1e-12
) -> float:
    """Convert mean anomaly to true anomaly via eccentric anomaly.

    Parameters
    ----------
    mean_anomaly : float
        Mean anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).
    tol : float
        Convergence tolerance for Kepler's equation.

    Returns
    -------
    float
        True anomaly θ (rad) in [0, 2π).
    """
    eccentric_anomaly = mean_to_eccentric_anomaly(mean_anomaly, eccentricity, tol=tol)
    return eccentric_to_true_anomaly(eccentric_anomaly, eccentricity)


def true_to_mean_anomaly(true_anomaly: float, eccentricity: float) -> float:
    """Convert true anomaly to mean anomaly via eccentric anomaly.

    Parameters
    ----------
    true_anomaly : float
        True anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).

    Returns
    -------
    float
        Mean anomaly M (rad).
    """
    eccentric_anomaly = true_to_eccentric_anomaly(true_anomaly, eccentricity)
    return eccentric_to_mean_anomaly(eccentric_anomaly, eccentricity)


# ===================================================================
# Utility: mean motion <-> semi-major axis
# ===================================================================


def mean_motion_to_semi_major_axis(
    mean_motion_rev_per_day: float, mu: float = MU_EARTH
) -> float:
    """Convert mean motion (rev/day) to semi-major axis (m).

    Uses Kepler's third law: a = (mu / n^2)^(1/3).

    Parameters
    ----------
    mean_motion_rev_per_day : float
        Mean motion in revolutions per day.
    mu : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    float
        Semi-major axis in meters.
    """
    n_rad_per_sec = mean_motion_rev_per_day * 2.0 * np.pi / 86400.0
    return (mu / n_rad_per_sec**2) ** (1.0 / 3.0)


def semi_major_axis_to_mean_motion(
    semi_major_axis: float, mu: float = MU_EARTH
) -> float:
    """Convert semi-major axis (m) to mean motion (rev/day).

    Uses Kepler's third law: n = sqrt(mu / a^3).

    Parameters
    ----------
    semi_major_axis : float
        Semi-major axis in meters.
    mu : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    float
        Mean motion in revolutions per day.
    """
    n_rad_per_sec = np.sqrt(mu / semi_major_axis**3)
    return n_rad_per_sec * 86400.0 / (2.0 * np.pi)


# ===================================================================
# TLE -> Osculating Keplerian (with J2 short-period corrections)
# ===================================================================


def compute_brouwer_short_period_corrections(
    mean_keplerian_elements: np.ndarray,
    R_e: float = RE_EARTH,
    J2: float = J2_EARTH,
) -> np.ndarray:
    """Compute Brouwer first-order J2 short-period corrections.

    Converts mean Keplerian elements (as used in TLE/SGP4) to osculating
    elements by adding the J2 short-period perturbation terms.

    Supports both single and batch processing of element sets.

    The formulas follow Brouwer (1959) / Kozai (1959) and are consistent
    with the SGP4 mean-to-osculating transformation.

    Parameters
    ----------
    mean_keplerian_elements : np.ndarray
        Mean Keplerian element vector(s) [a, e, i, omega, RAAN, M].
        - Shape (6,): Single element set
        - Shape (N, 6): Batch of N element sets
        Element ordering follows the predefined Kepler index constants.
    R_e : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient.

    Returns
    -------
    np.ndarray
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta].
        - Shape (6,): If input is single element set
        - Shape (N, 6): If input is batch of N element sets
        Element ordering follows the predefined Kepler index constants.

    References
    ----------
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    Hoots, F.R. & Roehrich, R.L. "Spacetrack Report No. 3", 1980.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Ch. 9.
    """
    mean_elements = np.asarray(mean_keplerian_elements, dtype=float)

    # Determine if input is single or batch
    if mean_elements.ndim == 1:
        if mean_elements.shape != (6,):
            raise ValueError(
                f"Mean Keplerian elements must have shape (6,), got {mean_elements.shape}"
            )
        mean_elements = mean_elements.reshape(1, 6)
        single_input = True
    elif mean_elements.ndim == 2:
        if mean_elements.shape[1] != 6:
            raise ValueError(
                f"Mean Keplerian elements must have shape (N, 6), got {mean_elements.shape}"
            )
        single_input = False
    else:
        raise ValueError(
            f"Mean Keplerian elements must be 1D or 2D array, got {mean_elements.ndim}D"
        )

    # Extract elements: shape (N,)
    mean_semi_major_axes = mean_elements[:, SEMI_MAJOR_AXIS_INDEX]
    mean_eccentricities = mean_elements[:, ECCENTRICITY_INDEX]
    mean_inclinations = mean_elements[:, INCLINATION_INDEX]
    mean_arguments_of_periapsis = mean_elements[:, ARGUMENT_OF_PERIAPSIS_INDEX]
    mean_raans = mean_elements[:, RAAN_INDEX]
    mean_anomalies = mean_elements[:, MEAN_ANOMALY_INDEX]

    # Semi-latus rectum and related quantities: shape (N,)
    p_means = mean_semi_major_axes * (1.0 - mean_eccentricities**2)
    etas = np.sqrt(1.0 - mean_eccentricities**2)

    # Solve Kepler's equation for mean elements: M -> E -> theta
    # Note: These are scalar functions, so we need to vectorize them
    E_means = np.array(
        [
            mean_to_eccentric_anomaly(mean_anomalies[i], mean_eccentricities[i])
            for i in range(mean_elements.shape[0])
        ]
    )
    theta_means = np.array(
        [
            eccentric_to_true_anomaly(E_means[i], mean_eccentricities[i])
            for i in range(mean_elements.shape[0])
        ]
    )

    # Trigonometric quantities: shape (N,)
    cos_i = np.cos(mean_inclinations)
    sin_i = np.sin(mean_inclinations)
    cos_theta = np.cos(theta_means)
    sin_theta = np.sin(theta_means)

    # Argument of latitude u = omega + theta: shape (N,)
    u_means = mean_arguments_of_periapsis + theta_means
    cos_2u = np.cos(2.0 * u_means)
    sin_2u = np.sin(2.0 * u_means)

    # J2 perturbation scale factor: shape (N,)
    gammas = 0.5 * J2 * (R_e / p_means) ** 2

    # Convenience: shape (N,)
    one_plus_e_cos_f = 1.0 + mean_eccentricities * cos_theta
    sin2i = sin_i**2
    cos2i = cos_i**2

    # Short-period correction to semi-major axis: shape (N,)
    a_over_r = one_plus_e_cos_f / (1.0 - mean_eccentricities**2)
    delta_a_over_a = gammas * (
        (1.0 - 3.0 * cos2i) * (3.0 * a_over_r - 1.0 / etas - 1.0)
        + 3.0 * sin2i * a_over_r * cos_2u
    )
    osculating_semi_major_axes = mean_semi_major_axes * (1.0 + delta_a_over_a)

    # Short-period correction to eccentricity: shape (N,)
    two_omegas = 2.0 * mean_arguments_of_periapsis
    delta_e = (
        gammas
        * etas
        * sin2i
        * (
            np.cos(two_omegas + theta_means)
            + 0.5 * mean_eccentricities * np.cos(two_omegas)
            + 0.5 * mean_eccentricities * np.cos(two_omegas + 2.0 * theta_means)
        )
    )
    osculating_eccentricities = mean_eccentricities + delta_e

    # Short-period correction to inclination: shape (N,)
    delta_inclination = 0.5 * gammas * np.sin(2.0 * mean_inclinations) * cos_2u
    osculating_inclinations = mean_inclinations + delta_inclination

    # Short-period correction to RAAN: shape (N,)
    raan_corrections = -gammas * cos_i * sin_2u
    osculating_raans = mean_raans + raan_corrections

    # Short-period correction to argument of periapsis: shape (N,)
    argument_of_periapsis_corrections = gammas * (
        (5.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * etas)
        + (5.0 * cos2i - 1.0)
        * mean_eccentricities
        * np.sin(2.0 * u_means - theta_means)
        / (2.0 * etas)
        - (1.0 - 3.0 * cos2i) * mean_eccentricities * sin_theta / etas
    )

    # Short-period correction to argument of latitude: shape (N,)
    argument_of_latitude_corrections = gammas * (
        (7.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * etas)
    )

    # Osculating argument of latitude: shape (N,)
    osculating_arguments_of_latitude = u_means + argument_of_latitude_corrections

    # Osculating argument of periapsis: shape (N,)
    osculating_arguments_of_periapsis = (
        mean_arguments_of_periapsis + argument_of_periapsis_corrections
    )

    # Osculating true anomaly: shape (N,)
    osculating_true_anomalies = (
        osculating_arguments_of_latitude - osculating_arguments_of_periapsis
    )

    # Normalize angles to [0, 2pi): shape (N,)
    osculating_arguments_of_periapsis = osculating_arguments_of_periapsis % (
        2.0 * np.pi
    )
    neg_mask = osculating_arguments_of_periapsis < 0.0
    osculating_arguments_of_periapsis[neg_mask] += 2.0 * np.pi

    osculating_true_anomalies = osculating_true_anomalies % (2.0 * np.pi)
    neg_mask = osculating_true_anomalies < 0.0
    osculating_true_anomalies[neg_mask] += 2.0 * np.pi

    # Clamp osculating eccentricity: shape (N,)
    osculating_eccentricities = np.clip(osculating_eccentricities, 0.0, 0.9999999)

    # Assemble result: shape (N, 6)
    result = np.column_stack(
        [
            osculating_semi_major_axes,
            osculating_eccentricities,
            osculating_inclinations,
            osculating_arguments_of_periapsis,
            osculating_raans,
            osculating_true_anomalies,
        ]
    )

    # Return single vector if input was single
    return result[0] if single_input else result


def osculating_to_mean_keplerian(
    osculating_keplerian_elements: np.ndarray,
    R_e: float = RE_EARTH,
    J2: float = J2_EARTH,
    max_iter: int = 20,
    tol: float = 1e-12,
) -> np.ndarray:
    """Convert osculating Keplerian elements to mean (Brouwer) elements.

    Uses iterative inversion of the Brouwer short-period corrections.
    Starting from the osculating elements as an initial guess for the mean
    elements, repeatedly applies the forward correction and adjusts until
    convergence.

    Parameters
    ----------
    osculating_keplerian_elements : np.ndarray, shape (6,)
        Osculating Keplerian element vector [a, e, i, omega, RAAN, theta].
        Element ordering follows the predefined Kepler index constants.
    R_e : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient.
    max_iter : int
        Maximum iterations for convergence.
    tol : float
        Convergence tolerance on semi-major axis (m).

    Returns
    -------
    np.ndarray, shape (6,)
        Mean Keplerian elements [a, e, i, omega, RAAN, M].
        Angles are in radians and semi-major axis is in meters.
    """
    osculating_elements = np.asarray(osculating_keplerian_elements, dtype=float)
    if osculating_elements.shape != (6,):
        raise ValueError(
            f"Osculating Keplerian elements must have shape (6,), got {osculating_elements.shape}"
        )

    osculating_semi_major_axis = osculating_elements[SEMI_MAJOR_AXIS_INDEX]
    osculating_eccentricity = osculating_elements[ECCENTRICITY_INDEX]
    osculating_inclination = osculating_elements[INCLINATION_INDEX]
    osculating_argument_of_periapsis = osculating_elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    osculating_raan = osculating_elements[RAAN_INDEX]
    osculating_true_anomaly = osculating_elements[TRUE_ANOMALY_INDEX]

    # Convert osculating true anomaly to an initial mean anomaly guess
    initial_mean_anomaly = true_to_mean_anomaly(
        osculating_true_anomaly, osculating_eccentricity
    )

    # Initial guess: mean = osculating
    mean_semi_major_axis = osculating_semi_major_axis
    mean_eccentricity = osculating_eccentricity
    mean_inclination = osculating_inclination
    mean_raan = osculating_raan
    mean_argument_of_periapsis = osculating_argument_of_periapsis
    mean_anomaly_estimate = initial_mean_anomaly

    for _ in range(max_iter):
        # Apply forward correction
        osc = compute_brouwer_short_period_corrections(
            np.array(
                [
                    mean_semi_major_axis,
                    mean_eccentricity,
                    mean_inclination,
                    mean_argument_of_periapsis,
                    mean_raan,
                    mean_anomaly_estimate,
                ],
                dtype=float,
            ),
            R_e=R_e,
            J2=J2,
        )

        # Compute residuals (osculating_target - osculating_from_mean)
        delta_semimajor = osculating_semi_major_axis - osc[SEMI_MAJOR_AXIS_INDEX]
        delta_eccentricity = osculating_eccentricity - osc[ECCENTRICITY_INDEX]
        delta_inclination = osculating_inclination - osc[INCLINATION_INDEX]
        delta_raan = osculating_raan - osc[RAAN_INDEX]
        delta_argument_of_periapsis = (
            osculating_argument_of_periapsis - osc[ARGUMENT_OF_PERIAPSIS_INDEX]
        )
        delta_true_anomaly = osculating_true_anomaly - osc[TRUE_ANOMALY_INDEX]

        # Wrap angle differences to [-pi, pi]
        delta_raan = (delta_raan + np.pi) % (2.0 * np.pi) - np.pi
        delta_argument_of_periapsis = (delta_argument_of_periapsis + np.pi) % (
            2.0 * np.pi
        ) - np.pi
        delta_true_anomaly = (delta_true_anomaly + np.pi) % (2.0 * np.pi) - np.pi

        # Update mean elements
        mean_semi_major_axis += delta_semimajor
        mean_eccentricity += delta_eccentricity
        mean_inclination += delta_inclination
        mean_raan += delta_raan
        mean_argument_of_periapsis += delta_argument_of_periapsis

        # Update mean anomaly from corrected true anomaly
        target_theta_for_mean = osculating_true_anomaly - (
            osc[TRUE_ANOMALY_INDEX]
            - mean_to_true_anomaly(mean_anomaly_estimate, mean_eccentricity)
        )
        mean_anomaly_estimate = true_to_mean_anomaly(
            target_theta_for_mean, mean_eccentricity
        )

        # Check convergence
        if abs(delta_semimajor) < tol and abs(delta_eccentricity) < 1e-14:
            break

    # Normalize angles
    mean_raan = mean_raan % (2.0 * np.pi)
    if mean_raan < 0.0:
        mean_raan += 2.0 * np.pi
    mean_argument_of_periapsis = mean_argument_of_periapsis % (2.0 * np.pi)
    if mean_argument_of_periapsis < 0.0:
        mean_argument_of_periapsis += 2.0 * np.pi
    mean_anomaly_estimate = mean_anomaly_estimate % (2.0 * np.pi)
    if mean_anomaly_estimate < 0.0:
        mean_anomaly_estimate += 2.0 * np.pi

    return np.array(
        [
            mean_semi_major_axis,
            mean_eccentricity,
            mean_inclination,
            mean_argument_of_periapsis,
            mean_raan,
            mean_anomaly_estimate,
        ],
        dtype=float,
    )
