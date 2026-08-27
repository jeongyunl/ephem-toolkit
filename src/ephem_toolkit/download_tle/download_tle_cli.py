"""CLI argument parsing for the TLE download command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli

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


class DownloadTleArgs(argparse.Namespace):
    """Typed argument namespace for the TLE download CLI."""

    satellite_ids: list[str]
    """Satellite designators to download."""
    format: str
    """Requested output format."""


def parse_arguments(argv=None) -> DownloadTleArgs:
    """Parse command-line arguments for downloading TLE/OMM data."""
    parser: argparse.ArgumentParser = cli.create_parser(
        description="Download TLE/OMM data from CelesTrak.",
        epilog=(
            "Examples:\n"
            "  download-tle --satellite-id 1998-067A\n"
            "  download-tle --satellite-id 1998-067A --satellite-id 2019-050A\n"
            "  download-tle --format omm --satellite-id 1998-067A"
        ),
    )
    parser.prog = "download-tle"
    parser.add_argument(
        "--satellite-id",
        dest="satellite_ids",
        action="append",
        default=[],
        metavar="<id>",
        help="Satellite international designator; repeat this option for multiple satellites.",
    )
    parser.add_argument(
        "--format",
        dest="format",
        default="tle",
        choices=FORMATS.keys(),
        help="Output format (default: tle). Valid options: "
        + ", ".join(FORMATS.keys()),
    )
    return parser.parse_args(argv, namespace=DownloadTleArgs())
