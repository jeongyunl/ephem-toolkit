"""CLI argument parsing for the TLE-to-OMM conversion command."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for TLE-to-OMM conversion."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert a Two-Line Element (TLE) set to a CCSDS Orbit Mean-Elements "
            "Message (OMM). Reads TLE from a file path or stdin and writes OMM to "
            "stdout or a file."
        )
    )
    parser.add_argument(
        "input",
        metavar="<input.tle>",
        help='Input TLE file path. Use "-" to read TLE text from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<output.omm>",
        default=None,
        help="Output OMM file path. If omitted, OMM is printed to stdout.",
    )
    return parser.parse_args()
