#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import io
import math
import sys
import os
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings("ignore", module="urllib3")

try:
    from tudatpy.dynamics import environment_setup
    from tudatpy.interface import spice
except Exception:
    environment_setup = None
    spice = None

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.kepler as kepler
import common.oem as oem
import common.tle as tle

EARTH_GRAVITATIONAL_PARAMETER_KM3_S2 = 398600.4418
EARTH_EQUATORIAL_RADIUS_KM = 6378.1363
EARTH_J2 = 1.08262668e-3
SECONDS_PER_DAY = 86400.0
MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE = 0.99999999
PHASE_MATCH_BLEND_SOFTENING = 6.0
STATE_MATCH_MAX_ITERATIONS = 200
STATE_MATCH_POSITION_WEIGHT = 1.0
STATE_MATCH_VELOCITY_WEIGHT = 1000.0
BSTAR_FIT_MAX_ABS = 1.0e-3
BSTAR_FIT_INITIAL_STEP = 2.0e-5
BSTAR_FIT_MAX_ITERATIONS = 12
BSTAR_SAMPLE_COUNT = 9
STATE_MATCH_PARAMETER_STEPS = {
    "inclination_deg": 0.005,
    "raan_deg": 0.005,
    "eccentricity": 2.0e-5,
    "arg_perigee_deg": 0.01,
    "mean_anomaly_deg": 0.01,
    "mean_motion_rev_per_day": 1.0e-4,
}
_SPICE_KERNELS_LOADED = False


def ensure_spice_kernels_loaded():
    """Load SPICE kernels once per process.

    Returns True when kernels are available for subsequent TudatPy calls,
    otherwise False.
    """
    global _SPICE_KERNELS_LOADED
    if _SPICE_KERNELS_LOADED:
        return True
    if spice is None:
        return False

    try:
        spice.load_standard_kernels()
    except Exception:
        return False

    _SPICE_KERNELS_LOADED = True
    return True


def parse_oem_state_line(line):
    """Parse one OEM-like Cartesian state line.

    Expected format:
    UTC_ISO x_km y_km z_km vx_km_s vy_km_s vz_km_s

    Fields may be separated by whitespace or commas. A trailing "Z" suffix on
    the epoch is accepted and stripped before ISO parsing.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    parts = [p for token in stripped.split() for p in token.split(",")]
    if len(parts) < 7:
        raise ValueError(f"Line does not contain 7 fields: '{line.rstrip()}'")

    epoch_text = parts[0]
    if epoch_text.endswith("Z"):
        epoch_text = epoch_text[:-1]

    try:
        epoch_dt = datetime.fromisoformat(epoch_text)
    except ValueError as error:
        raise ValueError(
            f"Invalid epoch '{parts[0]}': expected ISO format like 2026-05-31T12:34:56.000"
        ) from error

    try:
        x, y, z, vx, vy, vz = (float(value) for value in parts[1:7])
    except ValueError as error:
        raise ValueError(
            f"Invalid numeric state fields in line: '{line.rstrip()}'"
        ) from error

    return epoch_dt, [x, y, z], [vx, vy, vz]


def norm3(vector):
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def wrap_angle_rad(angle):
    wrapped = math.fmod(angle, 2.0 * math.pi)
    if wrapped < 0.0:
        wrapped += 2.0 * math.pi
    return wrapped


def unwrap_angles_rad(angles):
    if not angles:
        return []

    unwrapped = [angles[0]]
    offset = 0.0
    previous = angles[0]

    for angle in angles[1:]:
        delta = angle - previous
        if delta > math.pi:
            offset -= 2.0 * math.pi
        elif delta < -math.pi:
            offset += 2.0 * math.pi

        unwrapped.append(angle + offset)
        previous = angle

    return unwrapped


def circular_mean_angle_rad(angles):
    """Return circular mean angle in [0, 2*pi)."""
    if not angles:
        return 0.0

    sin_sum = sum(math.sin(angle) for angle in angles)
    cos_sum = sum(math.cos(angle) for angle in angles)
    if abs(sin_sum) < 1e-15 and abs(cos_sum) < 1e-15:
        return wrap_angle_rad(angles[0])

    return wrap_angle_rad(math.atan2(sin_sum, cos_sum))


def angle_difference_rad(target, reference):
    """Return signed wrapped angle difference target-reference in [-pi, pi]."""
    delta = wrap_angle_rad(target - reference)
    if delta > math.pi:
        delta -= 2.0 * math.pi
    return delta


def circular_blend_angle_rad(primary_angle, correction_angle, correction_weight):
    """Blend angles along the shortest arc."""
    return wrap_angle_rad(
        primary_angle
        + correction_weight * angle_difference_rad(correction_angle, primary_angle)
    )


def phase_match_epoch_angles(records, first_u_rad, orbit_period_day, tolerance_deg=0.5):
    """Average osculating angles at repeated epoch-like orbital phases.

    This provides a local short-period correction around the chosen epoch phase.
    """
    if orbit_period_day <= 0.0:
        return None

    tolerance_rad = math.radians(tolerance_deg)
    max_revolution = int(records[-1]["t_day"] / orbit_period_day) + 1
    matched_records = []

    for revolution in range(max_revolution + 1):
        target_time_day = revolution * orbit_period_day
        best_record = None
        best_score = None

        for record in records:
            if abs(record["t_day"] - target_time_day) > 0.15 * orbit_period_day:
                continue

            score = abs(
                angle_difference_rad(record["mean_argument_latitude_rad"], first_u_rad)
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

    return {
        "count": len(matched_records),
        "raan_rad": circular_mean_angle_rad(
            [record["raan_rad"] for record in matched_records]
        ),
        "arg_perigee_rad": circular_mean_angle_rad(
            [record["arg_perigee_rad"] for record in matched_records]
        ),
        "mean_anomaly_rad": circular_mean_angle_rad(
            [record["mean_anomaly_rad"] for record in matched_records]
        ),
    }


def estimate_inclination_from_nodal_drift(
    times_s,
    raan_series_rad,
    mean_motion_rad_s_series,
    p_km_series,
    fallback_inclination_deg,
):
    """Estimate mean inclination from J2 nodal precession rate.

    Uses:
      dOmega/dt = -1.5 * J2 * n * (Re/p)^2 * cos(i)

    For near-equatorial orbits (inclination < 1 degree), the nodal drift
    signal is too weak relative to short-period noise, so the osculating
    inclination is used directly as a more reliable estimate.
    """
    # For near-equatorial orbits, nodal precession is dominated by noise.
    # Use the osculating inclination directly.
    if fallback_inclination_deg < 1.0 or fallback_inclination_deg > 179.0:
        return fallback_inclination_deg

    if len(times_s) < 2:
        return fallback_inclination_deg

    raan_unwrapped = unwrap_angles_rad(raan_series_rad)
    domega_dt = linear_regression_slope(times_s, raan_unwrapped)  # rad/s

    mean_n = sum(mean_motion_rad_s_series) / len(mean_motion_rad_s_series)
    mean_p = sum(p_km_series) / len(p_km_series)

    if mean_n <= 0.0 or mean_p <= 0.0:
        return fallback_inclination_deg

    coefficient = 1.5 * EARTH_J2 * mean_n * (EARTH_EQUATORIAL_RADIUS_KM / mean_p) ** 2
    if coefficient <= 0.0:
        return fallback_inclination_deg

    cos_inclination = -domega_dt / coefficient
    if cos_inclination < -1.0 or cos_inclination > 1.0:
        return fallback_inclination_deg

    estimated_deg = math.degrees(math.acos(cos_inclination))

    # Sanity check: if the nodal-drift estimate deviates too far from the
    # osculating value, it is likely corrupted by noise or insufficient arc.
    # In that case, fall back to the osculating inclination.
    if abs(estimated_deg - fallback_inclination_deg) > 5.0:
        return fallback_inclination_deg

    return estimated_deg


def linear_regression_slope(xs, ys):
    """Return OLS slope b from y = a + b*x."""
    if len(xs) < 2:
        return 0.0

    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)

    if denominator <= 0.0:
        return 0.0

    return numerator / denominator


def linear_regression_intercept(xs, ys):
    """Return OLS intercept a from y = a + b*x."""
    if len(xs) < 1:
        return 0.0
    if len(xs) == 1:
        return ys[0]

    slope = linear_regression_slope(xs, ys)
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    return mean_y - slope * mean_x


def solve_linear_system(matrix, vector):
    """Solve a dense linear system with Gaussian elimination."""
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]

    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        pivot_value = augmented[pivot_row][pivot_index]
        if abs(pivot_value) < 1e-15:
            return None

        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[pivot_index],
            )

        pivot_value = augmented[pivot_index][pivot_index]
        for column_index in range(pivot_index, size + 1):
            augmented[pivot_index][column_index] /= pivot_value

        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            for column_index in range(pivot_index, size + 1):
                augmented[row_index][column_index] -= (
                    factor * augmented[pivot_index][column_index]
                )

    return [augmented[row_index][size] for row_index in range(size)]


def solve_weighted_least_squares(design_matrix, target_vector):
    """Solve a small dense least-squares system via normal equations."""
    column_count = len(design_matrix[0])
    normal_matrix = [[0.0 for _ in range(column_count)] for _ in range(column_count)]
    normal_vector = [0.0 for _ in range(column_count)]

    for row, target in zip(design_matrix, target_vector):
        for column_i in range(column_count):
            normal_vector[column_i] += row[column_i] * target
            for column_j in range(column_count):
                normal_matrix[column_i][column_j] += row[column_i] * row[column_j]

    for diagonal_index in range(column_count):
        normal_matrix[diagonal_index][diagonal_index] += 1e-12

    return solve_linear_system(normal_matrix, normal_vector)


def build_tle_data(args, estimated):
    return tle.Tle(
        name=args.name,
        satellite_number=args.satellite_number,
        classification=args.classification,
        int_designator_year=args.int_designator_year,
        int_designator_launch_number=args.int_designator_launch_number,
        int_designator_piece=sanitize_piece(args.int_designator_piece),
        epoch_year=estimated["epoch_year"],
        epoch_day=estimated["epoch_day"],
        mean_motion_first_derivative=estimated["mean_motion_first_derivative"],
        mean_motion_second_derivative=args.mean_motion_second_derivative,
        bstar=estimated.get("bstar", args.bstar),
        ephemeris_type=args.ephemeris_type,
        element_set_number=args.element_set_number,
        inclination_deg=estimated["inclination_deg"],
        raan_deg=estimated["raan_deg"],
        eccentricity=estimated["eccentricity"],
        arg_perigee_deg=estimated["arg_perigee_deg"],
        mean_anomaly_deg=estimated["mean_anomaly_deg"],
        mean_motion_rev_per_day=estimated["mean_motion_rev_per_day"],
        revolution_number_at_epoch=args.revolution_number_at_epoch,
    )


def build_tle_lines(args, estimated):
    buffer = io.StringIO()
    line1, line2 = tle.write_tle(buffer, build_tle_data(args, estimated))
    return line1, line2


def evaluate_tle_epoch_states_km(line_pairs):
    """Evaluate SGP4 Cartesian states at each TLE's reference epoch.

    Returns a list of [x, y, z, vx, vy, vz] in km and km/s, or None on
    environment/runtime failure.
    """
    if environment_setup is None or spice is None:
        return None

    try:
        states = []
        for line1, line2 in line_pairs:
            settings = environment_setup.ephemeris.sgp4(line1, line2)
            ephemeris = environment_setup.create_body_ephemeris(
                settings, body_name="state_match"
            )
            tle_obj = ephemeris.tle
            state = ephemeris.cartesian_state(tle_obj.reference_epoch) / 1000.0
            states.append([float(value) for value in state])
        return states
    except Exception:
        return None


def evaluate_tle_states_for_offsets_km(line1, line2, time_offsets_s):
    """Evaluate one TLE at multiple offsets from its reference epoch.

    Returns a list of [x, y, z, vx, vy, vz] in km and km/s, or None on
    environment/runtime failure.
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

        states = []
        for dt in time_offsets_s:
            state = ephemeris.cartesian_state(epoch + dt) / 1000.0
            states.append([float(value) for value in state])
        return states
    except Exception:
        return None


