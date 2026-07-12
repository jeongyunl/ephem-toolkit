#!/usr/bin/env python3
"""Estimate TLE elements from a set of OEM-like Cartesian state vectors.

Reads state vectors from a file or stdin, fits mean orbital elements using
least-squares regression and optional Gauss-Newton refinement, and writes
the resulting TLE to a file or stdout.

Usage:
    python3 oem_to_tle.py [options] <input_file>
    cat states.txt | python3 oem_to_tle.py [options] -
"""

from __future__ import annotations

import io
import sys
import warnings
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from tudatpy.interface import spice

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.oem as oem
import common.time_utils as time_utils
import common.tle as tle
import oem_to_tle.constants as constants
import oem_to_tle.estimation as estimation
import oem_to_tle.parse_cli_args as parse_cli_args
import oem_to_tle.models as models
import oem_to_tle.refinement as refinement
import oem_to_tle.tle_builder as tle_builder

warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings("ignore", module="urllib3")


def load_spice_kernels() -> None:
    """Load required SPICE kernels for propagation support.

    Kernels are loaded from Tudat's managed kernel directory returned by
    ``common.common.get_spice_kernel_path()``.

    Returns
    -------
    None
        This function mutates the global SPICE kernel pool.
    """

    spice_kernel_files = [
        "naif0012.tls",  # Leap seconds kernel
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(common.get_spice_kernel_path() + "/" + kernel_file)


def print_summary(
    states: list[tuple[float, np.ndarray]],
    estimated: models.Estimated,
    args: Namespace,
    keplerian_accuracy: models.KeplerianAccuracy | None = None,
) -> None:
    """Print a summary of the TLE estimation results.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        List of (epoch_timestamp, state_vector_m) tuples where epoch_timestamp
        is a POSIX float (seconds since 1970-01-01 UTC) and state_vector_m is (6,).
    estimated : models.Estimated
        Estimated TLE elements dataclass.
    args : Namespace
        Parsed command-line arguments.
    keplerian_accuracy : models.KeplerianAccuracy | None
        Optional Keplerian accuracy verification results.
    """
    start_ts: float = states[0][0]
    end_ts: float = states[-1][0]
    span_s: float = end_ts - start_ts
    start_epoch: datetime = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end_epoch: datetime = datetime.fromtimestamp(end_ts, tz=timezone.utc)

    print("Estimated TLE elements from OEM-like dataset:")
    print(f"  records: {len(states)}")
    print(
        f"  epoch range: {time_utils.datetime_to_iso8601(start_epoch)} -> {time_utils.datetime_to_iso8601(end_epoch)}"
    )
    print(f"  span [s]: {span_s:.3f}")
    print(
        f"  chosen TLE epoch: {time_utils.datetime_to_iso8601(estimated.epoch_datetime)}"
    )
    print(f"  epoch-year: {estimated.epoch_year}")
    print(f"  epoch-day: {estimated.epoch_day:.8f}")
    print(f"  inclination-deg: {estimated.inclination_deg:.6f}")
    print(
        "  inclination-deg (osculating at epoch): "
        f"{estimated.inclination_deg_osculating_at_epoch:.6f}"
    )
    print(f"  raan-deg: {estimated.raan_deg:.6f}")
    print(
        "  raan-deg (osculating at epoch): "
        f"{estimated.raan_deg_osculating_at_epoch:.6f}"
    )
    print(f"  eccentricity: {estimated.eccentricity:.9f}")
    print(f"  arg-perigee-deg: {estimated.arg_perigee_deg:.6f}")
    print(
        "  arg-perigee-deg (osculating at epoch): "
        f"{estimated.arg_perigee_deg_osculating_at_epoch:.6f}"
    )
    print(f"  mean-anomaly-deg: {estimated.mean_anomaly_deg:.6f}")
    print(
        "  mean-anomaly-deg (osculating at epoch): "
        f"{estimated.mean_anomaly_deg_osculating_at_epoch:.6f}"
    )
    print(f"  mean-motion-rev-per-day: {estimated.mean_motion_rev_per_day:.10f}")
    print(
        "  mean-motion-rev-per-day (regression at epoch): "
        f"{estimated.mean_motion_rev_per_day_regression_at_epoch:.10f}"
    )
    print(
        "  mean-arg-latitude-rate-rev-per-day: "
        f"{estimated.mean_argument_latitude_rate_rev_per_day:.10f}"
    )
    print(
        "  mean-motion-rev-per-day (osculating at epoch): "
        f"{estimated.mean_motion_rev_per_day_osculating_at_epoch:.10f}"
    )
    print(f"  phase-match-count: {estimated.phase_match_count}")
    print(f"  phase-match-weight: {estimated.phase_match_weight:.6f}")
    if estimated.state_match_position_error_m is not None:
        print(
            "  state-match-position-error-m: "
            f"{estimated.state_match_position_error_m:.3f}"
        )
        print(
            "  state-match-velocity-error-m-s: "
            f"{estimated.state_match_velocity_error_m_s:.6f}"
        )
        print(
            "  state-match-refinement: "
            f"{'used' if estimated.state_match_refinement_used else 'not-used'}"
        )
        print(
            "  state-match-iterations: "
            f"{estimated.state_match_iterations if estimated.state_match_iterations is not None else 0}"
        )
    print(f"  semi-major-axis-m: {estimated.semi_major_axis_m:.3f}")
    print(
        "  d(mean-motion)/dt [rev/day²] (fit): "
        f"{estimated.dataset_slope_rev_per_day2:.12f}"
    )
    print(
        "  mean-motion-first-derivative (TLE field): "
        f"{estimated.mean_motion_first_derivative:.12f}"
    )
    if (
        abs(estimated.mean_motion_first_derivative_raw)
        > constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE
    ):
        print(
            "  note: first derivative was clamped to TLE field range "
            f"[-{constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE:.8f}, {constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE:.8f}]"
        )
    print(f"  bstar: {estimated.bstar if estimated.bstar is not None else args.bstar}")
    if estimated.bstar_source is not None:
        print(f"  bstar-source: {estimated.bstar_source}")
    if estimated.bstar_fit_score is not None:
        print(f"  bstar-fit-score: {estimated.bstar_fit_score:.9f}")
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
            f"    semi-major-axis error:    {keplerian_accuracy.semi_major_axis_error_m:+.3f} m"
        )
        print(
            f"    eccentricity error:       {keplerian_accuracy.eccentricity_error:+.10f}"
        )
        print(
            f"    inclination error:        {keplerian_accuracy.inclination_error_deg:+.6f} deg"
        )
        print(
            f"    RAAN error:               {keplerian_accuracy.raan_error_deg:+.6f} deg"
        )
        print(
            f"    arg-perigee error:        {keplerian_accuracy.arg_perigee_error_deg:+.6f} deg"
        )
        print(
            f"    true-anomaly error:       {keplerian_accuracy.true_anomaly_error_deg:+.6f} deg"
        )
        print(
            f"    arg-latitude (ω+θ) error: {keplerian_accuracy.arg_latitude_error_deg:+.6f} deg"
        )

    print()


