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
# tudatpy.interface.spice.get_angular_velocity_vector_of_frame_in_original_frame(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 1]]


def convert_frames_spice(base_frame, target_frame, input_epoch_et, input_state):
    """Convert a state vector from one SPICE frame to another.

    Uses SPICE rotation matrices and their time derivatives to build a
    6×6 state conversion matrix that correctly transforms both position
    and velocity (accounting for the rotating-frame transport term).

    Args:
        base_frame: Name of the source SPICE frame (e.g. ``"J2000"``).
        target_frame: Name of the destination SPICE frame (e.g. ``"ITRF93"``).
        input_epoch_et: Epoch in ephemeris time (TDB seconds since J2000).
        input_state: 6-element array-like ``[x, y, z, vx, vy, vz]`` in
            metres and m/s in the *base_frame*.

    Returns:
        numpy.ndarray: 6-element state vector ``[x, y, z, vx, vy, vz]``
            in metres and m/s in the *target_frame*.
    """
    # NOTE on inefficiency:
    # spice.compute_rotation_matrix_between_frames() and
    # spice.compute_rotation_matrix_derivative_between_frames() each end
    # up calling CSPICE sxform_c(), so the underlying C routine is
    # invoked twice.  This could be avoided by calling
    # tudat::spice_interface::computeStateRotationMatrixBetweenFrames(),
    # but tudatPy does not yet expose a Python binding for it.
    rotation_matrix = spice.compute_rotation_matrix_between_frames(
        base_frame, target_frame, input_epoch_et
    )
    rotation_matrix_derivative = spice.compute_rotation_matrix_derivative_between_frames(
        base_frame, target_frame, input_epoch_et
    )

    state_conversion_matrix = np.zeros((6, 6))
    state_conversion_matrix[0:3, 0:3] = rotation_matrix
    state_conversion_matrix[3:6, 0:3] = rotation_matrix_derivative
    state_conversion_matrix[3:6, 3:6] = rotation_matrix

    output_state = state_conversion_matrix @ np.asarray(input_state)

    return output_state


def process_stream(stream, reverse=False):
    """Read lines from *stream*, convert each state vector, and print results.

    Args:
        stream: An iterable of text lines (file object or sys.stdin).
        reverse: If True, convert ITRF93 → J2000 instead of J2000 → ITRF93.
    """

    load_spice_kernels()

    if reverse:
        base_frame, target_frame = "ITRF93", "J2000"
    else:
        base_frame, target_frame = "J2000", "ITRF93"

    for line in stream:
        try:
            parsed = parse_line(line)
        except Exception as exc:
            print(f"Skipping line (parse error): {line.strip()} -- {exc}")
            continue
        if parsed is None:
            continue

        epoch_dt, input_position_m, input_velocity_m_s = parsed
        epoch_tdb = datetime_to_tdb(epoch_dt)

        input_state = np.array(input_position_m + input_velocity_m_s)
        output_state = convert_frames_spice(base_frame, target_frame, epoch_tdb, input_state)

        output_position_km = output_state[0:3] / 1000.0
        output_velocity_km_s = output_state[3:6] / 1000.0

        print(epoch_dt.isoformat(), *output_position_km, *output_velocity_km_s, sep="  ")


def print_usage():
    """Print the script usage message to standard output."""
    print(
        "Usage: python gcrf_to_itrf_spice.py [-h] [-r] [input_file]\n"
        "\n"
        "Convert satellite state vectors between GCRF (J2000) and ITRF\n"
        "(ITRF93) using SPICE rotation matrices.\n"
        "\n"
        "Positional arguments:\n"
        "  input_file    Path to an OEM-style ephemeris file. If omitted,\n"
        "                lines are read from stdin.\n"
        "\n"
        "Options:\n"
        "  -h, --help    Show this help message and exit.\n"
        "  -r            Reverse conversion (ITRF93 to J2000 instead of\n"
        "                J2000 to ITRF93).\n"
        "\n"
        "Input format (one record per line, 7 whitespace- or comma-separated fields):\n"
        "  <ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>\n"
        "\n"
        "Blank lines and lines starting with '#' are skipped."
    )


if __name__ == "__main__":
    # Check for -h/--help and -r options
    set_reverse_conversion = False
    args = sys.argv[1:]

    if "-h" in args or "--help" in args:
        print_usage()
        sys.exit(0)

    if args and args[0] == "-r":
        set_reverse_conversion = True
        args = args[1:]

    if args:
        infile = args[0]
        with open(infile, "r") as f:
            process_stream(f, reverse=set_reverse_conversion)
    else:
        process_stream(sys.stdin, reverse=set_reverse_conversion)
