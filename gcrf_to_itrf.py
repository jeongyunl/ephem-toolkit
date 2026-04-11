#!/usr/bin/env python3

import sys

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

import numpy as np
from tudatpy.interface import spice


def print_usage():
    """Print the script usage message to standard output."""

    print(
        "Usage: python gcrf_to_itrf.py [-r] [ <time> <x_km> <y_km> <z_km> [ <vx_km/s> <vy_km/s> <vz_km/s> ] ]"
    )


def load_spice_kernels():
    """Load required SPICE kernels for time conversion and Earth orientation."""

    from tudatpy import data

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


def read_ephemeris():
    """Yield input ephemeris records from command-line arguments or stdin.

    Supported modes:
    - no args: read lines from stdin with `time x y z [vx vy vz]`
    - 4 or 7 args: Read time + position/velocity from command-line arguments

    Yields:
        tuple[str, numpy.ndarray, numpy.ndarray | None]: time string, position vector in km, and
            optional velocity vector in km/s.
    """

    if len(sys.argv) == 1:
        # No command-line data except script name: read time + position/velocity from stdin.
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            tokens = line.split()
            if len(tokens) not in (4, 7):
                print_usage()
                sys.exit(1)
            input_time_string = tokens[0]
            input_position_km = np.array([float(x) for x in tokens[1:4]])
            input_velocity_kms = (
                np.array([float(x) for x in tokens[4:7]]) if len(tokens) == 7 else None
            )
            yield input_time_string, input_position_km, input_velocity_kms
    else:
        # Read time + position/velocity from command-line arguments. Expecting either 4 or 7 arguments after the script name (time + position, optionally followed by velocity).
        input_time_string = sys.argv[1]
        input_position_km = np.array([float(x) for x in sys.argv[2:5]])
        input_velocity_kms = (
            np.array([float(x) for x in sys.argv[5:8]]) if len(sys.argv) == 8 else None
        )
        yield input_time_string, input_position_km, input_velocity_kms


def convert_gcrf_to_itrf(
    earth_rotation_model,
    input_epoch_et,
    input_gcrf_position_km,
    input_gcrf_velocity_kms=None,
):
    """Convert a GCRF position/velocity vector to the ITRF frame.

    Args:
        earth_rotation_model: TudatPy Earth rotation model instance.
        input_epoch_et: Epoch in ephemeris time (aka TDB, Barycentric Dynamical Time).
        input_gcrf_position_km: 3-element numpy array position in km.
        input_gcrf_velocity_kms: Optional 3-element numpy array velocity in km/s.

    Returns:
        tuple[numpy.ndarray, numpy.ndarray | None]: position and optional velocity in ITRF,
            both in kilometers / kilometers per second.
    """

    # Get rotation matrix for GCRS to ITRS transformation at the given epoch
    # GCRF is an inertial frame, ITRF is a body-fixed frame, so this rotation matrix accounts for Earth's rotation at the given epoch
    # Thus the name of the function is `inertial_to_body_fixed_rotation'
    gcrf_to_itrf_rotation_matrix = earth_rotation_model.inertial_to_body_fixed_rotation(
        input_epoch_et
    )

    # Get Earth's rotational velocity in the ITRF frame at the given epoch,
    # which is needed to correctly transform the velocity vector from GCRF to ITRF
    # by accounting for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.
    itrf_earth_rotational_velocity = (
        earth_rotation_model.angular_velocity_in_body_fixed_frame(input_epoch_et)
    )

    # Convert input position from km to m
    input_gcrf_position = input_gcrf_position_km * 1000.0

    # Rotate the position vector from GCRF to ITRF using the rotation matrix
    output_itrf_position = gcrf_to_itrf_rotation_matrix @ input_gcrf_position

    # Convert output position from m back to km
    output_itrf_position_km = output_itrf_position / 1000.0

    output_itrf_velocity_kms = None

    if input_gcrf_velocity_kms is not None:
        input_gcrf_velocity = input_gcrf_velocity_kms * 1000.0  # Convert to m/s

        # Rotate the velocity vector from GCRF to ITRF and account for Earth's rotation using the formula:
        #  v_ITRF = R * v_GCRF - w x r_ITRF
        # where R is the rotation matrix,
        # w is the Earth's rotational velocity in the ITRF frame, and
        # r_ITRF is the position in the ITRF frame.
        # The cross product term accounts for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.

        output_itrf_velocity = (
            gcrf_to_itrf_rotation_matrix @ input_gcrf_velocity
            - np.cross(itrf_earth_rotational_velocity, output_itrf_position)
        )

        # Convert output velocity from m/s back to km/s
        output_itrf_velocity_kms = output_itrf_velocity / 1000.0

    return output_itrf_position_km, output_itrf_velocity_kms


