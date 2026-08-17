"""CLI argument parsing for the TLE-to-OMM conversion command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for TLE-to-OMM conversion."""
    parser = cli.create_parser(
        description=(
            "Convert a Two-Line Element (TLE) set to a CCSDS Orbit Mean-Elements "
            "Message (OMM). Reads TLE from a file path or stdin and writes OMM to "
            "stdout or a file."
        ),
        epilog=(
            "Examples:\n"
            '  tle-to-omm input.tle\n'
            '  cat input.tle | tle-to-omm -\n'
            '  tle-to-omm input.tle -o output.omm'
        ),
    )
    parser.prog = "tle-to-omm"
    parser.add_argument(
        "input_tle",
        metavar="<input_tle|->",
        help='Input TLE file path; use "-" to read TLE text from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_omm",
        metavar="<output_omm|->",
        default=None,
        help="Output OMM file path; use '-' to write to stdout.",
    )
    return parser.parse_args()
