"""Time-axis units for OEM playback and plot views."""

from __future__ import annotations

from enum import Enum


class TimeUnit(Enum):
    """Enumeration for time units used on time-series x-axes."""

    MINUTES = "minutes"
    """Time unit in minutes; divisor 60 s/min."""

    HOURS = "hours"
    """Time unit in hours; divisor 3600 s/h."""

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
            return 60.0
        if self == TimeUnit.HOURS:
            return 3600.0
        raise ValueError(f"Unknown time unit: {self}")

    def get_axis_label(self) -> str:
        """Return the elapsed-time axis label."""
        if self == TimeUnit.MINUTES:
            return "Time from Start (minutes)"
        if self == TimeUnit.HOURS:
            return "Time from Start (hours)"
        raise ValueError(f"Unknown time unit: {self}")
