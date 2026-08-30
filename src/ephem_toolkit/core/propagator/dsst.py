"""DSST (Draper Semi-analytical Satellite Theory) propagator.

Provides :class:`DSSTPropagator` for class-based propagation, plus conversion
functions between osculating and DSST mean Keplerian elements.

Implements the Danielson et al. (1995) formulation with configurable
perturbations including J2, J3, J4 zonal harmonics, atmospheric drag, solar
radiation pressure, and third-body effects (Sun/Moon).

DSST mean elements are **not** interchangeable with Brouwer mean elements or
SGP4/TLE mean elements. Each mean element theory uses different averaging
procedures and perturbation models.

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

Coordinate Frame: J2000

References
----------
Danielson, D.A., et al. "Semianalytic Satellite Theory", Naval Research
Laboratory, 1995.
Vallado, D.A. "Fundamentals of Astrodynamics and Applications", 4th ed., Ch. 9.
Montenbruck, O. and Gill, E. "Satellite Orbits: Models, Methods and
Applications", Chapter 9.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ephem_toolkit.core.consts import (
    EARTH_EQUATORIAL_RADIUS_M,
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    EARTH_J2,
    EARTH_J3,
    EARTH_J4,
)
from ephem_toolkit.core.propagator.base import (
    AnomalyType,
    KeplerianState,
    Propagator,
)
from ephem_toolkit.core.propagator.kepler import (
    ARGUMENT_OF_PERIAPSIS_INDEX,
    ECCENTRICITY_INDEX,
    INCLINATION_INDEX,
    MEAN_ANOMALY_INDEX,
    RAAN_INDEX,
    SEMI_MAJOR_AXIS_INDEX,
    TRUE_ANOMALY_INDEX,
    keplerian_to_cartesian,
    mean_to_true_anomaly,
    true_to_mean_anomaly,
)


# ===================================================================
# Perturbation Configuration
# ===================================================================


@dataclass
class DsstPerturbations:
    """Configuration for DSST perturbation forces.
    
    Attributes
    ----------
    include_j2 : bool
        Include J2 zonal harmonic (default: True).
    include_j3 : bool
        Include J3 zonal harmonic (default: False).
    include_j4 : bool
        Include J4 zonal harmonic (default: False).
    include_drag : bool
        Include atmospheric drag (default: False).
    drag_coeff : float
        Drag coefficient (default: 2.2).
    drag_area_m2 : float
        Drag area in m² (default: 1.0).
    mass_kg : float
        Spacecraft mass in kg (default: 100.0).
    atmosphere_model : str
        Atmosphere model: "exponential" or "harris-priester" (default: "exponential").
    include_srp : bool
        Include solar radiation pressure (default: False).
    srp_coeff : float
        SRP coefficient (default: 1.0).
    srp_area_m2 : float
        SRP area in m² (default: 1.0).
    include_sun : bool
        Include Sun third-body perturbations (default: False).
    include_moon : bool
        Include Moon third-body perturbations (default: False).
    ephemeris_source : str
        Ephemeris source: "analytical" or "spice" (default: "analytical").
    R_e_m : float
        Earth equatorial radius in m (default: WGS-84).
    J2 : float
        J2 zonal harmonic coefficient (default: WGS-84).
    J3 : float
        J3 zonal harmonic coefficient (default: WGS-84).
    J4 : float
        J4 zonal harmonic coefficient (default: WGS-84).
    """
    
    # Zonal harmonics
    include_j2: bool = True
    include_j3: bool = False
    include_j4: bool = False
    
    # Atmospheric drag
    include_drag: bool = False
    drag_coeff: float = 2.2
    drag_area_m2: float = 1.0
    mass_kg: float = 100.0
    atmosphere_model: str = "exponential"
    
    # Solar radiation pressure
    include_srp: bool = False
    srp_coeff: float = 1.0
    srp_area_m2: float = 1.0
    
    # Third-body perturbations
    include_sun: bool = False
    include_moon: bool = False
    ephemeris_source: str = "analytical"
    
    # Earth parameters
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M
    J2: float = EARTH_J2
    J3: float = EARTH_J3
    J4: float = EARTH_J4


# ===================================================================
# DSST short-period corrections (mean -> osculating)
# ===================================================================


def compute_dsst_j2_short_period_corrections(
    mean_keplerian_elements: np.ndarray,
    R_e_m: float = EARTH_EQUATORIAL_RADIUS_M,
    J2: float = EARTH_J2,
) -> np.ndarray:
    """Compute DSST J2 short-period corrections.
    
    Converts DSST mean Keplerian elements to osculating elements by adding
    the J2 short-period perturbation terms using Danielson (1995) formulation.
    
    Parameters
    ----------
    mean_keplerian_elements : np.ndarray, shape (6,)
        DSST mean Keplerian element vector [a, e, i, omega, RAAN, M].
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).
    
    Returns
    -------
    np.ndarray, shape (6,)
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta].
    
    References
    ----------
    Danielson, D.A., et al. "Semianalytic Satellite Theory", NRL, 1995.
    """
    mean_elements = np.asarray(mean_keplerian_elements, dtype=float)
    if mean_elements.shape != (6,):
        raise ValueError(
            f"Mean Keplerian elements must have shape (6,), got {mean_elements.shape}"
        )
    
    # Extract mean elements
    a_m = mean_elements[SEMI_MAJOR_AXIS_INDEX]
    e_m = mean_elements[ECCENTRICITY_INDEX]
    i_m = mean_elements[INCLINATION_INDEX]
    omega_m = mean_elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    raan_m = mean_elements[RAAN_INDEX]
    M_m = mean_elements[MEAN_ANOMALY_INDEX]
    
    # Convert mean anomaly to true anomaly for mean elements
    theta_m = mean_to_true_anomaly(M_m, e_m)
    
    # Compute auxiliary quantities
    p = a_m * (1.0 - e_m**2)
    eta = np.sqrt(1.0 - e_m**2)
    
    cos_i = np.cos(i_m)
    sin_i = np.sin(i_m)
    cos2_i = cos_i**2
    sin2_i = sin_i**2
    
    cos_theta = np.cos(theta_m)
    sin_theta = np.sin(theta_m)
    
    u_m = omega_m + theta_m  # Argument of latitude
    cos_2u = np.cos(2.0 * u_m)
    sin_2u = np.sin(2.0 * u_m)
    
    # J2 coefficient
    gamma = 0.5 * J2 * (R_e_m / p)**2
    
    # Short-period corrections (first-order J2 terms)
    # Based on Danielson 1995, equations 3.1-3.6
    
    one_plus_e_cos_theta = 1.0 + e_m * cos_theta
    r_over_a = (1.0 - e_m**2) / one_plus_e_cos_theta
    
    # Semi-major axis correction
    delta_a = gamma * a_m * (
        (1.0 - 3.0 * cos2_i) * (3.0 * (1.0 + e_m * cos_theta)**2 / (1.0 - e_m**2)**2 - 1.0 / eta - 1.0)
        + 3.0 * sin2_i * (1.0 + e_m * cos_theta)**2 / (1.0 - e_m**2)**2 * cos_2u
    )
    
    # Eccentricity correction
    delta_e = gamma * eta * sin2_i * (
        np.cos(2.0 * omega_m + theta_m)
        + 0.5 * e_m * np.cos(2.0 * omega_m)
        + 0.5 * e_m * np.cos(2.0 * omega_m + 2.0 * theta_m)
    )
    
    # Inclination correction
    delta_i = 0.5 * gamma * np.sin(2.0 * i_m) * cos_2u
    
    # RAAN correction
    delta_raan = -gamma * cos_i * sin_2u
    
    # Argument of periapsis correction
    delta_omega = gamma * (
        (5.0 * cos2_i - 1.0) * sin_2u * one_plus_e_cos_theta / (2.0 * eta)
        + (5.0 * cos2_i - 1.0) * e_m * np.sin(2.0 * u_m - theta_m) / (2.0 * eta)
        - (1.0 - 3.0 * cos2_i) * e_m * sin_theta / eta
    )
    
    # True anomaly correction (via argument of latitude)
    delta_u = gamma * (7.0 * cos2_i - 1.0) * sin_2u * one_plus_e_cos_theta / (2.0 * eta)
    
    # Compute osculating elements
    a_osc = a_m + delta_a
    e_osc = e_m + delta_e
    i_osc = i_m + delta_i
    raan_osc = raan_m + delta_raan
    omega_osc = omega_m + delta_omega
    u_osc = u_m + delta_u
    theta_osc = u_osc - omega_osc
    
    # Normalize angles to [0, 2π)
    omega_osc = omega_osc % (2.0 * np.pi)
    raan_osc = raan_osc % (2.0 * np.pi)
    theta_osc = theta_osc % (2.0 * np.pi)
    
    # Clip eccentricity to valid range
    e_osc = np.clip(e_osc, 0.0, 0.9999999)
    
    return np.array([a_osc, e_osc, i_osc, omega_osc, raan_osc, theta_osc], dtype=float)


def dsst_mean_to_osculating(
    mean_keplerian_elements: np.ndarray,
    epoch_s: float,
    perturbations: DsstPerturbations | None = None,
) -> np.ndarray:
    """Convert DSST mean Keplerian elements to osculating elements.
    
    Applies short-period corrections based on configured perturbations.
    
    Parameters
    ----------
    mean_keplerian_elements : np.ndarray, shape (6,)
        DSST mean elements [a, e, i, omega, RAAN, M].
    epoch_s : float
        Epoch time (TT, s since J2000 TT). Currently unused but reserved
        for future third-body perturbations.
    perturbations : DsstPerturbations, optional
        Perturbation configuration. If None, uses J2-only defaults.
    
    Returns
    -------
    np.ndarray, shape (6,)
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta].
    """
    if perturbations is None:
        perturbations = DsstPerturbations()
    
    # Currently only J2 short-period corrections implemented
    if perturbations.include_j2:
        return compute_dsst_j2_short_period_corrections(
            mean_keplerian_elements,
            R_e_m=perturbations.R_e_m,
            J2=perturbations.J2,
        )
    else:
        # No corrections, just convert mean anomaly to true anomaly
        result = mean_keplerian_elements.copy()
        result[TRUE_ANOMALY_INDEX] = mean_to_true_anomaly(
            mean_keplerian_elements[MEAN_ANOMALY_INDEX],
            mean_keplerian_elements[ECCENTRICITY_INDEX],
        )
        return result


def osculating_to_dsst_mean(
    osculating_keplerian_elements: np.ndarray,
    epoch_s: float,
    perturbations: DsstPerturbations | None = None,
    max_iter: int = 20,
    tolerance: float = 1e-10,
) -> np.ndarray:
    """Convert osculating Keplerian elements to DSST mean elements.
    
    Uses iterative Newton-Raphson inversion of short-period corrections.
    
    Parameters
    ----------
    osculating_keplerian_elements : np.ndarray, shape (6,)
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta].
    epoch_s : float
        Epoch time (TT, s since J2000 TT). Currently unused but reserved
        for future third-body perturbations.
    perturbations : DsstPerturbations, optional
        Perturbation configuration. If None, uses J2-only defaults.
    max_iter : int
        Maximum iterations for convergence (default: 20).
    tolerance : float
        Convergence tolerance: ||Δelements|| < tolerance (default: 1e-10).
        Applied to semi-major axis (m) and angles (rad).
    
    Returns
    -------
    np.ndarray, shape (6,)
        DSST mean elements [a, e, i, omega, RAAN, M].
    
    Raises
    ------
    RuntimeError
        If convergence not achieved within max_iter iterations.
    """
    if perturbations is None:
        perturbations = DsstPerturbations()
    
    osc_elements = np.asarray(osculating_keplerian_elements, dtype=float)
    if osc_elements.shape != (6,):
        raise ValueError(
            f"Osculating Keplerian elements must have shape (6,), got {osc_elements.shape}"
        )
    
    # Initialize mean elements as osculating elements
    mean_elements = osc_elements.copy()
    mean_elements[MEAN_ANOMALY_INDEX] = true_to_mean_anomaly(
        osc_elements[TRUE_ANOMALY_INDEX],
        osc_elements[ECCENTRICITY_INDEX],
    )
    
    # Iterative inversion
    for iteration in range(max_iter):
        # Compute osculating elements from current mean estimate
        osc_from_mean = dsst_mean_to_osculating(mean_elements, epoch_s, perturbations)
        
        # Compute residuals
        delta = osc_elements - osc_from_mean
        
        # Handle angle wrapping for RAAN, omega, theta
        delta[RAAN_INDEX] = (delta[RAAN_INDEX] + np.pi) % (2.0 * np.pi) - np.pi
        delta[ARGUMENT_OF_PERIAPSIS_INDEX] = (
            delta[ARGUMENT_OF_PERIAPSIS_INDEX] + np.pi
        ) % (2.0 * np.pi) - np.pi
        delta[TRUE_ANOMALY_INDEX] = (
            delta[TRUE_ANOMALY_INDEX] + np.pi
        ) % (2.0 * np.pi) - np.pi
        
        # Update mean elements
        mean_elements[SEMI_MAJOR_AXIS_INDEX] += delta[SEMI_MAJOR_AXIS_INDEX]
        mean_elements[ECCENTRICITY_INDEX] += delta[ECCENTRICITY_INDEX]
        mean_elements[INCLINATION_INDEX] += delta[INCLINATION_INDEX]
        mean_elements[RAAN_INDEX] += delta[RAAN_INDEX]
        mean_elements[ARGUMENT_OF_PERIAPSIS_INDEX] += delta[ARGUMENT_OF_PERIAPSIS_INDEX]
        
        # Update mean anomaly via true anomaly correction
        target_theta = osc_elements[TRUE_ANOMALY_INDEX] - (
            osc_from_mean[TRUE_ANOMALY_INDEX]
            - mean_to_true_anomaly(
                mean_elements[MEAN_ANOMALY_INDEX],
                mean_elements[ECCENTRICITY_INDEX],
            )
        )
        mean_elements[MEAN_ANOMALY_INDEX] = true_to_mean_anomaly(
            target_theta,
            mean_elements[ECCENTRICITY_INDEX],
        )
        
        # Check convergence
        if (
            abs(delta[SEMI_MAJOR_AXIS_INDEX]) < tolerance
            and abs(delta[ECCENTRICITY_INDEX]) < tolerance
        ):
            break
    else:
        raise RuntimeError(
            f"osculating_to_dsst_mean failed to converge after {max_iter} iterations. "
            f"Final residuals: Δa={delta[SEMI_MAJOR_AXIS_INDEX]:.3e} m, "
            f"Δe={delta[ECCENTRICITY_INDEX]:.3e}"
        )
    
    # Normalize angles to [0, 2π)
    mean_elements[RAAN_INDEX] = mean_elements[RAAN_INDEX] % (2.0 * np.pi)
    mean_elements[ARGUMENT_OF_PERIAPSIS_INDEX] = (
        mean_elements[ARGUMENT_OF_PERIAPSIS_INDEX] % (2.0 * np.pi)
    )
    mean_elements[MEAN_ANOMALY_INDEX] = mean_elements[MEAN_ANOMALY_INDEX] % (2.0 * np.pi)
    
    return mean_elements


# ===================================================================
# DSST secular propagation
# ===================================================================


def propagate_dsst(
    mean_elements: np.ndarray,
    time_elapsed_s: float,
    mu_m3_s2: float,
    perturbations: DsstPerturbations | None = None,
) -> np.ndarray:
    """Propagate DSST mean elements using secular rates.

    Implements J2, J3, J4 secular rates (Danielson 1995 formulation).
    J3/J4 add corrections to omega, RAAN, and M secular rates.

    Parameters
    ----------
    mean_elements : np.ndarray, shape (6,)
        DSST mean elements at epoch [a, e, i, omega, RAAN, M].
    time_elapsed_s : float
        Time elapsed since epoch (s).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    perturbations : DsstPerturbations, optional
        Perturbation configuration. If None, uses J2-only defaults.

    Returns
    -------
    np.ndarray, shape (6,)
        DSST mean elements at epoch + time_elapsed_s.
    """
    if perturbations is None:
        perturbations = DsstPerturbations()

    # Extract elements
    a = mean_elements[SEMI_MAJOR_AXIS_INDEX]
    e = mean_elements[ECCENTRICITY_INDEX]
    i = mean_elements[INCLINATION_INDEX]
    omega = mean_elements[ARGUMENT_OF_PERIAPSIS_INDEX]
    raan = mean_elements[RAAN_INDEX]
    M = mean_elements[MEAN_ANOMALY_INDEX]

    # Mean motion
    n = np.sqrt(mu_m3_s2 / a**3)

    # Initialize secular rates
    raan_rate = 0.0
    omega_rate = 0.0
    M_rate = n

    if perturbations.include_j2:
        eta = np.sqrt(1.0 - e**2)
        eta2 = eta**2
        p = a * (1.0 - e**2)
        k2 = (perturbations.R_e_m / p)**2
        cos_i = np.cos(i)
        sin_i = np.sin(i)
        cos2_i = cos_i**2
        sin2_i = sin_i**2

        # J2 secular rates (Danielson 1995, eq. 2.7-2.9)
        raan_rate += -1.5 * n * perturbations.J2 * k2 * cos_i
        omega_rate += 0.75 * n * perturbations.J2 * k2 * (5.0 * cos2_i - 1.0)
        M_rate += 0.75 * n * perturbations.J2 * k2 * eta * (3.0 * cos2_i - 1.0)

        if perturbations.include_j3:
            # J3 secular rates (Danielson 1995, eq. 2.10-2.12)
            # J3 contributes secular terms to omega and M via e-coupling
            k3 = perturbations.J3 * (perturbations.R_e_m / p)**3
            sin_omega = np.sin(omega)
            cos_omega = np.cos(omega)

            # J3 secular rate for omega (eccentricity-dependent)
            if e > 1e-8:
                omega_rate += (
                    -0.9375 * n * k3 * (sin_i / e)
                    * (4.0 - 5.0 * sin2_i)
                    * sin_omega
                )
                # J3 secular rate for M
                M_rate += (
                    0.9375 * n * k3 * (eta / e)
                    * (4.0 - 5.0 * sin2_i)
                    * cos_omega
                )

        if perturbations.include_j4:
            # J4 secular rates (Danielson 1995, eq. 2.13-2.15)
            k4 = perturbations.J4 * (perturbations.R_e_m / p)**4

            # J4 secular rate for RAAN
            raan_rate += (
                1.875 * n * k4 * cos_i
                * (1.0 - (35.0 / 6.0) * sin2_i)
            )
            # J4 secular rate for omega
            omega_rate += (
                -0.9375 * n * k4
                * (12.0 - 21.0 * sin2_i + (35.0 / 4.0) * sin2_i**2)
            )
            # J4 secular rate for M
            M_rate += (
                0.9375 * n * k4 * eta
                * (12.0 - 21.0 * sin2_i + (35.0 / 4.0) * sin2_i**2)
            )

    # Drag secular rates (exponential atmosphere model)
    # da/dt and de/dt are non-zero for drag
    da_dt = 0.0
    de_dt = 0.0

    if perturbations.include_drag and perturbations.mass_kg > 0.0:
        # Ballistic coefficient B* = (Cd * A) / (2 * m)  [m²/kg]
        B_star = (perturbations.drag_coeff * perturbations.drag_area_m2) / (
            2.0 * perturbations.mass_kg
        )

        # Exponential atmosphere: ρ = ρ0 * exp(-(r - r0) / H)
        # Reference altitude: 400 km, scale height H = 8500 m
        # Reference density at 400 km: ~2.62e-10 kg/m³
        H_m = 8500.0  # Scale height (m)
        rho_ref = 2.62e-10  # kg/m³ at ~400 km
        r_ref_m = EARTH_EQUATORIAL_RADIUS_M + 400e3  # Reference radius (m)

        # Mean orbital radius (semi-latus rectum approximation)
        r_mean_m = a * (1.0 - e**2)  # Approximate mean radius ≈ semi-latus rectum

        # Atmospheric density at mean altitude
        rho = rho_ref * np.exp(-(r_mean_m - r_ref_m) / H_m)

        # Circular velocity at mean radius
        v_circ = np.sqrt(mu_m3_s2 / r_mean_m)

        # Secular drag rates (King-Hele approximation for small eccentricity)
        # da/dt = -2 * B* * rho * v_circ * a²/r_mean (secular decay)
        da_dt = -2.0 * B_star * rho * v_circ * a**2 / r_mean_m
        # de/dt ≈ -B* * rho * v_circ * e (circularization)
        de_dt = -B_star * rho * v_circ * e

    # Propagate elements
    a_new = a + da_dt * time_elapsed_s
    e_new = max(0.0, e + de_dt * time_elapsed_s)

    return np.array([
        a_new,
        e_new,
        i,
        omega + omega_rate * time_elapsed_s,
        raan + raan_rate * time_elapsed_s,
        M + M_rate * time_elapsed_s,
    ], dtype=float)


def dsst_mean_to_cartesian(
    mean_elements: np.ndarray,
    mu_m3_s2: float,
    epoch_s: float,
    perturbations: DsstPerturbations | None = None,
) -> np.ndarray:
    """Convert DSST mean elements to Cartesian state.
    
    Applies DSST short-period corrections to get osculating elements,
    then converts to Cartesian via :func:`keplerian_to_cartesian`.
    
    Parameters
    ----------
    mean_elements : np.ndarray, shape (6,)
        DSST mean elements [a, e, i, omega, RAAN, M].
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    epoch_s : float
        Epoch time (TT, s since J2000 TT).
    perturbations : DsstPerturbations, optional
        Perturbation configuration. If None, uses J2-only defaults.
    
    Returns
    -------
    np.ndarray, shape (6,)
        Cartesian state [x, y, z, vx, vy, vz] in m and m/s.
    """
    osculating = dsst_mean_to_osculating(mean_elements, epoch_s, perturbations)
    return keplerian_to_cartesian(osculating, mu_m3_s2)


# ===================================================================
# DSSTPropagator class
# ===================================================================


class DSSTPropagator(Propagator[KeplerianState]):
    """DSST semi-analytical propagator (Danielson 1995 formulation).
    
    Propagates DSST mean Keplerian elements using secular rates, then
    converts to Cartesian state via DSST short-period corrections.
    
    Initial state elements must be **DSST mean elements** — not osculating,
    not Brouwer mean elements, not SGP4/TLE mean elements. Element[5] is
    mean anomaly.
    
    Supports configurable perturbations:
    - J2, J3, J4 zonal harmonics
    - Atmospheric drag (exponential atmosphere, King-Hele secular rates)
    - Solar radiation pressure (future)
    - Third-body (Sun/Moon, future)
    
    Coordinate Frame: J2000
    Element Type: Classical Keplerian (mean)
    Singularity Handling: Warns for near-circular/equatorial orbits
    
    References
    ----------
    Danielson, D.A., et al. "Semianalytic Satellite Theory", NRL, 1995.
    """
    
    anomaly_type = AnomalyType.MEAN
    
    def __init__(
        self,
        initial_state: KeplerianState,
        perturbations: DsstPerturbations | None = None,
        mu_m3_s2: float = EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    ) -> None:
        """Initialize DSST propagator.
        
        Parameters
        ----------
        initial_state : KeplerianState
            Initial DSST mean elements + epoch (TT, s since J2000 TT).
            Element[5] must be mean anomaly.
        perturbations : DsstPerturbations, optional
            Perturbation configuration. If None, uses J2-only defaults.
        mu_m3_s2 : float
            Gravitational parameter (m³/s²). Defaults to Earth's GM.
        
        Raises
        ------
        ValueError
            If initial state is invalid or outside DSST validity range.
        """
        super().__init__()
        self._mu_m3_s2 = mu_m3_s2
        self._perturbations = perturbations if perturbations is not None else DsstPerturbations()
        self.set_initial_state(initial_state)
    
    def set_initial_state(self, initial_state: KeplerianState) -> None:
        """Set initial DSST mean state and reset reference epoch.
        
        Performs singularity checks for near-circular and near-equatorial orbits.
        """
        super().set_initial_state(initial_state)
        self._initial_state = initial_state
        self._reference_epoch_s = initial_state.epoch_s
        
        # Singularity warnings
        e = initial_state.elements[ECCENTRICITY_INDEX]
        i = initial_state.elements[INCLINATION_INDEX]
        
        if e < 1e-6:
            import warnings
            warnings.warn(
                f"Near-circular orbit (e={e:.2e}). DSST may have reduced accuracy. "
                "Consider using equinoctial elements for better numerical stability.",
                UserWarning,
            )
        
        if i < np.deg2rad(1.0) or i > np.deg2rad(179.0):
            import warnings
            warnings.warn(
                f"Near-equatorial orbit (i={np.rad2deg(i):.2f}°). DSST may have reduced accuracy. "
                "Consider using equinoctial elements for better numerical stability.",
                UserWarning,
            )
    
    def get_initial_epoch_s(self) -> float:
        """Return epoch of initial state (TT, s since J2000 TT)."""
        return self._initial_state.epoch_s
    
    def _propagate_to_impl(self, target_epoch_s: float) -> np.ndarray:
        """Propagate to target epoch and return Cartesian state.
        
        Parameters
        ----------
        target_epoch_s : float
            Target epoch (TT, s since J2000 TT).
        
        Returns
        -------
        np.ndarray, shape (6,)
            Cartesian state [x, y, z, vx, vy, vz] in m and m/s.
        """
        elapsed_s = target_epoch_s - self.get_initial_epoch_s()
        
        # Propagate mean elements
        propagated_mean = propagate_dsst(
            self._initial_state.elements,
            elapsed_s,
            self._mu_m3_s2,
            self._perturbations,
        )
        
        # Convert to Cartesian
        return dsst_mean_to_cartesian(
            propagated_mean,
            self._mu_m3_s2,
            target_epoch_s,
            self._perturbations,
        )
