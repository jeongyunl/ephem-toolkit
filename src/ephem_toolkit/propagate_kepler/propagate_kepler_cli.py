"""CLI argument parsing for the Kepler propagation command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.time_utils as time_utils

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
DEFAULT_OUTPUT_STEP_S: float = 15.0 * time_utils.SECONDS_PER_MINUTE


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for Keplerian propagation."""
    parser = argparse.ArgumentParser(
        description=(
            "Load one OEM-like line of Keplerian elements, propagate using two-body "
            "Kepler dynamics, and write propagated keplerian elements in OEM-like format."
        )
    )
    parser.add_argument(
        "input_file",
        metavar="<input_file>",
        help='Path to a file containing one OEM-like Keplerian element line. Use "-" to read from stdin.',
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=time_utils.parse_duration_to_seconds,
        metavar="<value[s|m|h|d]>",
        default=DEFAULT_PROPAGATION_DURATION_S,
        dest="duration_s",
        help=(
            "Propagation duration (default: 1d). "
            "Use -d/--duration, e.g. -d 90 (90 seconds), --duration 90s, -d 2m, -d 1.5h, -d 1d."
        ),
    )
    parser.add_argument(
        "-s",
        "--step",
        type=time_utils.parse_duration_to_seconds,
        metavar="<value[s|m]>",
        default=DEFAULT_OUTPUT_STEP_S,
        dest="step_s",
        help=(
            "Output interval (default: 15m). "
            "Use -s/--step, e.g. -s 60, --step 60s, -s 1m."
        ),
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help=(
            "Print only propagated state lines without the OEM metadata header. "
            "By default, output is CCSDS OEM format."
        ),
    )
    return parser.parse_args()
