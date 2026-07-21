"""TLE refinement algorithms using state-match and Keplerian-match methods.

This module provides iterative refinement algorithms to improve TLE accuracy:
- State-match: Minimizes weighted Cartesian state residuals at epoch using SGP4
- Keplerian-match: Minimizes osculating Keplerian element residuals using two-body mechanics

Both methods use finite-difference Gauss-Newton optimization with line search.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import replace

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.common as common
import common.convert_tle as convert_tle
import common.kepler as kepler
import common.tle as tle
import common.consts as consts

from . import constants
from .linalg import solve_weighted_least_squares
from .models import Estimated, KeplerianMatchErrors, TleDeltas, TleParameters
from .tle_builder import (
    build_tle_data,
    build_tle_lines,
    format_tle_exponential_from_float,
)

try:
    from tudatpy.dynamics import environment_setup
    from tudatpy.interface import spice
except Exception:
    environment_setup = None
    spice = None


def evaluate_tle_epoch_states_m(
    line_pairs: list[tuple[str, str]],
) -> list[np.ndarray] | None:
    """Evaluate SGP4 Cartesian states at each TLE's reference epoch.

    Parameters
    ----------
    line_pairs : list[tuple[str, str]]
        List of (line1, line2) TLE string pairs.

    Returns
    -------
    list[np.ndarray] | None
        List of state vectors (6,) [x, y, z, vx, vy, vz] in m and m/s, or None on failure.
    """
    if environment_setup is None or spice is None:
        return None

    try:
        states: list[np.ndarray] = []
        for line1, line2 in line_pairs:
            settings = environment_setup.ephemeris.sgp4(line1, line2)
            ephemeris = environment_setup.create_body_ephemeris(
                settings, body_name="state_match"
            )
            tle_obj = ephemeris.tle
            state = ephemeris.cartesian_state(tle_obj.reference_epoch)  # (6,) in meters
            states.append(np.asarray(state, dtype=float))  # (6,)
        return states
    except Exception:
        return None


def evaluate_tle_states_for_offsets_m(
    line1: str, line2: str, time_offsets_s: list[float]
) -> list[np.ndarray] | None:
    """Evaluate one TLE at multiple offsets from its reference epoch.

    Parameters
    ----------
    line1 : str
        TLE line 1 string.
    line2 : str
        TLE line 2 string.
    time_offsets_s : list[float]
        Time offsets from epoch in seconds.

    Returns
    -------
    list[np.ndarray] | None
        List of state vectors (6,) [x, y, z, vx, vy, vz] in m and m/s, or None on failure.
    """
    if environment_setup is None or spice is None:
        return None

    try:
        settings = environment_setup.ephemeris.sgp4(line1, line2)
        ephemeris = environment_setup.create_body_ephemeris(
            settings, body_name="state_match_arc"
        )
        tle_obj = ephemeris.tle
        epoch = tle_obj.reference_epoch

        states: list[np.ndarray] = []
        for dt in time_offsets_s:
            state = ephemeris.cartesian_state(epoch + dt)  # (6,) in meters
            states.append(np.asarray(state, dtype=float))  # (6,)
        return states
    except Exception:
        return None


def clamp_refined_elements(params: TleParameters) -> TleParameters:
    """Clamp refined TLE element parameters to valid ranges.

    Parameters
    ----------
    params : TleParameters
        TleParameters object.

    Returns
    -------
    TleParameters
        TleParameters object.
    """
    assert isinstance(params, TleParameters)

    return replace(
        params,
        inclination_deg=float(np.clip(params.inclination_deg, 0.0, 180.0)),
        raan_deg=math.degrees(common.wrap_angle_rad(math.radians(params.raan_deg))),
        arg_perigee_deg=math.degrees(
            common.wrap_angle_rad(math.radians(params.arg_perigee_deg))
        ),
        mean_anomaly_deg=math.degrees(
            common.wrap_angle_rad(math.radians(params.mean_anomaly_deg))
        ),
        eccentricity=float(np.clip(params.eccentricity, 0.0, 0.9999999)),
        mean_motion_rev_per_day=max(params.mean_motion_rev_per_day, 1e-8),
    )


def compute_state_match_score(
    residual_state: np.ndarray,
) -> tuple[float, float, float]:
    """Return weighted score plus position/velocity residual magnitudes.

    Parameters
    ----------
    residual_state : np.ndarray
        State residual vector (6,) [dx, dy, dz, dvx, dvy, dvz] in m and m/s.

    Returns
    -------
    tuple[float, float, float]
        Weighted score, position error (m), velocity error (m/s).
    """
    residual_state_vec: np.ndarray = np.asarray(
        residual_state, dtype=float
    )  # (6,) state residual
    position_error_m: float = float(
        np.linalg.norm(residual_state_vec[:3])
    )  # norm of (3,) position components
    velocity_error_m_s: float = float(
        np.linalg.norm(residual_state_vec[3:])
    )  # norm of (3,) velocity components
    score: float = (
        constants.STATE_MATCH_POSITION_WEIGHT * position_error_m
        + constants.STATE_MATCH_VELOCITY_WEIGHT * velocity_error_m_s
    )
    return score, position_error_m, velocity_error_m_s


def refine_estimated_fields_to_match_epoch_state(
    args: argparse.Namespace, estimated: Estimated, target_state_m_m_s: np.ndarray
) -> Estimated:
    """Refine line-2 fields using finite-difference Gauss-Newton iterations.

    The objective is weighted epoch-state residual in m and m/s.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    estimated : Estimated
        Estimated TLE elements dataclass.
    target_state_m_m_s : np.ndarray
        Target state vector (6,) [x, y, z, vx, vy, vz] in m and m/s.

    Returns
    -------
    Estimated
        Updated estimated dataclass with refined elements and error metrics.
    """
    step_sizes: list[float] = [
        constants.STATE_MATCH_PARAMETER_STEPS[name]
        for name in TleParameters.__dataclass_fields__
    ]

    def evaluate_with_params(
        current_params: TleParameters,
    ) -> tuple[
        np.ndarray | None, np.ndarray | None, float | None, tuple[float, float] | None
    ]:
        trial_estimated: Estimated = current_params.apply_to_estimated(estimated)
        line1: str
        line2: str
        line1, line2 = build_tle_lines(args, trial_estimated)
        states: list[np.ndarray] | None = evaluate_tle_epoch_states_m([(line1, line2)])
        state: np.ndarray | None = None if states is None else states[0]  # (6,)
        if state is None:
            return None, None, None, None
        residual: np.ndarray = target_state_m_m_s - state  # (6,) - (6,) = (6,)
        score: float
        position_error_m: float
        velocity_error_m_s: float
        score, position_error_m, velocity_error_m_s = compute_state_match_score(
            residual
        )
        return state, residual, score, (position_error_m, velocity_error_m_s)

    current_params: TleParameters = TleParameters.from_estimated(estimated)
    _: np.ndarray | None
    residual: np.ndarray | None
    best_score: float | None
    best_errors: tuple[float, float] | None
    _, residual, best_score, best_errors = evaluate_with_params(current_params)
    if residual is None:
        estimated.state_match_refinement_used = False
        estimated.state_match_position_error_m = None
        estimated.state_match_velocity_error_m_s = None
        return estimated

    best_params: TleParameters = current_params
    iteration_count: int = 0

    for _ in range(constants.STATE_MATCH_MAX_ITERATIONS):
        jacobian: np.ndarray = np.zeros((6, len(step_sizes)))  # (6×6) Jacobian matrix
        finite_difference_specs: list[
            tuple[int, float, TleParameters, TleParameters]
        ] = []
        for parameter_index, (parameter_name, step_size) in enumerate(
            zip(TleParameters.__dataclass_fields__, step_sizes)
        ):
            plus_params: TleParameters = clamp_refined_elements(
                current_params.perturb(parameter_name, step_size)
            )
            minus_params: TleParameters = clamp_refined_elements(
                current_params.perturb(parameter_name, -step_size)
            )
            finite_difference_specs.append(
                (parameter_index, step_size, plus_params, minus_params)
            )

        finite_difference_pairs: list[tuple[str, str]] = []
        for _, _, plus_params, minus_params in finite_difference_specs:
            for trial_params in (plus_params, minus_params):
                trial_estimated: Estimated = trial_params.apply_to_estimated(estimated)
                finite_difference_pairs.append(build_tle_lines(args, trial_estimated))

        finite_difference_states: list[np.ndarray] | None = evaluate_tle_epoch_states_m(
            finite_difference_pairs
        )
        if finite_difference_states is None:
            estimated.state_match_refinement_used = False
            estimated.state_match_position_error_m = best_errors[0]
            estimated.state_match_velocity_error_m_s = best_errors[1]
            return estimated

        for spec_index, (parameter_index, step_size, _, _) in enumerate(
            finite_difference_specs
        ):
            plus_state: np.ndarray = finite_difference_states[2 * spec_index]
            minus_state: np.ndarray = finite_difference_states[2 * spec_index + 1]
            if plus_state is None or minus_state is None:
                estimated.state_match_refinement_used = False
                estimated.state_match_position_error_m = best_errors[0]
                estimated.state_match_velocity_error_m_s = best_errors[1]
                return estimated

            jacobian[:, parameter_index] = (plus_state - minus_state) / (  # (6,) column
                2.0 * step_size
            )

        # Build weighted normal equations using numpy
        weights: np.ndarray = np.where(  # (6,) weight vector
            np.arange(6) < 3,
            constants.STATE_MATCH_POSITION_WEIGHT,
            constants.STATE_MATCH_VELOCITY_WEIGHT,
        )
        W: np.ndarray = np.diag(weights)  # (6×6) diagonal weight matrix
        Jw: np.ndarray = W @ jacobian  # (6×6) @ (6×6) = (6×6) weighted Jacobian
        rw: np.ndarray = weights * residual  # (6,) * (6,) = (6,) weighted residual
        delta_arr: np.ndarray | None  # (6,) parameter update vector
        try:
            delta_arr = np.linalg.lstsq(Jw, rw, rcond=None)[0]  # (6,)
        except np.linalg.LinAlgError:
            break

        accepted: bool = False
        line_search_params: list[tuple[float, TleParameters]] = []
        for line_search_scale in [1.0, 0.5, 0.25, 0.1]:
            trial_params: TleParameters = clamp_refined_elements(
                current_params.apply_deltas(
                    TleDeltas.from_array(delta_arr), scale=line_search_scale
                )
            )
            line_search_params.append((line_search_scale, trial_params))

        line_search_pairs: list[tuple[str, str]] = []
        for _, trial_params in line_search_params:
            trial_estimated: Estimated = trial_params.apply_to_estimated(estimated)
            line_search_pairs.append(build_tle_lines(args, trial_estimated))

        line_search_states: list[np.ndarray] | None = evaluate_tle_epoch_states_m(
            line_search_pairs
        )
        if line_search_states is None:
            break

        for (_, trial_params), trial_state in zip(
            line_search_params, line_search_states
        ):
            if trial_state is None:
                continue
            trial_residual: np.ndarray = (
                target_state_m_m_s - trial_state
            )  # (6,) - (6,) = (6,)
            trial_score: float
            position_error_m: float
            velocity_error_m_s: float
            (
                trial_score,
                position_error_m,
                velocity_error_m_s,
            ) = compute_state_match_score(trial_residual)
            trial_errors: tuple[float, float] = (position_error_m, velocity_error_m_s)
            if trial_score < best_score:
                current_params = trial_params
                residual = trial_residual
                best_score = trial_score
                best_errors = trial_errors
                best_params = trial_params
                accepted = True
                iteration_count += 1
                break

        if not accepted:
            break

    best_params.write_back(estimated)

    estimated.state_match_refinement_used = iteration_count > 0
    estimated.state_match_iterations = iteration_count
    estimated.state_match_position_error_m = best_errors[0]
    estimated.state_match_velocity_error_m_s = best_errors[1]
    return estimated


def compute_keplerian_match_score(
    tle_kep: list[float], ref_kep: list[float]
) -> tuple[float, KeplerianMatchErrors]:
    """Compute a scalar score from osculating Keplerian element residuals.

    Compares the TLE-derived osculating elements (from tle_to_osculating_keplerian)
    against reference osculating elements (from cartesian_to_keplerian).

    Weights are chosen so that semi-major axis (in km), eccentricity (scaled),
    and angular elements (in degrees) contribute comparably.

    Parameters
    ----------
    tle_kep : list[float]
        TLE-derived osculating Keplerian elements (6,) [a, e, i, Ω, ω, ν].
    ref_kep : list[float]
        Reference osculating Keplerian elements (6,) [a, e, i, Ω, ω, ν].

    Returns
    -------
    tuple[float, KeplerianMatchErrors]
        Weighted score and element-wise errors dataclass.
    """
    mu: float = (
        consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )  # Earth gravitational parameter (m³/s²)

    # Semi-major axis difference in m
    da_m: float = (
        tle_kep[kepler.SEMI_MAJOR_AXIS_INDEX] - ref_kep[kepler.SEMI_MAJOR_AXIS_INDEX]
    )

    # Eccentricity difference (dimensionless)
    de: float = tle_kep[kepler.ECCENTRICITY_INDEX] - ref_kep[kepler.ECCENTRICITY_INDEX]

    # Inclination difference in degrees
    di_deg: float = math.degrees(
        tle_kep[kepler.INCLINATION_INDEX] - ref_kep[kepler.INCLINATION_INDEX]
    )

    # Angle differences wrapped to [-180, 180] degrees
    def _angle_diff_deg(angle_a_rad: float, angle_b_rad: float) -> float:
        diff_deg: float = math.degrees(angle_a_rad - angle_b_rad) % 360.0
        if diff_deg > 180.0:
            diff_deg -= 360.0
        return diff_deg

    draan_deg: float = _angle_diff_deg(
        tle_kep[kepler.RAAN_INDEX], ref_kep[kepler.RAAN_INDEX]
    )
    domega_deg: float = _angle_diff_deg(
        tle_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX],
        ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX],
    )
    dtheta_deg: float = _angle_diff_deg(
        tle_kep[kepler.TRUE_ANOMALY_INDEX], ref_kep[kepler.TRUE_ANOMALY_INDEX]
    )

    # Argument of latitude u = ω + ν (well-defined for near-circular orbits)
    tle_u_rad: float = (
        tle_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX] + tle_kep[kepler.TRUE_ANOMALY_INDEX]
    ) % (2.0 * math.pi)
    ref_u_rad: float = (
        ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX] + ref_kep[kepler.TRUE_ANOMALY_INDEX]
    ) % (2.0 * math.pi)
    du_deg: float = _angle_diff_deg(tle_u_rad, ref_u_rad)

    # Weighted score: semi-major axis in m, eccentricity scaled by 1e4,
    # angles in degrees. This gives roughly comparable magnitudes for LEO.
    score: float = (
        abs(da_m) / 1000.0 + 1e4 * abs(de) + abs(di_deg) + abs(draan_deg) + abs(du_deg)
    )

    errors: KeplerianMatchErrors = KeplerianMatchErrors(
        semi_major_axis_error_m=da_m,
        eccentricity_error=de,
        inclination_error_deg=di_deg,
        raan_error_deg=draan_deg,
        arg_perigee_error_deg=domega_deg,
        true_anomaly_error_deg=dtheta_deg,
        arg_latitude_error_deg=du_deg,
    )

    return score, errors


def refine_estimated_fields_keplerian_match(
    args: argparse.Namespace,
    estimated: Estimated,
    states: list[tuple[float, np.ndarray]],
) -> Estimated:
    """Refine TLE fields by minimizing osculating Keplerian element residuals.

    Uses common.convert_tle.tle_to_osculating_keplerian to convert the candidate
    TLE to osculating elements, and compares against the reference osculating
    elements derived from the input Cartesian state at epoch via
    common.kepler.cartesian_to_keplerian.

    This approach does NOT require SGP4/tudatpy — it uses pure two-body
    Keplerian mechanics for the TLE-to-osculating conversion.

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
        Updated estimated dataclass with refined elements and error metrics.
    """
    mu: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2

    # Compute reference osculating Keplerian elements from input state at epoch
    ref_state_m: np.ndarray = states[0][1]  # (6,) state vector [x, y, z, vx, vy, vz]

    try:
        ref_kep: np.ndarray = kepler.cartesian_to_keplerian(
            ref_state_m, mu
        )  # (6,) Keplerian elements
    except ValueError:
        estimated.keplerian_match_refinement_used = False
        return estimated

    step_sizes: list[float] = [
        constants.STATE_MATCH_PARAMETER_STEPS[name]
        for name in TleParameters.__dataclass_fields__
    ]

    def evaluate_keplerian_score(
        current_params: TleParameters,
    ) -> tuple[float | None, KeplerianMatchErrors | None]:
        """Build TLE from params, convert to osculating, compute score."""
        trial_estimated: Estimated = current_params.apply_to_estimated(estimated)
        tle_data: tle.Tle = build_tle_data(args, trial_estimated)
        try:
            tle_kep: list[float] = convert_tle.tle_to_osculating_keplerian(tle_data, mu)
        except Exception:
            return None, None
        score: float
        errors: KeplerianMatchErrors
        score, errors = compute_keplerian_match_score(tle_kep, ref_kep)
        return score, errors

    current_params: TleParameters = TleParameters.from_estimated(estimated)
    best_score: float | None
    best_errors: KeplerianMatchErrors | None
    best_score, best_errors = evaluate_keplerian_score(current_params)
    if best_score is None:
        estimated.keplerian_match_refinement_used = False
        return estimated

    best_params: TleParameters = current_params
    iteration_count: int = 0

    for _ in range(constants.STATE_MATCH_MAX_ITERATIONS):
        # Build Jacobian via finite differences (6 elements output, 6 params input)
        # We use a 6-element residual vector: [da_km, de*1e4, di_deg, draan_deg, domega_deg, du_deg]
        def get_residual_vector(params: TleParameters) -> np.ndarray | None:
            trial_estimated: Estimated = params.apply_to_estimated(estimated)
            tle_data: tle.Tle = build_tle_data(args, trial_estimated)
            try:
                tle_kep: list[float] = convert_tle.tle_to_osculating_keplerian(
                    tle_data, mu
                )
            except Exception:
                return None
            score: float
            errors: KeplerianMatchErrors
            score, errors = compute_keplerian_match_score(tle_kep, ref_kep)
            # Residual vector (6,) (target - current = negative of errors)
            return np.array(
                [
                    -errors.semi_major_axis_error_m
                    / 1000.0,  # Scale to km for comparable magnitudes
                    -errors.eccentricity_error * 1e4,
                    -errors.inclination_error_deg,
                    -errors.raan_error_deg,
                    -errors.arg_latitude_error_deg,
                    -errors.arg_perigee_error_deg,
                ]
            )  # (6,)

        residual: np.ndarray | None = get_residual_vector(current_params)  # (6,)
        if residual is None:
            break

        jacobian: np.ndarray = np.zeros((6, len(step_sizes)))  # (6×6) Jacobian matrix
        jacobian_valid: bool = True
        for param_idx, (param_name, step_size) in enumerate(
            zip(TleParameters.__dataclass_fields__, step_sizes)
        ):
            plus_params: TleParameters = clamp_refined_elements(
                current_params.perturb(param_name, step_size)
            )
            minus_params: TleParameters = clamp_refined_elements(
                current_params.perturb(param_name, -step_size)
            )

            plus_residual: np.ndarray | None = get_residual_vector(plus_params)
            minus_residual: np.ndarray | None = get_residual_vector(minus_params)
            if plus_residual is None or minus_residual is None:
                jacobian_valid = False
                break

            # Fill column param_idx of (6×6) Jacobian
            # Jacobian of (target - f(x)) w.r.t. x
            # d(residual)/d(param) = -(d(error)/d(param))
            # But we compute it directly from finite differences of the residual
            jacobian[:, param_idx] = (plus_residual - minus_residual) / (
                2.0 * step_size
            )

        if not jacobian_valid:
            break

        # Solve least-squares: J * delta = residual
        delta: np.ndarray | None = solve_weighted_least_squares(
            jacobian, residual
        )  # (6,) parameter update
        if delta is None:
            break

        # Line search
        accepted: bool = False
        for line_search_scale in [1.0, 0.5, 0.25, 0.1]:
            trial_params: TleParameters = clamp_refined_elements(
                current_params.apply_deltas(
                    TleDeltas.from_array(delta), scale=line_search_scale
                )
            )

            trial_score: float | None
            trial_errors: KeplerianMatchErrors | None
            trial_score, trial_errors = evaluate_keplerian_score(trial_params)
            if trial_score is None:
                continue
            if trial_score < best_score:
                current_params = trial_params
                best_score = trial_score
                best_errors = trial_errors
                best_params = trial_params
                accepted = True
                iteration_count += 1
                break

        if not accepted:
            break

    best_params.write_back(estimated)

    estimated.keplerian_match_refinement_used = iteration_count > 0
    estimated.keplerian_match_iterations = iteration_count
    estimated.keplerian_match_score = best_score
    if best_errors is not None:
        estimated.keplerian_match_errors = best_errors
    return estimated
