"""Time conversion and parsing utilities for tudatpy-utils.

This module provides time-related functionality including:
- Time scale conversions between UTC and TDB (Barycentric Dynamical Time)
- ISO 8601 datetime string parsing and formatting
- CLI duration parsing with unit support

The time conversion functions use Tudat's time scale converter to handle
leap seconds and relativistic corrections when converting between UTC and TDB.

References:
    ISO 8601 "Date and time representations".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from tudatpy.astro import time_representation
from tudatpy.astro.time_representation import TimeScales

# ===================================================================
# Module-level state
# ===================================================================

_tudat_time_scale_converter: time_representation.TimeScaleConverter = (
    time_representation.default_time_scale_converter()
)
"""Tudat time scale converter for UTC ↔ TDB conversions."""

_UTC_J2000_DATETIME: datetime = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
"""J2000 epoch in UTC (2000-01-01 12:00:00 UTC)."""

_ISO8601_PATTERN: re.Pattern[str] = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})(T| )(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$"
)
"""Regex pattern for ISO 8601 datetime format validation."""


# ===================================================================
# Time conversion
# ===================================================================


def datetime_to_tdb_s(dt: datetime) -> float:
    """Convert a datetime object to TDB (ephemeris time) seconds since J2000.

    Parameters
    ----------
    dt : datetime
        Datetime object to convert.

    Returns
    -------
    float
        TDB seconds since J2000 epoch (s).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    utc_j2000_s: float = (dt - _UTC_J2000_DATETIME).total_seconds()
    return _tudat_time_scale_converter.convert_time(
        input_value=utc_j2000_s,
        input_scale=TimeScales.utc_scale,
        output_scale=TimeScales.tdb_scale,
    )


def tdb_s_to_datetime(tdb_s: float) -> datetime:
    """Convert TDB (ephemeris time) seconds since J2000 to a UTC datetime object.

    Parameters
    ----------
    tdb_s : float
        TDB seconds since J2000 epoch (s).

    Returns
    -------
    datetime
        UTC datetime object.
    """
    utc_j2000_s: float = _tudat_time_scale_converter.convert_time(
        input_value=tdb_s,
        input_scale=TimeScales.tdb_scale,
        output_scale=TimeScales.utc_scale,
    )
    return _UTC_J2000_DATETIME + timedelta(seconds=utc_j2000_s)


# ===================================================================
# ISO 8601 parsing and formatting
# ===================================================================


def iso8601_to_datetime(epoch_str: str) -> datetime:
    """Parse an ISO 8601 epoch string into a :class:`datetime`.

    Parameters
    ----------
    epoch_str : str
        ISO 8601 formatted datetime string to parse.

    Returns
    -------
    datetime
        Parsed datetime object with UTC timezone.

    Notes
    -----
    Supports various ISO 8601 formats including:
    - With 'T' separator: 2000-01-01T12:00:00, 2000-01-01T12:00:00.123
    - With space separator: 2000-01-01 12:00:00, 2000-01-01 12:00:00.123
    - With 'Z' timezone indicator: 2000-01-01T12:00:00Z
    - With fractional seconds: 2000-01-01T12:00:00.123456
    """
    s: str = epoch_str.strip()
    if s.endswith("Z"):
        s = s[:-1]

    # Use regex to detect format: YYYY-MM-DD[T| ]HH:MM:SS[.ffffff]
    match: re.Match[str] | None = _ISO8601_PATTERN.match(s)

    if not match:
        raise ValueError(
            f"Unable to parse epoch string '{epoch_str}'. "
            "Expected ISO 8601 format like '2000-01-01T12:00:00' or '2000-01-01 12:00:00' "
            "with optional fractional seconds and 'Z' timezone indicator."
        )

    # Determine separator (T or space)
    separator_char: str = match.group(4)
    separator: str = "T" if separator_char == "T" else " "

    # Determine if fractional seconds are present
    has_fractional: bool = match.group(8) is not None

    # Build the format string based on detected format
    if has_fractional:
        format_str: str = f"%Y-%m-%d{separator}%H:%M:%S.%f"
    else:
        format_str = f"%Y-%m-%d{separator}%H:%M:%S"

    try:
        return datetime.strptime(s, format_str).replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(
            f"Unable to parse epoch string '{epoch_str}'. "
            "Expected ISO 8601 format like '2000-01-01T12:00:00' or '2000-01-01 12:00:00' "
            "with optional fractional seconds and 'Z' timezone indicator."
        ) from e


def datetime_to_iso8601(
    dt: datetime, use_t_separator: bool = True, fractional_second_places: int = 3
) -> str:
    """Convert a datetime object to an ISO 8601 formatted string in UTC.

    Parameters
    ----------
    dt : datetime
        Datetime object to convert.
    use_t_separator : bool, optional
        If True, use 'T' as separator between date and time (ISO 8601 standard).
        If False, use a space instead. Default is True.
    fractional_second_places : int, optional
        Number of decimal places for fractional seconds. Default is 3.

    Returns
    -------
    str
        ISO 8601 formatted datetime string in UTC.

    See Also
    --------
    iso8601_to_datetime : Inverse operation (parse ISO 8601 string to datetime).
    """
    # Convert to UTC timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    separator: str = "T" if use_t_separator else " "

    # Format the datetime with full microseconds
    formatted: str = dt.strftime(f"%Y-%m-%d{separator}%H:%M:%S.%f")

    # Adjust fractional seconds to the requested number of places
    if fractional_second_places == 0:
        # Remove the decimal point and fractional part
        formatted = formatted.rsplit(".", 1)[0]
    else:
        # Truncate or pad fractional seconds to the requested number of places
        date_time_part, fractional_part = formatted.rsplit(".", 1)
        fractional_part = fractional_part[:fractional_second_places].ljust(
            fractional_second_places, "0"
        )
        formatted = f"{date_time_part}.{fractional_part}"

    return formatted


