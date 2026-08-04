#!/usr/bin/env python3
"""Transform OEM ephemeris files: change reference frames or convert to AER coordinates.

⚠️  WARNING: THIS SCRIPT IS NOT FULLY FUNCTIONAL YET ⚠️
This is a work in progress and may not produce correct results.

This utility can:
1. Output OEM files as-is (default when no options given)
2. Change the reference frame metadata (--ref-frame)
3. Convert ECEF positions to AER coordinates (--aer with lat,lon,alt)

Usage:
    # Output OEM file as-is
    python3 bin/xform_oem.py <oem_file>
    cat data.oem | python3 bin/xform_oem.py

    # Change reference frame
    python3 bin/xform_oem.py <oem_file> --ref-frame J2000

    # Convert to AER coordinates
    python3 bin/xform_oem.py <oem_file> --aer <lat>,<lon>,<alt>

Examples:
    # Output ISS OEM file as-is
    python3 bin/xform_oem.py iss.oem

    # Change reference frame to J2000
    python3 bin/xform_oem.py iss.oem --ref-frame J2000 -o output.oem

    # Convert ISS orbit to AER from ground station
    python3 bin/xform_oem.py iss.oem --aer 40.7128,-74.0060,10.0

    # Read from stdin and convert to AER
    cat iss.oem | python3 bin/xform_oem.py --aer 40.7128,-74.0060,10.0

AER Output format:
    Each line contains: timestamp azimuth elevation range
    - timestamp: ISO 8601 format (e.g., 2024-01-01T00:00:00.000000)
    - azimuth: Azimuth angle in degrees (0° = North, 90° = East)
    - elevation: Elevation angle in degrees (0° = horizon, 90° = zenith)
    - range: Distance in meters

Note: AER conversion only converts positions. Velocities are not converted to AER rates.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.aer as aer
import common.oem as oem
import common.time_utils as time_utils


def convert_to_aer(
    oem_data: oem.CcsdsOem,
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
    output_file,
    verbose: bool = False,
) -> None:
    """Convert OEM states to AER coordinates and write to output.

    Parameters
    ----------
    oem_data : oem.CcsdsOem
        Input OEM data with ECEF positions.
    lat_deg : float
        Ground station latitude in degrees.
    lon_deg : float
        Ground station longitude in degrees.
    alt_m : float
        Ground station altitude in meters.
    output_file : TextIO
        Output file handle.
    verbose : bool, optional
        Print verbose debug information.
    """
    # Validate reference frame
    ref_frame = oem_data.meta.ref_frame.upper()
    if "ECEF" not in ref_frame and "ITRF" not in ref_frame:
        print(
            f"Warning: Reference frame '{oem_data.meta.ref_frame}' may not be ECEF. "
            "Expected ECEF or ITRF variant.",
            file=sys.stderr,
        )

    # Convert ground station coordinates from degrees to radians
    lat_rad = np.deg2rad(lat_deg)
    lon_rad = np.deg2rad(lon_deg)
    reference_lla_rad_rad_m = np.array([lat_rad, lon_rad, alt_m])

    if verbose:
        print(f"[xform_oem] Ground station:", file=sys.stderr)
        print(f"[xform_oem]   Latitude:  {lat_deg:>10.6f}°", file=sys.stderr)
        print(f"[xform_oem]   Longitude: {lon_deg:>10.6f}°", file=sys.stderr)
        print(f"[xform_oem]   Altitude:  {alt_m:>10.3f} m", file=sys.stderr)
        print(file=sys.stderr)

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

    if verbose:
        print(
            f"[xform_oem] Converted {len(oem_data.states)} states to AER",
            file=sys.stderr,
        )


def convert_ref_frame(
    oem_data: oem.CcsdsOem,
    new_ref_frame: str,
    output_path: str,
) -> None:
    """Convert OEM reference frame metadata and write to output.

    Parameters
    ----------
    oem_data : oem.CcsdsOem
        Input OEM data.
    new_ref_frame : str
        New reference frame name to set in metadata.
    output_path : str
        Output file path. Use '-' for stdout.
    """
    oem_data.update_metadata(ref_frame=new_ref_frame)

    if output_path == "-":
        oem_data.write(sys.stdout)
    else:
        oem_data.write(output_path)


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with additional attributes:
        - lat_deg: float or None - Latitude in degrees
        - lon_deg: float or None - Longitude in degrees
        - alt_m: float or None - Altitude in meters
    """
    parser = argparse.ArgumentParser(
        description=(
            "⚠️  WARNING: NOT FULLY FUNCTIONAL YET ⚠️\n"
            "Transform OEM ephemeris files: change reference frames or convert to AER coordinates"
        ),
        epilog=(
            "By default, outputs the input OEM file as-is. "
            "Use --ref-frame to change the reference frame metadata, "
            "or --aer with comma-separated lat,lon,alt to convert to AER coordinates.\n\n"
            "⚠️  This script is a work in progress and may not produce correct results."
        ),
    )
    parser.add_argument(
        "oem_file",
        nargs="?",
        help='Path to input CCSDS OEM file in ECEF frame (use "-" or omit to read from stdin)',
    )
    parser.add_argument(
        "--aer",
        metavar="<lat,lon,alt>",
        help=(
            "Convert ECEF positions to AER (Azimuth-Elevation-Range) coordinates. "
            "Provide comma-separated values: latitude (degrees, +N/-S), "
            "longitude (degrees, +E/-W), altitude (meters above WGS-84 ellipsoid). "
            "Example: --aer 40.7128,-74.0060,10.0"
        ),
    )
    parser.add_argument(
        "--ref-frame",
        metavar="<frame>",
        help="Output reference frame. Updates the REF_FRAME metadata field in the output OEM file.",
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

    # Parse AER coordinates
    if args.aer:
        # Parse comma-separated lat,lon,alt
        try:
            parts = args.aer.split(",")
            if len(parts) != 3:
                parser.error(
                    "--aer requires exactly 3 comma-separated values: <lat>,<lon>,<alt>"
                )
            args.lat_deg = float(parts[0].strip())
            args.lon_deg = float(parts[1].strip())
            args.alt_m = float(parts[2].strip())
        except ValueError as e:
            parser.error(f"--aer values must be numeric: {e}")

        if args.ref_frame:
            parser.error("--aer and --ref-frame cannot be used together")
    else:
        args.lat_deg = None
        args.lon_deg = None
        args.alt_m = None

    return args


def main() -> None:
    """Parse CLI arguments and transform OEM file."""
    # Print warning message
    print("=" * 70, file=sys.stderr)
    print("⚠️  WARNING: THIS SCRIPT IS NOT FULLY FUNCTIONAL YET", file=sys.stderr)
    print(
        "This is a work in progress and may not produce correct results.",
        file=sys.stderr,
    )
    print("=" * 70, file=sys.stderr)
    print(file=sys.stderr)

    args = parse_arguments()

    # Determine if reading from stdin
    read_from_stdin = args.oem_file is None or args.oem_file == "-"

    # Read OEM data from stdin or file
    if read_from_stdin:
        oem_data = oem.CcsdsOem.read(sys.stdin)
        oem_file_path: str | Path = "<stdin>"
    else:
        oem_file_path = Path(args.oem_file)
        oem_data = oem.CcsdsOem.read(oem_file_path)

    # Print verbose info if requested
    if args.verbose:
        total_states = len(oem_data.states)
        print(f"[xform_oem] Input OEM:", file=sys.stderr)
        print(f"[xform_oem]   File: {oem_file_path}", file=sys.stderr)
        print(f"[xform_oem]   Object: {oem_data.meta.object_name}", file=sys.stderr)
        print(
            f"[xform_oem]   Reference frame: {oem_data.meta.ref_frame}",
            file=sys.stderr,
        )
        print(f"[xform_oem]   Center: {oem_data.meta.center_name}", file=sys.stderr)
        print(
            f"[xform_oem]   Time system: {oem_data.meta.time_system}",
            file=sys.stderr,
        )
        print(f"[xform_oem]   States: {total_states}", file=sys.stderr)

        if total_states > 0:
            first_ts, _ = oem_data.states[0]
            last_ts, _ = oem_data.states[-1]
            first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
            last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            span = last_dt - first_dt
            print(
                f"[xform_oem]   Start: {time_utils.datetime_to_iso8601(first_dt)}",
                file=sys.stderr,
            )
            print(
                f"[xform_oem]   End:   {time_utils.datetime_to_iso8601(last_dt)}",
                file=sys.stderr,
            )
            print(
                f"[xform_oem]   Span:  {time_utils.format_duration_human(span)}",
                file=sys.stderr,
            )
        print(file=sys.stderr)

    # Handle AER conversion mode
    if args.aer:
        # Determine output destination
        if args.output == "-":
            output_file = sys.stdout
        else:
            output_file = open(args.output, "w")

        try:
            convert_to_aer(
                oem_data,
                args.lat_deg,
                args.lon_deg,
                args.alt_m,
                output_file,
                args.verbose,
            )
        finally:
            if args.output != "-":
                output_file.close()
        return

    # Handle reference frame change or default output
    if args.ref_frame:
        convert_ref_frame(oem_data, args.ref_frame, args.output)
    else:
        # Output OEM file as-is
        if args.output == "-":
            oem_data.write(sys.stdout)
        else:
            oem_data.write(args.output)


if __name__ == "__main__":
    main()
