#!/usr/bin/env python3
"""Convert a CCSDS OMM file to a Two-Line Element (TLE) set.

Reads an OMM from a file path or stdin and writes the resulting TLE to
stdout or a file.
"""

from __future__ import annotations

import argparse
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.convert_tle as convert_tle
import common.omm as omm
import common.tle as tle


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for OMM-to-TLE conversion.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes ``input`` and ``output``.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Convert a CCSDS Orbit Mean-Elements Message (OMM) to a Two-Line Element "
            "(TLE) set. Reads OMM from a file path or stdin and writes TLE to stdout "
            "or a file."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.omm>",
        help=(
            "Input OMM file path. Use '-' or omit this argument to read OMM text "
            "from stdin (default: '-')."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<output.tle>",
        default=None,
        help="Output TLE file path. If omitted, TLE is printed to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    """Execute the OMM-to-TLE conversion workflow.

    Reads OMM from the configured source, converts to TLE, and writes the
    result to the configured destination. Exits with status 1 on error.
    """
    args: argparse.Namespace = parse_arguments()

    if args.input == "-":
        input_text: str = sys.stdin.read()
        if not input_text.strip():
            print("Error: no input from stdin", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(args.input, "r") as input_file:
                input_text = input_file.read()
        except OSError as error:
            print(
                f"Error: could not read input file '{args.input}': {error}",
                file=sys.stderr,
            )
            sys.exit(1)

        if not input_text.strip():
            print(f"Error: input file '{args.input}' is empty", file=sys.stderr)
            sys.exit(1)

    try:
        omm_data: omm.CcsdsOmm = omm.CcsdsOmm.from_source(io.StringIO(input_text))
    except (ValueError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    tle_data: tle.Tle = convert_tle.omm_to_tle(omm_data)

    if args.output:
        tle.write_tle(args.output, tle_data)
    else:
        tle.write_tle(sys.stdout, tle_data)


if __name__ == "__main__":
    main()
