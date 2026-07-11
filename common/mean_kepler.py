"""Convert between osculating and mean (Brouwer) Keplerian elements.

Provides functions for working with mean Keplerian elements, including
Brouwer first-order J2 short-period corrections, osculating-to-mean
inversion, J2 secular propagation, and conversion to Cartesian state.

The six classical Keplerian elements use the same ordering as
tudatpy's ``element_conversion`` module:

    ======  ====  ==========================================
    Index   Name  Description
    ======  ====  ==========================================
    0       a     Semi-major axis (m)
    1       e     Eccentricity (dimensionless)
    2       i     Inclination (rad)
    3       ω     Argument of periapsis (rad)
    4       Ω     Right ascension of ascending node (rad)
    5       M/θ   Mean anomaly or true anomaly (rad)
    ======  ====  ==========================================

References:
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    Hoots, F.R. & Roehrich, R.L. "Spacetrack Report No. 3", 1980.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Ch. 9.
"""

from __future__ import annotations

import numpy as np

import common.kepler as kepler
import common.consts as consts

# Re-export constants and indices used by this module for convenience
EARTH_GRAVITATIONAL_PARAMETER_M3_S2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
EARTH_EQUATORIAL_RADIUS_M: float = consts.EARTH_EQUATORIAL_RADIUS_M

SEMI_MAJOR_AXIS_INDEX: int = kepler.SEMI_MAJOR_AXIS_INDEX
ECCENTRICITY_INDEX: int = kepler.ECCENTRICITY_INDEX
INCLINATION_INDEX: int = kepler.INCLINATION_INDEX
ARGUMENT_OF_PERIAPSIS_INDEX: int = kepler.ARGUMENT_OF_PERIAPSIS_INDEX
RAAN_INDEX: int = kepler.RAAN_INDEX
TRUE_ANOMALY_INDEX: int = kepler.TRUE_ANOMALY_INDEX
MEAN_ANOMALY_INDEX: int = kepler.MEAN_ANOMALY_INDEX


# ===================================================================
# Brouwer short-period corrections (mean -> osculating)
# ===================================================================


