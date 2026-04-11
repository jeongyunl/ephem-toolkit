#!/usr/bin/env python3

# Read TLE file names from command line arguments and load each TLE file using TudatPy, then print the initial epoch and all the TLE parameters
import math
import sys

import warnings

# Suppress Warnings from urllib3
warnings.filterwarnings("ignore", module="urllib3")

# Suppress SyntaxWarnings from TudatPy
warnings.filterwarnings("ignore", category=SyntaxWarning)

from tudatpy.dynamics import environment
from tudatpy.astro.time_representation import DateTime
from tudatpy.interface import spice


def load_spice_kernels():
    """Load required SPICE kernels for time conversion and Earth orientation."""

    from tudatpy import data

    spice_kernel_files = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        # "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(data.get_spice_kernel_path() + "/" + kernel_file)


def get_tle_epoch(tle):
    """Convert the TLE epoch to a DateTime object."""

    tle_epoch_dt = None

    if True:
        """Use the TLE epoch from the TLE object, which is in ephemeris time (aka TDB),
        and convert it to a DateTime object."""

        # TLE set epoch in seconds from J2000
        tle_epoch_et = tle.get_epoch()

        tle_epoch_utc = spice.get_approximate_utc_from_tdb(tle_epoch_et)
        tle_epoch_dt = DateTime.from_epoch(tle_epoch_utc)
    else:
        """Parse the TLE epoch from the first line of the TLE data,
        which is in the format YYDDD.DDDDDDDD,
        where YY is the last two digits of the year
        and DDD.DDDDDDDD is the day of the year with a fractional portion representing the time of day.
        """

        tle_epoch_year = int(tle.raw_line_1[18:20])

        # Day of the year and fractional portion of the day
        tle_epoch_days = float(tle.raw_line_1[20:32])

        # Convert to seconds since J2000
        # TLE day number starts with a 1, so a day fraction of 1.0 would mean Jan 1st, 0:00.
        if tle_epoch_year < 57:
            tle_epoch_year += 2000
        else:
            tle_epoch_year += 1900

            # TLE day numbering starts with 1, whereas Tudat assumes January 1st to be number 0
        tle_epoch_dt = DateTime(tle_epoch_year, 1, 1, 0, 0, 0.0)
        tle_epoch_dt = tle_epoch_dt.add_days(tle_epoch_days - 1.0)

    return tle_epoch_dt


def main():
    if len(sys.argv) < 2:
        print("Usage: tle_info.py <tle_file_1> <tle_file_2> ...")
        sys.exit(1)

    tle_files = sys.argv[1:]
    print(f"TLE files: {tle_files}\n")

    load_spice_kernels()

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

            tle_epoch_dt = get_tle_epoch(tle)
            tle_epoch_iso = tle_epoch_dt.to_iso_string(number_of_digits_seconds=3)
            print(f"Epoch: {tle_epoch_iso}")

            # B-Star coefficient
            print(f"B* (B-star) Drag Term: {tle.get_b_star()}")

            # Inclination of the orbit in radians
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
            tle_mean_motion_deg_per_min = math.degrees(tle.mean_motion)
            print(f"Mean Motion: {tle_mean_motion_deg_per_min:.2f} degrees per minute")

            # Break the line after each TLE file
            print()

        except Exception as e:
            print(f"Error loading TLE file {tle_file}: {e}")


if __name__ == "__main__":
    main()
