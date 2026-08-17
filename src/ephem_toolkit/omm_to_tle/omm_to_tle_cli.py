"""CLI argument parsing for the OMM-to-TLE conversion command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for OMM-to-TLE conversion."""
    parser = cli.create_parser(
        description=(
            "Convert a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element "
            "(TLE) set. Reads OMM from a file path or stdin and writes TLE to stdout "
            "or a file."
        ),
        epilog=(
            "Examples:\n"
            '  omm-to-tle input.omm\n'
            '  cat input.omm | omm-to-tle -\n'
            '  omm-to-tle input.omm -o output.tle'
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
        default=None,
        help="Output TLE file path; '-' writes to stdout.",
    )
    return parser.parse_args()
