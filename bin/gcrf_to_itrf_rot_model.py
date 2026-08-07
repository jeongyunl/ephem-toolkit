#!/usr/bin/env python3
"""Convert satellite state vectors between GCRF and ITRF using a TudatPy Earth rotation model.

Usage:
    python3 gcrf_to_itrf_rot_model.py [-h] [-r] [-m MODEL] [input_file]
"""

from __future__ import annotations

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
from tudatpy.interface import spice

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
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
        spice.load_kernel(spice_utils.get_spice_kernel_path() + "/" + kernel_file)


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
# Frame conversion functions
# ===================================================================


def convert_gcrf_to_itrf_erm(
    earth_rotation_model: object,
    input_epoch_et_s: float,
    input_gcrf_position_m: np.ndarray,
    input_gcrf_velocity_m_s: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Convert an inertial (GCRF/J2000) position/velocity vector to the body-fixed (ITRF/IAU_Earth) frame.

    Works with any Earth rotation model (GCRS-to-ITRS IAU 2006, SPICE IAU_Earth,
    SPICE ITRF93, etc.) provided via *earth_rotation_model*.

    Parameters
    ----------
    earth_rotation_model : object
        TudatPy Earth rotation model instance.
    input_epoch_et_s : float
        Epoch in ephemeris time (TDB seconds since J2000).
    input_gcrf_position_m : np.ndarray, shape (3,)
        Position vector in metres in the inertial (GCRF) frame.
    input_gcrf_velocity_m_s : np.ndarray, shape (3,), optional
        Velocity vector in m/s in the inertial (GCRF) frame.

    Returns
    -------
    tuple[np.ndarray, np.ndarray | None]
        Position (m) and optional velocity (m/s) in the body-fixed frame.
    """

    # Get rotation matrix for inertial to body-fixed transformation at the given epoch.
    # The inertial frame is GCRF (or J2000) and the body-fixed frame is ITRF (or IAU_Earth),
    # so this rotation matrix accounts for Earth's rotation at the given epoch.
    gcrf_to_itrf_rotation_matrix: np.ndarray = (
        earth_rotation_model.inertial_to_body_fixed_rotation(input_epoch_et_s)
    )

    # Get Earth's rotational velocity in the body-fixed frame at the given epoch,
    # which is needed to correctly transform the velocity vector from the inertial
    # frame to the body-fixed frame by accounting for the rotation of the body-fixed
    # frame with respect to the inertial frame.
    itrf_earth_rotational_velocity_rad_s: np.ndarray = (
        earth_rotation_model.angular_velocity_in_body_fixed_frame(input_epoch_et_s)
    )

    # Rotate the position vector from the inertial frame to the body-fixed frame using the rotation matrix
    output_itrf_position_m: np.ndarray = (
        gcrf_to_itrf_rotation_matrix @ input_gcrf_position_m
    )

    output_itrf_velocity_m_s: np.ndarray | None = None

    if input_gcrf_velocity_m_s is not None:
        # Rotate the velocity vector from the inertial frame to the body-fixed frame
        # and account for Earth's rotation using the formula:
        #  v_body = R * v_inertial - w x r_body
        # where R is the rotation matrix,
        # w is the Earth's rotational velocity in the body-fixed frame, and
        # r_body is the position in the body-fixed frame.
        # The cross product term accounts for the rotation of the body-fixed frame
        # with respect to the inertial frame.

        output_itrf_velocity_m_s = (
            gcrf_to_itrf_rotation_matrix @ input_gcrf_velocity_m_s
            - np.cross(itrf_earth_rotational_velocity_rad_s, output_itrf_position_m)
        )

    return output_itrf_position_m, output_itrf_velocity_m_s


def convert_itrf_to_gcrf_erm(
    earth_rotation_model: object,
    input_epoch_et_s: float,
    input_itrf_position_m: np.ndarray,
    input_itrf_velocity_m_s: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Convert a body-fixed (ITRF/IAU_Earth) position/velocity vector to the inertial (GCRF/J2000) frame.

    Works with any Earth rotation model (GCRS-to-ITRS IAU 2006, SPICE IAU_Earth,
    SPICE ITRF93, etc.) provided via *earth_rotation_model*.

    Parameters
    ----------
    earth_rotation_model : object
        TudatPy Earth rotation model instance.
    input_epoch_et_s : float
        Epoch in ephemeris time (TDB seconds since J2000).
    input_itrf_position_m : np.ndarray, shape (3,)
        Position vector in metres in the body-fixed (ITRF) frame.
    input_itrf_velocity_m_s : np.ndarray, shape (3,), optional
        Velocity vector in m/s in the body-fixed (ITRF) frame.

    Returns
    -------
    tuple[np.ndarray, np.ndarray | None]
        Position (m) and optional velocity (m/s) in the inertial frame.
    """

    # Get rotation matrix for body-fixed to inertial transformation at the given epoch.
    # The inertial frame is GCRF (or J2000) and the body-fixed frame is ITRF (or IAU_Earth),
    # so this rotation matrix accounts for Earth's rotation at the given epoch.
    itrf_to_gcrf_rotation_matrix: np.ndarray = (
        earth_rotation_model.body_fixed_to_inertial_rotation(input_epoch_et_s)
    )

    # Get Earth's rotational velocity in the inertial frame at the given epoch,
    # which is needed to correctly transform the velocity vector from the body-fixed
    # frame to the inertial frame by accounting for the rotation of the body-fixed
    # frame with respect to the inertial frame.
    gcrf_earth_rotational_velocity_rad_s: np.ndarray = (
        earth_rotation_model.angular_velocity_in_inertial_frame(input_epoch_et_s)
    )

    # Rotate the position vector from the body-fixed frame to the inertial frame using the rotation matrix
    output_gcrf_position_m: np.ndarray = (
        itrf_to_gcrf_rotation_matrix @ input_itrf_position_m
    )

    output_gcrf_velocity_m_s: np.ndarray | None = None

    if input_itrf_velocity_m_s is not None:
        # Rotate the velocity vector from the body-fixed frame to the inertial frame
        # and account for Earth's rotation using the formula:
        #  v_inertial = R * v_body + w x r_inertial
        # where R is the rotation matrix,
        # w is the Earth's rotational velocity in the inertial frame, and
        # r_inertial is the position in the inertial frame.
        # The cross product term accounts for the rotation of the body-fixed frame
        # with respect to the inertial frame.

        output_gcrf_velocity_m_s = (
            itrf_to_gcrf_rotation_matrix @ input_itrf_velocity_m_s
            + np.cross(gcrf_earth_rotational_velocity_rad_s, output_gcrf_position_m)
        )

    return output_gcrf_position_m, output_gcrf_velocity_m_s


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
        position_m: np.ndarray = state_m[0:3]
        velocity_m_s: np.ndarray = state_m[3:6]

        if reverse:
            output_position_m, output_velocity_m_s = convert_itrf_to_gcrf_erm(
                earth_rotation_model,
                epoch_tdb_s,
                position_m,
                velocity_m_s,
            )
            output_ref_frame: str = "GCRF"
        else:
            output_position_m, output_velocity_m_s = convert_gcrf_to_itrf_erm(
                earth_rotation_model,
                epoch_tdb_s,
                position_m,
                velocity_m_s,
            )
            output_ref_frame: str = "ITRF"

        # Combine position and velocity into state vector
        output_state: np.ndarray = np.concatenate(
            [output_position_m, output_velocity_m_s]
        )
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
        position_m: np.ndarray = state_m[0:3]
        velocity_m_s: np.ndarray = state_m[3:6]

        if reverse:
            output_position_m, output_velocity_m_s = convert_itrf_to_gcrf_erm(
                earth_rotation_model,
                epoch_tdb_s,
                position_m,
                velocity_m_s,
            )
        else:
            output_position_m, output_velocity_m_s = convert_gcrf_to_itrf_erm(
                earth_rotation_model,
                epoch_tdb_s,
                position_m,
                velocity_m_s,
            )

        # Convert m / m/s → km / km/s for output
        output_position_km: np.ndarray = output_position_m / 1e3

        print(
            time_utils.datetime_to_iso8601(epoch_dt),
            *output_position_km,
            sep="  ",
            end="",
        )

        if output_velocity_m_s is not None:
            output_velocity_km_s: np.ndarray = output_velocity_m_s / 1e3
            print("  ", *output_velocity_km_s, sep="  ", end="")
        print()


def _is_oem_format(parsed_oem: oem.CcsdsOem) -> bool:
    """Check whether a parsed OEM has valid header and metadata.

    An OEM file is considered to be in proper OEM format if it has a non-zero
    version number in the header, indicating that the file contained
    CCSDS_OEM_VERS and metadata blocks.

    Parameters
    ----------
    parsed_oem : oem.CcsdsOem
        Parsed OEM instance to check.

    Returns
    -------
    bool
        True if the input has OEM header/metadata, False if it is a raw state list.
    """
    return parsed_oem.header.version > 0.0


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

    if _is_oem_format(input_oem):
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


def print_usage() -> None:
    """Print the script usage message to standard output.

    Displays usage information for the gcrf_to_itrf_rot_model CLI tool,
    including positional arguments, options, rotation model selection,
    and input/output formats.
    """
    print(
        "Usage: python3 gcrf_to_itrf_rot_model.py [-h] [-r] [-m MODEL] [input_file]\n"
        "\n"
        "Convert satellite state vectors between GCRF and ITRF using the\n"
        "specified Earth rotation model.\n"
        "\n"
        "Positional arguments:\n"
        "  input_file    Path to an OEM-style ephemeris file. If omitted,\n"
        "                lines are read from stdin.\n"
        "\n"
        "Options:\n"
        "  -h, --help    Show this help message and exit.\n"
        "  -r            Reverse conversion (ITRF to GCRF instead of GCRF\n"
        "                to ITRF).\n"
        "  -m MODEL      Name of the rotation model to use. Valid names:\n"
        "                  spice_iau_earth  SPICE IAU_Earth model (J2000 frame)\n"
        "                  spice_itrf93     SPICE ITRF93 model (J2000 frame)\n"
        "                  spice            Alias for spice_itrf93\n"
        "                  gcrs_to_itrs     IAU 2006 GCRS-to-ITRS model (GCRS frame)\n"
        "                (default: gcrs_to_itrs).\n"
        "\n"
        "Input format (one record per line, 7 whitespace- or comma-separated fields):\n"
        "  <ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>\n"
        "\n"
        "Blank lines and lines starting with '#' are skipped."
    )


if __name__ == "__main__":
    # Parse command-line options: -h/--help, -r, -m MODEL
    reverse_conversion: bool = False
    rotation_model_name: str = "gcrs_to_itrs"
    args: list[str] = sys.argv[1:]

    if "-h" in args or "--help" in args:
        print_usage()
        sys.exit(0)

    if "-r" in args:
        reverse_conversion = True
        args.remove("-r")

    if "-m" in args:
        m_index: int = args.index("-m")
        if m_index + 1 >= len(args):
            print("Error: -m requires a rotation model name argument.", file=sys.stderr)
            sys.exit(1)
        rotation_model_name = args[m_index + 1]
        del args[m_index : m_index + 2]

    load_spice_kernels()

    # Configure rotation model settings and inertial frame orientation
    # based on the selected rotation model name.
    if rotation_model_name == "spice_iau_earth":
        original_frame: str = "J2000"
        target_frame: str = "IAU_Earth"

        rotation_model_settings: RotationModelSettings = (
            environment_setup.rotation_model.spice(
                original_frame,
                target_frame,
            )
        )
        global_frame_orientation: str = original_frame

    elif rotation_model_name == "spice_itrf93" or rotation_model_name == "spice":
        original_frame: str = "J2000"
        target_frame: str = "ITRF93"

        rotation_model_settings: RotationModelSettings = (
            environment_setup.rotation_model.spice(
                original_frame,
                target_frame,
            )
        )
        global_frame_orientation: str = original_frame

    elif rotation_model_name == "gcrs_to_itrs":
        global_frame_orientation: str = "GCRS"

        rotation_model_settings: RotationModelSettings = (
            environment_setup.rotation_model.gcrs_to_itrs(
                environment_setup.rotation_model.IAUConventions.iau_2006,
                global_frame_orientation,
            )
        )

    else:
        print(
            f"Error: Unknown rotation model '{rotation_model_name}'. "
            f"Valid options: spice_iau_earth, spice_itrf93, spice, gcrs_to_itrs",
            file=sys.stderr,
        )
        sys.exit(1)

    if args:
        input_file: str = args[0]
        input_path: Path = Path(input_file)
        if not input_path.exists():
            print(f"Error: File not found: {input_file}", file=sys.stderr)
            sys.exit(1)
        process_oem_file(
            input_file,
            global_frame_orientation,
            rotation_model_settings,
            reverse=reverse_conversion,
        )
    else:
        process_stream(
            global_frame_orientation,
            rotation_model_settings,
            sys.stdin,
            reverse=reverse_conversion,
        )
