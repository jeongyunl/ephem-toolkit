#!/usr/bin/env python3
"""Slice and extract subsets of CCSDS OEM ephemeris data by index or time range.

This utility provides flexible slicing capabilities for OEM files:
- Index-based slicing: Extract states using Python-style slice notation
- Time-based slicing: Extract states within specific time windows
- Interpolation: Generate uniformly-spaced states at specified intervals
- Flexible output: Raw state vectors or full OEM format

Usage:
    python3 bin/slice_oem.py <oem_file> [OPTIONS]
    cat data.oem | python3 bin/slice_oem.py - [OPTIONS]
    cat data.oem | python3 bin/slice_oem.py [OPTIONS]

Index-based slicing examples:
    python3 bin/slice_oem.py data.oem --slice "0:10"
    python3 bin/slice_oem.py data.oem --slice "::2"
    python3 bin/slice_oem.py data.oem --slice "5"
    python3 bin/slice_oem.py data.oem --slice="-5:"
    cat data.oem | python3 bin/slice_oem.py --slice "0:10"

Time-based slicing examples:
    python3 bin/slice_oem.py data.oem --time-slice "0,1h"
    python3 bin/slice_oem.py data.oem --time-slice "2024-01-01T00:00:00,2024-01-02T00:00:00"
    python3 bin/slice_oem.py data.oem --time-slice "2024-01-01T12:00:00"
    python3 bin/slice_oem.py data.oem --time-slice="-30m,"
    cat data.oem | python3 bin/slice_oem.py - --time-slice "0,1h"

Interpolation examples:
    python3 bin/slice_oem.py data.oem --time-slice "0,1h,10m"
    python3 bin/slice_oem.py data.oem --time-slice "2024-01-01T00:00:00,2024-01-01T01:00:00,30s"
    python3 bin/slice_oem.py data.oem --time-slice="-1h,,5m"

Output format examples:
    python3 bin/slice_oem.py data.oem --slice "0:10" --raw
    python3 bin/slice_oem.py data.oem --time-slice "0,1h" > sliced.oem
    cat data.oem | python3 bin/slice_oem.py --time-slice "0,1h" > sliced.oem

For detailed documentation, see doc/SLICE_OEM.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.oem as oem
import common.slice_oem as slice_oem
import common.time_utils as time_utils


def _format_time_or_duration(value: datetime | timedelta | None) -> str:
    """Format datetime or timedelta as ISO-8601 string, or empty string if *None*.

    Parameters
    ----------
    value : datetime | timedelta | None
        Value to format.

    Returns
    -------
    str
        ISO-8601 datetime string, duration string (e.g., ``10h``), or empty string.
    """
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return time_utils.format_duration(value)
    return time_utils.datetime_to_iso8601(value)


def main() -> None:
    """Parse CLI arguments, slice OEM ephemeris data, and write results to stdout."""
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
        help="Enable Lagrange interpolation when step size is provided (enabled by default)",
    )
    parser.add_argument(
        "--no-interpolate",
        action="store_false",
        dest="interpolate",
        help="Disable interpolation",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw state vectors only (default: OEM format)",
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
                first_ts, _ = oem_data.states[0]
                last_ts, _ = oem_data.states[-1]
                first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
                last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
                span = last_dt - first_dt
                print(
                    f"[slice_oem]   Start: {time_utils.datetime_to_iso8601(first_dt)}",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   End:   {time_utils.datetime_to_iso8601(last_dt)}",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   Span:  {time_utils.format_duration_human(span)}",
                    file=sys.stderr,
                )
            print(file=sys.stderr)

        sliced_oem = None

        if args.time_slice:
            time_slice_opts = slice_oem.parse_time_slice_args(args.time_slice)
            time_slice_opts.interpolate = args.interpolate
            if (
                time_slice_opts.step_size is not None
                and not time_slice_opts.interpolate
            ):
                parser.error("step_size requires --interpolate")

            # Time slice extraction with optional interpolation
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data, time_slice_opts, verbose=args.verbose
            )

        elif args.slice:
            slice_obj = slice_oem.parse_slice_args(args.slice)
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data, slice_obj, verbose=args.verbose
            )

        if sliced_oem is not None:
            # Determine output destination
            if args.output == "-":
                output_file = sys.stdout
            else:
                output_file = open(args.output, "w")

            try:
                if args.raw:
                    oem.write_states(output_file, sliced_oem.states)
                else:
                    sliced_oem.write(output_file)
            finally:
                if args.output != "-":
                    output_file.close()


if __name__ == "__main__":
    main()
