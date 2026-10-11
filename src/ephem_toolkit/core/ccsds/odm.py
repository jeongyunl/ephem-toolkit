"""CCSDS Orbit Data Message (ODM)."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Mapping

REF_FRAME_DESCRIPTIONS: dict[str, str] = {
    "EME2000": "Earth Mean Equator and Equinox of J2000",
    "GCRF": "Geocentric Celestial Reference Frame",
    "GRC": "Greenwich Rotating Coordinates",
    "ICRF": "International Celestial Reference Frame",
    "ITRF": "International Terrestrial Reference Frame",
    "ITRF2000": "International Terrestrial Reference Frame 2000",
    "ITRF1993": "International Terrestrial Reference Frame 1993",
    "ITRF1997": "International Terrestrial Reference Frame 1997",
    "MCI": "Mars Centered Inertial",
    "TDR": "True of Date, Rotating",
    "TEME": "True Equator Mean Equinox (only used in OMMs)",
    "TOD": "True of Date",
}
"""Descriptions of reference frames permitted by the ODM standards."""


REF_FRAME_VALUES: frozenset[str] = frozenset(REF_FRAME_DESCRIPTIONS)
"""Reference-frame identifiers permitted in OEM and OMM files."""


REF_FRAMES: frozenset[str] = REF_FRAME_VALUES
"""Alias for :data:`REF_FRAME_VALUES`."""


TIME_SYSTEM_DESCRIPTIONS: dict[str, str] = {
    "GMST": "Greenwich Mean Sidereal Time",
    "GPS": "Global Positioning System",
    "MET": "Mission Elapsed Time (note)",
    "MRT": "Mission Relative Time (note)",
    "SCLK": "Spacecraft Clock (receiver) (requires rules for interpretation in ICD)",
    "TAI": "International Atomic Time",
    "TCB": "Barycentric Coordinate Time",
    "TDB": "Barycentric Dynamical Time",
    "TCG": "Geocentric Coordinate Time",
    "TT": "Terrestrial Time",
    "UT1": "Universal Time",
    "UTC": "Coordinated Universal Time",
}
"""Descriptions of time systems permitted by the ODM standards."""


TIME_SYSTEM_VALUES: frozenset[str] = frozenset(TIME_SYSTEM_DESCRIPTIONS)
"""Time-system identifiers permitted in OEM and OMM files."""


TIME_SYSTEMS: frozenset[str] = TIME_SYSTEM_VALUES
"""Alias for :data:`TIME_SYSTEM_VALUES`."""


_TOOLKIT_REF_FRAME_VALUES: frozenset[str] = frozenset({"J2000", "ITRF93"})
"""Reference-frame aliases accepted by existing toolkit routes."""

COVARIANCE_DIMENSION = 6
"""Number of position and velocity components in ODM covariance matrices."""

COVARIANCE_KEYS: tuple[str, ...] = (
    "CX_X",
    "CY_X",
    "CY_Y",
    "CZ_X",
    "CZ_Y",
    "CZ_Z",
    "CX_DOT_X",
    "CX_DOT_Y",
    "CX_DOT_Z",
    "CX_DOT_X_DOT",
    "CY_DOT_X",
    "CY_DOT_Y",
    "CY_DOT_Z",
    "CY_DOT_X_DOT",
    "CY_DOT_Y_DOT",
    "CZ_DOT_X",
    "CZ_DOT_Y",
    "CZ_DOT_Z",
    "CZ_DOT_X_DOT",
    "CZ_DOT_Y_DOT",
    "CZ_DOT_Z_DOT",
)
"""Covariance elements in lower-triangular row order."""

COVARIANCE_POSITIONS: tuple[tuple[int, int], ...] = tuple(
    (row, column) for row in range(COVARIANCE_DIMENSION) for column in range(row + 1)
)
"""Matrix coordinates corresponding to :data:`COVARIANCE_KEYS`."""

ODM_UNIT_BY_KEY: dict[str, str] = {
    "SEMI_MAJOR_AXIS": "km",
    "INCLINATION": "deg",
    "RA_OF_ASC_NODE": "deg",
    "ARG_OF_PERICENTER": "deg",
    "TRUE_ANOMALY": "deg",
    "MEAN_ANOMALY": "deg",
    "GM": "km**3/s**2",
    "MASS": "kg",
    "SOLAR_RAD_AREA": "m**2",
    "DRAG_AREA": "m**2",
}
for _covariance_key, (_row, _column) in zip(COVARIANCE_KEYS, COVARIANCE_POSITIONS):
    if _row < 3 and _column < 3:
        ODM_UNIT_BY_KEY[_covariance_key] = "km**2"
    elif _row >= 3 and _column < 3:
        ODM_UNIT_BY_KEY[_covariance_key] = "km**2/s"
    else:
        ODM_UNIT_BY_KEY[_covariance_key] = "km**2/s**2"
"""Native units shared by OPM and OMM fields."""


def validate_odm_context(
    center_name: str,
    ref_frame: str,
    time_system: str,
    *,
    require_center: bool = True,
) -> None:
    """Validate populated ODM center, reference-frame, and time-system values."""
    if require_center and not center_name.strip():
        raise ValueError("CENTER_NAME must not be empty")
    if ref_frame and ref_frame not in REF_FRAME_VALUES | _TOOLKIT_REF_FRAME_VALUES:
        raise ValueError(f"Unsupported ODM REF_FRAME: {ref_frame}")
    if time_system and time_system not in TIME_SYSTEM_VALUES:
        raise ValueError(f"Unsupported ODM TIME_SYSTEM: {time_system}")


CCSDS_TIMECODE_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:\s*)?(?P<yr>\d{4})-(?P<mo>\d{2})-(?P<dy>\d{2})T"
    r"(?P<hr>\d{2}):(?P<mn>\d{2}):(?P<sc>\d{2}(?:\.\d{1,16})?)(?:\s*)?$"
)
"""Regex for CCSDS timecode values used in OEM and OMM metadata."""


CCSDS_NON_DECIMAL_STRING_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:\s*)(?P<value>(?:(?:[0-9A-Z_\- ]*)|(?:[0-9a-z_\- ]*)))(?:\s*)$"
)
"""Regex for NonDecimalString metadata entries in CCSDS ODM files."""


CCSDS_FREE_TEXT_STRING_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:\s*)(?P<value>(?:(?:[0-9A-Z_\.\- ]*)|(?:[0-9a-z_\.\- ]*)))(?:\s*)$"
)
"""Regex for FreeTextString metadata entries in CCSDS ODM files."""


CCSDS_NUMERICAL_VALUE_WITH_OPTIONAL_UNITS_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:\s*)(?P<value>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"(?:\s+\[(?P<unit>[0-9A-Za-z/_*]+)\])?\s*$"
)
"""Regex for numeric value with optional CCSDS units."""


CCSDS_3VALUE_NUMERICAL_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*(?P<value1>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
    r"(?P<value2>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
    r"(?P<value3>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$"
)
"""Regex for multipartite CCSDS numerical values in a 3-value sequence."""

ODM_MAX_LINE_LENGTH = 254
"""Maximum permitted length of a CCSDS ODM KVN line."""

CCSDS_COMMENT_KEYWORD = "COMMENT"
"""Keyword identifying CCSDS ODM comment lines."""

CCSDS_COMMENT_PREFIX = f"{CCSDS_COMMENT_KEYWORD} "
"""Required token and trailing blank for a CCSDS KVN comment line."""

CCSDS_DATETIME_VALUE_PATTERN = re.compile(
    r"(?P<year>\d{4})-(?:(?P<month>0[1-9]|1[0-2])-"
    r"(?P<day>0[1-9]|[12]\d|3[01])|(?P<ordinal_day>00[1-9]|0[1-9]\d|"
    r"[12]\d{2}|3[0-5]\d|36[0-6]))T"
    r"(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d):"
    r"(?P<second>[0-5]\d|60)(?:\.\d{1,16})?Z?"
)
"""Common calendar-date or ordinal-date CCSDS time value syntax."""

CCSDS_NUMERIC_VALUE_PATTERN = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?")
"""Common CCSDS numeric syntax with a digit before the decimal point."""

CCSDS_FLOATING_POINT_VALUE_PATTERN = re.compile(r"[+-]?\d+\.\d+[Ee][+-]?\d+")
"""CCSDS floating-point form with a decimal mantissa and exponent."""

CCSDS_LEADING_DECIMAL_VALUE_PATTERN = re.compile(r"[+-]?\.\d+(?:[Ee][+-]?\d+)?")
"""Compatibility form accepted with a warning by popular OMM producers."""

CCSDS_USER_DEFINED_KEY_PATTERN = re.compile(r"USER_DEFINED_[A-Z0-9_]+")
"""Syntax of permitted user-defined ODM keywords."""


def parse_kvn_assignment(line: str) -> tuple[str, str] | None:
    """Parse a KVN ``KEY = VALUE`` assignment, returning ``None`` if absent."""
    if line.count("=") != 1:
        return None
    key, _, value = line.partition("=")
    return key.strip(), value.strip()


def validate_odm_line(
    line: str,
    message_type: str,
    *,
    printable_ascii: bool = True,
    line_number: int | None = None,
) -> None:
    """Validate shared ODM KVN line length and character-set constraints."""
    location = f" line {line_number}" if line_number is not None else ""
    if len(line) > ODM_MAX_LINE_LENGTH:
        raise ValueError(
            f"{message_type}{location} exceeds {ODM_MAX_LINE_LENGTH} characters "
            f"({ODM_MAX_LINE_LENGTH}-character limit)"
        )
    if printable_ascii and any(ord(char) < 32 or ord(char) > 126 for char in line):
        raise ValueError(
            f"{message_type}{location} is not ASCII printable text; "
            "lines must contain printable ASCII only"
        )


def validate_odm_unit(
    key: str, value: str, units: Mapping[str, str], message_type: str
) -> str:
    """Validate and remove a trailing unit expression when present."""
    if "[" not in value and "]" not in value:
        return value
    unit_match = re.search(r"\s+\[([^\]]*)\]$", value)
    if unit_match is None:
        raise ValueError(f"Invalid unit notation for {message_type} keyword {key}")
    expected_unit = units.get(key)
    if expected_unit is None or unit_match.group(1) != expected_unit:
        raise ValueError(f"Invalid unit for {message_type} keyword {key}")
    return value[: unit_match.start()].rstrip()


def validate_odm_numeric(
    key: str,
    value: str,
    message_type: str,
    *,
    allow_leading_decimal: bool = False,
) -> tuple[str, bool]:
    """Validate a CCSDS numeric value and return normalized value and compatibility flag."""
    if CCSDS_NUMERIC_VALUE_PATTERN.fullmatch(value):
        compatibility_value = False
    elif allow_leading_decimal and CCSDS_LEADING_DECIMAL_VALUE_PATTERN.fullmatch(value):
        value = re.sub(r"^([+-]?)\.", r"\g<1>0.", value)
        compatibility_value = True
    else:
        raise ValueError(
            f"Invalid numeric value for {message_type} keyword {key}: {value}"
        )
    if "E" in value.upper() and not CCSDS_FLOATING_POINT_VALUE_PATTERN.fullmatch(value):
        raise ValueError(
            f"Invalid floating-point value for {message_type} keyword {key}"
        )
    mantissa = re.split("[Ee]", value)[0].lstrip("+-").replace(".", "")
    if len(mantissa.lstrip("0")) > 16:
        raise ValueError(
            f"Too many significant digits for {message_type} keyword {key}"
        )
    if not math.isfinite(float(value)):
        raise ValueError(f"Non-finite numeric value for {message_type} keyword {key}")
    return value, compatibility_value


def validate_odm_datetime(value: str, key: str, message_type: str) -> None:
    """Validate calendar or ordinal CCSDS time syntax and date/time ranges."""
    match = CCSDS_DATETIME_VALUE_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid {message_type} time value for {key}: {value}")
    normalized = value.removesuffix("Z").split(".")[0]
    if match.group("second") == "60":
        normalized = normalized[:-2] + "59"
    date_format = "%Y-%m-%dT%H:%M:%S" if match.group("month") else "%Y-%jT%H:%M:%S"
    try:
        parsed = datetime.strptime(normalized, date_format)
        if parsed.year != int(match.group("year")):
            raise ValueError("Ordinal date is outside the given year")
    except ValueError as exc:
        raise ValueError(
            f"Invalid {message_type} time value for {key}: {value}"
        ) from exc
