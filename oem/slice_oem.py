#!/usr/bin/env python3
"""Slice and extract subsets of CCSDS OEM ephemeris data by index or time range.

Provides :func:`parse_slice` and :func:`parse_time_slice` to parse slice
specifications, :func:`slice_states_by_time` to extract time-windowed states,
and a CLI entry point to read OEM files and output sliced state vectors.
"""

from __future__ import annotations

import argparse
import bisect
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path to import common utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

import common.common as common
import common.oem as oem
import interpolator.lagrange as lagrange

INTERPOLATOR_NUMBER_OF_POINTS: int = 8
"""Polynomial degree for Lagrange interpolation when resampling states."""


@dataclass
class TimeSliceOptions:
    """Parsed options for a time-based OEM slice operation."""

    start_time: datetime | timedelta | None = None
    """Start of the time window; absolute datetime or relative timedelta offset from the OEM start/stop."""

    stop_time: datetime | timedelta | None = None
    """End of the time window; absolute datetime or relative timedelta offset from the OEM start/stop."""

    step_size: timedelta | None = None
    """Resampling interval; if set, states are interpolated at this fixed step."""

    interpolate: bool = False
    """Whether to enable Lagrange interpolation when step_size is provided."""


def parse_slice(slice_str: str) -> slice | int:
    """Parse a Python-style slice string into a slice object or integer index.

    Parameters
    ----------
    slice_str : str
        Slice notation string (e.g. ``"0:10"``, ``"::2"``, ``"5"``, ``"-5:"``).

    Returns
    -------
    slice | int
        A :class:`slice` object for range notation, or an :class:`int` for
        single-index notation.

    Raises
    ------
    ValueError
        If the slice string is malformed.
    """
    # Handle single index
    if ":" not in slice_str:
        try:
            return int(slice_str)
        except ValueError:
            raise ValueError(f"Invalid index: {slice_str}")

    # Handle slice notation
    parts: list[str] = slice_str.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid slice: {slice_str}")

    start: int | None = int(parts[0]) if parts[0] else None
    stop: int | None = int(parts[1]) if len(parts) > 1 and parts[1] else None
    step: int | None = int(parts[2]) if len(parts) > 2 and parts[2] else None

    return slice(start, stop, step)


ISO_DATETIME_RE: re.Pattern[str] = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)(?:Z|[+-]\d{2}:\d{2})?$"
)


