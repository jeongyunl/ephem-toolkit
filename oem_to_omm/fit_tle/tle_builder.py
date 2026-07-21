"""TLE building and formatting utilities."""

from __future__ import annotations

import argparse
import io
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.tle as tle
from . import models


def format_tle_exponential_from_float(value: float) -> str:
    """Convert float to 7-char compact TLE exponential, no leading sign space.

    Parameters
    ----------
    value : float
        Value to convert.

    Returns
    -------
    str
        7-character TLE exponential format string.
    """
    if value == 0.0:
        return "00000+0"

    sign: str = "-" if value < 0.0 else ""
    abs_value: float = abs(value)

    exponent: int = int(math.floor(math.log10(abs_value)))
    mantissa: float = abs_value / (10.0**exponent)
    mantissa_digits: int = int(round(mantissa * 1e4))

    if mantissa_digits >= 100000:
        mantissa_digits = 10000
        exponent += 1

    tle_exponent: int = exponent + 1
    if tle_exponent < -9 or tle_exponent > 9:
        return "00000+0"

    exp_sign: str = "+" if tle_exponent >= 0 else "-"
    return f"{sign}{mantissa_digits:05d}{exp_sign}{abs(tle_exponent)}"


def sanitize_piece(piece: str) -> str:
    """Sanitize international designator piece string.

    Parameters
    ----------
    piece : str
        Piece identifier string.

    Returns
    -------
    str
        Sanitized piece identifier (max 3 alphanumeric characters).
    """
    letters_digits = "".join(ch for ch in piece.upper() if ch.isalnum())
    if not letters_digits:
        return "A"
    return letters_digits[:3]


def build_tle_data(args: argparse.Namespace, estimated: models.Estimated) -> tle.Tle:
    """Build a TLE dataclass from arguments and estimated elements.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    estimated : Estimated
        Estimated TLE elements dataclass.

    Returns
    -------
    tle_module.Tle
        TLE dataclass instance.
    """
    return tle.Tle(
        name=args.name,
        norad_cat_id=args.norad_cat_id,
        classification=args.classification,
        int_designator_year=args.int_designator_year,
        int_designator_launch_number=args.int_designator_launch_number,
        int_designator_piece=sanitize_piece(args.int_designator_piece),
        epoch_year=estimated.epoch_year,
        epoch_day=estimated.epoch_day,
        mean_motion_first_derivative=estimated.mean_motion_first_derivative,
        mean_motion_second_derivative=args.mean_motion_second_derivative,
        bstar=estimated.bstar if estimated.bstar is not None else args.bstar,
        ephemeris_type=args.ephemeris_type,
        element_set_number=args.element_set_number,
        inclination_deg=estimated.inclination_deg,
        raan_deg=estimated.raan_deg,
        eccentricity=estimated.eccentricity,
        arg_perigee_deg=estimated.arg_perigee_deg,
        mean_anomaly_deg=estimated.mean_anomaly_deg,
        mean_motion_rev_per_day=estimated.mean_motion_rev_per_day,
        revolution_number_at_epoch=args.revolution_number_at_epoch,
    )


def build_tle_lines(
    args: argparse.Namespace, estimated: models.Estimated
) -> tuple[str, str]:
    """Build TLE line1 and line2 strings from arguments and estimated elements.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    estimated : Estimated
        Estimated TLE elements dataclass.

    Returns
    -------
    tuple[str, str]
        TLE line1 and line2 strings.
    """
    buffer: io.StringIO = io.StringIO()
    line1: str
    line2: str
    line1, line2 = tle.write_tle(buffer, build_tle_data(args, estimated))
    return line1, line2
