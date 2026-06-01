"""Read, parse, and write NORAD Two-Line Element (TLE) sets.

Provides a structured :class:`Tle` dataclass and low-level functions
(:func:`read_tle`, :func:`write_tle`) that operate on :class:`Tle`
instances or plain dictionaries.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Mapping, Union

# ===================================================================
# Structured dataclass
# ===================================================================


@dataclass
class Tle:
    """Parsed Two-Line Element set data.

    All fields correspond to the standard TLE format.  Angular quantities
    are stored in degrees and mean motion in revolutions per day, matching
    the native TLE representation.
    """

    # Satellite name (may be empty if not present in the TLE source)
    name: str = ""

    # Raw TLE lines
    line1: str = ""
    line2: str = ""

    # Line 1 elements
    satellite_number: int = 0
    classification: str = "U"
    int_designator_year: int = 0
    int_designator_launch_number: int = 0
    int_designator_piece: str = ""
    epoch_year: int = 0
    epoch_day: float = 0.0
    mean_motion_first_derivative: float = 0.0
    mean_motion_second_derivative: str = "00000+0"
    bstar: str = "00000+0"
    ephemeris_type: int = 0
    element_set_number: int = 0
    line1_checksum: str = ""
    line1_checksum_expected: str = ""

    # Line 2 elements
    inclination_deg: float = 0.0
    raan_deg: float = 0.0
    eccentricity_raw: str = ""
    eccentricity: float = 0.0
    arg_perigee_deg: float = 0.0
    mean_anomaly_deg: float = 0.0
    mean_motion_rev_per_day: float = 0.0
    revolution_number_at_epoch: int = 0
    line2_checksum: str = ""
    line2_checksum_expected: str = ""

    def to_dict(self) -> dict[str, object]:
        """Convert to a plain dictionary (for backward compatibility)."""
        return asdict(self)

    def __getitem__(self, key: str) -> object:
        """Allow dict-style access for backward compatibility."""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Support ``key in tle`` for backward compatibility."""
        return hasattr(self, key)

    def get(self, key: str, default: object = None) -> object:
        """Dict-like ``.get()`` for backward compatibility."""
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def __repr__(self) -> str:
        return (
            f"Tle(name={self.name!r}, "
            f"satellite_number={self.satellite_number}, "
            f"epoch_year={self.epoch_year}, "
            f"epoch_day={self.epoch_day:.8f})"
        )


# ===================================================================
# Internal helpers
# ===================================================================


def compute_tle_checksum(line_without_checksum: str) -> str:
    """Return the single-digit TLE checksum character for *line_without_checksum*."""
    checksum: int = 0
    for char in line_without_checksum:
        if char.isdigit():
            checksum += int(char)
        elif char == "-":
            checksum += 1
    return str(checksum % 10)


def _parse_tle_exponential(field_value: str, field_name: str) -> str:
    """Validate TLE exponential format, e.g. ``'00000-0'`` or ``'29661-4'``."""
    value: str = field_value.strip()

    if len(value) == 7:
        value = " " + value

    if len(value) != 8:
        raise ValueError(
            f"{field_name} must be 7 or 8 chars in TLE format "
            f"(e.g. 00000-0,  29661-4, -12345-6)"
        )

    if not re.fullmatch(r"[ +\-]\d{5}[+\-]\d", value):
        raise ValueError(
            f"{field_name} must match [sign]#####<+|-># in TLE notation; " f"got '{field_value}'"
        )

    return value


def _format_first_derivative(value: float) -> str:
    """Format first time derivative of mean motion for TLE line 1 (10 chars)."""
    sign: str = "-" if value < 0 else " "
    magnitude: str = f"{abs(value):.8f}"

    if magnitude.startswith("0"):
        magnitude = magnitude[1:]

    formatted: str = sign + magnitude
    if len(formatted) != 10:
        raise ValueError("mean-motion-first-derivative cannot be represented in 10-char TLE field")
    return formatted


def _tle_field(tle_data: Tle | Mapping[str, object], field_name: str) -> object:
    """Retrieve a field from a :class:`Tle` instance or a :class:`Mapping`."""
    if isinstance(tle_data, Tle):
        return getattr(tle_data, field_name)
    return tle_data[field_name]


