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

Reference:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 4.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Algorithm 9.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from common.tle import Tle

# ===================================================================
# Constants
# ===================================================================

MU_EARTH: float = 3.986004418e14
"""Earth gravitational parameter (m³/s²), WGS-84."""

RE_EARTH: float = 6378137.0
"""Earth equatorial radius (m), WGS-84."""

J2_EARTH: float = 1.08262668e-3
"""Earth J2 zonal harmonic coefficient, WGS-84."""


# ===================================================================
# Keplerian element indices (matches tudatpy convention)
# ===================================================================

SEMI_MAJOR_AXIS_INDEX: int = 0
ECCENTRICITY_INDEX: int = 1
INCLINATION_INDEX: int = 2
ARGUMENT_OF_PERIAPSIS_INDEX: int = 3
RAAN_INDEX: int = 4
TRUE_ANOMALY_INDEX: int = 5


# ===================================================================
# Cartesian -> Keplerian
# ===================================================================


def cartesian_to_keplerian(cartesian_state_vector: np.ndarray, mu: float) -> np.ndarray:
    """Convert a Cartesian state vector to osculating Keplerian elements.

    Parameters
    ----------
    cartesian_state_vector : np.ndarray, shape (6,)
        Cartesian state vector [x, y, z, vx, vy, vz].
        Position in meters, velocity in m/s.
    mu : float
        Gravitational parameter of the central body (m³/s²).

    Returns
    -------
    np.ndarray, shape (6,)
        Keplerian elements [a, e, i, omega, RAAN, theta].
        Angles in radians, semi-major axis in meters.
        Element ordering matches tudatpy convention.

    Raises
    ------
    ValueError
        If the state vector does not have 6 elements or if the orbit is
        degenerate (zero angular momentum).
    """
    state_vector = np.asarray(cartesian_state_vector, dtype=float)
    if state_vector.shape != (6,):
        raise ValueError(f"State vector must have shape (6,), got {state_vector.shape}")

    position_vector = state_vector[0:3]
    velocity_vector = state_vector[3:6]

    position_norm = np.linalg.norm(position_vector)
    velocity_norm = np.linalg.norm(velocity_vector)

    if position_norm < 1e-10:
        raise ValueError("Position vector has zero magnitude — degenerate orbit.")

    # --- Specific angular momentum ---
    angular_momentum_vector = np.cross(position_vector, velocity_vector)
    angular_momentum = np.linalg.norm(angular_momentum_vector)

    if angular_momentum < 1e-10:
        raise ValueError(
            "Angular momentum is zero — rectilinear orbit, "
            "Keplerian elements are undefined."
        )

    # --- Node vector (points toward ascending node) ---
    K = np.array([0.0, 0.0, 1.0])
    node_vector = np.cross(K, angular_momentum_vector)
    node_norm = np.linalg.norm(node_vector)

    # --- Eccentricity vector (points toward periapsis) ---
    eccentricity_vector = (
        (velocity_norm**2 - mu / position_norm) * position_vector
        - np.dot(position_vector, velocity_vector) * velocity_vector
    ) / mu
    eccentricity = np.linalg.norm(eccentricity_vector)

    # --- Specific mechanical energy ---
    energy = 0.5 * velocity_norm**2 - mu / position_norm

    # --- Semi-major axis ---
    if abs(1.0 - eccentricity) > 1e-10:  # elliptic or hyperbolic
        semi_major_axis = -mu / (2.0 * energy)
    else:
        # Parabolic orbit — semi-major axis is undefined (infinite)
        semi_major_axis = np.inf

    # --- Inclination ---
    inclination = np.arccos(
        np.clip(angular_momentum_vector[2] / angular_momentum, -1.0, 1.0)
    )

    # --- Right Ascension of the Ascending Node (RAAN / Ω) ---
    if node_norm > 1e-10:
        raan = np.arccos(np.clip(node_vector[0] / node_norm, -1.0, 1.0))
        if node_vector[1] < 0.0:
            raan = 2.0 * np.pi - raan
    else:
        # Equatorial orbit — RAAN is undefined, conventionally set to 0
        raan = 0.0

    # --- Argument of Periapsis (ω) ---
    if node_norm > 1e-10 and eccentricity > 1e-10:
        cos_argument_of_periapsis = np.dot(node_vector, eccentricity_vector) / (
            node_norm * eccentricity
        )
        argument_of_periapsis = np.arccos(np.clip(cos_argument_of_periapsis, -1.0, 1.0))
        if eccentricity_vector[2] < 0.0:
            argument_of_periapsis = 2.0 * np.pi - argument_of_periapsis
    elif eccentricity > 1e-10:
        # Equatorial orbit with nonzero eccentricity:
        # use longitude of periapsis (angle from x-axis to eccentricity_vector)
        argument_of_periapsis = np.arctan2(
            eccentricity_vector[1], eccentricity_vector[0]
        )
        if argument_of_periapsis < 0.0:
            argument_of_periapsis += 2.0 * np.pi
    else:
        # Circular orbit — argument of periapsis is undefined, set to 0
        argument_of_periapsis = 0.0

    # --- True Anomaly (θ / ν) ---
    if eccentricity > 1e-10:
        cos_true_anomaly = np.dot(eccentricity_vector, position_vector) / (
            eccentricity * position_norm
        )
        true_anomaly = np.arccos(np.clip(cos_true_anomaly, -1.0, 1.0))
        # Quadrant check: if r·v < 0, spacecraft is approaching periapsis
        if np.dot(position_vector, velocity_vector) < 0.0:
            true_anomaly = 2.0 * np.pi - true_anomaly
    elif node_norm > 1e-10:
        # Circular, non-equatorial: use argument of latitude (u = ω + θ)
        cos_argument_of_latitude = np.dot(node_vector, position_vector) / (
            node_norm * position_norm
        )
        true_anomaly = np.arccos(np.clip(cos_argument_of_latitude, -1.0, 1.0))
        if position_vector[2] < 0.0:
            true_anomaly = 2.0 * np.pi - true_anomaly
    else:
        # Circular, equatorial: use true longitude (l = Ω + ω + θ)
        true_anomaly = np.arctan2(position_vector[1], position_vector[0])
        if true_anomaly < 0.0:
            true_anomaly += 2.0 * np.pi

    # Return in tudatpy order: [a, e, i, omega, RAAN, theta]
    return np.array(
        [
            semi_major_axis,
            eccentricity,
            inclination,
            argument_of_periapsis,
            raan,
            true_anomaly,
        ]
    )


