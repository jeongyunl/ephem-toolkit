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
    from contextlib import redirect_stdout

    import ephem_toolkit.core.ccsds.omm as omm
    import ephem_toolkit.core.convert_tle as convert_tle
    import ephem_toolkit.core.provenance as provenance
    import ephem_toolkit.core.time_utils as time_utils
    import ephem_toolkit.core.tle as tle

    try:
        source_model, source_report = provenance.resolve_source_model(
            cli_args.source_model, cli_args.source_report
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    if not cli_args.refit_sgp4 and (
        cli_args.fit_report is not None
        or cli_args.no_fit_report
        or cli_args.source_model != "auto"
        or cli_args.source_report is not None
    ):
        cli_parser.error(
            "fit/provenance options require --refit-sgp4; direct conversion is lossless"
        )

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

    if cli_args.refit_sgp4:
        if cli_args.output_tle == "-" and cli_args.fit_report == "-":
            cli_parser.error("--output and --fit-report cannot both be '-'")
        try:
            from ephem_toolkit.propagate_omm.propagation import (
                propagate_omm_dsst,
                propagate_omm_kepler,
                propagate_omm_sgp4,
            )
            from ephem_toolkit.oem_to_omm import fit_tle_main
            import ephem_toolkit.core.ccsds.oem as oem

            reference_time = time_utils.iso8601_to_datetime(omm_data.epoch)
            stop_time = reference_time + cli_args.fit_span
            propagated_output = io.StringIO()
            with redirect_stdout(propagated_output):
                if omm_data.tle_parameters is not None:
                    propagate_omm_sgp4(
                        omm_data, reference_time, stop_time, 60.0, False, "-"
                    )
                elif omm_data.mean_element_theory.upper() == "DSST":
                    propagate_omm_dsst(
                        omm_data, reference_time, stop_time, 60.0, False, "-"
                    )
                else:
                    propagate_omm_kepler(
                        omm_data, reference_time, stop_time, 60.0, False, "-"
                    )
            reference_oem = oem.CcsdsOem.read(
                io.StringIO(propagated_output.getvalue())
            )
            tle_data, diagnostics = fit_tle_main.fit_tle(
                reference_oem.states,
                cli_args.fit_span.total_seconds(),
                refinement_method="cartesian",
                object_name=omm_data.object_name or "OBJECT",
                object_id=omm_data.object_id or "UNKNOWN",
                norad_cat_id=(
                    omm_data.tle_parameters.norad_cat_id
                    if omm_data.tle_parameters is not None
                    else 0
                ),
            )
            report_path = None if cli_args.no_fit_report else (
                cli_args.fit_report
                or provenance.default_fit_report_path(
                    cli_args.input_omm, cli_args.output_tle
                )
            )
            if report_path:
                if source_model == "auto":
                    source_model = omm_data.mean_element_theory
                provenance.write_fit_report(
                    report_path,
                    provenance={
                        "source": f"OMM/{source_model}",
                        "transformation": "SGP4 refit",
                        "target_model": "SGP4",
                    },
                    diagnostics=diagnostics,
                    configuration={
                        "fit_model": "sgp4",
                        "fit_span_s": cli_args.fit_span.total_seconds(),
                        "source_theory": omm_data.mean_element_theory,
                    },
                    source_report=source_report,
                )
        except (OSError, ValueError, RuntimeError) as error:
            print(f"Error refitting OMM to SGP4: {error}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            convert_tle.validate_sgp4_compatible_omm(omm_data)
            tle_data = convert_tle.omm_to_tle(omm_data)
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
