#!/usr/bin/env python3

import sys

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

import numpy as np
from tudatpy.interface import spice


def print_usage():
    print(
        "Usage: python gcrf_to_itrf.py [-r] [ <time> <x_km> <y_km> <z_km> [ <vx_km/s> <vy_km/s> <vz_km/s> ] ]"
    )


# Load necessary SPICE kernels for time conversion and Earth rotation model
def load_spice_kernels():
    from tudatpy import data

    spice_kernel_files = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(data.get_spice_kernel_path() + "/" + kernel_file)


# Create Earth rotation model using TudatPy's environment setup utilities
def create_earth_rotation_model():
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


# Function to convert position and velocity from GCRF to ITRF at a given epoch using the Earth rotation model
def convert_gcrf_to_itrf(
    earth_rotation_model,
    input_epoch_et,
    input_gcrf_position_km,
    input_gcrf_velocity_kms=None,
):
    # Get rotation matrix for GCRS to ITRS transformation at the given epoch
    # GCRF is an inertial frame, ITRF is a body-fixed frame, so this rotation matrix accounts for Earth's rotation at the given epoch
    # Thus the name of the function is `inertial_to_body_fixed_rotation'
    gcrf_to_itrf_rotation_matrix = earth_rotation_model.inertial_to_body_fixed_rotation(
        input_epoch_et
    )

    itrf_earth_rotational_velocity = (
        earth_rotation_model.angular_velocity_in_body_fixed_frame(input_epoch_et)
    )

    input_gcrf_position = input_gcrf_position_km * 1000.0  # Convert to meters
    output_itrf_position = gcrf_to_itrf_rotation_matrix @ input_gcrf_position

    output_itrf_position_km = (
        output_itrf_position / 1000.0
    )  # Convert back to kilometers

    output_itrf_velocity_kms = None

    if input_gcrf_velocity_kms is not None:
        input_gcrf_velocity = input_gcrf_velocity_kms * 1000.0  # Convert to m/s

        output_itrf_velocity = (
            gcrf_to_itrf_rotation_matrix @ input_gcrf_velocity
            - np.cross(itrf_earth_rotational_velocity, output_itrf_position)
        )
        output_itrf_velocity_kms = output_itrf_velocity / 1000.0  # Convert back to km/s

    return output_itrf_position_km, output_itrf_velocity_kms


# Function to convert position and velocity from ITRF to GCRF at a given epoch using the Earth rotation model
def convert_itrf_to_gcrf(
    earth_rotation_model,
    input_epoch_et,
    input_itrf_position_km,
    input_itrf_velocity_kms=None,
):
    # Get rotation matrix for ITRS to GCRS transformation at the given epoch
    # GCRF is an inertial frame, ITRF is a body-fixed frame, so this rotation matrix accounts for Earth's rotation at the given epoch
    # Thus the name of the function is `body_fixed_to_inertial_rotation'
    itrf_to_gcrf_rotation_matrix = earth_rotation_model.body_fixed_to_inertial_rotation(
        input_epoch_et
    )

    gcrf_earth_rotational_velocity = (
        earth_rotation_model.angular_velocity_in_inertial_frame(input_epoch_et)
    )

    input_itrf_position = input_itrf_position_km * 1000.0  # Convert to meters
    output_gcrf_position = itrf_to_gcrf_rotation_matrix @ input_itrf_position

    output_gcrf_position_km = (
        output_gcrf_position / 1000.0
    )  # Convert back to kilometers

    output_gcrf_velocity_kms = None

    if input_itrf_velocity_kms is not None:
        input_itrf_velocity = input_itrf_velocity_kms * 1000.0  # Convert to m/s

        output_gcrf_velocity = (
            itrf_to_gcrf_rotation_matrix @ input_itrf_velocity
            + np.cross(gcrf_earth_rotational_velocity, output_gcrf_position)
        )
        output_gcrf_velocity_kms = output_gcrf_velocity / 1000.0  # Convert back to km/s

    return output_gcrf_position_km, output_gcrf_velocity_kms


def main():

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
        # Convert input time string to ephemeris time (seconds past J2000) using SPICE function
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
