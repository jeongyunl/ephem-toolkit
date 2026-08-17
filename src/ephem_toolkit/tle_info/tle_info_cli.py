"""CLI argument parsing for TLE inspection."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


def parse_arguments() -> argparse.Namespace:
    """Create the command-line argument parser."""
    parser: argparse.ArgumentParser = cli.create_parser(
        description=(
            "Display TLE parameters and derived orbital elements for one or more TLE files."
        ),
        epilog=(
            "Loads each TLE file using TudatPy's SGP4 ephemeris and prints the epoch, "
            "TLE parameters, Cartesian state, and osculating Keplerian elements."
        ),
    )
    parser.prog = "tle-info"
    parser.add_argument(
        "tle_files",
        nargs="+",
        metavar="<tle_file>",
        help="Path to one or more TLE files to process.",
    )
    return parser.parse_args()
