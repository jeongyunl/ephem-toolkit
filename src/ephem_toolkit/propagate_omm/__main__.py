#!/usr/bin/env python3
"""Command-line entry point for OMM/TLE propagation."""

from __future__ import annotations

from .propagate_omm_cli import build_arg_parser, parse_arguments


def main(argv=None) -> int:
    """Execute the OMM propagation workflow."""
    cli_args = parse_arguments(build_arg_parser(), argv)

    import datetime as dt

    import ephem_toolkit.core.time_utils as time_utils
    import ephem_toolkit.core.tle as tle_mod

    from .propagation import (
        propagate_omm_dsst,
        propagate_omm_kepler,
        propagate_omm_sgp4,
        propagate_tle_sgp4,
        read_omm_input,
        read_tle_input,
        resolve_time_bounds,
    )

    tle_data = None
    omm_data = None
    if cli_args.is_tle:
        tle_data = read_tle_input(cli_args.input_file)
        if tle_data is None:
            raise ValueError("TLE input did not produce TLE data")
        reference_dt = tle_mod.tle_epoch_to_datetime(
            tle_data.epoch_year, tle_data.epoch_day
        )
    else:
        omm_data = read_omm_input(cli_args.input_file)
        if omm_data is None:
            raise ValueError("OMM input did not produce OMM data")
        reference_dt = time_utils.iso8601_to_datetime(omm_data.epoch)

    start_spec = (
        dt.timedelta(0)
        if cli_args.start is None
        else time_utils.parse_time_or_duration(cli_args.start)
    )
    stop_spec = (
        dt.timedelta(seconds=cli_args.duration_s)
        if cli_args.stop is None
        else time_utils.parse_time_or_duration(cli_args.stop)
    )
    start_time, stop_time = resolve_time_bounds(
        reference_dt, start_spec, stop_spec, cli_args.duration_s
    )

    if cli_args.step <= 0.0:
        raise ValueError("--step must be > 0")

    if cli_args.is_tle:
        assert tle_data is not None
        propagate_tle_sgp4(
            tle_data,
            start_time,
            stop_time,
            cli_args.step,
            cli_args.data_only,
            cli_args.output_oem,
        )
    else:
        assert omm_data is not None
        if omm_data.tle_parameters is not None:
            propagate_omm_sgp4(
                omm_data,
                start_time,
                stop_time,
                cli_args.step,
                cli_args.data_only,
                cli_args.output_oem,
            )
        elif omm_data.mean_element_theory.upper() == "DSST":
            propagate_omm_dsst(
                omm_data,
                start_time,
                stop_time,
                cli_args.step,
                cli_args.data_only,
                cli_args.output_oem,
            )
        else:
            propagate_omm_kepler(
                omm_data,
                start_time,
                stop_time,
                cli_args.step,
                cli_args.data_only,
                cli_args.output_oem,
            )

    return 0


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