# ===================================================================
# Keplerian -> Cartesian
# ===================================================================


def keplerian_to_cartesian(keplerian_elements: np.ndarray, mu: float) -> np.ndarray:
    """Convert osculating Keplerian elements to a Cartesian state vector.

    Parameters
    ----------
    keplerian_elements : np.ndarray, shape (6,)
        Keplerian elements [a, e, i, omega, RAAN, theta].
        Angles in radians, semi-major axis in meters.
        Element ordering matches tudatpy convention.
    mu : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    np.ndarray, shape (6,)
        Cartesian state vector [x, y, z, vx, vy, vz] in m and m/s.

    Raises
    ------
    ValueError
        If the orbit is parabolic (infinite semi-major axis).
    """
    semi_major_axis = keplerian_elements[SEMI_MAJOR_AXIS_INDEX]
    eccentricity = keplerian_elements[ECCENTRICITY_INDEX]
    inclination = keplerian_elements[INCLINATION_INDEX]
    argument_of_periapsis = keplerian_elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    raan = keplerian_elements[RAAN_INDEX]
    true_anomaly = keplerian_elements[TRUE_ANOMALY_INDEX]

    if np.isinf(semi_major_axis):
        raise ValueError("Parabolic orbits not supported in inverse conversion.")

    # Semi-latus rectum
    semi_latus_rectum = semi_major_axis * (1.0 - eccentricity**2)

    # Position and velocity in the perifocal frame (PQW)
    r_mag = semi_latus_rectum / (1.0 + eccentricity * np.cos(true_anomaly))

    position_perifocal = np.array(
        [
            r_mag * np.cos(true_anomaly),
            r_mag * np.sin(true_anomaly),
            0.0,
        ]
    )

    velocity_perifocal = np.sqrt(mu / semi_latus_rectum) * np.array(
        [
            -np.sin(true_anomaly),
            eccentricity + np.cos(true_anomaly),
            0.0,
        ]
    )

    # Rotation matrix from perifocal to inertial (3-1-3: RAAN, i, omega)
    cos_raan = np.cos(raan)
    sin_raan = np.sin(raan)
    cos_inclination = np.cos(inclination)
    sin_inclination = np.sin(inclination)
    cos_argument_of_periapsis = np.cos(argument_of_periapsis)
    sin_argument_of_periapsis = np.sin(argument_of_periapsis)

    rotation_matrix_perifocal_to_inertial = np.array(
        [
            [
                cos_raan * cos_argument_of_periapsis
                - sin_raan * sin_argument_of_periapsis * cos_inclination,
                -cos_raan * sin_argument_of_periapsis
                - sin_raan * cos_argument_of_periapsis * cos_inclination,
                sin_raan * sin_inclination,
            ],
            [
                sin_raan * cos_argument_of_periapsis
                + cos_raan * sin_argument_of_periapsis * cos_inclination,
                -sin_raan * sin_argument_of_periapsis
                + cos_raan * cos_argument_of_periapsis * cos_inclination,
                -cos_raan * sin_inclination,
            ],
            [
                sin_argument_of_periapsis * sin_inclination,
                cos_argument_of_periapsis * sin_inclination,
                cos_inclination,
            ],
        ]
    )

    position_inertial = rotation_matrix_perifocal_to_inertial @ position_perifocal
    velocity_inertial = rotation_matrix_perifocal_to_inertial @ velocity_perifocal

    return np.concatenate([position_inertial, velocity_inertial])


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
    n_rev_per_day : float
        Mean motion in revolutions per day.
    mu : float
        Gravitational parameter (m^3/s^2).

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
    a : float
        Semi-major axis in meters.
    mu : float
        Gravitational parameter (m^3/s^2).

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


