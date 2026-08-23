#!/usr/bin/env python3
"""Keplerian element propagation.

Read one OEM-like line of Keplerian elements from a file or stdin, then
propagate the orbit using the two-body Kepler propagator.

Usage:
    propagate-kepler - [-d <duration>] [-s <step>] -o - [--data-only]

Expected input format:
    <ISO-8601 epoch>  <a_km>  <e>  <i_rad>  <omega_rad>  <RAAN_rad>  <theta_rad>

The semi-major axis is interpreted in kilometers and converted to meters before
calling the propagator. Output is emitted as the same OEM-like format.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys
import warnings
from typing import TextIO

import numpy as np

from . import propagate_kepler_cli
from .propagate_kepler_cli import PropagateKeplerArgs

# Suppress warnings that tudatpy / urllib3 may emit on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings(
    "ignore",
    module=r"urllib3(\..*)?",
)

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.kepler as kepler
import ephem_toolkit.core.time_utils as time_utils

# ===================================================================
# Constants
# ===================================================================

DEFAULT_PROPAGATION_DURATION_S: float = time_utils.SECONDS_PER_DAY
"""Default propagation duration in seconds (1 day)."""

DEFAULT_OUTPUT_STEP_S: float = 15.0 * time_utils.SECONDS_PER_MINUTE
"""Default output sampling interval in seconds (15 minutes)."""


# ===================================================================
# Command-line interface
# ===================================================================


def parse_arguments() -> PropagateKeplerArgs:
    """Parse command-line arguments for Keplerian propagation.

    Delegates to the canonical propagation-family parser so the console entry
    point and the dedicated parser module stay in sync.
    """
    args: PropagateKeplerArgs = propagate_kepler_cli.parse_arguments()
    args.input_file = args.initial_state
    return args


def _normalize_kepler_state(
    state_line: str,
) -> tuple[dt.datetime, np.ndarray]:
    """Parse a single Keplerian state line into UTC time and a 6-element vector."""
    stripped = state_line.strip()
    if not stripped or stripped.startswith("#"):
        raise ValueError(f"No valid Keplerian element line found: {state_line!r}")

    tokens = stripped.split()
    if len(tokens) != 7:
        raise ValueError(
            f"Keplerian state line must contain an ISO-8601 epoch and 6 values: {state_line!r}"
        )

    epoch_str = tokens[0]
    values = [float(token) for token in tokens[1:7]]
    if len(values) != 6:
        raise ValueError(
            f"Keplerian state line must contain exactly 6 orbital elements: {state_line!r}"
        )

    epoch_dt = time_utils.iso8601_to_datetime(epoch_str)
    kepler_km = np.asarray(values, dtype=float)
    return epoch_dt, kepler_km


def read_kepler_input(source: str | None) -> tuple[dt.datetime, np.ndarray, str]:
    """Read the initial Keplerian element line from inline text, file, or stdin."""
    if source is None:
        source = "-"

    if source == "-":
        if sys.stdin.isatty():
            raise ValueError(
                "Keplerian input not provided. Pass --initial-state or pipe a Keplerian state line on stdin."
            )

        stdin_text: str = sys.stdin.read()
        if not stdin_text.strip():
            raise ValueError(
                "Empty stdin input. Provide a Keplerian element line on stdin."
            )
        lines: list[str] = [
            line.strip() for line in stdin_text.splitlines() if line.strip()
        ]
        epoch_dt, kepler_km = _normalize_kepler_state(lines[-1])
        return epoch_dt, kepler_km, "KEPLER_STDIN"

    inline_candidate = source.strip()
    try:
        if inline_candidate:
            epoch_dt, kepler_km = _normalize_kepler_state(inline_candidate)
            return epoch_dt, kepler_km, "INITIAL_STATE"
    except ValueError:
        pass

    input_path: pathlib.Path = pathlib.Path(source.strip()).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as file_stream:
        lines: list[str] = [line.strip() for line in file_stream if line.strip()]
    if not lines:
        raise ValueError(f"Empty input file: {input_path}")

    epoch_dt, kepler_km = _normalize_kepler_state(lines[-1])
    return epoch_dt, kepler_km, input_path.stem


# ===================================================================
# Propagation
# ===================================================================


def propagate_kepler_elements(
    initial_epoch: dt.datetime,
    initial_kepler_km: np.ndarray,
    duration_s: float,
    step_s: float,
    data_only: bool,
    object_name: str,
    output_path: str = "-",
) -> None:
    """Propagate the given Keplerian elements and write output lines to a stream.

    Converts the initial Keplerian state from km to m, steps through the
    propagation interval, converts each propagated state back to Cartesian
    km, and writes either a full CCSDS OEM or bare state lines to stdout or a
    file path provided via ``output_path``.
    """
    initial_kepler_m: np.ndarray = initial_kepler_km.astype(np.float64).copy()
    initial_kepler_m[kepler.SEMI_MAJOR_AXIS_INDEX] *= 1000.0  # Convert km to m
    initial_kepler_m = initial_kepler_m.reshape((6, 1))

    stop_time_s: float = duration_s
    current_time_s: float = 0.0
    # Build list of (POSIX timestamp, state vector) tuples for consistency with OEM migration
    propagated_states: list[tuple[float, np.ndarray]] = []
    while current_time_s <= stop_time_s + 1.0e-12:
        propagated_kepler: np.ndarray = kepler.propagate_kepler(
            initial_kepler_m,
            current_time_s,
        ).flatten()
        propagated_cartesian_m: np.ndarray = kepler.keplerian_to_cartesian(
            propagated_kepler
        ).flatten()
        propagated_cartesian_km: np.ndarray = (
            propagated_cartesian_m / 1000.0
        )  # Convert m to km
        epoch_posix: float = (
            initial_epoch + dt.timedelta(seconds=current_time_s)
        ).timestamp()
        propagated_states.append((epoch_posix, propagated_cartesian_km))
        current_time_s += step_s

    output_stream: TextIO
    if output_path == "-":
        output_stream = sys.stdout
    else:
        output_stream = open(output_path, "w", encoding="utf-8")

    try:
        if not data_only:
            # Use from_states() for automatic header/metadata generation.
            # Note: propagated_states are in km (not SI meters) because this is
            # Keplerian propagation output; the OEM writer converts km→km (no-op).
            oem_message: oem.CcsdsOem = oem.CcsdsOem.from_states(
                propagated_states,
                object_name=object_name,
                ref_frame="KEPLERIAN",
                center_name="EARTH",
                time_system="UTC",
            )
            oem_message.write(output_stream)
        else:
            oem.CcsdsOem.from_states(propagated_states).write_states(output_stream)
    finally:
        if output_path != "-":
            output_stream.close()


# ===================================================================
# Main entry point
# ===================================================================


def main() -> int:
    """Execute the Keplerian propagation workflow.

    Returns
    -------
    int
        Process return code. ``0`` on success.
    """
    cli_args: PropagateKeplerArgs = parse_arguments()
    if cli_args.duration_s <= 0.0:
        raise ValueError("--duration must be > 0")
    if cli_args.step_s <= 0.0:
        raise ValueError("--step must be > 0")

    initial_epoch: dt.datetime
    initial_kepler_km: np.ndarray
    object_name: str
    input_source = (
        cli_args.initial_state
        if cli_args.initial_state is not None
        else cli_args.input_file
    )
    initial_epoch, initial_kepler_km, object_name = read_kepler_input(input_source)

    propagate_kepler_elements(
        initial_epoch=initial_epoch,
        initial_kepler_km=initial_kepler_km,
        duration_s=cli_args.duration_s,
        step_s=cli_args.step_s,
        data_only=cli_args.data_only,
        object_name=object_name,
        output_path=cli_args.output_oem,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
