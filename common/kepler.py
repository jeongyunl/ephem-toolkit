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


def cartesian_to_keplerian(state: np.ndarray, mu: float) -> np.ndarray:
    """Convert a Cartesian state vector to osculating Keplerian elements.

    Parameters
    ----------
    state : np.ndarray, shape (6,)
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
    state = np.asarray(state, dtype=float)
    if state.shape != (6,):
        raise ValueError(f"State vector must have shape (6,), got {state.shape}")

    r_vec = state[0:3]
    v_vec = state[3:6]

    r = np.linalg.norm(r_vec)
    v = np.linalg.norm(v_vec)

    if r < 1e-10:
        raise ValueError("Position vector has zero magnitude — degenerate orbit.")

    # --- Specific angular momentum ---
    h_vec = np.cross(r_vec, v_vec)
    h = np.linalg.norm(h_vec)

    if h < 1e-10:
        raise ValueError(
            "Angular momentum is zero — rectilinear orbit, " "Keplerian elements are undefined."
        )

    # --- Node vector (points toward ascending node) ---
    K = np.array([0.0, 0.0, 1.0])
    n_vec = np.cross(K, h_vec)
    n = np.linalg.norm(n_vec)

    # --- Eccentricity vector (points toward periapsis) ---
    e_vec = ((v**2 - mu / r) * r_vec - np.dot(r_vec, v_vec) * v_vec) / mu
    e = np.linalg.norm(e_vec)

    # --- Specific mechanical energy ---
    energy = 0.5 * v**2 - mu / r

    # --- Semi-major axis ---
    if abs(1.0 - e) > 1e-10:  # elliptic or hyperbolic
        a = -mu / (2.0 * energy)
    else:
        # Parabolic orbit — semi-major axis is undefined (infinite)
        a = np.inf

    # --- Inclination ---
    i = np.arccos(np.clip(h_vec[2] / h, -1.0, 1.0))

    # --- Right Ascension of the Ascending Node (RAAN / Ω) ---
    if n > 1e-10:
        RAAN = np.arccos(np.clip(n_vec[0] / n, -1.0, 1.0))
        if n_vec[1] < 0.0:
            RAAN = 2.0 * np.pi - RAAN
    else:
        # Equatorial orbit — RAAN is undefined, conventionally set to 0
        RAAN = 0.0

    # --- Argument of Periapsis (ω) ---
    if n > 1e-10 and e > 1e-10:
        cos_omega = np.dot(n_vec, e_vec) / (n * e)
        omega = np.arccos(np.clip(cos_omega, -1.0, 1.0))
        if e_vec[2] < 0.0:
            omega = 2.0 * np.pi - omega
    elif e > 1e-10:
        # Equatorial orbit with nonzero eccentricity:
        # use longitude of periapsis (angle from x-axis to e_vec)
        omega = np.arctan2(e_vec[1], e_vec[0])
        if omega < 0.0:
            omega += 2.0 * np.pi
    else:
        # Circular orbit — argument of periapsis is undefined, set to 0
        omega = 0.0

    # --- True Anomaly (θ / ν) ---
    if e > 1e-10:
        cos_theta = np.dot(e_vec, r_vec) / (e * r)
        theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        # Quadrant check: if r·v < 0, spacecraft is approaching periapsis
        if np.dot(r_vec, v_vec) < 0.0:
            theta = 2.0 * np.pi - theta
    elif n > 1e-10:
        # Circular, non-equatorial: use argument of latitude (u = ω + θ)
        cos_u = np.dot(n_vec, r_vec) / (n * r)
        theta = np.arccos(np.clip(cos_u, -1.0, 1.0))
        if r_vec[2] < 0.0:
            theta = 2.0 * np.pi - theta
    else:
        # Circular, equatorial: use true longitude (l = Ω + ω + θ)
        theta = np.arctan2(r_vec[1], r_vec[0])
        if theta < 0.0:
            theta += 2.0 * np.pi

    # Return in tudatpy order: [a, e, i, omega, RAAN, theta]
    return np.array([a, e, i, omega, RAAN, theta])


# ===================================================================
# Keplerian -> Cartesian
# ===================================================================


def keplerian_to_cartesian(elements: np.ndarray, mu: float) -> np.ndarray:
    """Convert osculating Keplerian elements to a Cartesian state vector.

    Parameters
    ----------
    elements : np.ndarray, shape (6,)
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
    a = elements[SEMI_MAJOR_AXIS_INDEX]
    e = elements[ECCENTRICITY_INDEX]
    i = elements[INCLINATION_INDEX]
    omega = elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    RAAN = elements[RAAN_INDEX]
    theta = elements[TRUE_ANOMALY_INDEX]

    if np.isinf(a):
        raise ValueError("Parabolic orbits not supported in inverse conversion.")

    # Semi-latus rectum
    p = a * (1.0 - e**2)

    # Position and velocity in the perifocal frame (PQW)
    r_mag = p / (1.0 + e * np.cos(theta))

    r_pqw = np.array(
        [
            r_mag * np.cos(theta),
            r_mag * np.sin(theta),
            0.0,
        ]
    )

    v_pqw = np.sqrt(mu / p) * np.array(
        [
            -np.sin(theta),
            e + np.cos(theta),
            0.0,
        ]
    )

    # Rotation matrix from perifocal to inertial (3-1-3: RAAN, i, omega)
    cos_O = np.cos(RAAN)
    sin_O = np.sin(RAAN)
    cos_i = np.cos(i)
    sin_i = np.sin(i)
    cos_w = np.cos(omega)
    sin_w = np.sin(omega)

    R = np.array(
        [
            [
                cos_O * cos_w - sin_O * sin_w * cos_i,
                -cos_O * sin_w - sin_O * cos_w * cos_i,
                sin_O * sin_i,
            ],
            [
                sin_O * cos_w + cos_O * sin_w * cos_i,
                -sin_O * sin_w + cos_O * cos_w * cos_i,
                -cos_O * sin_i,
            ],
            [sin_w * sin_i, cos_w * sin_i, cos_i],
        ]
    )

    r_vec = R @ r_pqw
    v_vec = R @ v_pqw

    return np.concatenate([r_vec, v_vec])


