"""CLI argument parsing for TLE inspection."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Create the command-line argument parser."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Display TLE parameters and derived orbital elements for one or more TLE files."
        ),
        epilog=(
            "Loads each TLE file using TudatPy's SGP4 ephemeris and prints the epoch, "
            "TLE parameters, Cartesian state, and osculating Keplerian elements."
        ),
    )
    parser.add_argument(
        "tle_files",
        nargs="+",
        metavar="tle_file",
        help="Path(s) to TLE file(s) to process",
    )
    return parser.parse_args()
