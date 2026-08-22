"""CCSDS Orbit Data Message (ODM)."""

from __future__ import annotations

import re

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


REF_FRAMES = REF_FRAME_VALUES
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


TIME_SYSTEMS = TIME_SYSTEM_VALUES
"""Alias for :data:`TIME_SYSTEM_VALUES`."""


CCSDS_TIMECODE_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:\s*)?(?P<yr>\d{4})-(?P<mo>\d{1,2})-(?P<dy>\d{1,2})T(?P<hr>\d{1,2}):(?P<mn>\d{1,2}):(?P<sc>\d{0,2}(?:\.\d*)?)(?:\s*)?$"
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
    r"^(?:\s*)(?P<value>(?:[-+]?)(?:[0-9]+)(?:\.\d*)?(?:[eE][+-]?(?:\d+))?)(?:(?:\s*)(?:\[(?P<unit>[0-9A-Za-z/_*]*)\]?))?(?:\s*)?$"
)
"""Regex for numeric value with optional CCSDS units."""


CCSDS_3VALUE_NUMERICAL_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:\s*)(?P<value1>(?:[-+]?)(?:[0-9]*)(?:\.\d*)?(?:[eE][+-]?\d+)?)(?:\s+)(?P<value2>(?:[-+]?)(?:[0-9]*)(?:\.\d*)?(?:[eE][+-]?\d+)?)(?:\s+)(?P<value3>(?:[-+]?)(?:[0-9]*)(?:\.\d*)?(?:[eE][+-]?\d+)?)(?:\s*)$"
)
"""Regex for multipartite CCSDS numerical values in a 3-value sequence."""
