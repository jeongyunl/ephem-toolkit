"""Common slice helpers for OEM state selection.

This module provides the library functions used by the OEM CLI wrapper in
`bin/slice_oem.py`.

References:
    ISO 8601 "Date and time representations".
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta

import common.interpolator.lagrange as lagrange
import common.time_utils as time_utils

# ===================================================================
# Constants
# ===================================================================

INTERPOLATION_DEGREE: int = 8
"""Polynomial degree for Lagrange interpolation when resampling states."""


# ===================================================================
# Data structures
# ===================================================================


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


# ===================================================================
# Public parsers
# ===================================================================


def parse_slice_args(slice_str: str) -> slice:
    """Parse a Python-style slice string into a slice object.

    Parameters
    ----------
    slice_str : str
        Slice notation string (e.g. ``"0:10"``, ``"::2"``, ``"5"``, ``"-5:"``).

    Returns
    -------
    slice
        A :class:`slice` object representing the requested range.

    Raises
    ------
    ValueError
        If the slice string is malformed.
    """
    if ":" not in slice_str:
        try:
            index: int = int(slice_str)
        except ValueError:
            raise ValueError(f"Invalid index: {slice_str}")
        if index == -1:
            return slice(-1, None)
        return slice(index, index + 1)

    parts: list[str] = slice_str.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid slice: {slice_str}")

    start: int | None = int(parts[0]) if parts[0] else None
    stop: int | None = int(parts[1]) if len(parts) > 1 and parts[1] else None
    step: int | None = int(parts[2]) if len(parts) > 2 and parts[2] else None

    return slice(start, stop, step)


def parse_time_slice_args(time_slice_str: str) -> TimeSliceOptions:
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
    """
    text: str = time_slice_str.strip()
    if not text:
        raise ValueError("Invalid time slice: empty string")

    parts: list[str] = [part.strip() for part in text.split(",")]
    if len(parts) > 3:
        raise ValueError(f"Invalid time slice: {time_slice_str}")

    if len(parts) == 1 and parts[0]:
        parsed: datetime | timedelta = _parse_time_or_duration(parts[0])
        if isinstance(parsed, timedelta):
            return TimeSliceOptions(start_time=parsed)
        return TimeSliceOptions(start_time=parsed)

    parts += [""] * (3 - len(parts))

    return TimeSliceOptions(
        start_time=_parse_time_or_duration(parts[0]) if parts[0] else None,
        stop_time=_parse_time_or_duration(parts[1]) if parts[1] else None,
        step_size=(
            time_utils.parse_duration_to_timedelta(parts[2], default_unit="m")
            if parts[2]
            else None
        ),
    )


def slice_states(
    states: dict[float, object],
    slice_spec: TimeSliceOptions | slice,
) -> list[tuple[float, object]]:
    """Return sliced OEM states based on a time or index slice specification.

    Parameters
    ----------
    states : dict[float, object]
        Mapping of POSIX timestamps (float, seconds since epoch) to state vectors.
    slice_spec : TimeSliceOptions | slice
        Time-based slice options or a Python slice object.

    Returns
    -------
    list[tuple[float, object]]
        List of ``(timestamp, state)`` tuples selected by the slice.
    """
    if isinstance(slice_spec, TimeSliceOptions):
        if slice_spec.step_size is not None and not slice_spec.interpolate:
            raise ValueError("step_size requires interpolate=True")
        return slice_states_by_time(states, slice_spec)
    if isinstance(slice_spec, slice):
        sorted_states: list[tuple[float, object]] = sorted(
            states.items(), key=lambda item: item[0]
        )
        return sorted_states[slice_spec]
    raise TypeError("slice_spec must be a TimeSliceOptions or slice object")


# ===================================================================
# Public slicers
# ===================================================================


def slice_states_by_time(
    states: dict[float, object],
    options: TimeSliceOptions,
) -> list[tuple[float, object]]:
    """Extract states within a time window using TimeSliceOptions.

    Parameters
    ----------
    states : dict[float, object]
        Mapping of POSIX timestamps (float, seconds since epoch) to state vectors.
    options : TimeSliceOptions
        Parsed time slice options specifying start, stop, step and interpolation.

    Returns
    -------
    list[tuple[float, object]]
        List of ``(timestamp, state)`` tuples within the specified window.
    """
    if options.step_size is not None and not options.interpolate:
        raise ValueError("step_size requires interpolate=True")

    sorted_states: list[tuple[float, object]] = sorted(
        states.items(), key=lambda item: item[0]
    )
    timestamps_s: list[float] = [ts_s for ts_s, _ in sorted_states]

    start_ts_s: float | None = (
        options.start_time.timestamp() if options.start_time is not None else None
    )
    stop_ts_s: float | None = (
        options.stop_time.timestamp() if options.stop_time is not None else None
    )

    if start_ts_s is not None and options.stop_time is None:
        start_idx: int = bisect.bisect_left(timestamps_s, start_ts_s)
        return sorted_states[start_idx : start_idx + 1]

    start_idx: int = (
        bisect.bisect_left(timestamps_s, start_ts_s) if start_ts_s is not None else 0
    )
    stop_idx: int = (
        bisect.bisect_right(timestamps_s, stop_ts_s)
        if stop_ts_s is not None
        else len(sorted_states)
    )

    if options.step_size is None:
        return sorted_states[start_idx:stop_idx]

    # Interpolation requires both start and stop times
    if start_ts_s is None or stop_ts_s is None:
        raise ValueError(
            "Interpolation with step_size requires both start_time and stop_time"
        )

    interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
        dimension=6,
        degree=INTERPOLATION_DEGREE,
    )

    interpolator.set_data(sorted_states)

    result: list[tuple[float, object]] = []
    timestamp_s: float = start_ts_s
    while timestamp_s <= stop_ts_s:
        result.append((timestamp_s, interpolator.interpolate(timestamp_s)))
        timestamp_s += options.step_size.total_seconds()

    return result


def _parse_time_or_duration(value: str) -> datetime | timedelta:
    """Parse either an ISO datetime or a duration token.

    Parameters
    ----------
    value : str
        ISO 8601 datetime string or duration specification.

    Returns
    -------
    datetime | timedelta
        Parsed datetime or timedelta object.

    Raises
    ------
    ValueError
        If the value cannot be parsed as either format.
    """
    try:
        return time_utils.iso8601_to_datetime(value)
    except ValueError:
        return time_utils.parse_duration_to_timedelta(
            value, default_unit="m", allow_negative=True, allow_zero=True
        )
