"""CLI argument parsing for orbit plotting."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli


class PlotOrbitArgs(argparse.Namespace):
    """Typed argument namespace for the orbit plotting CLI."""

    input_oem: str
    """OEM input path or '-' for stdin."""
    output: str | None
    """Optional output plot path."""
    duration: str | None
    """Optional analysis duration string."""
    time_unit: str
    """Time unit used in time-series plots."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Parse command-line arguments for plotting a single orbit."""
    cli_parser = cli.build_arg_parser(
        description=(
            "Plot a single OEM orbit with RTN deltas, velocity magnitude, "
            "geocentric distance, and WGS84 altitude."
        ),
        epilog=(
            "Examples:\n"
            "  plot-orbit orbit.oem\n"
            "  plot-orbit orbit.oem -d 6h --time-unit minutes\n"
            "  plot-orbit orbit.oem -o orbit_plots.png"
        ),
    )
    cli_parser.prog = "plot-orbit"
    cli_parser.add_argument(
        "input_oem",
        type=str,
        metavar="<input_oem>",
        help="Path to the input CCSDS OEM file.",
    )
    cli_parser.add_argument(
        "-o",
        "--output",
        dest="output",
        type=str,
        default=None,
        metavar="<output_plot>",
        help="Base output image path for saving figures (e.g., orbit.png).",
    )
    cli_parser.add_argument(
        "-d",
        "--duration",
        dest="duration",
        type=str,
        default=None,
        metavar="<duration>",
        help="Duration to analyze from the start (e.g., 1h, 30m, or 3600s).",
    )
    cli_parser.add_argument(
        "--time-unit",
        dest="time_unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help=(
            "Time unit for time-series plots: "
            "m/minute/minutes or h/hour/hours (default: hours)."
        ),
    )
    return cli_parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> PlotOrbitArgs:
    """Parse command-line arguments for orbit plotting."""
    return parser.parse_args(argv, namespace=PlotOrbitArgs())