# Function to convert position and velocity from ITRF to GCRF at a given epoch using the Earth rotation model
def convert_itrf_to_gcrf(
    earth_rotation_model,
    input_epoch_et,
    input_itrf_position_km,
    input_itrf_velocity_kms=None,
):
    """Convert an ITRF position/velocity vector to the GCRF frame.

    Args:
        earth_rotation_model: TudatPy Earth rotation model instance.
        input_epoch_et: Epoch in ephemeris time (aka TDB, Barycentric Dynamical Time).
        input_itrf_position_km: 3-element numpy array position in km.
        input_itrf_velocity_kms: Optional 3-element numpy array velocity in km/s.

    Returns:
        tuple[numpy.ndarray, numpy.ndarray | None]: position and optional velocity in GCRF,
            both in kilometers / kilometers per second.
    """

    # Get rotation matrix for ITRS to GCRS transformation at the given epoch
    # GCRF is an inertial frame, ITRF is a body-fixed frame, so this rotation matrix accounts for Earth's rotation at the given epoch
    # Thus the name of the function is `body_fixed_to_inertial_rotation'
    itrf_to_gcrf_rotation_matrix = earth_rotation_model.body_fixed_to_inertial_rotation(
        input_epoch_et
    )

    # Get Earth's rotational velocity in the GCRF frame at the given epoch,
    # which is needed to correctly transform the velocity vector from ITRF to GCRF
    # by accounting for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.
    gcrf_earth_rotational_velocity = (
        earth_rotation_model.angular_velocity_in_inertial_frame(input_epoch_et)
    )

    # Convert input position from km to m
    input_itrf_position = input_itrf_position_km * 1000.0

    # Rotate the position vector from ITRF to GCRF using the rotation matrix
    output_gcrf_position = itrf_to_gcrf_rotation_matrix @ input_itrf_position

    # Convert output position from m back to km
    output_gcrf_position_km = output_gcrf_position / 1000.0

    output_gcrf_velocity_kms = None

    if input_itrf_velocity_kms is not None:
        input_itrf_velocity = input_itrf_velocity_kms * 1000.0  # Convert to m/s

        # Rotate the velocity vector from ITRF to GCRF and account for Earth's rotation using the formula:
        #  v_GCRF = R * v_ITRF + w x r_GCRF
        # where R is the rotation matrix,
        # w is the Earth's rotational velocity in the GCRF frame, and
        # r_GCRF is the position in the GCRF frame.
        # The cross product term accounts for the fact that the ITRF frame is rotating with respect to the inertial GCRF frame.

        output_gcrf_velocity = (
            itrf_to_gcrf_rotation_matrix @ input_itrf_velocity
            + np.cross(gcrf_earth_rotational_velocity, output_gcrf_position)
        )

        # Convert output velocity from m/s back to km/s
        output_gcrf_velocity_kms = output_gcrf_velocity / 1000.0

    return output_gcrf_position_km, output_gcrf_velocity_kms


def main():
    """Parse inputs, perform frame conversion, and print transformed outputs."""

    # Check options command line arguments
    # See if -r option was given to specify reverse conversion (ITRF to GCRF instead of GCRF to ITRF) and set a flag accordingly
    set_reverse_conversion = False
    if len(sys.argv) > 1 and sys.argv[1] == "-r":
        set_reverse_conversion = True
        sys.argv.pop(1)  # Remove the -r option from the arguments list

    if len(sys.argv) not in (1, 5, 8):
        print_usage()
        sys.exit(1)

    load_spice_kernels()

    # Create Earth rotation model

    earth_rotation_model = create_earth_rotation_model()

    # Read input ephemeris data (time + position/velocity) from command-line arguments or stdin, convert each entry, and print the results. Expecting either 4 or 7 arguments per entry (time + position, optionally followed by velocity).

    # Flag to track if we processed any input data, so we can print usage and exit if no valid data was provided
    processed_any = False

    for input_time_string, input_position_km, input_velocity_kms in read_ephemeris():
        processed_any = True

        # Convert input time string to ephemeris time (TDB) using SPICE function
        input_epoch_et = spice.convert_date_string_to_ephemeris_time(input_time_string)

        # Call the reference frame conversion function
        if set_reverse_conversion:
            output_position_km, output_velocity_kms = convert_itrf_to_gcrf(
                earth_rotation_model,
                input_epoch_et,
                input_position_km,
                input_velocity_kms,
            )
        else:
            output_position_km, output_velocity_kms = convert_gcrf_to_itrf(
                earth_rotation_model,
                input_epoch_et,
                input_position_km,
                input_velocity_kms,
            )

        print(
            input_time_string,
            output_position_km[0],
            output_position_km[1],
            output_position_km[2],
            end="",
        )

        if output_velocity_kms is not None:
            print(
                " ",
                output_velocity_kms[0],
                output_velocity_kms[1],
                output_velocity_kms[2],
                end="",
            )
        print()

    if not processed_any:
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
