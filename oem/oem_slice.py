#!/usr/bin/env python3

from __future__ import annotations

import argparse
import bisect
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tudatpy.math.interpolators as interpolators

# Add parent directory to path to import common utilities
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class TimeSliceOptions:
    start_time: datetime | timedelta | None = None
    stop_time: datetime | timedelta | None = None
    step_size: timedelta | None = None
    interpolate: bool = False


from common.oem import CcsdsOem, write_states


def parse_slice(slice_str: str) -> slice | int:
    """Parse a Python-style slice string (e.g., '0:10', '::2', '5', '-5:').

    Returns either a slice object or an int for single indices.
    """
    # Handle single index
    if ":" not in slice_str:
        try:
            return int(slice_str)
        except ValueError:
            raise ValueError(f"Invalid index: {slice_str}")

    # Handle slice notation
    parts = slice_str.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid slice: {slice_str}")

    start = int(parts[0]) if parts[0] else None
    stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
    step = int(parts[2]) if len(parts) > 2 and parts[2] else None

    return slice(start, stop, step)


ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)(?:Z|[+-]\d{2}:\d{2})?$"
)


def parse_time_slice(
    time_slice_str: str,
) -> TimeSliceOptions:
    """Parse an ISO-8601 time slice string using comma separators.

    Examples:
        start_time,stop_time
        start_time,stop_time,step_size
        ,stop_time,step_size
        start_time,,step_size
        start_time,stop_time,
    """
    text = time_slice_str.strip()
    if not text:
        raise ValueError("Invalid time slice: empty string")

    parts = [part.strip() for part in text.split(",")]
    if len(parts) > 3:
        raise ValueError(f"Invalid time slice: {time_slice_str}")

    if len(parts) == 1 and parts[0]:
        parsed = _parse_time_or_duration(parts[0])
        if isinstance(parsed, timedelta):
            return TimeSliceOptions(start_time=parsed)
        return TimeSliceOptions(start_time=parsed)

    parts += [""] * (3 - len(parts))

    return TimeSliceOptions(
        start_time=_parse_time_or_duration(parts[0]) if parts[0] else None,
        stop_time=_parse_time_or_duration(parts[1]) if parts[1] else None,
        step_size=_parse_duration_with_default_minutes(parts[2]) if parts[2] else None,
    )


def slice_states_by_time(
    states: dict[float, any],
    start_time: datetime | None,
    stop_time: datetime | None,
    step_size: timedelta | None = None,
) -> list[tuple[float, any]]:
    """Return the sublist of states within [start_time, stop_time] using bisect.

    If stop_time is missing, return only one matching state at or after start_time.
    """
    state_list = sorted(states.items(), key=lambda item: item[0])
    epochs = [epoch for epoch, _ in state_list]
    if start_time is not None and stop_time is None:
        start_idx = bisect.bisect_left(
            epochs,
            start_time.timestamp() if isinstance(start_time, datetime) else start_time,
        )
        return state_list[start_idx : start_idx + 1]

    start_idx = (
        bisect.bisect_left(
            epochs,
            start_time.timestamp() if isinstance(start_time, datetime) else start_time,
        )
        if start_time is not None
        else 0
    )
    stop_idx = (
        bisect.bisect_right(
            epochs,
            stop_time.timestamp() if isinstance(stop_time, datetime) else stop_time,
        )
        if stop_time is not None
        else len(state_list)
    )

    if step_size is None:
        return state_list[start_idx:stop_idx]

    interpolator = interpolators.create_one_dimensional_vector_interpolator(
        states, interpolators.lagrange_interpolation(8)
    )

    state_list = []
    timestamp = start_time.timestamp()
    while timestamp <= stop_time.timestamp():
        state_list.append((timestamp, interpolator.interpolate(timestamp)))

        timestamp += step_size.total_seconds()

    return state_list


def _parse_duration_with_default_minutes(
    value: str,
    allow_negative: bool = False,
    allow_zero: bool = False,
) -> timedelta:
    """Parse a duration token and return a timedelta.

    Bare numeric values are treated as minutes.
    """
    token = value.strip()
    if not token:
        raise ValueError(
            "step duration must be a number optionally followed by s, m, h, or d"
        )

    sign = 1
    if token[0] in "+-":
        if token[0] == "-":
            sign = -1
        token = token[1:].strip()

    if not token:
        raise ValueError(
            "step duration must be a number optionally followed by s, m, h, or d"
        )

    component_re = re.compile(r"([0-9]*\.?[0-9]+)\s*([smhdSMHD]?)")
    pos = 0
    total_seconds = 0.0
    components = []

    while pos < len(token):
        match = component_re.match(token, pos)
        if not match:
            raise ValueError(
                "step duration must be a number optionally followed by s, m, h, or d"
            )
        magnitude = float(match.group(1))
        unit = match.group(2).lower() if match.group(2) else "m"
        components.append((magnitude, unit))
        pos = match.end()

    if not components:
        raise ValueError(
            "step duration must be a number optionally followed by s, m, h, or d"
        )

    if len(components) == 1 and components[0][1] == "":
        components[0] = (components[0][0], "m")

    for magnitude, unit in components:
        if magnitude < 0.0 and not allow_negative:
            raise ValueError("step duration must be a positive value")
        if magnitude == 0.0 and not allow_zero:
            raise ValueError("step duration must be a positive value")
        if unit == "s":
            total_seconds += magnitude
        elif unit == "m":
            total_seconds += magnitude * 60.0
        elif unit == "h":
            total_seconds += magnitude * 3600.0
        elif unit == "d":
            total_seconds += magnitude * 86400.0
        else:
            raise ValueError("step duration unit must be one of: s, m, h, d")

    return timedelta(seconds=sign * total_seconds)


