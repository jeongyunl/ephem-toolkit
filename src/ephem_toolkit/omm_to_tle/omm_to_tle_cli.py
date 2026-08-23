"""CLI argument parsing for the OMM-to-TLE conversion command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


class OmmToTleArgs(argparse.Namespace):
    """Typed argument namespace for the OMM-to-TLE CLI."""

    input_omm: str
    """Input OMM path or '-' for stdin."""
    output_tle: str | None
    """Output TLE path or '-' for stdout."""


def parse_arguments() -> OmmToTleArgs:
    """Parse command-line arguments for OMM-to-TLE conversion."""
    parser = cli.create_parser(
        description=(
            "Convert a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element "
            "(TLE) set. Reads OMM from a file path or stdin and writes TLE to stdout "
            "or a file."
        ),
        epilog=(
            "Examples:\n"
            "  omm-to-tle input.omm -o -\n"
            "  cat input.omm | omm-to-tle - -o -\n"
            "  omm-to-tle input.omm -o output.tle"
        ),
    )
    parser.prog = "omm-to-tle"
    parser.add_argument(
        "input_omm",
        metavar="<input_omm|->",
        help='Input OMM file path; use "-" to read OMM text from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_tle",
        metavar="<output_tle|->",
        required=True,
        help="Output TLE file path; '-' writes to stdout.",
    )
    return parser.parse_args(namespace=OmmToTleArgs())
