"""Common utilities shared by frame-conversion scripts."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import os
import re
from pathlib import Path

import numpy as np
from tudatpy.astro import time_representation
from tudatpy.astro.time_representation import TimeScales

_tudat_time_scale_converter = time_representation.default_time_scale_converter()
_UTC_J2000_DATETIME = datetime(2000, 1, 1, 12, 0, 0)
_SPICE_CACHE_FILE = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "tudatpy-utils"
    / "spice_kernel_path"
)


def parse_oem_state_line(line: str):
    """Parse a single line of OEM-style data.

    Accepts whitespace or comma separated values.

    Returns
    -------
    tuple | None
        ``(epoch_dt, position_km, velocity_km_s)`` where *position_km* and
        *velocity_km_s* are 3-element numpy arrays in km / km·s⁻¹,
        or ``None`` for blank / comment lines.
    """
    if not line.strip():
        return None
    if line.strip().startswith("#"):
        return None

    parts = [p for tok in line.strip().split() for p in tok.split(",")]
    if len(parts) < 7:
        raise ValueError(f"Line does not contain 7 fields: '{line}'")

    epoch_str = parts[0]
    if epoch_str.endswith("Z"):
        epoch_str = epoch_str[:-1]
    try:
        epoch_dt = datetime.fromisoformat(epoch_str)
    except Exception:
        epoch_dt = datetime.strptime(epoch_str, "%Y-%m-%dT%H:%M:%S")

    vals = [float(x) for x in parts[1:7]]
    position_km = np.array(vals[:3])
    velocity_km_s = np.array(vals[3:])

    return epoch_dt, position_km, velocity_km_s


def datetime_to_tdb(dt: datetime):
    """Convert a datetime object to TDB (ephemeris time) seconds since J2000."""
    utc_j2000_s = (dt - _UTC_J2000_DATETIME).total_seconds()
    return _tudat_time_scale_converter.convert_time(
        input_value=utc_j2000_s,
        input_scale=TimeScales.utc_scale,
        output_scale=TimeScales.tdb_scale,
    )


def tdb_to_datetime(tdb_s: float):
    """Convert TDB (ephemeris time) seconds since J2000 to a datetime object."""
    utc_j2000_s = _tudat_time_scale_converter.convert_time(
        input_value=tdb_s,
        input_scale=TimeScales.tdb_scale,
        output_scale=TimeScales.utc_scale,
    )
    return _UTC_J2000_DATETIME + timedelta(seconds=utc_j2000_s)


def get_spice_kernel_path() -> str:
    """Return the Tudatpy SPICE kernel path using an XDG-style cache file."""
    try:
        cached_path = _SPICE_CACHE_FILE.read_text(encoding="utf-8").strip()
        if cached_path and Path(cached_path).is_dir():
            return cached_path
    except OSError:
        pass

    from tudatpy import data

    resolved_path = data.get_spice_kernel_path()

    try:
        _SPICE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SPICE_CACHE_FILE.write_text(resolved_path, encoding="utf-8")
    except OSError:
        # Cache writes are best effort; continue with the resolved path.
        pass

    return resolved_path


# ===================================================================
# CLI duration / step-size parsing
# ===================================================================

SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86400.0


def parse_duration_to_seconds(value: str) -> float:
    """Parse a duration token and convert it to seconds.

    Parameters
    ----------
    value : str
        Duration token in ``<number>[s|m|h|d]`` format.

    Returns
    -------
    float
        Duration in seconds.

    Notes
    -----
    Accepted formats are ``<number>`` (seconds), ``<number>s``,
    ``<number>m``, ``<number>h``, and ``<number>d``.
    """
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([smhdSMHD]?)\s*", value)
    if not match:
        raise argparse.ArgumentTypeError(
            "duration must be a positive number optionally followed by s, m, h, or d"
        )

    magnitude = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) else "s"

    if unit == "s":
        duration_s = magnitude
    elif unit == "m":
        duration_s = magnitude * SECONDS_PER_MINUTE
    elif unit == "h":
        duration_s = magnitude * SECONDS_PER_HOUR
    elif unit == "d":
        duration_s = magnitude * SECONDS_PER_DAY
    else:
        raise argparse.ArgumentTypeError("duration unit must be one of: s, m, h, d")

    if duration_s <= 0.0:
        raise argparse.ArgumentTypeError("duration must be a positive value")

    return duration_s


def parse_step_to_seconds(value: str) -> float:
    """Parse output step-size token and convert it to seconds.

    Parameters
    ----------
    value : str
        Step-size token in ``<number>[s|m]`` format.

    Returns
    -------
    float
        Step size in seconds.

    Notes
    -----
    Accepted formats are ``<number>`` (seconds), ``<number>s``, and
    ``<number>m``.
    """
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([smSM]?)\s*", value)
    if not match:
        raise argparse.ArgumentTypeError(
            "step size must be a positive number optionally followed by s or m"
        )

    magnitude = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) else "s"

    if unit == "s":
        step_s = magnitude
    elif unit == "m":
        step_s = magnitude * SECONDS_PER_MINUTE
    else:
        raise argparse.ArgumentTypeError("step-size unit must be one of: s, m")

    if step_s <= 0.0:
        raise argparse.ArgumentTypeError("step size must be a positive value")

    return step_s
