#!/usr/bin/env python3
"""Convert ECEF OEM ephemeris data to AER (Azimuth-Elevation-Range) coordinates.

This utility reads CCSDS OEM files with ECEF reference frame and converts
position vectors to AER coordinates relative to a ground station specified
in geodetic coordinates (latitude, longitude, altitude).

Note: Only positions are converted. Velocities are not converted to AER rates.

Usage:
    python3 bin/ecef_to_aer.py <oem_file> --lat <lat> --lon <lon> --alt <alt>
    cat data.oem | python3 bin/ecef_to_aer.py - --lat <lat> --lon <lon> --alt <alt>
    cat data.oem | python3 bin/ecef_to_aer.py --lat <lat> --lon <lon> --alt <alt>

Examples:
    # Convert ISS orbit to AER from ground station
    python3 bin/ecef_to_aer.py iss.oem --lat 40.7128 --lon -74.0060 --alt 10.0

    # Read from stdin
    cat iss.oem | python3 bin/ecef_to_aer.py --lat 40.7128 --lon -74.0060 --alt 10.0

    # Latitude/longitude in degrees, altitude in meters
    python3 bin/ecef_to_aer.py data.oem --lat 51.5074 --lon -0.1278 --alt 0.0

Output format:
    Each line contains: timestamp azimuth elevation range
    - timestamp: ISO 8601 format (e.g., 2024-01-01T00:00:00.000000)
    - azimuth: Azimuth angle in degrees (0° = North, 90° = East)
    - elevation: Elevation angle in degrees (0° = horizon, 90° = zenith)
    - range: Distance in meters
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.aer as aer
import common.ccsds.oem as oem
import common.time_utils as time_utils


def main() -> None:
    """Parse CLI arguments, convert ECEF OEM to AER, and write results to stdout."""
    parser = argparse.ArgumentParser(
        description="Convert ECEF OEM ephemeris data to AER coordinates",
        epilog=(
            "Converts position vectors from ECEF to AER coordinates relative to a "
            "ground station. Velocities are not converted."
        ),
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        help='Path to input CCSDS OEM file in ECEF frame (use "-" or omit to read from stdin)',
    )
    parser.add_argument(
        "--lat",
        "--latitude",
        dest="lat_deg",
        type=float,
        required=True,
        metavar="<degrees>",
        help="Ground station latitude in degrees (positive = North, negative = South)",
    )
    parser.add_argument(
        "--lon",
        "--longitude",
        dest="lon_deg",
        type=float,
        required=True,
        metavar="<degrees>",
        help="Ground station longitude in degrees (positive = East, negative = West)",
    )
    parser.add_argument(
        "--alt",
        "--altitude",
        dest="alt_m",
        type=float,
        required=True,
        metavar="<meters>",
        help="Ground station altitude above WGS-84 ellipsoid in meters",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help="Output file path (default: '-'). Use '-' to print to stdout.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )

    args = parser.parse_args()

    # Determine if reading from stdin
    read_from_stdin = args.oem_file is None or args.oem_file == "-"

    # Read OEM data from stdin or file
    if read_from_stdin:
        oem_data = oem.CcsdsOem.read(sys.stdin)
        oem_file_path: str | Path = "<stdin>"
    else:
        oem_file_path = Path(args.oem_file)
        oem_data = oem.CcsdsOem.read(oem_file_path)

    # Validate reference frame
    ref_frame = oem_data.meta.ref_frame.upper()
    if "ECEF" not in ref_frame and "ITRF" not in ref_frame:
        print(
            f"Warning: Reference frame '{oem_data.meta.ref_frame}' may not be ECEF. "
            "Expected ECEF or ITRF variant.",
            file=sys.stderr,
        )

    # Convert ground station coordinates from degrees to radians
    lat_rad = np.deg2rad(args.lat_deg)
    lon_rad = np.deg2rad(args.lon_deg)
    reference_lla_rad_rad_m = np.array([lat_rad, lon_rad, args.alt_m])

    if args.verbose:
        total_states = len(oem_data.states)
        print(f"[ecef_to_aer] Input OEM:", file=sys.stderr)
        print(f"[ecef_to_aer]   File: {oem_file_path}", file=sys.stderr)
        print(f"[ecef_to_aer]   Object: {oem_data.meta.object_name}", file=sys.stderr)
        print(
            f"[ecef_to_aer]   Reference frame: {oem_data.meta.ref_frame}",
            file=sys.stderr,
        )
        print(f"[ecef_to_aer]   Center: {oem_data.meta.center_name}", file=sys.stderr)
        print(
            f"[ecef_to_aer]   Time system: {oem_data.meta.time_system}",
            file=sys.stderr,
        )
        print(f"[ecef_to_aer]   States: {total_states}", file=sys.stderr)

        if total_states > 0:
            first_ts, _ = oem_data.states[0]
            last_ts, _ = oem_data.states[-1]
            first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
            last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            span = last_dt - first_dt
            print(
                f"[ecef_to_aer]   Start: {time_utils.datetime_to_iso8601(first_dt)}",
                file=sys.stderr,
            )
            print(
                f"[ecef_to_aer]   End:   {time_utils.datetime_to_iso8601(last_dt)}",
                file=sys.stderr,
            )
            print(
                f"[ecef_to_aer]   Span:  {time_utils.format_duration_human(span)}",
                file=sys.stderr,
            )

        print(f"[ecef_to_aer] Ground station:", file=sys.stderr)
        print(f"[ecef_to_aer]   Latitude:  {args.lat_deg:>10.6f}°", file=sys.stderr)
        print(f"[ecef_to_aer]   Longitude: {args.lon_deg:>10.6f}°", file=sys.stderr)
        print(f"[ecef_to_aer]   Altitude:  {args.alt_m:>10.3f} m", file=sys.stderr)
        print(file=sys.stderr)

    # Determine output destination
    if args.output == "-":
        output_file = sys.stdout
    else:
        output_file = open(args.output, "w")

    try:
        # Convert each state to AER
        for timestamp, state_vector in oem_data.states:
            # Extract position (first 3 elements)
            ecef_position = state_vector[0:3]

            # Convert ECEF position to AER
            aer_position = aer.ecef_to_aer(ecef_position, reference_lla_rad_rad_m)

            # Convert to degrees for output
            azimuth_deg = np.rad2deg(aer_position[0])
            elevation_deg = np.rad2deg(aer_position[1])
            range_m = aer_position[2]

            # Format timestamp
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            timestamp_str = time_utils.datetime_to_iso8601(dt)

            # Write output
            output_file.write(
                f"{timestamp_str} {azimuth_deg:>12.6f} {elevation_deg:>12.6f} {range_m:>15.3f}\n"
            )

        if args.verbose:
            print(
                f"[ecef_to_aer] Converted {len(oem_data.states)} states to AER",
                file=sys.stderr,
            )

    finally:
        if args.output != "-":
            output_file.close()


if __name__ == "__main__":
    main()
