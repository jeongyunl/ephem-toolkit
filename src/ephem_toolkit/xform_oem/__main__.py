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

import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from . import xform_oem_cli

if TYPE_CHECKING:
    from .xform_oem_cli import XformOemArgs


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and transform an OEM file.

    Parameters
    ----------
    argv : list[str] | None, optional
        Command-line arguments, or ``None`` to use process arguments.

    Returns
    -------
    None
    """

    cli_parser = xform_oem_cli.build_arg_parser()
    cli_args: XformOemArgs = xform_oem_cli.parse_arguments(cli_parser, argv)

    # Suppress warnings that tudatpy / urllib3 may emit on import.
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    warnings.filterwarnings(
        "ignore",
        module=r"urllib3(\..*)?",
    )

    from . import operations
    import ephem_toolkit.core.ccsds.oem as oem
    import ephem_toolkit.core.time_utils as time_utils

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
            first_epoch_tt_s, _ = oem_data.states[0]
            last_epoch_tt_s, _ = oem_data.states[-1]
            first_datetime = time_utils.tt_s_to_datetime(first_epoch_tt_s)
            last_datetime = time_utils.tt_s_to_datetime(last_epoch_tt_s)
            span = last_datetime - first_datetime
            print(
                f"[xform_oem]   Start: {time_utils.datetime_to_iso8601(first_datetime)}",
                file=sys.stderr,
            )
            print(
                f"[xform_oem]   End:   {time_utils.datetime_to_iso8601(last_datetime)}",
                file=sys.stderr,
            )
            print(
                f"[xform_oem]   Span:  {time_utils.format_duration_human(span)}",
                file=sys.stderr,
            )
        print(file=sys.stderr)

    # Handle AER conversion mode
    if cli_args.x_aer:
        if (
            cli_args.lat_deg is None
            or cli_args.lon_deg is None
            or cli_args.alt_m is None
        ):
            raise ValueError(
                "AER conversion requires latitude, longitude, and altitude"
            )

        # Determine output destination
        if cli_args.output_oem == "-":
            dest: TextIO = sys.stdout
        else:
            dest = open(cli_args.output_oem, "w", encoding="utf-8")

        try:
            operations.convert_to_aer(
                oem_data,
                cli_args.lat_deg,
                cli_args.lon_deg,
                cli_args.alt_m,
                dest,
                cli_args.verbose,
            )
        finally:
            if cli_args.output_oem != "-":
                dest.close()
        return

    # Handle reference frame change or default output
    if cli_args.x_ref_frame_parts:
        source_frame, target_frame = cli_args.x_ref_frame_parts
        converted_ref_frame = operations.convert_ref_frame(
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
        dest: TextIO = sys.stdout
    else:
        dest = open(cli_args.output_oem, "w", encoding="utf-8")

    try:
        if cli_args.data_only:
            oem_data.write_states(dest, format_type=output_format)
        else:
            oem_data.write(dest, format_type=output_format)
    finally:
        if cli_args.output_oem != "-":
            dest.close()


def cli(argv: list[str] | None = None) -> int:
    """Run the xform-oem CLI and return its exit status.

    Parameters
    ----------
    argv : list[str] | None, optional
        Command-line arguments, or ``None`` to use process arguments.

    Returns
    -------
    int
        CLI exit status.
    """
    import ephem_toolkit.core.cli as core_cli

    return core_cli.run_cli(main, argv)


if __name__ == "__main__":
    raise SystemExit(cli())
