#!/usr/bin/env python3
"""Plot multiple orbit trajectories with various views and RTN coordinates.

This script reads multiple OEM or raw-state files and overlays orbit data in
different views (3D, XY, XZ, YZ) as well as RTN (Radial-Transverse-Normal)
coordinates. The first input file is treated as the reference orbit trajectory
that other orbit trajectories are compared with.

Usage:
    plot-orbit-deltas <reference_oem> [comparison_oem1] [comparison_oem2] ...
"""

from __future__ import annotations

import argparse
import bisect
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import tudatpy_utils.core.time_utils as time_utils

from .constants import DEFAULT_INTERPOLATION_DEGREE
from .data_structures import StateHistory, TimeUnit
from .file_io import read_orbit_file
from .plotting import (
    plot_angular_separation,
    plot_orbits,
    plot_relative_cartesian_timeseries,
    plot_relative_rtn_orbits,
    plot_relative_rtn_timeseries,
)


def generate_output_filename(base_output: str | None, suffix: str) -> str | None:
    """Generate output filename with suffix if base output is provided.

    Parameters
    ----------
    base_output : str | None
        Base output filename, or None.
    suffix : str
        Suffix to append to the filename stem.

    Returns
    -------
    str | None
        Generated filename with suffix, or None if base_output is None.
    """
    if base_output is None:
        return None
    path = Path(base_output)
    stem = path.stem
    suffix_str = f"_{suffix}"
    return str(path.parent / f"{stem}{suffix_str}{path.suffix}")


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Plot multiple orbit trajectories with various views and RTN coordinates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot single orbit
  python3 plot_orbits.py reference.oem

  # Plot reference orbit with comparison orbits
  python3 plot_orbits.py reference.oem comparison1.oem comparison2.oem

  # Save output to file
  python3 plot_orbits.py reference.oem comparison.oem -o orbits.png
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="OEM or raw-state files. First file is the reference orbit.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path for saving the figure (e.g., orbits.png)",
    )

    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        default=None,
        help="Duration of data to analyze from start (e.g., 1h, 30m, 3600s)",
    )

    parser.add_argument(
        "--time-unit",
        type=str,
        default="hours",
        choices=["m", "minute", "minutes", "h", "hour", "hours"],
        help="Time unit for time series plots: m/minute/minutes or h/hour/hours (default: hours)",
    )

    args = parser.parse_args()

    if len(args.files) < 1:
        parser.print_help()
        sys.exit(1)

    # Parse duration if provided
    duration_s: float | None = None
    if args.duration:
        try:
            duration_s = time_utils.parse_duration_to_seconds(args.duration)
            print(
                f"Analyzing data for duration: {args.duration} ({duration_s:.0f} seconds)"
            )
        except Exception as e:
            print(f"Error parsing duration: {e}")
            sys.exit(1)

    # Read reference orbit
    print(f"Reading reference orbit from {args.files[0]}...")
    ref_state_history: dict[float, np.ndarray] = read_orbit_file(args.files[0])
    print(f"  Loaded {len(ref_state_history)} states")

    # Read comparison orbits
    comparison_data: list[StateHistory] = []
    for filepath in args.files[1:]:
        print(f"Reading comparison orbit from {filepath}...")
        state_history: dict[float, np.ndarray] = read_orbit_file(filepath)
        print(f"  Loaded {len(state_history)} states")

        label: str = Path(filepath).name
        comparison_data.append(StateHistory(label=label, state_history=state_history))

    # Calculate end timestamp from reference state history and duration option
    ref_timestamps_sorted: list[float] = sorted(ref_state_history.keys())
    start_timestamp_s: float = ref_timestamps_sorted[0]

    if duration_s is not None:
        end_timestamp_s: float = start_timestamp_s + duration_s
    else:
        end_timestamp_s: float = ref_timestamps_sorted[-1]

    print(f"Reference orbit end timestamp: {end_timestamp_s}")

    # Filter reference and comparison data using end timestamp
    # Include up to (DEFAULT_INTERPOLATION_DEGREE + 1)/2 additional states past end_timestamp_s for interpolation
    end_idx: int = bisect.bisect_left(ref_timestamps_sorted, end_timestamp_s)

    # Include states up to end_timestamp_s plus additional states for interpolation
    include_count: int = min(
        int((DEFAULT_INTERPOLATION_DEGREE + 1) / 2),
        len(ref_timestamps_sorted) - end_idx,
    )
    cutoff_idx: int = end_idx + include_count
    ref_state_history = {
        ts: state
        for ts, state in ref_state_history.items()
        if ts in ref_timestamps_sorted[:cutoff_idx]
    }

    reference_state_history_obj: StateHistory = StateHistory(
        label=Path(args.files[0]).name, state_history=ref_state_history
    )

    filtered_comparison_data: list[StateHistory] = []
    for orbit in comparison_data:
        filtered_state_history: dict[float, np.ndarray] = {
            ts: state
            for ts, state in orbit.state_history.items()
            if ts <= end_timestamp_s
        }
        filtered_comparison_data.append(
            StateHistory(label=orbit.label, state_history=filtered_state_history)
        )
    comparison_data = filtered_comparison_data

    time_unit: TimeUnit = TimeUnit.from_string(args.time_unit)

    print(
        "Plotting time series of relative position and velocity in RTN coordinates..."
    )
    relative_rtn_timeseries_output: str | None = generate_output_filename(
        args.output, "relative_rtn_timeseries"
    )
    plot_relative_rtn_timeseries(
        reference_state_history_obj,
        comparison_data,
        relative_rtn_timeseries_output,
        time_unit,
    )

    print("Plotting relative orbits in RTN coordinates...")
    relative_rtn_output: str | None = generate_output_filename(
        args.output, "relative_rtn"
    )
    plot_relative_rtn_orbits(
        reference_state_history_obj, comparison_data, relative_rtn_output
    )

    print(
        "Plotting time series of relative position and velocity in Cartesian coordinates..."
    )
    relative_cartesian_timeseries_output: str | None = generate_output_filename(
        args.output, "relative_cartesian_timeseries"
    )

    plot_relative_cartesian_timeseries(
        reference_state_history_obj,
        comparison_data,
        relative_cartesian_timeseries_output,
        time_unit,
    )

    print("Plotting angular separation from reference orbit...")
    angular_separation_output: str | None = generate_output_filename(
        args.output, "angular_separation"
    )
    plot_angular_separation(
        reference_state_history_obj,
        comparison_data,
        angular_separation_output,
        time_unit,
    )

    # Plot orbits
    print("Plotting absolute orbits in multiple views...")
    plot_orbits(reference_state_history_obj, comparison_data, args.output)

    if args.output is None:
        plt.show()

    print("Done!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl-C)")
        sys.exit(0)
