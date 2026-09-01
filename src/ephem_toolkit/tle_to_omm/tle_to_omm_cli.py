"""CLI argument parsing for the TLE-to-OMM conversion command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


class TleToOmmArgs(argparse.Namespace):
    """Typed argument namespace for the TLE-to-OMM CLI."""

    input_tle: str
    """Input TLE path or '-' for stdin."""
    output_omm: str | None
    """Output OMM path or '-' for stdout."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    cli_parser = cli.build_arg_parser(
        description=(
            "Convert a Two-Line Element (TLE) set to a CCSDS Orbit Mean-Elements "
            "Message (OMM). Reads TLE from a file path or stdin and writes OMM to "
            "stdout or a file."
        ),
        epilog=(
            "Examples:\n"
            "  tle-to-omm input.tle -o -\n"
            "  cat input.tle | tle-to-omm - -o -\n"
            "  tle-to-omm input.tle -o output.omm"
        ),
    )
    cli_parser.prog = "tle-to-omm"
    cli_parser.add_argument(
        "input_tle",
        metavar="<input_tle|->",
        help='Input TLE file path; use "-" to read TLE text from stdin.',
    )
    cli_parser.add_argument(
        "-o",
        "--output",
        dest="output_omm",
        metavar="<output_omm|->",
        required=True,
        help="Output OMM file path; use '-' to write to stdout.",
    )
    return cli_parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> TleToOmmArgs:
    """Parse command-line arguments for TLE-to-OMM conversion."""
    return parser.parse_args(argv, namespace=TleToOmmArgs())