def main() -> None:
    """Execute the TLE estimation workflow.

    Parses CLI arguments, reads input state vectors, estimates TLE elements
    using the selected refinement method, verifies accuracy, prints a summary,
    and writes the resulting TLE to the configured output. Exits with status 1
    on validation or input errors.
    """
    args = parse_cli_args.parse_cli_arguments()

    # SPICE kernels are initialized once here and reused by all evaluations.
    load_spice_kernels()

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
        # Read OEM data using CcsdsOem.read() directly
        # CcsdsOem.read() handles both full OEM files and raw state lists

        # Handle stdin vs file input
        if args.input == "-":
            input_text: str = sys.stdin.read()
            if not input_text.strip():
                raise ValueError("No input from stdin")
            source = io.StringIO(input_text)
        else:
            source = args.input

        # Read OEM data (handles both OEM format and raw state lists)
        oem_data = oem.CcsdsOem.read(source)

        # Validate state records
        if not oem_data.states or len(oem_data.states) < 2:
            raise ValueError(
                "Need at least 2 OEM-like state vectors to estimate TLE trend"
            )

        # Use states directly (already in correct format: list of (timestamp, state_vector) tuples)
        oem_states: list[tuple[float, np.ndarray]] = oem_data.states

        if args.refinement == "keplerian":
            estimated: models.Estimated = estimation.estimate_tle_fields(
                oem_states, use_state_match=True
            )
            estimated = refinement.refine_estimated_fields_keplerian_match(
                args, estimated, oem_states
            )
        elif args.refinement == "cartesian":
            estimated: models.Estimated = estimation.estimate_tle_fields(
                oem_states, use_state_match=True
            )
            target_state_m_m_s: np.ndarray = oem_states[0][1]  # (6,) target state
            estimated = refinement.refine_estimated_fields_to_match_epoch_state(
                args, estimated, target_state_m_m_s
            )
        else:
            # refinement == "none"
            estimated: models.Estimated = estimation.estimate_tle_fields(
                oem_states, use_state_match=False
            )
        estimated = estimation.estimate_bstar_from_arc(args, estimated, oem_states)
    except (ValueError, FileNotFoundError, OSError) as error:
        print(f"Error: {error}")
        sys.exit(1)

    # Verify accuracy using osculating Keplerian elements (common.kepler)
    keplerian_accuracy: models.KeplerianAccuracy | None = (
        estimation.verify_accuracy_keplerian(args, estimated, oem_states)
    )

    print_summary(oem_states, estimated, args, keplerian_accuracy=keplerian_accuracy)

    tle_data: tle.Tle = tle_builder.build_tle_data(args, estimated)

    if args.output == "-":
        tle.write_tle(sys.stdout, tle_data)
    else:
        tle.write_tle(args.output, tle_data)
        print(f"Saved TLE file: {args.output}")


if __name__ == "__main__":
    main()
