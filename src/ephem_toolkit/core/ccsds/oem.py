"""Read, parse, and write CCSDS Orbit Ephemeris Message (OEM) files.

Provides a structured :class:`CcsdsOem` class as the primary interface, plus
low-level parsing helpers.

Unit Conversion
---------------
OEM files use kilometers (km) and km/s per the CCSDS standard. This module
converts state vectors to SI units (meters and m/s) when reading, and converts
back to km/km·s⁻¹ when writing. This ensures:

- **Internal consistency:** All state vectors use SI units (m, m/s)
- **File compliance:** OEM files remain CCSDS-compliant (km, km/s)
- **Project alignment:** Follows the project-wide SI unit convention

Examples
--------
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
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

import numpy as np

from .. import misc
from .. import time_utils

# ===================================================================
# Constants
# ===================================================================


KILOMETERS_TO_METERS: float = 1000.0
"""Conversion factor from kilometers to meters."""


# ===================================================================
# Internal helpers
# ===================================================================


_META_KEY_ORDER: list[str] = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "REF_FRAME_EPOCH",
    "TIME_SYSTEM",
    "START_TIME",
    "USEABLE_START_TIME",
    "USEABLE_STOP_TIME",
    "STOP_TIME",
    "INTERPOLATION",
    "INTERPOLATION_DEGREE",
]
"""Preferred ordering of metadata keys when writing OEM files."""


_HEADER_KEY_ORDER: list[str] = [
    "CCSDS_OEM_VERS",
    "CREATION_DATE",
    "ORIGINATOR",
    "CLASSIFICATION",
    "MESSAGE_ID",
]
"""Preferred ordering of header keys when writing OEM files."""


_CSV_STATE_HEADERS: list[str] = [
    "epoch",
    "x_km",
    "y_km",
    "z_km",
    "vx_km_s",
    "vy_km_s",
    "vz_km_s",
]
"""Column names for CSV state output."""


class OemFormat(Enum):
    """Supported output formats for CCSDS OEM data."""

    OEM = "OEM"
    CSV = "CSV"


# ===================================================================
# Structured classes
# ===================================================================


@dataclass
class OemHeader:
    """File-level header fields for a CCSDS OEM message."""

    version: float = 0.0
    """CCSDS OEM format version number."""

    comments: list[str] = field(default_factory=list)
    """Comment lines from the header section (after CCSDS_OEM_VERS, before META_START)."""

    creation_date: str = ""
    """File creation date (ISO 8601 format)."""

    originator: str = ""
    """Organization or entity that created the OEM file."""

    classification: str = ""
    """Security classification of the OEM message."""

    message_id: str = ""
    """Identifier for the OEM message."""


@dataclass
class OemMeta:
    """Metadata block fields for a CCSDS OEM segment."""

    comments: list[str] = field(default_factory=list)
    """Comment lines from the metadata block."""

    object_name: str = ""
    """Satellite or object name."""

    object_id: str = ""
    """International designator or NORAD catalog number."""

    center_name: str = ""
    """Central body name (e.g., EARTH, MOON)."""

    ref_frame: str = ""
    """Reference frame (e.g., GCRF, J2000, ITRF)."""

    ref_frame_epoch: str = ""
    """Epoch of the reference frame, when required by its definition."""

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


class CcsdsOem:
    """Structured CCSDS Orbit Ephemeris Message with header, metadata, and states."""

    @classmethod
    def write_line(cls, dest: TextIO, *parts: str, sep: str = " ") -> None:
        """Concatenate string parts and write them to a text stream."""
        dest.write(sep.join(parts) + "\n")

    @classmethod
    def parse_oem_state_line(cls, line: str) -> tuple[float, np.ndarray] | None:
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
            ``(tt_s, state_m)`` where *tt_s* is TT seconds since J2000 (float)
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
        timestamp: float = time_utils.datetime_to_tt_s(epoch_dt)

        values: list[float] = [float(value) for value in parts[1:7]]
        state_km: np.ndarray = np.array(values)

        # Convert from km/km·s⁻¹ (OEM standard) to m/m·s⁻¹ (SI units)
        state_m: np.ndarray = state_km * KILOMETERS_TO_METERS

        return timestamp, state_m

    def __init__(
        self,
        header: OemHeader,
        meta: OemMeta,
        data_comments: list[str],
        states: list[tuple[float, np.ndarray]],
    ) -> None:
        """Initialise a :class:`CcsdsOem` from pre-parsed components.

        Parameters
        ----------
        header : OemHeader
            File-level header fields.
        meta : OemMeta
            Metadata block fields.
        data_comments : list[str]
            Comment lines from the ephemeris data section.
        states : list[tuple[float, np.ndarray]]
            List of (TT seconds since J2000, state_vector) tuples, sorted in
            ascending order. State vectors are 6-element arrays in meters (m)
            and m/s.
        """
        self.header = header
        """File-level header fields."""

        self.meta = meta
        """Metadata block fields."""

        self.states = states
        """List of (TT seconds since J2000, state_vector) tuples, sorted in ascending order. State vectors are 6-element arrays [x, y, z, vx, vy, vz] in meters (m) and m/s."""

        self.data_comments = data_comments
        """Comment lines from the ephemeris data section (after META_STOP, before state data)."""

    @staticmethod
    def _is_state_line(line: str) -> bool:
        """Return whether a line starts with a date-like state token."""
        token: str = line.split()[0] if line.split() else ""
        return len(token) >= 10 and token[4:5] == "-"

    @staticmethod
    def _read_oem_impl(
        source: TextIO | str | Path,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        list[str],
        list[tuple[float, np.ndarray]],
    ]:
        """Read OEM content into header, metadata, data comments, and states."""
        if isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8") as file_handle:
                return CcsdsOem._read_oem_impl(file_handle)

        header: dict[str, Any] = {}
        meta: dict[str, Any] = {}
        data_comments: list[str] = []
        states: list[tuple[float, np.ndarray]] = []
        in_meta: bool = False
        past_meta: bool = False

        for raw_line in source:
            line: str = raw_line.strip()
            if not line:
                continue

            if line == "META_START":
                in_meta = True
                continue
            if line == "META_STOP":
                in_meta = False
                past_meta = True
                continue

            if line.startswith("COMMENT"):
                comment_text: str = line[len("COMMENT") :].strip()
                if in_meta:
                    meta.setdefault("COMMENT", [])
                    meta["COMMENT"].append(comment_text)
                elif past_meta:
                    data_comments.append(comment_text)
                else:
                    header.setdefault("COMMENT", [])
                    header["COMMENT"].append(comment_text)
                continue

            key_value: tuple[str, str] | None = misc.parse_key_value_line(line)
            if key_value is not None and (in_meta or not CcsdsOem._is_state_line(line)):
                key, value = key_value
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

            if CcsdsOem._is_state_line(line):
                state_fields: list[str] = line.split()
                if len(state_fields) < 7:
                    continue
                epoch: datetime = time_utils.iso8601_to_datetime(state_fields[0])
                timestamp: float = time_utils.datetime_to_tt_s(epoch)
                state_km: np.ndarray = np.array(
                    [float(value) for value in state_fields[1:7]]
                )
                states.append((timestamp, state_km * KILOMETERS_TO_METERS))

        return header, meta, data_comments, states

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
        raw_header: dict[str, Any]
        raw_meta: dict[str, Any]
        raw_data_comments: list[str]
        raw_states: list[tuple[float, np.ndarray]]
        raw_header, raw_meta, raw_data_comments, raw_states = cls._read_oem_impl(source)

        header: OemHeader = OemHeader(
            version=float(raw_header.get("CCSDS_OEM_VERS", 0.0)),
            comments=raw_header.get("COMMENT", []),
            creation_date=str(raw_header.get("CREATION_DATE", "")),
            originator=str(raw_header.get("ORIGINATOR", "")),
            classification=str(raw_header.get("CLASSIFICATION", "")),
            message_id=str(raw_header.get("MESSAGE_ID", "")),
        )

        meta: OemMeta = OemMeta(
            object_name=str(raw_meta.get("OBJECT_NAME", "")),
            object_id=str(raw_meta.get("OBJECT_ID", "")),
            center_name=str(raw_meta.get("CENTER_NAME", "")),
            ref_frame=str(raw_meta.get("REF_FRAME", "")),
            ref_frame_epoch=str(raw_meta.get("REF_FRAME_EPOCH", "")),
            time_system=str(raw_meta.get("TIME_SYSTEM", "")),
            start_time=str(raw_meta.get("START_TIME", "")),
            stop_time=str(raw_meta.get("STOP_TIME", "")),
            useable_start_time=str(raw_meta.get("USEABLE_START_TIME", "")),
            useable_stop_time=str(raw_meta.get("USEABLE_STOP_TIME", "")),
            interpolation=str(raw_meta.get("INTERPOLATION", "")),
            interpolation_degree=int(raw_meta.get("INTERPOLATION_DEGREE", 0)),
            comments=raw_meta.get("COMMENT", []),
        )

        return cls(
            header=header,
            meta=meta,
            data_comments=raw_data_comments,
            states=raw_states,
        )

    @classmethod
    def from_states(
        cls,
        states: list[tuple[float, np.ndarray]],
        object_name: str = "",
        object_id: str = "",
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
            List of (TT seconds since J2000, state_vector) tuples in meters (m) and m/s.
        object_name : str, optional
            Satellite or object name.
        object_id : str, optional
            International designator or NORAD catalog number.
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
        # Sort states by timestamp.
        sorted_states = sorted(states, key=lambda state: state[0])

        # Create minimal header.
        header = OemHeader(
            version=2.0,
            creation_date=time_utils.datetime_to_iso8601(datetime.now(timezone.utc)),
            originator="ephem-toolkit",
        )

        # Create metadata with provided values.
        meta = OemMeta(
            object_name=object_name,
            object_id=object_id,
            ref_frame=ref_frame,
            center_name=center_name,
            time_system=time_system,
        )

        # Set start/stop times from states.
        if sorted_states:
            start_dt = time_utils.tt_s_to_datetime(sorted_states[0][0])
            stop_dt = time_utils.tt_s_to_datetime(sorted_states[-1][0])
            meta.start_time = time_utils.datetime_to_iso8601(start_dt)
            meta.stop_time = time_utils.datetime_to_iso8601(stop_dt)

        return cls(header=header, meta=meta, data_comments=[], states=sorted_states)

    @property
    def epochs(self) -> list[float]:
        """Sorted list of epoch timestamps in TT seconds since J2000."""
        return [epoch for epoch, _ in self.states]

    @property
    def state_vectors(self) -> np.ndarray:
        """State vectors ordered by epoch, shape ``(N, 6)`` in meters (m) and m/s."""
        return np.array([state for _, state in self.states])

    def write_state(
        self,
        dest: TextIO,
        epoch: datetime,
        state_vector: np.ndarray,
        sep: str = " ",
    ) -> None:
        """Write a single state vector without header or metadata.

        Converts from internal SI units (m, m/s) to OEM standard units (km, km/s).

        Parameters
        ----------
        dest : TextIO
            Writable text stream.
        epoch : datetime
            State epoch.
        state_vector : np.ndarray
            Six-element state vector in meters (m) and m/s.
        sep : str, optional
            Separator between fields (default: a single space).
        """
        dt: datetime = epoch
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        epoch_str: str = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

        state_km: np.ndarray = state_vector / KILOMETERS_TO_METERS
        values: list[str] = [f"{value:.15g}" for value in state_km]
        self.write_line(dest, epoch_str, *values, sep=sep)

    def write_states(
        self,
        dest: TextIO,
        format_type: OemFormat = OemFormat.OEM,
    ) -> None:
        """Write this OEM's state vectors without header or metadata.

        Parameters
        ----------
        dest : TextIO
            Writable text stream.
        format_type : OemFormat, optional
            Output format, either :attr:`OemFormat.OEM` or :attr:`OemFormat.CSV`.
        """
        sep: str = "," if format_type is OemFormat.CSV else " "
        if format_type is OemFormat.CSV:
            self.write_line(dest, *_CSV_STATE_HEADERS, sep=sep)

        for epoch, state_vector in self.states:
            self.write_state(
                dest,
                time_utils.tt_s_to_datetime(epoch),
                state_vector,
                sep=sep,
            )

    def _write_header(self, dest: TextIO, sep: str = " ") -> None:
        """Write the OEM header to a writable text stream."""
        header_pad: int = max(len(key) for key in _HEADER_KEY_ORDER)

        self.write_line(
            dest,
            f"{'CCSDS_OEM_VERS':<{header_pad}}",
            "=",
            str(self.header.version),
            sep=sep,
        )

        # Header COMMENT lines are allowed only immediately after the OEM version.
        if self.header.comments:
            self.write_line(dest, sep=sep)
            for comment in self.header.comments:
                self.write_line(dest, "COMMENT", comment, sep=sep)
            self.write_line(dest, sep=sep)

        self.write_line(
            dest,
            f"{'CREATION_DATE':<{header_pad}}",
            "=",
            self.header.creation_date,
            sep=sep,
        )
        self.write_line(
            dest,
            f"{'ORIGINATOR':<{header_pad}}",
            "=",
            self.header.originator,
            sep=sep,
        )
        if self.header.classification:
            self.write_line(
                dest,
                f"{'CLASSIFICATION':<{header_pad}}",
                "=",
                self.header.classification,
                sep=sep,
            )
        if self.header.message_id:
            self.write_line(
                dest,
                f"{'MESSAGE_ID':<{header_pad}}",
                "=",
                self.header.message_id,
                sep=sep,
            )
        self.write_line(dest, sep=sep)

    def _write_meta(self, dest: TextIO, sep: str = " ") -> None:
        """Write the OEM metadata section to a writable text stream."""
        self.write_line(dest, "META_START", sep=sep)

        # Metadata COMMENT lines are allowed only immediately after META_START.
        for comment in self.meta.comments:
            self.write_line(dest, "COMMENT", comment, sep=sep)

        pad: int = max(
            (
                len(key)
                for key in _META_KEY_ORDER
                if getattr(self.meta, key.lower()) not in (None, "", 0)
            ),
            default=0,
        )

        for key in _META_KEY_ORDER:
            value: str | int = getattr(self.meta, key.lower())
            if value is not None and value != "" and value != 0:
                self.write_line(dest, f"{key:<{pad}}", "=", str(value), sep=sep)

        self.write_line(dest, "META_STOP", sep=sep)
        self.write_line(dest, sep=sep)

    def write(
        self,
        dest: TextIO | str | Path,
        format_type: OemFormat = OemFormat.OEM,
    ) -> None:
        """Write this OEM to a file or stream.

        Parameters
        ----------
        dest : TextIO | str | Path
            A writable text stream, file path string, or :class:`Path`.
        format_type : OemFormat, optional
            Output format, either :attr:`OemFormat.OEM` or :attr:`OemFormat.CSV`.
        """
        sep: str = "," if format_type is OemFormat.CSV else " "

        if isinstance(dest, (str, Path)):
            with open(dest, "w", encoding="utf-8") as file_handle:
                self.write(file_handle, format_type=format_type)
            return

        self._write_header(dest, sep=sep)

        self._write_meta(dest, sep=sep)

        for comment in self.data_comments:
            self.write_line(dest, "COMMENT", comment, sep=sep)
        if self.data_comments:
            self.write_line(dest, sep=sep)

        self.write_states(dest, format_type=format_type)

    def update_metadata(self, **kwargs: Any) -> None:
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

    def __len__(self) -> int:
        """Return the number of state vectors stored in this OEM."""
        return len(self.states)

    def find_state_by_timestamp(
        self,
        timestamp: float,
        tolerance: float = 0.0,
    ) -> tuple[float, np.ndarray] | None:
        """Find a state by timestamp using binary search.

        Parameters
        ----------
        timestamp : float
            TT seconds since J2000 to search for.
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
        if not self.states:
            return None

        timestamps = [epoch for epoch, _ in self.states]
        timestamp_index = bisect.bisect_left(timestamps, timestamp)

        if tolerance == 0.0:
            if (
                timestamp_index < len(self.states)
                and timestamps[timestamp_index] == timestamp
            ):
                return self.states[timestamp_index]
            return None

        candidates: list[tuple[int, float]] = []
        if timestamp_index < len(self.states):
            candidates.append(
                (
                    timestamp_index,
                    abs(timestamps[timestamp_index] - timestamp),
                )
            )
        if timestamp_index > 0:
            candidates.append(
                (
                    timestamp_index - 1,
                    abs(timestamps[timestamp_index - 1] - timestamp),
                )
            )

        if not candidates:
            return None

        best_idx, best_diff = min(candidates, key=lambda candidate: candidate[1])
        if best_diff <= tolerance:
            return self.states[best_idx]
        return None

    def __repr__(self) -> str:
        """Return a concise string representation of this OEM instance."""
        return (
            f"CcsdsOem(object={self.meta.object_name!r}, "
            f"frame={self.meta.ref_frame!r}, "
            f"epochs={len(self.states)})"
        )
