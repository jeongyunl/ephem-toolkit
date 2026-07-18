"""Convert between TLE and OMM representations, and TLE to osculating Keplerian elements.

Provides :func:`tle_to_omm` and :func:`omm_to_tle` for round-trip conversion
between :class:`~common.tle.Tle` and :class:`~common.omm.CcsdsOmm`, and
:func:`tle_to_osculating_keplerian` to extract osculating Keplerian elements
from a TLE at its reference epoch.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

import numpy as np

import common.kepler as kepler
import common.mean_kepler as mean_kepler
import common.omm as omm
import common.tle as tle
import common.consts as consts

# ===================================================================
# Internal helpers
# ===================================================================


def _tle_exponential_to_float(tle_exp: str) -> float:
    """Convert TLE exponential notation to a float.

    TLE exponential format: ``[sign]#####[+|-]#``
    Examples: ``"17978-3"`` -> 0.17978e-3, ``" 00000+0"`` -> 0.0,
    ``"-12345-6"`` -> -0.12345e-6.

    Parameters
    ----------
    tle_exp : str
        The TLE exponential field (7 or 8 characters).

    Returns
    -------
    float
        The numeric value.
    """
    value: str = tle_exp.strip()
    if not value or value == "00000+0" or value == "00000-0":
        return 0.0

    # Normalize to 8 chars with leading space if needed
    if len(value) == 7:
        value = " " + value

    # Parse sign
    sign_char: str = value[0]
    sign: float = -1.0 if sign_char == "-" else 1.0

    # Mantissa digits (5 digits)
    mantissa_str: str = value[1:6]

    # Exponent sign and digit
    exp_sign_char: str = value[6]
    exp_digit: str = value[7]

    exponent: int = -int(exp_digit) if exp_sign_char == "-" else int(exp_digit)

    # The mantissa is an assumed decimal: ##### -> 0.#####
    mantissa: float = int(mantissa_str) * 1e-5

    return sign * mantissa * (10.0**exponent)


def _float_to_tle_exponential(value: float) -> str:
    """Convert a float to TLE exponential notation (7 chars).

    Produces the compact 7-character form used in TLE fields,
    e.g. ``"17978-3"`` or ``"00000+0"``.

    For negative values, returns 8-char form with leading minus,
    e.g. ``"-12345-6"``.

    Parameters
    ----------
    value : float
        The numeric value to convert.

    Returns
    -------
    str
        TLE exponential string.
    """
    if value == 0.0:
        return "00000+0"

    sign: float = -1.0 if value < 0 else 1.0
    magnitude: float = abs(value)

    # Find exponent such that mantissa is 0.##### x 10^exp
    # i.e., 0.1 <= mantissa < 1.0
    exp: int = math.floor(math.log10(magnitude)) + 1
    mantissa: float = magnitude / (10.0**exp)

    # Round mantissa to 5 digits
    mantissa_int: int = int(round(mantissa * 1e5))

    # Handle rounding overflow
    if mantissa_int >= 100000:
        mantissa_int = 10000
        exp += 1

    # Format exponent
    if exp >= 0:
        exp_str: str = f"+{exp}"
    else:
        exp_str = f"-{abs(exp)}"

    unsigned_result: str = f"{mantissa_int:05d}{exp_str}"

    if sign < 0:
        return f"-{unsigned_result}"
    return unsigned_result


def _float_to_omm_scientific(value: float) -> str:
    """Convert a float to OMM scientific notation string.

    OMM uses a format like ``.1797805E-3`` or ``0`` for zero values.

    Parameters
    ----------
    value : float
        The numeric value to convert.

    Returns
    -------
    str
        OMM-style scientific notation string.
    """
    if value == 0.0:
        return "0"

    sign: str = ""
    if value < 0:
        sign = "-"
        value = abs(value)

    # Find exponent such that value = mantissa x 10^exp with 0.1 <= mantissa < 1.0
    exp: int = math.floor(math.log10(value)) + 1
    mantissa: float = value / (10.0**exp)

    # Format mantissa with enough significant digits (7 digits after decimal)
    # Remove trailing zeros
    mantissa_str: str = f"{mantissa:.7f}".rstrip("0").rstrip(".")

    # Remove leading "0" -> ".xxxxx"
    if mantissa_str.startswith("0."):
        mantissa_str = mantissa_str[1:]

    return f"{sign}{mantissa_str}E{exp:+d}" if exp != 0 else f"{sign}{mantissa_str}"


def _omm_scientific_to_float(omm_str: str) -> float:
    """Convert OMM scientific notation string to float.

    Handles formats like ``.1797805E-3``, ``-.25E-6``, ``0``.

    Parameters
    ----------
    omm_str : str
        OMM-style scientific notation string.

    Returns
    -------
    float
        The numeric value.
    """
    s: str = omm_str.strip()
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
    int_designator_year: int,
    int_designator_launch_number: int,
    int_designator_piece: str,
) -> str:
    """Build COSPAR Object ID from TLE international designator components.

    Parameters
    ----------
    int_designator_year : int
        2-digit year from TLE international designator.
    int_designator_launch_number : int
        Launch number within the year.
    int_designator_piece : str
        Piece identifier (e.g. "A", "B").

    Returns
    -------
    str
        COSPAR ID in format ``"YYYY-NNNP"`` (e.g. ``"1998-067A"``).
    """
    # Resolve 2-digit year
    if int_designator_year >= 57:
        full_year: int = 1900 + int_designator_year
    else:
        full_year = 2000 + int_designator_year

    piece: str = int_designator_piece.strip() if int_designator_piece else ""
    return f"{full_year}-{int_designator_launch_number:03d}{piece}"


def _parse_object_id(object_id: str) -> tuple[int, int, str]:
    """Parse COSPAR Object ID into TLE international designator components.

    Parameters
    ----------
    object_id : str
        COSPAR ID in format ``"YYYY-NNNP"`` (e.g. ``"1998-067A"``).

    Returns
    -------
    tuple[int, int, str]
        ``(int_designator_year, int_designator_launch_number, int_designator_piece)``
        where year is 2-digit.
    """
    match: re.Match[str] | None = re.match(r"(\d{4})-(\d{3})(\w*)", object_id.strip())
    if not match:
        return 0, 0, ""

    full_year: int = int(match.group(1))
    launch_number: int = int(match.group(2))
    piece: str = match.group(3)

    if full_year >= 2000:
        year_2digit: int = full_year - 2000
    else:
        year_2digit = full_year - 1900

    return year_2digit, launch_number, piece


# ===================================================================
# TLE -> OMM conversion
# ===================================================================


def tle_to_omm(
    tle_obj: tle.Tle, *, creation_date: str = "", originator: str = ""
) -> omm.CcsdsOmm:
    """Convert a :class:`~common.tle.Tle` to a :class:`~common.omm.CcsdsOmm`.

    Parameters
    ----------
    tle_obj : tle.Tle
        Parsed TLE dataclass instance.
    creation_date : str
        Optional creation date for the OMM header.
    originator : str
        Optional originator for the OMM header.

    Returns
    -------
    omm.CcsdsOmm
        The equivalent OMM representation.
    """
    # Convert epoch
    epoch_iso: str = tle.tle_epoch_to_iso8601(tle_obj.epoch_year, tle_obj.epoch_day)

    # Convert BSTAR from TLE exponential to OMM scientific
    bstar_float: float = _tle_exponential_to_float(tle_obj.bstar)
    bstar_omm: str = _float_to_omm_scientific(bstar_float)

    # Convert mean motion first derivative to OMM scientific
    mean_motion_dot_omm: str = _float_to_omm_scientific(
        tle_obj.mean_motion_first_derivative
    )

    # Convert mean motion second derivative from TLE exponential to OMM scientific
    mean_motion_ddot_float: float = _tle_exponential_to_float(
        tle_obj.mean_motion_second_derivative
    )
    mean_motion_ddot_omm: str = _float_to_omm_scientific(mean_motion_ddot_float)

    # Build COSPAR Object ID
    object_id: str = _build_object_id(
        tle_obj.int_designator_year,
        tle_obj.int_designator_launch_number,
        tle_obj.int_designator_piece,
    )

    return omm.CcsdsOmm(
        version=2.0,
        creation_date=creation_date,
        originator=originator,
        comments=[],
        object_name=tle_obj.name,
        object_id=object_id,
        center_name="EARTH",
        ref_frame="TEME",
        time_system="UTC",
        mean_element_theory="SGP/SGP4",
        epoch=epoch_iso,
        mean_motion=tle_obj.mean_motion_rev_per_day,
        eccentricity=tle_obj.eccentricity,
        inclination=tle_obj.inclination_deg,
        ra_of_asc_node=tle_obj.raan_deg,
        arg_of_pericenter=tle_obj.arg_perigee_deg,
        mean_anomaly=tle_obj.mean_anomaly_deg,
        tle_parameters=omm.TleParameters(
            ephemeris_type=tle_obj.ephemeris_type,
            classification_type=tle_obj.classification,
            norad_cat_id=tle_obj.satellite_number,
            element_set_no=tle_obj.element_set_number,
            rev_at_epoch=tle_obj.revolution_number_at_epoch,
            bstar=bstar_omm,
            mean_motion_dot=mean_motion_dot_omm,
            mean_motion_ddot=mean_motion_ddot_omm,
        ),
    )


# ===================================================================
# OMM -> TLE conversion
# ===================================================================


def omm_to_tle(omm_obj: omm.CcsdsOmm) -> tle.Tle:
    """Convert a :class:`~common.omm.CcsdsOmm` to a :class:`~common.tle.Tle`.

    Parameters
    ----------
    omm_obj : omm.CcsdsOmm
        Parsed OMM dataclass instance.

    Returns
    -------
    tle.Tle
        The equivalent TLE representation.

    Notes
    -----
    The returned :class:`tle.Tle` will have empty ``line1`` and ``line2`` fields.
    Use :func:`~common.tle.write_tle` to generate the formatted TLE lines.
    """
    # Ensure TLE parameters are present
    if omm_obj.tle_parameters is None:
        raise ValueError("OMM object must have TLE parameters to convert to TLE")

    tle_params = omm_obj.tle_parameters

    # Convert epoch
    epoch_year: int
    epoch_day: float
    epoch_year, epoch_day = tle.iso8601_to_tle_epoch(omm_obj.epoch)

    # Convert BSTAR from OMM scientific to TLE exponential
    bstar_float: float = _omm_scientific_to_float(tle_params.bstar)
    bstar_tle: str = _float_to_tle_exponential(bstar_float)

    # Convert mean motion dot from OMM scientific to float
    mean_motion_dot_float: float = _omm_scientific_to_float(tle_params.mean_motion_dot)

    # Convert mean motion ddot from OMM scientific to TLE exponential
    mean_motion_ddot_float: float = _omm_scientific_to_float(
        tle_params.mean_motion_ddot
    )
    mean_motion_ddot_tle: str = _float_to_tle_exponential(mean_motion_ddot_float)

    # Parse Object ID into international designator components
    int_year: int
    int_launch: int
    int_piece: str
    int_year, int_launch, int_piece = _parse_object_id(omm_obj.object_id)

    # Eccentricity raw: 7-digit integer representation
    eccentricity_raw: str = f"{int(round(omm_obj.eccentricity * 1e7)):07d}"

    return tle.Tle(
        name=omm_obj.object_name,
        line1="",
        line2="",
        satellite_number=tle_params.norad_cat_id,
        classification=tle_params.classification_type,
        int_designator_year=int_year,
        int_designator_launch_number=int_launch,
        int_designator_piece=int_piece,
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        mean_motion_first_derivative=mean_motion_dot_float,
        mean_motion_second_derivative=mean_motion_ddot_tle,
        bstar=bstar_tle,
        ephemeris_type=tle_params.ephemeris_type,
        element_set_number=tle_params.element_set_no,
        inclination_deg=omm_obj.inclination,
        raan_deg=omm_obj.ra_of_asc_node,
        eccentricity_raw=eccentricity_raw,
        eccentricity=omm_obj.eccentricity,
        arg_perigee_deg=omm_obj.arg_of_pericenter,
        mean_anomaly_deg=omm_obj.mean_anomaly,
        mean_motion_rev_per_day=omm_obj.mean_motion,
        revolution_number_at_epoch=tle_params.rev_at_epoch,
        line1_checksum="",
        line1_checksum_expected="",
        line2_checksum="",
        line2_checksum_expected="",
    )


# ===================================================================
# TLE -> osculating Keplerian conversion
# ===================================================================


def tle_to_osculating_keplerian(
    tle_obj: tle.Tle,
    mu_m3_s2: float = consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    apply_j2: bool = True,
) -> np.ndarray:
    """Extract osculating Keplerian elements at the TLE epoch.

    Converts the TLE mean elements to osculating elements. When *apply_j2*
    is True (default), applies Brouwer first-order J2 short-period
    corrections to approximate the osculating state. When False, uses
    simple two-body mechanics (Kepler's equation for true anomaly,
    Kepler's third law for semi-major axis).

    Parameters
    ----------
    tle_obj : tle.Tle
        Parsed TLE dataclass (from common.tle.read_tle).
    mu_m3_s2 : float
        Gravitational parameter (m³/s²).
    apply_j2 : bool
        If True, apply Brouwer J2 short-period corrections to convert
        mean elements to osculating. If False, use simple two-body
        conversion (backward-compatible behavior).

    Returns
    -------
    np.ndarray, shape (6,)
        Osculating Keplerian elements [semi_major_axis_m, eccentricity,
        inclination_rad, raan_rad, arg_periapsis_rad, true_anomaly_rad].

    References
    ----------
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications"
    Brouwer, D. "Solution of the Problem of Artificial Satellite Theory
    Without Drag", Astronomical Journal, 64, 1959.
    """
    # Extract mean elements from TLE
    mean_eccentricity: float = tle_obj.eccentricity
    inclination_deg: float = tle_obj.inclination_deg
    raan_deg: float = tle_obj.raan_deg
    argument_of_perigee_deg: float = tle_obj.arg_perigee_deg
    mean_anomaly_deg: float = tle_obj.mean_anomaly_deg
    mean_motion_rev_per_day: float = tle_obj.mean_motion_rev_per_day

    # Convert to radians
    inclination_rad: float = np.radians(inclination_deg)
    raan_rad: float = np.radians(raan_deg)
    argument_of_perigee_rad: float = np.radians(argument_of_perigee_deg)
    mean_anomaly_rad: float = np.radians(mean_anomaly_deg)

    # Semi-major axis from mean motion (Kepler's third law)
    semi_major_axis_m: float = kepler.mean_motion_to_semi_major_axis(
        mean_motion_rev_per_day, mu_m3_s2
    )

    if apply_j2:
        # Apply Brouwer J2 short-period corrections
        osc: np.ndarray = mean_kepler.compute_brouwer_short_period_corrections(
            np.array(
                [
                    semi_major_axis_m,
                    mean_eccentricity,
                    inclination_rad,
                    argument_of_perigee_rad,
                    raan_rad,
                    mean_anomaly_rad,
                ],
                dtype=float,
            )
        )
        return osc
    else:
        # Simple two-body conversion (legacy behavior)
        true_anomaly_rad: float = kepler.mean_to_true_anomaly(
            mean_anomaly_rad, mean_eccentricity
        )
        return np.array(
            [
                semi_major_axis_m,
                mean_eccentricity,
                inclination_rad,
                argument_of_perigee_rad,
                raan_rad,
                true_anomaly_rad,
            ],
            dtype=float,
        )
