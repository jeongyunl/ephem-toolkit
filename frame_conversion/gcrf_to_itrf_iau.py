#!/usr/bin/env python3

import sys

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

import numpy as np
from tudatpy.interface import spice
from tudatpy import data

from common import parse_line, datetime_to_tdb


def load_spice_kernels():
    """Load required SPICE kernels for time conversion and Earth orientation."""

    spice_kernel_files = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(data.get_spice_kernel_path() + "/" + kernel_file)


def create_earth_rotation_model():
    """Create and return an Earth rotation model using TudatPy.

    The rotation model is configured for the Earth body in the GCRS inertial frame
    and can be used to convert between inertial (GCRF/ICRF) and body-fixed (ECEF) coordinate systems.
    """

    from tudatpy.dynamics import environment_setup

    Earth = "Earth"
    global_frame_origin = Earth
    global_frame_orientation = "GCRS"
    bodies_to_create = [Earth]

    body_settings = environment_setup.get_default_body_settings(
        bodies_to_create, global_frame_origin, global_frame_orientation
    )

    bodies = environment_setup.create_system_of_bodies(body_settings)

    environment_setup.add_rotation_model(
        bodies,
        Earth,
        environment_setup.rotation_model.gcrs_to_itrs(
            environment_setup.rotation_model.IAUConventions.iau_2006,
            global_frame_orientation,
        ),
    )

    return bodies.get(Earth).rotation_model


def convert_gcrf_to_itrf_iau(
    earth_rotation_model,
    input_epoch_et_s,
    input_gcrf_position_m,
    input_gcrf_velocity_m_s=None,
):
    """Convert a GCRF position/velocity vector to the ITRF frame.

    Args:
        earth_rotation_model: TudatPy Earth rotation model instance.
        input_epoch_et_s: Epoch in ephemeris time (TDB seconds since J2000).
        input_gcrf_position_m: 3-element numpy array position in metres.
        input_gcrf_velocity_m_s: Optional 3-element numpy array velocity in m/s.

    Returns:
        tuple[numpy.ndarray, numpy.ndarray | None]: position (m) and optional
            velocity (m/s) in ITRF.
    """

    # Get rotation matrix for GCRS to ITRS transformation at the given epoch
    # GCRF is an inertial frame, ITRF is a body-fixed frame, so this rotation matrix accounts for Earth's rotation at the given epoch
    # Thus the name of the function is `inertial_to_body_fixed_rotation'
    gcrf_to_itrf_rotation_matrix = earth_rotation_model.inertial_to_body_fixed_rotation(
        input_epoch_et_s
    )

    # Get Earth's rotational velocity in the ITRF frame at the given epoch,
    # which is needed to correctly transform the velocity vector from GCRF to ITRF
    # by accounting for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.
    itrf_earth_rotational_velocity_rad_s = (
        earth_rotation_model.angular_velocity_in_body_fixed_frame(input_epoch_et_s)
    )

    # Rotate the position vector from GCRF to ITRF using the rotation matrix
    output_itrf_position_m = gcrf_to_itrf_rotation_matrix @ input_gcrf_position_m

    output_itrf_velocity_m_s = None

    if input_gcrf_velocity_m_s is not None:
        # Rotate the velocity vector from GCRF to ITRF and account for Earth's rotation using the formula:
        #  v_ITRF = R * v_GCRF - w x r_ITRF
        # where R is the rotation matrix,
        # w is the Earth's rotational velocity in the ITRF frame, and
        # r_ITRF is the position in the ITRF frame.
        # The cross product term accounts for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.

        output_itrf_velocity_m_s = (
            gcrf_to_itrf_rotation_matrix @ input_gcrf_velocity_m_s
            - np.cross(itrf_earth_rotational_velocity_rad_s, output_itrf_position_m)
        )

    return output_itrf_position_m, output_itrf_velocity_m_s


