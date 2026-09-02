"""Brouwer J2 secular mean-element propagator and conversion utilities.

Provides :class:`BrouwerJ2Propagator` for class-based propagation, plus
conversion functions between osculating and Brouwer mean Keplerian elements.

All functions use the Brouwer (1959) mean element theory with first-order J2
short-period corrections. Elements are **not** interchangeable with SGP4/TLE
mean elements or DSST/USM mean elements.

The six Keplerian elements use the same ordering as tudatpy's
``element_conversion`` module:

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
    https://en.wikipedia.org/wiki/Brouwer%E2%80%93Lyddane_mean_motion_model
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Ch. 9.
"""

from __future__ import annotations

import numpy as np

from ..consts import (
    EARTH_EQUATORIAL_RADIUS_M,
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    EARTH_J2,
)
from .base import (
    AnomalyType,
    KeplerianState,
    Propagator,
)
from .kepler import (
    ARGUMENT_OF_PERIAPSIS_INDEX,
    ECCENTRICITY_INDEX,
    INCLINATION_INDEX,
    MEAN_ANOMALY_INDEX,
    RAAN_INDEX,
    SEMI_MAJOR_AXIS_INDEX,
    TRUE_ANOMALY_INDEX,
    eccentric_to_true_anomaly,
    keplerian_to_cartesian,
    mean_to_eccentric_anomaly,
    mean_to_true_anomaly,
    true_to_mean_anomaly,
)

# ===================================================================
# Constants
# ===================================================================

MAX_ECCENTRICITY: float = 0.9999999
"""Maximum allowed eccentricity to prevent numerical instability."""

ECCENTRICITY_CONVERGENCE_TOLERANCE: float = 1e-14
"""Convergence tolerance for eccentricity in iterative algorithms (dimensionless)."""

# ===================================================================
# Brouwer short-period corrections (mean -> osculating)
# ===================================================================


