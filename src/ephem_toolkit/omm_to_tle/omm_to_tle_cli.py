"""CLI argument parsing for the OMM-to-TLE conversion command."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for OMM-to-TLE conversion."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element "
            "(TLE) set. Reads OMM from a file path or stdin and writes TLE to stdout "
            "or a file."
        )
    )
    parser.add_argument(
        "input",
        metavar="<input.omm>",
        help='Input OMM file path. Use "-" to read OMM text from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<output.tle>",
        default=None,
        help="Output TLE file path. If omitted, TLE is printed to stdout.",
    )
    return parser.parse_args()
