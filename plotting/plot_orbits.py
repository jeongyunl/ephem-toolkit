#!/usr/bin/env python3
"""Plot multiple orbit trajectories with various views and RTN coordinates.

This script reads multiple OEM or raw-state files and overlays orbit data in
different views (3D, XY, XZ, YZ) as well as RTN (Radial-Transverse-Normal)
coordinates. The first input file is treated as the reference orbit trajectory
that other orbit trajectories are compared with.

Usage:
    python plot_orbits.py <reference_oem> [comparison_oem1] [comparison_oem2] ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

import tudatpy.math.interpolators as interpolators

# Add parent directory to path to import common utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.common import parse_oem_state_line, parse_duration_to_seconds
from common.oem import read_oem


def read_orbit_file(filepath: str | Path) -> dict[float, np.ndarray]:
    """Read an OEM or raw-state file and return state history.

    Parameters
    ----------
    filepath : str | Path
        Path to the OEM or raw-state file.

    Returns
    -------
    dict[float, np.ndarray]
        State history: dictionary mapping epoch timestamps (float, seconds since epoch) to
        state vectors (6-element numpy arrays [x, y, z, vx, vy, vz] in km and km/s).
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    state_history = {}

    # Try reading as OEM file first (more robust)
    try:
        header, meta, raw_states = read_oem(filepath)
        for epoch_dt, state in raw_states.items():
            timestamp = epoch_dt.timestamp()
            state_history[timestamp] = state
        return state_history
    except Exception:
        pass

    # Fall back to line-by-line parsing for raw state files
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                result = parse_oem_state_line(line)
                if result is not None:
                    epoch_dt, position_km, velocity_km_s = result
                    timestamp = epoch_dt.timestamp()
                    state = np.concatenate([position_km, velocity_km_s])
                    state_history[timestamp] = state
            except ValueError:
                # Skip lines that don't parse (headers, comments, etc.)
                continue

    if not state_history:
        raise ValueError(f"Could not parse any state data from {filepath}")

    return state_history


def compute_rsw_frame(position: np.ndarray, velocity: np.ndarray) -> np.ndarray:
    """Compute RTN (Radial-Transverse-Normal) frame transformation matrix.

    Parameters
    ----------
    position : np.ndarray
        Position vector in km (3-element array).
    velocity : np.ndarray
        Velocity vector in km/s (3-element array).

    Returns
    -------
    np.ndarray
        3x3 transformation matrix from inertial to RTN frame.
    """
    # R: radial direction (along position)
    r_mag = np.linalg.norm(position)
    r_hat = position / r_mag

    # W: normal to orbital plane (along angular momentum)
    h = np.cross(position, velocity)
    h_mag = np.linalg.norm(h)
    w_hat = h / h_mag

    # S: transverse direction (completes right-handed system)
    s_hat = np.cross(w_hat, r_hat)

    # Transformation matrix (rows are RTN basis vectors)
    return np.array([r_hat, s_hat, w_hat])


def transform_to_rsw(states: np.ndarray) -> np.ndarray:
    """Transform state vectors to RTN coordinates.

    Parameters
    ----------
    states : np.ndarray
        Array of state vectors, shape (N, 6) with [x, y, z, vx, vy, vz].

    Returns
    -------
    np.ndarray
        Array of RTN coordinates, shape (N, 6) with [r, s, w, vr, vs, vw].
    """
    rsw_states = np.zeros_like(states)

    for i, state in enumerate(states):
        position = state[:3]
        velocity = state[3:]

        # Compute RTN transformation matrix
        rsw_matrix = compute_rsw_frame(position, velocity)

        # Transform position and velocity
        rsw_states[i, :3] = rsw_matrix @ position
        rsw_states[i, 3:] = rsw_matrix @ velocity

    return rsw_states


def get_interpolated_state(interpolator, timestamp: float) -> np.ndarray | None:
    """Get interpolated state at a given timestamp.

    Parameters
    ----------
    interpolator : interpolator or None
        Interpolator object from tudatpy.
    timestamp : float
        Timestamp to interpolate at.

    Returns
    -------
    np.ndarray
        Interpolated state vector.
    """

    # TODO improve get_interpolated_state. Dedicated interpolator for the last N points?

    if (
        timestamp < interpolator.independent_values[0]
        or timestamp > interpolator.independent_values[-1]
    ):
        return None

    return interpolator.interpolate(timestamp)