def compute_brouwer_short_period_corrections(
    brouwerian_elements: np.ndarray,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
) -> np.ndarray:
    """Compute Brouwer first-order J2 short-period corrections.

    Converts Brouwer mean Keplerian elements to osculating elements by adding
    the J2 short-period perturbation terms.

    Supports both single and batch processing of element sets.

    Parameters
    ----------
    brouwerian_elements : np.ndarray
        Brouwer mean Keplerian element vector(s) [a, e, i, omega, RAAN, M].
        - Shape (6,): Single element set
        - Shape (N, 6): Batch of N element sets
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

    References
    ----------
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    """
    mean_elements: np.ndarray = np.asarray(brouwerian_elements, dtype=float)

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

    mean_semi_major_axes: np.ndarray = mean_elements[:, SEMI_MAJOR_AXIS_INDEX]
    mean_eccentricities: np.ndarray = mean_elements[:, ECCENTRICITY_INDEX]
    mean_inclinations: np.ndarray = mean_elements[:, INCLINATION_INDEX]
    mean_arguments_of_periapsis: np.ndarray = mean_elements[
        :, ARGUMENT_OF_PERIAPSIS_INDEX
    ]
    mean_raans: np.ndarray = mean_elements[:, RAAN_INDEX]
    mean_anomalies: np.ndarray = mean_elements[:, MEAN_ANOMALY_INDEX]

    p_means: np.ndarray = mean_semi_major_axes * (1.0 - mean_eccentricities**2)
    etas: np.ndarray = np.sqrt(1.0 - mean_eccentricities**2)

    E_means: np.ndarray = np.array(
        [
            mean_to_eccentric_anomaly(mean_anomalies[i], mean_eccentricities[i])
            for i in range(mean_elements.shape[0])
        ]
    )
    theta_means: np.ndarray = np.array(
        [
            eccentric_to_true_anomaly(E_means[i], mean_eccentricities[i])
            for i in range(mean_elements.shape[0])
        ]
    )

    cos_i: np.ndarray = np.cos(mean_inclinations)
    sin_i: np.ndarray = np.sin(mean_inclinations)
    cos_theta: np.ndarray = np.cos(theta_means)
    sin_theta: np.ndarray = np.sin(theta_means)

    u_means: np.ndarray = mean_arguments_of_periapsis + theta_means
    cos_2u: np.ndarray = np.cos(2.0 * u_means)
    sin_2u: np.ndarray = np.sin(2.0 * u_means)

    gammas: np.ndarray = 0.5 * J2 * (R_e_m / p_means) ** 2

    one_plus_e_cos_f: np.ndarray = 1.0 + mean_eccentricities * cos_theta
    sin2i: np.ndarray = sin_i**2
    cos2i: np.ndarray = cos_i**2

    a_over_r: np.ndarray = one_plus_e_cos_f / (1.0 - mean_eccentricities**2)
    delta_a_over_a: np.ndarray = gammas * (
        (1.0 - 3.0 * cos2i) * (3.0 * a_over_r - 1.0 / etas - 1.0)
        + 3.0 * sin2i * a_over_r * cos_2u
    )
    osculating_semi_major_axes: np.ndarray = mean_semi_major_axes * (
        1.0 + delta_a_over_a
    )

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

    delta_inclination: np.ndarray = (
        0.5 * gammas * np.sin(2.0 * mean_inclinations) * cos_2u
    )
    osculating_inclinations: np.ndarray = mean_inclinations + delta_inclination

    raan_corrections: np.ndarray = -gammas * cos_i * sin_2u
    osculating_raans: np.ndarray = mean_raans + raan_corrections

    argument_of_periapsis_corrections: np.ndarray = gammas * (
        (5.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * etas)
        + (5.0 * cos2i - 1.0)
        * mean_eccentricities
        * np.sin(2.0 * u_means - theta_means)
        / (2.0 * etas)
        - (1.0 - 3.0 * cos2i) * mean_eccentricities * sin_theta / etas
    )

    argument_of_latitude_corrections: np.ndarray = gammas * (
        (7.0 * cos2i - 1.0) * sin_2u * one_plus_e_cos_f / (2.0 * etas)
    )

    osculating_arguments_of_latitude: np.ndarray = (
        u_means + argument_of_latitude_corrections
    )
    osculating_arguments_of_periapsis: np.ndarray = (
        mean_arguments_of_periapsis + argument_of_periapsis_corrections
    )
    osculating_true_anomalies: np.ndarray = (
        osculating_arguments_of_latitude - osculating_arguments_of_periapsis
    )

    # Normalize angles to [0, 2π)
    osculating_arguments_of_periapsis = osculating_arguments_of_periapsis % (
        2.0 * np.pi
    )
    neg_mask: np.ndarray = osculating_arguments_of_periapsis < 0.0
    osculating_arguments_of_periapsis[neg_mask] += 2.0 * np.pi

    osculating_true_anomalies = osculating_true_anomalies % (2.0 * np.pi)
    neg_mask = osculating_true_anomalies < 0.0
    osculating_true_anomalies[neg_mask] += 2.0 * np.pi

    osculating_eccentricities = np.clip(
        osculating_eccentricities, 0.0, MAX_ECCENTRICITY
    )

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

    return result[0] if single_input else result


def brouwer_mean_to_osculating(
    brouwerian_elements: np.ndarray,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
) -> np.ndarray:
    """Convert Brouwer mean Keplerian elements to osculating elements.

    Alias for :func:`compute_brouwer_short_period_corrections`.

    Parameters
    ----------
    brouwerian_elements : np.ndarray
        Brouwer mean elements [a, e, i, omega, RAAN, M].
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

    Returns
    -------
    np.ndarray
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta].
    """
    return compute_brouwer_short_period_corrections(
        brouwerian_elements, R_e_m=R_e_m, J2=J2
    )


