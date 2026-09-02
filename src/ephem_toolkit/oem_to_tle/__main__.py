#!/usr/bin/env python3
"""OEM-to-TLE wrapper around the OEM-to-OMM conversion command."""

from __future__ import annotations

import sys
import io
import importlib
from contextlib import redirect_stdout

from ephem_toolkit.oem_to_omm import __main__ as oem_to_omm
from ephem_toolkit.oem_to_omm.oem_to_omm_cli import build_common_arg_parser

omm_to_tle = importlib.import_module("ephem_toolkit.omm_to_tle.__main__")


def main(argv=None) -> None:
    """Invoke the OEM-to-OMM workflow in TLE conversion mode."""
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    cli_parser = build_common_arg_parser(
        prog="oem-to-tle",
        description="Convert OEM state vectors to a TLE.",
        epilog=(
            "Examples:\n"
            "  oem-to-tle input.oem -o output.tle\n"
            "  cat input.oem | oem-to-tle - -o output.tle"
        ),
        output_dest="output_tle",
        output_metavar="<output_tle|->",
        object_name_help="Satellite name.",
        object_id_help="International designator.",
    )
    cli_args = cli_parser.parse_args(argv)
    output_tle = cli_args.output_tle

    filtered_arguments: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-o", "--output"):
            filtered_arguments.extend(["-o", "-"])
            if index + 1 < len(argv):
                index += 2
            else:
                index += 1
            continue
        if argument.startswith("--output="):
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


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
