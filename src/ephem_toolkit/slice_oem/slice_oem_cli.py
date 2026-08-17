"""CLI argument parsing for the OEM slicing command."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract subsets of CCSDS OEM ephemeris data by index or time range",
        epilog="For detailed documentation and examples, see doc/SLICE_OEM.md",
    )
    parser.add_argument(
        "oem_file",
        help='Path to input CCSDS OEM file. Use "-" to read from stdin.',
    )
    exclusive = parser.add_mutually_exclusive_group()
    exclusive.add_argument(
        "-s",
        "--slice",
        help="Python-style slice index (e.g., '0:10', '::2', '5', '-5:')",
        default=None,
    )
    exclusive.add_argument(
        "-t",
        "--time-slice",
        metavar="start[,[stop][,step]]",
        help=(
            "Time slice specifier: start[,[stop][,step]]. "
            "Start and stop may be ISO 8601 datetimes or durations. "
            "Step size is a duration and enables interpolation by default."
        ),
        default=None,
    )
    parser.add_argument(
        "--interpolate",
        action="store_true",
        default=True,
        help="Enable interpolation when step size is provided (enabled by default)",
    )
    parser.add_argument(
        "--no-interpolate",
        action="store_false",
        dest="interpolate",
        help="Disable interpolation",
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Output state vectors only (default: OEM format)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help="Output file path (default: '-'). Use '-' to print to stdout.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )

    return parser.parse_args()
