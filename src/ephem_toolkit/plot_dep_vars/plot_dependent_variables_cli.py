"""CLI argument parsing for dependent-variable plotting."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.time_utils as time_utils


def parse_arguments() -> argparse.Namespace:
    """Build command-line argument parser."""
    parser = cli.create_parser(
        description="Plot dependent-variable histories from a saved Tudat CSV file.",
        epilog=(
            "Examples:\n"
            '  plot-dependent-variables dep_vars.csv\n'
            '  plot-dependent-variables dep_vars.csv --name ISS\n'
            '  plot-dependent-variables dep_vars.csv -d 6h'
        ),
    )
    parser.prog = "plot-dependent-variables"
    parser.add_argument(
        "dep_vars_csv",
        metavar="<dep_vars_csv|->",
        help="Path to the *_dep_vars.csv file produced by propagate_orbit; use '-' for stdin if supported.",
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
        help="Duration to plot in <number>[s|m|h|d] format (e.g., 1h, 30m, or 3600s). If omitted, plot all data.",
    )
    return parser.parse_args()