def select_bstar_fit_samples(records):
    """Select evenly spaced post-epoch records used for B* fitting."""
    if len(records) <= 1:
        return []

    if len(records) <= BSTAR_SAMPLE_COUNT:
        selected = records[1:]
    else:
        selected = []
        last_index = len(records) - 1
        for sample_index in range(1, BSTAR_SAMPLE_COUNT + 1):
            index = round(sample_index * last_index / BSTAR_SAMPLE_COUNT)
            index = min(max(index, 1), last_index)
            selected.append(records[index])
        # Preserve order while removing duplicates.
        seen = set()
        selected = [
            record
            for record in selected
            if not (
                (record[0], tuple(record[1]), tuple(record[2])) in seen
                or seen.add((record[0], tuple(record[1]), tuple(record[2])))
            )
        ]

    return selected


def estimate_bstar_from_arc(args, estimated, records):
    """Estimate B* by minimizing propagated state mismatch over the OEM arc.

    If --bstar is explicitly provided (not the default placeholder), that value
    is preserved and no estimation is performed.
    """
    if args.bstar != "00000+0":
        estimated["bstar"] = args.bstar
        estimated["bstar_source"] = "input"
        return estimated

    sampled_records = select_bstar_fit_samples(records)
    if not sampled_records:
        estimated["bstar"] = args.bstar
        estimated["bstar_source"] = "default"
        return estimated

    t0 = records[0][0]
    time_offsets_s = [(epoch - t0).total_seconds() for epoch, _, _ in sampled_records]
    target_states = [
        position_km + velocity_km_s for _, position_km, velocity_km_s in sampled_records
    ]

    def evaluate_bstar_cost(bstar_value):
        trial_estimated = estimated.copy()
        trial_estimated["bstar"] = format_tle_exponential_from_float(bstar_value)
        line1, line2 = build_tle_lines(args, trial_estimated)
        states = evaluate_tle_states_for_offsets_km(line1, line2, time_offsets_s)
        if states is None:
            return None

        total_score = 0.0
        for state, target_state in zip(states, target_states):
            residual = [target - value for target, value in zip(target_state, state)]
            score, _, _ = compute_state_match_score(residual)
            total_score += score
        return total_score

    bstar_value = 0.0
    step = BSTAR_FIT_INITIAL_STEP
    best_score = evaluate_bstar_cost(bstar_value)
    if best_score is None:
        estimated["bstar"] = args.bstar
        estimated["bstar_source"] = "default"
        return estimated

    for _ in range(BSTAR_FIT_MAX_ITERATIONS):
        improved = False
        for direction in (1.0, -1.0):
            trial_value = clamp(
                bstar_value + direction * step,
                -BSTAR_FIT_MAX_ABS,
                BSTAR_FIT_MAX_ABS,
            )
            trial_score = evaluate_bstar_cost(trial_value)
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

    estimated["bstar"] = format_tle_exponential_from_float(bstar_value)
    estimated["bstar_float"] = bstar_value
    estimated["bstar_fit_score"] = best_score
    estimated["bstar_source"] = "estimated"
    return estimated


