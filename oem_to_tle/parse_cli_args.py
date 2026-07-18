"""Command-line argument parsing for TLE estimation from OEM state vectors.

Provides argument parser configuration for the oem_to_tle workflow, including
input/output file paths, TLE metadata fields (satellite number, classification,
international designator), and refinement method selection.

References:
    CCSDS Recommended Standard for Orbit Data Messages (OEM).
    TLE format specification: https://celestrak.org/NORAD/documentation/tle-fmt.php
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

Timestamp = float
"""POSIX timestamp (seconds since 1970-01-01 UTC) used as the epoch type throughout the oem_to_tle pipeline."""

# Add parent directory to path to enable importing common module
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.oem as oem

# ===================================================================
# Command-line argument parsing
# ===================================================================


def parse_cli_arguments() -> argparse.Namespace:
    """Parse command-line arguments for TLE estimation workflow.

    Configures argument parser for converting OEM state vectors to TLE format.
    Accepts input/output file paths, TLE metadata fields (satellite number,
    classification, international designator, ephemeris type, element set number,
    BSTAR drag term, mean motion derivative, revolution number), and refinement
    method selection (none, cartesian, or keplerian).

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with the following attributes:

        - input : str
            Input OEM file path or '-' for stdin.
        - output : str
            Output TLE file path or '-' for stdout.
        - name : str
            Satellite name for TLE line 0.
        - satellite_number : int
            NORAD catalog number (0-99999).
        - classification : str
            Classification code ('U', 'C', or 'S').
        - int_designator_year : int
            International designator launch year (0-99).
        - int_designator_launch_number : int
            International designator launch number (0-999).
        - int_designator_piece : str
            International designator piece identifier.
        - ephemeris_type : int
            Ephemeris type (1=SGP, 2=SGP4, 3=SDP4, 4=SGP8, 5=SDP8).
        - element_set_number : int
            Element set number (0-9999).
        - bstar : str
            BSTAR drag term in TLE exponential format.
        - mean_motion_second_derivative : str
            Second derivative of mean motion in TLE exponential format.
        - revolution_number_at_epoch : int
            Revolution number at epoch (0-99999).
        - refinement : str
            Refinement method ('none', 'cartesian', or 'keplerian').

    Notes
    -----
    Default values produce a valid TLE with placeholder metadata suitable for
    testing. For operational use, provide accurate satellite identification and
    orbital parameters.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Read a set of OEM-like state vectors, estimate TLE element values, "
            "and write the resulting TLE to a file or stdout."
        )
    )

    # Input/output file paths
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.dat>",
        help=(
            "Input OEM-like state-vector file path. Use '-' or omit to read from stdin "
            "(default: '-')."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help=(
            "Output TLE file path (default: '-'). "
            "Use '-' to print TLE text to stdout."
        ),
    )

    # TLE line 0 (satellite name)
    parser.add_argument(
        "--name",
        metavar="<name>",
        default="",
        help="Optional satellite name written above line 1.",
    )

    # TLE line 1 fields
    parser.add_argument(
        "--satellite-number",
        type=int,
        default=99999,
        metavar="<0..99999>",
        help="NORAD satellite number for the generated command (default: 99999).",
    )
    parser.add_argument(
        "--classification",
        choices=["U", "C", "S"],
        default="U",
        metavar="<U|C|S>",
        help="Classification code for the generated command (default: U).",
    )
    parser.add_argument(
        "--int-designator-year",
        type=int,
        default=0,
        metavar="<0..99>",
        help="International designator launch year (default: 0).",
    )
    parser.add_argument(
        "--int-designator-launch-number",
        type=int,
        default=0,
        metavar="<0..999>",
        help="International designator launch number (default: 0).",
    )
    parser.add_argument(
        "--int-designator-piece",
        default="A",
        metavar="<piece>",
        help="International designator piece identifier (default: A).",
    )
    parser.add_argument(
        "--ephemeris-type",
        type=int,
        default=0,
        metavar="<0..9>",
        help="Ephemeris type value for generated command (default: 0).",
    )
    parser.add_argument(
        "--element-set-number",
        type=int,
        default=1,
        metavar="<0..9999>",
        help="Element set number for generated command (default: 1).",
    )
    parser.add_argument(
        "--bstar",
        default="00000+0",
        metavar="<tle-exp>",
        help="BSTAR drag term for generated command (default: 00000+0).",
    )
    parser.add_argument(
        "--mean-motion-second-derivative",
        default="00000+0",
        metavar="<tle-exp>",
        help="Second derivative of mean motion for generated command (default: 00000+0).",
    )
    parser.add_argument(
        "--revolution-number-at-epoch",
        type=int,
        default=0,
        metavar="<0..99999>",
        help="Revolution number at epoch for generated command (default: 0).",
    )

    # TLE refinement options
    parser.add_argument(
        "--refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        help=(
            "Refinement method for matching TLE elements to the epoch state. "
            "'cartesian' (default): minimize SGP4 Cartesian state residual "
            "(requires tudatpy). "
            "'keplerian': minimize osculating Keplerian element residual via "
            "common.convert_tle.tle_to_osculating_keplerian (no SGP4 needed). "
            "'none': skip refinement entirely."
        ),
    )
    return parser.parse_args()
