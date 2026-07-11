#!/usr/bin/env python3
"""Convert satellite state vectors between GCRF (J2000) and ITRF (ITRF93) using SPICE.

Provides :func:`convert_frames_spice` to transform a 6-element state vector
between any two SPICE frames, and :func:`process_stream` to apply the
conversion to a stream of OEM-style state lines.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import numpy as np
from tudatpy.interface import spice

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.oem as oem
import common.time_utils as time_utils


def load_spice_kernels() -> None:
    """Load required SPICE kernels for time conversion and Earth orientation."""

    spice_kernel_files: list[str] = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "earth_200101_990825_predict.bpc",  # Earth rotation prediction. Covers Jan, 2001 to Aug, 2099
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(common.get_spice_kernel_path() + "/" + kernel_file)


def convert_frames_spice(
    base_frame: str,
    target_frame: str,
    input_epoch_et_s: float,
    input_state_m: np.ndarray,
) -> np.ndarray:
    """Convert a state vector from one SPICE frame to another.

    Uses SPICE rotation matrices and their time derivatives to build a
    6×6 state conversion matrix that correctly transforms both position
    and velocity (accounting for the rotating-frame transport term).

    Parameters
    ----------
    base_frame : str
        Name of the source SPICE frame (e.g. ``"J2000"``).
    target_frame : str
        Name of the destination SPICE frame (e.g. ``"ITRF93"``).
    input_epoch_et_s : float
        Epoch in ephemeris time (TDB seconds since J2000).
    input_state_m : array-like, shape (6,)
        State vector ``[x, y, z, vx, vy, vz]`` in metres and m/s in
        *base_frame*.

    Returns
    -------
    np.ndarray
        6-element state vector ``[x, y, z, vx, vy, vz]`` in metres and
        m/s in *target_frame*.
    """
    # NOTE on inefficiency:
    # spice.compute_rotation_matrix_between_frames() and
    # spice.compute_rotation_matrix_derivative_between_frames() each end
    # up calling CSPICE sxform_c(), so the underlying C routine is
    # invoked twice.  This could be avoided by calling
    # tudat::spice_interface::computeStateRotationMatrixBetweenFrames(),
    # but tudatPy does not yet expose a Python binding for it.
    rotation_matrix: np.ndarray = spice.compute_rotation_matrix_between_frames(
        base_frame, target_frame, input_epoch_et_s
    )
    rotation_matrix_derivative: np.ndarray = (
        spice.compute_rotation_matrix_derivative_between_frames(
            base_frame, target_frame, input_epoch_et_s
        )
    )

    state_conversion_matrix: np.ndarray = np.zeros((6, 6))
    state_conversion_matrix[0:3, 0:3] = rotation_matrix
    state_conversion_matrix[3:6, 0:3] = rotation_matrix_derivative
    state_conversion_matrix[3:6, 3:6] = rotation_matrix

    output_state_m: np.ndarray = state_conversion_matrix @ np.asarray(input_state_m)

    return output_state_m


def process_stream(stream: TextIO, reverse: bool = False) -> None:
    """Read lines from *stream*, convert each state vector, and print results.

    Parameters
    ----------
    stream : TextIO
        An iterable of text lines (file object or sys.stdin).
    reverse : bool
        If True, convert ITRF93 → J2000 instead of J2000 → ITRF93.
    """

    load_spice_kernels()

    if reverse:
        base_frame: str = "ITRF93"
        target_frame: str = "J2000"
    else:
        base_frame = "J2000"
        target_frame = "ITRF93"

    for line in stream:
        try:
            parsed: tuple | None = oem.parse_oem_state_line(line)
        except Exception as exc:
            print(f"Skipping line (parse error): {line.strip()} -- {exc}")
            continue
        if parsed is None:
            continue

        epoch_dt, input_state_km = parsed
        epoch_tdb_s: float = time_utils.datetime_to_tdb(epoch_dt)

        input_state_m: np.ndarray = input_state_km * 1e3
        output_state_m: np.ndarray = convert_frames_spice(
            base_frame, target_frame, epoch_tdb_s, input_state_m
        )

        output_position_km: np.ndarray = output_state_m[0:3] / 1e3
        output_velocity_km_s: np.ndarray = output_state_m[3:6] / 1e3

        print(
            time_utils.datetime_to_iso8601(epoch_dt),
            *output_position_km,
            sep="  ",
            end="",
        )
        print("  ", *output_velocity_km_s, sep="  ")


def print_usage() -> None:
    """Print the script usage message to standard output.

    Displays usage information for the gcrf_to_itrf_spice CLI tool,
    including positional arguments, options, and input/output formats.
    """
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
    set_reverse_conversion: bool = False
    args: list[str] = sys.argv[1:]

    if "-h" in args or "--help" in args:
        print_usage()
        sys.exit(0)

    if args and args[0] == "-r":
        set_reverse_conversion = True
        args = args[1:]

    if args:
        infile: str = args[0]
        with open(infile, "r") as f:
            process_stream(f, reverse=set_reverse_conversion)
    else:
        process_stream(sys.stdin, reverse=set_reverse_conversion)
