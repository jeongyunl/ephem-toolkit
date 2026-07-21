"""Orbital mechanics calculations for TLE estimation."""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.common as common
import common.consts as consts

from . import constants
from .models import OrbitalElements, OrbitalRecord, PhaseMatchResult


def state_to_orbital_elements(state_vector_m: np.ndarray) -> OrbitalElements:
    """Compute osculating Keplerian elements from one Cartesian state.

    Units: m, m/s in; angular outputs in degrees; mean motion in rev/day.

    Parameters
    ----------
    state_vector_m : np.ndarray
        State vector (6,) in m and m/s: [x, y, z, vx, vy, vz].

    Returns
    -------
    OrbitalElements
        Osculating Keplerian orbital elements.

    Raises
    ------
    ValueError
        If state is invalid (zero position/momentum, parabolic, hyperbolic, or e>=1).
    """
    mu: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    state: np.ndarray = np.asarray(state_vector_m, dtype=float)  # (6,) state vector
    r: np.ndarray = state[:3]  # (3,) position
    v: np.ndarray = state[3:6]  # (3,) velocity

    r_norm: float = float(np.linalg.norm(r))
    v_norm: float = float(np.linalg.norm(v))
    if r_norm <= 0.0:
        raise ValueError("Invalid state: position norm is zero")

    h_vec: np.ndarray = np.cross(r, v)  # (3,) angular momentum vector
    h_norm: float = float(np.linalg.norm(h_vec))
    if h_norm <= 0.0:
        raise ValueError("Invalid state: angular momentum norm is zero")

    k_hat: np.ndarray = np.array([0.0, 0.0, 1.0])  # (3,) unit z-vector
    n_vec: np.ndarray = np.cross(k_hat, h_vec)  # (3,) node vector
    n_norm: float = float(np.linalg.norm(n_vec))

    vxh: np.ndarray = np.cross(v, h_vec)  # (3,) cross product
    e_vec: np.ndarray = vxh / mu - r / r_norm  # (3,) eccentricity vector
    eccentricity: float = float(np.linalg.norm(e_vec))

    specific_energy: float = 0.5 * v_norm**2 - mu / r_norm
    if abs(specific_energy) < 1e-15:
        raise ValueError("Parabolic trajectory not supported for TLE estimation")

    semi_major_axis_m: float = -mu / (2.0 * specific_energy)
    if semi_major_axis_m <= 0.0:
        raise ValueError("Hyperbolic trajectory not supported for TLE estimation")

    inclination_rad: float = math.acos(
        float(np.clip(float(h_vec[2]) / h_norm, -1.0, 1.0))
    )

    raan_rad: float
    if n_norm > 0.0:
        raan_rad = math.atan2(float(n_vec[1]), float(n_vec[0]))
    else:
        raan_rad = 0.0

    arg_perigee_rad: float
    if n_norm > 0.0 and eccentricity > 1e-12:
        arg_perigee_rad = math.atan2(
            float(np.dot(np.cross(n_vec, e_vec), h_vec)) / (n_norm * h_norm),
            float(np.dot(n_vec, e_vec)) / n_norm,
        )
    else:
        arg_perigee_rad = 0.0

    true_anomaly_rad: float
    if eccentricity > 1e-12:
        true_anomaly_rad = math.atan2(
            float(np.dot(np.cross(e_vec, r), h_vec)) / (eccentricity * h_norm * r_norm),
            float(np.dot(e_vec, r)) / (eccentricity * r_norm),
        )
    else:
        if n_norm > 0.0:
            true_anomaly_rad = math.atan2(
                float(np.dot(np.cross(n_vec, r), h_vec)) / (n_norm * h_norm * r_norm),
                float(np.dot(n_vec, r)) / (n_norm * r_norm),
            )
        else:
            true_anomaly_rad = math.atan2(float(r[1]), float(r[0]))

    true_anomaly_rad = common.wrap_angle_rad(true_anomaly_rad)

    mean_anomaly_rad: float
    if eccentricity < 1.0:
        eccentric_anomaly_rad: float = 2.0 * math.atan2(
            math.sqrt(max(0.0, 1.0 - eccentricity)) * math.sin(true_anomaly_rad / 2.0),
            math.sqrt(1.0 + eccentricity) * math.cos(true_anomaly_rad / 2.0),
        )
        mean_anomaly_rad = eccentric_anomaly_rad - eccentricity * math.sin(
            eccentric_anomaly_rad
        )
    else:
        raise ValueError("Eccentricity >= 1 is not supported for TLE estimation")

    mean_anomaly_rad = common.wrap_angle_rad(mean_anomaly_rad)

    mean_motion_rad_s: float = math.sqrt(mu / (semi_major_axis_m**3))
    mean_motion_rev_per_day: float = (
        mean_motion_rad_s * constants.SECONDS_PER_DAY_S / (2.0 * math.pi)
    )

    return OrbitalElements(
        semi_major_axis_m=semi_major_axis_m,
        eccentricity=eccentricity,
        inclination_deg=math.degrees(inclination_rad),
        raan_deg=math.degrees(common.wrap_angle_rad(raan_rad)),
        arg_perigee_deg=math.degrees(common.wrap_angle_rad(arg_perigee_rad)),
        mean_anomaly_deg=math.degrees(mean_anomaly_rad),
        mean_motion_rev_per_day=mean_motion_rev_per_day,
    )


