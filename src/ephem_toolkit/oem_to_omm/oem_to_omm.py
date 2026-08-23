#!/usr/bin/env python3
"""Convert OEM state vectors to mean Keplerian elements or OMM.

Supports two modes:

mean-kepler mode:
  Fits mean Keplerian elements to the first 2 hours of OEM states using
  J2 secular propagation. The result fits the initial state exactly and
  minimizes position residuals over the fit arc.

tle mode:
  Fits TLE mean elements (SGP4-compatible) to the OEM states. Creates an
  OMM with MEAN_ELEMENT_THEORY=SGP4 and includes TLE-related parameters
  (BSTAR, MEAN_MOTION_DOT, etc.). The output OMM can be converted to a
  standard TLE format per CCSDS 502.0-B-3 (2023-04).

Usage:
    oem-to-omm --mode mean-kepler <input.oem>
    oem-to-omm --mode tle <input.oem>
    oem-to-omm --mode tle - -o -
    cat input.oem | oem-to-omm --mode tle - -o -
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn, TextIO
import numpy as np

import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.consts as consts
import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.mean_kepler as mean_kepler
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.core.tle as tle

try:
    from .oem_to_omm_cli import OemToOmmArgs
    from .oem_to_omm_cli import parse_arguments
except ImportError:  # pragma: no cover - direct script execution fallback
    from ephem_toolkit.oem_to_omm.oem_to_omm_cli import OemToOmmArgs
    from ephem_toolkit.oem_to_omm.oem_to_omm_cli import parse_arguments

from . import fit_common
from . import fit_mean_kepler
from . import fit_tle_main as fit_tle

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
    cli_args: OemToOmmArgs = parse_arguments()

    # Determine input source: file path or stdin (piped input)
    read_from_stdin: bool = cli_args.input_oem == "-"

    # Read and parse CCSDS OEM ephemeris data
    if read_from_stdin:
        oem_data = oem.CcsdsOem.read(sys.stdin)
    else:
        oem_path = Path(cli_args.input_oem)
        if not oem_path.exists():
            report_error(f"Error: Input file not found: {cli_args.input_oem}")
        oem_data = oem.CcsdsOem.read(oem_path)

    states: list[tuple[float, np.ndarray]] = oem_data.states

    if len(states) < 2:
        report_error("Error: At least 2 state vectors required for fitting.")

    fit_span_s: float = cli_args.fit_span.total_seconds()

    # Determine object name: use --object-name if provided, otherwise use OEM metadata
    object_name: str = (
        cli_args.object_name
        if cli_args.object_name
        else (oem_data.meta.object_name or "OBJECT")
    )

    # Determine object_id: use --object-id if provided, otherwise use OEM metadata
    if cli_args.object_id:
        object_id: str = cli_args.object_id
    else:
        object_id: str = oem_data.meta.object_id or "UNKNOWN"

    if cli_args.mode == "mean-kepler":
        # Run the Gauss-Newton velocity-only fit for mean elements
        fitted_mean_elements: np.ndarray
        diagnostics: fit_common.FitDiagnostics
        try:
            fitted_mean_elements, diagnostics = fit_mean_kepler.fit_mean_kepler(
                states,
                fit_span_s,
                cli_args.mu_m3_s2,
            )
        except Exception as error:
            report_error(f"Error fitting mean Keplerian elements: {error}")

        # Compute propagation comparison at 10-minute intervals
        comparison: list[fit_common.PropagationComparison] = (
            fit_mean_kepler.compute_mean_kepler_propagation_comparison(
                fitted_mean_elements,
                states,
                cli_args.mu_m3_s2,
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
        if cli_args.verbose and cli_args.output_omm == "-":
            print(output_text, file=sys.stderr)
        elif cli_args.verbose:
            report_results(output_text, "-", cli_args.verbose)

        # Save OMM format if requested (convert mean to osculating first)
        if cli_args.output_omm:
            try:
                osculating_elements: np.ndarray = (
                    mean_kepler.mean_to_osculating_keplerian(fitted_mean_elements)
                )
                omm_obj: omm.CcsdsOmm = omm.keplerian_to_omm(
                    first_epoch,
                    osculating_elements,
                    object_name=object_name,
                    object_id=object_id,
                    mu_m3_s2=cli_args.mu_m3_s2,
                )
                omm_obj.originator = "oem_to_omm"
                if cli_args.output_omm == "-":
                    omm_obj.to_file(sys.stdout)
                else:
                    omm_obj.to_file(cli_args.output_omm)
                    if cli_args.verbose:
                        print(
                            f"OMM file written to: {cli_args.output_omm}",
                            file=sys.stderr,
                        )
            except Exception as error:
                report_error(f"Error writing OMM file: {error}")
        return

    if cli_args.mode == "tle":
        if not (0 <= cli_args.tle_norad_cat_id <= 99999):
            report_error("Error: --norad-cat-id must be in [0, 99999]")
        if not (0 <= cli_args.tle_ephemeris_type <= 9):
            report_error("Error: --ephemeris-type must be in [0, 9]")
        if not (0 <= cli_args.tle_element_set_no <= 9999):
            report_error("Error: --element-set-no must be in [0, 9999]")
        if not (0 <= cli_args.tle_rev_at_epoch <= 99999):
            report_error("Error: --rev-at-epoch must be in [0, 99999]")

        tle_obj: tle.Tle
        diagnostics: fit_common.FitDiagnostics
        try:
            tle_obj, diagnostics = fit_tle.fit_tle(
                states,
                fit_span_s,
                cli_args.tle_refinement,
                cli_args.mu_m3_s2,
                object_name=object_name,
                object_id=object_id,
                norad_cat_id=cli_args.tle_norad_cat_id,
                classification_type=cli_args.tle_classification_type,
                ephemeris_type=cli_args.tle_ephemeris_type,
                element_set_number=cli_args.tle_element_set_no,
                revolution_number_at_epoch=cli_args.tle_rev_at_epoch,
            )
        except Exception as error:
            import traceback

            traceback.print_exc()
            report_error(f"Error fitting TLE elements: {error}")

        comparison: list[fit_common.PropagationComparison] = (
            fit_tle.compute_tle_propagation_comparison(
                tle_obj, states, cli_args.mu_m3_s2, fit_span_s, interval_s=600.0
            )
        )

        first_epoch: datetime = datetime.fromtimestamp(states[0][0], tz=timezone.utc)
        output_text: str = fit_tle.format_tle_output(
            first_epoch, tle_obj, diagnostics, comparison
        )

        if cli_args.verbose and cli_args.output_omm == "-":
            print(output_text, file=sys.stderr)
        elif cli_args.verbose:
            report_results(output_text, "-", cli_args.verbose)

        if cli_args.output_omm:
            try:
                omm_obj: omm.CcsdsOmm = convert_tle.tle_to_omm(
                    tle_obj,
                    creation_date=time_utils.datetime_to_iso8601(
                        datetime.now(timezone.utc), fractional_second_places=3
                    ),
                    originator="oem_to_omm",
                )
                omm_obj.originator = "oem_to_omm"
                omm_obj.comments = [
                    "TLE mean elements (SGP4-compatible)",
                    "Compliant with CCSDS 502.0-B-3 (2023-04)",
                ]
                if cli_args.output_omm == "-":
                    omm_obj.to_file(sys.stdout)
                else:
                    omm_obj.to_file(cli_args.output_omm)
                    if cli_args.verbose:
                        print(
                            f"OMM file written to: {cli_args.output_omm}",
                            file=sys.stderr,
                        )
            except Exception as error:
                report_error(f"Error writing OMM file: {error}")
        return


if __name__ == "__main__":
    main()
