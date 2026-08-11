"""Read, parse, and write NORAD Two-Line Element (TLE) sets.

Provides a structured :class:`Tle` dataclass and low-level functions
(:func:`read_tle`, :func:`write_tle`) that operate on :class:`Tle`
instances or plain dictionaries.

References:
    NORAD Two-Line Element Set Format.
    Celestrak: https://celestrak.org/NORAD/documentation/tle-fmt.php
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, TextIO

import common.common as common
import common.time_utils as time_utils

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

    name: str = ""
    """Satellite name (may be empty if not present in the TLE source)"""

    line1: str = ""
    """Raw TLE line 1"""
    line2: str = ""
    """Raw TLE line 2"""

    norad_cat_id: int = 0
    """NORAD catalog number (satellite number)"""
    classification: str = "U"
    """Classification (U=Unclassified, C=Classified, S=Secret)"""
    int_designator_year: int = 0
    """International designator launch year (2-digit)"""
    int_designator_launch_number: int = 0
    """International designator launch number of the year"""
    int_designator_piece: str = ""
    """International designator piece of the launch"""
    epoch_year: int = 0
    """Epoch year (2-digit)"""
    epoch_day: float = 0.0
    """Epoch day of year with fractional portion"""
    mean_motion_first_derivative: float = 0.0
    """First time derivative of mean motion (revolutions per day²)"""
    mean_motion_second_derivative: str = "00000+0"
    """Second time derivative of mean motion (TLE exponential format)"""
    bstar: str = "00000+0"
    """BSTAR drag term (TLE exponential format)"""
    ephemeris_type: int = 0
    """Ephemeris type (1=SGP, 2=SGP4, 3=SDP4, 4=SGP8, 5=SDP8)"""
    element_set_number: int = 0
    """Element set number (incremented for each new TLE)"""
    line1_checksum: str = ""
    """Modulo-10 checksum for line 1 (as read from TLE)"""
    line1_checksum_expected: str = ""
    """Computed modulo-10 checksum for line 1"""

    inclination_deg: float = 0.0
    """Inclination (degrees)"""
    raan_deg: float = 0.0
    """Right ascension of ascending node (degrees)"""
    eccentricity_raw: str = ""
    """Eccentricity (raw 7-digit string from TLE, without leading decimal point)"""
    eccentricity: float = 0.0
    """Eccentricity (decimal value, 0.0 to 1.0)"""
    arg_perigee_deg: float = 0.0
    """Argument of perigee (degrees)"""
    mean_anomaly_deg: float = 0.0
    """Mean anomaly (degrees)"""
    mean_motion_rev_per_day: float = 0.0
    """Mean motion (revolutions per day)"""
    revolution_number_at_epoch: int = 0
    """Revolution number at epoch"""
    line2_checksum: str = ""
    """Modulo-10 checksum for line 2 (as read from TLE)"""
    line2_checksum_expected: str = ""
    """Computed modulo-10 checksum for line 2"""

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
            f"norad_cat_id={self.norad_cat_id}, "
            f"epoch_year={self.epoch_year}, "
            f"epoch_day={self.epoch_day:.8f})"
        )


# ===================================================================
# Internal helpers
# ===================================================================


def compute_tle_checksum(line_without_checksum: str) -> str:
    """Return the single-digit TLE checksum character for *line_without_checksum*.

    Parameters
    ----------
    line_without_checksum : str
        TLE line without the trailing checksum digit (68 characters).

    Returns
    -------
    str
        Single-digit checksum character (0-9).
    """
    checksum: int = 0
    for char in line_without_checksum:
        if char.isdigit():
            checksum += int(char)
        elif char == "-":
            checksum += 1
    return str(checksum % 10)


def _parse_tle_exponential(field_value: str, field_name: str) -> str:
    """Validate TLE exponential format, e.g. ``'00000-0'`` or ``'29661-4'``.

    Parameters
    ----------
    field_value : str
        Raw field value from TLE (7 or 8 characters).
    field_name : str
        Name of the field for error messages.

    Returns
    -------
    str
        Validated 8-character exponential format string.

    Raises
    ------
    ValueError
        If the format is invalid.
    """
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
            f"{field_name} must match [sign]#####<+|-># in TLE notation; "
            f"got '{field_value}'"
        )

    return value


def _format_first_derivative(value: float) -> str:
    """Format first time derivative of mean motion for TLE line 1 (10 chars).

    Parameters
    ----------
    value : float
        First time derivative of mean motion (revolutions per day²).

    Returns
    -------
    str
        Formatted 10-character string for TLE line 1.

    Raises
    ------
    ValueError
        If the value cannot be represented in the 10-character field.
    """
    sign: str = "-" if value < 0 else " "
    magnitude: str = f"{abs(value):.8f}"

    if magnitude.startswith("0"):
        magnitude = magnitude[1:]

    formatted: str = sign + magnitude
    if len(formatted) != 10:
        raise ValueError(
            "mean-motion-first-derivative cannot be represented in 10-char TLE field"
        )
    return formatted


def _tle_field(tle_data: Tle | Mapping[str, object], field_name: str) -> object:
    """Retrieve a field from a :class:`Tle` instance or a :class:`Mapping`.

    Parameters
    ----------
    tle_data : Tle | Mapping[str, object]
        A :class:`Tle` instance or a mapping.
    field_name : str
        Name of the field to retrieve.

    Returns
    -------
    object
        The field value.

    Raises
    ------
    AttributeError
        If the field does not exist in a :class:`Tle` instance.
    KeyError
        If the field does not exist in a mapping.
    """
    if isinstance(tle_data, Tle):
        return getattr(tle_data, field_name)
    return tle_data[field_name]


def _tle_field_opt(
    tle_data: Tle | Mapping[str, object],
    field_name: str,
    default: object = None,
) -> object:
    """Retrieve an optional field from a :class:`Tle` or :class:`Mapping`.

    Parameters
    ----------
    tle_data : Tle | Mapping[str, object]
        A :class:`Tle` instance or a mapping.
    field_name : str
        Name of the field to retrieve.
    default : object, optional
        Default value if the field does not exist (default: None).

    Returns
    -------
    object
        The field value or the default if not found.
    """
    if isinstance(tle_data, Tle):
        return getattr(tle_data, field_name, default)
    return tle_data.get(field_name, default)  # type: ignore[union-attr]


def create_tle_from_mean_keplerian(
    mean_elements: object,
    mu_m3_s2: float,
    epoch_year: int,
    epoch_day: float,
    name: str = "OBJECT",
    norad_cat_id: int = 0,
    classification: str = "U",
    int_designator_year: int = 0,
    int_designator_launch_number: int = 0,
    int_designator_piece: str = "",
    mean_motion_first_derivative: float = 0.0,
    mean_motion_second_derivative: str = "00000+0",
    bstar: str = "00000+0",
    ephemeris_type: int = 2,
    element_set_number: int = 0,
    revolution_number_at_epoch: int = 0,
) -> Tle:
    """Create a TLE object from mean Keplerian elements.

    Parameters
    ----------
    mean_elements : object
        Mean Keplerian elements array with indices:
        [0] = semi-major axis (m)
        [1] = eccentricity (dimensionless)
        [2] = inclination (rad)
        [3] = argument of periapsis (rad)
        [4] = RAAN (rad)
        [5] = mean anomaly (rad)
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    name : str
        Satellite name.
    norad_cat_id : int
        NORAD catalog number.
    classification : str
        Classification (U=Unclassified, C=Classified, S=Secret).
    int_designator_year : int
        International designator launch year (2-digit).
    int_designator_launch_number : int
        International designator launch number of the year.
    int_designator_piece : str
        International designator piece of the launch.
    epoch_year : int
        Epoch year (2-digit).
    epoch_day : float
        Epoch day of year with fractional portion.
    mean_motion_first_derivative : float
        First time derivative of mean motion (revolutions per day²).
    mean_motion_second_derivative : str
        Second time derivative of mean motion (TLE exponential format).
    bstar : str
        BSTAR drag term (TLE exponential format).
    ephemeris_type : int
        Ephemeris type (default: 2 for SGP4).
    element_set_number : int
        Element set number.
    revolution_number_at_epoch : int
        Revolution number at epoch.

    Returns
    -------
    Tle
        A :class:`Tle` dataclass instance with the provided elements.
    """
    import math
    import common.kepler as kepler

    # Extract mean Keplerian elements from array
    # Assuming mean_elements is array-like with indices:
    # [0] = semi-major axis (m)
    # [1] = eccentricity
    # [2] = inclination (rad)
    # [3] = argument of periapsis (rad)
    # [4] = RAAN (rad)
    # [5] = mean anomaly (rad)
    a_m: float = float(mean_elements[0])
    e: float = float(mean_elements[1])
    i_rad: float = float(mean_elements[2])
    omega_rad: float = float(mean_elements[3])
    raan_rad: float = float(mean_elements[4])
    M_rad: float = float(mean_elements[5])

    # Compute mean motion from semi-major axis
    mean_motion_rev_day: float = kepler.semi_major_axis_to_mean_motion(a_m, mu_m3_s2)

    # Create and return TLE object
    return Tle(
        name=name,
        norad_cat_id=norad_cat_id,
        classification=classification,
        int_designator_year=int_designator_year,
        int_designator_launch_number=int_designator_launch_number,
        int_designator_piece=int_designator_piece,
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        mean_motion_first_derivative=mean_motion_first_derivative,
        mean_motion_second_derivative=mean_motion_second_derivative,
        bstar=bstar,
        ephemeris_type=ephemeris_type,
        element_set_number=element_set_number,
        inclination_deg=math.degrees(i_rad),
        raan_deg=math.degrees(raan_rad),
        eccentricity=e,
        eccentricity_raw=f"{int(round(e * 1e7)):07d}",
        arg_perigee_deg=math.degrees(omega_rad),
        mean_anomaly_deg=math.degrees(M_rad),
        mean_motion_rev_per_day=mean_motion_rev_day,
        revolution_number_at_epoch=revolution_number_at_epoch,
    )


def _format_tle_strings(
    tle_data: Tle | Mapping[str, object],
) -> tuple[str, str]:
    """Format TLE data into line1 and line2 strings (without checksums).

    Parameters
    ----------
    tle_data : Tle | Mapping[str, object]
        A :class:`Tle` dataclass instance or a mapping containing the
        parsed TLE fields returned by :func:`read_tle`.

    Returns
    -------
    tuple[str, str]
        The formatted *(line1_no_cksum, line2_no_cksum)* strings (68 chars each,
        without trailing checksum digits).

    Raises
    ------
    ValueError
        If formatting fails or line lengths are incorrect.
    """
    norad_cat_id: int = _tle_field(tle_data, "norad_cat_id")  # type: ignore[assignment]
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

    sat_num: str = f"{norad_cat_id:05d}"
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

    line2_no_cksum: str = (
        f"2 {sat_num} " f"{inc} {raan} {ecc} {argp} {ma} " f"{mm}{rev_num}"
    )

    if len(line1_no_cksum) != 68:
        raise ValueError(
            f"Internal formatting error: line 1 length is "
            f"{len(line1_no_cksum)} (expected 68)"
        )

    if len(line2_no_cksum) != 68:
        raise ValueError(
            f"Internal formatting error: line 2 length is "
            f"{len(line2_no_cksum)} (expected 68)"
        )

    return line1_no_cksum, line2_no_cksum


def format_tle_strings(
    tle_data: Tle | Mapping[str, object],
) -> tuple[str, str]:
    line1_no_cksum: str
    line2_no_cksum: str
    line1_no_cksum, line2_no_cksum = _format_tle_strings(tle_data)

    line1: str = line1_no_cksum + compute_tle_checksum(line1_no_cksum)
    line2: str = line2_no_cksum + compute_tle_checksum(line2_no_cksum)
    return line1, line2


# ===================================================================
# Epoch utilities
# ===================================================================


def datetime_to_tle_epoch(epoch_dt: datetime) -> tuple[int, float]:
    """Convert datetime to (two-digit year, day-of-year with fraction).

    Parameters
    ----------
    epoch_dt : datetime
        Epoch datetime.

    Returns
    -------
    tuple[int, float]
        Two-digit year and day-of-year with fractional portion.
    """
    epoch_year: int = epoch_dt.year % 100
    start_of_year: datetime
    if epoch_dt.tzinfo is not None:
        epoch_dt = epoch_dt.astimezone(timezone.utc)
        start_of_year = datetime(epoch_dt.year, 1, 1, tzinfo=timezone.utc)
    else:
        start_of_year = datetime(epoch_dt.year, 1, 1)
    epoch_day: float = (
        epoch_dt - start_of_year
    ).total_seconds() / time_utils.SECONDS_PER_DAY + 1.0
    return epoch_year, epoch_day


def tle_epoch_to_iso8601(epoch_year: int, epoch_day: float) -> str:
    """Convert TLE epoch (2-digit year + fractional day) to a human-readable string.

    Uses :func:`common.time_utils.datetime_to_iso8601` for consistent ISO 8601
    formatting across the library.

    Parameters
    ----------
    epoch_year : int
        Two-digit year from TLE.
    epoch_day : float
        Fractional day of year.

    Returns
    -------
    str
        ISO 8601 date-time string with 6 fractional-second digits.

    See Also
    --------
    iso8601_to_tle_epoch : Inverse operation.
    common.time_utils.datetime_to_iso8601 : Shared ISO 8601 formatting utility.
    """
    # Convert 2-digit year to 4-digit year
    if epoch_year >= 57:
        year: int = 1900 + epoch_year
    else:
        year = 2000 + epoch_year

    # Day 1 = Jan 1, so day-of-year offset is (epoch_day - 1)
    dt: datetime = datetime(year, 1, 1) + timedelta(days=epoch_day - 1.0)
    return time_utils.datetime_to_iso8601(dt, fractional_second_places=6)


def iso8601_to_tle_epoch(iso_str: str) -> tuple[int, float]:
    """Convert ISO 8601 datetime string to TLE epoch (2-digit year + fractional day).

    Uses :func:`common.time_utils.iso8601_to_datetime` for consistent ISO 8601
    parsing across the library.

    Parameters
    ----------
    iso_str : str
        ISO 8601 datetime string, e.g. ``"2026-06-01T07:45:33.102720"``.

    Returns
    -------
    tuple[int, float]
        ``(epoch_year, epoch_day)`` where epoch_year is 2-digit and
        epoch_day is the 1-based fractional day of year.

    See Also
    --------
    tle_epoch_to_iso8601 : Inverse operation.
    common.time_utils.iso8601_to_datetime : Shared ISO 8601 parsing utility.
    """
    dt: datetime = time_utils.iso8601_to_datetime(iso_str)

    return datetime_to_tle_epoch(dt)


# ===================================================================
# Reader
# ===================================================================


def read_tle(stream: TextIO) -> Tle:
    """Parse TLE elements from a text stream (file-like object).

    The stream should contain either:

    * Two lines: *line1* and *line2* of the TLE.
    * Three lines: *name*, *line1*, and *line2* of the TLE.

    Parameters
    ----------
    stream : TextIO
        Readable text stream containing TLE data.

    Returns
    -------
    Tle
        A :class:`Tle` dataclass instance with all parsed elements.
    """
    lines: list[str] = [line.rstrip("\n") for line in stream if line.strip()]

    if len(lines) < 2:
        raise ValueError("Expected at least 2 non-empty lines from stream")

    if lines[0].startswith("1 ") and lines[1].startswith("2 "):
        name: str = ""
        line1: str = lines[0]
        line2: str = lines[1]
    elif len(lines) >= 3 and lines[1].startswith("1 ") and lines[2].startswith("2 "):
        name = lines[0].strip()
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
        norad_cat_id=int(line1[2:7]),
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
    dest: TextIO | str | Path,
    tle_data: Tle | Mapping[str, object],
) -> tuple[str, str]:
    """Write a TLE to a text stream or file path.

    Parameters
    ----------
    dest : TextIO | str | Path
        Writable text stream or destination file path.
    tle_data : Tle | Mapping[str, object]
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

    line1, line2 = format_tle_strings(tle_data)

    name: str = _tle_field_opt(tle_data, "name", "")  # type: ignore[assignment]
    w: Callable[[str], int] = dest.write

    if name:
        w(name + "\n")
    w(line1 + "\n")
    w(line2 + "\n")

    return line1, line2