# Function to convert position and velocity from ITRF to GCRF at a given epoch using the Earth rotation model
def convert_itrf_to_gcrf_iau(
    earth_rotation_model,
    input_epoch_et_s,
    input_itrf_position_m,
    input_itrf_velocity_m_s=None,
):
    """Convert an ITRF position/velocity vector to the GCRF frame.

    Args:
        earth_rotation_model: TudatPy Earth rotation model instance.
        input_epoch_et_s: Epoch in ephemeris time (TDB seconds since J2000).
        input_itrf_position_m: 3-element numpy array position in metres.
        input_itrf_velocity_m_s: Optional 3-element numpy array velocity in m/s.

    Returns:
        tuple[numpy.ndarray, numpy.ndarray | None]: position (m) and optional
            velocity (m/s) in GCRF.
    """

    # Get rotation matrix for ITRS to GCRS transformation at the given epoch
    # GCRF is an inertial frame, ITRF is a body-fixed frame, so this rotation matrix accounts for Earth's rotation at the given epoch
    # Thus the name of the function is `body_fixed_to_inertial_rotation'
    itrf_to_gcrf_rotation_matrix = earth_rotation_model.body_fixed_to_inertial_rotation(
        input_epoch_et_s
    )

    # Get Earth's rotational velocity in the GCRF frame at the given epoch,
    # which is needed to correctly transform the velocity vector from ITRF to GCRF
    # by accounting for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.
    gcrf_earth_rotational_velocity_rad_s = earth_rotation_model.angular_velocity_in_inertial_frame(
        input_epoch_et_s
    )

    # Rotate the position vector from ITRF to GCRF using the rotation matrix
    output_gcrf_position_m = itrf_to_gcrf_rotation_matrix @ input_itrf_position_m

    output_gcrf_velocity_m_s = None

    if input_itrf_velocity_m_s is not None:
        # Rotate the velocity vector from ITRF to GCRF and account for Earth's rotation using the formula:
        #  v_GCRF = R * v_ITRF + w x r_GCRF
        # where R is the rotation matrix,
        # w is the Earth's rotational velocity in the GCRF frame, and
        # r_GCRF is the position in the GCRF frame.
        # The cross product term accounts for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.

        output_gcrf_velocity_m_s = (
            itrf_to_gcrf_rotation_matrix @ input_itrf_velocity_m_s
            + np.cross(gcrf_earth_rotational_velocity_rad_s, output_gcrf_position_m)
        )

    return output_gcrf_position_m, output_gcrf_velocity_m_s


def process_stream(stream, reverse=False):
    """Read lines from *stream*, convert each epoch, and print transformed state vectors.

    Args:
        stream: An iterable of text lines (file object or sys.stdin).
        reverse: If True, perform ITRF→GCRF conversion instead of GCRF→ITRF.
    """

    load_spice_kernels()
    earth_rotation_model = create_earth_rotation_model()

    for line in stream:
        try:
            parsed = parse_line(line)
        except Exception as exc:
            print(f"Skipping line (parse error): {line.strip()} -- {exc}")
            continue
        if parsed is None:
            continue

        epoch_dt, position_km, velocity_km_s = parsed
        epoch_tdb_s = datetime_to_tdb(epoch_dt)

        # Convert km / km·s⁻¹ → m / m·s⁻¹ for the conversion functions
        position_m = position_km * 1e3
        velocity_m_s = velocity_km_s * 1e3

        if reverse:
            output_position_m, output_velocity_m_s = convert_itrf_to_gcrf_iau(
                earth_rotation_model,
                epoch_tdb_s,
                position_m,
                velocity_m_s,
            )
        else:
            output_position_m, output_velocity_m_s = convert_gcrf_to_itrf_iau(
                earth_rotation_model,
                epoch_tdb_s,
                position_m,
                velocity_m_s,
            )

        # Convert m / m·s⁻¹ → km / km·s⁻¹ for output
        output_position_km = output_position_m / 1e3

        print(epoch_dt.isoformat(), *output_position_km, sep="  ", end="")

        if output_velocity_m_s is not None:
            output_velocity_km_s = output_velocity_m_s / 1e3
            print("  ", *output_velocity_km_s, sep="  ", end="")
        print()


def print_usage():
    """Print the script usage message to standard output."""
    print(
        "Usage: python gcrf_to_itrf_iau.py [-h] [-r] [input_file]\n"
        "\n"
        "Convert satellite state vectors between GCRF and ITRF using the\n"
        "IAU 2006 Earth rotation model.\n"
        "\n"
        "Positional arguments:\n"
        "  input_file    Path to an OEM-style ephemeris file. If omitted,\n"
        "                lines are read from stdin.\n"
        "\n"
        "Options:\n"
        "  -h, --help    Show this help message and exit.\n"
        "  -r            Reverse conversion (ITRF to GCRF instead of GCRF\n"
        "                to ITRF).\n"
        "\n"
        "Input format (one record per line, 7 whitespace- or comma-separated fields):\n"
        "  <ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>\n"
        "\n"
        "Blank lines and lines starting with '#' are skipped."
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
