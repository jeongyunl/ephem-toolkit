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

import numpy as np
import common.consts as consts

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


def cartesian_to_keplerian(
    cartesian_state_vector: np.ndarray, mu_m3_s2: float
) -> np.ndarray:
    """Convert Cartesian state vector(s) to osculating Keplerian elements.

    Supports both single and batch processing of state vectors.

    Parameters
    ----------
    cartesian_state_vector : np.ndarray
        Cartesian state vector(s) in meters and m/s.
        - Shape (6,): Single state vector [x, y, z, vx, vy, vz]
        - Shape (N, 6): Batch of N state vectors
    mu_m3_s2 : float
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
    angular_momentum_vectors: np.ndarray = np.cross(
        positions, velocities
    )  # shape (N, 3)
    angular_momenta: np.ndarray = np.linalg.norm(
        angular_momentum_vectors, axis=1
    )  # shape (N,)

    if np.any(angular_momenta < 1e-10):
        raise ValueError(
            "Angular momentum is zero — rectilinear orbit, "
            "Keplerian elements are undefined."
        )

    # --- Node vector (points toward ascending node) ---
    z_axis_unit_vector: np.ndarray = np.array([0.0, 0.0, 1.0])
    node_vectors: np.ndarray = np.cross(
        z_axis_unit_vector, angular_momentum_vectors
    )  # shape (N, 3)
    node_norms: np.ndarray = np.linalg.norm(node_vectors, axis=1)  # shape (N,)

    # --- Eccentricity vector (points toward periapsis) ---
    # e = (v²/mu - 1/r) * r - (r·v)/mu * v
    eccentricity_vectors: np.ndarray = (
        velocity_norms**2 / mu_m3_s2 - 1.0 / position_norms
    )[:, np.newaxis] * positions - (np.sum(positions * velocities, axis=1) / mu_m3_s2)[
        :, np.newaxis
    ] * velocities  # shape (N, 3)
    eccentricities: np.ndarray = np.linalg.norm(
        eccentricity_vectors, axis=1
    )  # shape (N,)

    # --- Specific mechanical energy ---
    energies: np.ndarray = (
        0.5 * velocity_norms**2 - mu_m3_s2 / position_norms
    )  # shape (N,)

    # --- Semi-major axis ---
    semi_major_axes: np.ndarray = np.full(state_vector.shape[0], np.inf, dtype=float)
    elliptic_mask: np.ndarray = np.abs(1.0 - eccentricities) > 1e-10
    semi_major_axes[elliptic_mask] = -mu_m3_s2 / (2.0 * energies[elliptic_mask])

    # --- Inclination ---
    inclinations: np.ndarray = np.arccos(
        np.clip(angular_momentum_vectors[:, 2] / angular_momenta, -1.0, 1.0)
    )  # shape (N,)

    # --- Right Ascension of the Ascending Node (RAAN / Ω) ---
    raans: np.ndarray = np.zeros(state_vector.shape[0], dtype=float)
    equatorial_mask: np.ndarray = node_norms > 1e-10
    raans[equatorial_mask] = np.arccos(
        np.clip(
            node_vectors[equatorial_mask, 0] / node_norms[equatorial_mask], -1.0, 1.0
        )
    )
    # Quadrant check: if node_y < 0, RAAN is in [π, 2π]
    quadrant_mask: np.ndarray = equatorial_mask & (node_vectors[:, 1] < 0.0)
    raans[quadrant_mask] = 2.0 * np.pi - raans[quadrant_mask]

    # --- Argument of Periapsis (ω) ---
    argument_of_periapsis: np.ndarray = np.zeros(state_vector.shape[0], dtype=float)

    # Case 1: Non-equatorial, eccentric orbit
    case1_mask: np.ndarray = (node_norms > 1e-10) & (eccentricities > 1e-10)
    if np.any(case1_mask):
        cos_arg_peri: np.ndarray = np.sum(
            node_vectors[case1_mask] * eccentricity_vectors[case1_mask], axis=1
        ) / (node_norms[case1_mask] * eccentricities[case1_mask])
        argument_of_periapsis[case1_mask] = np.arccos(np.clip(cos_arg_peri, -1.0, 1.0))
        # Quadrant check: if e_z < 0, ω is in [π, 2π]
        quadrant_mask1: np.ndarray = case1_mask & (eccentricity_vectors[:, 2] < 0.0)
        argument_of_periapsis[quadrant_mask1] = (
            2.0 * np.pi - argument_of_periapsis[quadrant_mask1]
        )

    # Case 2: Equatorial, eccentric orbit
    case2_mask: np.ndarray = (node_norms <= 1e-10) & (eccentricities > 1e-10)
    if np.any(case2_mask):
        argument_of_periapsis[case2_mask] = np.arctan2(
            eccentricity_vectors[case2_mask, 1], eccentricity_vectors[case2_mask, 0]
        )
        # Ensure ω is in [0, 2π]
        neg_mask: np.ndarray = case2_mask & (argument_of_periapsis < 0.0)
        argument_of_periapsis[neg_mask] += 2.0 * np.pi

    # Case 3: Circular orbit — argument of periapsis is undefined, set to 0
    # (already initialized to 0)

    # --- True Anomaly (θ / ν) ---
    true_anomalies: np.ndarray = np.zeros(state_vector.shape[0], dtype=float)

    # Case 1: Eccentric orbit
    case1_mask = eccentricities > 1e-10
    if np.any(case1_mask):
        cos_true_anom: np.ndarray = np.sum(
            eccentricity_vectors[case1_mask] * positions[case1_mask], axis=1
        ) / (eccentricities[case1_mask] * position_norms[case1_mask])
        true_anomalies[case1_mask] = np.arccos(np.clip(cos_true_anom, -1.0, 1.0))
        # Quadrant check: if r·v < 0, spacecraft is approaching periapsis
        rv_dot: np.ndarray = np.sum(
            positions[case1_mask] * velocities[case1_mask], axis=1
        )
        quadrant_mask1: np.ndarray = case1_mask & (rv_dot < 0.0)
        true_anomalies[quadrant_mask1] = 2.0 * np.pi - true_anomalies[quadrant_mask1]

    # Case 2: Circular, non-equatorial orbit
    case2_mask = (eccentricities <= 1e-10) & (node_norms > 1e-10)
    if np.any(case2_mask):
        cos_arg_lat: np.ndarray = np.sum(
            node_vectors[case2_mask] * positions[case2_mask], axis=1
        ) / (node_norms[case2_mask] * position_norms[case2_mask])
        true_anomalies[case2_mask] = np.arccos(np.clip(cos_arg_lat, -1.0, 1.0))
        # Quadrant check: if z < 0, true anomaly is in [π, 2π]
        quadrant_mask2: np.ndarray = case2_mask & (positions[:, 2] < 0.0)
        true_anomalies[quadrant_mask2] = 2.0 * np.pi - true_anomalies[quadrant_mask2]

    # Case 3: Circular, equatorial orbit
    case3_mask: np.ndarray = (eccentricities <= 1e-10) & (node_norms <= 1e-10)
    if np.any(case3_mask):
        true_anomalies[case3_mask] = np.arctan2(
            positions[case3_mask, 1], positions[case3_mask, 0]
        )
        # Ensure θ is in [0, 2π]
        neg_mask = case3_mask & (true_anomalies < 0.0)
        true_anomalies[neg_mask] += 2.0 * np.pi

    # Assemble result: shape (N, 6)
    result: np.ndarray = np.column_stack(
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


def keplerian_to_cartesian(
    keplerian_elements: np.ndarray,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
) -> np.ndarray:
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
    mu_m3_s2 : float
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
    semi_latus_rectums: np.ndarray = semi_major_axes * (1.0 - eccentricities**2)

    # Position magnitude in perifocal frame: shape (N,)
    position_magnitudes: np.ndarray = semi_latus_rectums / (
        1.0 + eccentricities * np.cos(true_anomalies)
    )

    # Position in perifocal frame (PQW): shape (N, 3)
    positions_perifocal: np.ndarray = np.column_stack(
        [
            position_magnitudes * np.cos(true_anomalies),
            position_magnitudes * np.sin(true_anomalies),
            np.zeros(elements.shape[0]),
        ]
    )

    # Velocity in perifocal frame (PQW): shape (N, 3)
    velocities_perifocal: np.ndarray = np.column_stack(
        [
            -np.sqrt(mu_m3_s2 / semi_latus_rectums) * np.sin(true_anomalies),
            np.sqrt(mu_m3_s2 / semi_latus_rectums)
            * (eccentricities + np.cos(true_anomalies)),
            np.zeros(elements.shape[0]),
        ]
    )

    # Precompute trigonometric values: shape (N,)
    cos_raan: np.ndarray = np.cos(raans)
    sin_raan: np.ndarray = np.sin(raans)
    cos_inclination: np.ndarray = np.cos(inclinations)
    sin_inclination: np.ndarray = np.sin(inclinations)
    cos_argument_of_periapsis: np.ndarray = np.cos(arguments_of_periapsis)
    sin_argument_of_periapsis: np.ndarray = np.sin(arguments_of_periapsis)

    # Rotation matrix elements (3-1-3 Euler angles: RAAN, i, omega)
    # Build rotation matrix for each orbit: shape (N, 3, 3)
    r11: np.ndarray = (
        cos_raan * cos_argument_of_periapsis
        - sin_raan * sin_argument_of_periapsis * cos_inclination
    )
    r12: np.ndarray = (
        -cos_raan * sin_argument_of_periapsis
        - sin_raan * cos_argument_of_periapsis * cos_inclination
    )
    r13: np.ndarray = sin_raan * sin_inclination

    r21: np.ndarray = (
        sin_raan * cos_argument_of_periapsis
        + cos_raan * sin_argument_of_periapsis * cos_inclination
    )
    r22: np.ndarray = (
        -sin_raan * sin_argument_of_periapsis
        + cos_raan * cos_argument_of_periapsis * cos_inclination
    )
    r23: np.ndarray = -cos_raan * sin_inclination

    r31: np.ndarray = sin_argument_of_periapsis * sin_inclination
    r32: np.ndarray = cos_argument_of_periapsis * sin_inclination
    r33: np.ndarray = cos_inclination

    # Apply rotation to positions and velocities
    # For each orbit i: inertial = R @ perifocal
    positions_inertial: np.ndarray = np.column_stack(
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

    velocities_inertial: np.ndarray = np.column_stack(
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
    result: np.ndarray = np.column_stack([positions_inertial, velocities_inertial])

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
    eccentric_anomaly: float = 2.0 * np.arctan2(
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
        True anomaly θ (rad) in [-π, π].
    """
    # Use the half-angle formula with arctan2 for numerical stability
    # This naturally returns values in [-π, π] matching tudatpy's convention
    true_anomaly: float = 2.0 * np.arctan2(
        np.sqrt(1.0 + eccentricity) * np.sin(eccentric_anomaly / 2.0),
        np.sqrt(1.0 - eccentricity) * np.cos(eccentric_anomaly / 2.0),
    )
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
    mean_anomaly: float, eccentricity: float, tol: float = 1e-14, max_iter: int = 100
) -> float:
    """Solve Kepler's equation mean_anomaly = E − e·sin(E) for eccentric anomaly E.

    Uses Newton-Raphson iteration with improved initial guess and convergence.

    Parameters
    ----------
    mean_anomaly : float
        Mean anomaly (rad).
    eccentricity : float
        Eccentricity (0 ≤ eccentricity < 1).
    tol : float
        Convergence tolerance (default: 1e-14 for high precision).
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
    # Improved initial guess based on Vallado's method
    # Normalize mean anomaly to [-π, π] for better convergence
    normalized_mean_anomaly: float = mean_anomaly % (2.0 * np.pi)
    if normalized_mean_anomaly > np.pi:
        normalized_mean_anomaly = normalized_mean_anomaly - 2.0 * np.pi

    # Initial guess
    if eccentricity < 0.8:
        eccentric_anomaly: float = normalized_mean_anomaly + eccentricity * np.sin(
            normalized_mean_anomaly
        )
    else:
        eccentric_anomaly = np.pi if normalized_mean_anomaly > 0 else -np.pi

    for _ in range(max_iter):
        sin_eccentric_anomaly: float = np.sin(eccentric_anomaly)
        cos_eccentric_anomaly: float = np.cos(eccentric_anomaly)

        # Kepler's equation residual: f(E) = E - e*sin(E) - M
        residual: float = (
            eccentric_anomaly
            - eccentricity * sin_eccentric_anomaly
            - normalized_mean_anomaly
        )

        # Derivative: f'(E) = 1 - e*cos(E)
        residual_derivative: float = 1.0 - eccentricity * cos_eccentric_anomaly

        # Newton-Raphson update
        delta: float = residual / residual_derivative
        eccentric_anomaly = eccentric_anomaly - delta

        # Check convergence
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
        True anomaly θ (rad) in [-π, π].
    """
    eccentric_anomaly: float = mean_to_eccentric_anomaly(
        mean_anomaly, eccentricity, tol=tol
    )
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
    eccentric_anomaly: float = true_to_eccentric_anomaly(true_anomaly, eccentricity)
    return eccentric_to_mean_anomaly(eccentric_anomaly, eccentricity)


