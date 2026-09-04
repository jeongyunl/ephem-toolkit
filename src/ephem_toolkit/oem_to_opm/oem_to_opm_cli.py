"""CLI argument parsing for the OEM-to-OPM conversion command.

Usage:
    oem-to-opm <input_oem|-> -o <output_opm|->
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.consts as consts
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.propagate_orbit.constants import (
    DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2,
    DEFAULT_SATELLITE_DRAG_COEFFICIENT,
    DEFAULT_SATELLITE_MASS_KG,
    DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT,
)

DEFAULT_FIT_SPAN: timedelta = timedelta(hours=2)
"""Default arc span for OEM-to-OPM fitting operations."""


class OemToOpmArgs(argparse.Namespace):
    """Typed argument namespace for the OEM-to-OPM CLI."""

    input_oem: str
    """Input OEM path or '-' for stdin."""
    output_opm: str
    """Output OPM path or '-' for stdout."""
    verbose: bool
    """Print verbose diagnostic output to stderr."""
    debug: bool
    """Print detailed debug information to stderr."""
    mu_m3_s2: float
    """Gravitational parameter in m³/s²."""
    fit_span: timedelta
    """Maximum arc span for the fit."""
    object_name: str
    """Spacecraft name for OPM metadata."""
    object_id: str
    """International designator for OPM metadata."""
    fit_report: str | None
    source_model: str
    source_report: str | None
    no_fit_report: bool
    fit_model: str
    fit_observables: str
    fit_position_weight: float
    fit_max_iterations: int
    fit_end_weight: float
    fit_parameters: str


def parse_positive_float(value: str) -> float:
    """Parse a strictly positive floating-point CLI value."""
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a number") from error
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parse_positive_int(value: str) -> int:
    """Parse a strictly positive integer CLI value."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parse_bool(value: str) -> bool:
    """Parse an on/off CLI value."""
    normalized = value.strip().lower()
    if normalized in {"on", "true", "yes"}:
        return True
    if normalized in {"off", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError("value must be on/off, true/false, or yes/no")


def report_error(message: str, exit_code: int = 1) -> None:
    """Report an error message to stderr and exit.

    Parameters
    ----------
    message : str
        Error message to display.
    exit_code : int, optional
        Exit code to raise with SystemExit. Default is 1.

    Raises
    ------
    SystemExit
        Always raised with the supplied exit code.
    """
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def build_arg_parser() -> argparse.ArgumentParser:
    """Parse command-line arguments for the OEM-to-OPM conversion workflow.

    Returns
    -------
    OemToOpmArgs
        Parsed CLI arguments with the typed runtime namespace.
    """
    cli_parser = cli.build_arg_parser(
        description="Fit OEM state vectors and write an OPM with osculating elements.",
        epilog=(
            "Examples:\n"
            "  oem-to-opm input.oem -o output.opm\n"
            "  cat input.oem | oem-to-opm - -o -"
        ),
    )
    cli_parser.prog = "oem-to-opm"
    cli_parser.add_argument(
        "input_oem",
        metavar="<input_oem|->",
        help='Path to input CCSDS OEM file; use "-" to read from stdin',
    )
    cli_parser.add_argument(
        "-o",
        "--output",
        dest="output_opm",
        metavar="<output_opm|->",
        required=True,
        help="Output OPM file path; '-' writes to stdout",
    )
    cli_parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )
    cli_parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print detailed internal diagnostics to stderr; implies --verbose.",
    )
    cli_parser.add_argument(
        "--mu",
        type=float,
        default=consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
        metavar="<value>",
        dest="mu_m3_s2",
        help=(
            "Gravitational parameter (m³/s²). "
            f"(default: {consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2:.6e}, Earth WGS-84)."
        ),
    )
    cli_parser.add_argument(
        "--fit-span",
        type=time_utils.parse_duration_to_timedelta,
        default=DEFAULT_FIT_SPAN,
        metavar="<duration>",
        dest="fit_span",
        help=(
            "Maximum arc span for the fit (supports durations like 2h, 90m, 3600s; "
            "default: 2h)."
        ),
    )
    cli_parser.add_argument(
        "--fit-model",
        choices=["two-body", "numerical"],
        default="two-body",
        dest="fit_model",
        metavar="<two-body|numerical>",
        help="Fitting model (default: two-body).",
    )
    cli_parser.add_argument("--fit-observables", choices=["position"], default="position", dest="fit_observables", help="Residual observable: position only (default: position).")
    cli_parser.add_argument("--fit-position-weight", type=parse_positive_float, default=1.0, dest="fit_position_weight", metavar="<value>", help="Position residual weight.")
    cli_parser.add_argument("--fit-max-iterations", type=parse_positive_int, default=100, dest="fit_max_iterations", metavar="<count>", help="Maximum numerical-fit iterations (default: 100).")
    cli_parser.add_argument("--fit-end-weight", type=parse_positive_float, default=2.0, dest="fit_end_weight", metavar="<value>", help="Position residual multiplier at the end of the fit span (default: 2.0).")
    cli_parser.add_argument("--fit-parameters", choices=["initial-state", "initial-state,drag-coeff", "initial-state,srp-coeff"], default="initial-state", dest="fit_parameters", help="Fitted state selection; physical parameters are fixed user inputs.")
    cli_parser.add_argument("--mass", type=parse_positive_float, default=DEFAULT_SATELLITE_MASS_KG, metavar="<kg>", help=f"Fixed spacecraft mass for numerical propagation (default: {DEFAULT_SATELLITE_MASS_KG}).")
    cli_parser.add_argument("--drag-area", type=parse_positive_float, default=DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2, dest="drag_area", metavar="<m2>", help=f"Fixed drag/SRP reference area (default: {DEFAULT_CUBESAT_AVERAGE_PROJECTION_AREA_M2}).")
    cli_parser.add_argument("--drag", type=parse_bool, default=True, metavar="<on|off>", help="Enable fixed drag force model (default: on).")
    cli_parser.add_argument("--drag-coeff", type=parse_positive_float, default=DEFAULT_SATELLITE_DRAG_COEFFICIENT, dest="drag_coeff", metavar="<value>", help=f"Fixed drag coefficient (default: {DEFAULT_SATELLITE_DRAG_COEFFICIENT}).")
    cli_parser.add_argument("--srp", type=parse_bool, default=True, metavar="<on|off>", help="Enable fixed SRP force model (default: on).")
    cli_parser.add_argument("--srp-coeff", type=parse_positive_float, default=DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT, dest="srp_coeff", metavar="<value>", help=f"Fixed SRP coefficient (default: {DEFAULT_SATELLITE_RADIATION_PRESSURE_COEFFICIENT}).")
    cli_parser.add_argument(
        "--object-name",
        dest="object_name",
        metavar="<name>",
        default="",
        help="OBJECT_NAME: Spacecraft name for OPM output.",
    )
    cli_parser.add_argument(
        "--object-id",
        metavar="<YYYY-NNNP>",
        default="",
        dest="object_id",
        help="OBJECT_ID: International designator (e.g., 1998-067A) for OPM output.",
    )
    cli_parser.add_argument("--fit-report", metavar="<path|->", default=None, help="Write JSON fit diagnostics to a file or stdout.")
    cli_parser.add_argument("--no-fit-report", action="store_true", help="Disable automatic fit-report creation.")
    cli_parser.add_argument("--source-model", default="auto", help="Input provenance model (default: auto).")
    cli_parser.add_argument("--source-report", metavar="<path>", default=None, help="Supplementary input provenance report.")

    return cli_parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> OemToOpmArgs:
    """Parse command-line arguments."""
    return parser.parse_args(argv, namespace=OemToOpmArgs())
