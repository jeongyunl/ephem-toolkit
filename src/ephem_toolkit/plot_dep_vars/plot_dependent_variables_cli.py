"""CLI argument parsing for dependent-variable plotting."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.time_utils as time_utils


def parse_arguments() -> argparse.Namespace:
    """Build command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Plot dependent-variable histories from a saved Tudat CSV file."
    )
    parser.add_argument(
        "dep_vars_csv",
        metavar="<dep_vars_csv>",
        help="Path to *_dep_vars.csv produced by propagate_orbit.py",
    )
    parser.add_argument(
        "--name",
        default="Satellite",
        metavar="<name>",
        help="Satellite name used in labels and header filtering (default: Satellite).",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=time_utils.parse_duration_to_seconds,
        default=None,
        metavar="<duration>",
        help="Duration to plot in format <number>[s|m|h|d] (e.g., 1h, 30m, 3600s). If not specified, plots all data.",
    )
    return parser.parse_args()
