"""Time-axis units for OEM playback and plot views."""

from __future__ import annotations

from enum import Enum

SECONDS_PER_MINUTE: float = 60.0
"""Number of seconds in a minute."""

MINUTES_PER_HOUR: float = 60.0
"""Number of minutes in an hour."""

SECONDS_PER_HOUR: float = MINUTES_PER_HOUR * SECONDS_PER_MINUTE
"""Number of seconds in an hour."""

TIME_UNIT_SWITCH_SECONDS: float = SECONDS_PER_HOUR
"""Use minutes for spans shorter than an hour, and hours for longer spans."""


class TimeUnit(Enum):
    """Enumeration for time units used on time-series x-axes."""

    MINUTES = "minutes"
    """Time unit in minutes; divisor 60 s/min."""

    HOURS = "hours"
    """Time unit in hours; divisor 3600 s/h."""

    @classmethod
    def for_duration(cls, duration_s: float) -> TimeUnit:
        """Choose an axis unit that keeps shorter timelines easy to read."""
        if duration_s < TIME_UNIT_SWITCH_SECONDS:
            return cls.MINUTES
        return cls.HOURS

    @classmethod
    def from_string(cls, value: str) -> TimeUnit:
        """Convert a string token to a TimeUnit."""
        value_lower = value.lower()
        if value_lower in ["m", "minute", "minutes"]:
            return cls.MINUTES
        if value_lower in ["h", "hour", "hours"]:
            return cls.HOURS
        raise ValueError(
            f"Invalid time unit: {value}. "
            "Must be one of: m, minute, minutes, h, hour, hours"
        )

    def get_divisor_s(self) -> float:
        """Return the seconds per selected time unit."""
        if self == TimeUnit.MINUTES:
            return SECONDS_PER_MINUTE
        if self == TimeUnit.HOURS:
            return SECONDS_PER_HOUR
        raise ValueError(f"Unknown time unit: {self}")

    def get_axis_label(self) -> str:
        """Return the elapsed-time axis label."""
        if self == TimeUnit.MINUTES:
            return "Time from Start (minutes)"
        if self == TimeUnit.HOURS:
            return "Time from Start (hours)"
        raise ValueError(f"Unknown time unit: {self}")
