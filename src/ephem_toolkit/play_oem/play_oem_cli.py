"""CLI argument parsing for OEM playback."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


class PlayOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM playback CLI."""

    input_oem: str
    """Path to the input CCSDS OEM file."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for OEM playback."""
    parser = cli.build_arg_parser(
        description="Interactively play a CCSDS OEM ephemeris.",
        epilog="Example:\n  play-oem orbit.oem",
    )
    parser.prog = "play-oem"
    parser.add_argument(
        "input_oem",
        type=str,
        metavar="<input_oem>",
        help="Path to the input CCSDS OEM file.",
    )
    return parser


def parse_arguments(
    parser: argparse.ArgumentParser,
    argv: list[str] | None = None,
) -> PlayOemArgs:
    """Parse command-line arguments for OEM playback."""
    return parser.parse_args(argv, namespace=PlayOemArgs())