def _parse_time_or_duration(value: str) -> datetime | timedelta:
    """Parse either an ISO datetime or a duration token."""
    try:
        return _parse_iso_datetime(value)
    except ValueError:
        return _parse_duration_with_default_minutes(
            value, allow_negative=True, allow_zero=True
        )


def _format_time_or_duration(value: datetime | timedelta | None) -> str:
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return _format_duration(value)
    return value.isoformat()


def _format_duration(duration: timedelta) -> str:
    """Return a canonical duration string for the given timedelta."""
    total_seconds = duration.total_seconds()
    if total_seconds % 3600 == 0:
        hours = total_seconds / 3600
        return f"{hours:g}h"
    if total_seconds % 60 == 0:
        minutes = total_seconds / 60
        return f"{minutes:g}m"
    return f"{total_seconds:g}s"


def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO-8601-ish datetime string into a datetime object."""
    token = value.strip()
    if token.endswith("Z"):
        token = token[:-1]
    try:
        return datetime.fromisoformat(token)
    except ValueError as error:
        raise ValueError(f"Invalid ISO-8601 datetime: {value}") from error


def main() -> None:
    """Read OEM file name from CLI argument and load it."""
    parser = argparse.ArgumentParser(description="Load and slice CCSDS OEM file states")
    parser.add_argument("oem_file", nargs="?", help="Path to OEM file")
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

    if args.time_slice:
        time_slice_opts = parse_time_slice(args.time_slice)
        time_slice_opts.interpolate = args.interpolate
        if time_slice_opts.step_size is not None and not time_slice_opts.interpolate:
            parser.error("step_size requires --interpolate")
        if args.oem_file is None:
            print(_format_time_or_duration(time_slice_opts.start_time))
            print(_format_time_or_duration(time_slice_opts.stop_time))
            print(_format_time_or_duration(time_slice_opts.step_size))
            return

        oem_file = Path(args.oem_file)
        oem = CcsdsOem.from_source(oem_file)

        base_start = _parse_iso_datetime(oem.meta.start_time)
        base_stop = _parse_iso_datetime(oem.meta.stop_time)
        resolved_start = None
        if isinstance(time_slice_opts.start_time, timedelta):
            resolved_start = (
                base_start + time_slice_opts.start_time
                if time_slice_opts.start_time >= timedelta(0)
                else base_stop + time_slice_opts.start_time
            )
        else:
            resolved_start = time_slice_opts.start_time

        resolved_stop = time_slice_opts.stop_time
        if isinstance(time_slice_opts.stop_time, timedelta):
            resolved_stop = (
                base_start + time_slice_opts.stop_time
                if time_slice_opts.stop_time > timedelta(0)
                else base_stop + time_slice_opts.stop_time
            )
        sliced_states = slice_states_by_time(
            oem.states, resolved_start, resolved_stop, time_slice_opts.step_size
        )
        if sliced_states:
            first_epoch = sliced_states[0][0]
            last_epoch = sliced_states[-1][0]
            if isinstance(first_epoch, (int, float)):
                first_epoch = datetime.fromtimestamp(first_epoch, tz=timezone.utc)
            if isinstance(last_epoch, (int, float)):
                last_epoch = datetime.fromtimestamp(last_epoch, tz=timezone.utc)
            oem.meta.start_time = first_epoch.isoformat()
            oem.meta.stop_time = last_epoch.isoformat()
            oem.meta.useable_start_time = ""
            oem.meta.useable_stop_time = ""
        if args.oem:
            oem.states = dict(sliced_states)
            oem.to_file(sys.stdout)
        else:
            states_dict = dict(sliced_states)
            write_states(sys.stdout, states_dict)
        return

    oem_file = Path(args.oem_file)
    oem = CcsdsOem.from_source(oem_file)

    if args.slice:
        slice_obj = parse_slice(args.slice)
        state_items = list(oem.states.items())
        sliced_states = state_items[slice_obj]

        # Handle both single index (returns tuple) and slice (returns list)
        if isinstance(slice_obj, int):
            # Single index returns a tuple (epoch, state)
            epoch, state = sliced_states
            sliced_states_list = [(epoch, state)]
        else:
            # Slice returns a list of tuples
            sliced_states_list = sliced_states

        # Update time fields based on selected slice
        if sliced_states_list:
            first_epoch = sliced_states_list[0][0]
            last_epoch = sliced_states_list[-1][0]
            if isinstance(first_epoch, (int, float)):
                first_epoch = datetime.fromtimestamp(first_epoch, tz=timezone.utc)
            if isinstance(last_epoch, (int, float)):
                last_epoch = datetime.fromtimestamp(last_epoch, tz=timezone.utc)

            oem.meta.start_time = first_epoch.isoformat()
            oem.meta.stop_time = last_epoch.isoformat()
            oem.meta.useable_start_time = ""
            oem.meta.useable_stop_time = ""

        if args.oem:
            # Output in OEM file format
            oem.states = dict(sliced_states_list)
            oem.to_file(sys.stdout)
        else:
            # Output raw states
            states_dict = dict(sliced_states_list)
            write_states(sys.stdout, states_dict)


if __name__ == "__main__":
    main()
