"""CLI argument parsing for the OEM transformation command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.cli as cli


class XformOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM transformation CLI."""

    verbose: bool
    """Whether verbose diagnostics are enabled."""
    debug: bool
    """Whether low-level debug output is enabled."""
    set_header: list[str]
    """Header override entries as KEY=VALUE strings."""
    set_meta: list[str]
    """Metadata override entries as KEY=VALUE strings."""
    x_ref_frame: str | None
    """Optional target reference frame name."""
    x_aer: str | None
    """Optional AER conversion specification."""
    x_csv: bool
    """Whether to output CSV instead of OEM."""
    data_only: bool
    """Whether to omit OEM metadata header."""
    input_oem: str
    """Input OEM file path or '-' for stdin."""
    output_oem: str
    """Output OEM path or '-' for stdout."""
    x_ref_frame_parts: tuple[str | None, str] | None
    """Normalized frame conversion source/target pair, if applicable."""
    lat_deg: float | None
    """Latitude in degrees for AER conversion."""
    lon_deg: float | None
    """Longitude in degrees for AER conversion."""
    alt_m: float | None
    """Altitude in meters for AER conversion."""
    metadata_overrides: list[tuple[str, str | int]]
    """Parsed metadata overrides."""
    header_overrides: list[tuple[str, str | float]]
    """Parsed header overrides."""


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


def parse_arguments() -> XformOemArgs:
    """Parse and validate command-line arguments."""
    parser = cli.create_parser(
        description=(
            "Transform OEM ephemeris files by changing the reference frame "
            "or converting to AER coordinates."
        ),
        epilog=(
            "Examples:\n"
            "  xform-oem data.oem --x-ref-frame J2000\n"
            "  xform-oem data.oem --x-aer 40.7128,-74.0060,10.0\n"
            "  cat data.oem | xform-oem - --x-csv"
        ),
    )
    parser.prog = "xform-oem"
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Print extra diagnostic output.",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print low-level debug details.",
    )
    parser.add_argument(
        "--set-header",
        dest="set_header",
        action="append",
        default=[],
        metavar="<key=value>",
        help=(
            "Override an OEM header field in the output. Repeatable. "
            "Supported keys: CCSDS_OEM_VERS, CREATION_DATE, ORIGINATOR."
        ),
    )
    parser.add_argument(
        "--set-meta",
        dest="set_meta",
        action="append",
        default=[],
        metavar="<key=value>",
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
        dest="x_ref_frame",
        metavar="<frame>",
        help=(
            "Transform state vectors to a target reference frame and update "
            "the output REF_FRAME metadata. Use either a single target frame or "
            "<base_frame,target_frame> for an explicit source/target pair."
        ),
    )
    x_format_group.add_argument(
        "--x-aer",
        dest="x_aer",
        metavar="<lat,lon,alt>",
        help=(
            "Convert ECEF positions to AER coordinates using latitude, longitude, "
            "and altitude in degrees and meters. Example: --x-aer 40.7128,-74.0060,10.0"
        ),
    )
    x_format_group.add_argument(
        "--x-csv",
        dest="x_csv",
        action="store_true",
        help="Write the transformed OEM state data in CSV format.",
    )
    parser.add_argument(
        "--data-only",
        dest="data_only",
        action="store_true",
        help="Write only state data, without the OEM header and metadata.",
    )
    parser.add_argument(
        "input_oem",
        metavar="<input_oem|->",
        help='Primary input OEM file path; use "-" to read from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_oem",
        metavar="<output_oem|->",
        default="-",
        help="Output OEM file path; '-' writes to stdout.",
    )

    args: XformOemArgs = parser.parse_args(namespace=XformOemArgs())
    args.x_ref_frame_parts = None
    if args.x_ref_frame:
        frame_parts: list[str] = [part.strip() for part in args.x_ref_frame.split(",")]
        if len(frame_parts) == 1 and frame_parts[0]:
            args.x_ref_frame_parts = (None, frame_parts[0])
        elif len(frame_parts) == 2 and all(frame_parts):
            args.x_ref_frame_parts = (frame_parts[0], frame_parts[1])
        else:
            parser.error("--x-ref-frame requires <frame> or <base_frame,target_frame>")

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

    args.metadata_overrides = []
    args.header_overrides = []
    if args.set_meta:
        args.metadata_overrides = [
            (field_name, value)
            for field_name, value in parse_metadata_overrides(args.set_meta, parser)
        ]
    if args.set_header:
        args.header_overrides = [
            (field_name, value)
            for field_name, value in parse_header_overrides(args.set_header, parser)
        ]

    return args