def clamp_refined_elements(params):
    params["inclination_deg"] = clamp(params["inclination_deg"], 0.0, 180.0)
    params["raan_deg"] = math.degrees(wrap_angle_rad(math.radians(params["raan_deg"])))
    params["arg_perigee_deg"] = math.degrees(
        wrap_angle_rad(math.radians(params["arg_perigee_deg"]))
    )
    params["mean_anomaly_deg"] = math.degrees(
        wrap_angle_rad(math.radians(params["mean_anomaly_deg"]))
    )
    params["eccentricity"] = clamp(params["eccentricity"], 0.0, 0.9999999)
    params["mean_motion_rev_per_day"] = max(params["mean_motion_rev_per_day"], 1e-8)
    return params


def compute_state_match_score(residual_state):
    """Return weighted score plus position/velocity residual magnitudes."""
    position_error_km = math.sqrt(
        sum(component * component for component in residual_state[:3])
    )
    velocity_error_km_s = math.sqrt(
        sum(component * component for component in residual_state[3:])
    )
    score = (
        STATE_MATCH_POSITION_WEIGHT * position_error_km
        + STATE_MATCH_VELOCITY_WEIGHT * velocity_error_km_s
    )
    return score, position_error_km, velocity_error_km_s


def refine_estimated_fields_to_match_epoch_state(args, estimated, target_state_km_km_s):
    """Refine line-2 fields using finite-difference Gauss-Newton iterations.

    The objective is weighted epoch-state residual in km and km/s.
    """
    parameter_names = [
        "inclination_deg",
        "raan_deg",
        "eccentricity",
        "arg_perigee_deg",
        "mean_anomaly_deg",
        "mean_motion_rev_per_day",
    ]
    step_sizes = [STATE_MATCH_PARAMETER_STEPS[name] for name in parameter_names]

    def evaluate_with_params(current_params):
        trial_estimated = estimated.copy()
        trial_estimated.update(current_params)
        line1, line2 = build_tle_lines(args, trial_estimated)
        states = evaluate_tle_epoch_states_km([(line1, line2)])
        state = None if states is None else states[0]
        if state is None:
            return None, None, None, None
        residual = [
            target - value for target, value in zip(target_state_km_km_s, state)
        ]
        score, position_error_km, velocity_error_km_s = compute_state_match_score(
            residual
        )
        return state, residual, score, (position_error_km, velocity_error_km_s)

    current_params = {name: estimated[name] for name in parameter_names}
    _, residual, best_score, best_errors = evaluate_with_params(current_params)
    if residual is None:
        estimated["state_match_refinement_used"] = False
        estimated["state_match_position_error_km"] = None
        estimated["state_match_velocity_error_km_s"] = None
        return estimated

    best_params = current_params.copy()
    iteration_count = 0

    for _ in range(STATE_MATCH_MAX_ITERATIONS):
        weighted_design_matrix = []
        weighted_target_vector = []

        jacobian = [[0.0 for _ in parameter_names] for _ in range(6)]
        finite_difference_specs = []
        for parameter_index, (parameter_name, step_size) in enumerate(
            zip(parameter_names, step_sizes)
        ):
            plus_params = clamp_refined_elements(current_params.copy())
            minus_params = clamp_refined_elements(current_params.copy())
            plus_params[parameter_name] += step_size
            minus_params[parameter_name] -= step_size
            plus_params = clamp_refined_elements(plus_params)
            minus_params = clamp_refined_elements(minus_params)
            finite_difference_specs.append(
                (parameter_index, step_size, plus_params, minus_params)
            )

        finite_difference_pairs = []
        for _, _, plus_params, minus_params in finite_difference_specs:
            for trial_params in (plus_params, minus_params):
                trial_estimated = estimated.copy()
                trial_estimated.update(trial_params)
                finite_difference_pairs.append(build_tle_lines(args, trial_estimated))

        finite_difference_states = evaluate_tle_epoch_states_km(finite_difference_pairs)
        if finite_difference_states is None:
            estimated["state_match_refinement_used"] = False
            estimated["state_match_position_error_km"] = best_errors[0]
            estimated["state_match_velocity_error_km_s"] = best_errors[1]
            return estimated

        for spec_index, (parameter_index, step_size, _, _) in enumerate(
            finite_difference_specs
        ):
            plus_state = finite_difference_states[2 * spec_index]
            minus_state = finite_difference_states[2 * spec_index + 1]
            if plus_state is None or minus_state is None:
                estimated["state_match_refinement_used"] = False
                estimated["state_match_position_error_km"] = best_errors[0]
                estimated["state_match_velocity_error_km_s"] = best_errors[1]
                return estimated

            for state_index in range(6):
                jacobian[state_index][parameter_index] = (
                    plus_state[state_index] - minus_state[state_index]
                ) / (2.0 * step_size)

        for state_index, residual_value in enumerate(residual):
            weight = (
                STATE_MATCH_POSITION_WEIGHT
                if state_index < 3
                else STATE_MATCH_VELOCITY_WEIGHT
            )
            weighted_design_matrix.append(
                [weight * value for value in jacobian[state_index]]
            )
            weighted_target_vector.append(weight * residual_value)

        delta = solve_weighted_least_squares(
            weighted_design_matrix, weighted_target_vector
        )
        if delta is None:
            break

        accepted = False
        line_search_params = []
        for line_search_scale in [1.0, 0.5, 0.25, 0.1]:
            trial_params = current_params.copy()
            for parameter_name, raw_step in zip(parameter_names, delta):
                trial_params[parameter_name] += raw_step * line_search_scale
            trial_params = clamp_refined_elements(trial_params)
            line_search_params.append((line_search_scale, trial_params))

        line_search_pairs = []
        for _, trial_params in line_search_params:
            trial_estimated = estimated.copy()
            trial_estimated.update(trial_params)
            line_search_pairs.append(build_tle_lines(args, trial_estimated))

        line_search_states = evaluate_tle_epoch_states_km(line_search_pairs)
        if line_search_states is None:
            break

        for (_, trial_params), trial_state in zip(
            line_search_params, line_search_states
        ):
            if trial_state is None:
                continue
            trial_residual = [
                target - value
                for target, value in zip(target_state_km_km_s, trial_state)
            ]
            (
                trial_score,
                position_error_km,
                velocity_error_km_s,
            ) = compute_state_match_score(trial_residual)
            trial_errors = (position_error_km, velocity_error_km_s)
            if trial_residual is None:
                continue
            if trial_score < best_score:
                current_params = trial_params
                residual = trial_residual
                best_score = trial_score
                best_errors = trial_errors
                best_params = trial_params.copy()
                accepted = True
                iteration_count += 1
                break

        if not accepted:
            break

    for parameter_name, value in best_params.items():
        estimated[parameter_name] = value

    estimated["state_match_refinement_used"] = iteration_count > 0
    estimated["state_match_iterations"] = iteration_count
    estimated["state_match_position_error_km"] = best_errors[0]
    estimated["state_match_velocity_error_km_s"] = best_errors[1]
    return estimated


