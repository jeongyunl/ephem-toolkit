#!/usr/bin/env python3
"""Convert satellite states between Cartesian and Keplerian elements.

Provides :func:`process_stream` to read OEM-style state lines and convert
each record between Cartesian and osculating (or mean) Keplerian elements,
and a :func:`main` CLI entry point.
"""

from __future__ import annotations

import sys
from typing import TextIO


def process_stream(stream: TextIO, reverse: bool = False, mean: bool = False) -> None:
    """Read OEM-style state lines from *stream* and print converted elements.

    Each non-blank, non-comment line is parsed as an OEM-style record
    ``<epoch> <x> <y> <z> <vx> <vy> <vz>`` (km and km/s).  By default the
    Cartesian state is converted to osculating Keplerian elements; with
    *reverse* the direction is inverted.

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

    import numpy as np
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    import common.kepler as kepler
    import common.oem as oem
    import common.common as common

    for line in stream:
        try:
            parsed: tuple | None = oem.parse_oem_state_line(line)
        except Exception as exc:
            print(f"Skipping line (parse error): {line.strip()} -- {exc}")
            continue
        if parsed is None:
            continue

        # Index Keplerian Element
        # 0 Semi-major axis (except if eccentricity = 1.0, then represents semi-latus rectum)
        # 1 Eccentricity
        # 2 Inclination
        # 3 Argument of periapsis
        # 4 Longitude of ascending node
        # 5 True anomaly

        if reverse:
            epoch_dt, input_state_km = parsed

            input_keplerian: np.ndarray = input_state_km
            input_keplerian[0] *= 1e3

            output_cartesian: np.ndarray = kepler.keplerian_to_cartesian(
                input_keplerian,
                kepler.MU_EARTH,
            ).flatten()

            output_cartesian *= 1e-3

            print(common.datetime_to_iso8601(epoch_dt), *output_cartesian, sep="  ")
        else:
            epoch_dt, input_state_km = parsed

            input_state_m: np.ndarray = input_state_km * 1e3

            # Index Keplerian Element
            # 0 Semi-major axis (except if eccentricity = 1.0, then represents semi-latus rectum)
            # 1 Eccentricity
            # 2 Inclination
            # 3 Argument of periapsis
            # 4 Longitude of ascending node
            # 5 True anomaly / mean anomaly

            output_keplerian: np.ndarray = kepler.cartesian_to_keplerian(
                input_state_m,
                kepler.MU_EARTH,
            ).flatten()

            if mean:
                output_keplerian = kepler.osculating_to_mean_keplerian(output_keplerian)

            output_keplerian[0] *= 1e-3

            print(common.datetime_to_iso8601(epoch_dt), *output_keplerian, sep="  ")


def print_usage():
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
        "Input format (one record per line, 7 whitespace- or comma-separated fields):\n"
        "  <ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>\n"
        "\n"
        "Output format (one record per line):\n"
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
    args: list[str] = list(argv)

    if "-h" in args or "--help" in args:
        print_usage()
        return 0

    while args and args[0].startswith("-"):
        option: str = args[0]
        if option == "-r":
            set_reverse_conversion = True
        elif option == "--mean":
            set_mean_keplerian = True
        else:
            break
        args = args[1:]

    if set_reverse_conversion and set_mean_keplerian:
        print("Error: --mean cannot be used with -r/--reverse", file=sys.stderr)
        return 1

    if args:
        infile: str = args[0]
        with open(infile, "r") as f:
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
