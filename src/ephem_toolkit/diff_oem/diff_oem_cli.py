"""Command-line interface for OEM comparison.

Usage:
    python3 -m ephem_toolkit.diff_oem <reference_oem.oem> <comparison_oem.oem> [options]
"""

from __future__ import annotations

import argparse
from functools import partial
import sys

import ephem_toolkit.core.cli as cli
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.core.time_utils import parse_duration_to_seconds

from .utils import parse_rotation_fit_span

ROTATION_FIT_DURATION_S: float = 3600.0
"""Duration of the state history used by the optional rotation fit."""

DEFAULT_INTERPOLATION_TYPE: str = "hermite"
"""Default interpolation method."""

DEFAULT_INTERPOLATION_DEGREE: int = 5
"""Default polynomial degree for interpolation (Hermite default)."""

DEFAULT_INTERPOLATION_SPEC: InterpolationSpec = InterpolationSpec(
    interp_type=InterpolationType.HERMITE,
    degree=DEFAULT_INTERPOLATION_DEGREE,
)
"""Default interpolation specification."""

TRANSFORM_STAGE_OPTIONS: dict[str, str] = {
    "--rotate": "rotate",
    "--rotate-xy": "rotate_xy",
    "--rotate-z": "rotate_z",
    "--time-shift": "time_shift",
}
"""Supported transformation-stage options mapped to internal stage keys."""


class DiffOemArgs(argparse.Namespace):
    """Typed CLI arguments for the diff_oem command."""

    reference_oem: str
    """Reference OEM path or '-' for stdin."""
    comparison_oem: str
    """Comparison OEM path or '-' for stdin."""
    verbose: bool
    """Print detailed comparison diagnostics to stderr."""
    debug: bool
    """Print debug timing information to stderr."""
    interpolate_ref: bool
    """Interpolate the reference OEM to comparison timestamps."""
    interpolate_data: bool
    """Interpolate comparison data to reference timestamps."""
    interpolate: bool
    """Convenience flag enabling both interpolation paths."""
    interpolate_type: InterpolationSpec
    """Interpolation configuration for OEM comparisons."""
    rtn: bool
    """Report coordinates relative to the RTN frame."""
    rotate: bool
    """Apply a fixed rotation fit before comparing states."""
    rotate_xy: bool
    """Apply a fixed X/Y-axis rotation fit before comparing states."""
    rotate_z: bool
    """Apply a fixed Z-axis rotation fit before comparing states."""
    time_shift: bool
    """Apply a constant time shift before comparing states."""
    rot_fit_span: float
    """Duration used for rotation fitting."""
    start: str | None
    """Optional start timestamp or duration offset."""
    duration: float | None
    """Optional duration limit relative to --start."""
    stop: str | None
    """Optional stop timestamp or duration offset."""
    stage_sequence: list[str]
    """Transformation stage order as requested by the CLI."""


