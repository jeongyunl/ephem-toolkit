#!/usr/bin/env python3
"""Convert satellite state vectors between GCRF and ITRF using a TudatPy Earth rotation model.

Usage:
    python3 gcrf_to_itrf_rot_model.py [-h] [-r] [-m MODEL] [input_file]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

# Suppress Warnings from TudatPy
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import numpy as np
from tudatpy.dynamics import environment_setup
from tudatpy.dynamics.environment_setup.rotation_model import RotationModelSettings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.frame_utils as frame_utils
import common.oem as oem
import common.spice_utils as spice_utils
import common.time_utils as time_utils

# ===================================================================
# SPICE kernel loading
# ===================================================================


def load_spice_kernels() -> None:
    """Load required SPICE kernels for time conversion and Earth orientation."""

    spice_kernel_files: list[str] = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
        "earth_200101_990825_predict.bpc",  # Earth rotation prediction. Covers Jan, 2001 to Aug, 2099
    ]
    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


# ===================================================================
# Earth rotation model creation
# ===================================================================


def create_earth_rotation_model(
    global_frame_orientation: str,
    rotation_model_settings: RotationModelSettings,
) -> object:
    """Create and return an Earth rotation model using TudatPy.

    The rotation model is configured for the Earth body in the given inertial
    frame orientation and can be used to convert between inertial (GCRF/ICRF)
    and body-fixed (ECEF) coordinate systems.

    Parameters
    ----------
    global_frame_orientation : str
        Inertial frame orientation string (e.g. ``"GCRS"``).
    rotation_model_settings : RotationModelSettings
        Pre-configured rotation model settings (e.g. GCRS-to-ITRS IAU 2006).

    Returns
    -------
    object
        TudatPy Earth rotation model instance.
    """

    earth_name: str = "Earth"
    global_frame_origin: str = earth_name
    bodies_to_create: list[str] = [earth_name]

    body_settings: dict = environment_setup.get_default_body_settings(
        bodies_to_create, global_frame_origin, global_frame_orientation
    )

    bodies: object = environment_setup.create_system_of_bodies(body_settings)

    environment_setup.add_rotation_model(
        bodies,
        earth_name,
        rotation_model_settings,
    )

    return bodies.get(earth_name).rotation_model


# ===================================================================
# Stream processing
# ===================================================================


def convert_oem_states(
    input_oem: oem.CcsdsOem,
    global_frame_orientation: str,
    rotation_model_settings: RotationModelSettings,
    reverse: bool = False,
) -> oem.CcsdsOem:
    """Convert all states in a CcsdsOem between GCRF and ITRF frames.

    Parameters
    ----------
    input_oem : oem.CcsdsOem
        Input OEM with states to convert.
    global_frame_orientation : str
        Inertial frame orientation string (e.g. ``"GCRS"`` or ``"J2000"``).
    rotation_model_settings : RotationModelSettings
        Pre-configured rotation model settings (e.g. GCRS-to-ITRS IAU 2006,
        SPICE IAU_Earth, SPICE ITRF93).
    reverse : bool
        If True, perform ITRF→GCRF conversion instead of GCRF→ITRF.

    Returns
    -------
    oem.CcsdsOem
        New OEM with converted states and updated metadata.
    """

    earth_rotation_model: object = create_earth_rotation_model(
        global_frame_orientation, rotation_model_settings
    )

    converted_states: list[tuple[float, np.ndarray]] = []

    for timestamp, state_m in input_oem.states:
        # Convert POSIX timestamp (UTC) to datetime, then to TDB seconds since J2000
        epoch_dt: datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        epoch_tdb_s: float = time_utils.datetime_to_tdb_s(epoch_dt)

        # State vector is already in SI units (m, m/s)
        if reverse:
            output_state: np.ndarray = frame_utils.tudat_convert_body_fixed_to_inertial(
                earth_rotation_model,
                epoch_tdb_s,
                state_m,
            )
            output_ref_frame: str = "GCRF"
        else:
            output_state = frame_utils.tudat_convert_inertial_to_body_fixed(
                earth_rotation_model,
                epoch_tdb_s,
                state_m,
            )
            output_ref_frame: str = "ITRF"

        converted_states.append((timestamp, output_state))

    # Create new OEM with converted states and updated reference frame
    output_oem: oem.CcsdsOem = input_oem.with_metadata(ref_frame=output_ref_frame)
    output_oem.states = converted_states

    return output_oem


def process_stream(
    global_frame_orientation: str,
    rotation_model_settings: RotationModelSettings,
    stream: TextIO,
    reverse: bool = False,
) -> None:
    """Read lines from *stream*, convert each epoch, and print transformed state vectors.

    This function maintains backward compatibility with line-by-line stdin input.

    Parameters
    ----------
    global_frame_orientation : str
        Inertial frame orientation string (e.g. ``"GCRS"`` or ``"J2000"``).
    rotation_model_settings : RotationModelSettings
        Pre-configured rotation model settings (e.g. GCRS-to-ITRS IAU 2006,
        SPICE IAU_Earth, SPICE ITRF93).
    stream : TextIO
        An iterable of text lines (file object or sys.stdin).
    reverse : bool
        If True, perform ITRF→GCRF conversion instead of GCRF→ITRF.
    """

    earth_rotation_model: object = create_earth_rotation_model(
        global_frame_orientation, rotation_model_settings
    )

    for line in stream:
        try:
            parsed: tuple[float, np.ndarray] | None = oem.parse_oem_state_line(line)
        except Exception as exc:
            print(f"Skipping line (parse error): {line.strip()} -- {exc}")
            continue
        if parsed is None:
            continue

        timestamp, state_m = parsed

        # Convert POSIX timestamp (UTC) to datetime, then to TDB seconds since J2000
        epoch_dt: datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        epoch_tdb_s: float = time_utils.datetime_to_tdb_s(epoch_dt)

        # State vector is already in SI units (m, m/s) from oem.parse_oem_state_line()
        if reverse:
            output_state: np.ndarray = frame_utils.tudat_convert_body_fixed_to_inertial(
                earth_rotation_model,
                epoch_tdb_s,
                state_m,
            )
        else:
            output_state = frame_utils.tudat_convert_inertial_to_body_fixed(
                earth_rotation_model,
                epoch_tdb_s,
                state_m,
            )

        # Convert m / m/s → km / km/s for output
        output_position_km: np.ndarray = output_state[0:3] / 1e3

        print(
            time_utils.datetime_to_iso8601(epoch_dt),
            *output_position_km,
            sep="  ",
            end="",
        )

        output_velocity_km_s: np.ndarray = output_state[3:6] / 1e3
        print("  ", *output_velocity_km_s, sep="  ", end="")
        print()


def process_oem_file(
    input_file: str | Path,
    global_frame_orientation: str,
    rotation_model_settings: RotationModelSettings,
    reverse: bool = False,
) -> None:
    """Read an OEM file, convert states, and write output to stdout.

    If the input file is in proper OEM format (with header and metadata),
    the output is written in OEM format. Otherwise, the output is written
    as plain text state lines (one per epoch).

    Parameters
    ----------
    input_file : str | Path
        Path to input OEM file or raw state list.
    global_frame_orientation : str
        Inertial frame orientation string (e.g. ``"GCRS"`` or ``"J2000"``).
    rotation_model_settings : RotationModelSettings
        Pre-configured rotation model settings (e.g. GCRS-to-ITRS IAU 2006,
        SPICE IAU_Earth, SPICE ITRF93).
    reverse : bool
        If True, perform ITRF→GCRF conversion instead of GCRF→ITRF.
    """

    # Read OEM file using CcsdsOem class
    input_oem: oem.CcsdsOem = oem.CcsdsOem.read(input_file)

    if input_oem.header.version > 0.0:
        # Input is proper OEM format — output in OEM format
        output_oem: oem.CcsdsOem = convert_oem_states(
            input_oem,
            global_frame_orientation,
            rotation_model_settings,
            reverse,
        )
        output_oem.write(sys.stdout)
    else:
        # Input is a raw state list — output as plain text lines
        with open(input_file, "r", encoding="utf-8") as fh:
            process_stream(
                global_frame_orientation,
                rotation_model_settings,
                fh,
                reverse=reverse,
            )


# ===================================================================
# CLI usage and main entry point
# ===================================================================


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Convert satellite state vectors between GCRF and ITRF using "
            "the specified Earth rotation model."
        ),
        epilog=(
            "Input OEM states must contain position and velocity in SI units. "
            "The converted OEM is written to standard output."
        ),
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to input OEM file (default: read state lines from stdin)",
    )
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="Reverse conversion from ITRF to GCRF",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="rotation_model_name",
        choices=("spice_iau_earth", "spice_itrf93", "spice", "gcrs_to_itrs"),
        default="gcrs_to_itrs",
        help="Earth rotation model (default: gcrs_to_itrs)",
    )

    return parser


def main() -> None:
    """Parse arguments and convert the input OEM or stdin state stream."""

    parser: argparse.ArgumentParser = create_argument_parser()
    args: argparse.Namespace = parser.parse_args()

    load_spice_kernels()

    # Configure rotation model settings and inertial frame orientation
    # based on the selected rotation model name.
    if args.rotation_model_name == "spice_iau_earth":
        original_frame: str = "J2000"
        target_frame: str = "IAU_Earth"

        rotation_model_settings: RotationModelSettings = (
            environment_setup.rotation_model.spice(
                original_frame,
                target_frame,
            )
        )
        global_frame_orientation: str = original_frame

    elif (
        args.rotation_model_name == "spice_itrf93"
        or args.rotation_model_name == "spice"
    ):
        original_frame: str = "J2000"
        target_frame: str = "ITRF93"

        rotation_model_settings: RotationModelSettings = (
            environment_setup.rotation_model.spice(
                original_frame,
                target_frame,
            )
        )
        global_frame_orientation: str = original_frame

    elif args.rotation_model_name == "gcrs_to_itrs":
        global_frame_orientation: str = "GCRS"

        rotation_model_settings: RotationModelSettings = (
            environment_setup.rotation_model.gcrs_to_itrs(
                environment_setup.rotation_model.IAUConventions.iau_2006,
                global_frame_orientation,
            )
        )

    if args.input_file:
        input_file: str = args.input_file
        input_path: Path = Path(input_file)
        if not input_path.exists():
            parser.error(f"OEM file not found: {input_file}")
        process_oem_file(
            input_file,
            global_frame_orientation,
            rotation_model_settings,
            reverse=args.reverse,
        )
    else:
        process_stream(
            global_frame_orientation,
            rotation_model_settings,
            sys.stdin,
            reverse=args.reverse,
        )


if __name__ == "__main__":
    main()
