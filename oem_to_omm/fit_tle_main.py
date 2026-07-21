"""Fit TLE mean elements to OEM state vectors using J2 secular propagation.

This module provides functions to fit TLE (Two-Line Element) mean orbital
elements to Orbit Ephemeris Message (OEM) state vectors. The fitting process
estimates SGP4-compatible mean elements including TLE-specific parameters
like BSTAR drag term and mean motion derivatives.

The TLE fitting uses a Gauss-Newton velocity-only fitting approach where:
  - The epoch position r₀ is fixed to the first OEM position.
  - The epoch velocity v₀ is estimated via least-squares minimization
    of position residuals over the fit arc using J2 secular propagation.
  - TLE-specific parameters (BSTAR, mean motion derivatives) are estimated
    from the fitted arc.

This approach ensures the initial position matches the OEM exactly while
optimizing the velocity to best fit the arc under mean element propagation.

References:
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Ch. 8.
    SGP4 propagation model and TLE element fitting procedures.
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.common as common
import common.consts as consts
import common.time_utils as time_utils
import common.tle as tle
import common.convert_tle as convert_tle
from . import fit_common
from .fit_tle import constants
from .fit_tle import estimation
from .fit_tle import models
from .fit_tle import refinement
from .fit_tle import tle_builder

# ===================================================================
# Constants
# ===================================================================

SECONDS_PER_DAY: float = 86400.0
"""Seconds per day (time conversion constant)."""

MINUTES_PER_DAY: float = 1440.0
"""Minutes per day (time conversion constant)."""

TWO_PI: float = 2.0 * math.pi
"""2*pi (radians per revolution)."""

# SGP4 gravitational constant ke in [Earth radii^(3/2) / min].
# From Spacetrack Report No. 3 (Hoots & Roehrich, 1980), this value
# encodes the WGS-72 gravitational parameter mu = 398600.8 km^3/s^2
# with Earth equatorial radius R_e = 6378.135 km.
#
# ke = sqrt(mu) expressed in units where length = Earth radii and
# time = minutes:
#   ke = sqrt(3.986008e5 km^3/s^2) * (60 s/min) / (6378.135 km)^(3/2)
#      = 0.0743669161 [R_e^(3/2) / min]
_SGP4_KE: float = 0.0743669161
"""SGP4 gravitational constant ke (Earth radii^(3/2) / min).

This is the canonical value from Spacetrack Report No. 3 that defines
the relationship between semi-major axis and mean motion inside the
SGP4 propagator.  Using any other gravitational parameter to compute
the TLE mean motion field will produce a systematic semi-major axis
bias when SGP4 interprets the element set.

References:
    Hoots, F.R. & Roehrich, R.L. "Spacetrack Report No. 3", 1980.
    Vallado, D.A. et al. "Revisiting Spacetrack Report #3", AIAA 2006-6753.
