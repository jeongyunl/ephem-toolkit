#!/usr/bin/env python3
"""Compare two OEM-like Cartesian state vectors and report differences.

Provides :func:`compare_states` to compute time, position, and velocity
differences between two state vectors, and a CLI entry point to read states
from files or stdin and display the comparison results.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Add parent directory to path to import common module
sys.path.insert(0, str(Path(__file__).parent.parent))

import common.common as common
import common.oem as oem


def read_state_from_file(filepath: str) -> tuple:
    """Read a single OEM-like state line from a file.

    Skips comments and blank lines, returns the first valid state found.

    Parameters
    ----------
    filepath : str
        Path to file containing OEM-like state data.

    Returns
    -------
    tuple
        ``(epoch_dt, state_km)`` tuple where *state_km* is a 6-element vector
        ``[x, y, z, vx, vy, vz]`` in km / km·s⁻¹.

    Raises
    ------
    ValueError
        If file cannot be read or no valid state is found.
    """
    try:
        with open(filepath, "r") as f:
            for line in f:
                parsed: tuple | None = oem.parse_oem_state_line(line)
                if parsed is not None:
                    return parsed
    except OSError as error:
        raise ValueError(f"Could not read file '{filepath}': {error}") from error

    raise ValueError(f"No valid OEM-like state found in '{filepath}'")


def read_state_from_stdin() -> tuple:
    """Read a single OEM-like state line from stdin.

    Returns
    -------
    tuple
        ``(epoch_dt, state_km)`` tuple where *state_km* is a 6-element vector
        ``[x, y, z, vx, vy, vz]`` in km / km·s⁻¹.

    Raises
    ------
    ValueError
        If no valid state is found in stdin.
    """
    for line in sys.stdin:
        parsed: tuple | None = oem.parse_oem_state_line(line)
        if parsed is not None:
            return parsed

    raise ValueError("No valid OEM-like state found in stdin")


def compare_states(state1: tuple, state2: tuple) -> dict:
    """Compare two OEM-like states and return differences.

    Parameters
    ----------
    state1 : tuple
        First state: ``(epoch_dt, state_km)`` where *state_km* is a 6-element
        vector ``[x, y, z, vx, vy, vz]`` in km / km·s⁻¹.
    state2 : tuple
        Second state: ``(epoch_dt, state_km)`` where *state_km* is a 6-element
        vector ``[x, y, z, vx, vy, vz]`` in km / km·s⁻¹.

    Returns
    -------
    dict
        Dictionary containing:
        - epoch1, epoch2: datetime objects
        - time_diff_s: time difference in seconds
        - position_diff_km: 3-element array of position differences
        - position_diff_magnitude_km: magnitude of position difference
        - velocity_diff_km_s: 3-element array of velocity differences
        - velocity_diff_magnitude_km_s: magnitude of velocity difference
    """
    epoch1, state1_km = state1
    epoch2, state2_km = state2
    pos1: np.ndarray = state1_km[0:3]
    vel1: np.ndarray = state1_km[3:6]
    pos2: np.ndarray = state2_km[0:3]
    vel2: np.ndarray = state2_km[3:6]

    # Time difference
    time_diff_s: float = (epoch2 - epoch1).total_seconds()

    # Position difference
    pos_diff: np.ndarray = pos2 - pos1
    pos_diff_magnitude: np.floating = np.linalg.norm(pos_diff)

    # Velocity difference
    vel_diff: np.ndarray = vel2 - vel1
    vel_diff_magnitude: np.floating = np.linalg.norm(vel_diff)

    return {
        "epoch1": epoch1,
        "epoch2": epoch2,
        "time_diff_s": time_diff_s,
        "position_diff_km": pos_diff,
        "position_diff_magnitude_km": pos_diff_magnitude,
        "velocity_diff_km_s": vel_diff,
        "velocity_diff_magnitude_km_s": vel_diff_magnitude,
    }


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments with attributes ``state1``, ``state2``,
        and ``verbose``.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Compare two OEM-like Cartesian states and report differences in time, "
            "position, and velocity."
        )
    )
    parser.add_argument(
        "state1",
        nargs="?",
        default="-",
        metavar="<state1.dat>",
        help=(
            "First OEM-like state file path or '-' to read from stdin (default: '-'). "
            "If both state1 and state2 are '-', reads two states from stdin sequentially."
        ),
    )
    parser.add_argument(
        "state2",
        nargs="?",
        default="-",
        metavar="<state2.dat>",
        help=(
            "Second OEM-like state file path or '-' to read from stdin (default: '-'). "
            "If both state1 and state2 are '-', reads two states from stdin sequentially."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed component-wise differences.",
    )
    return parser.parse_args()


def print_results(diff: dict, verbose: bool = False) -> None:
    """Print comparison results.

    Parameters
    ----------
    diff : dict
        Comparison results from compare_states().
    verbose : bool, optional
        If True, print component-wise differences (default: False).
    """
    print("State Comparison Results:")
    print("=" * 70)
    print(f"State 1 Epoch: {common.datetime_to_iso8601(diff['epoch1'])}")
    print(f"State 2 Epoch: {common.datetime_to_iso8601(diff['epoch2'])}")
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
        # Read first state
        if args.state1 == "-":
            state1: tuple = read_state_from_stdin()
        else:
            state1 = read_state_from_file(args.state1)

        # Read second state
        if args.state2 == "-":
            state2: tuple = read_state_from_stdin()
        else:
            state2 = read_state_from_file(args.state2)

        # Compare states
        diff: dict = compare_states(state1, state2)

        # Print results
        print_results(diff, verbose=args.verbose)

    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