def compute_brouwer_short_period_corrections(
    mean_keplerian_elements: np.ndarray,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
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
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

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
    mean_elements: np.ndarray = np.asarray(mean_keplerian_elements, dtype=float)

    # Determine if input is single or batch
    if mean_elements.ndim == 1:
        if mean_elements.shape != (6,):
            raise ValueError(
                f"Mean Keplerian elements must have shape (6,), got {mean_elements.shape}"
            )
        mean_elements = mean_elements.reshape(1, 6)
        single_input: bool = True
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
    mean_semi_major_axes: np.ndarray = mean_elements[:, SEMI_MAJOR_AXIS_INDEX]
    mean_eccentricities: np.ndarray = mean_elements[:, ECCENTRICITY_INDEX]
    mean_inclinations: np.ndarray = mean_elements[:, INCLINATION_INDEX]
    mean_arguments_of_periapsis: np.ndarray = mean_elements[
        :, ARGUMENT_OF_PERIAPSIS_INDEX
    ]
    mean_raans: np.ndarray = mean_elements[:, RAAN_INDEX]
    mean_anomalies: np.ndarray = mean_elements[:, MEAN_ANOMALY_INDEX]

    # Semi-latus rectum and related quantities: shape (N,)
    p_means: np.ndarray = mean_semi_major_axes * (1.0 - mean_eccentricities**2)
    etas: np.ndarray = np.sqrt(1.0 - mean_eccentricities**2)

    # Solve Kepler's equation for mean elements: M -> E -> theta
    # Note: These are scalar functions, so we need to vectorize them
    E_means: np.ndarray = np.array(
        [
            kepler.mean_to_eccentric_anomaly(mean_anomalies[i], mean_eccentricities[i])
            for i in range(mean_elements.shape[0])
        ]
    )
    theta_means: np.ndarray = np.array(
        [
            kepler.eccentric_to_true_anomaly(E_means[i], mean_eccentricities[i])
            for i in range(mean_elements.shape[0])
        ]
    )

    # Trigonometric quantities: shape (N,)
    cos_i: np.ndarray = np.cos(mean_inclinations)
    sin_i: np.ndarray = np.sin(mean_inclinations)
    cos_theta: np.ndarray = np.cos(theta_means)
    sin_theta: np.ndarray = np.sin(theta_means)

    # Argument of latitude u = omega + theta: shape (N,)
    u_means: np.ndarray = mean_arguments_of_periapsis + theta_means
    cos_2u: np.ndarray = np.cos(2.0 * u_means)
    sin_2u: np.ndarray = np.sin(2.0 * u_means)

    # J2 perturbation scale factor: shape (N,)
    gammas: np.ndarray = 0.5 * J2 * (R_e_m / p_means) ** 2

    # Convenience: shape (N,)
    one_plus_e_cos_f: np.ndarray = 1.0 + mean_eccentricities * cos_theta
    sin2i: np.ndarray = sin_i**2
    cos2i: np.ndarray = cos_i**2

    # Short-period correction to semi-major axis: shape (N,)
    a_over_r: np.ndarray = one_plus_e_cos_f / (1.0 - mean_eccentricities**2)
    delta_a_over_a: np.ndarray = gammas * (
        (1.0 - 3.0 * cos2i) * (3.0 * a_over_r - 1.0 / etas - 1.0)
        + 3.0 * sin2i * a_over_r * cos_2u
    )
    osculating_semi_major_axes: np.ndarray = mean_semi_major_axes * (
        1.0 + delta_a_over_a
    )

    # Short-period correction to eccentricity: shape (N,)
    two_omegas: np.ndarray = 2.0 * mean_arguments_of_periapsis
    delta_e: np.ndarray = (
        gammas
        * etas
        * sin2i
        * (
            np.cos(two_omegas + theta_means)
            + 0.5 * mean_eccentricities * np.cos(two_omegas)
            + 0.5 * mean_eccentricities * np.cos(two_omegas + 2.0 * theta_means)
        )
    )
    osculating_eccentricities: np.ndarray = mean_eccentricities + delta_e

    # Short-period correction to inclination: shape (N,)
    delta_inclination: np.ndarray = (
        0.5 * gammas * np.sin(2.0 * mean_inclinations) * cos_2u
    )
    osculating_inclinations: np.ndarray = mean_inclinations + delta_inclination

    # Short-period correction to RAAN: shape (N,)
    raan_corrections: np.ndarray = -gammas * cos_i * sin_2u
    osculating_raans: np.ndarray = mean_raans + raan_corrections

    # Short-period correction to argument of periapsis: shape (N,)
    argument_of_periapsis_corrections: np.ndarray = gammas * (
        (5.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * etas)
        + (5.0 * cos2i - 1.0)
        * mean_eccentricities
        * np.sin(2.0 * u_means - theta_means)
        / (2.0 * etas)
        - (1.0 - 3.0 * cos2i) * mean_eccentricities * sin_theta / etas
    )

    # Short-period correction to argument of latitude: shape (N,)
    argument_of_latitude_corrections: np.ndarray = gammas * (
        (7.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * etas)
    )

    # Osculating argument of latitude: shape (N,)
    osculating_arguments_of_latitude: np.ndarray = (
        u_means + argument_of_latitude_corrections
    )

    # Osculating argument of periapsis: shape (N,)
    osculating_arguments_of_periapsis: np.ndarray = (
        mean_arguments_of_periapsis + argument_of_periapsis_corrections
    )

    # Osculating true anomaly: shape (N,)
    osculating_true_anomalies: np.ndarray = (
        osculating_arguments_of_latitude - osculating_arguments_of_periapsis
    )

    # Normalize angles to [0, 2π): shape (N,)
    osculating_arguments_of_periapsis = osculating_arguments_of_periapsis % (
        2.0 * np.pi
    )
    neg_mask: np.ndarray = osculating_arguments_of_periapsis < 0.0
    osculating_arguments_of_periapsis[neg_mask] += 2.0 * np.pi

    osculating_true_anomalies = osculating_true_anomalies % (2.0 * np.pi)
    neg_mask = osculating_true_anomalies < 0.0
    osculating_true_anomalies[neg_mask] += 2.0 * np.pi

    # Clamp osculating eccentricity: shape (N,)
    osculating_eccentricities = np.clip(osculating_eccentricities, 0.0, 0.9999999)

    # Assemble result: shape (N, 6)
    result: np.ndarray = np.column_stack(
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


# ===================================================================
# Osculating -> Mean (iterative inversion)
# ===================================================================


def osculating_to_mean_keplerian(
    osculating_keplerian_elements: np.ndarray,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
    max_iter: int = 20,
    tol_m: float = 1e-12,
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
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).
    max_iter : int
        Maximum iterations for convergence.
    tol_m : float
        Convergence tolerance on semi-major axis (m).

    Returns
    -------
    np.ndarray, shape (6,)
        Mean Keplerian elements [a, e, i, omega, RAAN, M].
        Angles are in radians and semi-major axis is in meters.
    """
    osculating_elements: np.ndarray = np.asarray(
        osculating_keplerian_elements, dtype=float
    )
    if osculating_elements.shape != (6,):
        raise ValueError(
            f"Osculating Keplerian elements must have shape (6,), got {osculating_elements.shape}"
        )

    osculating_semi_major_axis: float = osculating_elements[SEMI_MAJOR_AXIS_INDEX]
    osculating_eccentricity: float = osculating_elements[ECCENTRICITY_INDEX]
    osculating_inclination: float = osculating_elements[INCLINATION_INDEX]
    osculating_argument_of_periapsis: float = osculating_elements[
        ARGUMENT_OF_PERIAPSIS_INDEX
    ]
    osculating_raan: float = osculating_elements[RAAN_INDEX]
    osculating_true_anomaly: float = osculating_elements[TRUE_ANOMALY_INDEX]

    # Convert osculating true anomaly to an initial mean anomaly guess
    initial_mean_anomaly: float = kepler.true_to_mean_anomaly(
        osculating_true_anomaly, osculating_eccentricity
    )

    # Initial guess: mean = osculating
    mean_semi_major_axis: float = osculating_semi_major_axis
    mean_eccentricity: float = osculating_eccentricity
    mean_inclination: float = osculating_inclination
    mean_raan: float = osculating_raan
    mean_argument_of_periapsis: float = osculating_argument_of_periapsis
    mean_anomaly_estimate: float = initial_mean_anomaly

    for _ in range(max_iter):
        # Apply forward correction
        osc: np.ndarray = compute_brouwer_short_period_corrections(
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
            R_e_m=R_e_m,
            J2=J2,
        )

        # Compute residuals (osculating_target - osculating_from_mean)
        delta_semimajor: float = osculating_semi_major_axis - osc[SEMI_MAJOR_AXIS_INDEX]
        delta_eccentricity: float = osculating_eccentricity - osc[ECCENTRICITY_INDEX]
        delta_inclination: float = osculating_inclination - osc[INCLINATION_INDEX]
        delta_raan: float = osculating_raan - osc[RAAN_INDEX]
        delta_argument_of_periapsis: float = (
            osculating_argument_of_periapsis - osc[ARGUMENT_OF_PERIAPSIS_INDEX]
        )
        delta_true_anomaly: float = osculating_true_anomaly - osc[TRUE_ANOMALY_INDEX]

        # Wrap angle differences to [-π, π]
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
        target_theta_for_mean: float = osculating_true_anomaly - (
            osc[TRUE_ANOMALY_INDEX]
            - kepler.mean_to_true_anomaly(mean_anomaly_estimate, mean_eccentricity)
        )
        mean_anomaly_estimate = kepler.true_to_mean_anomaly(
            target_theta_for_mean, mean_eccentricity
        )

        # Check convergence
        if abs(delta_semimajor) < tol_m and abs(delta_eccentricity) < 1e-14:
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


# ===================================================================
# J2 secular propagation of mean elements
# ===================================================================


def compute_raan_rate(
    keplerian_elements: np.ndarray,
    mu_m3_s2: float,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
) -> float:
    """Compute the J2 secular rate of RAAN.

    Parameters
    ----------
    keplerian_elements : np.ndarray
        Keplerian elements (6,): [a, e, i, omega, RAAN, M/theta].
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

    Returns
    -------
    float
        RAAN rate (rad/s).
    """
    semi_major_axis: float = keplerian_elements[SEMI_MAJOR_AXIS_INDEX]
    eccentricity: float = keplerian_elements[ECCENTRICITY_INDEX]
    inclination: float = keplerian_elements[INCLINATION_INDEX]

    mean_motion: float = np.sqrt(mu_m3_s2 / semi_major_axis**3)  # rad/s
    semi_latus_rectum: float = semi_major_axis * (1.0 - eccentricity**2)
    radius_ratio_squared: float = (R_e_m / semi_latus_rectum) ** 2
    cos_inclination: float = np.cos(inclination)

    # Secular rates
    raan_rate: float = -1.5 * mean_motion * J2 * radius_ratio_squared * cos_inclination

    return raan_rate


def mean_elements_to_cartesian(
    mean_elements: np.ndarray,
    mu_m3_s2: float,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
) -> np.ndarray:
    """Convert mean elements to Cartesian state via Brouwer short-period corrections.

    This function performs a two-step conversion:

    1. Applies Brouwer J2 short-period corrections to obtain osculating
       elements [a, e, i, ω, Ω, θ] using
       :func:`compute_brouwer_short_period_corrections`.
    2. Converts osculating elements to Cartesian state [x, y, z, vx, vy, vz]
       using :func:`kepler.keplerian_to_cartesian`.

    For osculating elements, use :func:`kepler.keplerian_to_cartesian` directly.

    Parameters
    ----------
    mean_elements : np.ndarray
        Mean Keplerian elements (6,): [a, e, i, omega, RAAN, M].
        Element ordering follows kepler module index constants.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

    Returns
    -------
    np.ndarray
        Cartesian state vector (6,): [x, y, z, vx, vy, vz] in m and m/s.

    See Also
    --------
    kepler.keplerian_to_cartesian : Direct osculating-to-Cartesian conversion.
    compute_brouwer_short_period_corrections : Mean-to-osculating element conversion.
    propagate_mean_j2 : Propagate mean elements forward using J2 secular rates.
    """
    osculating_elements: np.ndarray = compute_brouwer_short_period_corrections(
        mean_elements, R_e_m=R_e_m, J2=J2
    )
    return kepler.keplerian_to_cartesian(osculating_elements, mu_m3_s2)


def propagate_mean_j2(
    keplerian_elements: np.ndarray,
    time_elapsed_s: float,
    mu_m3_s2: float,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
) -> np.ndarray:
    """Propagate mean Keplerian elements forward in time using J2 secular rates.

    Parameters
    ----------
    keplerian_elements : np.ndarray
        Mean Keplerian elements at epoch (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in metres, angles in radians.
        Element ordering follows kepler module index constants.
    time_elapsed_s : float
        Time elapsed since epoch (s).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

    Returns
    -------
    np.ndarray
        Mean Keplerian elements at epoch + time_elapsed_s (6,): [a, e, i, omega, RAAN, M].
        Element ordering follows kepler module index constants.
    """
    semi_major_axis: float = keplerian_elements[SEMI_MAJOR_AXIS_INDEX]
    eccentricity: float = keplerian_elements[ECCENTRICITY_INDEX]
    inclination: float = keplerian_elements[INCLINATION_INDEX]
    argument_of_periapsis: float = keplerian_elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    raan: float = keplerian_elements[RAAN_INDEX]
    mean_anomaly: float = keplerian_elements[MEAN_ANOMALY_INDEX]

    mean_motion: float = np.sqrt(mu_m3_s2 / semi_major_axis**3)  # rad/s
    eta: float = np.sqrt(1.0 - eccentricity**2)  # η = √(1-e²)
    semi_latus_rectum: float = semi_major_axis * (1.0 - eccentricity**2)
    radius_ratio_squared: float = (R_e_m / semi_latus_rectum) ** 2
    cos_inclination: float = np.cos(inclination)
    cos_inclination_squared: float = cos_inclination**2

    # Secular rates
    raan_rate: float = -1.5 * mean_motion * J2 * radius_ratio_squared * cos_inclination
    argument_of_periapsis_rate: float = (
        0.75
        * mean_motion
        * J2
        * radius_ratio_squared
        * (5.0 * cos_inclination_squared - 1.0)
    )
    mean_anomaly_rate: float = (
        mean_motion
        + 0.75
        * mean_motion
        * J2
        * radius_ratio_squared
        * eta
        * (3.0 * cos_inclination_squared - 1.0)
    )

    # Propagate (a, e, i are constant under J2 secular)
    propagated_raan: float = raan + raan_rate * time_elapsed_s
    propagated_argument_of_periapsis: float = (
        argument_of_periapsis + argument_of_periapsis_rate * time_elapsed_s
    )
    propagated_mean_anomaly: float = mean_anomaly + mean_anomaly_rate * time_elapsed_s

    return np.array(
        [
            semi_major_axis,
            eccentricity,
            inclination,
            propagated_argument_of_periapsis,
            propagated_raan,
            propagated_mean_anomaly,
        ]
    )