def tle_epoch_to_datetime_string(epoch_year: int, epoch_day: float) -> str:
    """Convert TLE epoch (2-digit year + fractional day) to a human-readable string.

    Parameters
    ----------
    epoch_year : int
        Two-digit year from TLE.
    epoch_day : float
        Fractional day of year.

    Returns
    -------
    str
        ISO-like date-time string.
    """
    # Convert 2-digit year to 4-digit year
    if epoch_year >= 57:
        year = 1900 + epoch_year
    else:
        year = 2000 + epoch_year

    # Day 1 = Jan 1, so day-of-year offset is (epoch_day - 1)
    dt = datetime(year, 1, 1) + timedelta(days=epoch_day - 1.0)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f UTC")


def brouwer_short_period_corrections(
    mean_semi_major_axis: float,
    mean_eccentricity: float,
    mean_inclination: float,
    mean_argument_of_periapsis: float,
    mean_anomaly: float,
    mu: float = MU_EARTH,
    R_e: float = RE_EARTH,
    J2: float = J2_EARTH,
) -> dict:
    """Compute Brouwer first-order J2 short-period corrections.

    Converts mean Keplerian elements (as used in TLE/SGP4) to osculating
    elements by adding the J2 short-period perturbation terms.

    The formulas follow Brouwer (1959) / Kozai (1959) and are consistent
    with the SGP4 mean-to-osculating transformation.

    Parameters
    ----------
    mean_semi_major_axis : float
        Mean semi-major axis (m).
    mean_eccentricity : float
        Mean eccentricity (dimensionless).
    mean_inclination : float
        Mean inclination (rad).
    mean_argument_of_periapsis : float
        Mean argument of periapsis (rad).
    mean_anomaly : float
        Mean anomaly (rad).
    mu : float
        Gravitational parameter (m^3/s^2).
    R_e : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient.

    Returns
    -------
    dict
        Osculating elements:
            - semi_major_axis_m: float
            - eccentricity: float
            - inclination_rad: float
            - raan_correction_rad: float (additive correction to RAAN)
            - arg_periapsis_rad: float
            - true_anomaly_rad: float

    Reference
    ---------
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    Hoots, F.R. & Roehrich, R.L. "Spacetrack Report No. 3", 1980.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Ch. 9.
    """
    # Semi-latus rectum and related quantities
    p_mean = mean_semi_major_axis * (1.0 - mean_eccentricity**2)
    eta = np.sqrt(1.0 - mean_eccentricity**2)

    # Solve Kepler's equation for mean elements: M -> E -> theta
    E_mean = mean_to_eccentric_anomaly(mean_anomaly, mean_eccentricity)
    theta_mean = eccentric_to_true_anomaly(E_mean, mean_eccentricity)

    # Trigonometric quantities
    cos_i = np.cos(mean_inclination)
    sin_i = np.sin(mean_inclination)
    cos_theta = np.cos(theta_mean)
    sin_theta = np.sin(theta_mean)

    # Argument of latitude u = omega + theta
    u_mean = mean_argument_of_periapsis + theta_mean
    cos_2u = np.cos(2.0 * u_mean)
    sin_2u = np.sin(2.0 * u_mean)

    # J2 perturbation scale factor
    gamma = 0.5 * J2 * (R_e / p_mean) ** 2

    # Convenience
    one_plus_e_cos_f = 1.0 + mean_eccentricity * cos_theta
    sin2i = sin_i**2
    cos2i = cos_i**2

    # Short-period correction to radial distance (r)
    # dr/r = gamma * [(1 - 3*cos2i) + 3*sin2i*cos(2u)]
    # This gives the osculating r relative to the mean r.
    dr_over_r = gamma * ((1.0 - 3.0 * cos2i) + 3.0 * sin2i * cos_2u)

    # Short-period correction to semi-major axis.
    # The osculating semi-major axis differs from the Kozai mean by the
    # short-period radial perturbation. Using the standard result from
    # Brouwer/Kozai theory (consistent with SGP4's near-earth model):
    #   a_osc = mean_semi_major_axis * (1 + delta)
    # where delta captures the instantaneous energy perturbation.
    # The dominant term is the radial correction scaled by the orbit geometry.
    a_over_r = one_plus_e_cos_f / (1.0 - mean_eccentricity**2)
    delta_a_over_a = gamma * (
        (1.0 - 3.0 * cos2i) * (3.0 * a_over_r - 1.0 / eta - 1.0)
        + 3.0 * sin2i * a_over_r * cos_2u
    )
    a_osc = mean_semi_major_axis * (1.0 + delta_a_over_a)

    # Short-period correction to eccentricity
    # de = gamma * eta * sin2i * [cos(2w+f) + e*cos(2w)/2 + e*cos(2w+2f)/2]
    # where w = omega, f = theta
    two_omega = 2.0 * mean_argument_of_periapsis
    delta_e = (
        gamma
        * eta
        * sin2i
        * (
            np.cos(two_omega + theta_mean)
            + 0.5 * mean_eccentricity * np.cos(two_omega)
            + 0.5 * mean_eccentricity * np.cos(two_omega + 2.0 * theta_mean)
        )
    )
    e_osc = mean_eccentricity + delta_e

    # Short-period correction to inclination
    # di = gamma/2 * sin(2i) * cos(2u)
    delta_i = 0.5 * gamma * np.sin(2.0 * mean_inclination) * cos_2u
    i_osc = mean_inclination + delta_i

    # Short-period correction to RAAN
    # dOmega = -gamma * cos_i * sin(2u)
    delta_raan = -gamma * cos_i * sin_2u

    # Short-period correction to argument of periapsis
    # dw = gamma * [(5*cos2i - 1)/2 * sin(2u)/eta
    #       + (1-5cos2i)/(2*eta) * e*sin(2u)  ... ]
    # Simplified dominant form:
    # dw = gamma * [(2+e*cos_f)/one_plus_e_cos_f * sin(2u) * (5cos2i-1)/2
    #       - e*sin_f*(1-3cos2i)/(2*eta)]
    # Standard Brouwer form for argument of periapsis short-period:
    delta_omega = gamma * (
        (5.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * eta)
        + (5.0 * cos2i - 1.0)
        * mean_eccentricity
        * np.sin(2.0 * u_mean - theta_mean)
        / (2.0 * eta)
        - (1.0 - 3.0 * cos2i) * mean_eccentricity * sin_theta / eta
    )

    # Short-period correction to mean anomaly -> affects true anomaly
    # The along-track correction modifies the argument of latitude:
    # du = dw + df, where df is the true anomaly correction
    # Total argument of latitude correction:
    # du_sp = gamma * [(7*cos2i - 1)/2 * sin(2u) / eta]
    delta_u_total = gamma * (
        (7.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * eta)
    )

    # Osculating argument of latitude
    u_osc = u_mean + delta_u_total

    # Osculating argument of periapsis
    omega_osc = mean_argument_of_periapsis + delta_omega

    # Osculating true anomaly from u_osc - omega_osc
    theta_osc = u_osc - omega_osc

    # Normalize angles to [0, 2pi)
    omega_osc = omega_osc % (2.0 * np.pi)
    if omega_osc < 0.0:
        omega_osc += 2.0 * np.pi

    theta_osc = theta_osc % (2.0 * np.pi)
    if theta_osc < 0.0:
        theta_osc += 2.0 * np.pi

    # Clamp eccentricity
    e_osc = max(0.0, min(e_osc, 0.9999999))

    return {
        "semi_major_axis_m": a_osc,
        "eccentricity": e_osc,
        "inclination_rad": i_osc,
        "raan_correction_rad": delta_raan,
        "arg_periapsis_rad": omega_osc,
        "true_anomaly_rad": theta_osc,
    }


