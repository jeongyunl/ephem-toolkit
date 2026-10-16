"""CLI argument parsing for OEM playback."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import ephem_toolkit.core.cli as cli


class PlayOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM playback CLI."""

    input_oem: str
    """Path to the input CCSDS OEM file."""
    duration: str | None
    """Optional analysis duration string."""
    time_unit: str
    """Time unit used in time-series plots."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for OEM playback."""
    parser = cli.build_arg_parser(
        description="Interactively explore and play a CCSDS OEM ephemeris.",
        epilog=(
            "Examples:\n"
            "  play-oem orbit.oem\n"
            "  play-oem orbit.oem -d 6h --time-unit minutes"
        ),
    )
    parser.prog = "play-oem"
    parser.add_argument(
        "input_oem",
        type=str,
        metavar="<input_oem>",
        help="Path to the input CCSDS OEM file.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        dest="duration",
        type=str,
        default=None,
        metavar="<duration>",
        help="Duration to analyze from the start (e.g., 1h, 30m, or 3600s).",
    )
    parser.add_argument(
        "--time-unit",
        dest="time_unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help=(
            "Time unit for time-series plots: "
            "m/minute/minutes or h/hour/hours (default: hours)."
        ),
    )
    return parser


def parse_arguments(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None = None,
) -> PlayOemArgs:
    """Parse command-line arguments for OEM playback."""
    return parser.parse_args(argv, namespace=PlayOemArgs())
