"""CLI argument parsing for the OEM transformation command."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Transform OEM ephemeris files: change reference frames or convert to AER coordinates"
        ),
        epilog=(
            "By default, outputs the input OEM file as-is. "
            "Use --x-ref-frame to transform state data and update its reference frame metadata, "
            "--set-meta KEY=VALUE to override output metadata, "
            "--set-header KEY=VALUE to override output header fields, "
            "--x-csv to write state data as CSV, --data-only to omit the OEM "
            "header and metadata, or --x-aer with comma-separated "
            "lat,lon,alt to convert to AER coordinates.\n\n"
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )
    parser.add_argument(
        "--set-header",
        action="append",
        default=[],
        metavar="<KEY=VALUE>",
        help=(
            "Override an OEM header field in the output. Repeatable. "
            "Supported keys: CCSDS_OEM_VERS, CREATION_DATE, ORIGINATOR."
        ),
    )
    parser.add_argument(
        "--set-meta",
        action="append",
        default=[],
        metavar="<KEY=VALUE>",
        help=(
            "Override an OEM metadata field in the output. Repeatable. "
            "Supported keys include OBJECT_NAME, OBJECT_ID, CENTER_NAME, "
            "REF_FRAME, TIME_SYSTEM, START_TIME, STOP_TIME, INTERPOLATION, "
            "and INTERPOLATION_DEGREE."
        ),
    )
    x_format_group = parser.add_mutually_exclusive_group()
    x_format_group.add_argument(
        "--x-ref-frame",
        metavar="<frame>|<base_frame,target_frame>",
        help=(
            "Transform state vectors to a target reference frame and update "
            "the output REF_FRAME metadata. Provide one "
            "frame to use the OEM REF_FRAME as the source, or provide "
            "base_frame,target_frame to override the source frame."
        ),
    )
    x_format_group.add_argument(
        "--x-aer",
        metavar="<lat,lon,alt>",
        help=(
            "Convert ECEF positions to AER (Azimuth-Elevation-Range) coordinates. "
            "Provide comma-separated values: latitude (degrees, +N/-S), "
            "longitude (degrees, +E/-W), altitude (meters above WGS-84 ellipsoid). "
            "Example: --x-aer 40.7128,-74.0060,10.0"
        ),
    )
    x_format_group.add_argument(
        "--x-csv",
        action="store_true",
        help="Write the transformed OEM state data in CSV format",
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Write only state data, without the OEM header and metadata",
    )
    parser.add_argument(
        "oem_file",
        help='Path to input CCSDS OEM file in ECEF frame. Use "-" to read from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help="Output file path (default: '-'). Use '-' to print to stdout.",
    )

    args = parser.parse_args()
    args.x_ref_frame_parts = None
    if args.x_ref_frame:
        frame_parts: list[str] = [part.strip() for part in args.x_ref_frame.split(",")]
        if len(frame_parts) == 1 and frame_parts[0]:
            args.x_ref_frame_parts = (None, frame_parts[0])
        elif len(frame_parts) == 2 and all(frame_parts):
            args.x_ref_frame_parts = (frame_parts[0], frame_parts[1])
        else:
            parser.error(
                "--x-ref-frame requires <frame> or <base_frame>,<target_frame>"
            )

    if args.x_aer:
        try:
            parts: list[str] = args.x_aer.split(",")
            if len(parts) != 3:
                parser.error(
                    "--x-aer requires exactly 3 comma-separated values: <lat>,<lon>,<alt>"
                )
            args.lat_deg = float(parts[0].strip())
            args.lon_deg = float(parts[1].strip())
            args.alt_m = float(parts[2].strip())
        except ValueError as exc:
            parser.error(f"--x-aer values must be numeric: {exc}")
    else:
        args.lat_deg = None
        args.lon_deg = None
        args.alt_m = None

    return args
