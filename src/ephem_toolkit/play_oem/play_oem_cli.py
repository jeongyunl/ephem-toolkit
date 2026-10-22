"""CLI argument parsing for OEM playback."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import ephem_toolkit.core.cli as cli
from .views.trajectory3d.selection import THREE_D_BACKEND_CHOICES
from .views.registry import parse_plot_selection


def _parse_plots(value: str) -> tuple[str, ...]:
    try:
        return parse_plot_selection(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


class PlayOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM playback CLI."""

    input_oem: str | None
    """Optional path to an initial CCSDS OEM file."""
    time_unit: str
    """Time unit used in time-series plots."""
    three_d_backend: str
    """3D trajectory rendering backend."""
    plots: tuple[str, ...]
    """View names selected for launch."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for OEM playback."""
    # CLI options select the file and views; transport settings live in the GUI.
    parser = cli.build_arg_parser(
        description="Interactively explore and play a CCSDS OEM ephemeris.",
        epilog=(
            "Examples:\n"
            "  play-oem\n"
            "  play-oem orbit.oem\n"
            "  play-oem orbit.oem --time-unit minutes"
        ),
    )
    parser.prog = "play-oem"
    parser.add_argument(
        "input_oem",
        type=str,
        metavar="<input_oem>",
        nargs="?",
        default=None,
        help="Optional path to an initial CCSDS OEM file.",
    )
    parser.add_argument(
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
    parser.add_argument(
        "--3d-backend",
        dest="three_d_backend",
        choices=THREE_D_BACKEND_CHOICES,
        default="auto",
        help=(
            "3D trajectory backend: auto selects VTK when its wx integration is "
            "available, vtk requires VTK, and matplotlib forces Matplotlib "
            "(default: auto)."
        ),
    )
    parser.add_argument(
        "--plots",
        type=_parse_plots,
        default=("overview",),
        metavar="<list>",
        help=(
            "Comma-separated plot names or groups to open "
            "(default: overview; groups: overview, state, motion, all; "
            "alias: state-vectors)."
        ),
    )
    return parser


def parse_arguments(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None = None,
) -> PlayOemArgs:
    """Parse command-line arguments for OEM playback."""
    return parser.parse_args(argv, namespace=PlayOemArgs())
