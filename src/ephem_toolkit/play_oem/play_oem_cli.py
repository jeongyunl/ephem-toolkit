"""CLI argument parsing for OEM playback."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

import ephem_toolkit.core.cli as cli
from .views.trajectory3d.selection import THREE_D_BACKEND_CHOICES
from .views.registry import parse_plot_selection

PLOTS_OPTION = "--plots"
THREE_D_BACKEND_OPTION = "--3d-backend"
CONFIG_FILE_OPTION = "--config-file"
STATE_FILE_OPTION = "--state-file"
CONFIG_DIR_OPTION = "--config-dir"
CONFIG_OPTION_DESTINATIONS = {
    PLOTS_OPTION: "plots",
    THREE_D_BACKEND_OPTION: "three_d_backend",
    CONFIG_FILE_OPTION: "config_file",
    STATE_FILE_OPTION: "state_file",
    CONFIG_DIR_OPTION: "config_dir",
}


def _parse_plots(value: str) -> tuple[str, ...]:
    try:
        return parse_plot_selection(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


class PlayOemArgs(argparse.Namespace):
    """Typed argument namespace for the OEM playback CLI."""

    input_oem: str | None
    """Optional path to an initial CCSDS OEM file."""
    three_d_backend: str
    """3D trajectory rendering backend."""
    plots: tuple[str, ...]
    """View names selected for launch."""
    config_file: str | None
    """Optional path to a user config TOML file."""
    state_file: str | None
    """Optional path to a saved-state TOML file."""
    config_dir: str | None
    """Optional directory containing the user config and saved-state TOML files."""
    provided_options: frozenset[str]
    """Config-capable destinations explicitly supplied on the command line."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for OEM playback."""
    # CLI options select the file and views; playback settings live in the GUI.
    parser = cli.build_arg_parser(
        description="Interactively explore and play a CCSDS OEM ephemeris.",
        epilog=(
            "Examples:\n"
            "  play-oem\n"
            "  play-oem orbit.oem\n"
            f"  play-oem orbit.oem {PLOTS_OPTION} overview"
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
        THREE_D_BACKEND_OPTION,
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
        PLOTS_OPTION,
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
        CONFIG_FILE_OPTION,
        dest="config_file",
        type=str,
        default=None,
        metavar="<path>",
        help="Load user defaults from this TOML file instead of the default location.",
    )
    parser.add_argument(
        STATE_FILE_OPTION,
        dest="state_file",
        type=str,
        default=None,
        metavar="<path>",
        help="Load and save application state from this TOML file instead of the default location.",
    )
    parser.add_argument(
        CONFIG_DIR_OPTION,
        dest="config_dir",
        type=str,
        default=None,
        metavar="<directory>",
        help=(
            "Load and save play-oem configuration and state TOML files from this directory. "
            f"Explicit {CONFIG_FILE_OPTION} and {STATE_FILE_OPTION} paths take precedence."
        ),
    )
    return parser


def parse_arguments(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None = None,
) -> PlayOemArgs:
    """Parse command-line arguments for OEM playback."""
    argument_list = list(sys.argv[1:] if argv is None else argv)
    parsed = parser.parse_args(argument_list, namespace=PlayOemArgs())
    provided: set[str] = set()
    for argument in argument_list:
        option = argument.split("=", 1)[0]
        if option in CONFIG_OPTION_DESTINATIONS:
            provided.add(CONFIG_OPTION_DESTINATIONS[option])
    parsed.provided_options = frozenset(provided)
    return parsed
