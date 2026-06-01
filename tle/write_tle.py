#!/usr/bin/env python3

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from common.tle import Tle, write_tle


def print_tle_summary(args, line1, line2):
    print("TLE data elements summary:")
    print(f"  output: {args.output}")
    print(f"  name: {args.name.strip() if args.name else '(none)'}")
    print("  line 1:")
    print(f"    satellite-number: {args.satellite_number}")
    print(f"    classification: {args.classification}")
    print(f"    int-designator-year: {args.int_designator_year}")
    print(f"    int-designator-launch-number: {args.int_designator_launch_number}")
    print(f"    int-designator-piece: {args.int_designator_piece}")
    print(f"    epoch-year: {args.epoch_year}")
    print(f"    epoch-day: {args.epoch_day}")
    print(f"    mean-motion-first-derivative: {args.mean_motion_first_derivative}")
    print(f"    mean-motion-second-derivative: {args.mean_motion_second_derivative}")
    print(f"    bstar: {args.bstar}")
    print(f"    ephemeris-type: {args.ephemeris_type}")
    print(f"    element-set-number: {args.element_set_number}")
    print("  line 2:")
    print(f"    inclination-deg: {args.inclination_deg}")
    print(f"    raan-deg: {args.raan_deg}")
    print(f"    eccentricity: {args.eccentricity}")
    print(f"    arg-perigee-deg: {args.arg_perigee_deg}")
    print(f"    mean-anomaly-deg: {args.mean_anomaly_deg}")
    print(f"    mean-motion-rev-per-day: {args.mean_motion_rev_per_day}")
    print(f"    revolution-number-at-epoch: {args.revolution_number_at_epoch}")
    print("  compiled:")
    print(f"    line1: {line1}")
    print(f"    line2: {line2}")
    print()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Build a Two-Line Element (TLE) set from explicit element values and "
            "write it to a file or stdout."
        )
    )

    parser.add_argument(
        "--output",
        metavar="<file|->",
        default="-",
        help=(
            "Output TLE file path. Use '-' to print the generated TLE text to stdout "
            "instead of writing a file (default: '-')."
        ),
    )
    parser.add_argument(
        "--name",
        metavar="<name>",
        default="",
        help=("Optional satellite name line written above TLE line 1 " "(default: none)."),
    )

    # Line 1 fields
    parser.add_argument(
        "--satellite-number",
        type=int,
        required=True,
        metavar="<0..99999>",
        help="NORAD catalog number (0 to 99999).",
    )
    parser.add_argument(
        "--classification",
        required=True,
        choices=["U", "C", "S"],
        metavar="<U|C|S>",
        help="Classification code: U (unclassified), C (classified), or S (secret).",
    )
    parser.add_argument(
        "--int-designator-year",
        type=int,
        required=True,
        metavar="<0..99>",
        help="International designator launch year (2-digit).",
    )
    parser.add_argument(
        "--int-designator-launch-number",
        type=int,
        required=True,
        metavar="<0..999>",
        help="International designator launch number of year.",
    )
    parser.add_argument(
        "--int-designator-piece",
        required=True,
        metavar="<piece>",
        help="International designator piece identifier (1 to 3 characters).",
    )
    parser.add_argument(
        "--epoch-year",
        type=int,
        required=True,
        metavar="<0..99>",
        help="Epoch year (2-digit).",
    )
    parser.add_argument(
        "--epoch-day",
        type=float,
        required=True,
        metavar="<day.fraction>",
        help="Epoch day-of-year with fractional day, for example 151.29745462.",
    )
    parser.add_argument(
        "--mean-motion-first-derivative",
        type=float,
        required=True,
        metavar="<value>",
        help="First derivative of mean motion in TLE decimal notation.",
    )
    parser.add_argument(
        "--mean-motion-second-derivative",
        required=True,
        metavar="<tle-exp>",
        help=(
            "Second derivative of mean motion in compact TLE exponential notation, "
            "for example 00000+0 or 29661-4."
        ),
    )
    parser.add_argument(
        "--bstar",
        required=True,
        metavar="<tle-exp>",
        help="BSTAR drag term in compact TLE exponential notation.",
    )
    parser.add_argument(
        "--ephemeris-type",
        type=int,
        required=True,
        metavar="<0..9>",
        help="Ephemeris type digit.",
    )
    parser.add_argument(
        "--element-set-number",
        type=int,
        required=True,
        metavar="<0..9999>",
        help="Element set number.",
    )

    # Line 2 fields
    parser.add_argument(
        "--inclination-deg",
        type=float,
        required=True,
        metavar="<deg>",
        help="Inclination in degrees.",
    )
    parser.add_argument(
        "--raan-deg",
        type=float,
        required=True,
        metavar="<deg>",
        help="Right ascension of ascending node in degrees.",
    )
    parser.add_argument(
        "--eccentricity",
        type=float,
        required=True,
        metavar="<0.0..1.0)",
        help="Eccentricity in decimal form (converted to 7-digit TLE field).",
    )
    parser.add_argument(
        "--arg-perigee-deg",
        type=float,
        required=True,
        metavar="<deg>",
        help="Argument of perigee in degrees.",
    )
    parser.add_argument(
        "--mean-anomaly-deg",
        type=float,
        required=True,
        metavar="<deg>",
        help="Mean anomaly in degrees.",
    )
    parser.add_argument(
        "--mean-motion-rev-per-day",
        type=float,
        required=True,
        metavar="<rev/day>",
        help="Mean motion in revolutions per day.",
    )
    parser.add_argument(
        "--revolution-number-at-epoch",
        type=int,
        required=True,
        metavar="<0..99999>",
        help="Revolution number at epoch.",
    )

    args = parser.parse_args()

    if not (0 <= args.satellite_number <= 99999):
        parser.error("--satellite-number must be in [0, 99999]")
    if not (0 <= args.int_designator_year <= 99):
        parser.error("--int-designator-year must be in [0, 99]")
    if not (0 <= args.int_designator_launch_number <= 999):
        parser.error("--int-designator-launch-number must be in [0, 999]")
    if not (1 <= len(args.int_designator_piece.strip()) <= 3):
        parser.error("--int-designator-piece must contain 1 to 3 characters")
    if not (0 <= args.epoch_year <= 99):
        parser.error("--epoch-year must be in [0, 99]")
    if not (0.0 <= args.epoch_day < 367.0):
        parser.error("--epoch-day must be in [0.0, 367.0)")
    if not (0 <= args.ephemeris_type <= 9):
        parser.error("--ephemeris-type must be in [0, 9]")
    if not (0 <= args.element_set_number <= 9999):
        parser.error("--element-set-number must be in [0, 9999]")
    if not (0.0 <= args.eccentricity < 1.0):
        parser.error("--eccentricity must be in [0.0, 1.0)")
    if not (0 <= args.revolution_number_at_epoch <= 99999):
        parser.error("--revolution-number-at-epoch must be in [0, 99999]")

    return args


