"""CLI argument parsing for the OMM-to-TLE conversion command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


class OmmToTleArgs(argparse.Namespace):
    """Typed argument namespace for the OMM-to-TLE CLI."""

    input_omm: str
    """Input OMM path or '-' for stdin."""
    output_tle: str | None
    """Output TLE path or '-' for stdout."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    cli_parser = cli.build_arg_parser(
        description=(
            "Convert a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element "
            "(TLE) set. Reads OMM from a file path or stdin and writes TLE to stdout "
            "or a file."
        ),
        epilog=(
            "Examples:\n"
            "  omm-to-tle input.omm -o -\n"
            "  cat input.omm | omm-to-tle - -o -\n"
            "  omm-to-tle input.omm -o output.tle"
        ),
    )
    cli_parser.prog = "omm-to-tle"
    cli_parser.add_argument(
        "input_omm",
        metavar="<input_omm|->",
        help='Input OMM file path; use "-" to read OMM text from stdin.',
    )
    cli_parser.add_argument(
        "-o",
        "--output",
        dest="output_tle",
        metavar="<output_tle|->",
        required=True,
        help="Output TLE file path; '-' writes to stdout.",
    )
    return cli_parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> OmmToTleArgs:
    """Parse command-line arguments for OMM-to-TLE conversion."""
    return parser.parse_args(argv, namespace=OmmToTleArgs())