def osculating_to_mean_keplerian(
    osculating_semi_major_axis: float,
    osculating_eccentricity: float,
    osculating_inclination: float,
    osculating_raan: float,
    osculating_argument_of_periapsis: float,
    osculating_true_anomaly: float,
    mu: float = MU_EARTH,
    R_e: float = RE_EARTH,
    J2: float = J2_EARTH,
    max_iter: int = 20,
    tol: float = 1e-12,
) -> dict:
    """Convert osculating Keplerian elements to mean (Brouwer) elements.

    Uses iterative inversion of the Brouwer short-period corrections.
    Starting from the osculating elements as an initial guess for the mean
    elements, repeatedly applies the forward correction and adjusts until
    convergence.

    Parameters
    ----------
    osculating_semi_major_axis : float
        Osculating semi-major axis (m).
    osculating_eccentricity : float
        Osculating eccentricity.
    osculating_inclination : float
        Osculating inclination (rad).
    osculating_raan : float
        Osculating RAAN (rad).
    osculating_argument_of_periapsis : float
        Osculating argument of periapsis (rad).
    osculating_true_anomaly : float
        Osculating true anomaly (rad).
    mu : float
        Gravitational parameter (m^3/s^2).
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
    dict
        Mean elements:
            - semi_major_axis_m: float
            - eccentricity: float
            - inclination_rad: float
            - raan_rad: float
            - arg_periapsis_rad: float
            - mean_anomaly_rad: float
            - mean_motion_rev_per_day: float
    """
    # Convert osculating true anomaly to mean anomaly
    mean_anomaly_osc = true_to_mean_anomaly(
        osculating_true_anomaly, osculating_eccentricity
    )

    # Initial guess: mean = osculating
    semi_major_axis_mean = osculating_semi_major_axis
    eccentricity_mean = osculating_eccentricity
    inclination_mean = osculating_inclination
    raan_mean = osculating_raan
    argument_of_periapsis_mean = osculating_argument_of_periapsis
    mean_anomaly_mean = mean_anomaly_osc

    for _ in range(max_iter):
        # Apply forward correction
        osc = brouwer_short_period_corrections(
            mean_semi_major_axis=semi_major_axis_mean,
            mean_eccentricity=eccentricity_mean,
            mean_inclination=inclination_mean,
            mean_argument_of_periapsis=argument_of_periapsis_mean,
            mean_anomaly=mean_anomaly_mean,
            mu=mu,
            R_e=R_e,
            J2=J2,
        )

        # Compute residuals (osculating_target - osculating_from_mean)
        delta_semimajor = osculating_semi_major_axis - osc["semi_major_axis_m"]
        delta_eccentricity = osculating_eccentricity - osc["eccentricity"]
        delta_inclination = osculating_inclination - osc["inclination_rad"]
        delta_raan = osculating_raan - (raan_mean + osc["raan_correction_rad"])
        delta_argument_of_periapsis = (
            osculating_argument_of_periapsis - osc["arg_periapsis_rad"]
        )
        delta_true_anomaly = osculating_true_anomaly - osc["true_anomaly_rad"]

        # Wrap angle differences to [-pi, pi]
        delta_raan = (delta_raan + np.pi) % (2.0 * np.pi) - np.pi
        delta_argument_of_periapsis = (delta_argument_of_periapsis + np.pi) % (
            2.0 * np.pi
        ) - np.pi
        delta_true_anomaly = (delta_true_anomaly + np.pi) % (2.0 * np.pi) - np.pi

        # Update mean elements
        semi_major_axis_mean += delta_semimajor
        eccentricity_mean += delta_eccentricity
        inclination_mean += delta_inclination
        raan_mean += delta_raan
        argument_of_periapsis_mean += delta_argument_of_periapsis

        # Update mean anomaly from corrected true anomaly
        target_theta_for_mean = osculating_true_anomaly - (
            osc["true_anomaly_rad"]
            - mean_to_true_anomaly(mean_anomaly_mean, eccentricity_mean)
        )
        mean_anomaly_mean = true_to_mean_anomaly(
            target_theta_for_mean, eccentricity_mean
        )

        # Clamp eccentricity
        eccentricity_mean = max(1e-10, min(eccentricity_mean, 0.9999999))

        # Check convergence
        if abs(delta_semimajor) < tol and abs(delta_eccentricity) < 1e-14:
            break

    # Normalize angles
    raan_mean = raan_mean % (2.0 * np.pi)
    if raan_mean < 0.0:
        raan_mean += 2.0 * np.pi
    argument_of_periapsis_mean = argument_of_periapsis_mean % (2.0 * np.pi)
    if argument_of_periapsis_mean < 0.0:
        argument_of_periapsis_mean += 2.0 * np.pi
    mean_anomaly_mean = mean_anomaly_mean % (2.0 * np.pi)
    if mean_anomaly_mean < 0.0:
        mean_anomaly_mean += 2.0 * np.pi

    mean_motion_rev_per_day = semi_major_axis_to_mean_motion(semi_major_axis_mean, mu)

    return {
        "semi_major_axis_m": semi_major_axis_mean,
        "eccentricity": eccentricity_mean,
        "inclination_rad": inclination_mean,
        "raan_rad": raan_mean,
        "arg_periapsis_rad": argument_of_periapsis_mean,
        "mean_anomaly_rad": mean_anomaly_mean,
        "mean_motion_rev_per_day": mean_motion_rev_per_day,
    }


