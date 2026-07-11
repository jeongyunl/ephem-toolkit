#!/usr/bin/env python3
"""Slice and extract subsets of CCSDS OEM ephemeris data by index or time range.

Provides :func:`parse_slice` and :func:`parse_time_slice` to parse slice
specifications, :func:`slice_states_by_time` to extract time-windowed states,
and a CLI entry point to read OEM files and output sliced state vectors.
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
    """Format a datetime or timedelta value as a string, or return empty string if None."""
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return _format_duration(value)
    return time_utils.datetime_to_iso8601(value)


def _format_duration(duration: timedelta) -> str:
    """Return a canonical duration string for the given timedelta."""
    total_seconds: float = duration.total_seconds()
    if total_seconds % 3600 == 0:
        hours: float = total_seconds / 3600
        return f"{hours:g}h"
    if total_seconds % 60 == 0:
        minutes: float = total_seconds / 60
        return f"{minutes:g}m"
    return f"{total_seconds:g}s"


def main() -> None:
    """Read OEM file name from CLI argument and load it."""
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
        "--oem",
        action="store_true",
        help="Write sliced results in OEM format",
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
        oem_data = oem.CcsdsOem.from_source(oem_file)

        if args.time_slice:
            base_start = time_utils.iso8601_to_datetime(oem_data.meta.start_time)
            base_stop = time_utils.iso8601_to_datetime(oem_data.meta.stop_time)

            resolved_start = None
            if isinstance(time_slice_opts.start_time, timedelta):
                resolved_start = (
                    base_start + time_slice_opts.start_time
                    if time_slice_opts.start_time >= timedelta(0)
                    else base_stop + time_slice_opts.start_time
                )
            else:
                resolved_start = time_slice_opts.start_time
                # Ensure timezone-aware datetime
                if resolved_start is not None and resolved_start.tzinfo is None:
                    resolved_start = resolved_start.replace(tzinfo=timezone.utc)

            resolved_stop = time_slice_opts.stop_time
            if isinstance(time_slice_opts.stop_time, timedelta):
                resolved_stop = (
                    base_start + time_slice_opts.stop_time
                    if time_slice_opts.stop_time > timedelta(0)
                    else base_stop + time_slice_opts.stop_time
                )
            else:
                resolved_stop = time_slice_opts.stop_time
                # Ensure timezone-aware datetime
                if resolved_stop is not None and resolved_stop.tzinfo is None:
                    resolved_stop = resolved_stop.replace(tzinfo=timezone.utc)

            time_slice_opts = slice_oem.TimeSliceOptions(
                start_time=resolved_start,
                stop_time=resolved_stop,
                step_size=time_slice_opts.step_size,
                interpolate=time_slice_opts.interpolate,
            )
            sliced_states = slice_oem.slice_states(oem_data.states, time_slice_opts)

        elif args.slice:
            slice_obj = slice_oem.parse_slice_args(args.slice)
            sliced_states = slice_oem.slice_states(oem_data.states, slice_obj)

        # Update time fields based on selected slice
        if sliced_states:
            first_epoch = datetime.fromtimestamp(sliced_states[0][0], tz=timezone.utc)
            last_epoch = datetime.fromtimestamp(sliced_states[-1][0], tz=timezone.utc)

            oem_data.meta.start_time = time_utils.datetime_to_iso8601(first_epoch)
            oem_data.meta.stop_time = time_utils.datetime_to_iso8601(last_epoch)
            oem_data.meta.useable_start_time = ""
            oem_data.meta.useable_stop_time = ""

        if args.oem:
            # Output in OEM file format
            oem_data.states = dict(sliced_states)
            oem_data.to_file(sys.stdout)
        else:
            # Output raw states
            states_dict = dict(sliced_states)
            oem.write_states(sys.stdout, states_dict)


if __name__ == "__main__":
    main()
