#!/usr/bin/env python3
"""Convert a CCSDS OMM file to a Two-Line Element (TLE) set.

Reads an OMM from a file path or stdin and writes the resulting TLE to
stdout or a file.
"""

from __future__ import annotations

from .omm_to_tle_cli import OmmToTleArgs, build_arg_parser, parse_arguments


def main(argv=None) -> None:
    """Execute the OMM-to-TLE conversion workflow.

    Reads OMM from the configured source, converts to TLE, and writes the
    result to the configured destination. Exits with status 1 on error.
    """
    cli_parser = build_arg_parser()
    cli_args: OmmToTleArgs = parse_arguments(cli_parser, argv)

    import io
    import sys

    import ephem_toolkit.core.ccsds.omm as omm
    import ephem_toolkit.core.convert_tle as convert_tle
    import ephem_toolkit.core.tle as tle

    if cli_args.input_omm == "-":
        input_text: str = sys.stdin.read()
        if not input_text.strip():
            print("Error: no input from stdin", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(cli_args.input_omm, "r", encoding="utf-8") as input_file:
                input_text = input_file.read()
        except OSError as error:
            print(
                f"Error: could not read input file '{cli_args.input_omm}': {error}",
                file=sys.stderr,
            )
            sys.exit(1)

        if not input_text.strip():
            print(f"Error: input file '{cli_args.input_omm}' is empty", file=sys.stderr)
            sys.exit(1)

    try:
        omm_data: omm.CcsdsOmm = omm.CcsdsOmm.from_source(io.StringIO(input_text))
    except (ValueError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    try:
        convert_tle.validate_sgp4_compatible_omm(omm_data)
        tle_data: tle.Tle = convert_tle.omm_to_tle(omm_data)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    if cli_args.output_tle == "-":
        tle.write_tle(sys.stdout, tle_data)
    elif cli_args.output_tle:
        tle.write_tle(cli_args.output_tle, tle_data)
    else:
        tle.write_tle(sys.stdout, tle_data)


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
