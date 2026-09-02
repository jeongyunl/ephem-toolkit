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

    format: str
    """Requested output format."""

    satellite_ids: list[str]
    """Satellite designators to download."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser: argparse.ArgumentParser = cli.build_arg_parser(
        description="Download TLE/OMM data from CelesTrak.",
        epilog=(
            "Examples:\n"
            "  download-tle 1998-067A\n"
            "  download-tle 1998-067A 2019-050A\n"
            "  download-tle --format omm 1998-067A"
        ),
    )
    parser.prog = "download-tle"
    parser.add_argument(
        "--format",
        dest="format",
        default="tle",
        choices=FORMATS.keys(),
        help="Output format (default: tle). Valid options: "
        + ", ".join(FORMATS.keys()),
    )
    parser.add_argument(
        "satellite_ids",
        nargs="+",
        metavar="<id>",
        help="Satellite international designator(s).",
    )
    return parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> DownloadTleArgs:
    """Parse command-line arguments for downloading TLE/OMM data."""
    return parser.parse_args(argv, namespace=DownloadTleArgs())