def osculating_to_brouwer_mean(
    osculating_keplerian_elements: np.ndarray,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
    max_iter: int = 20,
    tol_m: float = 1e-12,
) -> np.ndarray:
    """Convert osculating Keplerian elements to Brouwer mean elements.

    Uses iterative inversion of the Brouwer short-period corrections.

    Parameters
    ----------
    osculating_keplerian_elements : np.ndarray, shape (6,)
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta].
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
        Brouwer mean elements [a, e, i, omega, RAAN, M].
    """
    osculating_elements: np.ndarray = np.asarray(
        osculating_keplerian_elements, dtype=float
    )
    if osculating_elements.shape != (6,):
        raise ValueError(
            f"Osculating Keplerian elements must have shape (6,), got {osculating_elements.shape}"
        )

    osc_a = osculating_elements[SEMI_MAJOR_AXIS_INDEX]
    osc_e = osculating_elements[ECCENTRICITY_INDEX]
    osc_i = osculating_elements[INCLINATION_INDEX]
    osc_omega = osculating_elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    osc_raan = osculating_elements[RAAN_INDEX]
    osc_theta = osculating_elements[TRUE_ANOMALY_INDEX]

    mean_a = osc_a
    mean_e = osc_e
    mean_i = osc_i
    mean_raan = osc_raan
    mean_omega = osc_omega
    mean_M = true_to_mean_anomaly(osc_theta, osc_e)

    for _ in range(max_iter):
        osc_from_mean = compute_brouwer_short_period_corrections(
            np.array(
                [mean_a, mean_e, mean_i, mean_omega, mean_raan, mean_M], dtype=float
            ),
            R_e_m=R_e_m,
            J2=J2,
        )

        da = osc_a - osc_from_mean[SEMI_MAJOR_AXIS_INDEX]
        de = osc_e - osc_from_mean[ECCENTRICITY_INDEX]
        di = osc_i - osc_from_mean[INCLINATION_INDEX]
        draan = osc_raan - osc_from_mean[RAAN_INDEX]
        domega = osc_omega - osc_from_mean[ARGUMENT_OF_PERIAPSIS_INDEX]
        dtheta = osc_theta - osc_from_mean[TRUE_ANOMALY_INDEX]

        # Wrap angle differences to [-π, π)
        draan = (draan + np.pi) % (2.0 * np.pi) - np.pi
        domega = (domega + np.pi) % (2.0 * np.pi) - np.pi
        dtheta = (dtheta + np.pi) % (2.0 * np.pi) - np.pi

        mean_a += da
        mean_e += de
        mean_i += di
        mean_raan += draan
        mean_omega += domega

        target_theta = osc_theta - (
            osc_from_mean[TRUE_ANOMALY_INDEX] - mean_to_true_anomaly(mean_M, mean_e)
        )
        mean_M = true_to_mean_anomaly(target_theta, mean_e)

        if abs(da) < tol_m and abs(de) < ECCENTRICITY_CONVERGENCE_TOLERANCE:
            break

    # Normalize angles to [0, 2π)
    mean_raan = mean_raan % (2.0 * np.pi)
    if mean_raan < 0.0:
        mean_raan += 2.0 * np.pi
    mean_omega = mean_omega % (2.0 * np.pi)
    if mean_omega < 0.0:
        mean_omega += 2.0 * np.pi
    mean_M = mean_M % (2.0 * np.pi)
    if mean_M < 0.0:
        mean_M += 2.0 * np.pi

    return np.array(
        [mean_a, mean_e, mean_i, mean_omega, mean_raan, mean_M], dtype=float
    )


