"""CLI argument parsing for orbit-delta plotting."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for plotting multiple orbit trajectories."""
    parser = cli.create_parser(
        description="Plot multiple orbit trajectories with various views and RTN coordinates.",
        epilog=(
            "Examples:\n"
            '  plot-orbit-deltas reference.oem\n'
            '  plot-orbit-deltas reference.oem comparison1.oem comparison2.oem\n'
            '  plot-orbit-deltas reference.oem comparison.oem -o orbits.png'
        ),
    )
    parser.prog = "plot-orbit-deltas"

    parser.add_argument(
        "files",
        nargs="+",
        metavar="<input_oem|->",
        help="OEM or raw-state files. The first file is the reference orbit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        metavar="<output_plot|->",
        help="Output file path for saving the figure (e.g., orbits.png); '-' writes to stdout when supported.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        default=None,
        metavar="<duration>",
        help="Duration of data to analyze from start (e.g., 1h, 30m, 3600s)",
    )
    parser.add_argument(
        "--time-unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help="Time unit for time-series plots: m/minute/minutes or h/hour/hours (default: hours)",
    )

    return parser.parse_args()