def parse_arguments() -> DiffOemArgs:
    """Parse command-line arguments.

    Returns
    -------
    DiffOemArgs
        Parsed command-line arguments with attributes ``reference_oem``,
        ``comparison_oem``, ``verbose``, ``debug``, ``interpolate_ref``, and
        ``interpolate_data``. The ``--interpolate`` convenience option enables
        both interpolation flags, and is represented by the parsed interpolation
        attributes. ``stage_sequence`` records transformation stage order as
        requested in the CLI.
    """
    parser: argparse.ArgumentParser = cli.create_parser(
        description=(
            "Compare two OEM files and report differences in time, "
            "position, and velocity."
        ),
        epilog=(
            "Examples:\n"
            "  diff-oem reference.oem comparison.oem --rotate\n"
            "  diff-oem reference.oem comparison.oem --time-shift\n"
            "  diff-oem reference.oem comparison.oem --start 2026-01-01T00:00:00 --duration 1h"
        ),
    )
    parser.add_argument(
        "reference_oem",
        metavar="<reference_oem|->",
        help="Reference OEM file path; use '-' to read from stdin.",
    )
    parser.add_argument(
        "comparison_oem",
        metavar="<comparison_oem|->",
        help="Comparison OEM file path; use '-' to read from stdin.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Print detailed component-wise differences.",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print time-range determination details to stderr.",
    )
    parser.add_argument(
        "--interpolate-ref",
        dest="interpolate_ref",
        action="store_true",
        help="Interpolate the reference OEM at each comparison state timestamp.",
    )
    parser.add_argument(
        "--interpolate-data",
        dest="interpolate_data",
        action="store_true",
        default=True,
        help="Interpolate comparison data at each reference state timestamp (enabled by default).",
    )
    parser.add_argument(
        "--interpolate",
        dest="interpolate",
        action="store_true",
        help="Interpolate both reference and comparison OEM data.",
    )
    parser.add_argument(
        "--interpolate-type",
        dest="interpolate_type",
        type=partial(
            cli.parse_interpolate_type, default_degree=DEFAULT_INTERPOLATION_DEGREE
        ),
        default=DEFAULT_INTERPOLATION_SPEC,
        metavar="<type[,degree]>",
        help=(
            "Interpolation method: 'hermite[,degree]', 'chebyshev[,degree]', "
            "or 'lagrange[,degree]' "
            f"(default: {DEFAULT_INTERPOLATION_TYPE},{DEFAULT_INTERPOLATION_DEGREE}). "
            "Degree must be > 0."
        ),
    )
    parser.add_argument(
        "--rtn",
        dest="rtn",
        action="store_true",
        help="Include comparison state coordinates in the reference RTN frame.",
    )
    parser.add_argument(
        "--rotate",
        dest="rotate",
        action="store_true",
        help="Fit a fixed rotation from the initial comparison state span and apply it before reporting differences (may be repeated).",
    )
    parser.add_argument(
        "--rotate-xy",
        dest="rotate_xy",
        action="store_true",
        help="Fit a fixed rotation around the X and Y axes from the initial comparison state span (may be repeated).",
    )
    parser.add_argument(
        "--rotate-z",
        dest="rotate_z",
        action="store_true",
        help="Fit a fixed rotation around the Z axis from the initial comparison state span (may be repeated).",
    )
    parser.add_argument(
        "--time-shift",
        dest="time_shift",
        action="store_true",
        help="Fit a constant comparison epoch bias and shift comparison timestamps before reporting differences (may be repeated).",
    )
    parser.add_argument(
        "--rotate-fit-span",
        dest="rot_fit_span",
        type=parse_rotation_fit_span,
        default=ROTATION_FIT_DURATION_S,
        metavar="<duration>",
        help=f"Duration of initial state span used for --rotate fitting (default: {ROTATION_FIT_DURATION_S:g}s).",
    )
    parser.add_argument(
        "--start",
        dest="start",
        metavar="<timestamp|duration>",
        default=None,
        help="Start epoch in ISO-8601 format (for example, 2001-11-06T11:17:33 or 2001-11-06T11:17:33.1234) or as a duration offset from the reference epoch.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        dest="duration",
        type=parse_duration_to_seconds,
        metavar="<duration>",
        default=None,
        help="Relative stop duration from --start; equivalent to --stop = --start + duration.",
    )
    parser.add_argument(
        "--stop",
        dest="stop",
        metavar="<timestamp|duration>",
        default=None,
        help="Stop epoch in ISO-8601 format (for example, 2001-11-06T11:17:33 or 2001-11-06T11:17:33.1234) or as a duration offset from --start.",
    )
    args = parser.parse_args(namespace=DiffOemArgs())
    if args.duration is not None and args.stop is not None:
        parser.error("--duration and --stop cannot be used together")
    args.stage_sequence = extract_stage_sequence(sys.argv[1:])
    if args.interpolate:
        args.interpolate_ref = True
        args.interpolate_data = True
    if args.reference_oem == "-" and args.comparison_oem == "-":
        parser.error("reference_oem and comparison_oem cannot both be '-'")
    return args


def extract_stage_sequence(argv: list[str]) -> list[str]:
    """Return transformation stage keys in order of CLI appearance.

    Parameters
    ----------
    argv : list[str]
        Command-line argument list to extract stage sequence from.

    Returns
    -------
    list[str]
        Transformation stage keys in order of appearance.
    """
    stage_sequence: list[str] = []
    for token in argv:
        option = token.split("=", maxsplit=1)[0]
        stage_key = TRANSFORM_STAGE_OPTIONS.get(option)
        if stage_key is not None:
            stage_sequence.append(stage_key)
    return stage_sequence
