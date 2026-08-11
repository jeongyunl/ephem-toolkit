"""Data structures for orbit delta plotting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

import tudatpy_utils.core.interpolator.lagrange as lagrange

from .constants import INTERPOLATION_DEGREE


@dataclass
class StateHistory:
    """Orbit trajectory with state history and optional interpolator."""

    label: str
    """Label or identifier for the orbit (e.g., filename)."""

    state_history: dict[float, np.ndarray]
    """Mapping of POSIX epoch timestamps (seconds) to 6-element state vectors [x, y, z, vx, vy, vz] in meters (m) and m/s.
    
    Data is stored internally in SI units (m, m/s) as returned by the OEM reader,
    but will be converted to km and km/s for plotting and CSV export.
    """

    interpolator: lagrange.LagrangeInterpolator | None = None
    """Lagrange interpolator for querying state at arbitrary timestamps; initialised lazily on first use."""

    timestamps: list[float] | None = None
    """Sorted list of epoch timestamps from state_history keys; populated automatically in __post_init__."""

    def __post_init__(self) -> None:
        """Initialize epochs field from state_history keys."""
        if not self.timestamps:
            self.timestamps = list(self.state_history.keys())

    def get_start_time(self) -> float:
        """Return the earliest timestamp in the stored state history.

        Returns
        -------
        float
            Earliest timestamp (seconds since epoch).
        """
        return self.timestamps[0]

    def get_stop_time(self) -> float:
        """Return the latest timestamp in the stored state history.

        Returns
        -------
        float
            Latest timestamp (seconds since epoch).
        """
        return self.timestamps[-1]

    def get_interpolated_state(self, timestamp: float) -> np.ndarray | None:
        """Get interpolated state at a given timestamp.

        Parameters
        ----------
        timestamp : float
            Timestamp to interpolate at (seconds since epoch).

        Returns
        -------
        np.ndarray | None
            Interpolated state vector [x, y, z, vx, vy, vz] if timestamp is within
            interpolator bounds, None otherwise.

        Raises
        ------
        ValueError
            If no interpolator has been set for this StateHistory object.
        """

        if self.interpolator is None:
            interp: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=INTERPOLATION_DEGREE
            )
            interp.set_data(self.state_history)
            self.interpolator = interp

        if (
            timestamp < self.interpolator.independent_values[2]
            or timestamp > self.interpolator.independent_values[-3]
        ):
            return None

        interpolated_state: np.ndarray = self.interpolator.interpolate(timestamp)

        return interpolated_state


class TimeUnit(Enum):
    """Enumeration for time units in plots."""

    MINUTES = "minutes"
    """Time unit in minutes; divisor 60 s/min."""

    HOURS = "hours"
    """Time unit in hours; divisor 3600 s/h."""

    @classmethod
    def from_string(cls, value: str) -> TimeUnit:
        """Convert string to TimeUnit enum.

        Parameters
        ----------
        value : str
            String representation: 'm', 'minute', 'minutes', 'h', 'hour', or 'hours'.

        Returns
        -------
        TimeUnit
            Corresponding TimeUnit enum value.

        Raises
        ------
        ValueError
            If the string doesn't match any known time unit.
        """
        value_lower: str = value.lower()
        if value_lower in ["m", "minute", "minutes"]:
            return cls.MINUTES
        elif value_lower in ["h", "hour", "hours"]:
            return cls.HOURS
        else:
            raise ValueError(
                f"Invalid time unit: {value}. Must be one of: m, minute, minutes, h, hour, hours"
            )

    def get_divisor(self) -> float:
        """Get the divisor to convert seconds to this time unit.

        Returns
        -------
        float
            Divisor value (60 for minutes, 3600 for hours).
        """
        if self == TimeUnit.MINUTES:
            return 60.0
        elif self == TimeUnit.HOURS:
            return 3600.0
        else:
            raise ValueError(f"Unknown time unit: {self}")

    def get_label(self) -> str:
        """Get the label for this time unit.

        Returns
        -------
        str
            Label string for use in plot axes.
        """
        if self == TimeUnit.MINUTES:
            return "Time from Start (minutes)"
        elif self == TimeUnit.HOURS:
            return "Time from Start (hours)"
        else:
            raise ValueError(f"Unknown time unit: {self}")
