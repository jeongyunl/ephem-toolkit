"""Common slice helpers for OEM state selection.

This module provides the library functions used by the OEM CLI wrapper in
`bin/slice_oem.py`.

References:
    ISO 8601 "Date and time representations".
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sys

import common.interpolator.lagrange as lagrange
import common.time_utils as time_utils
from common.oem import CcsdsOem

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


def extract_sliced_states(
    oem: CcsdsOem,
    slice_spec: TimeSliceOptions | slice,
    verbose: bool = False,
) -> CcsdsOem:
    """Extract sliced OEM states based on a time or index slice specification.

    Returns a new CcsdsOem with the sliced states and preserved metadata.

    Parameters
    ----------
    oem : CcsdsOem
        CcsdsOem object containing states and metadata.
    slice_spec : TimeSliceOptions | slice
        Time-based slice options or a Python slice object.
    verbose : bool, optional
        If True, print debug information to stderr (default: False).

    Returns
    -------
    CcsdsOem
        Sliced CcsdsOem object with preserved metadata.

    Examples
    --------
    >>> oem = CcsdsOem.read("orbit.oem")
    >>> sliced_oem = extract_sliced_states(oem, slice(0, 10))
    >>> sliced_oem.meta.object_name  # Metadata preserved
    'ISS'
    """
    # Print OEM information before slicing if verbose
    if verbose:
        total_states = len(oem.states)
        print(f"[slice_oem] Input OEM:", file=sys.stderr)
        print(f"[slice_oem]   States: {total_states}", file=sys.stderr)

        if total_states > 0:
            first_ts, _ = oem.states[0]
            last_ts, _ = oem.states[-1]
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
                f"[slice_oem]   Span:  {_format_timedelta(span)}",
                file=sys.stderr,
            )

    # Extract the sliced states list
    if isinstance(slice_spec, TimeSliceOptions):
        if slice_spec.step_size is not None and not slice_spec.interpolate:
            raise ValueError("step_size requires interpolate=True")
        return extract_states_by_time(oem, slice_spec, verbose=verbose)
    elif isinstance(slice_spec, slice):
        # States are already sorted, no need to sort again
        sliced_states = oem.states[slice_spec]

        if verbose:
            # Compute actual indices after applying the slice
            total_states = len(oem.states)
            slice_start_index, slice_stop_index, slice_step = slice_spec.indices(
                total_states
            )

            print(f"[slice_oem] Slicing by index:", file=sys.stderr)
            print(
                f"[slice_oem]   Range: [{slice_start_index}:{slice_stop_index}], step={slice_step}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Selected {len(sliced_states)} of {total_states} states",
                file=sys.stderr,
            )

            if sliced_states:
                first_ts, _ = sliced_states[0]
                last_ts, _ = sliced_states[-1]
                first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
                last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
                print(
                    f"[slice_oem]   Output start: {time_utils.datetime_to_iso8601(first_dt)}",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   Output end:   {time_utils.datetime_to_iso8601(last_dt)}",
                    file=sys.stderr,
                )

        # Create new CcsdsOem with sliced states and preserved metadata
        return CcsdsOem.from_states(
            sliced_states,
            object_name=oem.meta.object_name,
            ref_frame=oem.meta.ref_frame,
            center_name=oem.meta.center_name,
            time_system=oem.meta.time_system,
        )
    else:
        raise TypeError("slice_spec must be a TimeSliceOptions or slice object")


# ===================================================================
# Internal helpers
# ===================================================================


def extract_states_by_time(
    oem: CcsdsOem,
    options: TimeSliceOptions,
    verbose: bool = False,
) -> CcsdsOem:
    """Extract states within a time window using TimeSliceOptions.

    Parameters
    ----------
    oem : CcsdsOem
        CcsdsOem object containing states and metadata.
    options : TimeSliceOptions
        Parsed time slice options specifying start, stop, step and interpolation.
    verbose : bool, optional
        If True, print debug information to stderr (default: False).

    Returns
    -------
    CcsdsOem
        New CcsdsOem object with sliced states and preserved metadata.
    """
    if options.step_size is not None and not options.interpolate:
        raise ValueError("step_size requires interpolate=True")

    # States are already sorted, no need to sort again
    states = oem.states
    timestamps_s: list[float] = [timestamp_s for timestamp_s, _ in states]

    # Get base times from OEM data
    base_start_timestamp_s: float = timestamps_s[0] if timestamps_s else 0.0
    base_stop_timestamp_s: float = timestamps_s[-1] if timestamps_s else 0.0

    if verbose:
        print(f"[slice_oem] Slicing by time:", file=sys.stderr)
        if options.start_time is not None:
            if isinstance(options.start_time, datetime):
                print(
                    f"[slice_oem]   Requested start: {time_utils.datetime_to_iso8601(options.start_time)}",
                    file=sys.stderr,
                )
            elif isinstance(options.start_time, timedelta):
                print(
                    f"[slice_oem]   Requested start: offset {_format_timedelta(options.start_time)} from {'end' if options.start_time < timedelta(0) else 'start'}",
                    file=sys.stderr,
                )
        else:
            print(
                f"[slice_oem]   Requested start: (beginning of OEM)",
                file=sys.stderr,
            )

        if options.stop_time is not None:
            if isinstance(options.stop_time, datetime):
                print(
                    f"[slice_oem]   Requested stop:  {time_utils.datetime_to_iso8601(options.stop_time)}",
                    file=sys.stderr,
                )
            elif isinstance(options.stop_time, timedelta):
                print(
                    f"[slice_oem]   Requested stop:  offset {_format_timedelta(options.stop_time)} from {'end' if options.stop_time <= timedelta(0) else 'start'}",
                    file=sys.stderr,
                )
        else:
            print(
                f"[slice_oem]   Requested stop:  (end of OEM)",
                file=sys.stderr,
            )

        if options.step_size is not None:
            print(
                f"[slice_oem]   Step size: {_format_timedelta(options.step_size)}",
                file=sys.stderr,
            )

    # Resolve start_time
    if options.start_time is None:
        slice_start_timestamp_s = base_start_timestamp_s
    elif isinstance(options.start_time, timedelta):
        # Positive timedelta: offset from start; Negative: offset from end
        if options.start_time >= timedelta(0):
            slice_start_timestamp_s = (
                base_start_timestamp_s + options.start_time.total_seconds()
            )
        else:
            slice_start_timestamp_s = (
                base_stop_timestamp_s + options.start_time.total_seconds()
            )
    else:
        # It's a datetime
        slice_start_timestamp_s = options.start_time.timestamp()

    # Resolve stop_time
    if options.stop_time is None:
        slice_stop_timestamp_s = base_stop_timestamp_s
    elif isinstance(options.stop_time, timedelta):
        # Positive timedelta: offset from start; Negative or zero: offset from end
        if options.stop_time > timedelta(0):
            slice_stop_timestamp_s = (
                base_start_timestamp_s + options.stop_time.total_seconds()
            )
        else:
            slice_stop_timestamp_s = (
                base_stop_timestamp_s + options.stop_time.total_seconds()
            )
    else:
        # It's a datetime
        slice_stop_timestamp_s = options.stop_time.timestamp()

    if options.start_time is not None and options.stop_time is None:
        slice_start_index: int = bisect.bisect_left(
            timestamps_s, slice_start_timestamp_s
        )
        slice_stop_index = slice_start_index + 1
        sliced_states = states[slice_start_index:slice_stop_index]

        if verbose:
            resolved_dt = datetime.fromtimestamp(
                slice_start_timestamp_s, tz=timezone.utc
            )
            print(
                f"[slice_oem]   Mode: single state (no stop time given)",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Resolved start: {time_utils.datetime_to_iso8601(resolved_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Nearest state at index {slice_start_index}",
                file=sys.stderr,
            )
    elif options.step_size is None:
        slice_start_index: int = (
            bisect.bisect_left(timestamps_s, slice_start_timestamp_s)
            if slice_start_timestamp_s is not None
            else 0
        )
        slice_stop_index: int = (
            bisect.bisect_right(timestamps_s, slice_stop_timestamp_s)
            if slice_stop_timestamp_s is not None
            else len(states)
        )
        sliced_states = states[slice_start_index:slice_stop_index]

        if verbose:
            resolved_start_dt = datetime.fromtimestamp(
                slice_start_timestamp_s, tz=timezone.utc
            )
            resolved_stop_dt = datetime.fromtimestamp(
                slice_stop_timestamp_s, tz=timezone.utc
            )
            print(
                f"[slice_oem]   Mode: time range (no interpolation)",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Resolved start: {time_utils.datetime_to_iso8601(resolved_start_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Resolved stop:  {time_utils.datetime_to_iso8601(resolved_stop_dt)}",
                file=sys.stderr,
            )
    else:
        # Interpolation requires both start and stop times
        if slice_start_timestamp_s is None or slice_stop_timestamp_s is None:
            raise ValueError(
                "Interpolation with step_size requires both start_time and stop_time"
            )

        interpolator: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
            dimension=6,
            degree=INTERPOLATION_DEGREE,
        )

        interpolator.set_data(states)

        sliced_states: list[tuple[float, object]] = []
        timestamp_s: float = slice_start_timestamp_s
        while timestamp_s <= slice_stop_timestamp_s:
            sliced_states.append((timestamp_s, interpolator.interpolate(timestamp_s)))
            timestamp_s += options.step_size.total_seconds()

        if verbose:
            resolved_start_dt = datetime.fromtimestamp(
                slice_start_timestamp_s, tz=timezone.utc
            )
            resolved_stop_dt = datetime.fromtimestamp(
                slice_stop_timestamp_s, tz=timezone.utc
            )
            print(
                f"[slice_oem]   Mode: interpolated (Lagrange degree {INTERPOLATION_DEGREE})",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Resolved start: {time_utils.datetime_to_iso8601(resolved_start_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Resolved stop:  {time_utils.datetime_to_iso8601(resolved_stop_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Step size: {_format_timedelta(options.step_size)}",
                file=sys.stderr,
            )

    if verbose:
        print(
            f"[slice_oem]   Selected {len(sliced_states)} of {len(states)} states",
            file=sys.stderr,
        )

        if sliced_states:
            first_ts, _ = sliced_states[0]
            last_ts, _ = sliced_states[-1]
            first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
            last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            print(
                f"[slice_oem]   Output start: {time_utils.datetime_to_iso8601(first_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Output end:   {time_utils.datetime_to_iso8601(last_dt)}",
                file=sys.stderr,
            )

    # Create new CcsdsOem with sliced states and preserved metadata
    return CcsdsOem.from_states(
        sliced_states,
        object_name=oem.meta.object_name,
        ref_frame=oem.meta.ref_frame,
        center_name=oem.meta.center_name,
        time_system=oem.meta.time_system,
    )


def _format_timedelta(td: timedelta) -> str:
    """Format a timedelta into a human-readable string.

    Parameters
    ----------
    td : timedelta
        The timedelta to format.

    Returns
    -------
    str
        Human-readable duration string (e.g. "2h 30m", "45s", "3d 1h").
    """
    total_seconds = abs(td.total_seconds())
    sign = "-" if td.total_seconds() < 0 else ""

    if total_seconds == 0:
        return "0s"

    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        if seconds == int(seconds):
            parts.append(f"{int(seconds)}s")
        else:
            parts.append(f"{seconds:.3g}s")

    return sign + " ".join(parts)


def _parse_time_or_duration(value: str) -> datetime | timedelta:
    """Parse ISO 8601 datetime or duration from string.

    Parameters
    ----------
    value : str
        ISO 8601 formatted datetime or duration string.

    Returns
    -------
    datetime | timedelta
        Parsed datetime or timedelta object.
    """
    try:
        return time_utils.iso8601_to_datetime(value)
    except ValueError:
        return time_utils.parse_duration_to_timedelta(
            value, default_unit="m", allow_negative=True, allow_zero=True
        )
