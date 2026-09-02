#!/usr/bin/env python3
"""Convert a Two-Line Element (TLE) set to a CCSDS OMM file.

Reads a TLE from a file path or stdin and writes the resulting OMM to
stdout or a file. Provides command-line interface for TLE-to-OMM conversion.
"""

from __future__ import annotations

import io
import sys

import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.tle as tle

from .tle_to_omm_cli import TleToOmmArgs
from .tle_to_omm_cli import build_arg_parser, parse_arguments


def main(argv=None) -> None:
    """Execute the TLE-to-OMM conversion workflow.

    Reads TLE from the configured source, converts to OMM, and writes the
    result to the configured destination. Exits with status 1 on error.
    """
    cli_parser = build_arg_parser()
    cli_args: TleToOmmArgs = parse_arguments(cli_parser, argv)

    if cli_args.input_tle == "-":
        input_text: str = sys.stdin.read()
        if not input_text.strip():
            print("Error: no input from stdin", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(cli_args.input_tle, "r", encoding="utf-8") as input_file:
                input_text = input_file.read()
        except OSError as error:
            print(
                f"Error: could not read input file '{cli_args.input_tle}': {error}",
                file=sys.stderr,
            )
            sys.exit(1)

        if not input_text.strip():
            print(f"Error: input file '{cli_args.input_tle}' is empty", file=sys.stderr)
            sys.exit(1)

    try:
        tle_data: tle.Tle = tle.read_tle(io.StringIO(input_text))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    omm_data: object = convert_tle.tle_to_omm(tle_data)

    if cli_args.output_omm == "-":
        omm_data.to_file(sys.stdout)
    else:
        omm_data.to_file(cli_args.output_omm)


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