# ===================================================================
# Anomaly conversions
# ===================================================================


def true_to_eccentric_anomaly(theta: float, e: float) -> float:
    """Convert true anomaly to eccentric anomaly.

    Parameters
    ----------
    theta : float
        True anomaly (rad).
    e : float
        Eccentricity (0 ≤ e < 1).

    Returns
    -------
    float
        Eccentric anomaly E (rad) in [0, 2π).
    """
    E = 2.0 * np.arctan2(
        np.sqrt(1.0 - e) * np.sin(theta / 2.0),
        np.sqrt(1.0 + e) * np.cos(theta / 2.0),
    )
    if E < 0.0:
        E += 2.0 * np.pi
    return E


def eccentric_to_true_anomaly(E: float, e: float) -> float:
    """Convert eccentric anomaly to true anomaly.

    Parameters
    ----------
    E : float
        Eccentric anomaly (rad).
    e : float
        Eccentricity (0 ≤ e < 1).

    Returns
    -------
    float
        True anomaly θ (rad) in [0, 2π).
    """
    theta = 2.0 * np.arctan2(
        np.sqrt(1.0 + e) * np.sin(E / 2.0),
        np.sqrt(1.0 - e) * np.cos(E / 2.0),
    )
    if theta < 0.0:
        theta += 2.0 * np.pi
    return theta


def eccentric_to_mean_anomaly(E: float, e: float) -> float:
    """Convert eccentric anomaly to mean anomaly (Kepler's equation).

    Parameters
    ----------
    E : float
        Eccentric anomaly (rad).
    e : float
        Eccentricity (0 ≤ e < 1).

    Returns
    -------
    float
        Mean anomaly M (rad).
    """
    return E - e * np.sin(E)