"""

_SGP4_R_E_KM: float = 6378.135
"""SGP4 Earth equatorial radius (km), WGS-72."""


# ===================================================================
# SGP4-compatible mean motion
# ===================================================================


def _sgp4_mean_motion_rev_per_day(semi_major_axis_m: float) -> float:
    """Compute SGP4-compatible mean motion from semi-major axis.

    Converts semi-major axis to mean motion using the SGP4 gravitational
    constant ke, ensuring the resulting TLE mean motion field is interpreted
    correctly by any standard SGP4 propagator.

    The SGP4 model internally relates mean motion n (rad/min) to
    semi-major axis a (Earth radii) via:

        n = ke / a^(3/2)

    This function accepts semi-major axis in metres and returns mean motion
    in revolutions per day, matching the TLE field convention.

    Parameters
    ----------
    semi_major_axis_m : float
        Semi-major axis in metres.

    Returns
    -------
    float
        Mean motion in revolutions per day, compatible with SGP4.

    Notes
    -----
    This function is self-contained and does not reference the generic
    kepler.semi_major_axis_to_mean_motion utility, which uses the
    WGS-84 gravitational parameter.  The difference between WGS-72
    (SGP4) and WGS-84 mu values is ~0.4 km^3/s^2, which translates to a
    ~1 km semi-major axis bias if the wrong mu is used.
    """
    # Convert semi-major axis from metres to Earth radii (WGS-72)
    a_er: float = semi_major_axis_m / (_SGP4_R_E_KM * 1000.0)

    # Mean motion in rad/min: n = ke / a^(3/2)
    n_rad_per_min: float = _SGP4_KE / (a_er**1.5)

    # Convert to rev/day: (rad/min) * (min/day) / (rad/rev)
    n_rev_per_day: float = n_rad_per_min * MINUTES_PER_DAY / TWO_PI

    return n_rev_per_day


# ===================================================================
# TudatPy
# ===================================================================

from tudatpy.dynamics import environment_setup
from tudatpy.interface import spice


def load_spice_kernels() -> None:
    """Load SPICE kernels required for time conversion.

    Parameters
    ----------

    Notes
    -----
    Type annotations omitted for TudatPy modules to avoid import-time dependencies.
    """
    spice_kernel_files = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
    ]

    for kernel_file in spice_kernel_files:
        spice.load_kernel(common.get_spice_kernel_path() + "/" + kernel_file)


def create_tle_ephemeris(line1, line2, object_name):
    tle_ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
    tle_ephemeris = environment_setup.create_body_ephemeris(
        tle_ephemeris_settings, body_name=object_name
    )
    return tle_ephemeris


load_spice_kernels()

# ===================================================================
# Internal helpers
# ===================================================================


def _estimate_mean_motion_derivative(
    states: list[tuple[float, np.ndarray]],
    mu_m3_s2: float,
) -> float:
    """Estimate the first time derivative of mean motion from OEM states.

    Uses linear regression on the SGP4-compatible mean motion computed from
    each state's semi-major axis to estimate the secular drift rate.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector) tuples.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    float
        First time derivative of mean motion in rev/day².
    """
    if len(states) < 2:
        return 0.0

    reference_timestamp: float = states[0][0]
    times_day: list[float] = []
    mean_motion_series: list[float] = []

    for timestamp, state_vector in states:
        time_offset_day: float = (timestamp - reference_timestamp) / SECONDS_PER_DAY

        # Compute osculating Keplerian elements using local function
        try:
            kep_elements: np.ndarray = _cartesian_to_osculating_keplerian(
                state_vector, mu_m3_s2
            )
            a_m: float = float(kep_elements[0])  # Semi-major axis is index 0
            # Use SGP4-compatible mean motion for consistency with TLE output
            mean_motion_rev_day: float = _sgp4_mean_motion_rev_per_day(a_m)
            times_day.append(time_offset_day)
            mean_motion_series.append(mean_motion_rev_day)
        except Exception:
            continue

    if len(times_day) < 2:
        return 0.0

    # Linear regression: mean_motion = intercept + slope * time
    times_arr: np.ndarray = np.array(times_day)
    mm_arr: np.ndarray = np.array(mean_motion_series)

    n: int = len(times_arr)
    sum_t: float = float(np.sum(times_arr))
    sum_mm: float = float(np.sum(mm_arr))
    sum_t2: float = float(np.sum(times_arr**2))
    sum_t_mm: float = float(np.sum(times_arr * mm_arr))

    denom: float = n * sum_t2 - sum_t**2
    if abs(denom) < 1e-20:
        return 0.0

    slope: float = (n * sum_t_mm - sum_t * sum_mm) / denom
    return slope


def _estimate_bstar_from_drag(
    mean_motion_derivative: float,
    semi_major_axis_m: float,
    eccentricity: float,
) -> float:
    """Estimate BSTAR drag term from mean motion derivative.

    Uses a simplified relationship between BSTAR and mean motion derivative
    based on atmospheric drag theory. This is an approximation suitable for
    LEO satellites.

    Parameters
    ----------
    mean_motion_derivative : float
        First time derivative of mean motion (rev/day²).
    semi_major_axis_m : float
        Semi-major axis (m).
    eccentricity : float
        Orbital eccentricity (dimensionless).

    Returns
    -------
    float
        BSTAR drag term (1/Earth radii).
    """
    # Simplified drag model: BSTAR is related to mean motion derivative
    # through the ballistic coefficient and atmospheric density.
    # This is a rough approximation; actual BSTAR fitting would require
    # SGP4 propagation and optimization.

    if abs(mean_motion_derivative) < 1e-12:
        return 0.0

    # Approximate BSTAR from mean motion derivative using simplified relationship:
    # ṅ ≈ -2/3 * n * BSTAR * ρ * a
    # where ρ is atmospheric density (highly variable)

    # For LEO, typical BSTAR values are in the range 1e-5 to 1e-3 (1/Earth radii)
    # We use a heuristic scaling based on the mean motion derivative

    # Convert mean motion derivative from rev/day² to rad/s²
    n_dot_rad_s2: float = mean_motion_derivative * 2.0 * math.pi / (SECONDS_PER_DAY**2)

    # Compute mean motion in rad/s
    n_rad_s: float = math.sqrt(
        consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2 / (semi_major_axis_m**3)
    )

    # Heuristic BSTAR estimate
    # BSTAR has units of 1/Earth_radii in TLE format
    if abs(n_rad_s) > 1e-12:
        # Scale factor to convert to BSTAR units
        bstar_estimate: float = abs(n_dot_rad_s2 / n_rad_s) * 1e4
        if mean_motion_derivative > 0:
            bstar_estimate = -bstar_estimate  # Negative for decaying orbits
        # Clamp to reasonable range [-1.0, 1.0]
        bstar_estimate = max(-1.0, min(1.0, bstar_estimate))
    else:
        bstar_estimate = 0.0

    return bstar_estimate


# ===================================================================
# Public API
# ===================================================================


def _compute_sgp4_residuals_from_mean_elements(
    mean_elements: np.ndarray,
    epoch_year: int,
    epoch_day: float,
    time_offsets_s: np.ndarray,
    target_positions_m: np.ndarray,
) -> np.ndarray:
    """Compute position residuals between SGP4-propagated states and target positions.

    Parameters
    ----------
    mean_elements : np.ndarray
        Mean Keplerian elements [a, e, i, omega, RAAN, M] in meters and radians.
    epoch_year : int
        TLE epoch year (2-digit).
    epoch_day : float
        TLE epoch day of year.
    time_offsets_s : np.ndarray
        Time offsets from epoch in seconds, shape (N,).
    target_positions_m : np.ndarray
        Target positions in meters, shape (N, 3).

    Returns
    -------
    np.ndarray
        Position residuals, shape (N*3,) in meters.
    """
    a_m, e, i_rad, omega_rad, raan_rad, M_rad = [float(x) for x in mean_elements]

    # Create TLE from mean elements
    test_tle: tle.Tle = _create_test_tle(
        a_m, e, i_rad, omega_rad, raan_rad, M_rad, epoch_year, epoch_day
    )

    line1_str, line2_str = tle.format_tle_strings(test_tle)
    tle_ephemeris = create_tle_ephemeris(line1_str, line2_str, object_name="FIT")

    n_samples: int = len(time_offsets_s)
    residuals: np.ndarray = np.zeros(n_samples * 3)

    for i, dt_s in enumerate(time_offsets_s):
        predicted_state: np.ndarray = tle_ephemeris.cartesian_state(
            tle_ephemeris.tle.reference_epoch + dt_s
        )
        residuals[i * 3 : i * 3 + 3] = target_positions_m[i] - predicted_state[:3]

    return residuals


def fit_tle(
    states: list[tuple[float, np.ndarray]],
    fit_span_s: float,
    refinement_method: str = "none",
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    max_iterations: int = 50,
    R_e_m: float = consts.EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
    object_name: str = "OBJECT",
    object_id: str = "UNKNOWN",
    norad_cat_id: int = 0,
    classification_type: str = "U",
    ephemeris_type: int = 2,
    element_set_number: int = 999,
    revolution_number_at_epoch: int = 0,
    bstar: str = "00000+0",
    mean_motion_second_derivative: str = "00000+0",
) -> tuple[tle.Tle, fit_common.FitDiagnostics]:
    """Fit TLE mean elements to OEM state vectors.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector) tuples.
    fit_span_s : float
        Maximum arc span (s).
    refinement_method : str
        Refinement method: "none", "keplerian", or "cartesian".
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    max_iterations : int
        Maximum refinement iterations.
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).
    object_name : str
        Satellite name.
    object_id : str
        International designator (e.g., "1998-067A").
    norad_cat_id : int
        NORAD catalog number.
    classification : str
        Classification (U/C/S).
    ephemeris_type : int
        Ephemeris type (0-9).
    element_set_number : int
        Element set number (0-9999).
    revolution_number_at_epoch : int
        Revolution number at epoch.
    bstar : str
        BSTAR drag term (TLE format string).
    mean_motion_second_derivative : str
        Mean motion second derivative (TLE format string).

    Returns
    -------
    tuple[tle.Tle, fit_common.FitDiagnostics]
        Fitted TLE object and diagnostics.
    """
    # Create a minimal args-like namespace for compatibility with existing functions
    import argparse

    args = argparse.Namespace(
        name=object_name,
        norad_cat_id=norad_cat_id,
        object_name=object_name,
        classification=classification_type,
        int_designator_year=0,
        int_designator_launch_number=0,
        int_designator_piece="",
        ephemeris_type=ephemeris_type,
        element_set_number=element_set_number,
        revolution_number_at_epoch=revolution_number_at_epoch,
        bstar=bstar,
        mean_motion_second_derivative=mean_motion_second_derivative,
        max_iterations=max_iterations,
    )

    # Parse object_id if provided
    if object_id != "UNKNOWN":
        try:
            int_year, int_launch, int_piece = convert_tle._parse_object_id(object_id)
            args.int_designator_year = int_year
            args.int_designator_launch_number = int_launch
            args.int_designator_piece = int_piece
        except Exception:
            pass

    try:
        if refinement_method == "keplerian":
            estimated: models.Estimated = estimation.estimate_tle_fields(
                states, use_state_match=True
            )
            estimated = refinement.refine_estimated_fields_keplerian_match(
                args, estimated, states
            )
        elif refinement_method == "cartesian":
            estimated: models.Estimated = estimation.estimate_tle_fields(
                states, use_state_match=True
            )
            target_state_m_m_s: np.ndarray = states[0][1]  # (6,) target state
            estimated = refinement.refine_estimated_fields_to_match_epoch_state(
                args, estimated, target_state_m_m_s
            )
        else:
            # refinement_method == "none"
            estimated: models.Estimated = estimation.estimate_tle_fields(
                states, use_state_match=False
            )
        estimated = estimation.estimate_bstar_from_arc(args, estimated, states)
    except (ValueError, FileNotFoundError, OSError) as error:
        raise ValueError(f"TLE fitting failed: {error}")

    tle_obj: tle.Tle = tle_builder.build_tle_data(args, estimated)

    # Compute diagnostics
    reference_timestamp: float = states[0][0]
    span_s: float = states[-1][0] - reference_timestamp

    # Compute RMS position error by comparing TLE propagation with OEM states
    line1_str, line2_str = tle.format_tle_strings(tle_obj)
    tle_ephemeris = create_tle_ephemeris(line1_str, line2_str, object_name=object_name)

    position_errors: list[float] = []
    for timestamp, state_vector in states:
        dt_s: float = timestamp - reference_timestamp
        if dt_s > fit_span_s:
            break
        try:
            predicted_state: np.ndarray = tle_ephemeris.cartesian_state(
                tle_ephemeris.tle.reference_epoch + dt_s
            )
            pos_error: float = float(
                np.linalg.norm(state_vector[:3] - predicted_state[:3])
            )
            position_errors.append(pos_error)
        except Exception:
            continue

    rms_position_m: float = (
        float(np.sqrt(np.mean(np.array(position_errors) ** 2)))
        if position_errors
        else 0.0
    )

    # Compute velocity delta at epoch if state match was used
    epoch_vel_delta_m_s: float | None = None
    if estimated.state_match_velocity_error_m_s is not None:
        epoch_vel_delta_m_s = estimated.state_match_velocity_error_m_s

    diagnostics = fit_common.FitDiagnostics(
        rms_position_m=rms_position_m,
        iterations=(
            estimated.state_match_iterations
            if estimated.state_match_iterations is not None
            else 0
        ),
        n_records=len(
            [s for s in states if (s[0] - reference_timestamp) <= fit_span_s]
        ),
        span_s=span_s,
        epoch_pos_delta_m=estimated.state_match_position_error_m,
        epoch_vel_delta_m_s=epoch_vel_delta_m_s,
        fit_method=f"tle_{refinement_method}",
    )

    return tle_obj, diagnostics


def compute_tle_propagation_comparison(
    tle_obj: tle.Tle,
    states: list[tuple[float, np.ndarray]],
    mu_m3_s2: float,
    fit_span_s: float,
    interval_s: float = 600.0,
    R_e_m: float = consts.EARTH_EQUATORIAL_RADIUS_M,
    J2: float = consts.EARTH_J2,
) -> list[fit_common.PropagationComparison]:
    """Compare TLE-propagated states with OEM states at regular intervals.

    Uses J2 secular propagation (as an approximation to SGP4) to propagate
    the fitted TLE elements and compare with OEM states.

    Parameters
    ----------
    tle_obj : tle.Tle
        TLE dataclass instance from fit_tle().
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector) tuples from OEM.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    fit_span_s : float
        Maximum arc span (s).
    interval_s : float
        Comparison interval (s), default: 600 = 10 minutes.
    R_e_m : float
        Earth equatorial radius (m).
    J2 : float
        J2 zonal harmonic coefficient (dimensionless).

    Returns
    -------
    list[fit_common.PropagationComparison]
        List of comparison records with keys: 'elapsed_s', 'elapsed_min',
        'pos_err_km', 'vel_err_m_s', 'dx_km', 'dy_km', 'dz_km',
        'dvx_m_s', 'dvy_m_s', 'dvz_m_s'.
    """
    reference_timestamp: float = states[0][0]

    # Filter state records to fit span
    filtered_states: list[tuple[float, np.ndarray]] = [
        (ts, sv) for ts, sv in states if (ts - reference_timestamp) <= fit_span_s
    ]

    if not filtered_states:
        return []

    # Reconstruct semi-major axis from TLE mean motion using SGP4-compatible inverse
    # Invert n = ke / a^(3/2) to get a = (ke / n)^(2/3) in Earth radii, then convert to m
    n_rev_per_day: float = tle_obj.mean_motion_rev_per_day
    n_rad_per_min: float = n_rev_per_day * TWO_PI / MINUTES_PER_DAY
    a_er: float = (_SGP4_KE / n_rad_per_min) ** (2.0 / 3.0)
    a_m: float = a_er * _SGP4_R_E_KM * 1000.0  # Convert to meters

    e: float = tle_obj.eccentricity  # Eccentricity (dimensionless)
    i_rad: float = math.radians(tle_obj.inclination_deg)  # Inclination (rad)
    omega_rad: float = math.radians(
        tle_obj.arg_perigee_deg
    )  # Argument of periapsis (rad)
    raan_rad: float = math.radians(tle_obj.raan_deg)  # RAAN (rad)
    M_rad: float = math.radians(tle_obj.mean_anomaly_deg)  # Mean anomaly (rad)

    mean_elements: np.ndarray = np.array(
        [a_m, e, i_rad, omega_rad, raan_rad, M_rad], dtype=float
    )

    max_elapsed: float = filtered_states[-1][0] - reference_timestamp

    # Generate comparison time points at the specified interval
    comparison_times_s: list[float] = []
    current_time_s: float = 0.0
    while current_time_s <= max_elapsed:
        comparison_times_s.append(current_time_s)
        current_time_s += interval_s
    if comparison_times_s[-1] < max_elapsed:
        comparison_times_s.append(max_elapsed)

    results: list[fit_common.PropagationComparison] = []

    line1_str, line2_str = tle.format_tle_strings(tle_obj)
    # print("compute_tle_propagation_comparison()")
    # print(f"DEBUG TLE Line 1: {line1_str}")
    # print(f"DEBUG TLE Line 2: {line2_str}")

    tle_ephemeris = create_tle_ephemeris(line1_str, line2_str, object_name="OBJECT")

    for elapsed_s in comparison_times_s:
        # Find closest OEM state to comparison time
        target_timestamp: float = reference_timestamp + elapsed_s
        closest_state: tuple[float, np.ndarray] | None = None
        closest_diff: float = float("inf")

        for ts, sv in filtered_states:
            diff: float = abs(ts - target_timestamp)
            if diff < closest_diff:
                closest_diff = diff
                closest_state = (ts, sv)

        if closest_state is None or closest_diff > interval_s / 2.0:
            continue

        actual_elapsed_s: float = closest_state[0] - reference_timestamp
        oem_state: np.ndarray = closest_state[1]

        predicted_state: np.ndarray = tle_ephemeris.cartesian_state(
            tle_ephemeris.tle.reference_epoch + actual_elapsed_s
        )

        # Compute position and velocity differences
        pos_diff_m: np.ndarray = oem_state[:3] - predicted_state[:3]
        vel_diff_m_s: np.ndarray = oem_state[3:6] - predicted_state[3:6]

        pos_err_m: float = float(np.linalg.norm(pos_diff_m))
        vel_err_m_s: float = float(np.linalg.norm(vel_diff_m_s))

        results.append(
            fit_common.PropagationComparison(
                elapsed_s=actual_elapsed_s,
                elapsed_min=actual_elapsed_s / 60.0,
                pos_err_km=pos_err_m / 1000.0,
                vel_err_m_s=vel_err_m_s,
                dx_km=pos_diff_m[0] / 1000.0,
                dy_km=pos_diff_m[1] / 1000.0,
                dz_km=pos_diff_m[2] / 1000.0,
                dvx_m_s=vel_diff_m_s[0],
                dvy_m_s=vel_diff_m_s[1],
                dvz_m_s=vel_diff_m_s[2],
            )
        )

    return results


def format_tle_output(
    epoch: datetime,
    tle_obj: tle.Tle,
    diagnostics: fit_common.FitDiagnostics,
    comparison: list[fit_common.PropagationComparison] | None = None,
) -> str:
    """Format TLE elements and fit diagnostics as human-readable text.

    Parameters
    ----------
    epoch : datetime
        Reference epoch.
    tle_obj : tle.Tle
        TLE dataclass instance from fit_tle().
    diagnostics : FitDiagnostics
        Fit diagnostics from fit_tle().
    comparison : list[fit_common.PropagationComparison] | None
        Optional propagation comparison results from compute_tle_propagation_comparison().

    Returns
    -------
    str
        Multi-line formatted text output.
    """
    lines: list[str] = []
    epoch_str: str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)

    lines.append("TLE mean elements (SGP4-compatible):")
    lines.append(f"  epoch:              {epoch_str}")
    lines.append(f"  records used:       {diagnostics.n_records}")
    lines.append(f"  arc span:           {diagnostics.span_s:.1f} s")
    lines.append(f"  iterations:         {diagnostics.iterations}")
    lines.append(f"  fit method:         {diagnostics.fit_method}")
    lines.append(f"  RMS position error: {diagnostics.rms_position_m / 1000.0:.6f} km")
    if diagnostics.epoch_vel_delta_m_s is not None:
        lines.append(f"  epoch Δ|v0|:        {diagnostics.epoch_vel_delta_m_s:.6f} m/s")
    lines.append("")
    lines.append("  Mean Keplerian Elements:")
    lines.append(
        f"    mean motion:           {tle_obj.mean_motion_rev_per_day:.10f} rev/day"
    )
    lines.append(f"    eccentricity:          {tle_obj.eccentricity:.10f}")
    lines.append(f"    inclination:           {tle_obj.inclination_deg:.6f} deg")
    lines.append(f"    RAAN:                  {tle_obj.raan_deg:.6f} deg")
    lines.append(f"    arg of periapsis:      {tle_obj.arg_perigee_deg:.6f} deg")
    lines.append(f"    mean anomaly:          {tle_obj.mean_anomaly_deg:.6f} deg")
    lines.append("")
    lines.append("  TLE-specific Parameters:")
    lines.append(f"    BSTAR:                 {tle_obj.bstar}")
    lines.append(
        f"    mean motion dot:       {tle_obj.mean_motion_first_derivative:.12f} rev/day²"
    )
    lines.append(f"    mean motion ddot:      {tle_obj.mean_motion_second_derivative}")

    # Derived quantities using SGP4-compatible inverse (WGS-72 ke)
    # Invert n = ke / a^(3/2) to get a = (ke / n)^(2/3) in Earth radii,
    # then convert to km.
    n_rev_per_day: float = tle_obj.mean_motion_rev_per_day
    n_rad_per_min: float = n_rev_per_day * TWO_PI / MINUTES_PER_DAY
    a_er: float = (_SGP4_KE / n_rad_per_min) ** (2.0 / 3.0)
    a_km: float = a_er * _SGP4_R_E_KM
    mean_motion_rad_s: float = n_rev_per_day * TWO_PI / SECONDS_PER_DAY
    lines.append("")
    lines.append("  Derived quantities:")
    lines.append(f"    semi-major axis:       {a_km:.6f} km")
    lines.append(f"    orbital period:        {TWO_PI / mean_motion_rad_s:.3f} s")

    # Propagation comparison table
    if comparison:
        lines.append("")
        lines.append("  Propagation comparison (TLE/J2 vs OEM) at 10-minute intervals:")
        lines.append("")
        lines.append(f"    {'t (min)':>8}  {'|Δr| (km)':>10}  {'|Δv| (km/s)':>12}")
        lines.append(f"    {'─' * 8}  {'─' * 10}  {'─' * 12}")

        for rec in comparison:
            lines.append(
                f"    {rec.elapsed_min:8.1f}  "
                f"{rec.pos_err_km:10.6f}  "
                f"{rec.vel_err_m_s / 1000.0:12.9f}"
            )

        # Summary statistics
        pos_errors: list[float] = [r.pos_err_km for r in comparison]
        vel_errors_km_s: list[float] = [r.vel_err_m_s / 1000.0 for r in comparison]
        lines.append("")
        lines.append("  Summary:")
        lines.append(
            f"    Position |Δr|:  min = {min(pos_errors):.6f} km   "
            f"max = {max(pos_errors):.6f} km   "
            f"avg = {np.mean(pos_errors):.6f} km"
        )
        lines.append(
            f"    Velocity |Δv|:  min = {min(vel_errors_km_s):.9f} km/s   "
            f"max = {max(vel_errors_km_s):.9f} km/s   "
            f"avg = {np.mean(vel_errors_km_s):.9f} km/s"
        )

    return "\n".join(lines)


#

# ===================================================================
# Cartesian to TLE mean elements conversion (SGP4-compatible)
# ===================================================================


# ===================================================================
# Cartesian to TLE mean elements conversion (SGP4-compatible)
# ===================================================================


def _cartesian_to_osculating_keplerian(
    cartesian_state: np.ndarray,
    mu_m3_s2: float,
) -> np.ndarray:
    """Convert Cartesian state to osculating Keplerian elements.

    Parameters
    ----------
    cartesian_state : np.ndarray
        Cartesian state vector [x, y, z, vx, vy, vz] in meters and m/s.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    np.ndarray
        Osculating Keplerian elements [a, e, i, omega, RAAN, theta] in meters and radians.
    """
    r_vec: np.ndarray = cartesian_state[:3]
    v_vec: np.ndarray = cartesian_state[3:6]

    r: float = float(np.linalg.norm(r_vec))
    v: float = float(np.linalg.norm(v_vec))

    h_vec: np.ndarray = np.cross(r_vec, v_vec)
    h: float = float(np.linalg.norm(h_vec))

    k_hat: np.ndarray = np.array([0.0, 0.0, 1.0])
    n_vec: np.ndarray = np.cross(k_hat, h_vec)
    n: float = float(np.linalg.norm(n_vec))

    e_vec: np.ndarray = (
        (v * v - mu_m3_s2 / r) * r_vec - np.dot(r_vec, v_vec) * v_vec
    ) / mu_m3_s2
    e: float = float(np.linalg.norm(e_vec))

    energy: float = v * v / 2.0 - mu_m3_s2 / r

    if abs(e - 1.0) > 1e-10:
        a: float = -mu_m3_s2 / (2.0 * energy)
    else:
        a = float("inf")

    i: float = math.acos(np.clip(h_vec[2] / h, -1.0, 1.0))

    if n > 1e-10:
        raan: float = math.acos(np.clip(n_vec[0] / n, -1.0, 1.0))
        if n_vec[1] < 0.0:
            raan = TWO_PI - raan
    else:
        raan = 0.0

    if n > 1e-10 and e > 1e-10:
        omega: float = math.acos(np.clip(np.dot(n_vec, e_vec) / (n * e), -1.0, 1.0))
        if e_vec[2] < 0.0:
            omega = TWO_PI - omega
    elif e > 1e-10:
        omega = math.atan2(e_vec[1], e_vec[0])
        if omega < 0.0:
            omega += TWO_PI
    else:
        omega = 0.0

    if e > 1e-10:
        theta: float = math.acos(np.clip(np.dot(e_vec, r_vec) / (e * r), -1.0, 1.0))
        if np.dot(r_vec, v_vec) < 0.0:
            theta = TWO_PI - theta
    elif n > 1e-10:
        theta = math.acos(np.clip(np.dot(n_vec, r_vec) / (n * r), -1.0, 1.0))
        if r_vec[2] < 0.0:
            theta = TWO_PI - theta
    else:
        theta = math.atan2(r_vec[1], r_vec[0])
        if theta < 0.0:
            theta += TWO_PI

    return np.array([a, e, i, omega, raan, theta], dtype=float)


def _true_to_mean_anomaly(theta: float, e: float) -> float:
    """Convert true anomaly to mean anomaly."""
    E: float = 2.0 * math.atan2(
        math.sqrt(1.0 - e) * math.sin(theta / 2.0),
        math.sqrt(1.0 + e) * math.cos(theta / 2.0),
    )
    M: float = E - e * math.sin(E)
    M = M % TWO_PI
    if M < 0.0:
        M += TWO_PI
    return M


def _create_test_tle(
    a_m: float,
    e: float,
    i_rad: float,
    omega_rad: float,
    raan_rad: float,
    M_rad: float,
    epoch_year: int,
    epoch_day: float,
) -> tle.Tle:
    """Create a TLE object from mean elements for testing."""
    n_rev_day: float = _sgp4_mean_motion_rev_per_day(a_m)
    return tle.Tle(
        name="REFINE",
        norad_cat_id=0,
        classification="U",
        int_designator_year=0,
        int_designator_launch_number=0,
        int_designator_piece="",
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        mean_motion_first_derivative=0.0,
        mean_motion_second_derivative="00000+0",
        bstar="00000+0",
        ephemeris_type=2,
        element_set_number=999,
        inclination_deg=math.degrees(i_rad),
        raan_deg=math.degrees(raan_rad),
        eccentricity=e,
        eccentricity_raw=f"{int(round(e * 1e7)):07d}",
        arg_perigee_deg=math.degrees(omega_rad),
        mean_anomaly_deg=math.degrees(M_rad),
        mean_motion_rev_per_day=n_rev_day,
        revolution_number_at_epoch=0,
    )


def _sgp4_position(
    a_m: float,
    e: float,
    i_rad: float,
    omega_rad: float,
    raan_rad: float,
    M_rad: float,
    epoch_year: int,
    epoch_day: float,
) -> np.ndarray:
    """Get SGP4-propagated position at epoch from mean elements."""
    test_tle = _create_test_tle(
        a_m, e, i_rad, omega_rad, raan_rad, M_rad, epoch_year, epoch_day
    )
    line1_str, line2_str = tle.format_tle_strings(test_tle)
    tle_ephemeris = create_tle_ephemeris(line1_str, line2_str, object_name="REFINE")
    predicted_state: np.ndarray = tle_ephemeris.cartesian_state(
        tle_ephemeris.tle.reference_epoch
    )
    return predicted_state[:3]


def cartesian_to_tle_mean_elements(
    cartesian_state: np.ndarray,
    epoch_timestamp: float,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    position_tolerance_m: float = 15.0,
    max_iterations: int = 50,
) -> np.ndarray:
    """Convert Cartesian state to SGP4-compatible TLE mean elements.

    Uses Gauss-Newton iteration to find mean elements that reproduce the
    input position when propagated with SGP4.

    Parameters
    ----------
    cartesian_state : np.ndarray
        Cartesian state vector [x, y, z, vx, vy, vz] in meters and m/s.
    epoch_timestamp : float
        POSIX timestamp of the epoch.
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    position_tolerance_m : float
        Target position accuracy (m). Default 15 m.
    max_iterations : int
        Maximum refinement iterations.

    Returns
    -------
    np.ndarray
        Mean Keplerian elements [a, e, i, omega, RAAN, M] in meters and radians.
    """
    state: np.ndarray = np.asarray(cartesian_state, dtype=float)
    if state.shape != (6,):
        raise ValueError(f"Cartesian state must have shape (6,), got {state.shape}")

    input_position: np.ndarray = state[:3].copy()

    # Convert Cartesian to osculating Keplerian elements
    osc: np.ndarray = _cartesian_to_osculating_keplerian(state, mu_m3_s2)
    a_osc, e_osc, i_osc, omega_osc, raan_osc, theta_osc = [float(x) for x in osc]
    M_osc: float = _true_to_mean_anomaly(theta_osc, e_osc)

    # Get epoch for TLE creation
    epoch_dt: datetime = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    epoch_year, epoch_day = tle.datetime_to_tle_epoch(epoch_dt)

    # Initialize mean elements from osculating elements
    x: np.ndarray = np.array(
        [a_osc, e_osc, i_osc, omega_osc, raan_osc, M_osc], dtype=float
    )

    # Finite difference step sizes
    h: np.ndarray = np.array([100.0, 1e-7, 1e-6, 1e-6, 1e-6, 1e-6])

    best_x: np.ndarray = x.copy()
    best_error: float = float("inf")

    for iteration in range(max_iterations):
        try:
            current_pos: np.ndarray = _sgp4_position(
                x[0], x[1], x[2], x[3], x[4], x[5], epoch_year, epoch_day
            )
        except Exception:
            break

        residual: np.ndarray = input_position - current_pos
        pos_error: float = float(np.linalg.norm(residual))

        if pos_error < best_error:
            best_error = pos_error
            best_x = x.copy()

        if pos_error < position_tolerance_m:
            break

        # Build Jacobian via central finite differences
        jacobian: np.ndarray = np.zeros((3, 6))
        for j in range(6):
            x_plus, x_minus = x.copy(), x.copy()
            x_plus[j] += h[j]
            x_minus[j] -= h[j]
            if j == 1:  # eccentricity bounds
                x_plus[j] = min(0.9, max(1e-7, x_plus[j]))
                x_minus[j] = min(0.9, max(1e-7, x_minus[j]))
            try:
                pos_plus = _sgp4_position(
                    x_plus[0],
                    x_plus[1],
                    x_plus[2],
                    x_plus[3],
                    x_plus[4],
                    x_plus[5],
                    epoch_year,
                    epoch_day,
                )
                pos_minus = _sgp4_position(
                    x_minus[0],
                    x_minus[1],
                    x_minus[2],
                    x_minus[3],
                    x_minus[4],
                    x_minus[5],
                    epoch_year,
                    epoch_day,
                )
                jacobian[:, j] = (pos_plus - pos_minus) / (2.0 * h[j])
            except Exception:
                jacobian[:, j] = 0.0

        # Solve least-squares with regularization
        try:
            jt_j: np.ndarray = jacobian.T @ jacobian + 1e-6 * np.eye(6)
            jt_r: np.ndarray = jacobian.T @ residual
            dx: np.ndarray = np.linalg.solve(jt_j, jt_r)
        except np.linalg.LinAlgError:
            break

        # Limit step size
        max_step = np.array([5000.0, 0.01, 0.01, 0.1, 0.1, 0.5])
        dx = np.clip(dx, -max_step, max_step)

        # Line search
        alpha: float = 1.0
        improved: bool = False
        for _ in range(10):
            x_new: np.ndarray = x + alpha * dx
            x_new[0] = max(6.4e6, x_new[0])
            x_new[1] = max(1e-7, min(0.9, x_new[1]))
            x_new[2] = max(0.0, min(math.pi, x_new[2]))
            for k in [3, 4, 5]:
                x_new[k] = x_new[k] % TWO_PI
                if x_new[k] < 0:
                    x_new[k] += TWO_PI
            try:
                new_pos = _sgp4_position(
                    x_new[0],
                    x_new[1],
                    x_new[2],
                    x_new[3],
                    x_new[4],
                    x_new[5],
                    epoch_year,
                    epoch_day,
                )
                new_error = float(np.linalg.norm(input_position - new_pos))
                if new_error < pos_error:
                    x = x_new
                    improved = True
                    break
            except Exception:
                pass
            alpha *= 0.5

        if not improved and iteration > 5:
            break

    return best_x


def cartesian_to_tle(
    cartesian_state: np.ndarray,
    epoch_timestamp: float,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    object_name: str = "OBJECT",
    object_id: str = "UNKNOWN",
    position_tolerance_m: float = 15.0,
    max_iterations: int = 50,
) -> tle.Tle:
    """Convert Cartesian state to a TLE at the specified epoch."""
    mean_elements: np.ndarray = cartesian_to_tle_mean_elements(
        cartesian_state,
        epoch_timestamp,
        mu_m3_s2=mu_m3_s2,
        position_tolerance_m=position_tolerance_m,
        max_iterations=max_iterations,
    )

    a_m, e, i_rad, omega_rad, raan_rad, M_rad = [float(x) for x in mean_elements]
    mean_motion_rev_day: float = _sgp4_mean_motion_rev_per_day(a_m)

    int_year, int_launch, int_piece = convert_tle._parse_object_id(object_id)
    epoch_dt: datetime = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    epoch_year, epoch_day = tle.datetime_to_tle_epoch(epoch_dt)

    bstar_tle: str = convert_tle._float_to_tle_exponential(0.0)
    mean_motion_ddot_tle: str = convert_tle._float_to_tle_exponential(0.0)

    return tle.Tle(
        name=object_name,
        norad_cat_id=0,
        classification="U",
        int_designator_year=int_year,
        int_designator_launch_number=int_launch,
        int_designator_piece=int_piece,
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        mean_motion_first_derivative=0.0,
        mean_motion_second_derivative=mean_motion_ddot_tle,
        bstar=bstar_tle,
        ephemeris_type=2,
        element_set_number=999,
        inclination_deg=math.degrees(i_rad),
        raan_deg=math.degrees(raan_rad),
        eccentricity=e,
        eccentricity_raw=f"{int(round(e * 1e7)):07d}",
        arg_perigee_deg=math.degrees(omega_rad),
        mean_anomaly_deg=math.degrees(M_rad),
        mean_motion_rev_per_day=mean_motion_rev_day,
        revolution_number_at_epoch=0,
    )


def verify_tle_epoch_position(
    tle_obj: tle.Tle,
    expected_position_m: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Verify TLE epoch position against expected position."""
    expected_pos: np.ndarray = np.asarray(expected_position_m, dtype=float)
    if expected_pos.shape != (3,):
        raise ValueError(
            f"Expected position must have shape (3,), got {expected_pos.shape}"
        )

    line1_str, line2_str = tle.format_tle_strings(tle_obj)
    tle_ephemeris = create_tle_ephemeris(line1_str, line2_str, object_name="VERIFY")
    predicted_state: np.ndarray = tle_ephemeris.cartesian_state(
        tle_ephemeris.tle.reference_epoch
    )

    pos_diff: np.ndarray = expected_pos - predicted_state[:3]
    pos_error: float = float(np.linalg.norm(pos_diff))

    return pos_error, pos_diff