def linear_regression_slope(xs: list[float], ys: list[float]) -> float:
    """Return OLS slope b from y = a + b*x.

    Parameters
    ----------
    xs : list[float]
        Independent variable values.
    ys : list[float]
        Dependent variable values.

    Returns
    -------
    float
        OLS slope coefficient.
    """
    if len(xs) < 2:
        return 0.0

    mean_x: float = sum(xs) / len(xs)
    mean_y: float = sum(ys) / len(ys)

    numerator: float = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator: float = sum((x - mean_x) ** 2 for x in xs)

    if denominator <= 0.0:
        return 0.0

    return numerator / denominator


def linear_regression_intercept(xs: list[float], ys: list[float]) -> float:
    """Return OLS intercept a from y = a + b*x.

    Parameters
    ----------
    xs : list[float]
        Independent variable values.
    ys : list[float]
        Dependent variable values.

    Returns
    -------
    float
        OLS intercept coefficient.
    """
    if len(xs) < 1:
        return 0.0
    if len(xs) == 1:
        return ys[0]

    slope: float = linear_regression_slope(xs, ys)
    mean_x: float = sum(xs) / len(xs)
    mean_y: float = sum(ys) / len(ys)
    return mean_y - slope * mean_x


def phase_match_epoch_angles(
    records: list[OrbitalRecord],
    first_u_rad: float,
    orbit_period_day: float,
    tolerance_deg: float = 0.5,
) -> PhaseMatchResult | None:
    """Average osculating angles at repeated epoch-like orbital phases.

    This provides a local short-period correction around the chosen epoch phase.

    Parameters
    ----------
    records : list[OrbitalRecord]
        List of records with orbital element data.
    first_u_rad : float
        First mean argument of latitude in radians.
    orbit_period_day : float
        Orbital period in days.
    tolerance_deg : float
        Tolerance in degrees for phase matching (default: 0.5).

    Returns
    -------
    PhaseMatchResult | None
        Phase match result with matched angle statistics, or None if insufficient matches.
    """
    if orbit_period_day <= 0.0:
        return None

    tolerance_rad: float = math.radians(tolerance_deg)
    max_revolution: int = int(records[-1].t_day / orbit_period_day) + 1
    matched_records: list[OrbitalRecord] = []

    for revolution in range(max_revolution + 1):
        target_time_day: float = revolution * orbit_period_day
        best_record: OrbitalRecord | None = None
        best_score: float | None = None

        for record in records:
            if abs(record.t_day - target_time_day) > 0.15 * orbit_period_day:
                continue

            score: float = abs(
                common.angle_difference_rad(
                    record.mean_argument_latitude_rad, first_u_rad
                )
            )
            if score > tolerance_rad:
                continue

            if best_score is None or score < best_score:
                best_record = record
                best_score = score

        if best_record is not None:
            matched_records.append(best_record)

    if len(matched_records) < 2:
        return None

    return PhaseMatchResult(
        count=len(matched_records),
        raan_rad=common.circular_mean_angle_rad(
            [record.raan_rad for record in matched_records]
        ),
        arg_perigee_rad=common.circular_mean_angle_rad(
            [record.arg_perigee_rad for record in matched_records]
        ),
        mean_anomaly_rad=common.circular_mean_angle_rad(
            [record.mean_anomaly_rad for record in matched_records]
        ),
    )


def estimate_inclination_from_nodal_drift(
    times_s: list[float],
    raan_series_rad: list[float],
    mean_motion_rad_s_series: list[float],
    p_m_series: list[float],
    fallback_inclination_deg: float,
) -> float:
    """Estimate mean inclination from J2 nodal precession rate.

    Uses:
      dOmega/dt = -1.5 * J2 * n * (Re/p)^2 * cos(i)

    For near-equatorial orbits (inclination < 1 degree), the nodal drift
    signal is too weak relative to short-period noise, so the osculating
    inclination is used directly as a more reliable estimate.

    Parameters
    ----------
    times_s : list[float]
        Time series in seconds.
    raan_series_rad : list[float]
        RAAN series in radians.
    mean_motion_rad_s_series : list[float]
        Mean motion series in radians per second.
    p_m_series : list[float]
        Semi-latus rectum series in m.
    fallback_inclination_deg : float
        Fallback inclination value in degrees.

    Returns
    -------
    float
        Estimated inclination in degrees.
    """
    # For near-equatorial orbits, nodal precession is dominated by noise.
    # Use the osculating inclination directly.
    if fallback_inclination_deg < 1.0 or fallback_inclination_deg > 179.0:
        return fallback_inclination_deg

    if len(times_s) < 2:
        return fallback_inclination_deg

    raan_unwrapped: list[float] = common.unwrap_angles_rad(raan_series_rad)
    domega_dt: float = linear_regression_slope(times_s, raan_unwrapped)

    mean_n: float = sum(mean_motion_rad_s_series) / len(mean_motion_rad_s_series)
    mean_p: float = sum(p_m_series) / len(p_m_series)

    if mean_n <= 0.0 or mean_p <= 0.0:
        return fallback_inclination_deg

    coefficient: float = (
        1.5
        * consts.EARTH_J2
        * mean_n
        * (consts.EARTH_EQUATORIAL_RADIUS_M / mean_p) ** 2
    )
    if coefficient <= 0.0:
        return fallback_inclination_deg

    cos_inclination: float = -domega_dt / coefficient
    if cos_inclination < -1.0 or cos_inclination > 1.0:
        return fallback_inclination_deg

    estimated_deg: float = math.degrees(math.acos(cos_inclination))

    # Sanity check: if the nodal-drift estimate deviates too far from the
    # osculating value, it is likely corrupted by noise or insufficient arc.
    # In that case, fall back to the osculating inclination.
    if abs(estimated_deg - fallback_inclination_deg) > 5.0:
        return fallback_inclination_deg

    return estimated_deg
