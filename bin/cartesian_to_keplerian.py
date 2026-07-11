#!/usr/bin/env python3
"""Convert satellite states between Cartesian and Keplerian elements.

Provides :func:`process_stream` to read OEM-style state lines and convert
each record between Cartesian and osculating (or mean) Keplerian elements,
and a :func:`main` CLI entry point.

References:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 4.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications", Algorithm 9.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

import numpy as np

import common.kepler as kepler
import common.mean_kepler as mean_kepler
import common.oem as oem
import common.common as common
import common.consts as consts
import common.time_utils as time_utils

# ===================================================================
# Main processing
# ===================================================================


def process_stream(stream: TextIO, reverse: bool = False, mean: bool = False) -> None:
    """Read OEM-style state lines from *stream* and print converted elements.

    Each non-blank, non-comment line is parsed as an OEM-style record
    ``<epoch> <x> <y> <z> <vx> <vy> <vz>`` (km and km/s in file, but parsed as m and m/s).
    By default the Cartesian state is converted to osculating Keplerian elements; with
    *reverse* the direction is inverted.

    Note: parse_oem_state_line() now returns state vectors in SI units (m, m/s).
    Output is converted to km for display.

    Parameters
    ----------
    stream : TextIO
        Readable text stream of OEM-style state lines.
    reverse : bool
        If True, convert Keplerian → Cartesian instead of Cartesian → Keplerian.
    mean : bool
        If True, convert the osculating Keplerian output to mean elements via
        Brouwer short-period inversion.  Only valid when *reverse* is False.
    """

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    for line in stream:
        if reverse:
            # For Keplerian to Cartesian, parse manually (not using parse_oem_state_line
            # because it's designed for Cartesian states and would incorrectly convert units)
            try:
                if not line.strip() or line.strip().startswith("#"):
                    continue
                
                parts: list[str] = [p for tok in line.strip().split() for p in tok.split(",")]
                if len(parts) < 7:
                    continue
                
                epoch_str: str = parts[0]
                epoch_dt = time_utils.iso8601_to_datetime(epoch_str)
                
                # Parse Keplerian elements (semi-major axis in km, angles in radians)
                input_keplerian_km: np.ndarray = np.array([float(x) for x in parts[1:7]])
                
                # Convert semi-major axis from km to m for internal calculation
                input_keplerian_m: np.ndarray = input_keplerian_km.copy()
                input_keplerian_m[0] *= 1e3

                output_cartesian_m: np.ndarray = kepler.keplerian_to_cartesian(
                    input_keplerian_m
                ).flatten()

                # Convert output from m to km for display
                output_cartesian_km: np.ndarray = output_cartesian_m * 1e-3

                print(time_utils.datetime_to_iso8601(epoch_dt), *output_cartesian_km, sep="  ")
            except Exception as exc:
                print(
                    f"Skipping line (parse error): {line.strip()} -- {exc}", file=sys.stderr
                )
                continue
        else:
            # For Cartesian to Keplerian, use parse_oem_state_line
            try:
                parsed: tuple[object, np.ndarray] | None = oem.parse_oem_state_line(line)
            except Exception as exc:
                print(
                    f"Skipping line (parse error): {line.strip()} -- {exc}", file=sys.stderr
                )
                continue
            if parsed is None:
                continue

            epoch_dt, input_state_m = parsed  # Now in meters (SI units)

            # Convert Cartesian to Keplerian
            # input_state_m is already in meters (SI units) from parse_oem_state_line()

            output_keplerian_m: np.ndarray = kepler.cartesian_to_keplerian(
                input_state_m,
                consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
            ).flatten()

            if mean:
                output_keplerian_m = mean_kepler.osculating_to_mean_keplerian(
                    output_keplerian_m
                )

            # Convert semi-major axis from m to km for display
            output_keplerian_km: np.ndarray = output_keplerian_m.copy()
            output_keplerian_km[0] *= 1e-3

            print(time_utils.datetime_to_iso8601(epoch_dt), *output_keplerian_km, sep="  ")


# ===================================================================
# CLI utilities
# ===================================================================


def print_usage() -> None:
    """Print the script usage message to standard output."""

    print(
        "Usage: python cartesian_to_keplerian.py [-h] [-r] [--mean] [input_file]\n"
        "\n"
        "Convert satellite states between Cartesian and Keplerian elements.\n"
        "\n"
        "Positional arguments:\n"
        "  input_file    Path to an OEM-style ephemeris file. If omitted,\n"
        "                lines are read from stdin.\n"
        "\n"
        "Options:\n"
        "  -h, --help    Show this help message and exit.\n"
        "  -r            Reverse conversion (Keplerian to Cartesian instead\n"
        "                of Cartesian to Keplerian).\n"
        "  --mean        Convert the resulting Keplerian elements to mean\n"
        "                Keplerian elements using Brouwer short-period\n"
        "                inversion. Only valid for Cartesian-to-Keplerian.\n"
        "\n"
        "Input format: (one record per line, 7 whitespace- or comma-separated fields)\n"
        "  <ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>\n"
        "\n"
        "Output format: (one record per line)\n"
        "  <ISO-8601 epoch>  <a_km>  <e>  <i_rad>  <omega_rad>  <RAAN_rad>  <theta_rad/M_rad>\n"
        "\n"
        "Keplerian elements are printed in the TudatPy convention:\n"
        "  a = semi-major axis (km, or semi-latus rectum if e = 1),\n"
        "  e = eccentricity,\n"
        "  i = inclination (rad),\n"
        "  omega = argument of periapsis (rad),\n"
        "  RAAN = longitude of ascending node (rad),\n"
        "  theta = true anomaly (rad) or M = mean anomaly (rad) when --mean is used.\n"
        "\n"
        "Blank lines and lines starting with '#' are skipped.\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for the cartesian_to_keplerian CLI.

    Parameters
    ----------
    argv : list[str] | None
        Arguments to parse. If None, uses sys.argv[1:].

    Returns
    -------
    int
        Exit code.
    """
    if argv is None:
        argv = sys.argv[1:]

    set_reverse_conversion: bool = False
    set_mean_keplerian: bool = False
    remaining_args: list[str] = list(argv)

    if "-h" in remaining_args or "--help" in remaining_args:
        print_usage()
        return 0

    while remaining_args and remaining_args[0].startswith("-"):
        flag: str = remaining_args[0]
        if flag == "-r":
            set_reverse_conversion = True
        elif flag == "--mean":
            set_mean_keplerian = True
        else:
            break
        remaining_args = remaining_args[1:]

    if set_reverse_conversion and set_mean_keplerian:
        print("Error: --mean cannot be used with -r/--reverse", file=sys.stderr)
        return 1

    if remaining_args:
        input_file_path: str = remaining_args[0]
        with open(input_file_path, "r") as f:
            process_stream(
                f,
                reverse=set_reverse_conversion,
                mean=set_mean_keplerian,
            )
    else:
        process_stream(
            sys.stdin,
            reverse=set_reverse_conversion,
            mean=set_mean_keplerian,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
