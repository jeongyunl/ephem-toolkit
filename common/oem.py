"""Read, parse, and write CCSDS Orbit Ephemeris Message (OEM) files.

Provides low-level functions (:func:`read_oem`, :func:`write_oem`) that
operate on plain dictionaries, and a structured :class:`CcsdsOem` class.

Unit Conversion
---------------
OEM files use kilometers (km) and km/s per the CCSDS standard. This module
converts state vectors to SI units (meters and m/s) when reading, and converts
back to km/km·s⁻¹ when writing. This ensures:

- **Internal consistency:** All state vectors use SI units (m, m/s)
- **File compliance:** OEM files remain CCSDS-compliant (km, km/s)
- **Project alignment:** Follows the project-wide SI unit convention

Example
-------
>>> oem = CcsdsOem.from_source("orbit.oem")
>>> oem.states[timestamp]  # Returns state in meters and m/s
array([6.7e6, 0.0, 0.0, 0.0, 7.5e3, 0.0])  # Position in m, velocity in m/s
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TextIO

import numpy as np

import common.common as common
import common.time_utils as time_utils

# ===================================================================
# Constants
# ===================================================================


KILOMETERS_TO_METERS: float = 1000.0
"""Conversion factor from kilometers to meters."""


# ===================================================================
# Internal helpers
# ===================================================================


def _is_state_line(line: str) -> bool:
    """Heuristic: a state line starts with a date-like token."""
    token: str = line.split()[0] if line.split() else ""
    return len(token) >= 10 and token[4:5] == "-"


_META_KEY_ORDER: list[str] = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "TIME_SYSTEM",
    "START_TIME",
    "USEABLE_START_TIME",
    "USEABLE_STOP_TIME",
    "STOP_TIME",
    "INTERPOLATION",
    "INTERPOLATION_DEGREE",
]
"""Preferred ordering of metadata keys when writing OEM files."""


# ===================================================================
# Low-level reader (dict-based)
# ===================================================================


def parse_oem_state_line(line: str) -> tuple[float, np.ndarray] | None:
    """Parse a single line of OEM-style data.

    Accepts whitespace or comma separated values.

    OEM files use km and km/s (CCSDS standard), but this function converts
    to SI units (m and m/s) for internal use.

    Parameters
    ----------
    line : str
        A single line of OEM-style data to parse.

    Returns
    -------
    tuple[float, np.ndarray] | None
        ``(timestamp, state_m)`` where *timestamp* is a POSIX timestamp (float, seconds since epoch)
        and *state_m* is a 6-element numpy array ``[x, y, z, vx, vy, vz]`` in meters (m) and m/s,
        or ``None`` for blank / comment lines.
    """
    if not line.strip():
        return None
    if line.strip().startswith("#"):
        return None

    parts: list[str] = [p for tok in line.strip().split() for p in tok.split(",")]
    if len(parts) < 7:
        raise ValueError(f"Line does not contain 7 fields: '{line}'")

    epoch_str: str = parts[0]
    epoch_dt: datetime = time_utils.iso8601_to_datetime(epoch_str)
    timestamp: float = epoch_dt.timestamp()

    vals: list[float] = [float(x) for x in parts[1:7]]
    state_km: np.ndarray = np.array(vals)

    # Convert from km/km·s⁻¹ (OEM standard) to m/m·s⁻¹ (SI units)
    state_m: np.ndarray = state_km * KILOMETERS_TO_METERS

    return timestamp, state_m


def read_oem(
    source: TextIO | str | Path,
) -> tuple[dict, dict, dict[float, np.ndarray]]:
    """Read an OEM file and return *(header, meta, states)*.

    OEM files use km and km/s (CCSDS standard), but state vectors are converted
    to SI units (m and m/s) for internal use.

    Parameters
    ----------
    source : TextIO | str | Path
        A readable text stream, file path string, or Path object.

    Returns
    -------
    tuple[dict, dict, dict[float, np.ndarray]]
        A 3-tuple of ``(header, meta, states)`` where *header* and *meta*
        are dictionaries, and *states* maps epoch POSIX timestamps (float, seconds since epoch)
        to state vectors in meters (m) and m/s.
    """
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return read_oem(fh)

    header: dict = {}
    meta: dict = {}
    states: dict[float, np.ndarray] = {}
    in_meta: bool = False

    for raw_line in source:
        line: str = raw_line.strip()
        if not line:
            continue

        if line == "META_START":
            in_meta = True
            continue
        if line == "META_STOP":
            in_meta = False
            continue

        if line.startswith("COMMENT"):
            comment_text: str = line[len("COMMENT") :].strip()
            target: dict = meta if in_meta else header
            target.setdefault("COMMENT", [])
            target["COMMENT"].append(comment_text)
            continue

        kv: tuple[str, str] | None = common.parse_key_value_line(line)
        if kv is not None and (in_meta or not _is_state_line(line)):
            key, value = kv
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            if in_meta:
                meta[key] = value
            else:
                header[key] = value
            continue

        if _is_state_line(line):
            parts: list[str] = line.split()
            if len(parts) < 7:
                continue
            epoch: datetime = time_utils.iso8601_to_datetime(parts[0])
            timestamp: float = epoch.timestamp()
            state_km: np.ndarray = np.array([float(v) for v in parts[1:7]])
            # Convert from km/km·s⁻¹ (OEM standard) to m/m·s⁻¹ (SI units)
            states[timestamp] = state_km * KILOMETERS_TO_METERS

    return header, meta, states


# ===================================================================
# Low-level writer
# ===================================================================


def write_state(
    dest: TextIO,
    epoch: datetime,
    state_vector: np.ndarray,
) -> None:
    """Write a single state vector to a file handle.

    Converts from internal SI units (m, m/s) to OEM standard units (km, km/s).

    Parameters
    ----------
    dest : TextIO
        Writable text stream.
    epoch : datetime
        Epoch datetime object.
    state_vector : np.ndarray
        State vector (6-element array) [x, y, z, vx, vy, vz] in meters (m) and m/s.
    """
    dt: datetime = epoch
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch_str: str = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

    # Convert from m/m·s⁻¹ (SI units) to km/km·s⁻¹ (OEM standard)
    state_km: np.ndarray = state_vector / KILOMETERS_TO_METERS

    vals: str = " ".join(f"{v:.15g}" for v in state_km)
    dest.write(f"{epoch_str} {vals}\n")


def write_states(
    dest: TextIO,
    states: (
        dict[datetime, np.ndarray]
        | dict[float, np.ndarray]
        | list[tuple[datetime, np.ndarray]]
        | list[tuple[float, np.ndarray]]
    ),
) -> None:
    """Write state vectors to a file handle.

    Converts from internal SI units (m, m/s) to OEM standard units (km, km/s).

    Parameters
    ----------
    dest : TextIO
        Writable text stream.
    states : dict[datetime, np.ndarray] | dict[float, np.ndarray] | list[tuple[datetime, np.ndarray]] | list[tuple[float, np.ndarray]]
        Dictionary mapping epoch datetimes or POSIX timestamps to state vectors
        in meters (m) and m/s, or a sorted list of (epoch, state_vector) tuples.
    """
    if isinstance(states, dict):
        items: list[tuple[datetime | float, np.ndarray]] = sorted(states.items())
    else:
        items: list[tuple[datetime | float, np.ndarray]] = states

    for epoch, state_vector in items:
        # Convert float timestamp to datetime if needed
        if isinstance(epoch, float):
            epoch = datetime.fromtimestamp(epoch, tz=timezone.utc)
        write_state(dest, epoch, state_vector)


def write_oem(
    dest: TextIO | str | Path,
    header: dict,
    meta: dict,
    states: dict[datetime, np.ndarray] | dict[float, np.ndarray],
) -> None:
    """Write an OEM file from *(header, meta, states)* dicts.

    Converts state vectors from internal SI units (m, m/s) to OEM standard
    units (km, km/s) when writing.

    Parameters
    ----------
    dest : TextIO | str | Path
        A writable text stream, file path string, or Path object.
    header : dict
        Dictionary containing OEM header fields.
    meta : dict
        Dictionary containing OEM metadata fields.
    states : dict[datetime, np.ndarray] | dict[float, np.ndarray]
        Dictionary mapping epoch datetimes or POSIX timestamps to state vectors
        in meters (m) and m/s.
    """
    if isinstance(dest, (str, Path)):
        with open(dest, "w", encoding="utf-8") as fh:
            return write_oem(fh, header, meta, states)

    w: Callable[[str], int] = dest.write

    version: float | int = header.get("CCSDS_OEM_VERS", 2.0)
    w(f"CCSDS_OEM_VERS = {version}\n")
    w("\n")

    for comment in header.get("COMMENT", []):
        w(f"COMMENT {comment}\n")
    if header.get("COMMENT"):
        w("\n")

    if "CREATION_DATE" in header:
        w(f"CREATION_DATE  = {header['CREATION_DATE']}\n")
    if "ORIGINATOR" in header:
        w(f"ORIGINATOR     = {header['ORIGINATOR']}\n")
    w("\n")

    w("META_START\n")
    for comment in meta.get("COMMENT", []):
        w(f"COMMENT {comment}\n")

    meta_keys: list[str] = [k for k in _META_KEY_ORDER if k in meta]
    extra_keys: list[str] = [
        k for k in meta if k not in _META_KEY_ORDER and k != "COMMENT"
    ]
    all_keys: list[str] = meta_keys + extra_keys
    pad: int = max((len(k) for k in all_keys), default=0)

    for key in all_keys:
        w(f"{key:<{pad}} = {meta[key]}\n")

    w("META_STOP\n")
    w("\n")

    write_states(dest, states)


# ===================================================================
# Structured classes
# ===================================================================


@dataclass
class OemHeader:
    """File-level header fields for a CCSDS OEM message."""

    version: float = 0.0
    """CCSDS OEM format version number."""

    comments: list[str] = field(default_factory=list)
    """List of comment lines from the OEM header."""

    creation_date: str = ""
    """File creation date (ISO 8601 format)."""

    originator: str = ""
    """Organization or entity that created the OEM file."""


@dataclass
class OemMeta:
    """Metadata block fields for a CCSDS OEM segment."""

    object_name: str = ""
    """Satellite or object name."""

    object_id: str = ""
    """International designator or NORAD catalog number."""

    center_name: str = ""
    """Central body name (e.g., EARTH, MOON)."""

    ref_frame: str = ""
    """Reference frame (e.g., GCRF, J2000, ITRF)."""

    time_system: str = ""
    """Time system (e.g., UTC, GPS, TAI)."""

    start_time: str = ""
    """Start time of the ephemeris data (ISO 8601 format)."""

    stop_time: str = ""
    """Stop time of the ephemeris data (ISO 8601 format)."""

    useable_start_time: str = ""
    """Recommended start time for using the ephemeris (ISO 8601 format)."""

    useable_stop_time: str = ""
    """Recommended stop time for using the ephemeris (ISO 8601 format)."""

    interpolation: str = ""
    """Interpolation method (e.g., HERMITE, LAGRANGE, LINEAR)."""

    interpolation_degree: int = 0
    """Degree of interpolation polynomial."""

    comments: list[str] = field(default_factory=list)
    """List of comment lines from the metadata block."""


class CcsdsOem:
    """Structured CCSDS Orbit Ephemeris Message with header, metadata, and states."""

    def __init__(
        self,
        header: OemHeader,
        meta: OemMeta,
        states: dict[float, np.ndarray],
    ) -> None:
        """Initialise a :class:`CcsdsOem` from pre-parsed components.

        Parameters
        ----------
        header : OemHeader
            File-level header fields.
        meta : OemMeta
            Metadata block fields.
        states : dict[float, np.ndarray]
            Mapping of epoch POSIX timestamps (float, seconds since epoch) to 6-element state vectors
            in meters (m) and m/s.
        """
        self.header = header
        """File-level header fields."""

        self.meta = meta
        """Metadata block fields."""

        self.states = states
        """Mapping of epoch POSIX timestamps (float, seconds since epoch) to 6-element state vectors [x, y, z, vx, vy, vz] in meters (m) and m/s."""

    @classmethod
    def from_source(cls, source: TextIO | str | Path) -> CcsdsOem:
        """Construct a :class:`CcsdsOem` from a file or stream.

        Parameters
        ----------
        source : TextIO | str | Path
            A readable text stream, file path string, or :class:`Path`.

        Returns
        -------
        CcsdsOem
            Parsed OEM instance.
        """
        raw_header: dict
        raw_meta: dict
        raw_states_float: dict[float, np.ndarray]
        raw_header, raw_meta, raw_states_float = read_oem(source)

        header: OemHeader = OemHeader(
            version=float(raw_header.get("CCSDS_OEM_VERS", 0.0)),
            comments=raw_header.get("COMMENT", []),
            creation_date=str(raw_header.get("CREATION_DATE", "")),
            originator=str(raw_header.get("ORIGINATOR", "")),
        )

        meta: OemMeta = OemMeta(
            object_name=str(raw_meta.get("OBJECT_NAME", "")),
            object_id=str(raw_meta.get("OBJECT_ID", "")),
            center_name=str(raw_meta.get("CENTER_NAME", "")),
            ref_frame=str(raw_meta.get("REF_FRAME", "")),
            time_system=str(raw_meta.get("TIME_SYSTEM", "")),
            start_time=str(raw_meta.get("START_TIME", "")),
            stop_time=str(raw_meta.get("STOP_TIME", "")),
            useable_start_time=str(raw_meta.get("USEABLE_START_TIME", "")),
            useable_stop_time=str(raw_meta.get("USEABLE_STOP_TIME", "")),
            interpolation=str(raw_meta.get("INTERPOLATION", "")),
            interpolation_degree=int(raw_meta.get("INTERPOLATION_DEGREE", 0)),
            comments=raw_meta.get("COMMENT", []),
        )

        return cls(header=header, meta=meta, states=raw_states_float)

    @property
    def epochs(self) -> list[float]:
        """Sorted list of epoch POSIX timestamps."""
        return sorted(self.states.keys())

    @property
    def state_vectors(self) -> np.ndarray:
        """State vectors ordered by epoch, shape ``(N, 6)`` in meters (m) and m/s."""
        return np.array([self.states[epoch] for epoch in self.epochs])

    def to_file(self, dest: TextIO | str | Path) -> None:
        """Write this OEM to a file or stream.

        Parameters
        ----------
        dest : TextIO | str | Path
            A writable text stream, file path string, or :class:`Path`.
        """
        hdr: dict = {
            "CCSDS_OEM_VERS": self.header.version,
            "CREATION_DATE": self.header.creation_date,
            "ORIGINATOR": self.header.originator,
        }
        if self.header.comments:
            hdr["COMMENT"] = self.header.comments

        mt: dict = {}
        if self.meta.comments:
            mt["COMMENT"] = self.meta.comments
        for key in _META_KEY_ORDER:
            attr: str = key.lower()
            val: str | int | None = getattr(self.meta, attr, None)
            if val is not None and val != "" and val != 0:
                mt[key] = val

        write_oem(dest, hdr, mt, self.states)

    def __len__(self) -> int:
        """Return the number of state vectors stored in this OEM."""
        return len(self.states)

    def __repr__(self) -> str:
        """Return a concise string representation of this OEM instance."""
        return (
            f"CcsdsOem(object={self.meta.object_name!r}, "
            f"frame={self.meta.ref_frame!r}, "
            f"epochs={len(self.states)})"
        )
