#!/usr/bin/env python3
"""OEM-to-TLE wrapper around the OEM-to-OMM conversion command."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv=None) -> None:
    """Invoke the OEM-to-OMM workflow in TLE conversion mode."""
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    from ephem_toolkit.oem_to_omm.oem_to_omm_cli import build_common_arg_parser

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

    from ephem_toolkit.core.provenance import default_fit_report_path

    if cli_args.no_fit_report and cli_args.fit_report:
        cli_parser.error("--fit-report and --no-fit-report cannot be used together")
    fit_report = None if cli_args.no_fit_report else (
        cli_args.fit_report or default_fit_report_path(
            cli_args.input_oem, cli_args.output_tle
        )
    )

    if cli_args.output_tle == "-" and fit_report == "-":
        cli_parser.error("--output and --fit-report cannot both be '-' because they are different formats")

    import io
    import tempfile
    from contextlib import redirect_stdout
    import ephem_toolkit.oem_to_omm as oem_to_omm
    import ephem_toolkit.omm_to_tle as omm_to_tle

    output_tle = cli_args.output_tle

    filtered_arguments: list[str] = []
    report_stdout = False
    report_file = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-o", "--output"):
            filtered_arguments.extend(["-o", "-"])
            index += 2
            continue
        if argument.startswith("--output="):
            filtered_arguments.append("--output=-")
            index += 1
            continue
        if argument in ("--fit-report", "--source-report") and index + 1 < len(argv):
            value = argv[index + 1]
            if argument == "--fit-report" and value == "-":
                report_stdout = True
                report_file = tempfile.NamedTemporaryFile(prefix="oem-to-tle-fit-", suffix=".json", delete=False)
                report_file.close()
                filtered_arguments.extend([argument, report_file.name])
            else:
                filtered_arguments.extend([argument, value])
            index += 2
            continue
        filtered_arguments.append(argument)
        index += 1

    if fit_report is not None and not any(
        argument == "--fit-report" or argument.startswith("--fit-report=")
        for argument in filtered_arguments
    ):
        filtered_arguments.extend(["--fit-report", str(fit_report)])

    omm_output = io.StringIO()
    try:
        with redirect_stdout(omm_output):
            oem_to_omm.main(["--fit-model", "sgp4", *filtered_arguments])

        original_stdin = sys.stdin
        sys.stdin = io.StringIO(omm_output.getvalue())
        try:
            omm_to_tle.main(["-", "-o", output_tle or "-"])
        finally:
            sys.stdin = original_stdin

        if report_stdout and report_file is not None:
            sys.stdout.write(Path(report_file.name).read_text(encoding="utf-8"))
    finally:
        if report_file is not None:
            import os

            os.unlink(report_file.name)


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
