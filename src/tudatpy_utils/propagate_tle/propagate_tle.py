#!/usr/bin/env python3
"""TLE propagation to OEM-like output.

Load one TLE file, propagate the orbit with TudatPy's SGP4 TLE ephemeris, and
print state vectors in an OEM-like text format.

Only light standard-library modules are imported at file import time. TudatPy
modules are imported only when propagation is actually requested. This keeps
``--help`` and early argument validation responsive.

Usage:
    propagate-tle <tle_file> [options]
    cat <tle_file> | propagate-tle [options]

Time window options:
    --start <iso8601|duration>   Start epoch (absolute or relative to TLE epoch)
    --stop  <iso8601|duration>   Stop epoch (absolute or relative to start epoch)
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys
from typing import Any
import numpy as np

import warnings

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import tudatpy_utils.core.ccsds.oem as oem
import tudatpy_utils.core.spice_utils as spice_utils
import tudatpy_utils.core.time_utils as time_utils

# CLI defaults
DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 5.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (5 minutes)."""


# ===================================================================
# CLI argument parsing
# ===================================================================


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments for TLE propagation.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Load one TLE file, propagate with TudatPy SGP4, and print an "
            "OEM-like state history."
        )
    )
    parser.add_argument(
        "tle_file",
        nargs="?",
        metavar="<tle_file>",
        help=("Path to a TLE file. If omitted, read TLE text directly from stdin."),
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


# ===================================================================
# TLE input and parsing
# ===================================================================


def extract_tle_line_pair(text_lines: list[str], source_label: str) -> tuple[str, str]:
    """Extract and validate one TLE line pair from non-empty text lines.

    Parameters
    ----------
    text_lines : list[str]
        Non-empty candidate lines.
    source_label : str
        Human-readable source used in error messages.

    Returns
    -------
    tuple[str, str]
        Two TLE lines in ``(line1, line2)`` order.

    Raises
    ------
    ValueError
        If fewer than two lines are available or TLE line tags are invalid.
    """
    if len(text_lines) < 2:
        raise ValueError(
            f"TLE source '{source_label}' must contain at least 2 non-empty lines."
        )

    line1: str = text_lines[-2]
    line2: str = text_lines[-1]
    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError(
            "Could not find TLE line pair at end of input "
            "(expected lines starting with '1 ' and '2 ')."
        )

    return line1, line2


def read_tle_input(cli_value: str | None) -> tuple[str, str, str]:
    """Read TLE lines from file input or stdin text.

    Parameters
    ----------
    cli_value : str | None
        Positional CLI value for TLE file path.

    Returns
    -------
    tuple[str, str, str]
        ``(line1, line2, object_name)`` where ``object_name`` is derived from
        the file stem for file input, or ``TLE_STDIN`` for stdin input.

    Notes
    -----
    For both file and stdin input, the final two non-empty lines are interpreted
    as the TLE pair.
    """
    if cli_value:
        tle_path: pathlib.Path = pathlib.Path(cli_value.strip()).expanduser().resolve()
        if not tle_path.is_file():
            raise FileNotFoundError(f"TLE file not found: {tle_path}")

        with tle_path.open("r", encoding="utf-8") as handle:
            text_lines: list[str] = [line.strip() for line in handle if line.strip()]
        line1, line2 = extract_tle_line_pair(text_lines, str(tle_path))
        return line1, line2, tle_path.stem

    if sys.stdin.isatty():
        raise ValueError(
            "TLE input not provided. Pass <tle_file> or pipe TLE text on stdin."
        )

    stdin_text: str = sys.stdin.read()
    if not stdin_text.strip():
        raise ValueError("Empty stdin input. Provide TLE text on stdin.")
    text_lines: list[str] = [
        line.strip() for line in stdin_text.splitlines() if line.strip()
    ]
    line1, line2 = extract_tle_line_pair(text_lines, "stdin")
    return line1, line2, "TLE_STDIN"


# ===================================================================
# TudatPy integration
# ===================================================================


def load_spice_kernels() -> None:
    """Load SPICE kernels required for time conversion.

    Notes
    -----
    The TudatPy ephemeris is typed as ``Any`` to avoid importing TudatPy at
    module import time.
    """
    spice_kernel_files: list[str] = [
        "naif0012.tls",  # LEAPSECONDS KERNEL FILE
        "pck00011.tpc",  # PLANETARY CONSTANTS KERNEL FILE: orientation and size/shape data for natural bodies(Sun, planets, asteroids, etc)
    ]

    for kernel_file in spice_kernel_files:
        spice_utils.load_kernel(kernel_file)


def resolve_epoch_datetime(
    reference_dt: dt.datetime,
    spec: dt.datetime | dt.timedelta,
) -> dt.datetime:
    """Resolve absolute UTC datetime from a datetime or offset specification.

    Parameters
    ----------
    reference_dt : dt.datetime
        TLE reference epoch as UTC datetime.
    spec : dt.datetime | dt.timedelta
        Absolute datetime or offset relative to the reference epoch.

    Returns
    -------
    dt.datetime
        Resolved absolute UTC datetime.
    """
    if isinstance(spec, dt.timedelta):
        return reference_dt + spec
    return spec


def resolve_time_bounds(
    reference_dt: dt.datetime,
    start_spec: dt.datetime | dt.timedelta,
    stop_spec: dt.datetime | dt.timedelta | None,
) -> tuple[dt.datetime, dt.datetime]:
    """Resolve absolute start and stop datetimes for a propagation window."""
    start_time = resolve_epoch_datetime(reference_dt, start_spec)
    if stop_spec is None:
        stop_time = start_time + dt.timedelta(seconds=DEFAULT_PROPAGATION_DURATION_S)
    else:
        stop_time = resolve_epoch_datetime(start_time, stop_spec)
    return start_time, stop_time


def write_oem_file(
    object_name: str,
    tle_ephemeris: Any,
    start_time: dt.datetime,
    stop_time: dt.datetime,
    step_s: float,
    data_only: bool,
) -> None:
    """Print propagated state history using an OEM-like text layout.

    Parameters
    ----------
    object_name : str
        Object name/id written to OEM metadata.
    tle_ephemeris
        TudatPy ephemeris object exposing ``cartesian_state(epoch)``.
    start_time : dt.datetime
        Absolute UTC start epoch.
    stop_time : dt.datetime
        Absolute UTC stop epoch.
    step_s : float
        Output sampling interval (s).
    data_only : bool
        Whether to print state lines only (without OEM metadata header).

    Notes
    -----
    Type annotations omitted for TudatPy modules to avoid import-time dependencies.
    """
    if stop_time < start_time:
        raise ValueError(
            "Invalid propagation window: stop epoch must be >= start epoch.\n"
            f"  Resolved start: {time_utils.datetime_to_iso8601(start_time)}\n"
            f"  Resolved stop:  {time_utils.datetime_to_iso8601(stop_time)}"
        )

    # Propagate and collect state vectors as list[tuple[float, np.ndarray]] (POSIX timestamps)
    propagated_states: list[tuple[float, np.ndarray]] = []
    step_dt = dt.timedelta(seconds=step_s)
    current_time: dt.datetime = start_time
    while current_time <= stop_time:
        current_tdb_s: float = time_utils.datetime_to_tdb_s(current_time)
        state_m: np.ndarray = tle_ephemeris.cartesian_state(current_tdb_s)

        # Convert to POSIX timestamp for CcsdsOem
        timestamp: float = current_time.timestamp()
        # Store state in meters (SI units) for CcsdsOem.
        propagated_states.append((timestamp, state_m))
        current_time = current_time + step_dt

    output_stream = sys.stdout
    if data_only:
        oem.CcsdsOem.from_states(propagated_states).write_states(output_stream)
    else:
        # Use from_states() for automatic header/metadata generation.
        # states_list contains SI units (m, m/s); write() converts to km automatically.
        oem_obj: oem.CcsdsOem = oem.CcsdsOem.from_states(
            propagated_states,
            object_name=object_name,
            ref_frame="EME2000",
            center_name="EARTH",
            time_system="UTC",
        )
        oem_obj.write(output_stream)


# ===================================================================
# Main entry point
# ===================================================================


def main() -> int:
    """Execute the TLE propagation workflow.

    Returns
    -------
    int
        Process return code (0 on success).
    """
    # Parse CLI input and validate scalar settings first so invalid requests
    # fail quickly before importing TudatPy.
    args: argparse.Namespace = parse_arguments()

    if args.step <= 0.0:
        raise ValueError("--step must be > 0")

    line1: str
    line2: str
    object_name: str
    line1, line2, object_name = read_tle_input(args.tle_file)

    # Heavy TudatPy imports are intentionally delayed until after cheap input
    # validation is complete.
    from tudatpy.dynamics import environment_setup

    load_spice_kernels()

    # Create SGP4 ephemeris settings and ephemeris object from TLE lines
    tle_ephemeris_settings = environment_setup.ephemeris.sgp4(line1, line2)
    tle_ephemeris = environment_setup.create_body_ephemeris(
        tle_ephemeris_settings, body_name=object_name
    )
    reference_dt: dt.datetime = time_utils.tdb_s_to_datetime(
        tle_ephemeris.tle.reference_epoch
    )

    start_spec: dt.datetime | dt.timedelta
    stop_spec: dt.datetime | dt.timedelta

    if args.start is None:
        start_spec = dt.timedelta(0)
    else:
        start_spec = time_utils.parse_time_or_duration(args.start)

    if args.stop is None:
        stop_spec = None
    else:
        stop_spec = time_utils.parse_time_or_duration(args.stop)

    start_time, stop_time = resolve_time_bounds(reference_dt, start_spec, stop_spec)

    write_oem_file(
        object_name=object_name,
        tle_ephemeris=tle_ephemeris,
        start_time=start_time,
        stop_time=stop_time,
        step_s=args.step,
        data_only=args.data_only,
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
