#!/usr/bin/env python3
"""Display TLE parameters and derived orbital elements for one or more TLE files.

Reads TLE files provided as CLI arguments, loads each using TudatPy's SGP4
ephemeris, and prints the epoch, TLE parameters, Cartesian state, and
osculating Keplerian elements at the reference epoch.

References:
    Curtis, H.D. "Orbital Mechanics for Engineering Students", Chapter 4.
    Vallado, D.A. "Fundamentals of Astrodynamics and Applications".
"""

from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

from tudatpy.astro.element_conversion import KeplerianElementIndices
from tudatpy.astro.time_representation import DateTime
from tudatpy.dynamics import environment_setup
from tudatpy.interface import spice

# Suppress warnings from urllib3
warnings.filterwarnings("ignore", module="urllib3")

# Suppress SyntaxWarnings from TudatPy
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Support direct execution from the bin directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.common as common
import common.kepler as kepler

# ===================================================================
# SPICE Kernel Management
# ===================================================================


def load_spice_kernels() -> None:
    """Load required SPICE kernels for time conversion and Earth orientation.

    Loads the NAIF leapseconds kernel and planetary constants kernel
    required for accurate time conversions and Earth orientation data.

    Returns
    -------
    None
    """
    spice_kernel_files: list[str] = [
        "naif0012.tls",
        "pck00011.tpc",
    ]
    for kernel_file in spice_kernel_files:
        spice.load_kernel(common.get_spice_kernel_path() + "/" + kernel_file)


# ===================================================================
# TLE Epoch Conversion
# ===================================================================


def get_tle_epoch(tle: object) -> tuple[DateTime, float]:
    """Convert the TLE epoch to a TudatPy DateTime object.

    Parameters
    ----------
    tle : object
        TudatPy TLE object exposing ``reference_epoch``.

    Returns
    -------
    tuple[DateTime, float]
        Tuple of (tle_epoch_dt, tle_epoch_tdb) where tle_epoch_dt is a
        TudatPy DateTime object and tle_epoch_tdb is the epoch in TDB
        seconds since J2000.
    """
    tle_epoch_tdb: float = tle.reference_epoch
    tle_epoch_utc: str = spice.get_approximate_utc_from_tdb(tle_epoch_tdb)
    tle_epoch_dt: DateTime = DateTime.from_epoch(tle_epoch_utc)

    return tle_epoch_dt, tle_epoch_tdb


# ===================================================================
# Main Entry Point
# ===================================================================


