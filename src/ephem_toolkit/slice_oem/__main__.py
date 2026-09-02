#!/usr/bin/env python3
"""Slice and extract subsets of CCSDS OEM ephemeris data by index or time range.

This utility provides flexible slicing capabilities for OEM files:
- Index-based slicing: Extract states using Python-style slice notation
- Time-based slicing: Extract states within specific time windows
- Interpolation: Generate uniformly-spaced states at specified intervals
- Flexible output: State data only or full OEM format

Usage:
    slice-oem <input_oem> [OPTIONS]
    cat data.oem | slice-oem - [OPTIONS]
    slice-oem - [OPTIONS]

Index-based slicing examples:
    slice-oem data.oem --slice "0:10"
    slice-oem data.oem --slice "::2"
    slice-oem data.oem --slice "5"
    slice-oem data.oem --slice="-5:"
    cat data.oem | slice-oem - --slice "0:10"

Time-based slicing examples:
    slice-oem data.oem --time-slice "0,1h"
    slice-oem data.oem --time-slice "2024-01-01T00:00:00,2024-01-02T00:00:00"
    slice-oem data.oem --time-slice "2024-01-01T12:00:00"
    slice-oem data.oem --time-slice="-30m,"
    cat data.oem | slice-oem - --time-slice "0,1h"

Interpolation examples:
    slice-oem data.oem --time-slice "0,1h,10m"
    slice-oem data.oem --time-slice "2024-01-01T00:00:00,2024-01-01T01:00:00,30s"
    slice-oem data.oem --time-slice="-1h,,5m"

Output format examples:
    slice-oem data.oem --slice "0:10" --data-only
    slice-oem data.oem --time-slice "0,1h" > sliced.oem
    slice-oem data.oem --time-slice "0,1h" -o -
    cat data.oem | slice-oem - --time-slice "0,1h" -o -
    slice-oem data.oem --slice "5" --opm -o state.opm
    cat data.oem | slice-oem - --slice "5" --opm -o -

For detailed documentation, see doc/SLICE_OEM.md
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.interpolator.interpolation_spec as interpolation_spec
import ephem_toolkit.core.slice_oem as slice_oem
import ephem_toolkit.core.time_utils as time_utils

if __package__ in {None, ""}:
    from slice_oem_cli import SliceOemArgs, build_arg_parser, parse_arguments
else:
    from .slice_oem_cli import SliceOemArgs, build_arg_parser, parse_arguments

DEFAULT_INTERPOLATION_TYPE: str = "hermite"
"""Default interpolation method."""

DEFAULT_INTERPOLATION_DEGREE: int = 5
"""Default polynomial degree for interpolation (Hermite default)."""

DEFAULT_INTERPOLATION_SPEC: interpolation_spec.InterpolationSpec = (
    interpolation_spec.InterpolationSpec(
        interp_type=interpolation_spec.InterpolationType.HERMITE,
        degree=DEFAULT_INTERPOLATION_DEGREE,
    )
)
"""Default interpolation specification."""


def main(argv=None) -> None:
    """Parse CLI arguments, slice OEM ephemeris data, and write results to stdout."""
    cli_parser = build_arg_parser()
    cli_args: SliceOemArgs = parse_arguments(cli_parser, argv)

    # Determine if reading from stdin
    read_from_stdin = cli_args.input_oem == "-"

    # Ensure at least one slicing option is provided when processing OEM data
    if not cli_args.time_slice and not cli_args.slice:
        # If no slice options and no file, just exit successfully (no-op)
        if read_from_stdin:
            return
        raise SystemExit("Error: either -s/--slice or -t/--time-slice must be provided")

    if cli_args.time_slice or cli_args.slice:
        # Read OEM data from stdin or file
        if read_from_stdin:
            oem_data = oem.CcsdsOem.read(sys.stdin)
            oem_file = "<stdin>"
        else:
            oem_file = Path(cli_args.input_oem)
            oem_data = oem.CcsdsOem.read(oem_file)

        if (
            cli_args.time_slice
            and cli_args.interpolate
            and len(oem_data.states) < cli_args.interpolate_type.degree
        ):
            print(
                "Warning: input contains "
                f"{len(oem_data.states)} states, fewer than the requested "
                f"interpolation degree {cli_args.interpolate_type.degree}; "
                "the degree will be reduced to fit the available data.",
                file=sys.stderr,
            )

        if cli_args.verbose:
            total_states = len(oem_data.states)
            print(f"[slice_oem] Input OEM:", file=sys.stderr)
            print(f"[slice_oem]   File: {oem_file}", file=sys.stderr)
            print(f"[slice_oem]   Object: {oem_data.meta.object_name}", file=sys.stderr)
            print(
                f"[slice_oem]   Reference frame: {oem_data.meta.ref_frame}",
                file=sys.stderr,
            )
            print(f"[slice_oem]   Center: {oem_data.meta.center_name}", file=sys.stderr)
            print(
                f"[slice_oem]   Time system: {oem_data.meta.time_system}",
                file=sys.stderr,
            )
            print(f"[slice_oem]   States: {total_states}", file=sys.stderr)

            if total_states > 0:
                first_timestamp, _ = oem_data.states[0]
                last_timestamp, _ = oem_data.states[-1]
                first_datetime = time_utils.tt_s_to_datetime(first_timestamp)
                last_datetime = time_utils.tt_s_to_datetime(last_timestamp)
                duration = last_datetime - first_datetime
                print(
                    "[slice_oem]   Start: "
                    f"{time_utils.datetime_to_iso8601(first_datetime)}",
                    file=sys.stderr,
                )
                print(
                    "[slice_oem]   End:   "
                    f"{time_utils.datetime_to_iso8601(last_datetime)}",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   Span:  {time_utils.format_duration_human(duration)}",
                    file=sys.stderr,
                )
            print(file=sys.stderr)

        sliced_oem = None

        if cli_args.time_slice:
            time_slice_options = slice_oem.parse_time_slice_args(cli_args.time_slice)

            # Set interpolation spec if interpolation is enabled
            if cli_args.interpolate:
                time_slice_options.interpolation_spec = cli_args.interpolate_type

            if (
                time_slice_options.step_size is not None
                and time_slice_options.interpolation_spec is None
            ):
                raise SystemExit("step_size requires --interpolate")

            if cli_args.opm:
                if cli_args.verbose:
                    print(
                        "[slice_oem] --opm selected: truncating time slice to single state",
                        file=sys.stderr,
                    )
                time_slice_options.stop_time = timedelta(0)
                time_slice_options.step_size = None

            # Time slice extraction with optional interpolation
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data,
                time_slice_options,
                verbose=cli_args.verbose,
            )

        elif cli_args.slice:
            slice_obj = slice_oem.parse_slice_args(cli_args.slice)

            if cli_args.opm:
                if cli_args.verbose:
                    print(
                        "[slice_oem] --opm selected: selecting first state only",
                        file=sys.stderr,
                    )
                slice_obj = slice(slice_obj.start, slice_obj.start + 1, None)

            sliced_oem = slice_oem.extract_sliced_states(
                oem_data,
                slice_obj,
                verbose=cli_args.verbose,
            )

        if sliced_oem is not None:
            emit_opm = cli_args.opm

            if cli_args.verbose:
                if emit_opm:
                    print(
                        "[slice_oem] Output format: OPM (--opm)",
                        file=sys.stderr,
                    )
                else:
                    print("[slice_oem] Output format: OEM", file=sys.stderr)

            if emit_opm and cli_args.data_only:
                raise SystemExit("--data-only cannot be used with OPM output")

            # Determine output destination
            if cli_args.output_path == "-":
                output_stream = sys.stdout
            else:
                output_stream = open(cli_args.output_path, "w", encoding="utf-8")

            try:
                if emit_opm:
                    if not sliced_oem.states:
                        raise SystemExit(
                            "OPM output requires at least one selected state"
                        )
                    epoch, state = sliced_oem.states[0]
                    first_state_opm = opm.CcsdsOpm(
                        header=opm.OpmHeader(
                            version=3.0,
                            comments=sliced_oem.header.comments,
                            classification=sliced_oem.header.classification,
                            creation_date=sliced_oem.header.creation_date,
                            originator=sliced_oem.header.originator,
                            message_id=sliced_oem.header.message_id,
                        ),
                        metadata={
                            key: value
                            for key, value in {
                                "OBJECT_NAME": sliced_oem.meta.object_name,
                                "OBJECT_ID": sliced_oem.meta.object_id,
                                "CENTER_NAME": sliced_oem.meta.center_name,
                                "REF_FRAME": sliced_oem.meta.ref_frame,
                                "REF_FRAME_EPOCH": sliced_oem.meta.ref_frame_epoch,
                                "TIME_SYSTEM": sliced_oem.meta.time_system,
                            }.items()
                            if value
                        },
                        state_vector=opm.OpmStateVector(
                            epoch=time_utils.datetime_to_iso8601(
                                time_utils.tt_s_to_datetime(epoch)
                            ),
                            x=state[0] / oem.KILOMETERS_TO_METERS,
                            y=state[1] / oem.KILOMETERS_TO_METERS,
                            z=state[2] / oem.KILOMETERS_TO_METERS,
                            x_dot=state[3] / oem.KILOMETERS_TO_METERS,
                            y_dot=state[4] / oem.KILOMETERS_TO_METERS,
                            z_dot=state[5] / oem.KILOMETERS_TO_METERS,
                        ),
                    )
                    first_state_opm.to_file(output_stream)
                elif cli_args.data_only:
                    sliced_oem.write_states(output_stream)
                else:
                    sliced_oem.write(output_stream)
            finally:
                if cli_args.output_path != "-":
                    output_stream.close()


def cli(argv=None) -> int:
    from ephem_toolkit.core.cli import run_cli

    return run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
