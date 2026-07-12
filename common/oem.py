"""Read, parse, and write CCSDS Orbit Ephemeris Message (OEM) files.

Provides a structured :class:`CcsdsOem` class as the primary interface, plus
low-level functions (:func:`read_oem`, :func:`write_oem`) retained for
backward compatibility.

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
>>> oem = CcsdsOem.read("orbit.oem")
>>> epoch, state = oem.states[0]  # First state (already sorted by time)
>>> state  # Returns state in meters and m/s
array([6.7e6, 0.0, 0.0, 0.0, 7.5e3, 0.0])  # Position in m, velocity in m/s
>>> oem.write("output.oem")  # Write to file
"""

from __future__ import annotations

import bisect
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
) -> tuple[dict, dict, list[tuple[float, np.ndarray]]]:
    """Read an OEM file or raw state list and return *(header, meta, states)*.

    OEM files use km and km/s (CCSDS standard), but state vectors are converted
    to SI units (m and m/s) for internal use.

    For raw state list files (without OEM headers), header and meta will be empty dicts.

    Parameters
    ----------
    source : TextIO | str | Path
        A readable text stream, file path string, or Path object.

    Returns
    -------
    tuple[dict, dict, list[tuple[float, np.ndarray]]]
        A 3-tuple of ``(header, meta, states)`` where:
        - *header* is a dictionary of header fields, or empty dict for raw state lists
        - *meta* is a dictionary of metadata fields, or empty dict for raw state lists
        - *states* is a list of (POSIX timestamp, state_vector) tuples,
          sorted by POSIX timestamp (float, seconds since epoch) in ascending order.
          State vectors are in meters (m) and m/s.
    """
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return _read_oem_impl(fh)
    return _read_oem_impl(source)


def _read_oem_impl(
    source: TextIO,
) -> tuple[dict, dict, list[tuple[float, np.ndarray]]]:
    """Internal implementation of OEM reading (no deprecation warning)."""
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return _read_oem_impl(fh)

    header: dict = {}
    meta: dict = {}
    states: list[tuple[float, np.ndarray]] = []
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
            states.append((timestamp, state_km * KILOMETERS_TO_METERS))

    # Return empty dicts for header/meta if none found (raw state list)
    return header, meta, states


