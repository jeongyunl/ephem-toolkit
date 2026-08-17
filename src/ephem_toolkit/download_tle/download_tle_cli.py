"""CLI argument parsing for the TLE download command."""

from __future__ import annotations

import argparse

FORMATS = {
    "tle": ".tle",
    "3le": ".tle",
    "2le": ".tle",
    "xml": ".xml",
    "kvn": ".omm",
    "omm": ".omm",
    "json": ".json",
    "json-pretty": ".json",
    "csv": ".csv",
}

FORMAT_ALIASES = {
    "omm": "kvn",
}


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for downloading TLE/OMM data."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Download TLE/OMM data from CelesTrak"
    )
    parser.add_argument(
        "satellite_ids",
        nargs="+",
        help="One or more satellite international designators",
    )
    parser.add_argument(
        "--format",
        dest="format",
        default="tle",
        choices=FORMATS.keys(),
        help="Output format (default: tle). Valid options: "
        + ", ".join(FORMATS.keys()),
    )
    return parser.parse_args()
