"""Convert between TLE and OMM representations.

Provides :func:`tle_to_omm` to convert a :class:`~common.tle.Tle` instance
into a :class:`~common.omm.CcsdsOmm` instance, performing the necessary
field mapping and format transformations.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

from common.omm import CcsdsOmm
from common.tle import Tle

# ===================================================================
# Internal helpers
# ===================================================================


def _epoch_to_iso8601(epoch_year: int, epoch_day: float) -> str:
    """Convert TLE epoch (2-digit year + fractional day-of-year) to ISO 8601.

    Parameters
    ----------
    epoch_year:
        Two-digit year from TLE (e.g. 26 for 2026, 99 for 1999).
    epoch_day:
        Fractional day of year (1-based, e.g. 152.32329980).

    Returns
    -------
    str
        ISO 8601 datetime string with microsecond precision,
        e.g. ``"2026-06-01T07:45:33.102720"``.
    """
    # Resolve 2-digit year: 57-99 -> 1957-1999, 00-56 -> 2000-2056
    if epoch_year >= 57:
        full_year = 1900 + epoch_year
    else:
        full_year = 2000 + epoch_year

    # Day 1 = January 1, so day-of-year is 1-based
    jan1 = datetime(full_year, 1, 1, tzinfo=timezone.utc)
    dt = jan1 + timedelta(days=epoch_day - 1.0)

    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _iso8601_to_epoch(iso_str: str) -> tuple[int, float]:
    """Convert ISO 8601 datetime string to TLE epoch (2-digit year + fractional day).

    Parameters
    ----------
    iso_str:
        ISO 8601 datetime string, e.g. ``"2026-06-01T07:45:33.102720"``.

    Returns
    -------
    tuple[int, float]
        ``(epoch_year, epoch_day)`` where epoch_year is 2-digit and
        epoch_day is the 1-based fractional day of year.
    """
    dt = datetime.fromisoformat(iso_str)
    full_year = dt.year
    jan1 = datetime(full_year, 1, 1, tzinfo=dt.tzinfo if dt.tzinfo else None)
    epoch_day = (dt - jan1).total_seconds() / 86400.0 + 1.0

    # 2-digit year
    if full_year >= 2000:
        epoch_year = full_year - 2000
    else:
        epoch_year = full_year - 1900

    return epoch_year, epoch_day


def _tle_exponential_to_float(tle_exp: str) -> float:
    """Convert TLE exponential notation to a float.

    TLE exponential format: ``[sign]#####[+|-]#``
    Examples: ``"17978-3"`` -> 0.17978e-3, ``" 00000+0"`` -> 0.0,
    ``"-12345-6"`` -> -0.12345e-6.

    Parameters
    ----------
    tle_exp:
        The TLE exponential field (7 or 8 characters).

    Returns
    -------
    float
        The numeric value.
    """
    value = tle_exp.strip()
    if not value or value == "00000+0" or value == "00000-0":
        return 0.0

    # Normalize to 8 chars with leading space if needed
    if len(value) == 7:
        value = " " + value

    # Parse sign
    sign_char = value[0]
    if sign_char == "-":
        sign = -1.0
    else:
        sign = 1.0

    # Mantissa digits (5 digits)
    mantissa_str = value[1:6]

    # Exponent sign and digit
    exp_sign_char = value[6]
    exp_digit = value[7]

    if exp_sign_char == "-":
        exponent = -int(exp_digit)
    else:
        exponent = int(exp_digit)

    # The mantissa is an assumed decimal: ##### -> 0.#####
    mantissa = int(mantissa_str) * 1e-5

    return sign * mantissa * (10.0**exponent)


def _float_to_tle_exponential(value: float) -> str:
    """Convert a float to TLE exponential notation (7 chars).

    Produces the compact 7-character form used in TLE fields,
    e.g. ``"17978-3"`` or ``"00000+0"``.

    For negative values, returns 8-char form with leading minus,
    e.g. ``"-12345-6"``.

    Parameters
    ----------
    value:
        The numeric value to convert.

    Returns
    -------
    str
        TLE exponential string.
    """
    if value == 0.0:
        return "00000+0"

    sign = -1.0 if value < 0 else 1.0
    magnitude = abs(value)

    # Find exponent such that mantissa is 0.##### x 10^exp
    # i.e., 0.1 <= mantissa < 1.0
    exp = math.floor(math.log10(magnitude)) + 1
    mantissa = magnitude / (10.0**exp)

    # Round mantissa to 5 digits
    mantissa_int = int(round(mantissa * 1e5))

    # Handle rounding overflow
    if mantissa_int >= 100000:
        mantissa_int = 10000
        exp += 1

    # Format exponent
    if exp >= 0:
        exp_str = f"+{exp}"
    else:
        exp_str = f"-{abs(exp)}"

    unsigned_result = f"{mantissa_int:05d}{exp_str}"

    if sign < 0:
        return f"-{unsigned_result}"
    return unsigned_result


def _float_to_omm_scientific(value: float) -> str:
    """Convert a float to OMM scientific notation string.

    OMM uses a format like ``.1797805E-3`` or ``0`` for zero values.

    Parameters
    ----------
    value:
        The numeric value to convert.

    Returns
    -------
    str
        OMM-style scientific notation string.
    """
    if value == 0.0:
        return "0"

    sign = ""
    if value < 0:
        sign = "-"
        value = abs(value)

    # Find exponent such that value = mantissa x 10^exp with 0.1 <= mantissa < 1.0
    exp = math.floor(math.log10(value)) + 1
    mantissa = value / (10.0**exp)

    # Format mantissa with enough significant digits (7 digits after decimal)
    # Remove trailing zeros
    mantissa_str = f"{mantissa:.7f}".rstrip("0").rstrip(".")

    # Remove leading "0" -> ".xxxxx"
    if mantissa_str.startswith("0."):
        mantissa_str = mantissa_str[1:]

    return f"{sign}{mantissa_str}E{exp:+d}" if exp != 0 else f"{sign}{mantissa_str}"


def _omm_scientific_to_float(omm_str: str) -> float:
    """Convert OMM scientific notation string to float.

    Handles formats like ``.1797805E-3``, ``-.25E-6``, ``0``.

    Parameters
    ----------
    omm_str:
        OMM-style scientific notation string.

    Returns
    -------
    float
        The numeric value.
    """
    s = omm_str.strip()
    if not s or s == "0":
        return 0.0

    # Handle the OMM format: optional sign, then .digits, then E+/-exp
    # Add leading 0 if starts with . or -.
    if s.startswith("."):
        s = "0" + s
    elif s.startswith("-."):
        s = "-0" + s[1:]

    return float(s)


def _build_object_id(
    int_designator_year: int, int_designator_launch_number: int, int_designator_piece: str
) -> str:
    """Build COSPAR Object ID from TLE international designator components.

    Parameters
    ----------
    int_designator_year:
        2-digit year from TLE international designator.
    int_designator_launch_number:
        Launch number within the year.
    int_designator_piece:
        Piece identifier (e.g. "A", "B").

    Returns
    -------
    str
        COSPAR ID in format ``"YYYY-NNNP"`` (e.g. ``"1998-067A"``).
    """
    # Resolve 2-digit year
    if int_designator_year >= 57:
        full_year = 1900 + int_designator_year
    else:
        full_year = 2000 + int_designator_year

    piece = int_designator_piece.strip() if int_designator_piece else ""
    return f"{full_year}-{int_designator_launch_number:03d}{piece}"


def _parse_object_id(object_id: str) -> tuple[int, int, str]:
    """Parse COSPAR Object ID into TLE international designator components.

    Parameters
    ----------
    object_id:
        COSPAR ID in format ``"YYYY-NNNP"`` (e.g. ``"1998-067A"``).

    Returns
    -------
    tuple[int, int, str]
        ``(int_designator_year, int_designator_launch_number, int_designator_piece)``
        where year is 2-digit.
    """
    match = re.match(r"(\d{4})-(\d{3})(\w*)", object_id.strip())
    if not match:
        return 0, 0, ""

    full_year = int(match.group(1))
    launch_number = int(match.group(2))
    piece = match.group(3)

    if full_year >= 2000:
        year_2digit = full_year - 2000
    else:
        year_2digit = full_year - 1900

    return year_2digit, launch_number, piece


# ===================================================================
# TLE -> OMM conversion
# ===================================================================


def tle_to_omm(tle: Tle, *, creation_date: str = "", originator: str = "") -> CcsdsOmm:
    """Convert a :class:`~common.tle.Tle` to a :class:`~common.omm.CcsdsOmm`.

    Parameters
    ----------
    tle:
        Parsed TLE dataclass instance.
    creation_date:
        Optional creation date for the OMM header.
    originator:
        Optional originator for the OMM header.

    Returns
    -------
    CcsdsOmm
        The equivalent OMM representation.
    """
    # Convert epoch
    epoch_iso = _epoch_to_iso8601(tle.epoch_year, tle.epoch_day)

    # Convert BSTAR from TLE exponential to OMM scientific
    bstar_float = _tle_exponential_to_float(tle.bstar)
    bstar_omm = _float_to_omm_scientific(bstar_float)

    # Convert mean motion first derivative to OMM scientific
    mean_motion_dot_omm = _float_to_omm_scientific(tle.mean_motion_first_derivative)

    # Convert mean motion second derivative from TLE exponential to OMM scientific
    mean_motion_ddot_float = _tle_exponential_to_float(tle.mean_motion_second_derivative)
    mean_motion_ddot_omm = _float_to_omm_scientific(mean_motion_ddot_float)

    # Build COSPAR Object ID
    object_id = _build_object_id(
        tle.int_designator_year,
        tle.int_designator_launch_number,
        tle.int_designator_piece,
    )

    # Eccentricity: use the parsed float value
    eccentricity = tle.eccentricity

    return CcsdsOmm(
        version=2.0,
        creation_date=creation_date,
        originator=originator,
        comments=[],
        object_name=tle.name,
        object_id=object_id,
        center_name="EARTH",
        ref_frame="TEME",
        time_system="UTC",
        mean_element_theory="SGP/SGP4",
        epoch=epoch_iso,
        mean_motion=tle.mean_motion_rev_per_day,
        eccentricity=eccentricity,
        inclination=tle.inclination_deg,
        ra_of_asc_node=tle.raan_deg,
        arg_of_pericenter=tle.arg_perigee_deg,
        mean_anomaly=tle.mean_anomaly_deg,
        ephemeris_type=tle.ephemeris_type,
        classification_type=tle.classification,
        norad_cat_id=tle.satellite_number,
        element_set_no=tle.element_set_number,
        rev_at_epoch=tle.revolution_number_at_epoch,
        bstar=bstar_omm,
        mean_motion_dot=mean_motion_dot_omm,
        mean_motion_ddot=mean_motion_ddot_omm,
    )


# ===================================================================
# OMM -> TLE conversion
# ===================================================================


def omm_to_tle(omm: CcsdsOmm) -> Tle:
    """Convert a :class:`~common.omm.CcsdsOmm` to a :class:`~common.tle.Tle`.

    Parameters
    ----------
    omm:
        Parsed OMM dataclass instance.

    Returns
    -------
    Tle
        The equivalent TLE representation.

    Note
    ----
    The returned :class:`Tle` will have empty ``line1`` and ``line2`` fields.
    Use :func:`~common.tle.write_tle` to generate the formatted TLE lines.
    """
    # Convert epoch
    epoch_year, epoch_day = _iso8601_to_epoch(omm.epoch)

    # Convert BSTAR from OMM scientific to TLE exponential
    bstar_float = _omm_scientific_to_float(omm.bstar)
    bstar_tle = _float_to_tle_exponential(bstar_float)

    # Convert mean motion dot from OMM scientific to float
    mean_motion_dot_float = _omm_scientific_to_float(omm.mean_motion_dot)

    # Convert mean motion ddot from OMM scientific to TLE exponential
    mean_motion_ddot_float = _omm_scientific_to_float(omm.mean_motion_ddot)
    mean_motion_ddot_tle = _float_to_tle_exponential(mean_motion_ddot_float)

    # Parse Object ID into international designator components
    int_year, int_launch, int_piece = _parse_object_id(omm.object_id)

    # Eccentricity raw: 7-digit integer representation
    eccentricity_raw = f"{int(round(omm.eccentricity * 1e7)):07d}"

    return Tle(
        name=omm.object_name,
        line1="",
        line2="",
        satellite_number=omm.norad_cat_id,
        classification=omm.classification_type,
        int_designator_year=int_year,
        int_designator_launch_number=int_launch,
        int_designator_piece=int_piece,
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        mean_motion_first_derivative=mean_motion_dot_float,
        mean_motion_second_derivative=mean_motion_ddot_tle,
        bstar=bstar_tle,
        ephemeris_type=omm.ephemeris_type,
        element_set_number=omm.element_set_no,
        inclination_deg=omm.inclination,
        raan_deg=omm.ra_of_asc_node,
        eccentricity_raw=eccentricity_raw,
        eccentricity=omm.eccentricity,
        arg_perigee_deg=omm.arg_of_pericenter,
        mean_anomaly_deg=omm.mean_anomaly,
        mean_motion_rev_per_day=omm.mean_motion,
        revolution_number_at_epoch=omm.rev_at_epoch,
        line1_checksum="",
        line1_checksum_expected="",
        line2_checksum="",
        line2_checksum_expected="",
    )


# ===================================================================
# CLI entry point
# ===================================================================


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from common.tle import read_tle

    if len(sys.argv) < 2:
        print("Usage: python -m common.convert_tle <input.tle> [output.omm]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    with open(input_path, "r", encoding="utf-8") as fh:
        tle_data = read_tle(fh)

    omm_data = tle_to_omm(tle_data)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
        omm_data.to_file(output_path)
        print(f"Wrote OMM to: {output_path}")
    else:
        omm_data.to_file(sys.stdout)
