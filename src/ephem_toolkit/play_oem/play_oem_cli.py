"""CLI argument parsing for OEM playback."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import math

import ephem_toolkit.core.cli as cli
from .views.trajectory3d.selection import THREE_D_BACKEND_CHOICES
from .views.registry import parse_plot_selection

MIN_SPEED = 1.0
MAX_SPEED = 1000.0
MIN_FPS = 1
MAX_FPS = 1000


def _parse_plots(value: str) -> tuple[str, ...]:
    try:
        return parse_plot_selection(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


class PlayOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM playback CLI."""

    input_oem: str
    """Path to the input CCSDS OEM file."""
    duration: str | None
    """Optional analysis duration string."""
    time_unit: str
    """Time unit used in time-series plots."""
    three_d_backend: str
    """3D trajectory rendering backend."""
    speed: float
    """Signed initial playback speed multiplier."""
    reverse: bool
    """Whether to negate the initial playback speed."""
    start: str | None
    """Optional initial elapsed duration or UTC epoch."""
    autoplay: bool
    """Whether playback starts immediately."""
    loop: bool
    """Whether playback wraps at timeline boundaries."""
    plots: tuple[str, ...]
    """View names selected for launch."""
    fps: int
    """Maximum requested render rate."""


def _parse_speed(value: str) -> float:
    try:
        speed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--speed must be a number") from error
    if (
        not math.isfinite(speed)
        or speed == 0.0
        or abs(speed) < MIN_SPEED
        or abs(speed) > MAX_SPEED
    ):
        raise argparse.ArgumentTypeError(
            "--speed must be between -1000 and -1 or between 1 and 1000"
        )
    return speed


def _parse_fps(value: str) -> int:
    try:
        fps = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--fps must be an integer") from error
    if fps < MIN_FPS or fps > MAX_FPS:
        raise argparse.ArgumentTypeError("--fps must be between 1 and 1000")
    return fps


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for OEM playback."""
    parser = cli.build_arg_parser(
        description="Interactively explore and play a CCSDS OEM ephemeris.",
        epilog=(
            "Examples:\n"
            "  play-oem orbit.oem\n"
            "  play-oem orbit.oem -d 6h --time-unit minutes"
        ),
    )
    parser.prog = "play-oem"
    parser.add_argument(
        "input_oem",
        type=str,
        metavar="<input_oem>",
        help="Path to the input CCSDS OEM file.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        dest="duration",
        type=str,
        default=None,
        metavar="<duration>",
        help="Duration to analyze from the start (e.g., 1h, 30m, or 3600s).",
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
    parser.add_argument(
        "--speed",
        type=_parse_speed,
        default=1.0,
        metavar="<x>",
        help="Initial signed speed multiplier (1x–1000x; negative plays in reverse).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help=(
            "Negate --speed; negative effective speed starts at the timeline end "
            "unless --start is given."
        ),
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        metavar="<time>",
        help="Initial elapsed duration (e.g., 30m) or UTC epoch.",
    )
    parser.add_argument(
        "--autoplay",
        action="store_true",
        help="Begin playback immediately.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Wrap to the opposite timeline boundary during playback.",
    )
    parser.add_argument(
        "--fps",
        type=_parse_fps,
        default=30,
        metavar="<n>",
        help="Maximum render rate from 1 to 1000 frames per second (default: 30).",
    )
    return parser


def parse_arguments(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None = None,
) -> PlayOemArgs:
    """Parse command-line arguments for OEM playback."""
    return parser.parse_args(argv, namespace=PlayOemArgs())
