"""Formatting helpers for timestamps shown by the playback application."""

from __future__ import annotations

from datetime import datetime, timezone
from ephem_toolkit.core import time_utils

UTC_DISPLAY = "UTC"
LOCAL_DISPLAY = "local"
DISPLAY_TIME_ZONES = (UTC_DISPLAY, LOCAL_DISPLAY)


def format_datetime(
    value: datetime,
    display_time_zone: str = UTC_DISPLAY,
    *,
    fractional_second_places: int = 3,
) -> str:
    """Format a timestamp in UTC or the machine's local time zone with a suffix."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if display_time_zone == UTC_DISPLAY:
        converted = value.astimezone(timezone.utc)
        suffix = "UTC"
    elif display_time_zone == LOCAL_DISPLAY:
        converted = value.astimezone()
        suffix = converted.tzname() or "Local"
    else:
        raise ValueError("display_time_zone must be 'UTC' or 'local'")

    formatted = converted.strftime("%Y-%m-%dT%H:%M:%S")
    if fractional_second_places:
        fraction = f"{converted.microsecond:06d}"[:fractional_second_places].ljust(
            fractional_second_places, "0"
        )
        formatted += f".{fraction}"
    return f"{formatted} {suffix}"


def format_tt(
    time_s: float,
    display_time_zone: str = UTC_DISPLAY,
    *,
    fractional_second_places: int = 3,
) -> str:
    """Format TT seconds as a timestamp in the selected display time zone."""
    return format_datetime(
        time_utils.tt_s_to_datetime(time_s),
        display_time_zone,
        fractional_second_places=fractional_second_places,
    )


def format_timestamp_text(value: str, display_time_zone: str) -> str:
    """Format an ISO timestamp from OEM metadata when it is parseable."""
    try:
        parsed = time_utils.iso8601_to_datetime(value)
    except (TypeError, ValueError):
        return value
    return format_datetime(parsed, display_time_zone)