def parse_time_slice(
    time_slice_str: str,
) -> TimeSliceOptions:
    """Parse an ISO-8601 time slice string using comma separators.

    Parameters
    ----------
    time_slice_str : str
        Comma-separated time slice specification. Format:
        ``start[,stop[,step]]`` where start/stop are ISO-8601 datetimes or
        durations, and step is a duration.

    Returns
    -------
    TimeSliceOptions
        Parsed time slice options with ``start_time``, ``stop_time``, and
        ``step_size`` fields.

    Raises
    ------
    ValueError
        If the time slice string is malformed.

    Notes
    -----
    Examples: ``"start_time,stop_time"``, ``"start_time,stop_time,step_size"``,
    ``",stop_time,step_size"``, ``"start_time,,step_size"``.
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
    """Extract states within a time window, optionally resampling at a fixed step.

    Uses binary search to efficiently locate the start and stop indices. If
    *step_size* is provided, interpolates states at regular intervals using
    Lagrange polynomial interpolation.

    Parameters
    ----------
    states : dict[float, any]
        Mapping of POSIX timestamps (float, seconds since epoch) to state vectors.
    start_time : datetime | None
        Start of the time window. If None, starts from the first state.
    stop_time : datetime | None
        End of the time window. If None and *start_time* is provided, returns
        only one state at or after *start_time*.
    step_size : timedelta | None
        If provided, resample states at this fixed interval using interpolation.

    Returns
    -------
    list[tuple[float, any]]
        List of ``(timestamp, state)`` tuples within the specified window.
    """
    sorted_states = sorted(states.items(), key=lambda item: item[0])
    timestamps = [ts for ts, _ in sorted_states]

    # Convert datetime bounds to float timestamps for comparison
    start_ts: float | None = start_time.timestamp() if start_time is not None else None
    stop_ts: float | None = stop_time.timestamp() if stop_time is not None else None

    if start_ts is not None and stop_ts is None:
        start_idx = bisect.bisect_left(timestamps, start_ts)
        return sorted_states[start_idx : start_idx + 1]

    start_idx = bisect.bisect_left(timestamps, start_ts) if start_ts is not None else 0
    stop_idx = (
        bisect.bisect_right(timestamps, stop_ts)
        if stop_ts is not None
        else len(sorted_states)
    )

    if step_size is None:
        return sorted_states[start_idx:stop_idx]

    # states already uses float timestamps — use directly for interpolation
    interpolator = lagrange.LagrangeInterpolator(
        dimension=6, degree=INTERPOLATOR_NUMBER_OF_POINTS
    )
    interpolator.set_data(sorted_states)

    result: list[tuple[float, any]] = []
    timestamp = start_ts
    while timestamp <= stop_ts:
        result.append((timestamp, interpolator.interpolate(timestamp)))
        timestamp += step_size.total_seconds()

    return result


def _parse_duration_with_default_minutes(
    value: str,
    allow_negative: bool = False,
    allow_zero: bool = False,
) -> timedelta:
    """Parse a duration token and return a timedelta.

    Bare numeric values are treated as minutes.
    """
    token: str = value.strip()
    if not token:
        raise ValueError(
            "step duration must be a number optionally followed by s, m, h, or d"
        )

    sign: int = 1
    if token[0] in "+-":
        if token[0] == "-":
            sign = -1
        token = token[1:].strip()

    if not token:
        raise ValueError(
            "step duration must be a number optionally followed by s, m, h, or d"
        )

    component_re: re.Pattern[str] = re.compile(r"([0-9]*\.?[0-9]+)\s*([smhdSMHD]?)")
    pos: int = 0
    total_seconds: float = 0.0
    components: list[tuple[float, str]] = []

    while pos < len(token):
        match: re.Match[str] | None = component_re.match(token, pos)
        if not match:
            raise ValueError(
                "step duration must be a number optionally followed by s, m, h, or d"
            )
        magnitude: float = float(match.group(1))
        unit: str = match.group(2).lower() if match.group(2) else "m"
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
        return common.iso8601_to_datetime(value)
    except ValueError:
        return _parse_duration_with_default_minutes(
            value, allow_negative=True, allow_zero=True
        )


def _format_time_or_duration(value: datetime | timedelta | None) -> str:
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return _format_duration(value)
    return common.datetime_to_iso8601(value)


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
        oem_data = oem.CcsdsOem.from_source(oem_file)

        base_start = common.iso8601_to_datetime(oem_data.meta.start_time)
        base_stop = common.iso8601_to_datetime(oem_data.meta.stop_time)

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

        sliced_states = slice_states_by_time(
            oem_data.states, resolved_start, resolved_stop, time_slice_opts.step_size
        )
        if sliced_states:
            first_epoch = sliced_states[0][0]
            last_epoch = sliced_states[-1][0]
            if isinstance(first_epoch, (int, float)):
                first_epoch = datetime.fromtimestamp(first_epoch, tz=timezone.utc)
            if isinstance(last_epoch, (int, float)):
                last_epoch = datetime.fromtimestamp(last_epoch, tz=timezone.utc)
            oem_data.meta.start_time = common.datetime_to_iso8601(first_epoch)
            oem_data.meta.stop_time = common.datetime_to_iso8601(last_epoch)
            oem_data.meta.useable_start_time = ""
            oem_data.meta.useable_stop_time = ""
        if args.oem:
            oem_data.states = dict(sliced_states)
            oem_data.to_file(sys.stdout)
        else:
            states_dict = dict(sliced_states)
            oem.write_states(sys.stdout, states_dict)
        return

    oem_file = Path(args.oem_file)
    oem_data = oem.CcsdsOem.from_source(oem_file)

    if args.slice:
        slice_obj = parse_slice(args.slice)
        state_items = list(oem_data.states.items())
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

            oem_data.meta.start_time = common.datetime_to_iso8601(first_epoch)
            oem_data.meta.stop_time = common.datetime_to_iso8601(last_epoch)
            oem_data.meta.useable_start_time = ""
            oem_data.meta.useable_stop_time = ""

        if args.oem:
            # Output in OEM file format
            oem_data.states = dict(sliced_states_list)
            oem_data.to_file(sys.stdout)
        else:
            # Output raw states
            states_dict = dict(sliced_states_list)
            oem.write_states(sys.stdout, states_dict)


if __name__ == "__main__":
    main()
