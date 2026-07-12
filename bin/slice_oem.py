#!/usr/bin/env python3
"""Slice and extract subsets of CCSDS OEM ephemeris data by index or time range.

Usage:
    python3 slice_oem.py <oem_file> [--slice SLICE | --time-slice TIME_SLICE] [--interpolate] [--raw]

Examples:
    python3 slice_oem.py data.oem --slice "0:10"
    python3 slice_oem.py data.oem --time-slice "2024-01-01T00:00:00Z,2024-01-02T00:00:00Z,1h" --interpolate
    python3 slice_oem.py data.oem --slice "0:10" --raw
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.common as common
import common.oem as oem
import common.slice_oem as slice_oem
import common.time_utils as time_utils


def _format_time_or_duration(value: datetime | timedelta | None) -> str:
    """Format datetime or timedelta as ISO-8601 string, or empty string if *None*."""
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return _format_duration(value)
    return time_utils.datetime_to_iso8601(value)


def _format_duration(duration: timedelta) -> str:
    """Return canonical duration string (e.g., ``10h``, ``30m``, ``45s``)."""
    total_seconds: float = duration.total_seconds()
    if total_seconds % 3600 == 0:
        hours: float = total_seconds / 3600
        return f"{hours:g}h"
    if total_seconds % 60 == 0:
        minutes: float = total_seconds / 60
        return f"{minutes:g}m"
    return f"{total_seconds:g}s"


def main() -> None:
    """Parse CLI arguments, slice OEM ephemeris data, and write results to stdout."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Load and slice CCSDS OEM file states"
    )
    parser.add_argument("oem_file", nargs="?", help="Path to OEM file")
    exclusive: argparse._MutuallyExclusiveGroup = parser.add_mutually_exclusive_group()
    exclusive.add_argument(
        "-s",
        "--slice",
        help="Python-style slice index (e.g., '0:10', '::2', '5', '-5:')",
        default=None,
    )
    exclusive.add_argument(
        "-t",
        "--time-slice",
        metavar="start[,stop[,step]]",
        help=(
            "Time slice specifier using comma-separated values. "
            "Format: start,stop,step. "
            "Start and stop may be ISO-8601 datetimes or durations like 10m, 1h30m, 1d, or -10m for a relative end offset. "
            "Step size is a duration such as 30s, 5m, or 1h. "
            "If stop is omitted, only one matching state is returned."
        ),
        default=None,
    )
    parser.add_argument(
        "-i",
        "--interpolate",
        action="store_true",
        help="Enable interpolation when a step size is provided",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Write sliced results in raw format (state vectors only)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose debug information to stderr",
    )

    args = parser.parse_args()

    if args.time_slice or args.slice:
        if args.time_slice:
            time_slice_opts = slice_oem.parse_time_slice_args(args.time_slice)
            time_slice_opts.interpolate = args.interpolate
            if (
                time_slice_opts.step_size is not None
                and not time_slice_opts.interpolate
            ):
                parser.error("step_size requires --interpolate")
            if args.oem_file is None:
                print(_format_time_or_duration(time_slice_opts.start_time))
                print(_format_time_or_duration(time_slice_opts.stop_time))
                print(_format_time_or_duration(time_slice_opts.step_size))
                return

        oem_file = Path(args.oem_file)
        oem_data = oem.CcsdsOem.read(oem_file)

        if args.time_slice:
            # Timedelta resolution is now handled in extract_states_by_time
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data, time_slice_opts, verbose=args.verbose
            )

        elif args.slice:
            slice_obj = slice_oem.parse_slice_args(args.slice)
            sliced_oem = slice_oem.extract_sliced_states(
                oem_data, slice_obj, verbose=args.verbose
            )

        if args.raw:
            oem.write_states(sys.stdout, sliced_oem.states)
        else:
            sliced_oem.write(sys.stdout)


if __name__ == "__main__":
    main()
