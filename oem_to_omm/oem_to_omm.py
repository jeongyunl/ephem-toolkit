#!/usr/bin/env python3
"""Convert OEM state vectors to osculating Keplerian elements or OMM.

Supports three modes:

--kepler mode:
  Fits osculating Keplerian elements to the first 2 hours of OEM states
  using two-body (Kepler) propagation. The result fits the initial state
  exactly and minimizes position residuals over the fit arc.

--mean-kepler mode:
  Fits mean Keplerian elements to the first 2 hours of OEM states using
  J2 secular propagation. The result fits the initial state exactly and
  minimizes position residuals over the fit arc.

--tle mode:
  Fits TLE mean elements (SGP4-compatible) to the OEM states. Creates an
  OMM with MEAN_ELEMENT_THEORY=SGP4 and includes TLE-related parameters
  (BSTAR, MEAN_MOTION_DOT, etc.). The output OMM can be converted to a
  standard TLE format per CCSDS 502.0-B-3 (2023-04).

Algorithm overview (--kepler mode):
  - The epoch position r₀ is fixed to the first OEM position.
  - The epoch velocity v₀ is estimated via a Gauss-Newton least-squares
    minimizer that minimizes position residuals ‖r_OEM(tᵢ) - r_Kepler(tᵢ)‖
    over the fit arc.
  - A numerical (forward-difference) Jacobian ∂residuals/∂v₀ is computed
    at each iteration.
  - Levenberg-Marquardt-style diagonal damping stabilizes the normal
    equations, and a backtracking line search with physical feasibility
    guards (eccentricity < 1, semi-major axis > 6000 km) ensures
    convergence to a physically meaningful orbit.

Usage:
    python3 oem_to_omm.py --kepler <input.oem>
    python3 oem_to_omm.py --mean-kepler <input.oem>
    python3 oem_to_omm.py --tle <input.oem>
    python3 oem_to_omm.py --tle - < input.oem
"""

from __future__ import annotations

import argparse
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn, TextIO

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.consts as consts
import common.convert_tle as convert_tle
import common.kepler as kepler
import common.mean_kepler as mean_kepler
import common.oem as oem
import common.omm as omm
import common.time_utils as time_utils
import common.tle as tle

import oem_to_omm.fit_common as fit_common
import oem_to_omm.fit_mean_kepler as fit_mean_kepler
import oem_to_omm.fit_osculating_kepler as fit_osculating_kepler
import oem_to_omm.fit_tle_main as fit_tle

FIT_SPAN_S: float = 7200.0
"""Default fit span: 2 hours in seconds."""


# ===================================================================
# Reporting
# ===================================================================


def report_results(
    output_text: str,
    dest: TextIO | str | Path,
    verbose: bool = False,
) -> None:
    """Report results to stdout, file, or stderr.

    Handles all output operations including writing to files or stdout,
    and optional verbose status messages to stderr.

    Parameters
    ----------
    output_text : str
        Formatted output text to write.
    dest : TextIO | str | Path
        Output destination. Use "-" for stdout, a file path, or a TextIO stream.
    verbose : bool
        If True, print status messages to stderr.
    """
    if dest == "-":
        print(output_text)
    elif isinstance(dest, (str, Path)):
        output_path = Path(dest)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    else:
        # Handle TextIO stream
        dest.write(output_text)


def report_error(message: str, exit_code: int = 1) -> NoReturn:
    """Report an error message to stderr and exit.

    Parameters
    ----------
    message : str
        Error message to display.
    exit_code : int
        Exit code (default: 1).
    """
    print(message, file=sys.stderr)
    sys.exit(exit_code)