def _tle_field_opt(
    tle_data: Tle | Mapping[str, object],
    field_name: str,
    default: object = None,
) -> object:
    """Retrieve an optional field from a :class:`Tle` or :class:`Mapping`."""
    if isinstance(tle_data, Tle):
        return getattr(tle_data, field_name, default)
    return tle_data.get(field_name, default)  # type: ignore[union-attr]


# ===================================================================
# Reader
# ===================================================================


def read_tle(stream: IO[str]) -> Tle:
    """Parse TLE elements from a text stream (file-like object).

    The stream should contain either:

    * Two lines: *line1* and *line2* of the TLE.
    * Three lines: *name*, *line1*, and *line2* of the TLE.

    Returns a :class:`Tle` dataclass instance with all parsed elements.
    """
    lines: list[str] = [line.rstrip("\n") for line in stream if line.strip()]

    if len(lines) < 2:
        raise ValueError("Expected at least 2 non-empty lines from stream")

    if lines[0].startswith("1 ") and lines[1].startswith("2 "):
        name: str = ""
        line1: str = lines[0]
        line2: str = lines[1]
    elif len(lines) >= 3 and lines[1].startswith("1 ") and lines[2].startswith("2 "):
        name = lines[0]
        line1 = lines[1]
        line2 = lines[2]
    else:
        raise ValueError(
            "Could not identify TLE lines. Expected either "
            "'<line1> <line2>' or '<name> <line1> <line2>'"
        )

    if len(line1) < 69 or len(line2) < 69:
        raise ValueError("TLE lines must be at least 69 characters long")

    line1 = line1[:69]
    line2 = line2[:69]

    if line1[0] != "1" or line2[0] != "2":
        raise ValueError("Invalid line numbers in TLE")

    eccentricity_raw: str = line2[26:33]

    return Tle(
        name=name,
        line1=line1,
        line2=line2,
        satellite_number=int(line1[2:7]),
        classification=line1[7],
        int_designator_year=int(line1[9:11]),
        int_designator_launch_number=int(line1[11:14]),
        int_designator_piece=line1[14:17].strip(),
        epoch_year=int(line1[18:20]),
        epoch_day=float(line1[20:32]),
        mean_motion_first_derivative=float(line1[33:43]),
        mean_motion_second_derivative=line1[44:52].strip(),
        bstar=line1[53:61].strip(),
        ephemeris_type=int(line1[62]),
        element_set_number=int(line1[64:68]),
        line1_checksum=line1[68],
        line1_checksum_expected=compute_tle_checksum(line1[:68]),
        inclination_deg=float(line2[8:16]),
        raan_deg=float(line2[17:25]),
        eccentricity_raw=eccentricity_raw,
        eccentricity=float(f"0.{eccentricity_raw}"),
        arg_perigee_deg=float(line2[34:42]),
        mean_anomaly_deg=float(line2[43:51]),
        mean_motion_rev_per_day=float(line2[52:63]),
        revolution_number_at_epoch=int(line2[63:68]),
        line2_checksum=line2[68],
        line2_checksum_expected=compute_tle_checksum(line2[:68]),
    )


# ===================================================================
# Writer
# ===================================================================


