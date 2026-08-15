#!/usr/bin/env python3
"""Slice and extract subsets of CCSDS OEM ephemeris data by index or time range.

This utility provides flexible slicing capabilities for OEM files:
- Index-based slicing: Extract states using Python-style slice notation
- Time-based slicing: Extract states within specific time windows
- Interpolation: Generate uniformly-spaced states at specified intervals
- Flexible output: State data only or full OEM format

Usage:
    slice-oem <oem_file> [OPTIONS]
    cat data.oem | slice-oem - [OPTIONS]
    cat data.oem | slice-oem [OPTIONS]

Index-based slicing examples:
    slice-oem data.oem --slice "0:10"
    slice-oem data.oem --slice "::2"
    slice-oem data.oem --slice "5"
    slice-oem data.oem --slice="-5:"
    cat data.oem | slice-oem --slice "0:10"

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
    cat data.oem | slice-oem --time-slice "0,1h" > sliced.oem

For detailed documentation, see doc/SLICE_OEM.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.interpolator.interpolation_spec as interpolation_spec
import ephem_toolkit.core.slice_oem as slice_oem
import ephem_toolkit.core.time_utils as time_utils

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


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Extract subsets of CCSDS OEM ephemeris data by index or time range",
        epilog="For detailed documentation and examples, see doc/SLICE_OEM.md",
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        help='Path to input CCSDS OEM file (use "-" or omit to read from stdin)',
    )
    exclusive = parser.add_mutually_exclusive_group()
    exclusive.add_argument(
        "-s",
        "--slice",
        help="Python-style slice index (e.g., '0:10', '::2', '5', '-5:')",
        default=None,
    )
    exclusive.add_argument(
        "-t",
        "--time-slice",
        metavar="start[,[stop][,step]]",
        help=(
            "Time slice specifier: start[,[stop][,step]]. "
            "Start and stop may be ISO 8601 datetimes (e.g., 2024-01-01T00:00:00) "
            "or durations (e.g., 10m, 1h30m, 1d, -10m for offset from end). "
            "Step size is a duration (e.g., 30s, 5m, 1h) and enables interpolation by default. "
            "Use 0 for OEM start/end times. "
            "Examples: '0,1h' (first hour), '2024-01-01T12:00:00' (single state), "
            "'-30m,' (last 30 minutes), '0,1h,10m' (first hour at 10-minute intervals)"
        ),
        default=None,
    )
    parser.add_argument(
        "--interpolate",
        action="store_true",
        default=True,
        help="Enable interpolation when step size is provided (enabled by default)",
    )
    parser.add_argument(
        "--no-interpolate",
        action="store_false",
        dest="interpolate",
        help="Disable interpolation",
    )
    parser.add_argument(
        "--interpolate-type",
        type=partial(
            cli.parse_interpolate_type, default_degree=DEFAULT_INTERPOLATION_DEGREE
        ),
        default=DEFAULT_INTERPOLATION_SPEC,
        metavar="TYPE[,DEGREE]",
        help=(
            "Interpolation method: 'hermite[,degree]', 'chebyshev[,degree]', "
            "or 'lagrange[,degree]' "
            f"(default: {DEFAULT_INTERPOLATION_TYPE},{DEFAULT_INTERPOLATION_DEGREE}). "
            "Degree must be > 0"
        ),
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Output state vectors only (default: OEM format)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help=("Output file path (default: '-'). " "Use '-' to print to stdout."),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )

    args = parser.parse_args()

    return args


def main() -> None:
    """Parse CLI arguments, slice OEM ephemeris data, and write results to stdout."""
    args = parse_arguments()

    # Determine if reading from stdin
    read_from_stdin = args.oem_file is None or args.oem_file == "-"

    # Ensure at least one slicing option is provided when processing OEM data
    if not args.time_slice and not args.slice:
        # If no slice options and no file, just exit successfully (no-op)
        if read_from_stdin:
            return
        parser.error("either -s/--slice or -t/--time-slice must be provided")

    if args.time_slice or args.slice:
        # Read OEM data from stdin or file
        if read_from_stdin:
            oem_data = oem.CcsdsOem.read(sys.stdin)
            oem_file = "<stdin>"
        else:
            oem_file = Path(args.oem_file)
            oem_data = oem.CcsdsOem.read(oem_file)

        if (
            args.time_slice
            and args.interpolate
            and len(oem_data.states) < args.interpolate_type.degree
        ):
            print(
                "Warning: input contains "
                f"{len(oem_data.states)} states, fewer than the requested "
                f"interpolation degree {args.interpolate_type.degree}; "
                "the degree will be reduced to fit the available data.",
                file=sys.stderr,
            )

        if args.verbose:
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
                first_datetime = datetime.fromtimestamp(
                    first_timestamp, tz=timezone.utc
                )
                last_datetime = datetime.fromtimestamp(last_timestamp, tz=timezone.utc)
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

        if args.time_slice:
            time_slice_options = slice_oem.parse_time_slice_args(args.time_slice)

            # Set interpolation spec if interpolation is enabled
            if args.interpolate:
                time_slice_options.interpolation_spec = args.interpolate_type

            if (
                time_slice_options.step_size is not None
                and time_slice_options.interpolation_spec is None
            ):
                parser.error("step_size requires --interpolate")

            # Time slice extraction with optional interpolation
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data,
                time_slice_options,
                verbose=args.verbose,
            )

        elif args.slice:
            slice_obj = slice_oem.parse_slice_args(args.slice)
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data,
                slice_obj,
                verbose=args.verbose,
            )

        if sliced_oem is not None:
            # Determine output destination
            if args.output == "-":
                output_stream = sys.stdout
            else:
                output_stream = open(args.output, "w", encoding="utf-8")

            try:
                if args.data_only:
                    sliced_oem.write_states(output_stream)
                else:
                    sliced_oem.write(output_stream)
            finally:
                if args.output != "-":
                    output_stream.close()


if __name__ == "__main__":
    main()
