"""CLI argument parsing for the OEM-to-OMM conversion command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ephem_toolkit.core.consts as consts

FIT_SPAN_S: float = 7200.0


def report_error(message: str, exit_code: int = 1) -> None:
    """Report an error message to stderr and exit."""
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for OEM to OMM conversion."""
    parser = argparse.ArgumentParser(
        description="Convert OEM state vectors to Keplerian elements or OMM."
    )
    parser.add_argument(
        "oem_file",
        help='Path to input CCSDS OEM file (use "-" to read from stdin)',
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="<file|->",
        default="-",
        help="Save fitted Keplerian elements in OMM format to the specified file. Use '-' to print to stdout.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed debug information to stderr",
    )
    parser.add_argument(
        "--mu",
        type=float,
        default=consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
        metavar="<value>",
        dest="mu_m3_s2",
        help=(
            "Gravitational parameter (m³/s²). "
            f"Default: {consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2:.6e} (Earth WGS-84)."
        ),
    )
    parser.add_argument(
        "--fit-span",
        type=float,
        default=2.0,
        metavar="<hours>",
        dest="fit_span_hours",
        help="Maximum arc span in hours for --kepler fit (default: 2.0).",
    )
    parser.add_argument(
        "--kepler",
        action="store_true",
        help=(
            "Fit osculating Keplerian elements to the first 2 hours of OEM states "
            "using two-body (Kepler) propagation."
        ),
    )
    parser.add_argument(
        "--mean-kepler",
        action="store_true",
        dest="mean_kepler",
        help=(
            "Fit mean Keplerian elements to the first 2 hours of OEM states "
            "using J2 secular propagation."
        ),
    )
    parser.add_argument(
        "--tle",
        action="store_true",
        default=True,
        help=(
            "Fit TLE mean elements (SGP4-compatible) to the OEM states."
        ),
    )
    parser.add_argument(
        "--object-name",
        metavar="<name>",
        default="",
        help="OBJECT_NAME: Spacecraft name for OMM output.",
    )
    parser.add_argument(
        "--object-id",
        metavar="<YYYY-NNNP>",
        default="",
        dest="object_id",
        help="OBJECT_ID: International designator (e.g., 1998-067A) for OMM output.",
    )
    parser.add_argument(
        "--tle-refinement",
        choices=["none", "cartesian", "keplerian"],
        default="cartesian",
        metavar="<none|cartesian|keplerian>",
        dest="tle_refinement",
        help=(
            "Refinement method for TLE fitting (used with --tle mode)."
        ),
    )
    parser.add_argument(
        "--tle-norad-cat-id",
        type=int,
        default=0,
        metavar="<0..99999>",
        dest="tle_norad_cat_id",
        help="NORAD_CAT_ID: NORAD Catalog Number (default: 0, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-classification-type",
        choices=["U", "C", "S"],
        default="U",
        metavar="<U|C|S>",
        dest="tle_classification_type",
        help="CLASSIFICATION_TYPE: U=Unclassified, C=Classified, S=Secret (default: U, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-ephemeris-type",
        type=int,
        default=2,
        metavar="<0..9>",
        dest="tle_ephemeris_type",
        help="EPHEMERIS_TYPE: 0=SGP, 2=SGP4, 4=SGP4-XP, 6=SP (default: 2, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-element-set-no",
        type=int,
        default=999,
        metavar="<0..9999>",
        dest="tle_element_set_no",
        help="ELEMENT_SET_NO: Element set number for this satellite (default: 999, used with --tle mode).",
    )
    parser.add_argument(
        "--tle-rev-at-epoch",
        type=int,
        default=0,
        metavar="<0..99999>",
        dest="tle_rev_at_epoch",
        help="REV_AT_EPOCH: Revolution number at epoch (default: 0, used with --tle mode).",
    )

    return parser.parse_args()