def write_tle(
    dest: Union[IO[str], str, Path],
    tle_data: Tle | Mapping[str, object],
) -> tuple[str, str]:
    """Write a TLE to a text stream or file path.

    Parameters
    ----------
    dest:
        Writable text stream or destination file path.
    tle_data:
        A :class:`Tle` dataclass instance or a mapping containing the
        parsed TLE fields returned by :func:`read_tle`.

    Returns
    -------
    tuple[str, str]
        The formatted *(line1, line2)* strings that were written.
    """
    if isinstance(dest, (str, Path)):
        with open(dest, "w", encoding="utf-8") as fh:
            return write_tle(fh, tle_data)

    satellite_number: int = _tle_field(tle_data, "satellite_number")  # type: ignore[assignment]
    classification: str = _tle_field(tle_data, "classification")  # type: ignore[assignment]
    int_designator_year: int = _tle_field(tle_data, "int_designator_year")  # type: ignore[assignment]
    int_designator_launch_number: int = _tle_field(tle_data, "int_designator_launch_number")  # type: ignore[assignment]
    int_designator_piece: str = _tle_field(tle_data, "int_designator_piece")  # type: ignore[assignment]
    epoch_year: int = _tle_field(tle_data, "epoch_year")  # type: ignore[assignment]
    epoch_day: float = _tle_field(tle_data, "epoch_day")  # type: ignore[assignment]
    mean_motion_first_derivative: float = _tle_field(tle_data, "mean_motion_first_derivative")  # type: ignore[assignment]
    mean_motion_second_derivative: str = _tle_field(tle_data, "mean_motion_second_derivative")  # type: ignore[assignment]
    bstar: str = _tle_field(tle_data, "bstar")  # type: ignore[assignment]
    ephemeris_type: int = _tle_field(tle_data, "ephemeris_type")  # type: ignore[assignment]
    element_set_number: int = _tle_field(tle_data, "element_set_number")  # type: ignore[assignment]
    inclination_deg: float = _tle_field(tle_data, "inclination_deg")  # type: ignore[assignment]
    raan_deg: float = _tle_field(tle_data, "raan_deg")  # type: ignore[assignment]
    eccentricity: float = _tle_field(tle_data, "eccentricity")  # type: ignore[assignment]
    arg_perigee_deg: float = _tle_field(tle_data, "arg_perigee_deg")  # type: ignore[assignment]
    mean_anomaly_deg: float = _tle_field(tle_data, "mean_anomaly_deg")  # type: ignore[assignment]
    mean_motion_rev_per_day: float = _tle_field(tle_data, "mean_motion_rev_per_day")  # type: ignore[assignment]
    revolution_number_at_epoch: int = _tle_field(tle_data, "revolution_number_at_epoch")  # type: ignore[assignment]
    name: str = _tle_field_opt(tle_data, "name", "")  # type: ignore[assignment]

    sat_num: str = f"{satellite_number:05d}"
    cls: str = classification.upper()

    intl_year: str = f"{int_designator_year:02d}"
    intl_launch: str = f"{int_designator_launch_number:03d}"
    intl_piece: str = int_designator_piece.strip().upper().ljust(3)[:3]

    ep_year: str = f"{epoch_year:02d}"
    ep_day: str = f"{epoch_day:012.8f}"

    mm_first: str = _format_first_derivative(mean_motion_first_derivative)
    mm_second: str = _parse_tle_exponential(
        mean_motion_second_derivative, "mean-motion-second-derivative"
    )
    bstar_fmt: str = _parse_tle_exponential(bstar, "bstar")

    eph_type: str = str(ephemeris_type)
    elem_set: str = f"{element_set_number:4d}"

    inc: str = f"{inclination_deg:8.4f}"
    raan: str = f"{raan_deg:8.4f}"
    ecc: str = f"{int(round(eccentricity * 1e7)):07d}"
    argp: str = f"{arg_perigee_deg:8.4f}"
    ma: str = f"{mean_anomaly_deg:8.4f}"
    mm: str = f"{mean_motion_rev_per_day:11.8f}"
    rev_num: str = f"{revolution_number_at_epoch:05d}"

    line1_no_cksum: str = (
        f"1 {sat_num}{cls} "
        f"{intl_year}{intl_launch}{intl_piece} "
        f"{ep_year}{ep_day} "
        f"{mm_first} {mm_second} {bstar_fmt} "
        f"{eph_type} "
        f"{elem_set}"
    )

    line2_no_cksum: str = f"2 {sat_num} " f"{inc} {raan} {ecc} {argp} {ma} " f"{mm}{rev_num}"

    if len(line1_no_cksum) != 68:
        raise ValueError(
            f"Internal formatting error: line 1 length is " f"{len(line1_no_cksum)} (expected 68)"
        )

    if len(line2_no_cksum) != 68:
        raise ValueError(
            f"Internal formatting error: line 2 length is " f"{len(line2_no_cksum)} (expected 68)"
        )

    line1: str = line1_no_cksum + compute_tle_checksum(line1_no_cksum)
    line2: str = line2_no_cksum + compute_tle_checksum(line2_no_cksum)

    w = dest.write

    if name:
        w(name.strip() + "\n")
    w(line1 + "\n")
    w(line2 + "\n")

    return line1, line2
