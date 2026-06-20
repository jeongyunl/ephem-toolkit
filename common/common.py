"""Common utilities shared by frame-conversion scripts."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
import re
from pathlib import Path

import numpy as np
from tudatpy.astro import time_representation
from tudatpy.astro.time_representation import TimeScales

_tudat_time_scale_converter = time_representation.default_time_scale_converter()
_UTC_J2000_DATETIME = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_SPICE_CACHE_FILE = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "tudatpy-utils"
    / "spice_kernel_path"
)


def parse_oem_state_line(line: str) -> tuple[datetime, np.ndarray] | None:
    """Parse a single line of OEM-style data.

    Accepts whitespace or comma separated values.

    Returns
    -------
    tuple | None
        ``(epoch_dt, state_km)`` where *state_km* is a 6-element numpy array
        ``[x, y, z, vx, vy, vz]`` in km / km·s⁻¹,
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

    if epoch_dt.tzinfo is None:
        epoch_dt = epoch_dt.replace(tzinfo=timezone.utc)
    else:
        epoch_dt = epoch_dt.astimezone(timezone.utc)

    vals = [float(x) for x in parts[1:7]]
    state_km = np.array(vals)

    return epoch_dt, state_km


def datetime_to_tdb(dt: datetime) -> float:
    """Convert a datetime object to TDB (ephemeris time) seconds since J2000."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    utc_j2000_s = (dt - _UTC_J2000_DATETIME).total_seconds()
    return _tudat_time_scale_converter.convert_time(
        input_value=utc_j2000_s,
        input_scale=TimeScales.utc_scale,
        output_scale=TimeScales.tdb_scale,
    )


def tdb_to_datetime(tdb_s: float) -> datetime:
    """Convert TDB (ephemeris time) seconds since J2000 to a UTC datetime object."""
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


def transform_to_rtn(
    state: np.ndarray, reference_state: np.ndarray | None = None
) -> np.ndarray:
    """Calculate relative position and velocity in the RTN frame.

    Computes the relative state vector between two objects and transforms to the RTN
    (Radial-Transverse-Normal) frame of the reference object using 6-element ECI
    state vectors [x, y, z, vx, vy, vz].

    Parameters
    ----------
    state : np.ndarray
        6-element state vector of the target object [x, y, z, vx, vy, vz].
    reference_state : np.ndarray | None
        6-element state vector of the reference object for RTN frame definition.
        Defaults to [0, 0, 0, 0, 0, 0] if None.

    Returns
    -------
    np.ndarray
        6-element relative state vector in RTN coordinates [r, t, n, vr, vt, vn].
    """
    if reference_state is None:
        reference_state = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    # 1. Unpack 6D vectors into 3D position and velocity sub-vectors
    reference_position, reference_velocity = reference_state[0:3], reference_state[3:6]
    target_position, target_velocity = state[0:3], state[3:6]

    # 2. Compute inertial differences
    inertial_position = target_position - reference_position
    inertial_velocity = target_velocity - reference_velocity

    # 3. Compute RTN unit basis vectors
    reference_position_magnitude = np.linalg.norm(reference_position)
    radial_unit_vector = reference_position / reference_position_magnitude

    angular_momentum_vector = np.cross(reference_position, reference_velocity)
    angular_momentum_magnitude = np.linalg.norm(angular_momentum_vector)
    normal_unit_vector = angular_momentum_vector / angular_momentum_magnitude

    transverse_unit_vector = np.cross(normal_unit_vector, radial_unit_vector)

    # 4. Assemble ECI to RTN rotation matrix
    rtn_transformation_matrix = np.vstack(
        [radial_unit_vector, transverse_unit_vector, normal_unit_vector]
    )

    # 5. Compute relative position vector in RTN
    rtn_position = rtn_transformation_matrix @ inertial_position

    # 6. Compute relative velocity vector in RTN (Transport Theorem)
    angular_velocity_z = angular_momentum_magnitude / (reference_position_magnitude**2)
    angular_velocity_rtn = np.array([0.0, 0.0, angular_velocity_z])

    rtn_velocity_rotational = rtn_transformation_matrix @ inertial_velocity
    rtn_velocity = rtn_velocity_rotational - np.cross(
        angular_velocity_rtn, rtn_position
    )

    # 7. Package back into a single 6-element relative state vector
    rtn_state = np.concatenate([rtn_position, rtn_velocity])

    return rtn_state
