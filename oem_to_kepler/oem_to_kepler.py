#!/usr/bin/env python3
"""Convert OEM Cartesian state vectors to mean Keplerian elements via fit.

Reads state vectors from a CCSDS OEM file or stdin, computes a single set
of mean Keplerian elements (at the first epoch) that best matches the OEM arc
(up to 2 hours) by minimizing Cartesian position residuals via least-squares
over J2-propagated mean elements with Brouwer short-period corrections.

Output format (multi-line summary):
    Fitted mean Keplerian elements with diagnostics and propagation accuracy.

Uses common.kepler for the Cartesian-to-Keplerian conversion and
common.oem for OEM parsing.

Keplerian element ordering follows the convention defined in common.kepler:
    - Index 0: a (semi-major axis, m)
    - Index 1: e (eccentricity, dimensionless)
    - Index 2: i (inclination, rad)
    - Index 3: ω (argument of periapsis, rad)
    - Index 4: Ω (right ascension of ascending node, rad)
    - Index 5: θ/M (true anomaly or mean anomaly, rad)

References:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 4.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Algorithm 9.
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.kepler as kepler
import common.mean_kepler as mean_kepler
import common.oem as oem
import common.consts as consts
import common.time_utils as time_utils


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    argument_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Fit a single set of mean Keplerian elements to an OEM arc using "
            "least-squares minimization."
        )
    )
    argument_parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.oem>",
        help=(
            "Input OEM file path. Use '-' or omit to read from stdin " "(default: '-')."
        ),
    )
    argument_parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help=("Output file path (default: '-'). " "Use '-' to print to stdout."),
    )
    argument_parser.add_argument(
        "--mu",
        type=float,
        default=consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
        metavar="<value>",
        dest="mu_m3_s2",
        help=(
            "Gravitational parameter (m³/s²). "
            f"Default: {consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2:.6e} (Earth WGS-84)."
        ),
    )
    argument_parser.add_argument(
        "--fit-span",
        type=float,
        default=2.0,
        metavar="<hours>",
        dest="fit_span_hours",
        help=(
            "Maximum arc span in hours (default: 2.0). "
            "Records beyond this span from the first epoch are excluded."
        ),
    )
    return argument_parser.parse_args()


def read_input_text(source: str) -> str:
    """Read input text from file or stdin.

    Parameters
    ----------
    source : str
        Input file path or '-' for stdin.

    Returns
    -------
    str
        Input text content.

    Raises
    ------
    ValueError
        If input is empty or file cannot be read.
    """
    if source == "-":
        file_content: str = sys.stdin.read()
        if not file_content.strip():
            raise ValueError("No input from stdin")
        return file_content

    try:
        with open(source, "r", encoding="utf-8") as input_file:
            file_content = input_file.read()
    except OSError as error:
        raise ValueError(f"Could not read input file '{source}': {error}") from error

    if not file_content.strip():
        raise ValueError(f"Input file '{source}' is empty")

    return file_content


def parse_dataset(
    input_text: str,
) -> list[tuple[float, np.ndarray]]:
    """Parse input text into (timestamp, state_vector) records.

    First attempts to parse as a CCSDS OEM file using common.oem.read_oem.
    Falls back to line-by-line parsing for simple state-vector files.

    OEM parsers now return state vectors in SI units (m and m/s).

    Parameters
    ----------
    input_text : str
        Input text containing state vectors.

    Returns
    -------
    list[tuple[float, np.ndarray]]
        List of (timestamp, state_vector (6,)) tuples.
        Timestamp is Unix timestamp (seconds since epoch).
        State vector contains [x, y, z, vx, vy, vz] in meters and m/s (SI units).

    Raises
    ------
    ValueError
        If no valid state vectors are found.
    """
    # Try CCSDS OEM format first
    try:
        _, _, states = oem.read_oem(io.StringIO(input_text))
        if states:
            state_records: list[tuple[float, np.ndarray]] = []
            for timestamp in sorted(states):
                state_vector_m: np.ndarray = states[timestamp]
                if len(state_vector_m) < 6:
                    continue
                # State vectors are already in m and m/s (SI units)
                state_records.append((timestamp, state_vector_m))
            if len(state_records) >= 1:
                return state_records
    except Exception:
        pass

    # Fall back to line-by-line parsing
    state_records = []
    for raw_line in input_text.splitlines():
        parsed_line: tuple[float, np.ndarray] | None = oem.parse_oem_state_line(
            raw_line
        )
        if parsed_line is not None:
            timestamp: float = parsed_line[0]
            state_vector_m: np.ndarray = parsed_line[1]
            # State vectors are already in m and m/s (SI units)
            state_records.append((timestamp, state_vector_m))

    if len(state_records) < 1:
        raise ValueError(
            "No valid state vectors found in input. "
            "Expected OEM format or whitespace-separated "
            "ISO8601 x y z vx vy vz lines."
        )

    return state_records


def format_keplerian_line(
    epoch: datetime,
    keplerian_elements: np.ndarray,
    output_units: str,
) -> str:
    """Format a single Keplerian element record as a text line.

    Converts internal SI units (meters, radians) to display units (km, degrees)
    when output_units is 'km-deg'.

    Parameters
    ----------
    epoch : datetime
        Epoch datetime.
    keplerian_elements : np.ndarray
        Keplerian elements (6,): [a, e, i, omega, RAAN, theta].
        Semi-major axis in meters, angles in radians (SI units).
        Element ordering follows kepler module index constants.
    output_units : str
        Output units: 'km-deg' or 'm-rad'.

    Returns
    -------
    str
        Formatted line with units as specified by output_units.
    """
    epoch_str: str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)

    semi_major_axis_m: float = keplerian_elements[kepler.SEMI_MAJOR_AXIS_INDEX]
    eccentricity: float = keplerian_elements[kepler.ECCENTRICITY_INDEX]
    inclination_rad: float = keplerian_elements[kepler.INCLINATION_INDEX]
    argument_of_periapsis_rad: float = keplerian_elements[
        kepler.ARGUMENT_OF_PERIAPSIS_INDEX
    ]
    raan_rad: float = keplerian_elements[kepler.RAAN_INDEX]
    true_anomaly_rad: float = keplerian_elements[kepler.TRUE_ANOMALY_INDEX]

    if output_units == "km-deg":
        # Convert from SI units (m, rad) to display units (km, deg)
        semi_major_axis_km: float = semi_major_axis_m / 1000.0
        inclination_deg: float = np.degrees(inclination_rad)
        argument_of_periapsis_deg: float = np.degrees(argument_of_periapsis_rad)
        raan_deg: float = np.degrees(raan_rad)
        true_anomaly_deg: float = np.degrees(true_anomaly_rad)
        return (
            f"{epoch_str}"
            f"  {semi_major_axis_km:16.6f}"
            f"  {eccentricity:14.10f}"
            f"  {inclination_deg:12.6f}"
            f"  {argument_of_periapsis_deg:12.6f}"
            f"  {raan_deg:12.6f}"
            f"  {true_anomaly_deg:12.6f}"
        )
    else:
        # Output in SI units (m, rad)
        return (
            f"{epoch_str}"
            f"  {semi_major_axis_m:16.6f}"
            f"  {eccentricity:14.10f}"
            f"  {inclination_rad:14.10f}"
            f"  {argument_of_periapsis_rad:14.10f}"
            f"  {raan_rad:14.10f}"
            f"  {true_anomaly_rad:14.10f}"
        )


# ===================================================================
# Fit: J2 secular propagation of mean elements
# ===================================================================


def compute_fit_residuals(
    mean_elements_at_epoch: np.ndarray,
    time_offsets_s: np.ndarray,
    target_positions_m: np.ndarray,
    mu_m3_s2: float,
) -> np.ndarray:
    """Compute position residuals for all sample times.

    All computations use SI units (meters, seconds, radians).

    Parameters
    ----------
    mean_elements_at_epoch : np.ndarray
        Mean Keplerian elements at epoch (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in meters, angles in radians (SI units).
        Element ordering follows kepler module index constants.
    time_offsets_s : np.ndarray
        Time offsets from epoch in seconds, shape (N,).
    target_positions_m : np.ndarray
        Target positions in meters, shape (N, 3).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).

    Returns
    -------
    np.ndarray
        Position residuals, shape (N*3,) in meters.
    """
    residuals: np.ndarray = np.zeros(len(time_offsets_s) * 3)
    for sample_index, elapsed_time_s in enumerate(time_offsets_s):
        propagated_mean_elements: np.ndarray = mean_kepler.propagate_mean_j2(
            mean_elements_at_epoch, elapsed_time_s, mu_m3_s2
        )
        try:
            predicted_state: np.ndarray = mean_kepler.mean_elements_to_cartesian(
                propagated_mean_elements, mu_m3_s2
            )
        except (ValueError, RuntimeError):
            # If conversion fails, assign large residual
            residuals[sample_index * 3 : sample_index * 3 + 3] = 1.0e6
            continue
        residuals[sample_index * 3 : sample_index * 3 + 3] = (
            target_positions_m[sample_index] - predicted_state[:3]
        )
    return residuals


def fit_mean_elements(
    records: list[tuple[float, np.ndarray]],
    mu_m3_s2: float,
    fit_span_s: float = 7200.0,
    max_iterations: int = 50,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Fit a single set of mean Keplerian elements to an OEM arc.

    Uses Gauss-Newton least-squares minimization of Cartesian position
    residuals. The mean elements are propagated using J2 secular rates
    and Brouwer short-period corrections are applied before comparing
    to the OEM states.

    All internal computations use SI units (meters, seconds, radians).

    Parameters
    ----------
    records : list[tuple[float, np.ndarray]]
        List of (timestamp, state_vector (6,)) tuples.
        Timestamp is Unix timestamp (seconds since epoch).
        State vectors contain [x, y, z, vx, vy, vz] in meters and m/s (SI units).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    fit_span_s : float
        Maximum arc span in seconds (default: 7200 = 2 hours).
    max_iterations : int
        Maximum Gauss-Newton iterations.

    Returns
    -------
    tuple[np.ndarray, dict]
        - Fitted mean Keplerian elements at epoch (6,): [a, e, i, omega, RAAN, M].
          Semi-major axis in meters, angles in radians (SI units).
          Element ordering follows kepler module index constants.
        - Dictionary with fit diagnostics: 'rms_position_m', 'iterations', 'n_records'.
    """
    # Filter records to fit span
    reference_timestamp: float = records[0][0]
    filtered_records: list[tuple[float, np.ndarray]] = [
        (timestamp, state_vector)
        for timestamp, state_vector in records
        if (timestamp - reference_timestamp) <= fit_span_s
    ]

    num_records: int = len(filtered_records)
    time_offsets_s: np.ndarray = np.array(
        [(timestamp - reference_timestamp) for timestamp, _ in filtered_records]
    )
    target_positions_m: np.ndarray = np.array(
        [state_vector[:3] for _, state_vector in filtered_records]
    )  # (N, 3) in meters

    # Initial guess: mean elements from the first osculating state (data is already in m, m/s SI units)
    first_state_m: np.ndarray = filtered_records[0][1]
    osculating_elements_at_first_epoch: np.ndarray = kepler.cartesian_to_keplerian(
        first_state_m, mu_m3_s2
    )
    current_mean_elements: np.ndarray = mean_kepler.osculating_to_mean_keplerian(
        osculating_elements_at_first_epoch
    )

    # Finite-difference step sizes for numerical Jacobian (parameters: [a, e, i, omega, RAAN, M])
    finite_difference_steps: np.ndarray = np.array(
        [
            1.0,  # a (m)
            1.0e-7,  # e (dimensionless)
            1.0e-6,  # i (rad)
            1.0e-5,  # omega (rad)
            1.0e-5,  # RAAN (rad)
            1.0e-5,  # M (rad)
        ]
    )

    best_mean_elements: np.ndarray = current_mean_elements.copy()
    best_rms_error: float = np.inf
    previous_rms_error: float = np.inf
    final_iteration_count: int = 0

    for iteration in range(max_iterations):
        residuals: np.ndarray = compute_fit_residuals(
            current_mean_elements, time_offsets_s, target_positions_m, mu_m3_s2
        )
        rms_error: float = np.sqrt(np.mean(residuals**2))

        if rms_error < best_rms_error:
            best_rms_error = rms_error
            best_mean_elements = current_mean_elements.copy()

        # Check convergence
        if (
            iteration > 0
            and abs(previous_rms_error - rms_error) / max(rms_error, 1.0) < 1.0e-12
        ):
            final_iteration_count = iteration
            break
        previous_rms_error = rms_error
        final_iteration_count = iteration

        # Build Jacobian via finite differences
        num_parameters: int = 6
        num_residuals: int = len(residuals)
        jacobian_matrix: np.ndarray = np.zeros((num_residuals, num_parameters))

        for parameter_index in range(num_parameters):
            perturbed_elements: np.ndarray = current_mean_elements.copy()
            perturbed_elements[parameter_index] += finite_difference_steps[
                parameter_index
            ]
            perturbed_residuals: np.ndarray = compute_fit_residuals(
                perturbed_elements, time_offsets_s, target_positions_m, mu_m3_s2
            )
            jacobian_matrix[:, parameter_index] = (
                perturbed_residuals - residuals
            ) / finite_difference_steps[parameter_index]

        # Solve normal equations: Jᵀ J dx = Jᵀ r
        normal_matrix: np.ndarray = jacobian_matrix.T @ jacobian_matrix
        gradient_vector: np.ndarray = jacobian_matrix.T @ residuals

        # Regularize to avoid singular matrix
        normal_matrix_diagonal: np.ndarray = np.diag(normal_matrix).copy()
        normal_matrix_diagonal[normal_matrix_diagonal < 1.0e-20] = 1.0e-20
        normal_matrix += np.diag(1.0e-8 * normal_matrix_diagonal)

        try:
            parameter_correction: np.ndarray = np.linalg.solve(
                normal_matrix, gradient_vector
            )
        except np.linalg.LinAlgError:
            break

        # Line search: try full step, then halve
        line_search_scale: float = 1.0
        step_improved: bool = False
        for _ in range(10):
            trial_elements: np.ndarray = (
                current_mean_elements - line_search_scale * parameter_correction
            )
            # Clamp eccentricity to valid range
            trial_elements[kepler.ECCENTRICITY_INDEX] = np.clip(
                trial_elements[kepler.ECCENTRICITY_INDEX], 1.0e-8, 0.9999
            )
            # Clamp semi-major axis (must be positive, minimum 6000 km for Earth orbits)
            trial_elements[kepler.SEMI_MAJOR_AXIS_INDEX] = max(
                trial_elements[kepler.SEMI_MAJOR_AXIS_INDEX], 6.0e6
            )
            trial_residuals: np.ndarray = compute_fit_residuals(
                trial_elements, time_offsets_s, target_positions_m, mu_m3_s2
            )
            trial_rms_error: float = np.sqrt(np.mean(trial_residuals**2))
            if trial_rms_error < rms_error:
                current_mean_elements = trial_elements
                step_improved = True
                break
            line_search_scale *= 0.5

        if not step_improved:
            break

    # Final RMS with best elements
    final_residuals: np.ndarray = compute_fit_residuals(
        best_mean_elements, time_offsets_s, target_positions_m, mu_m3_s2
    )
    final_rms_error: float = np.sqrt(np.mean(final_residuals**2))

    diagnostics: dict[str, float | int] = {
        "rms_position_m": final_rms_error,
        "iterations": final_iteration_count + 1,
        "n_records": num_records,
        "span_s": float(time_offsets_s[-1]) if len(time_offsets_s) > 0 else 0.0,
    }

    return best_mean_elements, diagnostics


