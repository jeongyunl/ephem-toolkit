#!/usr/bin/env python3

# Read TLE file names from command line arguments and load each TLE file using TudatPy, then print the initial epoch and all the TLE parameters
import math
import sys

# Suppress Warnings from urllib3
import warnings

warnings.filterwarnings("ignore", module="urllib3")

from tudatpy.dynamics import environment
from tudatpy.astro.time_representation import DateTime


def main():
    if len(sys.argv) < 2:
        print("Usage: tle_info.py <tle_file_1> <tle_file_2> ...")
        sys.exit(1)

    tle_files = sys.argv[1:]
    print(f"TLE files: {tle_files}\n")

    for tle_file in tle_files:
        print(f"Loading TLE file: {tle_file}")

        try:
            # Load the TLE file into a variable
            with open(tle_file, "r") as f:
                tle_data = f.read()
                f.close()
            tle_lines = tle_data.splitlines()
            # Load the TLE file using TudatPy
            tle = environment.Tle(tle_lines[0], tle_lines[1])

            # Print the TLE parameters

            # TLE set epoch in seconds from J2000
            tle_epoch_et = tle.get_epoch()
            tle_epoch_dt = DateTime.from_epoch(tle_epoch_et)
            tle_epoch_iso = tle_epoch_dt.iso_string(number_of_digits_seconds=3)
            print(f"Epoch: {tle_epoch_iso}")

            # B-Star coefficient
            print(f"B* (B-star) Drag Term: {tle.get_b_star()}")

            # Inclination of the orbit in radians
            math.degrees
            tle_inclination_deg = math.degrees(tle.get_inclination())
            print(f"Inclination: {tle_inclination_deg:.2f} degrees")

            # Right ascension of the orbit in radians
            tle_right_ascension_deg = math.degrees(tle.get_right_ascension())
            print(f"Right Ascension: {tle_right_ascension_deg:.2f} degrees")

            # Eccentricity of the orbit
            print(f"Eccentricity: {tle.get_eccentricity()}")

            # Argument of perigee in radians
            tle_arg_of_perigee_deg = math.degrees(tle.get_arg_of_perigee())
            print(f"Argument of Perigee: {tle_arg_of_perigee_deg:.2f} degrees")

            # Mean anomaly in radians
            tle_mean_anomaly_deg = math.degrees(tle.get_mean_anomaly())
            print(f"Mean Anomaly: {tle_mean_anomaly_deg:.2f} degrees")

            # Mean motion in radians per minute
            tle_mean_motion_deg_per_min = math.degrees(tle.get_mean_motion())
            print(f"Mean Motion: {tle_mean_motion_deg_per_min:.2f} degrees per minute")

            # Break the line after each TLE file
            print()

        except Exception as e:
            print(f"Error loading TLE file {tle_file}: {e}")


if __name__ == "__main__":
    main()