def compute_keplerian_match_score(tle_kep, ref_kep):
    """Compute a scalar score from osculating Keplerian element residuals.

    Compares the TLE-derived osculating elements (from tle_to_osculating_keplerian)
    against reference osculating elements (from cartesian_to_keplerian).

    Weights are chosen so that semi-major axis (in km), eccentricity (scaled),
    and angular elements (in degrees) contribute comparably.

    Returns (score, element_errors_dict).
    """
    import numpy as np

    mu = kepler.MU_EARTH

    # Semi-major axis difference in km
    da_km = (
        tle_kep["semi_major_axis_m"] - ref_kep[kepler.SEMI_MAJOR_AXIS_INDEX]
    ) / 1000.0

    # Eccentricity difference
    de = tle_kep["eccentricity"] - ref_kep[kepler.ECCENTRICITY_INDEX]

    # Inclination difference in degrees
    di_deg = math.degrees(
        tle_kep["inclination_rad"] - ref_kep[kepler.INCLINATION_INDEX]
    )

    # Angle differences wrapped to [-180, 180] degrees
    def _angle_diff_deg(a_rad, b_rad):
        d = math.degrees(a_rad - b_rad) % 360.0
        if d > 180.0:
            d -= 360.0
        return d

    draan_deg = _angle_diff_deg(tle_kep["raan_rad"], ref_kep[kepler.RAAN_INDEX])
    domega_deg = _angle_diff_deg(
        tle_kep["arg_periapsis_rad"], ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX]
    )
    dtheta_deg = _angle_diff_deg(
        tle_kep["true_anomaly_rad"], ref_kep[kepler.TRUE_ANOMALY_INDEX]
    )

    # Argument of latitude (well-defined for near-circular)
    tle_u = (tle_kep["arg_periapsis_rad"] + tle_kep["true_anomaly_rad"]) % (
        2.0 * math.pi
    )
    ref_u = (
        ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX] + ref_kep[kepler.TRUE_ANOMALY_INDEX]
    ) % (2.0 * math.pi)
    du_deg = _angle_diff_deg(tle_u, ref_u)

    # Weighted score: semi-major axis in km, eccentricity scaled by 1e4,
    # angles in degrees. This gives roughly comparable magnitudes for LEO.
    score = abs(da_km) + 1e4 * abs(de) + abs(di_deg) + abs(draan_deg) + abs(du_deg)

    errors = {
        "semi_major_axis_error_km": da_km,
        "eccentricity_error": de,
        "inclination_error_deg": di_deg,
        "raan_error_deg": draan_deg,
        "arg_perigee_error_deg": domega_deg,
        "true_anomaly_error_deg": dtheta_deg,
        "arg_latitude_error_deg": du_deg,
    }

    return score, errors


def refine_estimated_fields_keplerian_match(args, estimated, records):
    """Refine TLE fields by minimizing osculating Keplerian element residuals.

    Uses common.kepler.tle_to_osculating_keplerian to convert the candidate
    TLE to osculating elements, and compares against the reference osculating
    elements derived from the input Cartesian state at epoch via
    common.kepler.cartesian_to_keplerian.

    This approach does NOT require SGP4/tudatpy — it uses pure two-body
    Keplerian mechanics for the TLE-to-osculating conversion.
    """
    import numpy as np

    mu = kepler.MU_EARTH

    # Compute reference osculating Keplerian elements from input state
    ref_pos_km = records[0][1]
    ref_vel_km_s = records[0][2]
    ref_state_m = np.array(
        [
            ref_pos_km[0] * 1000.0,
            ref_pos_km[1] * 1000.0,
            ref_pos_km[2] * 1000.0,
            ref_vel_km_s[0] * 1000.0,
            ref_vel_km_s[1] * 1000.0,
            ref_vel_km_s[2] * 1000.0,
        ]
    )

    try:
        ref_kep = kepler.cartesian_to_keplerian(ref_state_m, mu)
    except ValueError:
        estimated["keplerian_match_refinement_used"] = False
        return estimated

    parameter_names = [
        "inclination_deg",
        "raan_deg",
        "eccentricity",
        "arg_perigee_deg",
        "mean_anomaly_deg",
        "mean_motion_rev_per_day",
    ]
    step_sizes = [STATE_MATCH_PARAMETER_STEPS[name] for name in parameter_names]

    def evaluate_keplerian_score(current_params):
        """Build TLE from params, convert to osculating, compute score."""
        trial_estimated = estimated.copy()
        trial_estimated.update(current_params)
        tle_data = build_tle_data(args, trial_estimated)
        try:
            tle_kep = kepler.tle_to_osculating_keplerian(tle_data, mu)
        except Exception:
            return None, None
        score, errors = compute_keplerian_match_score(tle_kep, ref_kep)
        return score, errors

    current_params = {name: estimated[name] for name in parameter_names}
    best_score, best_errors = evaluate_keplerian_score(current_params)
    if best_score is None:
        estimated["keplerian_match_refinement_used"] = False
        return estimated

    best_params = current_params.copy()
    iteration_count = 0

    for _ in range(STATE_MATCH_MAX_ITERATIONS):
        # Build Jacobian via finite differences (6 elements output, 6 params input)
        # We use a 6-element residual vector: [da_km, de*1e4, di_deg, draan_deg, domega_deg, du_deg]
        def get_residual_vector(params):
            trial_estimated = estimated.copy()
            trial_estimated.update(params)
            tle_data = build_tle_data(args, trial_estimated)
            try:
                tle_kep = kepler.tle_to_osculating_keplerian(tle_data, mu)
            except Exception:
                return None
            score, errors = compute_keplerian_match_score(tle_kep, ref_kep)
            # Residual vector (target - current = negative of errors)
            return [
                -errors["semi_major_axis_error_km"],
                -errors["eccentricity_error"] * 1e4,
                -errors["inclination_error_deg"],
                -errors["raan_error_deg"],
                -errors["arg_latitude_error_deg"],
                -errors["arg_perigee_error_deg"],
            ]

        residual = get_residual_vector(current_params)
        if residual is None:
            break

        jacobian = [[0.0 for _ in parameter_names] for _ in range(6)]
        jacobian_valid = True
        for param_idx, (param_name, step_size) in enumerate(
            zip(parameter_names, step_sizes)
        ):
            plus_params = clamp_refined_elements(current_params.copy())
            minus_params = clamp_refined_elements(current_params.copy())
            plus_params[param_name] += step_size
            minus_params[param_name] -= step_size
            plus_params = clamp_refined_elements(plus_params)
            minus_params = clamp_refined_elements(minus_params)

            plus_residual = get_residual_vector(plus_params)
            minus_residual = get_residual_vector(minus_params)
            if plus_residual is None or minus_residual is None:
                jacobian_valid = False
                break

            for res_idx in range(6):
                # Jacobian of (target - f(x)) w.r.t. x
                # d(residual)/d(param) = -(d(error)/d(param))
                # But we compute it directly from finite differences of the residual
                jacobian[res_idx][param_idx] = (
                    plus_residual[res_idx] - minus_residual[res_idx]
                ) / (2.0 * step_size)

        if not jacobian_valid:
            break

        # Solve least-squares: J * delta = residual
        delta = solve_weighted_least_squares(jacobian, residual)
        if delta is None:
            break

        # Line search
        accepted = False
        for line_search_scale in [1.0, 0.5, 0.25, 0.1]:
            trial_params = current_params.copy()
            for param_name, raw_step in zip(parameter_names, delta):
                trial_params[param_name] += raw_step * line_search_scale
            trial_params = clamp_refined_elements(trial_params)

            trial_score, trial_errors = evaluate_keplerian_score(trial_params)
            if trial_score is None:
                continue
            if trial_score < best_score:
                current_params = trial_params
                best_score = trial_score
                best_errors = trial_errors
                best_params = trial_params.copy()
                accepted = True
                iteration_count += 1
                break

        if not accepted:
            break

    for param_name, value in best_params.items():
        estimated[param_name] = value

    estimated["keplerian_match_refinement_used"] = iteration_count > 0
    estimated["keplerian_match_iterations"] = iteration_count
    estimated["keplerian_match_score"] = best_score
    if best_errors is not None:
        estimated["keplerian_match_errors"] = best_errors
    return estimated


def parse_dataset_from_oem(source):
    """Parse a CCSDS OEM source into (epoch, position_km, velocity_km_s) records.

    *source* may be a file path (str/Path) or a file-like object.
    Returns the record list, or None if the source is not a valid CCSDS OEM.
    """
    try:
        _, _, states = oem.read_oem(source)
    except Exception:
        return None

    if not states:
        return None

    records = []
    for epoch in sorted(states):
        sv = states[epoch]
        if len(sv) < 6:
            continue
        if isinstance(epoch, (int, float)):
            epoch = datetime.fromtimestamp(epoch, tz=timezone.utc)
        position_km = [float(sv[0]), float(sv[1]), float(sv[2])]
        velocity_km_s = [float(sv[3]), float(sv[4]), float(sv[5])]
        records.append((epoch, position_km, velocity_km_s))

    if len(records) < 2:
        return None

    return records


