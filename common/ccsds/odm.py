"""CCSDS Orbit Data Message (ODM)."""

from __future__ import annotations

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
