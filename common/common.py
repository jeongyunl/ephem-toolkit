"""Common utilities shared by frame-conversion scripts."""

from datetime import datetime

import numpy as np
from tudatpy.astro import time_representation
from tudatpy.astro.time_representation import TimeScales

_tudat_time_scale_converter = time_representation.default_time_scale_converter()
_UTC_J2000_DATETIME = datetime(2000, 1, 1, 12, 0, 0)


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


