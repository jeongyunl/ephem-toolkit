"""CLI argument parsing for the OMM/TLE propagation command.

Usage:
    propagate-omm <input_omm|input_tle|-> [options]
"""

from __future__ import annotations

import argparse

import ephem_toolkit.core.cli as cli
import ephem_toolkit.core.time_utils as time_utils

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 5.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (5 minutes)."""


class PropagateOmmArgs(argparse.Namespace):
    """Typed argument namespace for the OMM/TLE propagation CLI."""

    input_file: str
    """Input file path for OMM or TLE, or '-' for stdin."""
    is_tle: bool
    duration_s: float
    """Propagation duration in seconds."""
    output_oem: str
    """Output OEM path or '-' for stdout."""
    start: str | None
    """Optional propagation start specification."""
    stop: str | None
    """Optional propagation stop specification."""
    step: float
    """Output sampling interval in seconds."""
    data_only: bool
    """Whether to emit data-only OEM state lines."""


def parse_arguments(argv=None) -> PropagateOmmArgs:
    """Parse command-line arguments for the OMM/TLE propagation workflow.

    Returns
    -------
    PropagateOmmArgs
        Parsed argument namespace for the propagation command.
    """
    parser = cli.create_parser(
        description=(
            "Load one OMM or TLE input and propagate the orbit. Uses SGP4 if the "
            "input is a raw TLE or an OMM with TLE parameters; otherwise uses "
            "two-body Kepler propagation. Output is CCSDS OEM state history."
        ),
        epilog=(
            "Examples:\n"
            "  propagate-omm satellite.omm --duration 6h -o output.oem\n"
            "  propagate-omm image.tle --tle --duration 6h -o propagated.oem\n"
            "  cat satellite.omm | propagate-omm - -o - --data-only"
        ),
    )
    parser.add_argument(
        "input_file",
        metavar="<tle_file|omm_file|->",
        help='Path to an OMM or TLE file. Use "-" to read input text from stdin.',
    )
    parser.add_argument(
        "--tle",
        dest="is_tle",
        action="store_true",
        help="Interpret the input as a raw TLE file instead of an OMM file.",
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
        dest="output_oem",
        metavar="<output_oem|->",
        required=True,
        help=(
            "Write propagated state history as OEM state-vector lines to the target path; "
            "'-' writes to stdout."
        ),
    )
    parser.add_argument(
        "--start",
        dest="start",
        metavar="<timestamp|duration>",
        default=None,
        help=(
            "Propagation start epoch. Accepts ISO 8601 timestamp (e.g. "
            "2026-01-01T00:00:00) or duration offset from the OMM epoch "
            "(e.g. 90m, -30m)."
        ),
    )
    parser.add_argument(
        "--stop",
        dest="stop",
        metavar="<timestamp|duration>",
        default=None,
        help=(
            "Propagation stop epoch. Accepts ISO 8601 timestamp (e.g. "
            "2026-01-01T06:00:00) or duration offset from the start epoch "
            "(e.g. 1d, 6h)."
        ),
    )
    parser.add_argument(
        "-s",
        "--step",
        dest="step",
        type=time_utils.parse_duration_to_seconds,
        metavar="<duration>",
        default=DEFAULT_OUTPUT_STEP_S,
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
            "Print propagated state lines only (no OEM metadata header). "
            "By default, output is CCSDS OEM format."
        ),
    )
    return parser.parse_args(argv, namespace=PropagateOmmArgs())
