#!/usr/bin/env python3
"""Estimate TLE elements from a set of OEM-like Cartesian state vectors.

Reads state vectors from a file or stdin, fits mean orbital elements using
least-squares regression and optional Gauss-Newton refinement, and writes
the resulting TLE to a file or stdout.
"""

from __future__ import annotations

import sys
import warnings

import numpy as np

import common.common as common
import common.tle as tle
import oem_to_tle.constants as constants
import oem_to_tle.estimation as estimation
import oem_to_tle.io_utils as io_utils
import oem_to_tle.models as models
import oem_to_tle.refinement as refinement
import oem_to_tle.tle_builder as tle_builder

warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings("ignore", module="urllib3")

try:
    from tudatpy.interface import spice
except Exception:
    spice = None

_SPICE_KERNELS_LOADED = False
"""Module-level flag tracking whether SPICE kernels have been loaded."""


def ensure_spice_kernels_loaded() -> bool:
    """Load SPICE kernels once per process.

    Returns
    -------
    bool
        True when kernels are available for subsequent TudatPy calls, False otherwise.
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


def print_summary(
    records: list,
    estimated,
    args,
    keplerian_accuracy: models.KeplerianAccuracy | None = None,
) -> None:
    """Print a summary of the TLE estimation results.

    Parameters
    ----------
    records : list
        List of (epoch, position_km, velocity_km_s) tuples.
    estimated : Estimated
        Estimated TLE elements dataclass.
    args : argparse.Namespace
        Parsed command-line arguments.
    keplerian_accuracy : KeplerianAccuracy | None
        Optional Keplerian accuracy verification results.
    """
    start_epoch = records[0][0]
    end_epoch = records[-1][0]
    span_s = (end_epoch - start_epoch).total_seconds()

    print("Estimated TLE elements from OEM-like dataset:")
    print(f"  records: {len(records)}")
    print(
        f"  epoch range: {common.datetime_to_iso8601(start_epoch)} -> {common.datetime_to_iso8601(end_epoch)}"
    )
    print(f"  span [s]: {span_s:.3f}")
    print(f"  chosen TLE epoch: {common.datetime_to_iso8601(estimated.epoch_datetime)}")
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
    if estimated.state_match_position_error_km is not None:
        print(
            "  state-match-position-error-km: "
            f"{estimated.state_match_position_error_km:.6f}"
        )
        print(
            "  state-match-velocity-error-km-s: "
            f"{estimated.state_match_velocity_error_km_s:.9f}"
        )
        print(
            "  state-match-refinement: "
            f"{'used' if estimated.state_match_refinement_used else 'not-used'}"
        )
        print(
            "  state-match-iterations: "
            f"{estimated.state_match_iterations if estimated.state_match_iterations is not None else 0}"
        )
    print(f"  semi-major-axis-km: {estimated.semi_major_axis_km:.6f}")
    print(
        "  d(mean-motion)/dt [rev/day^2] (fit): "
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
            f"    semi-major-axis error:    {keplerian_accuracy.semi_major_axis_error_km:+.6f} km"
            f"  ({keplerian_accuracy.semi_major_axis_error_m:+.3f} m)"
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
    args = io_utils.parse_arguments()

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
        input_text: str = io_utils.read_input_text(args.input)
        records: list = io_utils.parse_dataset(input_text)
        if args.refinement == "keplerian":
            estimated: models.Estimated = estimation.estimate_tle_fields(
                records, use_state_match=True
            )
            estimated = refinement.refine_estimated_fields_keplerian_match(
                args, estimated, records
            )
        elif args.refinement == "cartesian":
            estimated: models.Estimated = estimation.estimate_tle_fields(
                records, use_state_match=True
            )
            target_state_km_km_s: np.ndarray = np.concatenate(  # (6,) target state
                [records[0][1], records[0][2]]  # (3,) + (3,) -> (6,)
            )
            estimated = refinement.refine_estimated_fields_to_match_epoch_state(
                args, estimated, target_state_km_km_s
            )
        else:
            # refinement == "none"
            estimated: models.Estimated = estimation.estimate_tle_fields(
                records, use_state_match=False
            )
        estimated = estimation.estimate_bstar_from_arc(args, estimated, records)
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)

    # Verify accuracy using osculating Keplerian elements (common.kepler)
    keplerian_accuracy: models.KeplerianAccuracy | None = (
        estimation.verify_accuracy_keplerian(args, estimated, records)
    )

    print_summary(records, estimated, args, keplerian_accuracy=keplerian_accuracy)

    tle_data: tle.Tle = tle_builder.build_tle_data(args, estimated)

    if args.output == "-":
        tle.write_tle(sys.stdout, tle_data)
    else:
        tle.write_tle(args.output, tle_data)
        print(f"Saved TLE file: {args.output}")


if __name__ == "__main__":
    main()
