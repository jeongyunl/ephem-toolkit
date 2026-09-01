"""CLI argument parsing for the Kepler propagation command.

Usage:
    propagate-kepler <input_opm|-> [-d <duration>] [-s <step>] -o <output_oem|->
"""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.time_utils as time_utils

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 15.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (15 minutes)."""


class PropagateKeplerArgs(argparse.Namespace):
    """Typed argument namespace for the Kepler propagation CLI."""

    input_opm: str
    """Input OPM file path or '-' if OPM content is read from stdin."""
    duration_s: float
    """Propagation duration in seconds."""
    output_oem: str
    """Output OEM file path or '-' for stdout."""
    step_s: float
    """Output sampling interval in seconds."""
    data_only: bool
    """Whether to emit data-only OEM state lines."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Parse command-line arguments for Keplerian propagation."""
    cli_parser = cli.build_arg_parser(
        description=(
            "Run two-body Keplerian propagation from an OPM Keplerian state and "
            "a user-provided simulation duration."
        ),
        epilog=(
            "Examples:\n"
            "  propagate-kepler input.opm -d 6h -o propagated.oem\n"
            "  propagate-kepler input.opm --duration 90m --output propagated.oem\n"
            "  cat input.opm | propagate-kepler - --output - --data-only"
        ),
    )
    cli_parser.add_argument(
        "input_opm",
        metavar="<input_opm|->",
        help="Input OPM file path, or '-' to read OPM content from stdin.",
    )
    cli_parser.add_argument(
        "-d",
        "--duration",
        type=time_utils.parse_duration_to_seconds,
        metavar="<duration>",
        default=DEFAULT_PROPAGATION_DURATION_S,
        dest="duration_s",
        help=(
            "Simulation duration. Accepts values like 90s, 2m, 1.5h, or 1d "
            f"(default: {DEFAULT_PROPAGATION_DURATION_S})."
        ),
    )
    cli_parser.add_argument(
        "-o",
        "--output",
        dest="output_oem",
        metavar="<output_oem|->",
        required=True,
        help=(
            "Write propagated state history as OEM state-vector lines to the target path; "
            "'-' writes to stdout."
        ),
    )
    cli_parser.add_argument(
        "-s",
        "--step",
        type=time_utils.parse_duration_to_seconds,
        metavar="<duration>",
        default=DEFAULT_OUTPUT_STEP_S,
        dest="step_s",
        help=(
            "Output interval. Accepts values like 60s or 1m "
            f"(default: {DEFAULT_OUTPUT_STEP_S})."
        ),
    )
    cli_parser.add_argument(
        "--data-only",
        dest="data_only",
        action="store_true",
        help=(
            "Print only propagated state lines without the OEM metadata header. "
            "By default, output is CCSDS OEM format."
        ),
    )
    return cli_parser


def parse_arguments(parser: argparse.ArgumentParser, argv=None) -> PropagateKeplerArgs:
    """Parse command-line arguments for Kepler propagation."""
    return parser.parse_args(argv, namespace=PropagateKeplerArgs())
