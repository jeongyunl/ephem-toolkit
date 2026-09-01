#!/usr/bin/env python3
"""OEM-to-TLE wrapper around the OEM-to-OMM conversion command."""

from __future__ import annotations

import sys
import io
import argparse
from contextlib import redirect_stdout

from ephem_toolkit.oem_to_omm import __main__ as oem_to_omm
from ephem_toolkit.omm_to_tle import omm_to_tle


def _print_help(argv: list[str]) -> None:
    """Print help for the OEM-to-TLE wrapper when requested."""
    if "-h" not in argv and "--help" not in argv:
        return

    parser = argparse.ArgumentParser(
        prog="oem-to-tle",
        description="Convert OEM state vectors to a TLE.",
        epilog=(
            "Examples:\n"
            "  oem-to-tle input.oem -o output.tle\n"
            "  cat input.oem | oem-to-tle - -o output.tle"
        ),
    )
    parser.add_argument(
        "input_oem",
        metavar="<input_oem|->",
        help='Path to input CCSDS OEM file; use "-" to read from stdin',
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<output_tle|->",
        required=True,
        help="Output TLE file path; '-' writes to stdout",
    )
    parser.add_argument(
        "-v", "--verbose", help="Print detailed debug information", action="store_true"
    )
    parser.add_argument(
        "--fit-span",
        metavar="<duration>",
        help="Maximum arc span for the fit (e.g. 2h, 90m)",
    )
    parser.add_argument(
        "--object-name", metavar="<name>", help="Spacecraft name for OMM output"
    )
    parser.add_argument(
        "--object-id",
        metavar="<YYYY-NNNP>",
        help="International designator for OMM output",
    )
    parser.add_argument(
        "--tle-refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        help="Refinement method for TLE fitting",
    )
    parser.add_argument(
        "--tle-norad-cat-id", metavar="<0..99999>", help="NORAD Catalog Number"
    )
    parser.add_argument(
        "--tle-classification-type",
        choices=["U", "C", "S"],
        help="TLE classification type",
    )
    parser.add_argument(
        "--tle-ephemeris-type", metavar="<0..9>", help="TLE ephemeris type"
    )
    parser.add_argument(
        "--tle-element-set-no", metavar="<0..9999>", help="TLE element set number"
    )
    parser.add_argument(
        "--tle-rev-at-epoch",
        metavar="<0..99999>",
        help="TLE revolution number at epoch",
    )
    parser.parse_args(argv)
    raise AssertionError("argparse help should exit")


def main(argv=None) -> None:
    """Invoke the OEM-to-OMM workflow in TLE conversion mode."""
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    _print_help(argv)

    filtered_arguments: list[str] = []
    output_tle: str | None = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--mode":
            raise SystemExit("oem-to-tle: error: unrecognized argument: --mode")
        if argument.startswith("--mode="):
            raise SystemExit(f"oem-to-tle: error: unrecognized argument: {argument}")
        if argument in ("-o", "--output"):
            filtered_arguments.append(argument)
            if index + 1 < len(argv):
                output_tle = argv[index + 1]
                filtered_arguments.append("-")
            index += 2
            continue
        if argument.startswith("--output="):
            output_tle = argument.partition("=")[2]
            filtered_arguments.append("--output=-")
            index += 1
            continue
        filtered_arguments.append(argument)
        index += 1

    omm_output = io.StringIO()
    with redirect_stdout(omm_output):
        oem_to_omm.main(["--mode", "tle", *filtered_arguments])

    original_stdin = sys.stdin
    sys.stdin = io.StringIO(omm_output.getvalue())
    try:
        omm_to_tle.main(["-", "-o", output_tle or "-"])
    finally:
        sys.stdin = original_stdin


if __name__ == "__main__":
    main()