# ===================================================================
# Utility: mean motion <-> semi-major axis
# ===================================================================


def mean_motion_to_semi_major_axis(
    mean_motion_rev_per_day: float,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
) -> float:
    """Convert mean motion (rev/day) to semi-major axis (m).

    Uses Kepler's third law: a = (mu / n²)^(1/3).

    Parameters
    ----------
    mean_motion_rev_per_day : float
        Mean motion in revolutions per day.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    float
        Semi-major axis in meters.
    """
    n_rad_per_sec: float = mean_motion_rev_per_day * 2.0 * np.pi / 86400.0
    return (mu_m3_s2 / n_rad_per_sec**2) ** (1.0 / 3.0)


def semi_major_axis_to_mean_motion(
    semi_major_axis_m: float,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
) -> float:
    """Convert semi-major axis (m) to mean motion (rev/day).

    Uses Kepler's third law: n = sqrt(mu / a³).

    Parameters
    ----------
    semi_major_axis_m : float
        Semi-major axis (m).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    float
        Mean motion in revolutions per day.
    """
    n_rad_per_sec: float = np.sqrt(mu_m3_s2 / semi_major_axis_m**3)
    return n_rad_per_sec * 86400.0 / (2.0 * np.pi)


def propagate_kepler(
    keplerian_elements: np.ndarray,
    time_elapsed_s: float,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
) -> np.ndarray:
    """Propagate Keplerian elements forward in time using the two-body solution.

    In the two-body problem, the orbital elements (a, e, i, ω, Ω) remain constant,
    and only the true anomaly (or mean anomaly) changes with time. This function
    computes the new true anomaly at the given elapsed time.

    Parameters
    ----------
    keplerian_elements : np.ndarray
        Keplerian elements [a, e, i, omega, RAAN, theta].
        Angles in radians, semi-major axis in meters.
        - Shape (6,): Single element set
        - Shape (6, 1): Column vector (as used by tudatpy)
        - Shape (N, 6): Batch of N element sets
    time_elapsed_s : float
        Time elapsed since the initial epoch (s).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    np.ndarray
        Propagated Keplerian elements [a, e, i, omega, RAAN, theta].
        Same shape as input.

    Notes
    -----
    The propagation uses the mean motion to compute the change in mean anomaly,
    then converts back to true anomaly. This is equivalent to solving Kepler's
    problem for the two-body case.

    References
    ----------
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 3.
    """
    elements: np.ndarray = np.asarray(keplerian_elements, dtype=float)
    original_shape: tuple[int, ...] = elements.shape

    # Normalize to (N, 6) shape for processing
    if elements.ndim == 1:
        if elements.shape != (6,):
            raise ValueError(
                f"Keplerian elements must have shape (6,), got {elements.shape}"
            )
        elements = elements.reshape(1, 6)
    elif elements.ndim == 2:
        if elements.shape[1] == 1 and elements.shape[0] == 6:
            # Handle column vector (6, 1) from tudatpy
            elements = elements.T  # Convert to (1, 6)
        elif elements.shape[1] != 6:
            raise ValueError(
                f"Keplerian elements must have shape (N, 6), got {elements.shape}"
            )
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

    # Compute mean motion (rad/s) from semi-major axis using Kepler's third law
    # n = sqrt(mu / a³)
    mean_motions: np.ndarray = np.sqrt(mu_m3_s2 / semi_major_axes**3)

    # Convert initial true anomaly to mean anomaly
    initial_mean_anomalies: np.ndarray = np.array(
        [
            true_to_mean_anomaly(true_anomalies[i], eccentricities[i])
            for i in range(elements.shape[0])
        ]
    )

    # Compute new mean anomaly at elapsed time
    # M(t) = M(0) + n * t
    new_mean_anomalies: np.ndarray = (
        initial_mean_anomalies + mean_motions * time_elapsed_s
    )

    # Normalize mean anomalies to [0, 2π)
    new_mean_anomalies = new_mean_anomalies % (2.0 * np.pi)

    # Convert new mean anomaly back to true anomaly
    new_true_anomalies: np.ndarray = np.array(
        [
            mean_to_true_anomaly(new_mean_anomalies[i], eccentricities[i])
            for i in range(elements.shape[0])
        ]
    )

    # Assemble propagated elements: shape (N, 6)
    propagated_elements: np.ndarray = np.column_stack(
        [
            semi_major_axes,
            eccentricities,
            inclinations,
            arguments_of_periapsis,
            raans,
            new_true_anomalies,
        ]
    )

    # Restore original shape
    if original_shape == (6,):
        return propagated_elements[0]
    elif original_shape == (6, 1):
        return propagated_elements.T
    else:
        return propagated_elements