def parse_dataset(input_text):
    """Parse input text into (epoch, position, velocity) records.

    First attempts to parse as a CCSDS OEM file using common.oem.read_oem.
    Falls back to the legacy line-by-line parser for simple state-vector files.
    """
    # Try CCSDS OEM format first.
    oem_records = parse_dataset_from_oem(io.StringIO(input_text))
    if oem_records is not None:
        return oem_records

    # Fall back to legacy line-by-line parsing.
    records = []
    for raw_line in input_text.splitlines():
        parsed = parse_oem_state_line(raw_line)
        if parsed is not None:
            records.append(parsed)

    if len(records) < 2:
        raise ValueError("Need at least 2 OEM-like state vectors to estimate TLE trend")

    return records


def state_to_orbital_elements(position_km, velocity_km_s):
    """Compute osculating Keplerian elements from one Cartesian state.

    Units: km, km/s in; angular outputs in degrees; mean motion in rev/day.
    """
    mu = EARTH_GRAVITATIONAL_PARAMETER_KM3_S2
    r = position_km
    v = velocity_km_s

    r_norm = norm3(r)
    v_norm = norm3(v)
    if r_norm <= 0.0:
        raise ValueError("Invalid state: position norm is zero")

    h_vec = cross3(r, v)
    h_norm = norm3(h_vec)
    if h_norm <= 0.0:
        raise ValueError("Invalid state: angular momentum norm is zero")

    k_hat = [0.0, 0.0, 1.0]
    n_vec = cross3(k_hat, h_vec)
    n_norm = norm3(n_vec)

    vxh = cross3(v, h_vec)
    e_vec = [vxh[i] / mu - r[i] / r_norm for i in range(3)]
    eccentricity = norm3(e_vec)

    specific_energy = 0.5 * v_norm**2 - mu / r_norm
    if abs(specific_energy) < 1e-15:
        raise ValueError("Parabolic trajectory not supported for TLE estimation")

    semi_major_axis_km = -mu / (2.0 * specific_energy)
    if semi_major_axis_km <= 0.0:
        raise ValueError("Hyperbolic trajectory not supported for TLE estimation")

    inclination_rad = math.acos(clamp(h_vec[2] / h_norm, -1.0, 1.0))

    if n_norm > 0.0:
        raan_rad = math.atan2(n_vec[1], n_vec[0])
    else:
        raan_rad = 0.0

    if n_norm > 0.0 and eccentricity > 1e-12:
        arg_perigee_rad = math.atan2(
            dot3(cross3(n_vec, e_vec), h_vec) / (n_norm * h_norm),
            dot3(n_vec, e_vec) / n_norm,
        )
    else:
        arg_perigee_rad = 0.0

    if eccentricity > 1e-12:
        true_anomaly_rad = math.atan2(
            dot3(cross3(e_vec, r), h_vec) / (eccentricity * h_norm * r_norm),
            dot3(e_vec, r) / (eccentricity * r_norm),
        )
    else:
        if n_norm > 0.0:
            true_anomaly_rad = math.atan2(
                dot3(cross3(n_vec, r), h_vec) / (n_norm * h_norm * r_norm),
                dot3(n_vec, r) / (n_norm * r_norm),
            )
        else:
            true_anomaly_rad = math.atan2(r[1], r[0])

    true_anomaly_rad = wrap_angle_rad(true_anomaly_rad)

    if eccentricity < 1.0:
        eccentric_anomaly_rad = 2.0 * math.atan2(
            math.sqrt(max(0.0, 1.0 - eccentricity)) * math.sin(true_anomaly_rad / 2.0),
            math.sqrt(1.0 + eccentricity) * math.cos(true_anomaly_rad / 2.0),
        )
        mean_anomaly_rad = eccentric_anomaly_rad - eccentricity * math.sin(
            eccentric_anomaly_rad
        )
    else:
        raise ValueError("Eccentricity >= 1 is not supported for TLE estimation")

    mean_anomaly_rad = wrap_angle_rad(mean_anomaly_rad)

    mean_motion_rad_s = math.sqrt(mu / (semi_major_axis_km**3))
    mean_motion_rev_per_day = mean_motion_rad_s * SECONDS_PER_DAY / (2.0 * math.pi)

    return {
        "semi_major_axis_km": semi_major_axis_km,
        "eccentricity": eccentricity,
        "inclination_deg": math.degrees(inclination_rad),
        "raan_deg": math.degrees(wrap_angle_rad(raan_rad)),
        "arg_perigee_deg": math.degrees(wrap_angle_rad(arg_perigee_rad)),
        "mean_anomaly_deg": math.degrees(mean_anomaly_rad),
        "mean_motion_rev_per_day": mean_motion_rev_per_day,
    }


def datetime_to_tle_epoch(epoch_dt):
    """Convert datetime to (two-digit year, day-of-year with fraction)."""
    year_two_digit = epoch_dt.year % 100
    if epoch_dt.tzinfo is not None:
        epoch_dt = epoch_dt.astimezone(timezone.utc)
        start_of_year = datetime(epoch_dt.year, 1, 1, tzinfo=timezone.utc)
    else:
        start_of_year = datetime(epoch_dt.year, 1, 1)
    day_of_year = (epoch_dt - start_of_year).total_seconds() / SECONDS_PER_DAY + 1.0
    return year_two_digit, day_of_year


def format_tle_exponential_from_float(value):
    """Convert float to 7-char compact TLE exponential, no leading sign space."""
    if value == 0.0:
        return "00000+0"

    sign = "-" if value < 0.0 else ""
    abs_value = abs(value)

    exponent = int(math.floor(math.log10(abs_value)))
    mantissa = abs_value / (10.0**exponent)
    mantissa_digits = int(round(mantissa * 1e4))

    if mantissa_digits >= 100000:
        mantissa_digits = 10000
        exponent += 1

    tle_exponent = exponent + 1
    if tle_exponent < -9 or tle_exponent > 9:
        return "00000+0"

    exp_sign = "+" if tle_exponent >= 0 else "-"
    return f"{sign}{mantissa_digits:05d}{exp_sign}{abs(tle_exponent)}"


def sanitize_piece(piece):
    letters_digits = "".join(ch for ch in piece.upper() if ch.isalnum())
    if not letters_digits:
        return "A"
    return letters_digits[:3]


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Read a set of OEM-like state vectors, estimate TLE element values, "
            "and write the resulting TLE to a file or stdout."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.dat>",
        help=(
            "Input OEM-like state-vector file path. Use '-' or omit to read from stdin "
            "(default: '-')."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help=(
            "Output TLE file path (default: '-'). "
            "Use '-' to print TLE text to stdout."
        ),
    )
    parser.add_argument(
        "--name",
        metavar="<name>",
        default="",
        help="Optional satellite name written above line 1.",
    )
    parser.add_argument(
        "--satellite-number",
        type=int,
        default=99999,
        metavar="<0..99999>",
        help="NORAD satellite number for the generated command (default: 99999).",
    )
    parser.add_argument(
        "--classification",
        choices=["U", "C", "S"],
        default="U",
        metavar="<U|C|S>",
        help="Classification code for the generated command (default: U).",
    )
    parser.add_argument(
        "--int-designator-year",
        type=int,
        default=0,
        metavar="<0..99>",
        help="International designator launch year (default: 0).",
    )
    parser.add_argument(
        "--int-designator-launch-number",
        type=int,
        default=0,
        metavar="<0..999>",
        help="International designator launch number (default: 0).",
    )
    parser.add_argument(
        "--int-designator-piece",
        default="A",
        metavar="<piece>",
        help="International designator piece identifier (default: A).",
    )
    parser.add_argument(
        "--ephemeris-type",
        type=int,
        default=0,
        metavar="<0..9>",
        help="Ephemeris type value for generated command (default: 0).",
    )
    parser.add_argument(
        "--element-set-number",
        type=int,
        default=1,
        metavar="<0..9999>",
        help="Element set number for generated command (default: 1).",
    )
    parser.add_argument(
        "--bstar",
        default="00000+0",
        metavar="<tle-exp>",
        help="BSTAR drag term for generated command (default: 00000+0).",
    )
    parser.add_argument(
        "--mean-motion-second-derivative",
        default="00000+0",
        metavar="<tle-exp>",
        help="Second derivative of mean motion for generated command (default: 00000+0).",
    )
    parser.add_argument(
        "--revolution-number-at-epoch",
        type=int,
        default=0,
        metavar="<0..99999>",
        help="Revolution number at epoch for generated command (default: 0).",
    )
    parser.add_argument(
        "--refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        help=(
            "Refinement method for matching TLE elements to the epoch state. "
            "'cartesian' (default): minimize SGP4 Cartesian state residual "
            "(requires tudatpy). "
            "'keplerian': minimize osculating Keplerian element residual via "
            "common.kepler.tle_to_osculating_keplerian (no SGP4 needed). "
            "'none': skip refinement entirely."
        ),
    )
    return parser.parse_args()


