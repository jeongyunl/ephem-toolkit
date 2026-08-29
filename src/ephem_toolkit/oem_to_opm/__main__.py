#!/usr/bin/env python3
"""Fit OEM state vectors and write an OPM with osculating Keplerian elements.

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
    oem-to-opm <input_oem|-> -o <output_opm|->
"""

from __future__ import annotations

import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn, TextIO

import numpy as np

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.consts as consts
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.kepler as kepler
import ephem_toolkit.core.time_utils as time_utils

try:
    from .oem_to_opm_cli import OemToOpmArgs
    from .oem_to_opm_cli import parse_arguments
except ImportError:  # pragma: no cover - direct script execution fallback
    from ephem_toolkit.oem_to_opm.oem_to_opm_cli import OemToOpmArgs
    from ephem_toolkit.oem_to_opm.oem_to_opm_cli import parse_arguments

from . import fit_common
from . import fit_osculating_kepler

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

    Raises
    ------
    SystemExit
        Always raised with the supplied exit code.
    """
    print(message, file=sys.stderr)
    sys.exit(exit_code)


def build_opm(
    epoch: datetime,
    initial_state_m_m_s: np.ndarray,
    keplerian_elements: np.ndarray,
    *,
    object_name: str,
    object_id: str,
    center_name: str,
    ref_frame: str,
    time_system: str,
    mu_m3_s2: float,
) -> opm.CcsdsOpm:
    """Build an OPM containing the initial state and fitted elements.

    Parameters
    ----------
    epoch : datetime
        Epoch of the initial state.
    initial_state_m_m_s : np.ndarray
        Initial Cartesian state in meters and meters per second.
    keplerian_elements : np.ndarray
        Fitted Keplerian elements in meters and radians.
    object_name : str
        Spacecraft name for OPM metadata.
    object_id : str
        International designator for OPM metadata.
    center_name : str
        Central body name for OPM metadata.
    ref_frame : str
        Reference frame for OPM metadata.
    time_system : str
        Time system for OPM metadata.
    mu_m3_s2 : float
        Gravitational parameter in m³/s².

    Returns
    -------
    opm.CcsdsOpm
        OPM containing the initial state and fitted elements.
    """
    epoch_str = time_utils.datetime_to_iso8601(epoch, fractional_second_places=6)
    return opm.CcsdsOpm(
        header=opm.OpmHeader(
            creation_date=time_utils.datetime_to_iso8601(
                datetime.now(timezone.utc), fractional_second_places=3
            ),
            originator="oem_to_opm",
        ),
        metadata={
            "OBJECT_NAME": object_name,
            "OBJECT_ID": object_id,
            "CENTER_NAME": center_name,
            "REF_FRAME": ref_frame,
            "TIME_SYSTEM": time_system,
        },
        state_vector=opm.OpmStateVector(
            epoch=epoch_str,
            x=float(initial_state_m_m_s[0] / 1000.0),
            y=float(initial_state_m_m_s[1] / 1000.0),
            z=float(initial_state_m_m_s[2] / 1000.0),
            x_dot=float(initial_state_m_m_s[3] / 1000.0),
            y_dot=float(initial_state_m_m_s[4] / 1000.0),
            z_dot=float(initial_state_m_m_s[5] / 1000.0),
        ),
        keplerian_elements=opm.OpmKeplerianElements(
            semi_major_axis=float(
                keplerian_elements[kepler.SEMI_MAJOR_AXIS_INDEX] / 1000.0
            ),
            eccentricity=float(keplerian_elements[kepler.ECCENTRICITY_INDEX]),
            inclination=float(np.degrees(keplerian_elements[kepler.INCLINATION_INDEX])),
            ra_of_asc_node=float(np.degrees(keplerian_elements[kepler.RAAN_INDEX])),
            arg_of_pericenter=float(
                np.degrees(keplerian_elements[kepler.ARGUMENT_OF_PERIAPSIS_INDEX])
            ),
            true_anomaly=float(
                np.degrees(keplerian_elements[kepler.TRUE_ANOMALY_INDEX])
            ),
            gm=float(mu_m3_s2 / 1.0e9),
        ),
    )


# ===================================================================
# Main
# ===================================================================


def main(argv=None) -> None:
    """Parse CLI arguments and dispatch to the appropriate conversion mode."""
    cli_args: OemToOpmArgs = parse_arguments(argv)

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

    # Run the Gauss-Newton velocity-only fit (position at epoch is fixed)
    fitted_elements: np.ndarray
    diagnostics: fit_common.FitDiagnostics
    try:
        fitted_elements, diagnostics = fit_osculating_kepler.fit_osculating_kepler(
            states,
            fit_span_s,
            cli_args.mu_m3_s2,
        )
    except Exception as error:
        report_error(f"Error fitting Keplerian elements: {error}")

    # Compute propagation comparison at 10-minute intervals
    comparison: list[fit_common.PropagationComparison] = (
        fit_osculating_kepler.compute_kepler_propagation_comparison(
            fitted_elements, states, cli_args.mu_m3_s2, fit_span_s, interval_s=600.0
        )
    )

    # Format and report output
    first_epoch: datetime = time_utils.tt_s_to_datetime(states[0][0])
    output_text: str = fit_osculating_kepler.format_kepler_output(
        first_epoch, fitted_elements, diagnostics, comparison
    )

    # Report results to stderr in verbose mode when output is stdout
    if cli_args.verbose and cli_args.output_opm == "-":
        print(output_text, file=sys.stderr)
    elif cli_args.verbose:
        report_results(output_text, "-", cli_args.verbose)

    # Save the initial state and fitted osculating elements as an OPM.
    if cli_args.output_opm:
        try:
            opm_obj = build_opm(
                first_epoch,
                states[0][1],
                fitted_elements,
                object_name=object_name,
                object_id=object_id,
                center_name=oem_data.meta.center_name or "EARTH",
                ref_frame=oem_data.meta.ref_frame or "ICRF",
                time_system=oem_data.meta.time_system or "UTC",
                mu_m3_s2=cli_args.mu_m3_s2,
            )
            # Output to stdout if dest is "-", otherwise to file
            if cli_args.output_opm == "-":
                opm_obj.to_file(sys.stdout)
            else:
                opm_obj.to_file(cli_args.output_opm)
                if cli_args.verbose:
                    print(
                        f"OPM file written to: {cli_args.output_opm}",
                        file=sys.stderr,
                    )
        except Exception as error:
            report_error(f"Error writing OPM file: {error}")


if __name__ == "__main__":
    main()