# ===================================================================
# CLI duration parsing
# ===================================================================

SECONDS_PER_MINUTE: float = 60.0
"""Seconds in one minute."""

SECONDS_PER_HOUR: float = 3600.0
"""Seconds in one hour."""

SECONDS_PER_DAY: float = 86400.0
"""Seconds in one day."""

_UNIT_TO_SECONDS: dict[str, float] = {
    "s": 1.0,
    "m": SECONDS_PER_MINUTE,
    "h": SECONDS_PER_HOUR,
    "d": SECONDS_PER_DAY,
}
"""Mapping from unit character to seconds multiplier."""


def parse_duration_to_timedelta(
    value: str,
    default_unit: str = "s",
    allow_negative: bool = False,
    allow_zero: bool = False,
) -> timedelta:
    """Parse a duration string and return a timedelta.

    Supports both single-component durations (e.g., ``"5m"``, ``"90s"``) and
    multi-component durations (e.g., ``"1h30m"``, ``"2m30s"``). If no unit is
    specified, the ``default_unit`` is applied.

    Parameters
    ----------
    value : str
        Duration string with optional unit suffix (s, m, h, d).
        Supports multi-component format like ``"1h30m"`` or ``"2m30s"``.
        May be prefixed with ``+`` or ``-`` for signed durations.
    default_unit : str, optional
        Unit to apply when no unit suffix is present. Default is ``"s"`` (seconds).
        Must be one of: ``"s"``, ``"m"``, ``"h"``, ``"d"``.
    allow_negative : bool, optional
        If True, allow negative durations (default: False).
    allow_zero : bool, optional
        If True, allow zero durations (default: False).

    Returns
    -------
    timedelta
        Parsed duration as a timedelta object.

    Raises
    ------
    ValueError
        If the duration string is malformed or violates constraints.

    See Also
    --------
    parse_duration_to_seconds : Convenience wrapper with same default unit ``"s"``.
    """
    # Fall back to multi-component parsing for complex durations like "1h30m"
    token: str = value.strip()
    if not token:
        raise ValueError(
            f"{value}: duration must be a number optionally followed by s, m, h, or d. (a)"
        )

    sign: int = 1
    if token[0] in "+-":
        if token[0] == "-":
            if not allow_negative:
                raise ValueError(f"{value}: duration must be a positive value")
            sign = -1
        token = token[1:].strip()

    if not token:
        raise ValueError(
            f"{value}: duration must be a number optionally followed by s, m, h, or d. (b)"
        )

    component_re: re.Pattern[str] = re.compile(r"^([0-9]*\.?[0-9]+)\s*([smhdSMHD]?)")
    pos: int = 0
    total_seconds: float = 0.0
    components: list[tuple[float, str]] = []

    while pos < len(token):
        match: re.Match[str] | None = component_re.match(token, pos)
        if not match:
            raise ValueError(
                f"{value}: duration must be a number optionally followed by s, m, h, or d. (c)"
            )
        magnitude: float = float(match.group(1))
        unit: str = match.group(2).lower() if match.group(2) else default_unit
        components.append((magnitude, unit))
        pos = match.end()

    if not components:
        raise ValueError(
            f"{value}: duration must be a number optionally followed by s, m, h, or d. (d)"
        )

    if len(components) == 1 and components[0][1] == "":
        components[0] = (components[0][0], default_unit)

    for magnitude, unit in components:
        if magnitude == 0.0 and not allow_zero:
            raise ValueError(f"{value}: duration must be a positive value")
        if unit == "s":
            total_seconds += magnitude
        elif unit == "m":
            total_seconds += magnitude * 60.0
        elif unit == "h":
            total_seconds += magnitude * 3600.0
        elif unit == "d":
            total_seconds += magnitude * 86400.0
        else:
            raise ValueError(f"{value}: duration unit must be one of: s, m, h, d. (e)")

    return timedelta(seconds=sign * total_seconds)


def parse_duration_to_seconds(
    value: str,
    default_unit: str = "s",
    allow_negative: bool = False,
    allow_zero: bool = False,
) -> float:
    """Parse a duration string and convert it to seconds.

    Convenience wrapper around :func:`parse_duration_to_timedelta` that returns
    the duration as a float in seconds rather than a timedelta object.

    Parameters
    ----------
    value : str
        Duration string with optional unit suffix (s, m, h, d).
        Supports multi-component format like ``"1h30m"`` or ``"2m30s"``.
        May be prefixed with ``+`` or ``-`` for signed durations.
    default_unit : str, optional
        Unit to apply when no unit suffix is present. Default is ``"s"`` (seconds).
        Must be one of: ``"s"``, ``"m"``, ``"h"``, ``"d"``.
    allow_negative : bool, optional
        If True, allow negative durations (default: False).
    allow_zero : bool, optional
        If True, allow zero durations (default: False).

    Returns
    -------
    float
        Duration in seconds (s).

    Raises
    ------
    ValueError
        If the duration string is malformed or violates constraints.

    See Also
    --------
    parse_duration_to_timedelta : Full-featured duration parser returning timedelta.
    """
    return parse_duration_to_timedelta(
        value,
        default_unit=default_unit,
        allow_negative=allow_negative,
        allow_zero=allow_zero,
    ).total_seconds()
