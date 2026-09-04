"""CLI argument parsing for the OEM-to-OMM conversion command.

Usage:
    oem-to-omm --mode {mean-kepler,tle} <input_oem|->
"""

from __future__ import annotations

import argparse
from datetime import timedelta
import warnings

import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.consts as consts
import ephem_toolkit.core.time_utils as time_utils

DEFAULT_FIT_SPAN: timedelta = timedelta(hours=2)
"""Default arc span for OEM-to-OMM fitting operations."""


class OemToOmmArgs(argparse.Namespace):
    """Typed argument namespace for the OEM-to-OMM CLI."""

    input_oem: str
    """Input OEM path or '-' for stdin."""
    output_omm: str
    """Output OMM path or '-' for stdout."""
    verbose: bool
    """Print verbose diagnostic output to stderr."""
    mu_m3_s2: float
    """Gravitational parameter in m³/s²."""
    fit_span: timedelta
    """Maximum arc span for the fit."""
    mode: str
    """Selected conversion mode: brouwer, dsst, or tle."""
    fit_model: str
    """Canonical selected fit model: brouwer, dsst, or sgp4."""
    theory: str
    """Mean element theory for brouwer/dsst modes."""
    object_name: str
    """Spacecraft name for OMM metadata."""
    object_id: str
    """International designator for OMM metadata."""
    tle_refinement: str
    """TLE refinement method."""
    tle_norad_cat_id: int
    """NORAD catalog ID for the TLE output."""
    tle_classification_type: str
    """TLE classification type."""
    tle_ephemeris_type: int
    """TLE ephemeris type."""
    tle_element_set_no: int
    """TLE element set number."""
    tle_rev_at_epoch: int
    """TLE revolution number at epoch."""
    fit_report: str | None
    source_model: str
    source_report: str | None
    no_fit_report: bool


def build_common_arg_parser(
    *,
    prog: str | None = None,
    description: str,
    epilog: str | None = None,
    output_dest: str = "output_omm",
    output_metavar: str = "<output_omm|->",
    object_name_help: str = "OBJECT_NAME: Spacecraft name for OMM metadata.",
    object_id_help: str = "OBJECT_ID: International designator (e.g., 1998-067A) for OMM output.",
) -> argparse.ArgumentParser:
    """Build the common OEM conversion options shared by OEM-to-OMM and OEM-to-TLE."""
    cli_parser = cli.build_arg_parser(description=description, epilog=epilog)
    if prog is not None:
        cli_parser.prog = prog

    cli_parser.add_argument(
        "input_oem",
        metavar="<input_oem|->",
        help='Path to input CCSDS OEM file; use "-" to read from stdin',
    )
    cli_parser.add_argument(
        "-o",
        "--output",
        dest=output_dest,
        metavar=output_metavar,
        required=True,
        help="Output file path; '-' writes to stdout",
    )
    cli_parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
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
        "--object-name",
        dest="object_name",
        metavar="<name>",
        default="",
        help=object_name_help,
    )
    cli_parser.add_argument(
        "--object-id",
        metavar="<YYYY-NNNP>",
        default="",
        dest="object_id",
        help=object_id_help,
    )
    cli_parser.add_argument("--fit-report", metavar="<path|->", default=None, help="Write JSON fit diagnostics to a file or stdout.")
    cli_parser.add_argument("--no-fit-report", action="store_true", help="Disable automatic fit-report creation.")
    cli_parser.add_argument("--source-model", default="auto", help="Input provenance model (default: auto).")
    cli_parser.add_argument("--source-report", metavar="<path>", default=None, help="Supplementary input provenance report.")
    cli_parser.add_argument(
        "--tle-refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        dest="tle_refinement",
        help=("Refinement method for TLE fitting (used with --tle mode)."),
    )
    cli_parser.add_argument(
        "--tle-norad-cat-id",
        type=int,
        default=0,
        metavar="<0..99999>",
        dest="tle_norad_cat_id",
        help="NORAD_CAT_ID: NORAD Catalog Number (default: 0, used with --tle mode).",
    )
    cli_parser.add_argument(
        "--tle-classification-type",
        choices=["U", "C", "S"],
        default="U",
        metavar="<U|C|S>",
        dest="tle_classification_type",
        help="CLASSIFICATION_TYPE: U=Unclassified, C=Classified, S=Secret (default: U, used with --tle mode).",
    )
    cli_parser.add_argument(
        "--tle-ephemeris-type",
        type=int,
        default=2,
        metavar="<0..9>",
        dest="tle_ephemeris_type",
        help="EPHEMERIS_TYPE: 0=SGP, 2=SGP4, 4=SGP4-XP, 6=SP (default: 2, used with --tle mode).",
    )
    cli_parser.add_argument(
        "--tle-element-set-no",
        type=int,
        default=999,
        metavar="<0..9999>",
        dest="tle_element_set_no",
        help="ELEMENT_SET_NO: Element set number for this satellite (default: 999, used with --tle mode).",
    )
    cli_parser.add_argument(
        "--tle-rev-at-epoch",
        type=int,
        default=0,
        metavar="<0..99999>",
        dest="tle_rev_at_epoch",
        help="REV_AT_EPOCH: Revolution number at epoch (default: 0, used with --tle mode).",
    )

    return cli_parser


