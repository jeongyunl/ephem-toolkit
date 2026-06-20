#!/usr/bin/env python3

import sys


def process_stream(stream, reverse=False):

    import numpy as np
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    import common.common as common
    import common.kepler as kepler

    for line in stream:
        try:
            parsed = common.parse_oem_state_line(line)
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

            input_keplerian = input_state_km
            input_keplerian[0] *= 1e3

            output_cartesian = kepler.keplerian_to_cartesian(
                input_keplerian,
                kepler.MU_EARTH,
            ).flatten()

            output_cartesian *= 1e-3

            print(epoch_dt.isoformat(), *output_cartesian, sep="  ")
        else:
            epoch_dt, input_state_km = parsed

            input_state_m = input_state_km * 1e3

            # Index Keplerian Element
            # 0 Semi-major axis (except if eccentricity = 1.0, then represents semi-latus rectum)
            # 1 Eccentricity
            # 2 Inclination
            # 3 Argument of periapsis
            # 4 Longitude of ascending node
            # 5 True anomaly

            output_keplerian = kepler.cartesian_to_keplerian(
                input_state_m,
                kepler.MU_EARTH,
            ).flatten()

            output_keplerian[0] *= 1e-3

            print(epoch_dt.isoformat(), *output_keplerian, sep="  ")


def print_usage():
    """Print the script usage message to standard output."""

    print(
        "Usage: python cartesian_to_keplerian.py [-h] [-r] [input_file]\n"
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
        "\n"
        "Input format (one record per line, 7 whitespace- or comma-separated fields):\n"
        "  <ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>\n"
        "\n"
        "Output format (one record per line):\n"
        "  <ISO-8601 epoch>  <a_km>  <e>  <i_rad>  <omega_rad>  <RAAN_rad>  <theta_rad>\n"
        "\n"
        "Keplerian elements are printed in the TudatPy convention:\n"
        "  a = semi-major axis (km, or semi-latus rectum if e = 1),\n"
        "  e = eccentricity,\n"
        "  i = inclination (rad),\n"
        "  omega = argument of periapsis (rad),\n"
        "  RAAN = longitude of ascending node (rad),\n"
        "  theta = true anomaly (rad).\n"
        "\n"
        "Blank lines and lines starting with '#' are skipped.\n"
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