def mean_to_eccentric_anomaly(M: float, e: float, tol: float = 1e-12, max_iter: int = 50) -> float:
    """Solve Kepler's equation M = E − e·sin(E) for eccentric anomaly E.

    Uses Newton-Raphson iteration.

    Parameters
    ----------
    M : float
        Mean anomaly (rad).
    e : float
        Eccentricity (0 ≤ e < 1).
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
    if e < 0.8:
        E = M
    else:
        E = np.pi

    for _ in range(max_iter):
        f = E - e * np.sin(E) - M
        f_prime = 1.0 - e * np.cos(E)
        delta = f / f_prime
        E = E - delta
        if abs(delta) < tol:
            return E

    raise RuntimeError(
        f"Kepler's equation did not converge after {max_iter} iterations "
        f"(M={M:.10f}, e={e:.10f})"
    )


def mean_to_true_anomaly(M: float, e: float, tol: float = 1e-12) -> float:
    """Convert mean anomaly to true anomaly via eccentric anomaly.

    Parameters
    ----------
    M : float
        Mean anomaly (rad).
    e : float
        Eccentricity (0 ≤ e < 1).
    tol : float
        Convergence tolerance for Kepler's equation.

    Returns
    -------
    float
        True anomaly θ (rad) in [0, 2π).
    """
    E = mean_to_eccentric_anomaly(M, e, tol=tol)
    return eccentric_to_true_anomaly(E, e)


def true_to_mean_anomaly(theta: float, e: float) -> float:
    """Convert true anomaly to mean anomaly via eccentric anomaly.

    Parameters
    ----------
    theta : float
        True anomaly (rad).
    e : float
        Eccentricity (0 ≤ e < 1).

    Returns
    -------
    float
        Mean anomaly M (rad).
    """
    E = true_to_eccentric_anomaly(theta, e)
    return eccentric_to_mean_anomaly(E, e)


# ===================================================================
# Utility: mean motion <-> semi-major axis
# ===================================================================


def mean_motion_to_semi_major_axis(n_rev_per_day: float, mu: float = MU_EARTH) -> float:
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
    n_rad_per_sec = n_rev_per_day * 2.0 * np.pi / 86400.0
    return (mu / n_rad_per_sec**2) ** (1.0 / 3.0)


def semi_major_axis_to_mean_motion(a: float, mu: float = MU_EARTH) -> float:
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
    n_rad_per_sec = np.sqrt(mu / a**3)
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
    a_mean: float,
    e_mean: float,
    i_mean: float,
    omega_mean: float,
    M_mean: float,
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
    a_mean : float
        Mean semi-major axis (m).
    e_mean : float
        Mean eccentricity (dimensionless).
    i_mean : float
        Mean inclination (rad).
    omega_mean : float
        Mean argument of periapsis (rad).
    M_mean : float
        Mean mean anomaly (rad).
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
    p_mean = a_mean * (1.0 - e_mean**2)
    eta = np.sqrt(1.0 - e_mean**2)

    # Solve Kepler's equation for mean elements: M -> E -> theta
    E_mean = mean_to_eccentric_anomaly(M_mean, e_mean)
    theta_mean = eccentric_to_true_anomaly(E_mean, e_mean)

    # Trigonometric quantities
    cos_i = np.cos(i_mean)
    sin_i = np.sin(i_mean)
    cos_theta = np.cos(theta_mean)
    sin_theta = np.sin(theta_mean)

    # Argument of latitude u = omega + theta
    u_mean = omega_mean + theta_mean
    cos_2u = np.cos(2.0 * u_mean)
    sin_2u = np.sin(2.0 * u_mean)

    # J2 perturbation scale factor
    gamma = 0.5 * J2 * (R_e / p_mean) ** 2

    # Convenience
    one_plus_e_cos_f = 1.0 + e_mean * cos_theta
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
    #   a_osc = a_mean * (1 + delta)
    # where delta captures the instantaneous energy perturbation.
    # The dominant term is the radial correction scaled by the orbit geometry.
    a_over_r = one_plus_e_cos_f / (1.0 - e_mean**2)
    delta_a_over_a = gamma * (
        (1.0 - 3.0 * cos2i) * (3.0 * a_over_r - 1.0 / eta - 1.0)
        + 3.0 * sin2i * a_over_r * cos_2u
    )
    a_osc = a_mean * (1.0 + delta_a_over_a)

    # Short-period correction to eccentricity
    # de = gamma * eta * sin2i * [cos(2w+f) + e*cos(2w)/2 + e*cos(2w+2f)/2]
    # where w = omega, f = theta
    two_omega = 2.0 * omega_mean
    delta_e = gamma * eta * sin2i * (
        np.cos(two_omega + theta_mean)
        + 0.5 * e_mean * np.cos(two_omega)
        + 0.5 * e_mean * np.cos(two_omega + 2.0 * theta_mean)
    )
    e_osc = e_mean + delta_e

    # Short-period correction to inclination
    # di = gamma/2 * sin(2i) * cos(2u)
    delta_i = 0.5 * gamma * np.sin(2.0 * i_mean) * cos_2u
    i_osc = i_mean + delta_i

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
        + (5.0 * cos2i - 1.0) * e_mean * np.sin(2.0 * u_mean - theta_mean) / (2.0 * eta)
        - (1.0 - 3.0 * cos2i) * e_mean * sin_theta / eta
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
    omega_osc = omega_mean + delta_omega

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
    a_osc: float,
    e_osc: float,
    i_osc: float,
    raan_osc: float,
    omega_osc: float,
    theta_osc: float,
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
    a_osc : float
        Osculating semi-major axis (m).
    e_osc : float
        Osculating eccentricity.
    i_osc : float
        Osculating inclination (rad).
    raan_osc : float
        Osculating RAAN (rad).
    omega_osc : float
        Osculating argument of periapsis (rad).
    theta_osc : float
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
    M_osc = true_to_mean_anomaly(theta_osc, e_osc)

    # Initial guess: mean = osculating
    a_m = a_osc
    e_m = e_osc
    i_m = i_osc
    raan_m = raan_osc
    omega_m = omega_osc
    M_m = M_osc

    for _ in range(max_iter):
        # Apply forward correction
        osc = brouwer_short_period_corrections(a_m, e_m, i_m, omega_m, M_m, mu, R_e, J2)

        # Compute residuals (osculating_target - osculating_from_mean)
        da = a_osc - osc["semi_major_axis_m"]
        de = e_osc - osc["eccentricity"]
        di = i_osc - osc["inclination_rad"]
        draan = raan_osc - (raan_m + osc["raan_correction_rad"])
        domega = omega_osc - osc["arg_periapsis_rad"]
        dtheta = theta_osc - osc["true_anomaly_rad"]

        # Wrap angle differences to [-pi, pi]
        draan = (draan + np.pi) % (2.0 * np.pi) - np.pi
        domega = (domega + np.pi) % (2.0 * np.pi) - np.pi
        dtheta = (dtheta + np.pi) % (2.0 * np.pi) - np.pi

        # Update mean elements
        a_m += da
        e_m += de
        i_m += di
        raan_m += draan
        omega_m += domega

        # Update mean anomaly from corrected true anomaly
        theta_m_corrected = theta_osc - dtheta
        # Actually, adjust M_m based on the true anomaly residual
        # Convert the target theta to mean anomaly with current e_m
        target_theta_for_mean = theta_osc - (osc["true_anomaly_rad"] - mean_to_true_anomaly(M_m, e_m))
        M_m = true_to_mean_anomaly(target_theta_for_mean, e_m)

        # Clamp eccentricity
        e_m = max(1e-10, min(e_m, 0.9999999))

        # Check convergence
        if abs(da) < tol and abs(de) < 1e-14:
            break

    # Normalize angles
    raan_m = raan_m % (2.0 * np.pi)
    if raan_m < 0.0:
        raan_m += 2.0 * np.pi
    omega_m = omega_m % (2.0 * np.pi)
    if omega_m < 0.0:
        omega_m += 2.0 * np.pi
    M_m = M_m % (2.0 * np.pi)
    if M_m < 0.0:
        M_m += 2.0 * np.pi

    n_rev_per_day = semi_major_axis_to_mean_motion(a_m, mu)

    return {
        "semi_major_axis_m": a_m,
        "eccentricity": e_m,
        "inclination_rad": i_m,
        "raan_rad": raan_m,
        "arg_periapsis_rad": omega_m,
        "mean_anomaly_rad": M_m,
        "mean_motion_rev_per_day": n_rev_per_day,
    }


def tle_to_osculating_keplerian(
    tle: "Tle", mu: float = MU_EARTH, apply_j2: bool = True
) -> dict:
    """Extract osculating Keplerian elements at the TLE epoch.

    Converts the TLE mean elements to osculating elements. When *apply_j2*
    is True (default), applies Brouwer first-order J2 short-period
    corrections to approximate the osculating state. When False, uses
    simple two-body mechanics (Kepler's equation for true anomaly,
    Kepler's third law for semi-major axis).

    Parameters
    ----------
    tle : Tle
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
    e = tle.eccentricity
    i_deg = tle.inclination_deg
    raan_deg = tle.raan_deg
    omega_deg = tle.arg_perigee_deg
    M_deg = tle.mean_anomaly_deg
    n_rev_per_day = tle.mean_motion_rev_per_day

    # Convert to radians
    i_rad = np.radians(i_deg)
    raan_rad = np.radians(raan_deg)
    omega_rad = np.radians(omega_deg)
    M_rad = np.radians(M_deg)

    # Semi-major axis from mean motion (Kepler's third law)
    a = mean_motion_to_semi_major_axis(n_rev_per_day, mu)

    # Epoch string
    epoch_string = tle_epoch_to_datetime_string(tle.epoch_year, tle.epoch_day)

    if apply_j2:
        # Apply Brouwer J2 short-period corrections
        osc = brouwer_short_period_corrections(
            a_mean=a,
            e_mean=e,
            i_mean=i_rad,
            omega_mean=omega_rad,
            M_mean=M_rad,
            mu=mu,
        )

        return {
            "semi_major_axis_m": osc["semi_major_axis_m"],
            "eccentricity": osc["eccentricity"],
            "inclination_rad": osc["inclination_rad"],
            "raan_rad": raan_rad + osc["raan_correction_rad"],
            "arg_periapsis_rad": osc["arg_periapsis_rad"],
            "true_anomaly_rad": osc["true_anomaly_rad"],
            "epoch_year": tle.epoch_year,
            "epoch_day": tle.epoch_day,
            "epoch_string": epoch_string,
        }
    else:
        # Simple two-body conversion (legacy behavior)
        theta = mean_to_true_anomaly(M_rad, e)

        return {
            "semi_major_axis_m": a,
            "eccentricity": e,
            "inclination_rad": i_rad,
            "raan_rad": raan_rad,
            "arg_periapsis_rad": omega_rad,
            "true_anomaly_rad": theta,
            "epoch_year": tle.epoch_year,
            "epoch_day": tle.epoch_day,
            "epoch_string": epoch_string,
        }


# ===================================================================
# CLI entry point
# ===================================================================


if __name__ == "__main__":
    import sys

    # Example: ISS-like orbit (approx 408 km altitude, 51.6 deg inclination)
    state_iss = np.array(
        [
            -2700816.14,
            -3314092.80,
            5266346.42,  # position [m]
            5168.606550,
            -5597.546618,
            -2131.981798,  # velocity [m/s]
        ]
    )

    print("=" * 65)
    print("Cartesian to Keplerian Conversion")
    print("=" * 65)
    print()
    print("Input Cartesian state (ISS-like orbit):")
    print(f"  r = [{state_iss[0]:.3f}, {state_iss[1]:.3f}, {state_iss[2]:.3f}] m")
    print(f"  v = [{state_iss[3]:.6f}, {state_iss[4]:.6f}, {state_iss[5]:.6f}] m/s")
    print(f"  mu = {MU_EARTH:.6e} m^3/s^2")
    print()

    # Convert to Keplerian
    kep = cartesian_to_keplerian(state_iss, MU_EARTH)

    print("Osculating Keplerian Elements [a, e, i, omega, RAAN, theta]:")
    print(f"  Semi-major axis   a     = {kep[SEMI_MAJOR_AXIS_INDEX] / 1000:.6f} km")
    print(f"  Eccentricity      e     = {kep[ECCENTRICITY_INDEX]:.10f}")
    print(f"  Inclination       i     = {np.degrees(kep[INCLINATION_INDEX]):.6f} deg")
    print(f"  Arg. of periapsis omega  = {np.degrees(kep[ARGUMENT_OF_PERIAPSIS_INDEX]):.6f} deg")
    print(f"  RAAN              RAAN   = {np.degrees(kep[RAAN_INDEX]):.6f} deg")
    print(f"  True anomaly      theta  = {np.degrees(kep[TRUE_ANOMALY_INDEX]):.6f} deg")
    print()

    # Verify round-trip
    state_reconstructed = keplerian_to_cartesian(kep, MU_EARTH)
    pos_err = np.linalg.norm(state_reconstructed[0:3] - state_iss[0:3])
    vel_err = np.linalg.norm(state_reconstructed[3:6] - state_iss[3:6])

    print("Round-trip verification (Cartesian -> Keplerian -> Cartesian):")
    print(f"  Position error: {pos_err:.6e} m")
    print(f"  Velocity error: {vel_err:.6e} m/s")
    print()

    # Verify against tudatpy if available
    try:
        from tudatpy.astro.element_conversion import (
            cartesian_to_keplerian as tudat_c2k,
            keplerian_to_cartesian as tudat_k2c,
        )

        kep_tudat = tudat_c2k(state_iss, MU_EARTH)

        print("Comparison with tudatpy.astro.element_conversion:")
        print(f"  {'Element':<20} {'This module':<18} {'tudatpy':<18} {'delta':<12}")
        print(f"  {'-'*20} {'-'*18} {'-'*18} {'-'*12}")

        labels = ["a (km)", "e", "i (deg)", "omega (deg)", "RAAN (deg)", "theta (deg)"]
        scales = [1e-3, 1.0, np.degrees(1), np.degrees(1), np.degrees(1), np.degrees(1)]

        for idx, (label, scale) in enumerate(zip(labels, scales)):
            val_ours = kep[idx] * scale
            val_tudat = kep_tudat[idx] * scale
            delta = abs(val_ours - val_tudat)
            print(f"  {label:<20} {val_ours:<18.10f} {val_tudat:<18.10f} {delta:<12.2e}")

        print()

        # Also verify keplerian_to_cartesian against tudatpy
        state_from_tudat = tudat_k2c(kep, MU_EARTH)
        state_from_ours = keplerian_to_cartesian(kep, MU_EARTH)

        pos_diff = np.linalg.norm(state_from_ours[0:3] - state_from_tudat[0:3])
        vel_diff = np.linalg.norm(state_from_ours[3:6] - state_from_tudat[3:6])

        print("keplerian_to_cartesian vs tudatpy:")
        print(f"  Position difference: {pos_diff:.6e} m")
        print(f"  Velocity difference: {vel_diff:.6e} m/s")

    except ImportError:
        print("(tudatpy not available -- skipping cross-validation)")

    # Exit with error if round-trip failed
    if pos_err > 1e-6 or vel_err > 1e-9:
        print("\nERROR: Round-trip error exceeds tolerance!", file=sys.stderr)
        sys.exit(1)