def compute_all_differences(
    fitted_mean_elements: np.ndarray,
    records: list[tuple[float, np.ndarray]],
    mu_m3_s2: float,
    fit_span_s: float,
) -> dict[str, float | int]:
    """Compare every OEM state in the fit span against the Kepler-propagated state.

    Internal computations use SI units (meters, seconds, radians).
    Output statistics are converted to km and km/s for display.

    Parameters
    ----------
    fitted_mean_elements : np.ndarray
        Fitted mean Keplerian elements at epoch (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in meters, angles in radians (SI units).
        Element ordering follows kepler module index constants.
    records : list[tuple[float, np.ndarray]]
        List of (timestamp, state_vector (6,)) tuples.
        Timestamp is Unix timestamp (seconds since epoch).
        State vectors contain [x, y, z, vx, vy, vz] in meters and m/s (SI units).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    fit_span_s : float
        Maximum arc span in seconds.

    Returns
    -------
    dict
        Summary statistics with keys (all in km and km/s for display):
        - 'n_compared': number of states compared
        - 'min_pos_km': minimum position error (km)
        - 'max_pos_km': maximum position error (km)
        - 'avg_pos_km': average position error (km)
        - 'min_vel_km_s': minimum velocity error (km/s)
        - 'max_vel_km_s': maximum velocity error (km/s)
        - 'avg_vel_km_s': average velocity error (km/s)
    """
    reference_timestamp: float = records[0][0]

    # Filter records to fit span
    filtered_records: list[tuple[float, np.ndarray]] = [
        (timestamp, state_vector)
        for timestamp, state_vector in records
        if (timestamp - reference_timestamp) <= fit_span_s
    ]

    position_errors_km: list[float] = []
    velocity_errors_km_s: list[float] = []

    for record_timestamp, record_state_m in filtered_records:
        elapsed_time_s: float = record_timestamp - reference_timestamp

        propagated_mean_elements: np.ndarray = mean_kepler.propagate_mean_j2(
            fitted_mean_elements, elapsed_time_s, mu_m3_s2
        )
        try:
            predicted_state_m: np.ndarray = mean_kepler.mean_elements_to_cartesian(
                propagated_mean_elements, mu_m3_s2
            )
        except (ValueError, RuntimeError):
            continue

        # Data is already in m, m/s (SI units)
        oem_position_m: np.ndarray = record_state_m[:3]
        oem_velocity_m_s: np.ndarray = record_state_m[3:6]

        # Compute errors in SI units (meters, m/s)
        position_error_magnitude: float = float(
            np.linalg.norm(oem_position_m - predicted_state_m[:3])
        )
        velocity_error_magnitude: float = float(
            np.linalg.norm(oem_velocity_m_s - predicted_state_m[3:6])
        )

        # Convert errors to km and km/s for display
        position_errors_km.append(position_error_magnitude / 1000.0)
        velocity_errors_km_s.append(velocity_error_magnitude / 1000.0)

    position_error_array: np.ndarray = (
        np.array(position_errors_km) if position_errors_km else np.array([0.0])
    )
    velocity_error_array: np.ndarray = (
        np.array(velocity_errors_km_s) if velocity_errors_km_s else np.array([0.0])
    )

    return {
        "n_compared": len(position_errors_km),
        "min_pos_km": float(position_error_array.min()),
        "max_pos_km": float(position_error_array.max()),
        "avg_pos_km": float(position_error_array.mean()),
        "min_vel_km_s": float(velocity_error_array.min()),
        "max_vel_km_s": float(velocity_error_array.max()),
        "avg_vel_km_s": float(velocity_error_array.mean()),
    }