def tle_to_osculating_keplerian(
    tle_obj: "Tle", mu: float = MU_EARTH, apply_j2: bool = True
) -> dict:
    """Extract osculating Keplerian elements at the TLE epoch.

    Converts the TLE mean elements to osculating elements. When *apply_j2*
    is True (default), applies Brouwer first-order J2 short-period
    corrections to approximate the osculating state. When False, uses
    simple two-body mechanics (Kepler's equation for true anomaly,
    Kepler's third law for semi-major axis).

    Parameters
    ----------
    tle_obj : Tle
        Parsed TLE dataclass (from common.tle.read_tle).
    mu : float
        Gravitational parameter (m^3/s^2).
    apply_j2 : bool
        If True, apply Brouwer J2 short-period corrections to convert
        mean elements to osculating. If False, use simple two-body
        conversion (backward-compatible behavior).

    Returns
    -------
    dict
        Dictionary with osculating Keplerian elements:
            - semi_major_axis_m: float (meters)
            - eccentricity: float (dimensionless)
            - inclination_rad: float (radians)
            - raan_rad: float (radians)
            - arg_periapsis_rad: float (radians)
            - true_anomaly_rad: float (radians)
            - epoch_year: int
            - epoch_day: float
            - epoch_string: str

    Reference
    ---------
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications"
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    """
    # Extract mean elements from TLE
    mean_eccentricity = tle_obj.eccentricity
    inclination_deg = tle_obj.inclination_deg
    raan_deg = tle_obj.raan_deg
    argument_of_perigee_deg = tle_obj.arg_perigee_deg
    mean_anomaly_deg = tle_obj.mean_anomaly_deg
    mean_motion_rev_per_day = tle_obj.mean_motion_rev_per_day

    # Convert to radians
    inclination_rad = np.radians(inclination_deg)
    raan_rad = np.radians(raan_deg)
    argument_of_perigee_rad = np.radians(argument_of_perigee_deg)
    mean_anomaly_rad = np.radians(mean_anomaly_deg)

    # Semi-major axis from mean motion (Kepler's third law)
    semi_major_axis_m = mean_motion_to_semi_major_axis(mean_motion_rev_per_day, mu)

    # Epoch string
    epoch_string = tle_epoch_to_datetime_string(tle_obj.epoch_year, tle_obj.epoch_day)

    if apply_j2:
        # Apply Brouwer J2 short-period corrections
        osc = brouwer_short_period_corrections(
            mean_semi_major_axis=semi_major_axis_m,
            mean_eccentricity=mean_eccentricity,
            mean_inclination=inclination_rad,
            mean_argument_of_periapsis=argument_of_perigee_rad,
            mean_anomaly=mean_anomaly_rad,
            mu=mu,
        )

        return {
            "semi_major_axis_m": osc["semi_major_axis_m"],
            "eccentricity": osc["eccentricity"],
            "inclination_rad": osc["inclination_rad"],
            "raan_rad": raan_rad + osc["raan_correction_rad"],
            "arg_periapsis_rad": osc["arg_periapsis_rad"],
            "true_anomaly_rad": osc["true_anomaly_rad"],
            "epoch_year": tle_obj.epoch_year,
            "epoch_day": tle_obj.epoch_day,
            "epoch_string": epoch_string,
        }
    else:
        # Simple two-body conversion (legacy behavior)
        true_anomaly_rad = mean_to_true_anomaly(mean_anomaly_rad, mean_eccentricity)

        return {
            "semi_major_axis_m": semi_major_axis_m,
            "eccentricity": mean_eccentricity,
            "inclination_rad": inclination_rad,
            "raan_rad": raan_rad,
            "arg_periapsis_rad": argument_of_perigee_rad,
            "true_anomaly_rad": true_anomaly_rad,
            "epoch_year": tle_obj.epoch_year,
            "epoch_day": tle_obj.epoch_day,
            "epoch_string": epoch_string,
        }