def main() -> None:
    """Print TLE parameters and derived orbital elements for each TLE file.

    Reads TLE file paths from ``sys.argv``, loads each via TudatPy SGP4,
    and prints the epoch, TLE fields, Cartesian state, and osculating
    Keplerian elements at the reference epoch.
    """
    if len(sys.argv) < 2:
        print("Usage: tle_info.py <tle_file_1> <tle_file_2> ...", file=sys.stderr)
        sys.exit(1)

    tle_files: list[str] = sys.argv[1:]
    print(f"TLE files: {tle_files}\n")

    load_spice_kernels()

    bodies_to_create: list[str] = ["Earth"]
    global_frame_origin: str = "Earth"
    global_frame_orientation: str = "J2000"
    body_settings: dict[str, object] = environment_setup.get_default_body_settings(
        bodies_to_create, global_frame_origin, global_frame_orientation
    )

    bodies: object = environment_setup.create_system_of_bodies(body_settings)
    earth_gravitational_parameter: float = bodies.get("Earth").gravitational_parameter

    for tle_file in tle_files:
        print(f"Loading TLE file: {tle_file}")

        try:
            with open(tle_file, "r", encoding="utf-8") as file_handle:
                tle_data: str = file_handle.read()

            tle_lines: list[str] = tle_data.splitlines()[-2:]

            tle_ephemeris_settings: object = environment_setup.ephemeris.sgp4(
                tle_lines[0], tle_lines[1]
            )
            tle_ephemeris: object = environment_setup.create_body_ephemeris(
                tle_ephemeris_settings, body_name=tle_file
            )
            tle: object = tle_ephemeris.tle

            print(f"NORAD catalog number: {tle.norad_catalog_number}")
            print(f"Element set number: {tle.element_set_number}")
            print(f"Revolution number at epoch: {tle.revolution_number_at_epoch}")

            tle_epoch_dt: DateTime
            tle_epoch_tdb: float
            tle_epoch_dt, tle_epoch_tdb = get_tle_epoch(tle)
            tle_epoch_iso: str = tle_epoch_dt.to_iso_string(number_of_digits_seconds=3)
            print(f"Epoch: {tle_epoch_iso}")

            print(f"B* (B-star) Drag Term: {tle.b_star}")

            tle_inclination_deg: float = math.degrees(tle.inclination)
            print(f"Inclination: {tle_inclination_deg:.2f} degrees")

            tle_right_ascension_deg: float = math.degrees(tle.right_ascension)
            print(f"Right Ascension: {tle_right_ascension_deg:.2f} degrees")

            print(f"Eccentricity: {tle.eccentricity}")

            tle_argument_of_perigee_deg: float = math.degrees(tle.argument_of_perigee)
            print(f"Argument of Perigee: {tle_argument_of_perigee_deg:.2f} degrees")

            tle_mean_anomaly_deg: float = math.degrees(tle.mean_anomaly)
            print(f"Mean Anomaly: {tle_mean_anomaly_deg:.2f} degrees")

            tle_mean_motion_deg_per_min: float = math.degrees(tle.mean_motion)
            print(f"Mean Motion: {tle_mean_motion_deg_per_min:.2f} degrees per minute")

            tle_mean_motion_rev_per_day: float = float(tle.raw_line_2[52:63])
            print(f"Mean Motion: {tle_mean_motion_rev_per_day:.2f} revolutions per day")

            tle_mean_motion_first_derivative_deg_per_min2: float = math.degrees(
                tle.mean_motion_first_derivative
            )
            print(
                f"Mean Motion First Derivative: {tle_mean_motion_first_derivative_deg_per_min2:.2f} degrees per minute²"
            )

            tle_mean_motion_second_derivative_deg_per_min2: float = math.degrees(
                tle.mean_motion_second_derivative
            )
            print(
                f"Mean Motion Second Derivative: {tle_mean_motion_second_derivative_deg_per_min2:.2f} degrees per minute²"
            )

            cartesian_state_j2000: object = tle_ephemeris.cartesian_state(tle_epoch_tdb)
            print(
                f"Cartesian state at initial epoch:\n{cartesian_state_j2000[0:3]/1000} km\n{cartesian_state_j2000[3:6]/1000} km/s"
            )

            keplerian_state: object = kepler.cartesian_to_keplerian(
                cartesian_state_j2000, earth_gravitational_parameter
            )

            print(f"Keplerian state at initial epoch:")

            semi_major_axis_km: float = (
                keplerian_state[KeplerianElementIndices.semi_major_axis_index] / 1000
            )
            print(f"\tSemi-major axis: {semi_major_axis_km:.2f} km")

            eccentricity: float = keplerian_state[
                KeplerianElementIndices.eccentricity_index
            ]
            print(f"\tEccentricity: {eccentricity:.6f}")

            inclination_deg: float = math.degrees(
                keplerian_state[KeplerianElementIndices.inclination_index]
            )
            print(f"\tInclination: {inclination_deg:.2f} degrees")

            argument_of_perigee_deg: float = math.degrees(
                keplerian_state[KeplerianElementIndices.argument_of_periapsis_index]
            )
            print(f"\tArgument of Perigee: {argument_of_perigee_deg:.2f} degrees")

            longitude_of_ascending_node_deg: float = math.degrees(
                keplerian_state[
                    KeplerianElementIndices.longitude_of_ascending_node_index
                ]
            )
            print(
                f"\tLongitude of Ascending Node: {longitude_of_ascending_node_deg:.2f} degrees"
            )

            true_anomaly_deg: float = math.degrees(
                keplerian_state[KeplerianElementIndices.true_anomaly_index]
            )
            print(f"\tTrue Anomaly: {true_anomaly_deg:.2f} degrees")

            print()

        except Exception as error:
            print(f"Error loading TLE file {tle_file}: {error}")


if __name__ == "__main__":
    main()
