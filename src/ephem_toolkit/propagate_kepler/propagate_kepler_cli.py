"""CLI argument parsing for the Kepler propagation command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.time_utils as time_utils

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
DEFAULT_OUTPUT_STEP_S: float = 15.0 * time_utils.SECONDS_PER_MINUTE


class PropagateKeplerArgs(argparse.Namespace):
    """Typed argument namespace for the Kepler propagation CLI."""

    initial_state: str | None
    """Initial Keplerian state line or None if stdin is used."""
    duration_s: float
    """Propagation duration in seconds."""
    output: str
    """Output OEM file path or '-' for stdout."""
    step_s: float
    """Output sampling interval in seconds."""
    data_only: bool
    """Whether to emit data-only OEM state lines."""


def parse_arguments() -> PropagateKeplerArgs:
    """Parse command-line arguments for Keplerian propagation."""
    parser = cli.create_parser(
        description=(
            "Run two-body Keplerian propagation from one OEM-style state line and "
            "a user-provided simulation duration."
        ),
        epilog=(
            "Examples:\n"
            '  propagate-kepler --initial-state "2026-05-29T00:00:00.000000 6793.456 0.001234 0.9013 4.094 2.155 0.797" -d 6h\n'
            "  propagate-kepler --duration 90m --output propagated.oem < initial_state.txt\n"
            "  cat input.txt | propagate-kepler --output - --data-only"
        ),
    )
    parser.add_argument(
        "-i",
        "--initial-state",
        dest="initial_state",
        metavar="<state-line>",
        help=(
            "One OEM-style Keplerian state line provided directly on the command line. "
            "If omitted, one line is read from stdin."
        ),
    )
    parser.add_argument(
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
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="<output_oem|->",
        default="-",
        help=(
            "Write propagated state history as OEM state-vector lines to the target path; "
            "'-' writes to stdout."
        ),
    )
    parser.add_argument(
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
    parser.add_argument(
        "--data-only",
        dest="data_only",
        action="store_true",
        help=(
            "Print only propagated state lines without the OEM metadata header. "
            "By default, output is CCSDS OEM format."
        ),
    )
    return parser.parse_args(namespace=PropagateKeplerArgs())
