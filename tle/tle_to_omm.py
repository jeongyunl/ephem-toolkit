#!/usr/bin/env python3

import argparse
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import common.convert_tle as convert_tle
import common.tle as tle


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Convert a Two-Line Element (TLE) set to a CCSDS Orbit Mean-Elements "
            "Message (OMM). Reads TLE from a file path or stdin and writes OMM to "
            "stdout or a file."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.tle>",
        help=(
            "Input TLE file path. Use '-' or omit this argument to read TLE text "
            "from stdin (default: '-')."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<output.omm>",
        default=None,
        help="Output OMM file path. If omitted, OMM is printed to stdout.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.input == "-":
        input_text = sys.stdin.read()
        if not input_text.strip():
            print("Error: no input from stdin", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(args.input, "r") as input_file:
                input_text = input_file.read()
        except OSError as error:
            print(f"Error: could not read input file '{args.input}': {error}", file=sys.stderr)
            sys.exit(1)

        if not input_text.strip():
            print(f"Error: input file '{args.input}' is empty", file=sys.stderr)
            sys.exit(1)

    try:
        tle_data = tle.read_tle(io.StringIO(input_text))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    omm_data = convert_tle.tle_to_omm(tle_data)

    if args.output:
        omm_data.to_file(args.output)
    else:
        omm_data.to_file(sys.stdout)


if __name__ == "__main__":
    main()
