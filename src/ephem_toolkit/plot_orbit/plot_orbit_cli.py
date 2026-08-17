"""CLI argument parsing for orbit plotting."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for plotting a single orbit."""
    parser = cli.create_parser(
        description=(
            "Plot a single OEM orbit with RTN deltas, velocity magnitude, "
            "geocentric distance, and WGS84 altitude."
        ),
        epilog=(
            "Examples:\n"
            '  plot-orbit orbit.oem\n'
            '  plot-orbit orbit.oem -d 6h --time-unit minutes\n'
            '  plot-orbit orbit.oem -o orbit_plots.png'
        ),
    )
    parser.prog = "plot-orbit"
    parser.add_argument(
        "input_oem",
        type=str,
        metavar="<input_oem|->",
        help="OEM file to plot; use '-' to read from stdin when supported.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        metavar="<output_plot|->",
        help="Base output image path for saving figures (e.g., orbit.png); '-' writes to stdout when supported.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        default=None,
        metavar="<duration>",
        help="Duration to analyze from the start (e.g., 1h, 30m, or 3600s).",
    )
    parser.add_argument(
        "--time-unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help=(
            "Time unit for time-series plots: "
            "m/minute/minutes or h/hour/hours (default: hours)."
        ),
    )
    return parser.parse_args()