def build_arg_parser() -> argparse.ArgumentParser:
    """Parse command-line arguments for the OEM-to-OMM conversion workflow.

    Returns
    -------
    OemToOmmArgs
        Parsed CLI arguments with the typed runtime namespace.
    """
    cli_parser = build_common_arg_parser(
        prog="oem-to-omm",
        description="Convert OEM state vectors to Keplerian elements or OMM.",
        epilog=(
            "Examples:\n"
            "  oem-to-omm --mode brouwer input.oem -o output.omm\n"
            "  cat input.oem | oem-to-omm --mode tle - -o -\n"
            "  cat input.oem | oem-to-omm --mode tle - -o output.omm"
        ),
        output_dest="output_omm",
        output_metavar="<output_omm|->",
        object_name_help="OBJECT_NAME: Spacecraft name for the generated OMM metadata.",
        object_id_help="OBJECT_ID: International designator for the generated OMM metadata.",
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
        "--fit-model",
        dest="fit_model",
        choices=["brouwer", "dsst", "sgp4"],
        default=None,
        metavar="<brouwer|dsst|sgp4>",
        help="Target mean-element model (default: sgp4).",
    )
    cli_parser.add_argument(
        "--mode",
        dest="mode",
        choices=["brouwer", "dsst", "tle"],
        default=None,
        metavar="<brouwer|dsst|tle>",
        help=(
            "Deprecated alias for --fit-model; 'tle' maps to 'sgp4'. "
            "'brouwer' fits Brouwer mean elements, "
            "'dsst' fits DSST mean elements, "
            "and 'tle' fits a TLE."
        ),
    )
    cli_parser.add_argument(
        "--theory",
        dest="theory",
        default=None,
        metavar="<theory>",
        help=(
            "Override MEAN_ELEMENT_THEORY in OMM output "
            "(e.g., 'DSST', 'BROUWER'). "
            "Defaults to theory matching the selected mode."
        ),
    )
    return cli_parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> OemToOmmArgs:
    """Parse command-line arguments."""
    args = parser.parse_args(argv, namespace=OemToOmmArgs())
    mode_model = {"brouwer": "brouwer", "dsst": "dsst", "tle": "sgp4"}
    legacy_model = mode_model.get(args.mode) if args.mode is not None else None
    if args.fit_model is not None and legacy_model is not None and args.fit_model != legacy_model:
        parser.error("--fit-model conflicts with deprecated --mode")
    if args.mode is not None:
        warnings.warn(
            "--mode is deprecated; use --fit-model instead",
            DeprecationWarning,
            stacklevel=2,
        )
    args.fit_model = args.fit_model or legacy_model or "sgp4"
    expected_theories = {
        "brouwer": {"BROUWER", "BROUWER-LYDDANE"},
        "dsst": {"DSST"},
        "sgp4": {"SGP4"},
    }
    if args.theory is not None and args.theory.upper() not in expected_theories[args.fit_model]:
        parser.error(
            f"--theory {args.theory!r} conflicts with --fit-model {args.fit_model!r}"
        )
    # Keep the existing implementation branches stable while exposing the
    # canonical model name to callers and reports.
    args.mode = "tle" if args.fit_model == "sgp4" else args.fit_model
    return args
