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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.consts as consts
import common.convert_tle as convert_tle
import common.kepler as kepler
import common.mean_kepler as mean_kepler
import common.oem as oem
import common.omm as omm
import common.time_utils as time_utils
import common.tle as tle

import fit_common
import fit_mean_kepler
import fit_osculating_kepler
import fit_tle

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

    args = parser.parse_args()

    # Determine input source: file path or stdin (piped input)
    read_from_stdin: bool = args.oem_file is None or args.oem_file == "-"

    # --kepler mode: fit osculating Keplerian elements to OEM arc
    if args.kepler:
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
                    object_name=oem_data.meta.object_name or "OBJECT",
                    object_id=oem_data.meta.object_id or "UNKNOWN",
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
                    object_name=oem_data.meta.object_name or "OBJECT",
                    object_id=oem_data.meta.object_id or "UNKNOWN",
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

        # Run TLE fitting
        tle_obj: tle.Tle
        diagnostics: fit_common.FitDiagnostics
        try:
            tle_obj, diagnostics = fit_tle.fit_tle(
                states,
                fit_span_s,
                "cartesian",
                args.mu_m3_s2,
                object_name=oem_data.meta.object_name or "OBJECT",
                object_id=oem_data.meta.object_id or "UNKNOWN",
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
