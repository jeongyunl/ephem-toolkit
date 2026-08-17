"""CLI argument parsing for the TLE propagation command."""

from __future__ import annotations

import argparse

import ephem_toolkit.core.time_utils as time_utils

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
DEFAULT_OUTPUT_STEP_S: float = 5.0 * time_utils.SECONDS_PER_MINUTE


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments for TLE propagation."""
    parser = argparse.ArgumentParser(
        description=(
            "Load one TLE file, propagate with TudatPy SGP4, and print an "
            "OEM-like state history."
        )
    )
    parser.add_argument(
        "tle_file",
        metavar="<tle_file>",
        help='Path to a TLE file. Use "-" to read TLE text from stdin.',
    )
    parser.add_argument(
        "--start",
        metavar="<iso8601|duration>",
        default=None,
        help=(
            "Propagation start epoch. Accepts ISO 8601 timestamp (e.g. "
            "2026-01-01T00:00:00) or duration offset from the TLE epoch "
            "(e.g. 90m, -30m)."
        ),
    )
    parser.add_argument(
        "--stop",
        metavar="<iso8601|duration>",
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
        type=time_utils.parse_duration_to_seconds,
        metavar="<value[s|m]>",
        default=DEFAULT_OUTPUT_STEP_S,
        help=(
            "Output interval (default: 5m). "
            "Use -s/--step, e.g. -s 60, --step 60s, -s 1m."
        ),
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help=(
            "Print propagated state lines only (no OEM metadata header). "
            "By default, output is CCSDS OEM format."
        ),
    )
    return parser.parse_args()
