"""CLI argument parsing for orbit-delta plotting."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


class PlotOrbitDeltasArgs(argparse.Namespace):
    """Typed argument namespace for orbit-delta plotting."""

    input_oem_files: list[str]
    """Input OEM files; the first is the reference orbit."""
    output: str | None
    """Optional output image path."""
    duration: str | None
    """Optional analysis duration string."""
    time_unit: str
    """Time unit for the plot axes."""


def parse_arguments() -> PlotOrbitDeltasArgs:
    """Parse command-line arguments for plotting multiple orbit trajectories."""
    parser = cli.create_parser(
        description="Plot multiple orbit trajectories with various views and RTN coordinates.",
        epilog=(
            "Examples:\n"
            "  plot-orbit-deltas reference.oem\n"
            "  plot-orbit-deltas reference.oem comparison1.oem comparison2.oem\n"
            "  plot-orbit-deltas reference.oem comparison.oem -o orbits.png"
        ),
    )
    parser.prog = "plot-orbit-deltas"

    parser.add_argument(
        "files",
        nargs="+",
        metavar="<input_oem>",
        help="OEM or raw-state files. The first file is the reference orbit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        type=str,
        default=None,
        metavar="<output_plot>",
        help="Output file path for saving the figure (e.g., orbits.png).",
    )
    parser.add_argument(
        "-d",
        "--duration",
        dest="duration",
        type=str,
        default=None,
        metavar="<duration>",
        help="Duration of data to analyze from the start (e.g., 1h, 30m, or 3600s).",
    )
    parser.add_argument(
        "--time-unit",
        dest="time_unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help="Time unit for time-series plots: m/minute/minutes or h/hour/hours (default: hours).",
    )

    return parser.parse_args(namespace=PlotOrbitDeltasArgs())