def plot_orbits(
    reference_state_history: dict[float, np.ndarray],
    comparison_data: list[tuple[str, dict[float, np.ndarray]]],
    output_file: Optional[str] = None,
) -> None:
    """Plot multiple orbits in various views.

    Parameters
    ----------
    reference_state_history : dict[float, np.ndarray]
        State history for reference orbit (timestamp -> state vector).
    comparison_data : list[tuple[str, dict[float, np.ndarray]]]
        List of (label, state_history) tuples for comparison orbits.
    output_file : str, optional
        Path to save the figure. If None, displays interactively.
    """
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))

    # Extract reference positions and states
    ref_timestamps = sorted(reference_state_history.keys())
    ref_pos = np.array([reference_state_history[ts][:3] for ts in ref_timestamps])
    ref_states = np.array([reference_state_history[ts] for ts in ref_timestamps])
    ref_rsw = transform_to_rsw(ref_states)

    # Create all axes
    ax1 = fig.add_subplot(2, 3, 1, projection="3d")
    ax2 = fig.add_subplot(2, 3, 2)
    ax3 = fig.add_subplot(2, 3, 3)
    ax4 = fig.add_subplot(2, 3, 4)
    ax5 = fig.add_subplot(2, 3, 5)
    ax6 = fig.add_subplot(2, 3, 6)

    # Plot reference data on all axes
    ax1.plot(
        ref_pos[:, 0],
        ref_pos[:, 1],
        ref_pos[:, 2],
        "b-",
        linewidth=2,
        label="Reference",
    )
    ax1.scatter(
        ref_pos[0, 0],
        ref_pos[0, 1],
        ref_pos[0, 2],
        c="b",
        s=100,
        marker="o",
        label="Start",
    )
    ax1.scatter(
        ref_pos[-1, 0],
        ref_pos[-1, 1],
        ref_pos[-1, 2],
        c="b",
        s=100,
        marker="x",
        label="End",
    )

    ax2.plot(ref_pos[:, 0], ref_pos[:, 1], "b-", linewidth=2, label="Reference")
    ax2.scatter(ref_pos[0, 0], ref_pos[0, 1], c="b", s=100, marker="o", label="Start")
    ax2.scatter(ref_pos[-1, 0], ref_pos[-1, 1], c="b", s=100, marker="x", label="End")

    ax3.plot(ref_pos[:, 0], ref_pos[:, 2], "b-", linewidth=2, label="Reference")
    ax3.scatter(ref_pos[0, 0], ref_pos[0, 2], c="b", s=100, marker="o", label="Start")
    ax3.scatter(ref_pos[-1, 0], ref_pos[-1, 2], c="b", s=100, marker="x", label="End")

    ax4.plot(ref_pos[:, 1], ref_pos[:, 2], "b-", linewidth=2, label="Reference")
    ax4.scatter(ref_pos[0, 1], ref_pos[0, 2], c="b", s=100, marker="o", label="Start")
    ax4.scatter(ref_pos[-1, 1], ref_pos[-1, 2], c="b", s=100, marker="x", label="End")

    ax5.plot(ref_rsw[:, 1], ref_rsw[:, 0], "b-", linewidth=2, label="Reference")
    ax5.scatter(ref_rsw[0, 1], ref_rsw[0, 0], c="b", s=100, marker="o", label="Start")
    ax5.scatter(ref_rsw[-1, 1], ref_rsw[-1, 0], c="b", s=100, marker="x", label="End")

    ax6.plot(ref_rsw[:, 2], ref_rsw[:, 0], "b-", linewidth=2, label="Reference")
    ax6.scatter(ref_rsw[0, 2], ref_rsw[0, 0], c="b", s=100, marker="o", label="Start")
    ax6.scatter(ref_rsw[-1, 2], ref_rsw[-1, 0], c="b", s=100, marker="x", label="End")

    # Plot comparison data in a single loop
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        # Extract positions for Cartesian plots
        pos_data = np.array([state_history[ts][:3] for ts in comp_timestamps])

        # Extract and transform states for RSW plots
        states = np.array([state_history[ts] for ts in comp_timestamps])
        rsw_data = transform_to_rsw(states)

        # Plot on all axes
        ax1.plot(
            pos_data[:, 0], pos_data[:, 1], pos_data[:, 2], linewidth=2, label=label
        )
        ax2.plot(pos_data[:, 0], pos_data[:, 1], linewidth=2, label=label)
        ax3.plot(pos_data[:, 0], pos_data[:, 2], linewidth=2, label=label)
        ax4.plot(pos_data[:, 1], pos_data[:, 2], linewidth=2, label=label)
        ax5.plot(rsw_data[:, 1], rsw_data[:, 0], linewidth=2, label=label)
        ax6.plot(rsw_data[:, 2], rsw_data[:, 0], linewidth=2, label=label)

    # Configure all axes
    ax1.set_xlabel("X (km)")
    ax1.set_ylabel("Y (km)")
    ax1.set_zlabel("Z (km)")
    ax1.set_title("3D Orbit Trajectory")
    ax1.legend()
    ax1.grid(True)

    ax2.set_xlabel("X (km)")
    ax2.set_ylabel("Y (km)")
    ax2.set_title("XY Plane")
    ax2.legend()
    ax2.grid(True)
    ax2.axis("equal")

    ax3.set_xlabel("X (km)")
    ax3.set_ylabel("Z (km)")
    ax3.set_title("XZ Plane")
    ax3.legend()
    ax3.grid(True)
    ax3.axis("equal")

    ax4.set_xlabel("Y (km)")
    ax4.set_ylabel("Z (km)")
    ax4.set_title("YZ Plane")
    ax4.legend()
    ax4.grid(True)
    ax4.axis("equal")

    ax5.set_xlabel("Transverse (km)")
    ax5.set_ylabel("Radial (km)")
    ax5.set_title("RTN: Radial-Transverse Plane")
    ax5.legend()
    ax5.grid(True)
    ax5.axis("equal")

    ax6.set_xlabel("Normal (km)")
    ax6.set_ylabel("Radial (km)")
    ax6.set_title("RTN: Radial-Normal Plane")
    ax6.legend()
    ax6.grid(True)
    ax6.axis("equal")

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_relative_cartesian_timeseries(
    reference_interpolator,
    comparison_data: list[tuple[str, dict[float, np.ndarray]]],
    output_file: Optional[str] = None,
) -> None:
    """Plot time series of relative position and velocity in Cartesian coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit
    as a function of time in Cartesian coordinates.

    Parameters
    ----------
    reference_interpolator : interpolator or None
        Interpolator for reference orbit state history.
    comparison_data : list[tuple[str, dict[float, np.ndarray]]]
        List of (label, state_history) tuples for comparison orbits.
    output_file : str, optional
        Path to save the figure. If None, displays interactively.
    """
    fig = plt.figure(figsize=(16, 12))

    # Create all axes
    ax1 = fig.add_subplot(3, 2, 1)
    ax2 = fig.add_subplot(3, 2, 2)
    ax3 = fig.add_subplot(3, 2, 3)
    ax4 = fig.add_subplot(3, 2, 4)
    ax5 = fig.add_subplot(3, 2, 5)
    ax6 = fig.add_subplot(3, 2, 6)

    ax1.ticklabel_format(style="plain", axis="y")
    ax2.ticklabel_format(style="plain", axis="y")
    ax3.ticklabel_format(style="plain", axis="y")
    ax4.ticklabel_format(style="plain", axis="y")
    ax5.ticklabel_format(style="plain", axis="y")
    ax6.ticklabel_format(style="plain", axis="y")

    # Add reference lines
    ax1.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax2.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax3.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax4.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax5.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax6.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)

    # Plot comparison data in a single loop
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        # Compute deltas for all 6 components
        delta_times = []
        deltas = [[], [], [], [], [], []]  # x, y, z, vx, vy, vz

        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_times.append(ts)
                for i in range(6):
                    deltas[i].append(comp_state[i] - ref_state[i])

        # Plot on all axes if data exists
        if delta_times:
            ax1.plot(delta_times, deltas[0], linewidth=2, label=label, alpha=0.7)
            ax2.plot(delta_times, deltas[1], linewidth=2, label=label, alpha=0.7)
            ax3.plot(delta_times, deltas[2], linewidth=2, label=label, alpha=0.7)
            ax4.plot(delta_times, deltas[3], linewidth=2, label=label, alpha=0.7)
            ax5.plot(delta_times, deltas[4], linewidth=2, label=label, alpha=0.7)
            ax6.plot(delta_times, deltas[5], linewidth=2, label=label, alpha=0.7)

    # Configure all axes
    ax1.set_ylabel("X Position Delta (km)")
    ax1.set_title("X Position Delta vs Time")
    ax1.legend()
    ax1.grid(True)

    ax2.set_ylabel("Y Position Delta (km)")
    ax2.set_title("Y Position Delta vs Time")
    ax2.legend()
    ax2.grid(True)

    ax3.set_ylabel("Z Position Delta (km)")
    ax3.set_title("Z Position Delta vs Time")
    ax3.legend()
    ax3.grid(True)

    ax4.set_ylabel("Vx Velocity Delta (km/s)")
    ax4.set_title("Vx Velocity Delta vs Time")
    ax4.legend()
    ax4.grid(True)

    ax5.set_xlabel("Time from Start (seconds)")
    ax5.set_ylabel("Vy Velocity Delta (km/s)")
    ax5.set_title("Vy Velocity Delta vs Time")
    ax5.legend()
    ax5.grid(True)

    ax6.set_xlabel("Time from Start (seconds)")
    ax6.set_ylabel("Vz Velocity Delta (km/s)")
    ax6.set_title("Vz Velocity Delta vs Time")
    ax6.legend()
    ax6.grid(True)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_relative_rtn_timeseries(
    reference_interpolator,
    comparison_data: list[tuple[str, dict[float, np.ndarray]]],
    output_file: Optional[str] = None,
) -> None:
    """Plot time series of relative position and velocity in RTN coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit
    as a function of time in RTN coordinates.

    Parameters
    ----------
    reference_interpolator : interpolator or None
        Interpolator for reference orbit state history.
    comparison_data : list[tuple[str, dict[float, np.ndarray]]]
        List of (label, state_history) tuples for comparison orbits.
    output_file : str, optional
        Path to save the figure. If None, displays interactively.
    """
    fig = plt.figure(figsize=(16, 12))

    # Create all axes
    ax1 = fig.add_subplot(3, 2, 1)
    ax2 = fig.add_subplot(3, 2, 2)
    ax3 = fig.add_subplot(3, 2, 3)
    ax4 = fig.add_subplot(3, 2, 4)
    ax5 = fig.add_subplot(3, 2, 5)
    ax6 = fig.add_subplot(3, 2, 6)

    ax1.ticklabel_format(style="plain", axis="y")
    ax2.ticklabel_format(style="plain", axis="y")
    ax3.ticklabel_format(style="plain", axis="y")
    ax4.ticklabel_format(style="plain", axis="y")
    ax5.ticklabel_format(style="plain", axis="y")
    ax6.ticklabel_format(style="plain", axis="y")

    # Add reference lines
    ax1.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax2.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax3.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax4.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax5.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax6.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)

    # Plot comparison data in a single loop
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        # Compute deltas for all 6 RTN components
        delta_times = []
        deltas = [[], [], [], [], [], []]  # r, s, w, vr, vs, vw

        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                # Transform to RTN
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_times.append(ts)
                for i in range(6):
                    deltas[i].append(comp_rsw[i] - ref_rsw[i])

        # Plot on all axes if data exists
        if delta_times:
            ax1.plot(delta_times, deltas[0], linewidth=2, label=label, alpha=0.7)
            ax2.plot(delta_times, deltas[1], linewidth=2, label=label, alpha=0.7)
            ax3.plot(delta_times, deltas[2], linewidth=2, label=label, alpha=0.7)
            ax4.plot(delta_times, deltas[3], linewidth=2, label=label, alpha=0.7)
            ax5.plot(delta_times, deltas[4], linewidth=2, label=label, alpha=0.7)
            ax6.plot(delta_times, deltas[5], linewidth=2, label=label, alpha=0.7)

    # Configure all axes
    ax1.set_ylabel("Radial Delta (km)")
    ax1.set_title("Radial Position Delta vs Time")
    ax1.legend()
    ax1.grid(True)

    ax2.set_ylabel("Transverse Delta (km)")
    ax2.set_title("Transverse Position Delta vs Time")
    ax2.legend()
    ax2.grid(True)

    ax3.set_ylabel("Normal Delta (km)")
    ax3.set_title("Normal Position Delta vs Time")
    ax3.legend()
    ax3.grid(True)

    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Radial Velocity Delta vs Time")
    ax4.legend()
    ax4.grid(True)

    ax5.set_xlabel("Time from Start (seconds)")
    ax5.set_ylabel("Transverse Velocity Delta (km/s)")
    ax5.set_title("Transverse Velocity Delta vs Time")
    ax5.legend()
    ax5.grid(True)

    ax6.set_xlabel("Time from Start (seconds)")
    ax6.set_ylabel("Normal Velocity Delta (km/s)")
    ax6.set_title("Normal Velocity Delta vs Time")
    ax6.legend()
    ax6.grid(True)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_relative_rtn_orbits(
    reference_interpolator,
    comparison_data: list[tuple[str, dict[float, np.ndarray]]],
    output_file: Optional[str] = None,
) -> None:
    """Plot relative RTN orbits (deltas) in RTN coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit.

    Parameters
    ----------
    reference_interpolator : interpolator or None
        Interpolator for reference orbit state history.
    comparison_data : list[tuple[str, dict[float, np.ndarray]]]
        List of (label, state_history) tuples for comparison orbits.
    output_file : str, optional
        Path to save the figure. If None, displays interactively.
    """
    fig = plt.figure(figsize=(14, 10))

    # Create all axes
    ax1 = fig.add_subplot(2, 2, 1)
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 3)
    ax4 = fig.add_subplot(2, 2, 4)

    ax1.ticklabel_format(style="plain", axis="y")
    ax2.ticklabel_format(style="plain", axis="y")
    ax3.ticklabel_format(style="plain", axis="y")
    ax4.ticklabel_format(style="plain", axis="y")

    # Add reference points
    ax1.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)
    ax2.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)
    ax3.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)
    ax4.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)

    # Plot comparison data in a single loop
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        # Compute all deltas for all 4 plots
        deltas_rs = []  # Radial-Transverse position
        deltas_rw = []  # Radial-Normal position
        deltas_vrs = []  # Radial-Transverse velocity
        deltas_vrw = []  # Radial-Normal velocity

        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                # Transform to RTN
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]

                # Compute position deltas
                delta_r = comp_rsw[0] - ref_rsw[0]
                delta_s = comp_rsw[1] - ref_rsw[1]
                delta_w = comp_rsw[2] - ref_rsw[2]

                # Compute velocity deltas
                delta_vr = comp_rsw[3] - ref_rsw[3]
                delta_vs = comp_rsw[4] - ref_rsw[4]
                delta_vw = comp_rsw[5] - ref_rsw[5]

                deltas_rs.append([delta_s, delta_r])
                deltas_rw.append([delta_w, delta_r])
                deltas_vrs.append([delta_vs, delta_vr])
                deltas_vrw.append([delta_vw, delta_vr])

        # Convert to arrays and plot on all axes if data exists
        if deltas_rs:
            deltas_rs = np.array(deltas_rs)
            deltas_rw = np.array(deltas_rw)
            deltas_vrs = np.array(deltas_vrs)
            deltas_vrw = np.array(deltas_vrw)

            ax1.plot(
                deltas_rs[:, 0],
                deltas_rs[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=label,
                alpha=0.7,
            )
            ax2.plot(
                deltas_rw[:, 0],
                deltas_rw[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=label,
                alpha=0.7,
            )
            ax3.plot(
                deltas_vrs[:, 0],
                deltas_vrs[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=label,
                alpha=0.7,
            )
            ax4.plot(
                deltas_vrw[:, 0],
                deltas_vrw[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=label,
                alpha=0.7,
            )

    # Configure all axes
    ax1.set_xlabel("Transverse Delta (km)")
    ax1.set_ylabel("Radial Delta (km)")
    ax1.set_title("Relative Position Delta: Radial-Transverse")
    ax1.legend()
    ax1.grid(True)
    ax1.axis("equal")

    ax2.set_xlabel("Normal Delta (km)")
    ax2.set_ylabel("Radial Delta (km)")
    ax2.set_title("Relative Position Delta: Radial-Normal")
    ax2.legend()
    ax2.grid(True)
    ax2.axis("equal")

    ax3.set_xlabel("Transverse Velocity Delta (km/s)")
    ax3.set_ylabel("Radial Velocity Delta (km/s)")
    ax3.set_title("Relative Velocity Delta: Radial-Transverse")
    ax3.legend()
    ax3.grid(True)

    ax4.set_xlabel("Normal Velocity Delta (km/s)")
    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Relative Velocity Delta: Radial-Normal")
    ax4.legend()
    ax4.grid(True)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Plot multiple orbit trajectories with various views and RTN coordinates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot single orbit
  python plot_orbits.py reference.oem

  # Plot reference orbit with comparison orbits
  python plot_orbits.py reference.oem comparison1.oem comparison2.oem

  # Save output to file
  python plot_orbits.py reference.oem comparison.oem -o orbits.png
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

    args = parser.parse_args()

    if len(args.files) < 1:
        parser.print_help()
        sys.exit(1)

    # Parse duration if provided
    duration_seconds = None
    if args.duration:
        try:
            duration_seconds = parse_duration_to_seconds(args.duration)
            print(
                f"Analyzing data for duration: {args.duration} ({duration_seconds:.0f} seconds)"
            )
        except Exception as e:
            print(f"Error parsing duration: {e}")
            sys.exit(1)

    # Read reference orbit
    print(f"Reading reference orbit from {args.files[0]}...")
    ref_state_history = read_orbit_file(args.files[0])
    print(f"  Loaded {len(ref_state_history)} states")

    # Read comparison orbits
    comparison_data = []
    for filepath in args.files[1:]:
        print(f"Reading comparison orbit from {filepath}...")
        state_history = read_orbit_file(filepath)
        print(f"  Loaded {len(state_history)} states")

        label = Path(filepath).name
        comparison_data.append((label, state_history))

    # Calculate end timestamp from reference state history and duration option
    ref_timestamps = sorted(ref_state_history.keys())
    start_timestamp = ref_timestamps[0]

    if duration_seconds is not None:
        end_timestamp = start_timestamp + duration_seconds
    else:
        end_timestamp = ref_timestamps[-1]

    print(f"Reference orbit end timestamp: {end_timestamp}")

    interpolator_number_of_points = 8

    # TODO improve interpolation

    # Filter reference and comparison data using end timestamp
    # Include up to interpolator_number_of_points/2 additional states past end_timestamp for reference orbit
    ref_timestamps_sorted = sorted(ref_state_history.keys())
    end_idx = next(
        (i for i, ts in enumerate(ref_timestamps_sorted) if ts > end_timestamp),
        len(ref_timestamps_sorted),
    )
    # Include states up to end_timestamp plus up to interpolator_number_of_points more states
    include_count = min(
        int(interpolator_number_of_points / 2), len(ref_timestamps_sorted) - end_idx
    )
    cutoff_idx = end_idx + include_count
    ref_state_history = {
        ts: state
        for ts, state in ref_state_history.items()
        if ts in ref_timestamps_sorted[:cutoff_idx]
    }
    filtered_comparison_data = []
    for label, state_history in comparison_data:
        filtered_state_history = {
            ts: state for ts, state in state_history.items() if ts <= end_timestamp
        }
        filtered_comparison_data.append((label, filtered_state_history))
    comparison_data = filtered_comparison_data

    # Determine output files
    def get_output_filename(base_output: Optional[str], suffix: str) -> Optional[str]:
        """Generate output filename with suffix if base output is provided."""
        if base_output is None:
            return None
        path = Path(base_output)
        stem = path.stem
        suffix_str = f"_{suffix}"
        return str(path.parent / f"{stem}{suffix_str}{path.suffix}")

    # Create interpolator for reference orbit
    print("Creating interpolator for reference orbit...")
    ref_interpolator = interpolators.create_one_dimensional_vector_interpolator(
        ref_state_history,
        interpolators.lagrange_interpolation(
            interpolator_number_of_points,
            # boundary_interpolation=interpolators.BoundaryInterpolationType.use_boundary_value,
        ),
    )

    # Plot orbits - save all output files by default
    print("Plotting absolute orbits in multiple views...")
    plot_orbits(ref_state_history, comparison_data, args.output)

    print("Plotting relative orbits in RTN coordinates...")
    relative_rtn_output = get_output_filename(args.output, "relative_rtn")
    plot_relative_rtn_orbits(ref_interpolator, comparison_data, relative_rtn_output)

    print(
        "Plotting time series of relative position and velocity in Cartesian coordinates..."
    )
    relative_cartesian_timeseries_output = get_output_filename(
        args.output, "relative_cartesian_timeseries"
    )
    plot_relative_cartesian_timeseries(
        ref_interpolator, comparison_data, relative_cartesian_timeseries_output
    )

    print(
        "Plotting time series of relative position and velocity in RTN coordinates..."
    )
    relative_rtn_timeseries_output = get_output_filename(
        args.output, "relative_rtn_timeseries"
    )
    plot_relative_rtn_timeseries(
        ref_interpolator, comparison_data, relative_rtn_timeseries_output
    )

    if args.output is None:
        plt.show()

    print("Done!")


if __name__ == "__main__":
    main()
