#!/usr/bin/env python3

import sys

# Suppress Warnings from TudatPy
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

import numpy as np
from tudatpy.interface import spice


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
    # print("gcrf_to_itrf_rotation_matrix", gcrf_to_itrf_rotation_matrix)

    itrf_earth_rotational_velocity = (
        earth_rotation_model.angular_velocity_in_inertial_frame(input_epoch_et)
    )
    # print("itrf_earth_rotational_velocity", itrf_earth_rotational_velocity)

    # print("input_gcrf_position_km", input_gcrf_position_km)

    input_gcrf_position = input_gcrf_position_km * 1000.0  # Convert to meters
    # print("input_gcrf_position", input_gcrf_position)

    output_itrf_position = gcrf_to_itrf_rotation_matrix @ input_gcrf_position
    # print("output_itrf_position", output_itrf_position)

    output_itrf_position_km = (
        output_itrf_position / 1000.0
    )  # Convert back to kilometers

    output_itrf_velocity_kms = None

    if input_gcrf_velocity_kms is not None:
        input_gcrf_velocity = input_gcrf_velocity_kms * 1000.0  # Convert to m/s
        # print("input_gcrf_velocity", input_gcrf_velocity)

        output_itrf_velocity = (
            gcrf_to_itrf_rotation_matrix @ input_gcrf_velocity
            - np.cross(itrf_earth_rotational_velocity, output_itrf_position)
        )
        # print("output_itrf_velocity", output_itrf_velocity)
        output_itrf_velocity_kms = output_itrf_velocity / 1000.0  # Convert back to km/s

    return output_itrf_position_km, output_itrf_velocity_kms


def main():

    # Read time, 3d position and optionally 3d velocity from command line arguments

    if len(sys.argv) != 5 and len(sys.argv) != 8:
        print(
            "Usage: python gcrf_to_itrf.py <time> <x_km> <y_km> <z_km> [ <vx_km/s> <vy_km/s> <vz_km/s> ]"
        )
        sys.exit(1)

    # Read time string then convert to ephemeris time using TudatPy's Spice interface

    input_time_string = sys.argv[1]

    load_spice_kernels()

    input_epoch_et = spice.convert_date_string_to_ephemeris_time(input_time_string)

    # Read position and velocity from command line arguments

    input_gcrf_position_km = np.array([float(x) for x in sys.argv[2:5]])
    input_gcrf_velocity_kms = None
    if len(sys.argv) == 8:
        input_gcrf_velocity_kms = np.array([float(x) for x in sys.argv[5:8]])

    # Create Earth rotation model

    earth_rotation_model = create_earth_rotation_model()

    # Call the conversion function

    output_itrf_position_km, output_itrf_velocity_kms = convert_gcrf_to_itrf(
        earth_rotation_model,
        input_epoch_et,
        input_gcrf_position_km,
        input_gcrf_velocity_kms,
    )

    print(
        input_time_string,
        output_itrf_position_km[0],
        output_itrf_position_km[1],
        output_itrf_position_km[2],
        end="",
    )

    if output_itrf_velocity_kms is not None:
        print(
            " ",
            output_itrf_velocity_kms[0],
            output_itrf_velocity_kms[1],
            output_itrf_velocity_kms[2],
            end="",
        )
    print()


if __name__ == "__main__":
    main()