# ===================================================================
# Main
# ===================================================================


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate conversion mode."""
    parser = argparse.ArgumentParser(
        description="Convert OEM state vectors to Keplerian elements or OMM."
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        help='Path to input CCSDS OEM file (use "-" or omit to read from stdin)',
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help="Save fitted Keplerian elements in OMM format to the specified file. Use '-' to print to stdout.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )
    parser.add_argument(
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
    parser.add_argument(
        "--fit-span",
        type=float,
        default=2.0,
        metavar="<hours>",
        dest="fit_span_hours",
        help="Maximum arc span in hours for --kepler fit (default: 2.0).",
    )
    parser.add_argument(
        "--kepler",
        action="store_true",
        help=(
            "Fit osculating Keplerian elements to the first 2 hours of OEM states "
            "using two-body (Kepler) propagation. The result fits the initial state "
            "exactly and minimizes position residuals over the 2-hour arc."
        ),
    )
    parser.add_argument(
        "--mean-kepler",
        action="store_true",
        dest="mean_kepler",
        help=(
            "Fit mean Keplerian elements to the first 2 hours of OEM states "
            "using J2 secular propagation. The result fits the initial state "
            "exactly and minimizes position residuals over the 2-hour arc."
        ),
    )
    parser.add_argument(
        "--tle",
        action="store_true",
        help=(
            "Fit TLE mean elements (SGP4-compatible) to the OEM states. "
            "Creates an OMM with MEAN_ELEMENT_THEORY=SGP4 and includes "
            "TLE-related parameters (BSTAR, MEAN_MOTION_DOT, etc.). "
            "The output OMM can be converted to a standard TLE format."
        ),
    )

    # Metadata options (aligned with OMM field names)
    parser.add_argument(
        "--object-name",
        metavar="<name>",
        default="",
        help="OBJECT_NAME: Spacecraft name for OMM output.",
    )
    parser.add_argument(
        "--object-id",
        metavar="<YYYY-NNNP>",
        default="",
        dest="object_id",
        help="OBJECT_ID: International designator (e.g., 1998-067A) for OMM output.",
    )
    parser.add_argument(
        "--tle-refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        dest="tle_refinement",
        help=(
            "Refinement method for TLE fitting (used with --tle mode). "
            "'cartesian' (default): minimize SGP4 Cartesian state residual. "
            "'keplerian': minimize osculating Keplerian element residual. "
            "'none': skip refinement entirely."
        ),
    )
    parser.add_argument(
        "--tle-norad-cat-id",
        type=int,
        default=0,
        metavar="<0..99999>",
        dest="tle_norad_cat_id",
        help="NORAD_CAT_ID: NORAD Catalog Number (default: 0, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-classification-type",
        choices=["U", "C", "S"],
        default="U",
        metavar="<U|C|S>",
        dest="tle_classification_type",
        help="CLASSIFICATION_TYPE: U=Unclassified, C=Classified, S=Secret (default: U, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-ephemeris-type",
        type=int,
        default=2,
        metavar="<0..9>",
        dest="tle_ephemeris_type",
        help="EPHEMERIS_TYPE: 0=SGP, 2=SGP4, 4=SGP4-XP, 6=SP (default: 2, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-element-set-no",
        type=int,
        default=999,
        metavar="<0..9999>",
        dest="tle_element_set_no",
        help="ELEMENT_SET_NO: Element set number for this satellite (default: 999, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-rev-at-epoch",
        type=int,
        default=0,
        metavar="<0..99999>",
        dest="tle_rev_at_epoch",
        help="REV_AT_EPOCH: Revolution number at epoch (default: 0, used with --tle mode).",
    )

    args = parser.parse_args()

    # Determine input source: file path or stdin (piped input)
    read_from_stdin: bool = args.oem_file is None or args.oem_file == "-"

    # Read and parse CCSDS OEM ephemeris data
    if read_from_stdin:
        oem_data = oem.CcsdsOem.read(sys.stdin)
    else:
        oem_path = Path(args.oem_file)
        if not oem_path.exists():
            report_error(f"Error: Input file not found: {args.oem_file}")
        oem_data = oem.CcsdsOem.read(oem_path)

    states: list[tuple[float, np.ndarray]] = oem_data.states

    if len(states) < 2:
        report_error("Error: At least 2 state vectors required for fitting.")

    fit_span_s: float = args.fit_span_hours * 3600.0

    # Determine object name: use --object-name if provided, otherwise use OEM metadata
    object_name: str = (
        args.object_name
        if args.object_name
        else (oem_data.meta.object_name or "OBJECT")
    )

    # Determine object_id: use --object-id if provided, otherwise use OEM metadata
    if args.object_id:
        object_id: str = args.object_id
    else:
        object_id: str = oem_data.meta.object_id or "UNKNOWN"

    # --kepler mode: fit osculating Keplerian elements to OEM arc
    if args.kepler:
        if len(states) < 2:
            report_error("Error: At least 2 state vectors required for fitting.")

        fit_span_s: float = args.fit_span_hours * 3600.0

        # Run the Gauss-Newton velocity-only fit (position at epoch is fixed)
        fitted_elements: np.ndarray
        diagnostics: fit_common.FitDiagnostics
        try:
            fitted_elements, diagnostics = fit_osculating_kepler.fit_osculating_kepler(
                states,
                fit_span_s,
                args.mu_m3_s2,
            )
        except Exception as error:
            report_error(f"Error fitting Keplerian elements: {error}")

        # Compute propagation comparison at 10-minute intervals
        comparison: list[fit_common.PropagationComparison] = (
            fit_osculating_kepler.compute_kepler_propagation_comparison(
                fitted_elements, states, args.mu_m3_s2, fit_span_s, interval_s=600.0
            )
        )

        # Format and report output
        first_epoch: datetime = datetime.fromtimestamp(states[0][0], tz=timezone.utc)
        output_text: str = fit_osculating_kepler.format_kepler_output(
            first_epoch, fitted_elements, diagnostics, comparison
        )

        # Report results to stderr in verbose mode when output is stdout
        if args.verbose and args.output == "-":
            print(output_text, file=sys.stderr)
        elif args.verbose:
            report_results(output_text, "-", args.verbose)

        # Save OMM format if requested
        if args.output:
            try:
                omm_obj: omm.CcsdsOmm = omm.keplerian_to_omm(
                    first_epoch,
                    fitted_elements,
                    object_name=object_name,
                    object_id=object_id,
                    mu_m3_s2=args.mu_m3_s2,
                )
                omm_obj.originator = "oem_to_omm"
                # Output to stdout if dest is "-", otherwise to file
                if args.output == "-":
                    omm_obj.to_file(sys.stdout)
                else:
                    omm_obj.to_file(args.output)
                    if args.verbose:
                        print(f"OMM file written to: {args.output}", file=sys.stderr)
            except Exception as error:
                report_error(f"Error writing OMM file: {error}")
        return

    # --mean-kepler mode: fit mean Keplerian elements to OEM arc
    if args.mean_kepler:
        # Run the Gauss-Newton velocity-only fit for mean elements
        fitted_mean_elements: np.ndarray
        diagnostics: fit_common.FitDiagnostics
        try:
            fitted_mean_elements, diagnostics = fit_mean_kepler.fit_mean_kepler(
                states,
                fit_span_s,
                args.mu_m3_s2,
            )
        except Exception as error:
            report_error(f"Error fitting mean Keplerian elements: {error}")

        # Compute propagation comparison at 10-minute intervals
        comparison: list[fit_common.PropagationComparison] = (
            fit_mean_kepler.compute_mean_kepler_propagation_comparison(
                fitted_mean_elements,
                states,
                args.mu_m3_s2,
                fit_span_s,
                interval_s=600.0,
            )
        )

        # Format and report output
        first_epoch: datetime = datetime.fromtimestamp(states[0][0], tz=timezone.utc)
        output_text: str = fit_mean_kepler.format_mean_kepler_output(
            first_epoch, fitted_mean_elements, diagnostics, comparison
        )

        # Report results to stderr in verbose mode when output is stdout
        if args.verbose and args.output == "-":
            print(output_text, file=sys.stderr)
        elif args.verbose:
            report_results(output_text, "-", args.verbose)

        # Save OMM format if requested (convert mean to osculating first)
        if args.output:
            try:

                # Convert mean elements to osculating for OMM output
                osculating_elements: np.ndarray = (
                    mean_kepler.mean_to_osculating_keplerian(fitted_mean_elements)
                )
                omm_obj: omm.CcsdsOmm = omm.keplerian_to_omm(
                    first_epoch,
                    osculating_elements,
                    object_name=object_name,
                    object_id=object_id,
                    mu_m3_s2=args.mu_m3_s2,
                )
                omm_obj.originator = "oem_to_omm"
                # Output to stdout if dest is "-", otherwise to file
                if args.output == "-":
                    omm_obj.to_file(sys.stdout)
                else:
                    omm_obj.to_file(args.output)
                    if args.verbose:
                        print(f"OMM file written to: {args.output}", file=sys.stderr)
            except Exception as error:
                report_error(f"Error writing OMM file: {error}")
        return

    # --tle mode: fit TLE mean elements (SGP4-compatible) to OEM arc
    if args.tle:
        # Validate TLE parameters
        if not (0 <= args.tle_norad_cat_id <= 99999):
            report_error("Error: --norad-cat-id must be in [0, 99999]")
        if not (0 <= args.tle_ephemeris_type <= 9):
            report_error("Error: --ephemeris-type must be in [0, 9]")
        if not (0 <= args.tle_element_set_no <= 9999):
            report_error("Error: --element-set-no must be in [0, 9999]")
        if not (0 <= args.tle_rev_at_epoch <= 99999):
            report_error("Error: --rev-at-epoch must be in [0, 99999]")

        # Run TLE fitting with user-specified refinement method and metadata
        tle_obj: tle.Tle
        diagnostics: fit_common.FitDiagnostics
        try:
            tle_obj, diagnostics = fit_tle.fit_tle(
                states,
                fit_span_s,
                args.tle_refinement,
                args.mu_m3_s2,
                object_name=object_name,
                object_id=object_id,
                norad_cat_id=args.tle_norad_cat_id,
                classification_type=args.tle_classification_type,
                ephemeris_type=args.tle_ephemeris_type,
                element_set_number=args.tle_element_set_no,
                revolution_number_at_epoch=args.tle_rev_at_epoch,
            )
        except Exception as error:
            import traceback

            traceback.print_exc()
            report_error(f"Error fitting TLE elements: {error}")

        # Compute propagation comparison at 10-minute intervals
        comparison: list[fit_common.PropagationComparison] = (
            fit_tle.compute_tle_propagation_comparison(
                tle_obj, states, args.mu_m3_s2, fit_span_s, interval_s=600.0
            )
        )

        # Format and report output
        first_epoch: datetime = datetime.fromtimestamp(states[0][0], tz=timezone.utc)
        output_text: str = fit_tle.format_tle_output(
            first_epoch, tle_obj, diagnostics, comparison
        )

        # Report results to stderr in verbose mode when output is stdout
        if args.verbose and args.output == "-":
            print(output_text, file=sys.stderr)
        elif args.verbose:
            report_results(output_text, "-", args.verbose)

        # Save OMM format with TLE parameters
        if args.output:
            try:
                # Convert TLE to OMM using common library function
                omm_obj: omm.CcsdsOmm = convert_tle.tle_to_omm(
                    tle_obj,
                    creation_date=time_utils.datetime_to_iso8601(
                        datetime.now(timezone.utc), fractional_second_places=3
                    ),
                    originator="oem_to_omm",
                )
                # Add comments
                omm_obj.comments = [
                    "TLE mean elements (SGP4-compatible)",
                    "Compliant with CCSDS 502.0-B-3 (2023-04)",
                ]
                # Output to stdout if dest is "-", otherwise to file
                if args.output == "-":
                    omm_obj.to_file(sys.stdout)
                else:
                    omm_obj.to_file(args.output)
                    if args.verbose:
                        print(f"OMM file written to: {args.output}", file=sys.stderr)
            except Exception as error:
                report_error(f"Error writing OMM file: {error}")
        return

    # No mode selected — currently only --kepler, --mean-kepler, and --tle are implemented
    if read_from_stdin:
        return
    parser.error("Either --kepler, --mean-kepler, or --tle must be provided")


if __name__ == "__main__":
    main()
