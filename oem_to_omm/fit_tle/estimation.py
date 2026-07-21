"""TLE field estimation from orbital records.

This module provides functions to estimate TLE orbital elements from sequences
of Cartesian state vectors, including B* drag term fitting and accuracy verification.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.common as common
import common.convert_tle as convert_tle
import common.kepler as kepler
import common.consts as consts
import common.tle as tle
from . import constants
from . import models
from . import orbital_mechanics
from . import tle_builder


def select_bstar_fit_samples(
    states: list[tuple[float, np.ndarray]],
) -> list[tuple[float, np.ndarray]]:
    """Select evenly spaced post-epoch records used for B* fitting.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector_m (6,)) tuples.

    Returns
    -------
    list[tuple[float, np.ndarray]]
        Selected subset of records (POSIX timestamp, state_vector_m (6,)) for B* fitting.
    """
    if len(states) <= 1:
        return []

    selected_states: list[tuple[float, np.ndarray]]
    if len(states) <= constants.BSTAR_SAMPLE_COUNT:
        selected_states = states[1:]
    else:
        selected_states = []
        last_index: int = len(states) - 1
        for sample_index in range(1, constants.BSTAR_SAMPLE_COUNT + 1):
            index: int = round(sample_index * last_index / constants.BSTAR_SAMPLE_COUNT)
            index = min(max(index, 1), last_index)
            selected_states.append(states[index])
        # Preserve order while removing duplicates.
        seen: set[tuple] = set()
        selected_states = [
            record
            for record in selected_states
            if not (
                (record[0], tuple(record[1].tolist())) in seen
                or seen.add((record[0], tuple(record[1].tolist())))
            )
        ]

    return selected_states


def estimate_bstar_from_arc(
    args: argparse.Namespace,
    estimated: models.Estimated,
    states: list[tuple[float, np.ndarray]],
) -> models.Estimated:
    """Estimate B* by minimizing propagated state mismatch over the OEM arc.

    If --bstar is explicitly provided (not the default placeholder), that value
    is preserved and no estimation is performed.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    estimated : Estimated
        Estimated TLE elements dataclass.
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector_m (6,)) tuples.

    Returns
    -------
    Estimated
        Updated estimated dataclass with B* value and metadata.
    """
    from .refinement import (
        compute_state_match_score,
        evaluate_tle_states_for_offsets_m,
    )
    from .tle_builder import build_tle_lines
    from dataclasses import replace

    if args.bstar != "00000+0":
        estimated.bstar = args.bstar
        estimated.bstar_source = "input"
        return estimated

    sampled_states: list[tuple[float, np.ndarray]] = select_bstar_fit_samples(states)
    if not sampled_states:
        estimated.bstar = args.bstar
        estimated.bstar_source = "default"
        return estimated

    epoch_timestamp: float = states[0][0]
    time_offsets_s: list[float] = [
        (timestamp - epoch_timestamp) for timestamp, _ in sampled_states
    ]
    target_states: list[np.ndarray] = [  # List of (6,)
        state_vector_m for _, state_vector_m in sampled_states  # Already (6,)
    ]

    def evaluate_bstar_cost(bstar_value: float) -> float | None:
        trial_estimated: models.Estimated = replace(
            estimated, bstar=tle_builder.format_tle_exponential_from_float(bstar_value)
        )
        line1: str
        line2: str
        line1, line2 = build_tle_lines(args, trial_estimated)
        states: list[np.ndarray] | None = evaluate_tle_states_for_offsets_m(
            line1, line2, time_offsets_s
        )
        if states is None:
            return None

        total_score: float = 0.0
        for state, target_state in zip(states, target_states):
            residual: np.ndarray = target_state - state  # (6,) - (6,) = (6,)
            score: float
            score, _, _ = compute_state_match_score(residual)
            total_score += score
        return total_score

    bstar_value: float = 0.0
    step: float = constants.BSTAR_FIT_INITIAL_STEP_1_ER
    best_score: float | None = evaluate_bstar_cost(bstar_value)
    if best_score is None:
        estimated.bstar = args.bstar
        estimated.bstar_source = "default"
        return estimated

    for _ in range(constants.BSTAR_FIT_MAX_ITERATIONS):
        improved: bool = False
        for direction in (1.0, -1.0):
            trial_value: float = float(
                np.clip(
                    bstar_value + direction * step,
                    -constants.BSTAR_FIT_MAX_ABS,
                    constants.BSTAR_FIT_MAX_ABS,
                )
            )
            trial_score: float | None = evaluate_bstar_cost(trial_value)
            if trial_score is None:
                continue
            if trial_score < best_score:
                bstar_value = trial_value
                best_score = trial_score
                improved = True
                break
        if not improved:
            step *= 0.5
            if step < 1.0e-8:
                break

    estimated.bstar = tle_builder.format_tle_exponential_from_float(bstar_value)
    estimated.bstar_float = bstar_value
    estimated.bstar_fit_score = best_score
    estimated.bstar_source = "estimated"
    return estimated


def estimate_tle_fields(
    states: list[tuple[float, np.ndarray]],
    use_state_match: bool = True,
) -> models.Estimated:
    """Estimate TLE orbital elements from a sequence of Cartesian state records.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector_m (6,)) tuples.
    use_state_match : bool
        If True, use osculating values as initial guess for state-match refinement.

    Returns
    -------
    Estimated
        Estimated TLE elements and diagnostic quantities.
    """
    # Use the first epoch/state as the epoch of the estimated TLE.
    epoch_timestamp: float = states[0][0]  # POSIX timestamp of epoch
    epoch_dt: datetime = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    first_state_vector_m: np.ndarray = states[0][1]  # (6,) state vector in SI units

    elements_first: models.OrbitalElements = (
        orbital_mechanics.state_to_orbital_elements(first_state_vector_m)
    )

    times_day: list[float] = []
    times_s: list[float] = []
    mean_motion_series: list[float] = []
    eccentricity_series: list[float] = []
    raan_series_rad: list[float] = []
    arg_perigee_series_rad: list[float] = []
    mean_anomaly_series_rad: list[float] = []
    mean_argument_latitude_series_rad: list[float] = []
    mean_motion_rad_s_series: list[float] = []
    p_m_series: list[float] = []
    records_with_elements: list[models.OrbitalRecord] = []
    for timestamp, state_vector_m in states:
        time_offset_s: float = timestamp - epoch_timestamp
        time_offset_day: float = time_offset_s / constants.SECONDS_PER_DAY_S
        elements: models.OrbitalElements = orbital_mechanics.state_to_orbital_elements(
            state_vector_m
        )
        times_s.append(time_offset_s)
        times_day.append(time_offset_day)
        mean_motion_series.append(elements.mean_motion_rev_per_day)
        eccentricity_series.append(elements.eccentricity)
        raan_rad: float = math.radians(elements.raan_deg)
        arg_perigee_rad: float = math.radians(elements.arg_perigee_deg)
        mean_anomaly_rad: float = math.radians(elements.mean_anomaly_deg)

        raan_series_rad.append(raan_rad)
        arg_perigee_series_rad.append(arg_perigee_rad)
        mean_anomaly_series_rad.append(mean_anomaly_rad)
        mean_argument_latitude_series_rad.append(
            common.wrap_angle_rad(arg_perigee_rad + mean_anomaly_rad)
        )
        mean_motion_rad_s_series.append(
            elements.mean_motion_rev_per_day
            * 2.0
            * math.pi
            / constants.SECONDS_PER_DAY_S
        )
        p_m_series.append(elements.semi_major_axis_m * (1.0 - elements.eccentricity**2))
        records_with_elements.append(
            models.OrbitalRecord(
                t_day=time_offset_day,
                raan_rad=raan_rad,
                arg_perigee_rad=arg_perigee_rad,
                mean_anomaly_rad=mean_anomaly_rad,
                mean_argument_latitude_rad=common.wrap_angle_rad(
                    arg_perigee_rad + mean_anomaly_rad
                ),
            )
        )

    raan_unwrapped = common.unwrap_angles_rad(raan_series_rad)
    raan_mean_at_epoch_deg = math.degrees(
        common.wrap_angle_rad(
            orbital_mechanics.linear_regression_intercept(times_s, raan_unwrapped)
        )
    )

    mean_argument_latitude_unwrapped = common.unwrap_angles_rad(
        mean_argument_latitude_series_rad
    )
    mean_argument_latitude_rate_rad_s = orbital_mechanics.linear_regression_slope(
        times_s, mean_argument_latitude_unwrapped
    )
    mean_argument_latitude_rate_rev_per_day = (
        mean_argument_latitude_rate_rad_s
        * constants.SECONDS_PER_DAY_S
        / (2.0 * math.pi)
    )

    # Remove fitted short-period phase progression and circular-average the
    # residuals to obtain a more stable epoch phase estimate.
    mean_argument_latitude_phase_residuals = [
        common.wrap_angle_rad(u - mean_argument_latitude_rate_rad_s * time_offset_s)
        for u, time_offset_s in zip(mean_argument_latitude_series_rad, times_s)
    ]
    mean_argument_latitude_at_epoch_rad = common.circular_mean_angle_rad(
        mean_argument_latitude_phase_residuals
    )

    # Mean anomaly can be highly sensitive to unwrap branch in near-circular
    # orbits. Anchor its phase detrending with epoch osculating mean motion.
    mean_motion_phase_rate_rev_per_day = elements_first.mean_motion_rev_per_day
    mean_motion_phase_rate_rad_s = (
        mean_motion_phase_rate_rev_per_day * 2.0 * math.pi / constants.SECONDS_PER_DAY_S
    )
    mean_anomaly_phase_residuals = [
        common.wrap_angle_rad(m - mean_motion_phase_rate_rad_s * time_offset_s)
        for m, time_offset_s in zip(mean_anomaly_series_rad, times_s)
    ]
    mean_anomaly_phase_at_epoch_rad = common.circular_mean_angle_rad(
        mean_anomaly_phase_residuals
    )
    mean_anomaly_osculating_at_epoch_rad = math.radians(elements_first.mean_anomaly_deg)
    mean_anomaly_at_epoch_rad = common.circular_mean_angle_rad(
        [
            mean_anomaly_phase_at_epoch_rad,
            mean_anomaly_osculating_at_epoch_rad,
        ]
    )
    mean_anomaly_at_epoch_deg = math.degrees(mean_anomaly_at_epoch_rad)

    arg_perigee_at_epoch_deg = math.degrees(
        common.wrap_angle_rad(
            mean_argument_latitude_at_epoch_rad - mean_anomaly_at_epoch_rad
        )
    )

    orbit_period_day = 1.0 / max(elements_first.mean_motion_rev_per_day, 1e-12)
    phase_matched_angles = orbital_mechanics.phase_match_epoch_angles(
        records_with_elements,
        first_u_rad=records_with_elements[0].mean_argument_latitude_rad,
        orbit_period_day=orbit_period_day,
    )
    phase_match_weight = 0.0
    if phase_matched_angles is not None:
        phase_match_weight = phase_matched_angles.count / (
            phase_matched_angles.count + constants.PHASE_MATCH_BLEND_SOFTENING
        )
        raan_mean_at_epoch_deg = math.degrees(
            common.circular_blend_angle_rad(
                math.radians(raan_mean_at_epoch_deg),
                phase_matched_angles.raan_rad,
                phase_match_weight,
            )
        )
        arg_perigee_at_epoch_deg = math.degrees(
            common.circular_blend_angle_rad(
                math.radians(arg_perigee_at_epoch_deg),
                phase_matched_angles.arg_perigee_rad,
                phase_match_weight,
            )
        )
        mean_anomaly_at_epoch_deg = math.degrees(
            common.circular_blend_angle_rad(
                math.radians(mean_anomaly_at_epoch_deg),
                phase_matched_angles.mean_anomaly_rad,
                phase_match_weight,
            )
        )

    mean_motion_regression_at_epoch_rev_per_day = (
        orbital_mechanics.linear_regression_intercept(times_day, mean_motion_series)
    )

    # Blend two complementary estimates to reduce osculating short-period bias:
    # - regression of energy-derived mean motion,
    # - rate of argument of latitude from angle-fit.
    mean_motion_at_epoch_rev_per_day = 0.5 * (
        mean_motion_regression_at_epoch_rev_per_day
        + mean_argument_latitude_rate_rev_per_day
    )

    inclination_deg_estimated = orbital_mechanics.estimate_inclination_from_nodal_drift(
        times_s=times_s,
        raan_series_rad=raan_series_rad,
        mean_motion_rad_s_series=mean_motion_rad_s_series,
        p_m_series=p_m_series,
        fallback_inclination_deg=elements_first.inclination_deg,
    )

    slope_rev_per_day2 = orbital_mechanics.linear_regression_slope(
        times_day, mean_motion_series
    )

    # TLE line 1 stores (1/2) * d(mean_motion)/dt.
    mean_motion_first_derivative_raw = 0.5 * slope_rev_per_day2
    mean_motion_first_derivative = float(
        np.clip(
            mean_motion_first_derivative_raw,
            -constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE,
            constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE,
        )
    )

    epoch_year, epoch_day = tle.datetime_to_tle_epoch(epoch_dt)

    # Compute mean eccentricity from regression intercept for no-state-match mode.
    eccentricity_mean_at_epoch = orbital_mechanics.linear_regression_intercept(
        times_day, eccentricity_series
    )
    eccentricity_mean_at_epoch = max(0.0, min(eccentricity_mean_at_epoch, 0.9999999))

    if use_state_match:
        # Use osculating values as the initial guess for the state-match
        # refinement.  The osculating elements at epoch are the closest to the
        # target Cartesian state and provide a much better starting point for
        # the Gauss-Newton optimizer than the averaged/blended values, which
        # can be biased by short-period perturbations (especially for ω and M
        # in near-circular orbits).
        chosen_raan_deg = elements_first.raan_deg
        chosen_arg_perigee_deg = elements_first.arg_perigee_deg
        chosen_mean_anomaly_deg = elements_first.mean_anomaly_deg
        chosen_eccentricity = max(0.0, min(elements_first.eccentricity, 0.9999999))
    else:
        # Without state-match refinement, use the averaged/blended values that
        # better approximate SGP4 "mean" elements.  Osculating values contain
        # short-period J2 perturbations that bias the TLE when no optimizer
        # corrects them.
        chosen_raan_deg = raan_mean_at_epoch_deg
        chosen_arg_perigee_deg = arg_perigee_at_epoch_deg
        chosen_mean_anomaly_deg = mean_anomaly_at_epoch_deg
        chosen_eccentricity = eccentricity_mean_at_epoch

    return models.Estimated(
        epoch_datetime=epoch_dt,
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        inclination_deg=inclination_deg_estimated,
        inclination_deg_osculating_at_epoch=elements_first.inclination_deg,
        raan_deg=chosen_raan_deg,
        raan_deg_osculating_at_epoch=elements_first.raan_deg,
        eccentricity=chosen_eccentricity,
        arg_perigee_deg=chosen_arg_perigee_deg,
        arg_perigee_deg_osculating_at_epoch=elements_first.arg_perigee_deg,
        mean_anomaly_deg=chosen_mean_anomaly_deg,
        mean_anomaly_deg_osculating_at_epoch=elements_first.mean_anomaly_deg,
        mean_motion_rev_per_day=mean_motion_at_epoch_rev_per_day,
        mean_motion_rev_per_day_regression_at_epoch=mean_motion_regression_at_epoch_rev_per_day,
        mean_argument_latitude_rate_rev_per_day=mean_argument_latitude_rate_rev_per_day,
        mean_motion_rev_per_day_osculating_at_epoch=elements_first.mean_motion_rev_per_day,
        phase_match_count=(
            0 if phase_matched_angles is None else phase_matched_angles.count
        ),
        phase_match_weight=phase_match_weight,
        mean_motion_first_derivative=mean_motion_first_derivative,
        mean_motion_first_derivative_raw=mean_motion_first_derivative_raw,
        semi_major_axis_m=elements_first.semi_major_axis_m,
        dataset_slope_rev_per_day2=slope_rev_per_day2,
    )


def verify_accuracy_keplerian(
    args: argparse.Namespace,
    estimated: models.Estimated,
    states: list[tuple[float, np.ndarray]],
) -> models.KeplerianAccuracy | None:
    """Verify TLE accuracy using osculating Keplerian elements from common.kepler.

    Uses common.convert_tle.tle_to_osculating_keplerian to convert the TLE directly
    to osculating elements (two-body), and compares against the reference
    osculating elements derived from the input Cartesian state at epoch via
    common.kepler.cartesian_to_keplerian.

    This does NOT require SGP4/tudatpy — it uses pure two-body Keplerian
    mechanics via common.kepler.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    estimated : Estimated
        Estimated TLE elements dataclass.
    states : list[tuple[float, np.ndarray]]
        List of (POSIX timestamp, state_vector_m (6,)) tuples.

    Returns
    -------
    KeplerianAccuracy | None
        Keplerian accuracy dataclass with element-wise residuals, or None on failure.
    """
    mu: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2

    # Reference state at epoch (already in m, m/s)
    ref_state_m: np.ndarray = states[0][1]  # (6,) state vector

    # Compute reference osculating Keplerian elements
    try:
        ref_kep = kepler.cartesian_to_keplerian(
            ref_state_m, mu
        )  # (6,) Keplerian elements
    except ValueError:
        return None

    # Convert TLE to osculating Keplerian elements via common.kepler
    tle_data = tle_builder.build_tle_data(args, estimated)
    try:
        tle_kep = convert_tle.tle_to_osculating_keplerian(tle_data, mu)
    except Exception:
        return None

    tle_kep_array = np.array(tle_kep)  # (6,) Keplerian elements

    # Element-wise differences
    da_m = tle_kep_array[0] - ref_kep[kepler.SEMI_MAJOR_AXIS_INDEX]  # scalar
    de = tle_kep_array[1] - ref_kep[kepler.ECCENTRICITY_INDEX]
    di_rad = tle_kep_array[2] - ref_kep[kepler.INCLINATION_INDEX]

    # Angle differences wrapped to [-pi, pi]
    def _angle_diff(a, b):
        """Compute angle difference wrapped to [-π, π]."""
        d = (a - b) % (2.0 * np.pi)
        if d > np.pi:
            d -= 2.0 * np.pi
        return d

    domega_rad = _angle_diff(
        tle_kep_array[4], ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX]
    )
    draan_rad = _angle_diff(tle_kep_array[3], ref_kep[kepler.RAAN_INDEX])
    dtheta_rad = _angle_diff(tle_kep_array[5], ref_kep[kepler.TRUE_ANOMALY_INDEX])

    # Argument of latitude difference (well-defined for near-circular orbits)
    ref_u = (
        ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX] + ref_kep[kepler.TRUE_ANOMALY_INDEX]
    ) % (2.0 * np.pi)
    tle_u = (tle_kep_array[4] + tle_kep_array[5]) % (2.0 * np.pi)
    du_rad = _angle_diff(tle_u, ref_u)

    return models.KeplerianAccuracy(
        semi_major_axis_error_m=float(da_m),
        eccentricity_error=float(de),
        inclination_error_deg=float(np.degrees(di_rad)),
        raan_error_deg=float(np.degrees(draan_rad)),
        arg_perigee_error_deg=float(np.degrees(domega_rad)),
        true_anomaly_error_deg=float(np.degrees(dtheta_rad)),
        arg_latitude_error_deg=float(np.degrees(du_rad)),
        ref_semi_major_axis_m=float(ref_kep[kepler.SEMI_MAJOR_AXIS_INDEX]),
        ref_eccentricity=float(ref_kep[kepler.ECCENTRICITY_INDEX]),
        ref_inclination_deg=float(np.degrees(ref_kep[kepler.INCLINATION_INDEX])),
        ref_raan_deg=float(np.degrees(ref_kep[kepler.RAAN_INDEX])),
        ref_arg_perigee_deg=float(
            np.degrees(ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX])
        ),
        ref_true_anomaly_deg=float(np.degrees(ref_kep[kepler.TRUE_ANOMALY_INDEX])),
        tle_semi_major_axis_m=float(tle_kep_array[0]),
        tle_eccentricity=float(tle_kep_array[1]),
        tle_inclination_deg=float(np.degrees(tle_kep_array[2])),
        tle_raan_deg=float(np.degrees(tle_kep_array[3])),
        tle_arg_perigee_deg=float(np.degrees(tle_kep_array[4])),
        tle_true_anomaly_deg=float(np.degrees(tle_kep_array[5])),
    )
