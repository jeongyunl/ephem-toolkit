#!/usr/bin/env python3
"""Transform OEM ephemeris files: change reference frames or convert to AER coordinates.

This utility can:
1. Output OEM files as-is (default when no options given)
2. Transform state data to another reference frame and update its metadata (--x-ref-frame)
3. Convert ECEF positions to AER coordinates (--x-aer with lat,lon,alt)
4. Override output OEM metadata (--set-meta KEY=VALUE)
5. Override output OEM header fields (--set-header KEY=VALUE)
6. Write state data as CSV (--x-csv)
7. Write state data without the OEM header and metadata (--data-only)

Usage:
    # Output OEM file as-is
    xform-oem <input_oem>
    cat data.oem | xform-oem - -o -

    # Transform state data and update the reference frame metadata
    xform-oem <input_oem> --x-ref-frame J2000

    # Convert to AER coordinates
    xform-oem <input_oem> --x-aer <lat>,<lon>,<alt>

Examples:
    # Output ISS OEM file as-is
    xform-oem iss.oem

    # Transform state data to J2000 and update the reference frame metadata
    xform-oem iss.oem --x-ref-frame J2000 -o output.oem

    # Rewrite metadata after any state transformation
    xform-oem iss.oem --x-ref-frame J2000 \
        --set-meta OBJECT_NAME=ISS --set-header ORIGINATOR=NASA -o output.oem

    # Convert ISS orbit to AER from ground station
    xform-oem iss.oem --x-aer 40.7128,-74.0060,10.0

    # Write state data as CSV
    xform-oem iss.oem --x-csv -o output.csv

    # Write state data without the OEM header and metadata
    xform-oem iss.oem --data-only -o states.txt

    # Read from stdin and convert to AER
    cat iss.oem | xform-oem - --x-aer 40.7128,-74.0060,10.0 -o -

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
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO
import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import numpy as np

try:
    from .xform_oem_cli import XformOemArgs
    from .xform_oem_cli import build_arg_parser, parse_arguments
except ImportError:  # pragma: no cover - direct script execution fallback
    from ephem_toolkit.xform_oem.xform_oem_cli import XformOemArgs
    from ephem_toolkit.xform_oem.xform_oem_cli import build_arg_parser, parse_arguments

import ephem_toolkit.core.aer as aer
import ephem_toolkit.core.frame_utils as frame_utils
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.time_utils as time_utils


def convert_to_aer(
    oem_data: oem.CcsdsOem,
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
    output_file: TextIO,
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
    ref_frame: str = oem_data.meta.ref_frame.upper()
    is_itrf = re.fullmatch(r"ITRF(?:\d{4})?", ref_frame) is not None
    if "ECEF" not in ref_frame and not is_itrf:
        print(
            f"Warning: Reference frame '{oem_data.meta.ref_frame}' may not be ECEF. "
            "Expected ECEF or ITRF variant.",
            file=sys.stderr,
        )

    # Convert ground station coordinates from degrees to radians
    lat_rad: float = np.deg2rad(lat_deg)
    lon_rad: float = np.deg2rad(lon_deg)
    reference_lla_rad_m: np.ndarray = np.array([lat_rad, lon_rad, alt_m])

    if verbose:
        print(f"[xform_oem] Ground station:", file=sys.stderr)
        print(f"[xform_oem]   Latitude:  {lat_deg:>10.6f}°", file=sys.stderr)
        print(f"[xform_oem]   Longitude: {lon_deg:>10.6f}°", file=sys.stderr)
        print(f"[xform_oem]   Altitude:  {alt_m:>10.3f} m", file=sys.stderr)
        print(file=sys.stderr)

    # Convert each state to AER
    for timestamp, state_vector in oem_data.states:
        # Extract position (first 3 elements)
        ecef_position_m: np.ndarray = state_vector[0:3]

        # Convert ECEF position to AER
        aer_position: np.ndarray = aer.ecef_to_aer(
            ecef_position_m,
            reference_lla_rad_m,
        )

        # Convert to degrees for output
        azimuth_deg: float = np.rad2deg(aer_position[0])
        elevation_deg: float = np.rad2deg(aer_position[1])
        range_m: float = aer_position[2]

        # Format timestamp
        dt: datetime = time_utils.tt_s_to_datetime(timestamp)
        timestamp_str: str = time_utils.datetime_to_iso8601(dt)

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
    target_ref_frame_name: str,
    source_ref_frame_override: str | None = None,
) -> str | None:
    """Convert OEM state vectors to a new reference frame.

    Parameters
    ----------
    oem_data : oem.CcsdsOem
        Input OEM data.
    target_ref_frame_name : str
        New reference frame name for the converted state vectors.
    source_ref_frame_override : str | None, optional
        Override the source reference frame name from the OEM file.
        If None, uses the reference frame from the OEM metadata.

    Returns
    -------
    str | None
        Canonical target frame name on success, or ``None`` if a state could
        not be converted.
    """

    # Use override if provided, otherwise use the OEM file's reference frame
    if source_ref_frame_override:
        original_reference_frame: frame_utils.Frame = frame_utils.Frame(
            source_ref_frame_override.upper()
        )
    else:
        original_reference_frame = frame_utils.Frame(oem_data.meta.ref_frame.upper())

    target_reference_frame: frame_utils.Frame = frame_utils.Frame(
        target_ref_frame_name.upper()
    )

    for state in oem_data.states:
        tt_s, state_vector_m = state
        # Convert state vector to new reference frame
        converted_state_vector_m: np.ndarray | None = frame_utils.convert_frame(
            base_frame=original_reference_frame,
            target_frame=target_reference_frame,
            epoch_tt_s=tt_s,
            input_state_m=state_vector_m,
        )

        if converted_state_vector_m is None:
            print(
                f"Error: Could not convert state at timestamp {tt_s} "
                f"from {original_reference_frame.value} to "
                f"{target_reference_frame.value}. "
                "Leaving state unchanged.",
                file=sys.stderr,
            )
            return None

        # Update the state in the OEM data
        state[1][:] = converted_state_vector_m

    return target_reference_frame.value


def parse_metadata_overrides(
    values: list[str], parser: argparse.ArgumentParser
) -> list[tuple[str, str | int]]:
    """Parse and validate repeated ``KEY=VALUE`` metadata overrides."""
    metadata_fields: dict[str, str] = {
        field_name.upper(): field_name
        for field_name in vars(oem.OemMeta())
        if field_name != "comments"
    }
    overrides: list[tuple[str, str | int]] = []

    for value in values:
        if "=" not in value:
            parser.error(f"--set-meta requires KEY=VALUE, got {value!r}")
        key, field_value = value.split("=", 1)
        field_name = metadata_fields.get(key.strip().upper())
        if field_name is None:
            supported_fields = ", ".join(sorted(metadata_fields))
            parser.error(
                f"unknown --set-meta key {key.strip()!r}; "
                f"supported keys: {supported_fields}"
            )

        if field_name == "interpolation_degree":
            try:
                parsed_value: str | int = int(field_value.strip())
            except ValueError:
                parser.error("--set-meta INTERPOLATION_DEGREE must be an integer")
        else:
            parsed_value = field_value
        overrides.append((field_name, parsed_value))

    return overrides


def parse_header_overrides(
    values: list[str], parser: argparse.ArgumentParser
) -> list[tuple[str, str | float]]:
    """Parse and validate repeated ``KEY=VALUE`` header overrides."""
    header_fields: dict[str, str] = {
        "CCSDS_OEM_VERS": "version",
        "CREATION_DATE": "creation_date",
        "ORIGINATOR": "originator",
        "CLASSIFICATION": "classification",
        "MESSAGE_ID": "message_id",
    }
    overrides: list[tuple[str, str | float]] = []

    for value in values:
        if "=" not in value:
            parser.error(f"--set-header requires KEY=VALUE, got {value!r}")
        key, field_value = value.split("=", 1)
        field_name = header_fields.get(key.strip().upper())
        if field_name is None:
            supported_fields = ", ".join(sorted(header_fields))
            parser.error(
                f"unknown --set-header key {key.strip()!r}; "
                f"supported keys: {supported_fields}"
            )

        if field_name == "version":
            try:
                parsed_value: str | float = float(field_value.strip())
            except ValueError:
                parser.error("--set-header CCSDS_OEM_VERS must be numeric")
        else:
            parsed_value = field_value
        overrides.append((field_name, parsed_value))

    return overrides


def main(argv=None) -> None:
    """Parse CLI arguments and transform OEM file."""

    cli_parser = build_arg_parser()
    cli_args: XformOemArgs = parse_arguments(cli_parser, argv)

    # Determine if reading from stdin
    read_from_stdin = cli_args.input_oem == "-"

    # Read OEM data from stdin or file
    if read_from_stdin:
        oem_data = oem.CcsdsOem.read(sys.stdin)
        oem_file_path: str | Path = "<stdin>"
    else:
        oem_file_path = Path(cli_args.input_oem)
        oem_data = oem.CcsdsOem.read(oem_file_path)

    # Print verbose info if requested
    if cli_args.verbose:
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
        if cli_args.x_ref_frame_parts:
            source_frame, target_frame = cli_args.x_ref_frame_parts
            print(
                f"[xform_oem]   Frame conversion: "
                f"{source_frame or oem_data.meta.ref_frame} -> {target_frame}",
                file=sys.stderr,
            )
        if cli_args.metadata_overrides:
            print("[xform_oem]   Metadata overrides:", file=sys.stderr)
            for field_name, value in cli_args.metadata_overrides:
                print(
                    f"[xform_oem]     {field_name.upper()}: "
                    f"{getattr(oem_data.meta, field_name)} -> {value}",
                    file=sys.stderr,
                )
        if cli_args.header_overrides:
            print("[xform_oem]   Header overrides:", file=sys.stderr)
            for field_name, value in cli_args.header_overrides:
                print(
                    f"[xform_oem]     {field_name.upper()}: "
                    f"{getattr(oem_data.header, field_name)} -> {value}",
                    file=sys.stderr,
                )

        print(f"[xform_oem]   Total States: {total_states}", file=sys.stderr)

        if total_states > 0:
            first_ts, _ = oem_data.states[0]
            last_ts, _ = oem_data.states[-1]
            first_dt = time_utils.tt_s_to_datetime(first_ts)
            last_dt = time_utils.tt_s_to_datetime(last_ts)
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
    if cli_args.x_aer:
        # Determine output destination
        if cli_args.output_oem == "-":
            output_file: TextIO = sys.stdout
        else:
            output_file = open(cli_args.output_oem, "w", encoding="utf-8")

        try:
            convert_to_aer(
                oem_data,
                cli_args.lat_deg,
                cli_args.lon_deg,
                cli_args.alt_m,
                output_file,
                cli_args.verbose,
            )
        finally:
            if cli_args.output_oem != "-":
                output_file.close()
        return

    # Handle reference frame change or default output
    if cli_args.x_ref_frame_parts:
        source_frame, target_frame = cli_args.x_ref_frame_parts
        converted_ref_frame = convert_ref_frame(
            oem_data,
            target_frame,
            source_frame,
        )
        if converted_ref_frame is None:
            return
        oem_data.update_metadata(ref_frame=converted_ref_frame)
    if cli_args.metadata_overrides:
        oem_data.update_metadata(**dict(cli_args.metadata_overrides))
    if cli_args.header_overrides:
        for field_name, value in cli_args.header_overrides:
            setattr(oem_data.header, field_name, value)

    output_format = oem.OemFormat.CSV if cli_args.x_csv else oem.OemFormat.OEM

    if cli_args.output_oem == "-":
        output_stream: TextIO = sys.stdout
    else:
        output_stream = open(cli_args.output_oem, "w", encoding="utf-8")

    try:
        if cli_args.data_only:
            oem_data.write_states(output_stream, format_type=output_format)
        else:
            oem_data.write(output_stream, format_type=output_format)
    finally:
        if cli_args.output_oem != "-":
            output_stream.close()


if __name__ == "__main__":
    main()
