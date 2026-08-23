"""CLI argument parsing for the OEM slicing command."""

from __future__ import annotations

import argparse
from functools import partial

import ephem_toolkit.core.cli as cli
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)

DEFAULT_INTERPOLATION_TYPE: str = "hermite"
DEFAULT_INTERPOLATION_DEGREE: int = 5
DEFAULT_INTERPOLATION_SPEC: InterpolationSpec = InterpolationSpec(
    interp_type=InterpolationType.HERMITE,
    degree=DEFAULT_INTERPOLATION_DEGREE,
)


class SliceOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM slicing CLI."""

    input_oem: str
    """Primary input OEM file path or '-' for stdin."""
    slice: str | None
    """Optional index slice specification."""
    time_slice: str | None
    """Optional time slice specification."""
    interpolate: bool
    """Whether interpolation is enabled."""
    interpolate_type: InterpolationSpec
    """Interpolation specification."""
    opm: bool
    """Whether to emit only the first selected state vector."""
    data_only: bool
    """Whether to omit OEM metadata header."""
    output_path: str
    """Output OEM/OPM path or '-' for stdout."""
    verbose: bool
    """Whether verbose diagnostics are enabled."""
    debug: bool
    """Whether low-level debug output is enabled."""


def parse_arguments() -> SliceOemArgs:
    """Parse and validate command-line arguments."""
    parser = cli.create_parser(
        description="Extract subsets of CCSDS OEM ephemeris data by index or time range.",
        epilog=(
            "Examples:\n"
            '  slice-oem data.oem --slice "0:10"\n'
            '  slice-oem data.oem --time-slice "0,1h"\n'
            '  cat data.oem | slice-oem - --slice "0:10"'
        ),
    )
    parser.add_argument(
        "input_oem",
        metavar="<input_oem|->",
        help='Primary input OEM file path; use "-" to read from stdin',
    )
    exclusive = parser.add_mutually_exclusive_group()
    exclusive.add_argument(
        "-s",
        "--slice",
        dest="slice",
        metavar="<slice>",
        help="Python-style slice specification, for example '0:10', '::2', '5', or '-5:'.",
        default=None,
    )
    exclusive.add_argument(
        "-t",
        "--time-slice",
        dest="time_slice",
        metavar="<start[,stop[,step]]>",
        help=(
            "Time slice specification: start[,stop[,step]]. Start and stop may be ISO-8601 "
            "timestamps or durations; step is a duration and enables interpolation by default."
        ),
        default=None,
    )
    parser.add_argument(
        "--interpolate",
        dest="interpolate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable interpolation when a step size is provided (enabled by default)",
    )
    parser.add_argument(
        "--interpolate-type",
        dest="interpolate_type",
        type=partial(
            cli.parse_interpolate_type,
            default_degree=DEFAULT_INTERPOLATION_DEGREE,
        ),
        default=DEFAULT_INTERPOLATION_SPEC,
        metavar="<type[,degree]>",
        help=(
            "Interpolation method: 'hermite[,degree]', 'chebyshev[,degree]', or "
            "'lagrange[,degree]' (default: hermite,5). Degree must be > 0."
        ),
    )
    parser.add_argument(
        "--opm",
        dest="opm",
        action="store_true",
        help="Emit only the first selected state vector",
    )
    parser.add_argument(
        "--data-only",
        dest="data_only",
        action="store_true",
        help="Write state vectors only; omit the OEM metadata header",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        metavar="<output_oem|output_opm|->",
        required=True,
        help="Output OEM/OPM file path; use '-' to write to stdout",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Print extra diagnostic output",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print low-level debug details",
    )
    args = parser.parse_args(namespace=SliceOemArgs())
    if not args.slice and not args.time_slice:
        parser.error("either -s/--slice or -t/--time-slice must be provided")
    return args