def format_fit_output(
    epoch: datetime,
    fitted_mean_elements: np.ndarray,
    diagnostics: dict,
    output_units: str,
    difference_summary: dict | None = None,
) -> str:
    """Format the fit output as a human-readable summary.

    Converts internal SI units (meters, radians) to display units (km, degrees)
    when output_units is 'km-deg'.

    Parameters
    ----------
    epoch : datetime
        Reference epoch.
    fitted_mean_elements : np.ndarray
        Fitted mean Keplerian elements (6,): [a, e, i, omega, RAAN, M].
        Semi-major axis in meters, angles in radians (SI units).
        Element ordering follows kepler module index constants.
    diagnostics : dict
        Fit diagnostics dictionary.
    output_units : str
        Output units: 'km-deg' or 'm-rad'.
    difference_summary : dict | None
        Difference summary from :func:`compute_all_differences`.

    Returns
    -------
    str
        Multi-line formatted output with units as specified by output_units.
    """
    output_lines: list[str] = []
    epoch_str: str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)

    semi_major_axis_m: float = fitted_mean_elements[kepler.SEMI_MAJOR_AXIS_INDEX]
    eccentricity: float = fitted_mean_elements[kepler.ECCENTRICITY_INDEX]
    inclination_rad: float = fitted_mean_elements[kepler.INCLINATION_INDEX]
    argument_of_periapsis_rad: float = fitted_mean_elements[
        kepler.ARGUMENT_OF_PERIAPSIS_INDEX
    ]
    raan_rad: float = fitted_mean_elements[kepler.RAAN_INDEX]
    mean_anomaly_rad: float = fitted_mean_elements[kepler.MEAN_ANOMALY_INDEX]

    # Compute RAAN rate for display
    raan_rate_rad_s: float = mean_kepler.compute_raan_rate(
        fitted_mean_elements, consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    )

    output_lines.append(
        "Fitted mean Keplerian elements (J2 secular + Brouwer short-period):"
    )
    output_lines.append(f"  epoch:              {epoch_str}")
    output_lines.append(f"  records used:       {diagnostics['n_records']}")
    output_lines.append(f"  arc span:           {diagnostics['span_s']:.1f} s")
    output_lines.append(f"  iterations:         {diagnostics['iterations']}")
    output_lines.append(
        f"  RMS position error: {diagnostics['rms_position_m'] / 1000.0:.6f} km"
    )
    output_lines.append("")

    if output_units == "km-deg":
        output_lines.append("  Elements (km, degrees):")
        output_lines.append(
            f"    semi-major axis:       {semi_major_axis_m / 1000.0:.6f} km"
        )
        output_lines.append(f"    eccentricity:          {eccentricity:.10f}")
        output_lines.append(
            f"    inclination:           {np.degrees(inclination_rad):.6f} deg"
        )
        output_lines.append(
            f"    arg of periapsis:      {np.degrees(argument_of_periapsis_rad):.6f} deg"
        )
        output_lines.append(
            f"    RAAN:                  {np.degrees(raan_rad):.6f} deg"
        )
        output_lines.append(
            f"    mean anomaly:          {np.degrees(mean_anomaly_rad):.6f} deg"
        )
    else:
        output_lines.append("  Elements (m, radians):")
        output_lines.append(f"    semi-major axis:       {semi_major_axis_m:.6f} m")
        output_lines.append(f"    eccentricity:          {eccentricity:.10f}")
        output_lines.append(f"    inclination:           {inclination_rad:.10f} rad")
        output_lines.append(
            f"    arg of periapsis:      {argument_of_periapsis_rad:.10f} rad"
        )
        output_lines.append(f"    RAAN:                  {raan_rad:.10f} rad")
        output_lines.append(f"    mean anomaly:          {mean_anomaly_rad:.10f} rad")

    # Compute and display derived quantities
    mean_motion_rev_day: float = kepler.semi_major_axis_to_mean_motion(
        semi_major_axis_m
    )
    mean_motion_rad_s: float = mean_motion_rev_day * 2.0 * np.pi / 86400.0
    output_lines.append("")
    output_lines.append("  Derived quantities:")
    output_lines.append(
        f"    mean motion:           {mean_motion_rev_day:.10f} rev/day"
    )
    output_lines.append(
        f"    orbital period:        {2.0 * np.pi / mean_motion_rad_s:.3f} s"
    )
    output_lines.append(f"    RAAN rate (dΩ/dt):     {raan_rate_rad_s:.10e} rad/s")
    output_lines.append(
        f"    RAAN rate (dΩ/dt):     {np.degrees(raan_rate_rad_s) * 86400.0:.6f} deg/day"
    )

    # Propagation accuracy summary
    if difference_summary and difference_summary["n_compared"] > 0:
        output_lines.append("")
        output_lines.append(
            f"  Propagation accuracy (OEM vs Kepler, {difference_summary['n_compared']} states compared):"
        )
        output_lines.append(
            f"    position |Δr|:  "
            f"min = {difference_summary['min_pos_km']:.6f} km   "
            f"max = {difference_summary['max_pos_km']:.6f} km   "
            f"avg = {difference_summary['avg_pos_km']:.6f} km"
        )
        output_lines.append(
            f"    velocity |Δv|:  "
            f"min = {difference_summary['min_vel_km_s']:.9f} km/s   "
            f"max = {difference_summary['max_vel_km_s']:.9f} km/s   "
            f"avg = {difference_summary['avg_vel_km_s']:.9f} km/s"
        )

    return "\n".join(output_lines)