def compute_raan_rate(
    keplerian_elements: np.ndarray,
    mu_m3_s2: float,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
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
    a = keplerian_elements[SEMI_MAJOR_AXIS_INDEX]
    e = keplerian_elements[ECCENTRICITY_INDEX]
    i = keplerian_elements[INCLINATION_INDEX]
    n = np.sqrt(mu_m3_s2 / a**3)
    p = a * (1.0 - e**2)
    return -1.5 * n * J2 * (R_e_m / p) ** 2 * np.cos(i)


def brouwer_mean_to_cartesian(
    mean_elements: np.ndarray,
    mu_m3_s2: float,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
) -> np.ndarray:
    """Convert Brouwer mean elements to Cartesian state.

    Applies Brouwer short-period corrections to get osculating elements,
    then converts to Cartesian via :func:`keplerian_to_cartesian`.

    Parameters
    ----------
    mean_elements : np.ndarray
        Brouwer mean elements (6,): [a, e, i, omega, RAAN, M].
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

    Returns
    -------
    np.ndarray
        Cartesian state (6,): [x, y, z, vx, vy, vz] in m and m/s.
    """
    osculating = compute_brouwer_short_period_corrections(
        mean_elements, R_e_m=R_e_m, J2=J2
    )
    return keplerian_to_cartesian(osculating, mu_m3_s2)


# ===================================================================
# BrouwerJ2Propagator class
# ===================================================================


class BrouwerJ2Propagator(Propagator[KeplerianState]):
    """Brouwer J2 secular mean-element propagator.

    Propagates Brouwer mean Keplerian elements using J2 secular rates, then
    converts to Cartesian state via Brouwer short-period corrections.

    Initial state elements must be **Brouwer mean elements** — not osculating,
    not SGP4/TLE mean elements. Element[5] is mean anomaly.

    References
    ----------
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    """

    anomaly_type = AnomalyType.MEAN

    def __init__(
        self,
        initial_state: KeplerianState,
        mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
        R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
        J2: float = EARTH_J2,
    ) -> None:
        """Initialize Brouwer J2 propagator.

        Parameters
        ----------
        initial_state : KeplerianState
            Initial Brouwer mean elements + epoch (TT, s since J2000 TT).
            Element[5] must be mean anomaly.
        mu_m3_s2 : float
            Gravitational parameter (m³/s²). Defaults to Earth's GM.
        R_e_m : float
            Earth equatorial radius (m). Defaults to WGS-84 value.
        J2 : float
            J2 zonal harmonic coefficient. Defaults to WGS-84 value.
        """
        super().__init__()
        self._mu_m3_s2 = mu_m3_s2
        self._R_e_m = R_e_m
        self._J2 = J2
        self.set_initial_state(initial_state)

    def set_initial_state(self, initial_state: KeplerianState) -> None:
        """Set initial Brouwer mean state and reset reference epoch."""
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s

    def get_initial_epoch_s(self) -> float:
        """Return epoch of initial state (TT, s since J2000 TT)."""
        return self._initial_state.epoch_s

    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Propagate to target epoch and return Cartesian state."""
        elapsed_s = target_epoch_s - self.get_initial_epoch_s()
        elems = self._initial_state.elements

        a = elems[SEMI_MAJOR_AXIS_INDEX]
        e = elems[ECCENTRICITY_INDEX]
        i = elems[INCLINATION_INDEX]
        omega = elems[ARGUMENT_OF_PERIAPSIS_INDEX]
        raan = elems[RAAN_INDEX]
        M = elems[MEAN_ANOMALY_INDEX]

        n = np.sqrt(self._mu_m3_s2 / a**3)
        eta = np.sqrt(1.0 - e**2)
        p = a * (1.0 - e**2)
        k = (self._R_e_m / p) ** 2
        cos_i = np.cos(i)
        cos2_i = cos_i**2

        raan_rate = -1.5 * n * self._J2 * k * cos_i
        omega_rate = 0.75 * n * self._J2 * k * (5.0 * cos2_i - 1.0)
        M_rate = n + 0.75 * n * self._J2 * k * eta * (3.0 * cos2_i - 1.0)

        propagated = np.array(
            [
                a,
                e,
                i,
                omega + omega_rate * elapsed_s,
                raan + raan_rate * elapsed_s,
                M + M_rate * elapsed_s,
            ]
        )
        return brouwer_mean_to_cartesian(
            propagated,
            self._mu_m3_s2,
            self._R_e_m,
            self._J2,
        )
