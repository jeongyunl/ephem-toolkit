#!/usr/bin/env python3

from datetime import datetime
import sys

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

import numpy as np
from tudatpy.interface import spice
from tudatpy import data
from tudatpy.astro import time_representation
from tudatpy.astro.time_representation import TimeScales

tudat_time_scale_converter = time_representation.default_time_scale_converter()
UTC_J2000_DATETIME = datetime(2000, 1, 1, 12, 0, 0)


def load_spice_kernels():
    """Load required SPICE kernels for time conversion and Earth orientation."""

    spice_kernel_files = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "earth_200101_990825_predict.bpc",  # Earth rotation prediction. Covers Jan, 2001 to Aug, 2099
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(data.get_spice_kernel_path() + "/" + kernel_file)


def parse_line(line: str):
    """Parse a single line of OEM-style data.

    Accepts whitespace or comma separated values.

    Returns
    -------
    tuple | None
        ``(epoch, position_m, velocity_m_s)`` where *position_m* and
        *velocity_m_s* are 3-element lists in SI units, or ``None`` for
        blank / comment lines.
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
    position_km = vals[:3]
    velocity_km_s = vals[3:]

    # Convert km / km·s⁻¹ → m / m·s⁻¹
    position_m = [c * 1e3 for c in position_km]
    velocity_m_s = [c * 1e3 for c in velocity_km_s]

    return epoch_dt, position_m, velocity_m_s


def datetime_to_tdb(dt: datetime):
    utc_j2000 = (dt - UTC_J2000_DATETIME).total_seconds()
    return tudat_time_scale_converter.convert_time(
        input_value=utc_j2000,
        input_scale=TimeScales.utc_scale,
        output_scale=TimeScales.tdb_scale,
    )


# tudatpy.interface.spice.compute_rotation_matrix_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]
# tudatpy.interface.spice.compute_rotation_quaternion_and_rotation_matrix_derivative_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → tuple[Eigen::Quaternion<double, 0>, numpy.ndarray[numpy.float64[3, 3]]]
# tudatpy.interface.spice.compute_rotation_matrix_derivative_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]
# tudatpy.interface.spice.compute_rotation_quaternion_and_rotation_matrix_derivative_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → tuple[Eigen::Quaternion<double, 0>, numpy.ndarray[numpy.float64[3, 3]]]
# tudatpy.interface.spice.get_angular_velocity_vector_of_frame_in_original_frame(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 1]]


def gcrf_to_itrf_spice(input_epoch_et, input_gcrf_position_m, input_gcrf_velocity_m_s=None):
    # NOTE on inefficiency of this function
    # spice.compute_rotation_matrix_between_frames() calls tudat::spice_interface::computeRotationMatrixBetweenFrames(),
    # which calls CSPICE sxform_c(), and
    # spice.compute_rotation_matrix_derivative_between_frames() also ends up calling CSPICE sxform_c()
    # Thus CSPICE sxform_c() is called twice
    # This can be avoided by calling tudat::spice_interface::computeStateRotationMatrixBetweenFrames()
    # However, tudatPy currently does not have a python binding for that function (yet?)
    j2000_to_itrf93_matrix = spice.compute_rotation_matrix_between_frames(
        "J2000", "ITRF93", input_epoch_et
    )
    j2000_to_itrf93_matrix_derivative = spice.compute_rotation_matrix_derivative_between_frames(
        "J2000", "ITRF93", input_epoch_et
    )

    state_conversion_matrix = np.zeros((6, 6))
    state_conversion_matrix[0:3, 0:3] = j2000_to_itrf93_matrix
    state_conversion_matrix[3:6, 0:3] = j2000_to_itrf93_matrix_derivative
    state_conversion_matrix[3:6, 3:6] = j2000_to_itrf93_matrix

    gcrf_state = np.zeros((6))
    gcrf_state[0:3] = input_gcrf_position_m
    gcrf_state[3:6] = input_gcrf_velocity_m_s

    itrf_state = state_conversion_matrix @ gcrf_state

    return itrf_state[0:3], itrf_state[3:6]


def process_stream(stream):
    """Read lines from *stream* and print Keplerian elements for each epoch."""

    load_spice_kernels()

    for line in stream:
        try:
            parsed = parse_line(line)
        except Exception as exc:
            print(f"Skipping line (parse error): {line.strip()} -- {exc}")
            continue
        if parsed is None:
            continue

        epoch_dt, position_gcrf_m, velocity_gcrf_m_s = parsed
        epoch_tdb = datetime_to_tdb(epoch_dt)

        position_itrf_m, velocity_itrf_m_s = gcrf_to_itrf_spice(
            epoch_tdb, position_gcrf_m, velocity_gcrf_m_s
        )
        position_itrf_km = position_itrf_m / 1000.0
        velocity_itrf_km_s = velocity_itrf_m_s / 1000.0

        print(epoch_dt.isoformat(), *position_itrf_km, *velocity_itrf_km_s, sep="  ")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        infile = sys.argv[1]
        with open(infile, "r") as f:
            process_stream(f)
    else:
        process_stream(sys.stdin)