def main() -> None:
    """Execute the OEM-to-Keplerian conversion workflow.

    Fits a single set of mean Keplerian elements to the OEM arc using
    least-squares minimization.

    Parses CLI arguments, reads input state vectors, and writes the results
    to the configured output.
    """
    args: argparse.Namespace = parse_arguments()

    try:
        input_text: str = read_input_text(args.input)
        records: list[tuple[float, np.ndarray]] = parse_dataset(input_text)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    # Compute a single best-fit mean element set
    if len(records) < 2:
        print("Error: At least 2 state vectors are required", file=sys.stderr)
        sys.exit(1)

    # Convert fit span from hours to seconds
    fit_span_s: float = args.fit_span_hours * 3600.0

    fitted_mean_elements: np.ndarray
    fit_diagnostics: dict[str, float | int]
    # All internal computations use SI units (meters, seconds, radians)
    fitted_mean_elements, fit_diagnostics = fit_mean_elements(
        records, args.mu_m3_s2, fit_span_s=fit_span_s
    )
    difference_summary: dict[str, float | int] = compute_all_differences(
        fitted_mean_elements, records, args.mu_m3_s2, fit_span_s
    )
    # Convert first timestamp to datetime for output formatting
    first_epoch: datetime = datetime.fromtimestamp(records[0][0], tz=timezone.utc)
    # Output uses km and degrees for display
    output_text: str = format_fit_output(
        first_epoch,
        fitted_mean_elements,
        fit_diagnostics,
        "km-deg",
        difference_summary=difference_summary,
    )
    output_text += "\n"

    if args.output == "-":
        sys.stdout.write(output_text)
    else:
        try:
            with open(args.output, "w", encoding="utf-8") as output_file:
                output_file.write(output_text)
            print(f"Saved fitted mean elements: {args.output}", file=sys.stderr)
        except OSError as error:
            print(f"Error: Could not write output file: {error}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
