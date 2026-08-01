#!/usr/bin/env python3
"""Compare two OEM-like Cartesian state vectors and report differences.

Usage:
    python3 bin/diff_oem.py <oem1.oem> <oem2.oem>
    python3 bin/diff_oem.py - <oem2.oem>
    python3 bin/diff_oem.py <oem1.oem> -

The utility compares the first state in each OEM file and reports time,
position, and velocity differences. Use ``-`` for one stdin input.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import common.oem as oem
import common.time_utils as time_utils

ComparisonState = tuple[datetime, np.ndarray]
"""State representation used by the comparison functions."""


class ComparisonResult(TypedDict):
    """Named results returned by :func:`compare_states`."""

    epoch1: datetime
    epoch2: datetime
    time_diff_s: float
    position_diff_km: np.ndarray
    position_diff_magnitude_km: float
    velocity_diff_km_s: np.ndarray
    velocity_diff_magnitude_km_s: float


def _to_comparison_state(
    state: tuple[float, np.ndarray],
) -> ComparisonState:
    """Convert a structured OEM state to UTC and km/km·s⁻¹ units."""
    timestamp, state_m = state
    epoch = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    state_km = state_m / oem.KILOMETERS_TO_METERS
    return epoch, state_km


def read_state_from_file(source: str | Path) -> ComparisonState:
    """Read the first state from a structured OEM file.

    Comments and blank lines are skipped by :class:`oem.CcsdsOem`.

    Parameters
    ----------
    source : str or pathlib.Path
        Path to an OEM file containing state data.

    Returns
    -------
    ComparisonState
        ``(epoch, state_km)`` where *state_km* is a six-element vector
        ``[x, y, z, vx, vy, vz]`` in km and km/s.

    Raises
    ------
    ValueError
        If file cannot be read or no valid state is found.
    """
    try:
        oem_data = oem.CcsdsOem.read(source)
    except OSError as error:
        raise ValueError(f"Could not read file '{source}': {error}") from error

    if not oem_data.states:
        raise ValueError(f"No valid OEM-like state found in '{source}'")
    return _to_comparison_state(oem_data.states[0])


def read_state_from_stdin() -> ComparisonState:
    """Read the first state from standard input."""
    oem_data = oem.CcsdsOem.read(sys.stdin)
    if not oem_data.states:
        raise ValueError("No valid OEM-like state found in stdin")
    return _to_comparison_state(oem_data.states[0])


def compare_states(oem1: ComparisonState, oem2: ComparisonState) -> ComparisonResult:
    """Compare two OEM-like states and return differences.

    Parameters
    ----------
    oem1 : ComparisonState
        First ``(epoch, state_km)`` tuple.
    oem2 : ComparisonState
        Second ``(epoch, state_km)`` tuple.

    Returns
    -------
    ComparisonResult
        Dictionary containing epochs, time difference in seconds, position
        difference in km, and velocity difference in km/s.
    """
    epoch1, oem1_km = oem1
    epoch2, oem2_km = oem2
    pos1: np.ndarray = oem1_km[0:3]
    vel1: np.ndarray = oem1_km[3:6]
    pos2: np.ndarray = oem2_km[0:3]
    vel2: np.ndarray = oem2_km[3:6]

    time_diff_s: float = (epoch2 - epoch1).total_seconds()

    pos_diff: np.ndarray = pos2 - pos1
    pos_diff_magnitude_km: float = float(np.linalg.norm(pos_diff))

    vel_diff: np.ndarray = vel2 - vel1
    vel_diff_magnitude_km_s: float = float(np.linalg.norm(vel_diff))

    return {
        "epoch1": epoch1,
        "epoch2": epoch2,
        "time_diff_s": time_diff_s,
        "position_diff_km": pos_diff,
        "position_diff_magnitude_km": pos_diff_magnitude_km,
        "velocity_diff_km_s": vel_diff,
        "velocity_diff_magnitude_km_s": vel_diff_magnitude_km_s,
    }


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with attributes ``oem1``, ``oem2``,
        and ``verbose``.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Compare two OEM-like Cartesian states and report differences in time, "
            "position, and velocity."
        )
    )
    parser.add_argument(
        "oem1",
        metavar="<oem1.oem>",
        help="First OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "oem2",
        metavar="<oem2.oem>",
        help="Second OEM file path or '-' to read from stdin.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed component-wise differences.",
    )
    args = parser.parse_args()
    if args.oem1 == "-" and args.oem2 == "-":
        parser.error("oem1 and oem2 cannot both be '-'")
    return args


def print_results(diff: ComparisonResult, verbose: bool = False) -> None:
    """Print comparison results.

    Parameters
    ----------
    diff : ComparisonResult
        Comparison results from :func:`compare_states`.
    verbose : bool, optional
        If True, print component-wise differences (default: False).
    """
    print("State Comparison Results:")
    print("=" * 70)
    print(f"State 1 Epoch: {time_utils.datetime_to_iso8601(diff['epoch1'])}")
    print(f"State 2 Epoch: {time_utils.datetime_to_iso8601(diff['epoch2'])}")
    print()
    print(f"Time Difference: {diff['time_diff_s']:.6f} seconds")
    print()
    print("Position Difference:")
    print(f"  Magnitude: {diff['position_diff_magnitude_km']:.9f} km")
    if verbose:
        print(f"  ΔX: {diff['position_diff_km'][0]:+.9f} km")
        print(f"  ΔY: {diff['position_diff_km'][1]:+.9f} km")
        print(f"  ΔZ: {diff['position_diff_km'][2]:+.9f} km")
    print()
    print("Velocity Difference:")
    print(f"  Magnitude: {diff['velocity_diff_magnitude_km_s']:.12f} km/s")
    if verbose:
        print(f"  ΔVX: {diff['velocity_diff_km_s'][0]:+.12f} km/s")
        print(f"  ΔVY: {diff['velocity_diff_km_s'][1]:+.12f} km/s")
        print(f"  ΔVZ: {diff['velocity_diff_km_s'][2]:+.12f} km/s")
    print("=" * 70)


def main() -> None:
    """Main entry point for the state comparison CLI.

    Parses command-line arguments, reads two OEM-like state vectors from
    files or stdin, compares them, and prints the differences to stdout.
    Exits with status 1 on error.
    """
    args: argparse.Namespace = parse_arguments()

    try:
        if args.oem1 == "-":
            oem1 = read_state_from_stdin()
            oem2 = read_state_from_file(args.oem2)
        else:
            oem1 = read_state_from_file(args.oem1)
            if args.oem2 == "-":
                oem2 = read_state_from_stdin()
            else:
                oem2 = read_state_from_file(args.oem2)

        diff: ComparisonResult = compare_states(oem1, oem2)

        print_results(diff, verbose=args.verbose)

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
