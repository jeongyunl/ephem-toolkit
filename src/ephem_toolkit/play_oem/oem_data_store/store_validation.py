"""OEM store request and coordinate validation helpers."""

from __future__ import annotations

import math

from .public_types import TimeBounds


def validate_time_bounds(bounds_s: TimeBounds) -> TimeBounds:
    try:
        start_value, stop_value = bounds_s
    except (TypeError, ValueError) as error:
        raise ValueError(
            "time bounds must contain exactly two finite values"
        ) from error
    if isinstance(start_value, bool) or isinstance(stop_value, bool):
        raise ValueError("time bounds must contain exactly two finite values")
    try:
        start = float(start_value)
        stop = float(stop_value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "time bounds must contain exactly two finite values"
        ) from error
    if not math.isfinite(start) or not math.isfinite(stop) or start > stop:
        raise ValueError("time bounds must be finite and ordered")
    return start, stop


def normalize_longitude(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("center_longitude_deg must be finite")
    try:
        longitude = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("center_longitude_deg must be finite") from error
    if not math.isfinite(longitude):
        raise ValueError("center_longitude_deg must be finite")
    return ((longitude + 180.0) % 360.0) - 180.0


def validate_nonnegative_finite(
    value: float,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite non-negative number") from error
    if not math.isfinite(converted) or converted < 0.0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return converted


def validate_elevation_threshold(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("minimum_elevation_deg must be an integer from 0 through 90")
    converted = float(value)
    if (
        not math.isfinite(converted)
        or converted < 0
        or converted > 90
        or not converted.is_integer()
    ):
        raise ValueError("minimum_elevation_deg must be an integer from 0 through 90")
    return int(converted)


def validate_query_time(t_s: float) -> float:
    if isinstance(t_s, bool):
        raise ValueError("query time must be a finite number")
    try:
        query_time = float(t_s)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("query time must be a finite number") from error
    if not math.isfinite(query_time):
        raise ValueError("query time must be a finite number")
    return query_time