def build_tle_data(args):
    return Tle(
        name=args.name,
        satellite_number=args.satellite_number,
        classification=args.classification,
        int_designator_year=args.int_designator_year,
        int_designator_launch_number=args.int_designator_launch_number,
        int_designator_piece=args.int_designator_piece,
        epoch_year=args.epoch_year,
        epoch_day=args.epoch_day,
        mean_motion_first_derivative=args.mean_motion_first_derivative,
        mean_motion_second_derivative=args.mean_motion_second_derivative,
        bstar=args.bstar,
        ephemeris_type=args.ephemeris_type,
        element_set_number=args.element_set_number,
        inclination_deg=args.inclination_deg,
        raan_deg=args.raan_deg,
        eccentricity=args.eccentricity,
        arg_perigee_deg=args.arg_perigee_deg,
        mean_anomaly_deg=args.mean_anomaly_deg,
        mean_motion_rev_per_day=args.mean_motion_rev_per_day,
        revolution_number_at_epoch=args.revolution_number_at_epoch,
    )


def main():
    try:
        args = parse_arguments()
        tle_data = build_tle_data(args)

        if args.output == "-":
            line1, line2 = write_tle(sys.stdout, tle_data)
            print_tle_summary(args, line1, line2)
            print("Printed TLE to stdout")
        else:
            with open(args.output, "w") as output_file:
                line1, line2 = write_tle(output_file, tle_data)

            print_tle_summary(args, line1, line2)
            print(f"Saved TLE file: {args.output}")

    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
