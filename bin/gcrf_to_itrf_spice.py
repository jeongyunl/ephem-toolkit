#!/usr/bin/env python3
"""Convert satellite state vectors between GCRF (J2000) and ITRF (ITRF93) using SPICE.

Usage:
    python3 gcrf_to_itrf_spice.py [-h] [-r] [input_file]

Reads OEM-format state vectors and transforms them between J2000 (GCRF) and
ITRF93 reference frames using SPICE rotation matrices.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sys
from pathlib import Path

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.frame_utils as frame_utils
import common.oem as oem
import common.spice_utils as spice_utils
import common.time_utils as time_utils


def process_oem(input_oem: oem.CcsdsOem, reverse: bool = False) -> oem.CcsdsOem:
    """Convert state vectors in an OEM between reference frames.

    Parameters
    ----------
    input_oem : oem.CcsdsOem
        Input OEM object with state vectors to convert.
    reverse : bool, optional
        If True, convert ITRF93 → J2000 instead of J2000 → ITRF93.
        Default: False (J2000 → ITRF93).

    Returns
    -------
    oem.CcsdsOem
        New OEM object with converted state vectors and updated metadata.
    """

    if reverse:
        base_frame: str = "ITRF93"
        target_frame: str = "J2000"
    else:
        base_frame = "J2000"
        target_frame = "ITRF93"

    # Convert all states
    converted_states: list[tuple[float, np.ndarray]] = []
    for epoch_timestamp, input_state_m in input_oem.states:
        epoch_dt: datetime = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
        epoch_tdb_s: float = time_utils.datetime_to_tdb_s(epoch_dt)

        # input_state_m is already in meters (from CcsdsOem)
        output_state_m: np.ndarray = frame_utils.spice_convert_frame(
            base_frame, target_frame, epoch_tdb_s, input_state_m
        )

        converted_states.append((epoch_timestamp, output_state_m))

    # Create new OEM with converted states and updated metadata
    output_oem: oem.CcsdsOem = oem.CcsdsOem(
        header=input_oem.header,
        meta=input_oem.meta,
        states=converted_states,
    )

    # Update reference frame in metadata
    output_oem.update_metadata(ref_frame=target_frame)

    return output_oem


def print_usage() -> None:
    """Print the script usage message to standard output.

    Displays usage information for the gcrf_to_itrf_spice CLI tool,
    including positional arguments, options, and input/output formats.
    """
    print(
        "Usage: python3 gcrf_to_itrf_spice.py [-h] [-r] [input_file]\n"
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
        input_file: str = args[0]
        # Read OEM file
        input_oem: oem.CcsdsOem = oem.CcsdsOem.read(input_file)
    else:
        # Read from stdin
        input_oem: oem.CcsdsOem = oem.CcsdsOem.read(sys.stdin)

    # Convert frames
    output_oem: oem.CcsdsOem = process_oem(input_oem, reverse=set_reverse_conversion)

    # Output in OEM format only if the input was OEM format (header exists)
    if input_oem.header.version > 0.0:
        output_oem.write(sys.stdout)
    else:
        oem.write_states(sys.stdout, output_oem.states)
