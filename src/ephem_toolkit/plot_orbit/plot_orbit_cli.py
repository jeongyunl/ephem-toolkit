"""CLI argument parsing for orbit plotting."""

from __future__ import annotations

import argparse


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for plotting a single orbit."""
    parser = argparse.ArgumentParser(
        description=(
            "Plot a single OEM orbit with RTN deltas, velocity magnitude, "
            "geocentric distance, and WGS84 altitude."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    plot-orbit orbit.oem
    plot-orbit orbit.oem -d 6h --time-unit minutes
    plot-orbit orbit.oem -o orbit_plots.png
        """,
    )
    parser.add_argument(
        "source",
        type=str,
        help="OEM file to plot.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Base output image path for saving figures (e.g., orbit.png)",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        default=None,
        help="Duration to analyze from start (e.g., 1h, 30m, 3600s)",
    )
    parser.add_argument(
        "--time-unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help=(
            "Time unit for time-series plots: "
            "m/minute/minutes or h/hour/hours (default: hours)"
        ),
    )
    return parser.parse_args()