def read_input_text(input_path):
    if input_path == "-":
        text = sys.stdin.read()
        if not text.strip():
            raise ValueError("No input from stdin")
        return text

    try:
        with open(input_path, "r") as input_file:
            text = input_file.read()
    except OSError as error:
        raise ValueError(
            f"Could not read input file '{input_path}': {error}"
        ) from error

    if not text.strip():
        raise ValueError(f"Input file '{input_path}' is empty")

    return text


def estimate_tle_fields(records, use_state_match=True):
    # Use the first epoch/state as the epoch of the estimated TLE.
    epoch_dt = records[0][0]
    first_position_km = records[0][1]
    first_velocity_km_s = records[0][2]

    elements_first = state_to_orbital_elements(first_position_km, first_velocity_km_s)

    t0 = records[0][0]
    times_day = []
    times_s = []
    mean_motion_series = []
    eccentricity_series = []
    raan_series_rad = []
    arg_perigee_series_rad = []
    mean_anomaly_series_rad = []
    mean_argument_latitude_series_rad = []
    mean_motion_rad_s_series = []
    p_km_series = []
    records_with_elements = []
    for epoch, position_km, velocity_km_s in records:
        dt_s = (epoch - t0).total_seconds()
        dt_day = dt_s / SECONDS_PER_DAY
        elements = state_to_orbital_elements(position_km, velocity_km_s)
        times_s.append(dt_s)
        times_day.append(dt_day)
        mean_motion_series.append(elements["mean_motion_rev_per_day"])
        eccentricity_series.append(elements["eccentricity"])
        raan_rad = math.radians(elements["raan_deg"])
        arg_perigee_rad = math.radians(elements["arg_perigee_deg"])
        mean_anomaly_rad = math.radians(elements["mean_anomaly_deg"])

        raan_series_rad.append(raan_rad)
        arg_perigee_series_rad.append(arg_perigee_rad)
        mean_anomaly_series_rad.append(mean_anomaly_rad)
        mean_argument_latitude_series_rad.append(
            wrap_angle_rad(arg_perigee_rad + mean_anomaly_rad)
        )
        mean_motion_rad_s_series.append(
            elements["mean_motion_rev_per_day"] * 2.0 * math.pi / SECONDS_PER_DAY
        )
        p_km_series.append(
            elements["semi_major_axis_km"] * (1.0 - elements["eccentricity"] ** 2)
        )
        records_with_elements.append(
            {
                "t_day": dt_day,
                "raan_rad": raan_rad,
                "arg_perigee_rad": arg_perigee_rad,
                "mean_anomaly_rad": mean_anomaly_rad,
                "mean_argument_latitude_rad": wrap_angle_rad(
                    arg_perigee_rad + mean_anomaly_rad
                ),
            }
        )

    raan_unwrapped = unwrap_angles_rad(raan_series_rad)
    raan_mean_at_epoch_deg = math.degrees(
        wrap_angle_rad(linear_regression_intercept(times_s, raan_unwrapped))
    )

    mean_argument_latitude_unwrapped = unwrap_angles_rad(
        mean_argument_latitude_series_rad
    )
    mean_argument_latitude_rate_rad_s = linear_regression_slope(
        times_s, mean_argument_latitude_unwrapped
    )
    mean_argument_latitude_rate_rev_per_day = (
        mean_argument_latitude_rate_rad_s * SECONDS_PER_DAY / (2.0 * math.pi)
    )

    # Remove fitted short-period phase progression and circular-average the
    # residuals to obtain a more stable epoch phase estimate.
    mean_argument_latitude_phase_residuals = [
        wrap_angle_rad(u - mean_argument_latitude_rate_rad_s * dt_s)
        for u, dt_s in zip(mean_argument_latitude_series_rad, times_s)
    ]
    mean_argument_latitude_at_epoch_rad = circular_mean_angle_rad(
        mean_argument_latitude_phase_residuals
    )

    # Mean anomaly can be highly sensitive to unwrap branch in near-circular
    # orbits. Anchor its phase detrending with epoch osculating mean motion.
    mean_motion_phase_rate_rev_per_day = elements_first["mean_motion_rev_per_day"]
    mean_motion_phase_rate_rad_s = (
        mean_motion_phase_rate_rev_per_day * 2.0 * math.pi / SECONDS_PER_DAY
    )
    mean_anomaly_phase_residuals = [
        wrap_angle_rad(m - mean_motion_phase_rate_rad_s * dt_s)
        for m, dt_s in zip(mean_anomaly_series_rad, times_s)
    ]
    mean_anomaly_phase_at_epoch_rad = circular_mean_angle_rad(
        mean_anomaly_phase_residuals
    )
    mean_anomaly_osculating_at_epoch_rad = math.radians(
        elements_first["mean_anomaly_deg"]
    )
    mean_anomaly_at_epoch_rad = circular_mean_angle_rad(
        [
            mean_anomaly_phase_at_epoch_rad,
            mean_anomaly_osculating_at_epoch_rad,
        ]
    )
    mean_anomaly_at_epoch_deg = math.degrees(mean_anomaly_at_epoch_rad)

    arg_perigee_at_epoch_deg = math.degrees(
        wrap_angle_rad(mean_argument_latitude_at_epoch_rad - mean_anomaly_at_epoch_rad)
    )

    orbit_period_day = 1.0 / max(elements_first["mean_motion_rev_per_day"], 1e-12)
    phase_matched_angles = phase_match_epoch_angles(
        records_with_elements,
        first_u_rad=records_with_elements[0]["mean_argument_latitude_rad"],
        orbit_period_day=orbit_period_day,
    )
    phase_match_weight = 0.0
    if phase_matched_angles is not None:
        phase_match_weight = phase_matched_angles["count"] / (
            phase_matched_angles["count"] + PHASE_MATCH_BLEND_SOFTENING
        )
        raan_mean_at_epoch_deg = math.degrees(
            circular_blend_angle_rad(
                math.radians(raan_mean_at_epoch_deg),
                phase_matched_angles["raan_rad"],
                phase_match_weight,
            )
        )
        arg_perigee_at_epoch_deg = math.degrees(
            circular_blend_angle_rad(
                math.radians(arg_perigee_at_epoch_deg),
                phase_matched_angles["arg_perigee_rad"],
                phase_match_weight,
            )
        )
        mean_anomaly_at_epoch_deg = math.degrees(
            circular_blend_angle_rad(
                math.radians(mean_anomaly_at_epoch_deg),
                phase_matched_angles["mean_anomaly_rad"],
                phase_match_weight,
            )
        )

    mean_motion_regression_at_epoch_rev_per_day = linear_regression_intercept(
        times_day, mean_motion_series
    )

    # Blend two complementary estimates to reduce osculating short-period bias:
    # - regression of energy-derived mean motion,
    # - rate of argument of latitude from angle-fit.
    mean_motion_at_epoch_rev_per_day = 0.5 * (
        mean_motion_regression_at_epoch_rev_per_day
        + mean_argument_latitude_rate_rev_per_day
    )

    inclination_deg_estimated = estimate_inclination_from_nodal_drift(
        times_s=times_s,
        raan_series_rad=raan_series_rad,
        mean_motion_rad_s_series=mean_motion_rad_s_series,
        p_km_series=p_km_series,
        fallback_inclination_deg=elements_first["inclination_deg"],
    )

    slope_rev_per_day2 = linear_regression_slope(times_day, mean_motion_series)

    # TLE line 1 stores (1/2) * d(mean_motion)/dt.
    mean_motion_first_derivative_raw = 0.5 * slope_rev_per_day2
    mean_motion_first_derivative = clamp(
        mean_motion_first_derivative_raw,
        -MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE,
        MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE,
    )

    epoch_year, epoch_day = datetime_to_tle_epoch(epoch_dt)

    # Compute mean eccentricity from regression intercept for no-state-match mode.
    eccentricity_mean_at_epoch = linear_regression_intercept(
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
        chosen_raan_deg = elements_first["raan_deg"]
        chosen_arg_perigee_deg = elements_first["arg_perigee_deg"]
        chosen_mean_anomaly_deg = elements_first["mean_anomaly_deg"]
        chosen_eccentricity = max(0.0, min(elements_first["eccentricity"], 0.9999999))
    else:
        # Without state-match refinement, use the averaged/blended values that
        # better approximate SGP4 "mean" elements.  Osculating values contain
        # short-period J2 perturbations that bias the TLE when no optimizer
        # corrects them.
        chosen_raan_deg = raan_mean_at_epoch_deg
        chosen_arg_perigee_deg = arg_perigee_at_epoch_deg
        chosen_mean_anomaly_deg = mean_anomaly_at_epoch_deg
        chosen_eccentricity = eccentricity_mean_at_epoch

    return {
        "epoch_datetime": epoch_dt,
        "epoch_year": epoch_year,
        "epoch_day": epoch_day,
        "inclination_deg": inclination_deg_estimated,
        "inclination_deg_osculating_at_epoch": elements_first["inclination_deg"],
        "raan_deg": chosen_raan_deg,
        "raan_deg_osculating_at_epoch": elements_first["raan_deg"],
        "eccentricity": chosen_eccentricity,
        "arg_perigee_deg": chosen_arg_perigee_deg,
        "arg_perigee_deg_osculating_at_epoch": elements_first["arg_perigee_deg"],
        "mean_anomaly_deg": chosen_mean_anomaly_deg,
        "mean_anomaly_deg_osculating_at_epoch": elements_first["mean_anomaly_deg"],
        "mean_motion_rev_per_day": mean_motion_at_epoch_rev_per_day,
        "mean_motion_rev_per_day_regression_at_epoch": mean_motion_regression_at_epoch_rev_per_day,
        "mean_argument_latitude_rate_rev_per_day": mean_argument_latitude_rate_rev_per_day,
        "mean_motion_rev_per_day_osculating_at_epoch": elements_first[
            "mean_motion_rev_per_day"
        ],
        "phase_match_count": (
            0 if phase_matched_angles is None else phase_matched_angles["count"]
        ),
        "phase_match_weight": phase_match_weight,
        "mean_motion_first_derivative": mean_motion_first_derivative,
        "mean_motion_first_derivative_raw": mean_motion_first_derivative_raw,
        "semi_major_axis_km": elements_first["semi_major_axis_km"],
        "dataset_slope_rev_per_day2": slope_rev_per_day2,
    }


def verify_accuracy_keplerian(args, estimated, records):
    """Verify TLE accuracy using osculating Keplerian elements from common.kepler.

    Uses common.kepler.tle_to_osculating_keplerian to convert the TLE directly
    to osculating elements (two-body), and compares against the reference
    osculating elements derived from the input Cartesian state at epoch via
    common.kepler.cartesian_to_keplerian.

    This does NOT require SGP4/tudatpy — it uses pure two-body Keplerian
    mechanics via common.kepler.

    Returns a dict with element-wise residuals, or None on failure.
    """
    import numpy as np

    mu = kepler.MU_EARTH

    # Reference state at epoch (convert km, km/s -> m, m/s)
    ref_pos_km = records[0][1]
    ref_vel_km_s = records[0][2]
    ref_state_m = np.array(
        [
            ref_pos_km[0] * 1000.0,
            ref_pos_km[1] * 1000.0,
            ref_pos_km[2] * 1000.0,
            ref_vel_km_s[0] * 1000.0,
            ref_vel_km_s[1] * 1000.0,
            ref_vel_km_s[2] * 1000.0,
        ]
    )

    # Compute reference osculating Keplerian elements
    try:
        ref_kep = kepler.cartesian_to_keplerian(ref_state_m, mu)
    except ValueError:
        return None

    # Convert TLE to osculating Keplerian elements via common.kepler
    tle_data = build_tle_data(args, estimated)
    try:
        tle_kep = kepler.tle_to_osculating_keplerian(tle_data, mu)
    except Exception:
        return None

    # Extract TLE osculating elements into array form for comparison
    tle_kep_array = np.array(
        [
            tle_kep["semi_major_axis_m"],
            tle_kep["eccentricity"],
            tle_kep["inclination_rad"],
            tle_kep["raan_rad"],
            tle_kep["arg_periapsis_rad"],
            tle_kep["true_anomaly_rad"],
        ]
    )

    # Element-wise differences
    da_m = tle_kep_array[0] - ref_kep[kepler.SEMI_MAJOR_AXIS_INDEX]
    de = tle_kep_array[1] - ref_kep[kepler.ECCENTRICITY_INDEX]
    di_rad = tle_kep_array[2] - ref_kep[kepler.INCLINATION_INDEX]

    # Angle differences wrapped to [-pi, pi]
    def _angle_diff(a, b):
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

    return {
        "semi_major_axis_error_m": float(da_m),
        "semi_major_axis_error_km": float(da_m) / 1000.0,
        "eccentricity_error": float(de),
        "inclination_error_deg": float(np.degrees(di_rad)),
        "raan_error_deg": float(np.degrees(draan_rad)),
        "arg_perigee_error_deg": float(np.degrees(domega_rad)),
        "true_anomaly_error_deg": float(np.degrees(dtheta_rad)),
        "arg_latitude_error_deg": float(np.degrees(du_rad)),
        "ref_semi_major_axis_km": float(ref_kep[kepler.SEMI_MAJOR_AXIS_INDEX]) / 1000.0,
        "ref_eccentricity": float(ref_kep[kepler.ECCENTRICITY_INDEX]),
        "ref_inclination_deg": float(np.degrees(ref_kep[kepler.INCLINATION_INDEX])),
        "ref_raan_deg": float(np.degrees(ref_kep[kepler.RAAN_INDEX])),
        "ref_arg_perigee_deg": float(
            np.degrees(ref_kep[kepler.ARGUMENT_OF_PERIAPSIS_INDEX])
        ),
        "ref_true_anomaly_deg": float(np.degrees(ref_kep[kepler.TRUE_ANOMALY_INDEX])),
        "tle_semi_major_axis_km": float(tle_kep_array[0]) / 1000.0,
        "tle_eccentricity": float(tle_kep_array[1]),
        "tle_inclination_deg": float(np.degrees(tle_kep_array[2])),
        "tle_raan_deg": float(np.degrees(tle_kep_array[3])),
        "tle_arg_perigee_deg": float(np.degrees(tle_kep_array[4])),
        "tle_true_anomaly_deg": float(np.degrees(tle_kep_array[5])),
    }


def print_summary(records, estimated, args, keplerian_accuracy=None):
    start_epoch = records[0][0]
    end_epoch = records[-1][0]
    span_s = (end_epoch - start_epoch).total_seconds()

    print("Estimated TLE elements from OEM-like dataset:")
    print(f"  records: {len(records)}")
    print(f"  epoch range: {start_epoch.isoformat()} -> {end_epoch.isoformat()}")
    print(f"  span [s]: {span_s:.3f}")
    print(f"  chosen TLE epoch: {estimated['epoch_datetime'].isoformat()}")
    print(f"  epoch-year: {estimated['epoch_year']}")
    print(f"  epoch-day: {estimated['epoch_day']:.8f}")
    print(f"  inclination-deg: {estimated['inclination_deg']:.6f}")
    print(
        "  inclination-deg (osculating at epoch): "
        f"{estimated['inclination_deg_osculating_at_epoch']:.6f}"
    )
    print(f"  raan-deg: {estimated['raan_deg']:.6f}")
    print(
        "  raan-deg (osculating at epoch): "
        f"{estimated['raan_deg_osculating_at_epoch']:.6f}"
    )
    print(f"  eccentricity: {estimated['eccentricity']:.9f}")
    print(f"  arg-perigee-deg: {estimated['arg_perigee_deg']:.6f}")
    print(
        "  arg-perigee-deg (osculating at epoch): "
        f"{estimated['arg_perigee_deg_osculating_at_epoch']:.6f}"
    )
    print(f"  mean-anomaly-deg: {estimated['mean_anomaly_deg']:.6f}")
    print(
        "  mean-anomaly-deg (osculating at epoch): "
        f"{estimated['mean_anomaly_deg_osculating_at_epoch']:.6f}"
    )
    print(f"  mean-motion-rev-per-day: {estimated['mean_motion_rev_per_day']:.10f}")
    print(
        "  mean-motion-rev-per-day (regression at epoch): "
        f"{estimated['mean_motion_rev_per_day_regression_at_epoch']:.10f}"
    )
    print(
        "  mean-arg-latitude-rate-rev-per-day: "
        f"{estimated['mean_argument_latitude_rate_rev_per_day']:.10f}"
    )
    print(
        "  mean-motion-rev-per-day (osculating at epoch): "
        f"{estimated['mean_motion_rev_per_day_osculating_at_epoch']:.10f}"
    )
    print(f"  phase-match-count: {estimated['phase_match_count']}")
    print(f"  phase-match-weight: {estimated['phase_match_weight']:.6f}")
    if estimated.get("state_match_position_error_km") is not None:
        print(
            "  state-match-position-error-km: "
            f"{estimated['state_match_position_error_km']:.6f}"
        )
        print(
            "  state-match-velocity-error-km-s: "
            f"{estimated['state_match_velocity_error_km_s']:.9f}"
        )
        print(
            "  state-match-refinement: "
            f"{'used' if estimated.get('state_match_refinement_used') else 'not-used'}"
        )
        print(
            "  state-match-iterations: " f"{estimated.get('state_match_iterations', 0)}"
        )
    print(f"  semi-major-axis-km: {estimated['semi_major_axis_km']:.6f}")
    print(
        "  d(mean-motion)/dt [rev/day^2] (fit): "
        f"{estimated['dataset_slope_rev_per_day2']:.12f}"
    )
    print(
        "  mean-motion-first-derivative (TLE field): "
        f"{estimated['mean_motion_first_derivative']:.12f}"
    )
    if (
        abs(estimated["mean_motion_first_derivative_raw"])
        > MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE
    ):
        print(
            "  note: first derivative was clamped to TLE field range "
            f"[-{MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE:.8f}, {MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE:.8f}]"
        )
    print(f"  bstar: {estimated.get('bstar', args.bstar)}")
    if estimated.get("bstar_source") is not None:
        print(f"  bstar-source: {estimated['bstar_source']}")
    if estimated.get("bstar_fit_score") is not None:
        print(f"  bstar-fit-score: {estimated['bstar_fit_score']:.9f}")
    print(
        "  mean-motion-second-derivative (input/default): "
        f"{args.mean_motion_second_derivative}"
    )

    # Keplerian element accuracy verification (via common.kepler)
    if keplerian_accuracy is not None:
        print()
        print(
            "  Accuracy verification (osculating Keplerian elements via common.kepler):"
        )
        print(
            f"    semi-major-axis error:    {keplerian_accuracy['semi_major_axis_error_km']:+.6f} km"
            f"  ({keplerian_accuracy['semi_major_axis_error_m']:+.3f} m)"
        )
        print(
            f"    eccentricity error:       {keplerian_accuracy['eccentricity_error']:+.10f}"
        )
        print(
            f"    inclination error:        {keplerian_accuracy['inclination_error_deg']:+.6f} deg"
        )
        print(
            f"    RAAN error:               {keplerian_accuracy['raan_error_deg']:+.6f} deg"
        )
        print(
            f"    arg-perigee error:        {keplerian_accuracy['arg_perigee_error_deg']:+.6f} deg"
        )
        print(
            f"    true-anomaly error:       {keplerian_accuracy['true_anomaly_error_deg']:+.6f} deg"
        )
        print(
            f"    arg-latitude (ω+θ) error: {keplerian_accuracy['arg_latitude_error_deg']:+.6f} deg"
        )
    elif keplerian_accuracy is None and environment_setup is not None:
        print()
        print("  Accuracy verification (osculating Keplerian): SGP4 evaluation failed")

    print()


def main():
    args = parse_arguments()

    # SPICE kernels are initialized once here and reused by all evaluations.
    ensure_spice_kernels_loaded()

    if not (0 <= args.satellite_number <= 99999):
        print("Error: --satellite-number must be in [0, 99999]")
        sys.exit(1)
    if not (0 <= args.int_designator_year <= 99):
        print("Error: --int-designator-year must be in [0, 99]")
        sys.exit(1)
    if not (0 <= args.int_designator_launch_number <= 999):
        print("Error: --int-designator-launch-number must be in [0, 999]")
        sys.exit(1)
    if not (0 <= args.ephemeris_type <= 9):
        print("Error: --ephemeris-type must be in [0, 9]")
        sys.exit(1)
    if not (0 <= args.element_set_number <= 9999):
        print("Error: --element-set-number must be in [0, 9999]")
        sys.exit(1)
    if not (0 <= args.revolution_number_at_epoch <= 99999):
        print("Error: --revolution-number-at-epoch must be in [0, 99999]")
        sys.exit(1)

    try:
        input_text = read_input_text(args.input)
        records = parse_dataset(input_text)
        if args.refinement == "keplerian":
            estimated = estimate_tle_fields(records, use_state_match=True)
            estimated = refine_estimated_fields_keplerian_match(
                args, estimated, records
            )
        elif args.refinement == "cartesian":
            estimated = estimate_tle_fields(records, use_state_match=True)
            target_state_km_km_s = records[0][1] + records[0][2]
            estimated = refine_estimated_fields_to_match_epoch_state(
                args, estimated, target_state_km_km_s
            )
        else:
            # refinement == "none"
            estimated = estimate_tle_fields(records, use_state_match=False)
        estimated = estimate_bstar_from_arc(args, estimated, records)
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)

    # Verify accuracy using osculating Keplerian elements (common.kepler)
    keplerian_accuracy = verify_accuracy_keplerian(args, estimated, records)

    print_summary(records, estimated, args, keplerian_accuracy=keplerian_accuracy)

    tle_data = build_tle_data(args, estimated)

    if args.output == "-":
        tle.write_tle(sys.stdout, tle_data)
    else:
        tle.write_tle(args.output, tle_data)
        print(f"Saved TLE file: {args.output}")


if __name__ == "__main__":
    main()