def find_state_by_timestamp(
    states: list[tuple[float, np.ndarray]],
    timestamp: float,
    tolerance: float = 0.0,
) -> tuple[float, np.ndarray] | None:
    """Find a state by timestamp using binary search.

    Uses binary search (O(log n)) to efficiently find a state with the given
    timestamp in a sorted list of states.

    Parameters
    ----------
    states : list[tuple[float, np.ndarray]]
        Sorted list of (POSIX timestamp, state_vector) tuples.
    timestamp : float
        POSIX timestamp to search for (seconds since epoch).
    tolerance : float, optional
        Maximum allowed difference between requested and found timestamp.
        If 0.0 (default), requires exact match. If > 0.0, returns the closest
        state within tolerance.

    Returns
    -------
    tuple[float, np.ndarray] | None
        The (timestamp, state_vector) tuple if found within tolerance,
        or None if not found.

    Examples
    --------
    >>> states = [(1000.0, np.array([1, 2, 3, 4, 5, 6])),
    ...           (2000.0, np.array([7, 8, 9, 10, 11, 12]))]
    >>> find_state_by_timestamp(states, 2000.0)
    (2000.0, array([7, 8, 9, 10, 11, 12]))
    >>> find_state_by_timestamp(states, 1500.0, tolerance=600.0)
    (2000.0, array([7, 8, 9, 10, 11, 12]))
    >>> find_state_by_timestamp(states, 3000.0) is None
    True
    """
    if not states:
        return None

    # Extract timestamps for binary search
    timestamps = [t for t, _ in states]

    if tolerance == 0.0:
        # Exact match required
        idx = bisect.bisect_left(timestamps, timestamp)
        if idx < len(states) and timestamps[idx] == timestamp:
            return states[idx]
        return None
    else:
        # Find closest within tolerance
        idx = bisect.bisect_left(timestamps, timestamp)

        # Check candidates: element at idx and idx-1
        candidates = []
        if idx < len(states):
            candidates.append((idx, abs(timestamps[idx] - timestamp)))
        if idx > 0:
            candidates.append((idx - 1, abs(timestamps[idx - 1] - timestamp)))

        if not candidates:
            return None

        # Find closest candidate
        best_idx, best_diff = min(candidates, key=lambda x: x[1])

        if best_diff <= tolerance:
            return states[best_idx]
        return None


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
        states: list[tuple[float, np.ndarray]],
    ) -> None:
        """Initialise a :class:`CcsdsOem` from pre-parsed components.

        Parameters
        ----------
        header : OemHeader
            File-level header fields.
        meta : OemMeta
            Metadata block fields.
        states : list[tuple[float, np.ndarray]]
            List of (POSIX timestamp, state_vector) tuples, sorted by POSIX timestamp
            (float, seconds since epoch) in ascending order. State vectors are 6-element
            arrays in meters (m) and m/s.
        """
        self.header = header
        """File-level header fields."""

        self.meta = meta
        """Metadata block fields."""

        self.states = states
        """List of (POSIX timestamp, state_vector) tuples, sorted by POSIX timestamp (float, seconds since epoch) in ascending order. State vectors are 6-element arrays [x, y, z, vx, vy, vz] in meters (m) and m/s."""

    @classmethod
    def read(cls, source: TextIO | str | Path) -> CcsdsOem:
        """Read and construct a :class:`CcsdsOem` from a file or stream.

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
        raw_states_float: list[tuple[float, np.ndarray]]
        # Call internal implementation directly to avoid triggering the
        # deprecation warning on read_oem().
        if isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8") as fh:
                raw_header, raw_meta, raw_states_float = _read_oem_impl(fh)
        else:
            raw_header, raw_meta, raw_states_float = _read_oem_impl(source)

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

    @classmethod
    def from_states(
        cls,
        states: list[tuple[float, np.ndarray]],
        object_name: str = "",
        ref_frame: str = "",
        center_name: str = "",
        time_system: str = "UTC",
    ) -> CcsdsOem:
        """Create a CcsdsOem from a list of states with minimal metadata.

        Useful for creating OEM objects from propagated states or other
        programmatically generated state vectors.

        Parameters
        ----------
        states : list[tuple[float, np.ndarray]]
            List of (POSIX timestamp, state_vector) tuples in meters (m) and m/s.
        object_name : str, optional
            Satellite or object name.
        ref_frame : str, optional
            Reference frame (e.g., GCRF, J2000).
        center_name : str, optional
            Central body name (e.g., EARTH).
        time_system : str, optional
            Time system (default: UTC).

        Returns
        -------
        CcsdsOem
            New CcsdsOem instance with minimal metadata.

        Examples
        --------
        >>> states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]
        >>> oem = CcsdsOem.from_states(states, object_name="TEST_SAT", ref_frame="GCRF")
        >>> oem.write("output.oem")
        """
        # Sort states by timestamp
        sorted_states = sorted(states, key=lambda x: x[0])

        # Create minimal header
        header = OemHeader(
            version=2.0,
            creation_date=datetime.now(timezone.utc).isoformat(),
            originator="tudatpy-utils",
        )

        # Create metadata with provided values
        meta = OemMeta(
            object_name=object_name,
            ref_frame=ref_frame,
            center_name=center_name,
            time_system=time_system,
        )

        # Set start/stop times from states
        if sorted_states:
            start_dt = datetime.fromtimestamp(sorted_states[0][0], tz=timezone.utc)
            stop_dt = datetime.fromtimestamp(sorted_states[-1][0], tz=timezone.utc)
            meta.start_time = start_dt.isoformat()
            meta.stop_time = stop_dt.isoformat()

        return cls(header=header, meta=meta, states=sorted_states)

    @classmethod
    def parse_state_line(cls, line: str) -> tuple[float, np.ndarray] | None:
        """Parse a single line of OEM-style state data.

        Wrapper around module-level :func:`parse_oem_state_line` for convenience.

        Parameters
        ----------
        line : str
            A single line of OEM-style data to parse.

        Returns
        -------
        tuple[float, np.ndarray] | None
            ``(timestamp, state_vector)`` or ``None`` for blank/comment lines.
            State vector is in meters (m) and m/s.

        Examples
        --------
        >>> line = "2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0"
        >>> timestamp, state = CcsdsOem.parse_state_line(line)
        >>> state  # In meters and m/s
        array([7000000., 0., 0., 0., 7500., 0.])
        """
        return parse_oem_state_line(line)

    @property
    def epochs(self) -> list[float]:
        """Sorted list of epoch POSIX timestamps."""
        return [epoch for epoch, _ in self.states]

    @property
    def state_vectors(self) -> np.ndarray:
        """State vectors ordered by epoch, shape ``(N, 6)`` in meters (m) and m/s."""
        return np.array([state for _, state in self.states])

    def write(self, dest: TextIO | str | Path) -> None:
        """Write this OEM to a file or stream.

        Parameters
        ----------
        dest : TextIO | str | Path
            A writable text stream, file path string, or :class:`Path`.
        """
        header_dict: dict = {
            "CCSDS_OEM_VERS": self.header.version,
            "CREATION_DATE": self.header.creation_date,
            "ORIGINATOR": self.header.originator,
        }
        if self.header.comments:
            header_dict["COMMENT"] = self.header.comments

        meta_dict: dict = {}
        if self.meta.comments:
            meta_dict["COMMENT"] = self.meta.comments
        for key in _META_KEY_ORDER:
            attr: str = key.lower()
            value: str | int | None = getattr(self.meta, attr, None)
            if value is not None and value != "" and value != 0:
                meta_dict[key] = value

        write_oem(dest, header_dict, meta_dict, self.states)

    def update_metadata(self, **kwargs) -> None:
        """Update metadata fields in-place.

        Parameters
        ----------
        **kwargs
            Metadata fields to update (e.g., object_name="ISS", ref_frame="GCRF").

        Raises
        ------
        ValueError
            If an unknown metadata field is specified.

        Examples
        --------
        >>> oem = CcsdsOem.read("orbit.oem")
        >>> oem.update_metadata(object_name="NEW_NAME", ref_frame="J2000")
        >>> oem.meta.object_name
        'NEW_NAME'
        """
        for key, value in kwargs.items():
            if hasattr(self.meta, key):
                setattr(self.meta, key, value)
            else:
                raise ValueError(f"Unknown metadata field: {key}")

    def with_metadata(self, **kwargs) -> CcsdsOem:
        """Return a new CcsdsOem with updated metadata.

        Creates a deep copy of this OEM with modified metadata fields.
        The original OEM instance is not modified.

        Parameters
        ----------
        **kwargs
            Metadata fields to update (e.g., object_name="ISS", ref_frame="GCRF").

        Returns
        -------
        CcsdsOem
            New instance with updated metadata.

        Raises
        ------
        ValueError
            If an unknown metadata field is specified.

        Examples
        --------
        >>> oem = CcsdsOem.read("orbit.oem")
        >>> new_oem = oem.with_metadata(object_name="RENAMED", ref_frame="J2000")
        >>> new_oem.meta.object_name
        'RENAMED'
        >>> oem.meta.object_name  # Original unchanged
        'ISS'
        """
        import copy

        new_oem = copy.deepcopy(self)
        new_oem.update_metadata(**kwargs)
        return new_oem

    def __len__(self) -> int:
        """Return the number of state vectors stored in this OEM."""
        return len(self.states)

    def find_state_by_timestamp(
        self,
        timestamp: float,
        tolerance: float = 0.0,
    ) -> tuple[float, np.ndarray] | None:
        """Find a state by timestamp using binary search.

        Wrapper around the module-level :func:`find_state_by_timestamp` function
        that operates on this OEM's states.

        Parameters
        ----------
        timestamp : float
            POSIX timestamp to search for (seconds since epoch).
        tolerance : float, optional
            Maximum allowed difference between requested and found timestamp.
            If 0.0 (default), requires exact match. If > 0.0, returns the closest
            state within tolerance.

        Returns
        -------
        tuple[float, np.ndarray] | None
            The (timestamp, state_vector) tuple if found within tolerance,
            or None if not found. State vector is in meters (m) and m/s.

        Examples
        --------
        >>> oem = CcsdsOem.read("orbit.oem")
        >>> state = oem.find_state_by_timestamp(1234567890.0)
        >>> if state:
        ...     timestamp, state_vector = state
        ...     print(f"Found state at {timestamp}")
        """
        return find_state_by_timestamp(self.states, timestamp, tolerance)

    def __repr__(self) -> str:
        """Return a concise string representation of this OEM instance."""
        return (
            f"CcsdsOem(object={self.meta.object_name!r}, "
            f"frame={self.meta.ref_frame!r}, "
            f"epochs={len(self.states)})"
        )
