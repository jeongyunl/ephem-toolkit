"""Common slice helpers for OEM state selection.

This module provides the library functions used by the ``slice-oem`` CLI tool
(``tudatpy_utils.slice_oem.slice_oem``).

References:
    https://en.wikipedia.org/wiki/ISO_8601 (ISO 8601 "Date and time representations")
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sys

import numpy as np

from . import time_utils
from .ccsds.oem import CcsdsOem
from .interpolator import factory
from .interpolator.interpolation_spec import InterpolationSpec, InterpolationType

# ===================================================================
# Data structures
# ===================================================================


@dataclass
class TimeSliceOptions:
    """Parsed options for a time-based OEM slice operation.

    Notes
    -----
    Unlike index-based slicing where the stop index is exclusive, time-based
    slicing is inclusive for both start and stop times. All states with
    timestamps within [start_time, stop_time] are included.
    """

    start_time: datetime | timedelta | None = None
    """Start of the time window; absolute datetime or relative timedelta offset from the OEM start/stop."""

    stop_time: datetime | timedelta | None = None
    """End of the time window; absolute datetime or relative timedelta offset from the OEM start/stop."""

    step_size: timedelta | None = None
    """Resampling interval; if set, states are interpolated at this fixed step."""

    interpolation_spec: InterpolationSpec | None = None
    """Interpolation specification for exact start/stop times and resampling."""


# ===================================================================
# Public parsers
# ===================================================================


def parse_slice_args(slice_str: str) -> slice:
    """Parse a Python-style slice string into a slice object.

    Parameters
    ----------
    slice_str : str
        Slice notation string (e.g. ``"0:10"``, ``"::2"``, ``"5"``, ``"-5:"``).
        Format: ``start[:[stop][:step]]`` where stop and step are optional.

    Returns
    -------
    slice
        A :class:`slice` object representing the requested range.

    Raises
    ------
    ValueError
        If the slice string is malformed.

    Notes
    -----
    - Single value (e.g., ``"5"``) extracts one state at that index
    - ``start:`` extracts from start to end
    - ``start:stop`` extracts from start to stop (exclusive)
    - ``start:stop:step`` extracts every step-th element from start to stop
    - ``::step`` extracts every step-th element from the entire range
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
        ``start[,[stop][,step]]`` where start/stop are ISO-8601 datetimes or
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

    # Check if comma is present to distinguish between single value and range
    has_comma: bool = "," in text

    parts: list[str] = [part.strip() for part in text.split(",")]
    if len(parts) > 3:
        raise ValueError(f"Invalid time slice: {time_slice_str}")

    if len(parts) == 1 and parts[0]:
        parsed: datetime | timedelta = time_utils.parse_time_or_duration(parts[0])
        if isinstance(parsed, timedelta):
            return TimeSliceOptions(start_time=parsed)
        return TimeSliceOptions(start_time=parsed)

    parts += [""] * (3 - len(parts))

    # If comma is present but stop is empty, use timedelta(0) to indicate OEM end
    stop_time_value = None
    if parts[1]:
        stop_time_value = time_utils.parse_time_or_duration(parts[1])
    elif has_comma:
        stop_time_value = timedelta(0)

    return TimeSliceOptions(
        start_time=time_utils.parse_time_or_duration(parts[0]) if parts[0] else None,
        stop_time=stop_time_value,
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
    # Extract the sliced states list
    if isinstance(slice_spec, TimeSliceOptions):
        if slice_spec.step_size is not None and slice_spec.interpolation_spec is None:
            raise ValueError("step_size requires interpolation_spec to be set")
        return extract_states_by_time(oem, slice_spec, verbose=verbose)
    elif isinstance(slice_spec, slice):
        # Validate slice indices before applying
        total_states = len(oem.states)
        _validate_slice_indices(slice_spec, total_states)

        # States are already sorted, no need to sort again
        sliced_states: list[tuple[float, np.ndarray]] = oem.states[slice_spec]

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
                first_timestamp_s, _ = sliced_states[0]
                last_timestamp_s, _ = sliced_states[-1]
                first_dt = datetime.fromtimestamp(first_timestamp_s, tz=timezone.utc)
                last_dt = datetime.fromtimestamp(last_timestamp_s, tz=timezone.utc)
                span = last_dt - first_dt
                print(
                    f"[slice_oem]   Output start: {time_utils.datetime_to_iso8601(first_dt)}",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   Output end:   {time_utils.datetime_to_iso8601(last_dt)}",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   Output span:  {time_utils.format_duration_human(span)}",
                    file=sys.stderr,
                )

        # Create new CcsdsOem with sliced states and preserved metadata
        return _create_sliced_oem(oem, sliced_states)
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
    # Use interpolation spec from options, or create default
    interpolation_spec = options.interpolation_spec
    if interpolation_spec is None and options.interpolation_spec is not None:
        interpolation_spec = options.interpolation_spec

    # States are already sorted, no need to sort again
    states: list[tuple[float, np.ndarray]] = oem.states

    # Validate that OEM has states
    if len(states) == 0:
        raise IndexError("Cannot slice empty OEM file (0 states)")

    timestamps_s: list[float] = [timestamp_s for timestamp_s, _ in states]

    # Get base times from OEM data
    base_start_timestamp_s: float = timestamps_s[0]
    base_stop_timestamp_s: float = timestamps_s[-1]

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
                    f"[slice_oem]   Requested start: offset {time_utils.format_duration_human(options.start_time)} from {'end' if options.start_time < timedelta(0) else 'start'}",
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
                    f"[slice_oem]   Requested stop:  offset {time_utils.format_duration_human(options.stop_time)} from {'end' if options.stop_time <= timedelta(0) else 'start'}",
                    file=sys.stderr,
                )
        else:
            print(
                f"[slice_oem]   Requested stop:  (same as start - single state)",
                file=sys.stderr,
            )

        if options.step_size is not None:
            print(
                f"[slice_oem]   Step size: {time_utils.format_duration_human(options.step_size)}",
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
        if options.start_time is None:
            # Both start and stop are None: use full OEM range
            slice_stop_timestamp_s = base_stop_timestamp_s
        else:
            # No comma present: single state extraction (stop = start)
            slice_stop_timestamp_s = slice_start_timestamp_s
    elif isinstance(options.stop_time, timedelta):
        # Positive timedelta: offset from start
        # Zero or negative timedelta: offset from end
        if options.stop_time > timedelta(0):
            # Positive: offset from the resolved slice start
            slice_stop_timestamp_s = (
                slice_start_timestamp_s + options.stop_time.total_seconds()
            )
        else:
            # Zero or negative: offset from OEM end
            # Zero (0) means end of OEM
            # Negative means offset backwards from end
            slice_stop_timestamp_s = (
                base_stop_timestamp_s + options.stop_time.total_seconds()
            )
    else:
        # It's a datetime
        slice_stop_timestamp_s = options.stop_time.timestamp()

    # Validate time range after resolving timestamps
    _validate_time_range(
        slice_start_timestamp_s,
        slice_stop_timestamp_s,
        base_start_timestamp_s,
        base_stop_timestamp_s,
        options,
    )

    # Validate step_size requires interpolation_spec
    if options.step_size is not None and options.interpolation_spec is None:
        raise ValueError("step_size requires interpolation_spec to be set")

    interpolator = None
    if options.interpolation_spec is not None:
        interpolator = factory.InterpolatorFactory.create(
            spec=interpolation_spec,
            dimension=6,
            is_cartesian_state=True,
            verbose=verbose,
            context="core.slice_oem.extract_states_by_time",
            data=states,
        )

    if options.start_time is not None and options.stop_time is None:
        # Single state extraction (no comma was present)
        if options.interpolation_spec is not None:
            # Interpolate single state at exact requested time
            interp_state = interpolator.interpolate(slice_start_timestamp_s)
            sliced_states = [(slice_start_timestamp_s, interp_state)]

            if verbose:
                resolved_dt = datetime.fromtimestamp(
                    slice_start_timestamp_s, tz=timezone.utc
                )
                print(
                    f"[slice_oem]   Mode: single state (interpolated)",
                    file=sys.stderr,
                )
                print(
                    f"[slice_oem]   Resolved start: {time_utils.datetime_to_iso8601(resolved_dt)}",
                    file=sys.stderr,
                )
        else:
            # Find nearest existing state
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
        if options.interpolation_spec is not None:
            # Interpolate at exact start and stop times
            # Get all states between start and stop, plus interpolated boundary states
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

            sliced_states = []

            # Add interpolated start state if it doesn't exactly match an existing state
            if (
                slice_start_index < len(timestamps_s)
                and timestamps_s[slice_start_index] != slice_start_timestamp_s
            ):
                if verbose:
                    start_dt = datetime.fromtimestamp(
                        slice_start_timestamp_s, tz=timezone.utc
                    )
                    print(
                        f"[slice_oem]   Interpolating start_state at {time_utils.datetime_to_iso8601(start_dt)}",
                        file=sys.stderr,
                    )
                start_state = interpolator.interpolate(slice_start_timestamp_s)
                sliced_states.append((slice_start_timestamp_s, start_state))

            # Add all existing states in the range
            sliced_states.extend(states[slice_start_index:slice_stop_index])

            # Add interpolated stop state if it doesn't exactly match an existing state
            if (
                slice_stop_index > 0
                and timestamps_s[slice_stop_index - 1] != slice_stop_timestamp_s
            ):
                if verbose:
                    stop_dt = datetime.fromtimestamp(
                        slice_stop_timestamp_s, tz=timezone.utc
                    )
                    print(
                        f"[slice_oem]   Interpolating stop_state at {time_utils.datetime_to_iso8601(stop_dt)}",
                        file=sys.stderr,
                    )
                stop_state = interpolator.interpolate(slice_stop_timestamp_s)
                sliced_states.append((slice_stop_timestamp_s, stop_state))

            if verbose:
                resolved_start_dt = datetime.fromtimestamp(
                    slice_start_timestamp_s, tz=timezone.utc
                )
                resolved_stop_dt = datetime.fromtimestamp(
                    slice_stop_timestamp_s, tz=timezone.utc
                )
                print(
                    f"[slice_oem]   Mode: time range (interpolated boundaries)",
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
            # Use existing states without interpolation
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
        # Interpolate with step size
        sliced_states: list[tuple[float, np.ndarray]] = []
        timestamp_s: float = slice_start_timestamp_s
        while timestamp_s <= slice_stop_timestamp_s:
            step_state = interpolator.interpolate(timestamp_s)
            sliced_states.append((timestamp_s, step_state))
            timestamp_s += options.step_size.total_seconds()

        if verbose:
            resolved_start_dt = datetime.fromtimestamp(
                slice_start_timestamp_s, tz=timezone.utc
            )
            resolved_stop_dt = datetime.fromtimestamp(
                slice_stop_timestamp_s, tz=timezone.utc
            )
            interp_type_str = f"{interpolation_spec.interp_type.value} degree {interpolation_spec.degree}"

            print(
                f"[slice_oem]   Mode: interpolated ({interp_type_str})",
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
                f"[slice_oem]   Step size: {time_utils.format_duration_human(options.step_size)}",
                file=sys.stderr,
            )

    if verbose:
        print(
            f"[slice_oem]   Selected {len(sliced_states)} of {len(states)} states",
            file=sys.stderr,
        )

        if sliced_states:
            first_timestamp_s, _ = sliced_states[0]
            last_timestamp_s, _ = sliced_states[-1]
            first_dt = datetime.fromtimestamp(first_timestamp_s, tz=timezone.utc)
            last_dt = datetime.fromtimestamp(last_timestamp_s, tz=timezone.utc)
            span = last_dt - first_dt
            print(
                f"[slice_oem]   Output start: {time_utils.datetime_to_iso8601(first_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Output end:   {time_utils.datetime_to_iso8601(last_dt)}",
                file=sys.stderr,
            )
            print(
                f"[slice_oem]   Output span:  {time_utils.format_duration_human(span)}",
                file=sys.stderr,
            )

    # Create new CcsdsOem with sliced states and preserved metadata
    return _create_sliced_oem(
        oem,
        sliced_states,
        interpolation_spec=interpolation_spec,
        source_states=states,
        step_size=options.step_size,
    )


def _compute_unusable_margin(
    interpolation_spec: InterpolationSpec | None,
    source_states: list[tuple[float, np.ndarray]],
) -> float:
    """Compute the time margin (seconds) at each boundary where interpolation is UNUSABLE (inaccurate).

    This margin represents the UNUSABLE region near boundaries where interpolation errors are large.
    The margin is based on the minimum number of data points needed for the interpolation stencil,
    scaled conservatively to account for boundary effects.

    Parameters
    ----------
    interpolation_spec : InterpolationSpec | None
        Interpolation specification used. If None, returns 0.
    source_states : list[tuple[float, np.ndarray]]
        Source data states used for interpolation.

    Returns
    -------
    float
        Time margin in seconds representing the UNUSABLE region to inset from each boundary.
    """
    if interpolation_spec is None or len(source_states) < 3:
        return 0.0

    # Estimate average data interval from source states
    first_ts = source_states[0][0]
    last_ts = source_states[-1][0]
    n_intervals = len(source_states) - 1
    avg_interval_s = (last_ts - first_ts) / n_intervals

    if interpolation_spec.interp_type == InterpolationType.HERMITE:
        # Hermite: no UNUSABLE margin needed (derivative info handles boundaries well).
        base_margin_intervals = 0
    elif interpolation_spec.interp_type == InterpolationType.LAGRANGE:
        # Lagrange: lower degrees have larger boundary errors, scale margin with degree.
        # degree 5-7: 2 intervals, degree 9+: 1 interval
        if interpolation_spec.degree <= 7:
            base_margin_intervals = 2
        else:
            base_margin_intervals = 1
    else:
        # Chebyshev: no UNUSABLE margin needed.
        base_margin_intervals = 0

    return base_margin_intervals * avg_interval_s


def _create_sliced_oem(
    original_oem: CcsdsOem,
    sliced_states: list[tuple[float, np.ndarray]],
    interpolation_spec: InterpolationSpec | None = None,
    source_states: list[tuple[float, np.ndarray]] | None = None,
    step_size: timedelta | None = None,
) -> CcsdsOem:
    """Create a new CcsdsOem with sliced states while preserving original metadata.

    This function creates a new OEM object that preserves all header and metadata
    from the original OEM file, except for time-related fields that change due to
    slicing (START_TIME, STOP_TIME, USEABLE_START_TIME, USEABLE_STOP_TIME).

    When interpolation was used, USEABLE_START_TIME and USEABLE_STOP_TIME are set
    to reflect the USABLE region where interpolation accuracy is reliable (excluding
    UNUSABLE boundary effects). If step_size is provided, USABLE boundaries are aligned
    to step boundaries.

    Parameters
    ----------
    original_oem : CcsdsOem
        Original OEM object to copy metadata from.
    sliced_states : list[tuple[float, np.ndarray]]
        List of (timestamp, state_vector) tuples for the sliced data.
    interpolation_spec : InterpolationSpec | None, optional
        Interpolation specification used, for computing USABLE time bounds.
    source_states : list[tuple[float, np.ndarray]] | None, optional
        Original source states used for interpolation (for margin calculation).
    step_size : timedelta | None, optional
        Step size used for interpolation, for aligning USABLE boundaries.

    Returns
    -------
    CcsdsOem
        New CcsdsOem object with sliced states and preserved metadata.
    """
    import copy

    # Deep copy the original header and metadata to preserve all fields
    new_header = copy.deepcopy(original_oem.header)
    new_meta = copy.deepcopy(original_oem.meta)

    # Update the creation date to reflect when the slice was created
    new_header.creation_date = time_utils.datetime_to_iso8601(
        datetime.now(timezone.utc)
    )

    # Update time-related metadata fields based on the sliced states
    if sliced_states:
        start_dt = datetime.fromtimestamp(sliced_states[0][0], tz=timezone.utc)
        stop_dt = datetime.fromtimestamp(sliced_states[-1][0], tz=timezone.utc)

        # Update START_TIME and STOP_TIME to match the sliced data
        new_meta.start_time = time_utils.datetime_to_iso8601(start_dt)
        new_meta.stop_time = time_utils.datetime_to_iso8601(stop_dt)

        # Compute USABLE time range by excluding UNUSABLE boundary margins
        # The margin represents the UNUSABLE region at each boundary
        src = source_states if source_states is not None else sliced_states
        unusable_margin_s = _compute_unusable_margin(interpolation_spec, src)

        if unusable_margin_s > 0.0 and len(sliced_states) > 1:
            # Inset by the UNUSABLE margin to find the USABLE region
            usable_start_ts = sliced_states[0][0] + unusable_margin_s
            usable_stop_ts = sliced_states[-1][0] - unusable_margin_s

            # Align USABLE boundaries to step size if provided
            if step_size is not None:
                step_s = step_size.total_seconds()
                start_ts = sliced_states[0][0]

                # Find first step boundary >= usable_start_ts (first USABLE step)
                steps_from_start = (usable_start_ts - start_ts) / step_s
                aligned_start_steps = int(np.ceil(steps_from_start))
                usable_start_ts = start_ts + aligned_start_steps * step_s

                # Find last step boundary <= usable_stop_ts (last USABLE step)
                steps_to_stop = (usable_stop_ts - start_ts) / step_s
                aligned_stop_steps = int(np.floor(steps_to_stop))
                usable_stop_ts = start_ts + aligned_stop_steps * step_s

            # Only set USABLE_START/STOP_TIME if there's a valid USABLE region
            if usable_start_ts < usable_stop_ts:
                usable_start_dt = datetime.fromtimestamp(
                    usable_start_ts, tz=timezone.utc
                )
                usable_stop_dt = datetime.fromtimestamp(usable_stop_ts, tz=timezone.utc)
                new_meta.useable_start_time = time_utils.datetime_to_iso8601(
                    usable_start_dt
                )
                new_meta.useable_stop_time = time_utils.datetime_to_iso8601(
                    usable_stop_dt
                )
            else:
                # No USABLE region exists (entire output is UNUSABLE)
                new_meta.useable_start_time = ""
                new_meta.useable_stop_time = ""
        else:
            # No interpolation or insufficient data: entire output is USABLE
            new_meta.useable_start_time = ""
            new_meta.useable_stop_time = ""

    # Create and return the new CcsdsOem object
    return CcsdsOem(
        header=new_header,
        meta=new_meta,
        data_comments=copy.deepcopy(original_oem.data_comments),
        states=sliced_states,
    )


def _validate_slice_indices(slice_obj: slice, total_states: int) -> None:
    """Validate slice indices against the source OEM file size.

    Parameters
    ----------
    slice_obj : slice
        The slice object to validate.
    total_states : int
        Total number of states in the source OEM file.

    Raises
    ------
    IndexError
        If slice indices are out of range for the source OEM file.
    ValueError
        If stop index is less than start index (when both are explicitly provided
        and within valid range).

    Notes
    -----
    This validation catches common user errors while allowing valid Python slice
    behavior. Out-of-range indices that would result in empty slices are allowed
    (consistent with Python list slicing), but we validate that:

    1. Negative indices are within bounds (e.g., -1 to -total_states)
    2. When both start and stop are explicitly provided and within range,
       stop must be >= start (for positive step)
    """
    if total_states == 0:
        raise IndexError("Cannot slice empty OEM file (0 states)")

    # Validate negative indices are within bounds
    # Negative indices must be in range [-total_states, -1]
    if slice_obj.start is not None and slice_obj.start < 0:
        if abs(slice_obj.start) > total_states:
            raise IndexError(
                f"Start index {slice_obj.start} is out of range for OEM file with "
                f"{total_states} states (valid negative range: -{total_states} to -1)"
            )

    if slice_obj.stop is not None and slice_obj.stop < 0:
        if abs(slice_obj.stop) > total_states:
            raise IndexError(
                f"Stop index {slice_obj.stop} is out of range for OEM file with "
                f"{total_states} states (valid negative range: -{total_states} to -1)"
            )

    # Check for stop < start when both are explicitly provided and within valid range
    # Only validate this for positive indices within bounds to catch obvious user errors
    if (
        slice_obj.start is not None
        and slice_obj.stop is not None
        and slice_obj.start >= 0
        and slice_obj.stop >= 0
        and slice_obj.start < total_states
        and slice_obj.stop <= total_states
    ):
        # Both indices are valid and within range, check ordering
        if slice_obj.stop < slice_obj.start:
            raise ValueError(
                f"Invalid slice: stop index ({slice_obj.stop}) must be greater than or equal to "
                f"start index ({slice_obj.start}) for OEM file with {total_states} states"
            )


def _validate_time_range(
    slice_start_timestamp_s: float,
    slice_stop_timestamp_s: float,
    base_start_timestamp_s: float,
    base_stop_timestamp_s: float,
    options: TimeSliceOptions,
) -> None:
    """Validate time range for time-based slicing.

    Parameters
    ----------
    slice_start_timestamp_s : float
        Resolved start timestamp in seconds (POSIX time).
    slice_stop_timestamp_s : float
        Resolved stop timestamp in seconds (POSIX time).
    base_start_timestamp_s : float
        First timestamp in the OEM file.
    base_stop_timestamp_s : float
        Last timestamp in the OEM file.
    options : TimeSliceOptions
        Original time slice options for error reporting.

    Raises
    ------
    ValueError
        If stop time is before start time, or if requested times are outside
        the OEM file's time range.

    Notes
    -----
    This validation helps catch common user errors in time-based slicing:

    1. Stop time must be >= start time (unless single state extraction)
    2. Requested times should be within or near the OEM file's time range
    """
    # Check that stop >= start (for range queries, not single state)
    if (
        options.stop_time is not None
        and slice_stop_timestamp_s < slice_start_timestamp_s
    ):
        # Format times for error message
        start_dt = datetime.fromtimestamp(slice_start_timestamp_s, tz=timezone.utc)
        stop_dt = datetime.fromtimestamp(slice_stop_timestamp_s, tz=timezone.utc)

        # Build descriptive error message based on input type
        if isinstance(options.start_time, datetime):
            start_str = time_utils.datetime_to_iso8601(options.start_time)
        elif isinstance(options.start_time, timedelta):
            start_str = f"offset {time_utils.format_duration_human(options.start_time)}"
        else:
            start_str = "OEM start"

        if isinstance(options.stop_time, datetime):
            stop_str = time_utils.datetime_to_iso8601(options.stop_time)
        elif isinstance(options.stop_time, timedelta):
            stop_str = f"offset {time_utils.format_duration_human(options.stop_time)}"
        else:
            stop_str = "OEM end"

        raise ValueError(
            f"Invalid time slice: stop time must be >= start time.\n"
            f"  Requested start: {start_str}\n"
            f"  Requested stop:  {stop_str}\n"
            f"  Resolved start:  {time_utils.datetime_to_iso8601(start_dt)}\n"
            f"  Resolved stop:   {time_utils.datetime_to_iso8601(stop_dt)}"
        )

    # Check if requested times are outside OEM range (warning-level check)
    # Allow some tolerance for interpolation, but catch obvious errors
    oem_duration = base_stop_timestamp_s - base_start_timestamp_s
    tolerance = oem_duration * 0.1  # 10% tolerance

    if slice_start_timestamp_s < (base_start_timestamp_s - tolerance):
        start_dt = datetime.fromtimestamp(slice_start_timestamp_s, tz=timezone.utc)
        oem_start_dt = datetime.fromtimestamp(base_start_timestamp_s, tz=timezone.utc)
        raise ValueError(
            f"Start time {time_utils.datetime_to_iso8601(start_dt)} is before "
            f"OEM file start time {time_utils.datetime_to_iso8601(oem_start_dt)}"
        )

    if slice_stop_timestamp_s > (base_stop_timestamp_s + tolerance):
        stop_dt = datetime.fromtimestamp(slice_stop_timestamp_s, tz=timezone.utc)
        oem_stop_dt = datetime.fromtimestamp(base_stop_timestamp_s, tz=timezone.utc)
        raise ValueError(
            f"Stop time {time_utils.datetime_to_iso8601(stop_dt)} is after "
            f"OEM file stop time {time_utils.datetime_to_iso8601(oem_stop_dt)}"
        )
