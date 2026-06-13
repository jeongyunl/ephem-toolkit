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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

try:
    import tudatpy.math.interpolators as interpolators

    TUDATPY_AVAILABLE = True
except ImportError:
    TUDATPY_AVAILABLE = False

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


def compute_relative_state(
    reference_state: np.ndarray, comparison_state: np.ndarray
) -> np.ndarray:
    """Compute relative state between reference and comparison orbits.

    Parameters
    ----------
    reference_state : np.ndarray
        Reference state vector [x, y, z, vx, vy, vz].
    comparison_state : np.ndarray
        Comparison state vector [x, y, z, vx, vy, vz].

    Returns
    -------
    np.ndarray
        Relative state vector (comparison - reference).
    """
    return comparison_state - reference_state


def filter_by_duration(
    state_history: dict[float, np.ndarray],
    duration_seconds: float,
) -> dict[float, np.ndarray]:
    """Filter orbit data to only include the specified duration from start.

    Parameters
    ----------
    state_history : dict[float, np.ndarray]
        State history dictionary mapping timestamps to state vectors.
    duration_seconds : float
        Duration in seconds from the first timestamp to include.

    Returns
    -------
    dict[float, np.ndarray]
        Filtered state history containing only data within the duration.
    """
    if not state_history:
        return state_history

    timestamps = sorted(state_history.keys())
    start_ts = timestamps[0]
    end_ts = start_ts + duration_seconds

    # Filter timestamps within the duration
    filtered_state_history = {
        ts: state_history[ts] for ts in timestamps if ts <= end_ts
    }

    if not filtered_state_history:
        print(f"Warning: No data found within duration {duration_seconds}s")
        return {start_ts: state_history[start_ts]}

    return filtered_state_history


def create_state_interpolator(state_history: dict[float, np.ndarray]):
    """Create a tudatpy interpolator for state history.

    Parameters
    ----------
    state_history : dict[float, np.ndarray]
        State history dictionary mapping timestamps to state vectors.

    Returns
    -------
    interpolator or None
        Interpolator object if tudatpy is available, None otherwise.
    """
    if not TUDATPY_AVAILABLE:
        return None

    try:
        # Create interpolator using Lagrange interpolation of order 2
        interpolator = interpolators.create_one_dimensional_vector_interpolator(
            state_history, interpolators.lagrange_interpolation(2)
        )
        return interpolator
    except Exception as e:
        print(f"Warning: Could not create interpolator: {e}")
        return None


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

    # Extract reference positions
    ref_timestamps = sorted(reference_state_history.keys())
    ref_pos = np.array([reference_state_history[ts][:3] for ts in ref_timestamps])

    # Plot 1: 3D Orbit
    ax1 = fig.add_subplot(2, 3, 1, projection="3d")
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

    for label, state_history in comparison_data:
        # Filter to only timestamps that exist in comparison data
        comp_timestamps = sorted(state_history.keys())
        valid_indices = [
            i for i, ts in enumerate(ref_timestamps) if ts in state_history
        ]
        if valid_indices:
            valid_ref_timestamps = [ref_timestamps[i] for i in valid_indices]
            pos = np.array([state_history[ts][:3] for ts in valid_ref_timestamps])
            ax1.plot(pos[:, 0], pos[:, 1], pos[:, 2], linewidth=2, label=label)

    ax1.set_xlabel("X (km)")
    ax1.set_ylabel("Y (km)")
    ax1.set_zlabel("Z (km)")
    ax1.set_title("3D Orbit Trajectory")
    ax1.legend()
    ax1.grid(True)

    # Plot 2: XY Plane
    ax2 = fig.add_subplot(2, 3, 2)
    ax2.plot(ref_pos[:, 0], ref_pos[:, 1], "b-", linewidth=2, label="Reference")
    ax2.scatter(ref_pos[0, 0], ref_pos[0, 1], c="b", s=100, marker="o", label="Start")
    ax2.scatter(ref_pos[-1, 0], ref_pos[-1, 1], c="b", s=100, marker="x", label="End")

    for label, state_history in comparison_data:
        valid_indices = [
            i for i, ts in enumerate(ref_timestamps) if ts in state_history
        ]
        if valid_indices:
            valid_ref_timestamps = [ref_timestamps[i] for i in valid_indices]
            pos = np.array([state_history[ts][:3] for ts in valid_ref_timestamps])
            ax2.plot(pos[:, 0], pos[:, 1], linewidth=2, label=label)

    ax2.set_xlabel("X (km)")
    ax2.set_ylabel("Y (km)")
    ax2.set_title("XY Plane")
    ax2.legend()
    ax2.grid(True)
    ax2.axis("equal")

    # Plot 3: XZ Plane
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.plot(ref_pos[:, 0], ref_pos[:, 2], "b-", linewidth=2, label="Reference")
    ax3.scatter(ref_pos[0, 0], ref_pos[0, 2], c="b", s=100, marker="o", label="Start")
    ax3.scatter(ref_pos[-1, 0], ref_pos[-1, 2], c="b", s=100, marker="x", label="End")

    for label, state_history in comparison_data:
        valid_indices = [
            i for i, ts in enumerate(ref_timestamps) if ts in state_history
        ]
        if valid_indices:
            valid_ref_timestamps = [ref_timestamps[i] for i in valid_indices]
            pos = np.array([state_history[ts][:3] for ts in valid_ref_timestamps])
            ax3.plot(pos[:, 0], pos[:, 2], linewidth=2, label=label)

    ax3.set_xlabel("X (km)")
    ax3.set_ylabel("Z (km)")
    ax3.set_title("XZ Plane")
    ax3.legend()
    ax3.grid(True)
    ax3.axis("equal")

    # Plot 4: YZ Plane
    ax4 = fig.add_subplot(2, 3, 4)
    ax4.plot(ref_pos[:, 1], ref_pos[:, 2], "b-", linewidth=2, label="Reference")
    ax4.scatter(ref_pos[0, 1], ref_pos[0, 2], c="b", s=100, marker="o", label="Start")
    ax4.scatter(ref_pos[-1, 1], ref_pos[-1, 2], c="b", s=100, marker="x", label="End")

    for label, state_history in comparison_data:
        valid_indices = [
            i for i, ts in enumerate(ref_timestamps) if ts in state_history
        ]
        if valid_indices:
            valid_ref_timestamps = [ref_timestamps[i] for i in valid_indices]
            pos = np.array([state_history[ts][:3] for ts in valid_ref_timestamps])
            ax4.plot(pos[:, 1], pos[:, 2], linewidth=2, label=label)

    ax4.set_xlabel("Y (km)")
    ax4.set_ylabel("Z (km)")
    ax4.set_title("YZ Plane")
    ax4.legend()
    ax4.grid(True)
    ax4.axis("equal")

    # Plot 5: RTN Radial-Transverse
    ax5 = fig.add_subplot(2, 3, 5)
    ref_states = np.array([reference_state_history[ts] for ts in ref_timestamps])
    ref_rsw = transform_to_rsw(ref_states)
    ax5.plot(ref_rsw[:, 1], ref_rsw[:, 0], "b-", linewidth=2, label="Reference")
    ax5.scatter(ref_rsw[0, 1], ref_rsw[0, 0], c="b", s=100, marker="o", label="Start")
    ax5.scatter(ref_rsw[-1, 1], ref_rsw[-1, 0], c="b", s=100, marker="x", label="End")

    for label, state_history in comparison_data:
        valid_indices = [
            i for i, ts in enumerate(ref_timestamps) if ts in state_history
        ]
        if valid_indices:
            valid_ref_timestamps = [ref_timestamps[i] for i in valid_indices]
            states = np.array([state_history[ts] for ts in valid_ref_timestamps])
            comp_rsw = transform_to_rsw(states)
            ax5.plot(comp_rsw[:, 1], comp_rsw[:, 0], linewidth=2, label=label)

    ax5.set_xlabel("Transverse (km)")
    ax5.set_ylabel("Radial (km)")
    ax5.set_title("RTN: Radial-Transverse Plane")
    ax5.legend()
    ax5.grid(True)
    ax5.axis("equal")

    # Plot 6: RTN Radial-Normal
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.plot(ref_rsw[:, 2], ref_rsw[:, 0], "b-", linewidth=2, label="Reference")
    ax6.scatter(ref_rsw[0, 2], ref_rsw[0, 0], c="b", s=100, marker="o", label="Start")
    ax6.scatter(ref_rsw[-1, 2], ref_rsw[-1, 0], c="b", s=100, marker="x", label="End")

    for label, state_history in comparison_data:
        valid_indices = [
            i for i, ts in enumerate(ref_timestamps) if ts in state_history
        ]
        if valid_indices:
            valid_ref_timestamps = [ref_timestamps[i] for i in valid_indices]
            states = np.array([state_history[ts] for ts in valid_ref_timestamps])
            comp_rsw = transform_to_rsw(states)
            ax6.plot(comp_rsw[:, 2], comp_rsw[:, 0], linewidth=2, label=label)

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

    # Plot 1: Position X Delta vs Time
    ax1 = fig.add_subplot(3, 2, 1)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        delta_x_comp_times = []
        deltas_x = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_x = comp_state[0] - ref_state[0]
                delta_x_comp_times.append(ts)
                deltas_x.append(delta_x)

        if deltas_x:
            ax1.plot(delta_x_comp_times, deltas_x, linewidth=2, label=label, alpha=0.7)

    ax1.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax1.set_ylabel("X Position Delta (km)")
    ax1.set_title("X Position Delta vs Time")
    ax1.legend()
    ax1.grid(True)

    # Plot 2: Position Y Delta vs Time
    ax2 = fig.add_subplot(3, 2, 2)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        delta_y_comp_times = []
        deltas_y = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_y = comp_state[1] - ref_state[1]
                delta_y_comp_times.append(ts)
                deltas_y.append(delta_y)

        if deltas_y:
            ax2.plot(delta_y_comp_times, deltas_y, linewidth=2, label=label, alpha=0.7)

    ax2.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax2.set_ylabel("Y Position Delta (km)")
    ax2.set_title("Y Position Delta vs Time")
    ax2.legend()
    ax2.grid(True)

    # Plot 3: Position Z Delta vs Time
    ax3 = fig.add_subplot(3, 2, 3)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        delta_z_comp_times = []
        deltas_z = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_z = comp_state[2] - ref_state[2]
                delta_z_comp_times.append(ts)
                deltas_z.append(delta_z)

        if deltas_z:
            ax3.plot(delta_z_comp_times, deltas_z, linewidth=2, label=label, alpha=0.7)

    ax3.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax3.set_ylabel("Z Position Delta (km)")
    ax3.set_title("Z Position Delta vs Time")
    ax3.legend()
    ax3.grid(True)

    # Plot 4: Velocity X Delta vs Time
    ax4 = fig.add_subplot(3, 2, 4)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        delta_vx_comp_times = []
        deltas_vx = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_vx = comp_state[3] - ref_state[3]
                delta_vx_comp_times.append(ts)
                deltas_vx.append(delta_vx)

        if deltas_vx:
            ax4.plot(
                delta_vx_comp_times, deltas_vx, linewidth=2, label=label, alpha=0.7
            )

    ax4.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax4.set_ylabel("Vx Velocity Delta (km/s)")
    ax4.set_title("Vx Velocity Delta vs Time")
    ax4.legend()
    ax4.grid(True)

    # Plot 5: Velocity Y Delta vs Time
    ax5 = fig.add_subplot(3, 2, 5)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        delta_vy_comp_times = []
        deltas_vy = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_vy = comp_state[4] - ref_state[4]
                delta_vy_comp_times.append(ts)
                deltas_vy.append(delta_vy)

        if deltas_vy:
            ax5.plot(
                delta_vy_comp_times, deltas_vy, linewidth=2, label=label, alpha=0.7
            )

    ax5.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax5.set_xlabel("Time from Start (seconds)")
    ax5.set_ylabel("Vy Velocity Delta (km/s)")
    ax5.set_title("Vy Velocity Delta vs Time")
    ax5.legend()
    ax5.grid(True)

    # Plot 6: Velocity Z Delta vs Time
    ax6 = fig.add_subplot(3, 2, 6)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())

        delta_vz_comp_times = []
        deltas_vz = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                delta_vz = comp_state[5] - ref_state[5]
                delta_vz_comp_times.append(ts)
                deltas_vz.append(delta_vz)

        if deltas_vz:
            ax6.plot(
                delta_vz_comp_times, deltas_vz, linewidth=2, label=label, alpha=0.7
            )

    ax6.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
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

    # Plot 1: Radial Position Delta vs Time
    ax1 = fig.add_subplot(3, 2, 1)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_start_ts = comp_timestamps[0]
        comp_times = np.array([ts - comp_start_ts for ts in comp_timestamps])

        delta_r_comp_times = []
        deltas_r = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                # Transform to RTN
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_r = comp_rsw[0] - ref_rsw[0]
                delta_r_comp_times.append(ts)
                deltas_r.append(delta_r)

        if deltas_r:
            ax1.plot(delta_r_comp_times, deltas_r, linewidth=2, label=label, alpha=0.7)

    ax1.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax1.set_ylabel("Radial Delta (km)")
    ax1.set_title("Radial Position Delta vs Time")
    ax1.legend()
    ax1.grid(True)

    # Plot 2: Transverse Position Delta vs Time
    ax2 = fig.add_subplot(3, 2, 2)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_start_ts = comp_timestamps[0]
        comp_times = np.array([ts - comp_start_ts for ts in comp_timestamps])

        delta_s_comp_times = []
        deltas_s = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_s = comp_rsw[1] - ref_rsw[1]
                delta_s_comp_times.append(ts)
                deltas_s.append(delta_s)

        if deltas_s:
            ax2.plot(delta_s_comp_times, deltas_s, linewidth=2, label=label, alpha=0.7)

    ax2.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax2.set_ylabel("Transverse Delta (km)")
    ax2.set_title("Transverse Position Delta vs Time")
    ax2.legend()
    ax2.grid(True)

    # Plot 3: Normal Position Delta vs Time
    ax3 = fig.add_subplot(3, 2, 3)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_start_ts = comp_timestamps[0]
        comp_times = np.array([ts - comp_start_ts for ts in comp_timestamps])

        delta_w_comp_times = []
        deltas_w = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_w = comp_rsw[2] - ref_rsw[2]
                delta_w_comp_times.append(ts)
                deltas_w.append(delta_w)

        if deltas_w:
            ax3.plot(delta_w_comp_times, deltas_w, linewidth=2, label=label, alpha=0.7)

    ax3.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax3.set_ylabel("Normal Delta (km)")
    ax3.set_title("Normal Position Delta vs Time")
    ax3.legend()
    ax3.grid(True)

    # Plot 4: Radial Velocity Delta vs Time
    ax4 = fig.add_subplot(3, 2, 4)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_start_ts = comp_timestamps[0]
        comp_times = np.array([ts - comp_start_ts for ts in comp_timestamps])

        delta_vr_comp_times = []
        deltas_vr = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_vr = comp_rsw[3] - ref_rsw[3]
                delta_vr_comp_times.append(ts)
                deltas_vr.append(delta_vr)

        if deltas_vr:
            ax4.plot(
                delta_vr_comp_times, deltas_vr, linewidth=2, label=label, alpha=0.7
            )

    ax4.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Radial Velocity Delta vs Time")
    ax4.legend()
    ax4.grid(True)

    # Plot 5: Transverse Velocity Delta vs Time
    ax5 = fig.add_subplot(3, 2, 5)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_start_ts = comp_timestamps[0]
        comp_times = np.array([ts - comp_start_ts for ts in comp_timestamps])

        delta_vs_comp_times = []
        deltas_vs = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_vs = comp_rsw[4] - ref_rsw[4]
                delta_vs_comp_times.append(ts)
                deltas_vs.append(delta_vs)

        if deltas_vs:
            ax5.plot(
                delta_vs_comp_times, deltas_vs, linewidth=2, label=label, alpha=0.7
            )

    ax5.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
    ax5.set_xlabel("Time from Start (seconds)")
    ax5.set_ylabel("Transverse Velocity Delta (km/s)")
    ax5.set_title("Transverse Velocity Delta vs Time")
    ax5.legend()
    ax5.grid(True)

    # Plot 6: Normal Velocity Delta vs Time
    ax6 = fig.add_subplot(3, 2, 6)
    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_start_ts = comp_timestamps[0]
        comp_times = np.array([ts - comp_start_ts for ts in comp_timestamps])

        delta_vw_comp_times = []
        deltas_vw = []
        for ts in comp_timestamps:
            ref_state = get_interpolated_state(reference_interpolator, ts)
            if ref_state is not None:
                comp_state = state_history[ts]
                ref_rsw = transform_to_rsw(np.array([ref_state]))[0]
                comp_rsw = transform_to_rsw(np.array([comp_state]))[0]
                delta_vw = comp_rsw[5] - ref_rsw[5]
                delta_vw_comp_times.append(ts)
                deltas_vw.append(delta_vw)

        if deltas_vw:
            ax6.plot(
                delta_vw_comp_times, deltas_vw, linewidth=2, label=label, alpha=0.7
            )

    ax6.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5)
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
    reference_state_history: dict[float, np.ndarray],
    comparison_data: list[tuple[str, dict[float, np.ndarray]]],
    output_file: Optional[str] = None,
) -> None:
    """Plot relative RTN orbits (deltas) in RTN coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit.

    Parameters
    ----------
    reference_state_history : dict[float, np.ndarray]
        State history for reference orbit (timestamp -> state vector).
    comparison_data : list[tuple[str, dict[float, np.ndarray]]]
        List of (label, state_history) tuples for comparison orbits.
    output_file : str, optional
        Path to save the figure. If None, displays interactively.
    """
    fig = plt.figure(figsize=(14, 10))

    # Extract reference timestamps and transform to RTN
    ref_timestamps = sorted(reference_state_history.keys())
    ref_states = np.array([reference_state_history[ts] for ts in ref_timestamps])
    ref_rsw = transform_to_rsw(ref_states)

    # Plot 1: Relative position in RTN (R-S plane)
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)

    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_states = np.array([state_history[ts] for ts in comp_timestamps])
        comp_rsw = transform_to_rsw(comp_states)

        # Compute deltas
        deltas_rs = []
        for ts in ref_timestamps:
            ref_state_rsw = ref_rsw[ref_timestamps.index(ts)]
            # Find closest comparison timestamp
            closest_ts = min(comp_timestamps, key=lambda t: abs(t - ts))
            comp_state_rsw = comp_rsw[comp_timestamps.index(closest_ts)]

            delta_r = comp_state_rsw[0] - ref_state_rsw[0]
            delta_s = comp_state_rsw[1] - ref_state_rsw[1]
            deltas_rs.append([delta_s, delta_r])

        deltas_rs = np.array(deltas_rs)
        ax1.plot(
            deltas_rs[:, 0],
            deltas_rs[:, 1],
            "o-",
            linewidth=2,
            markersize=4,
            label=label,
            alpha=0.7,
        )

    ax1.set_xlabel("Transverse Delta (km)")
    ax1.set_ylabel("Radial Delta (km)")
    ax1.set_title("Relative Position Delta: Radial-Transverse")
    ax1.legend()
    ax1.grid(True)
    ax1.axis("equal")

    # Plot 2: Relative position in RTN (R-W plane)
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)

    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_states = np.array([state_history[ts] for ts in comp_timestamps])
        comp_rsw = transform_to_rsw(comp_states)

        # Compute deltas
        deltas_rw = []
        for ts in ref_timestamps:
            ref_state_rsw = ref_rsw[ref_timestamps.index(ts)]
            closest_ts = min(comp_timestamps, key=lambda t: abs(t - ts))
            comp_state_rsw = comp_rsw[comp_timestamps.index(closest_ts)]

            delta_r = comp_state_rsw[0] - ref_state_rsw[0]
            delta_w = comp_state_rsw[2] - ref_state_rsw[2]
            deltas_rw.append([delta_w, delta_r])

        deltas_rw = np.array(deltas_rw)
        ax2.plot(
            deltas_rw[:, 0],
            deltas_rw[:, 1],
            "o-",
            linewidth=2,
            markersize=4,
            label=label,
            alpha=0.7,
        )

    ax2.set_xlabel("Normal Delta (km)")
    ax2.set_ylabel("Radial Delta (km)")
    ax2.set_title("Relative Position Delta: Radial-Normal")
    ax2.legend()
    ax2.grid(True)
    ax2.axis("equal")

    # Plot 3: Relative velocity in RTN (vR-vS plane)
    ax3 = fig.add_subplot(2, 2, 3)
    ax3.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)

    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_states = np.array([state_history[ts] for ts in comp_timestamps])
        comp_rsw = transform_to_rsw(comp_states)

        # Compute velocity deltas
        deltas_vrs = []
        for ts in ref_timestamps:
            ref_state_rsw = ref_rsw[ref_timestamps.index(ts)]
            closest_ts = min(comp_timestamps, key=lambda t: abs(t - ts))
            comp_state_rsw = comp_rsw[comp_timestamps.index(closest_ts)]

            delta_vr = comp_state_rsw[3] - ref_state_rsw[3]
            delta_vs = comp_state_rsw[4] - ref_state_rsw[4]
            deltas_vrs.append([delta_vs, delta_vr])

        deltas_vrs = np.array(deltas_vrs)
        ax3.plot(
            deltas_vrs[:, 0],
            deltas_vrs[:, 1],
            "o-",
            linewidth=2,
            markersize=4,
            label=label,
            alpha=0.7,
        )

    ax3.set_xlabel("Transverse Velocity Delta (km/s)")
    ax3.set_ylabel("Radial Velocity Delta (km/s)")
    ax3.set_title("Relative Velocity Delta: Radial-Transverse")
    ax3.legend()
    ax3.grid(True)

    # Plot 4: Relative velocity in RTN (vR-vW plane)
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)

    for label, state_history in comparison_data:
        comp_timestamps = sorted(state_history.keys())
        comp_states = np.array([state_history[ts] for ts in comp_timestamps])
        comp_rsw = transform_to_rsw(comp_states)

        # Compute velocity deltas
        deltas_vrw = []
        for ts in ref_timestamps:
            ref_state_rsw = ref_rsw[ref_timestamps.index(ts)]
            closest_ts = min(comp_timestamps, key=lambda t: abs(t - ts))
            comp_state_rsw = comp_rsw[comp_timestamps.index(closest_ts)]

            delta_vr = comp_state_rsw[3] - ref_state_rsw[3]
            delta_vw = comp_state_rsw[5] - ref_state_rsw[5]
            deltas_vrw.append([delta_vw, delta_vr])

        deltas_vrw = np.array(deltas_vrw)
        ax4.plot(
            deltas_vrw[:, 0],
            deltas_vrw[:, 1],
            "o-",
            linewidth=2,
            markersize=4,
            label=label,
            alpha=0.7,
        )

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

    # Apply duration filter if specified
    if duration_seconds is not None:
        ref_state_history = filter_by_duration(ref_state_history, duration_seconds)
        print(f"  Filtered to {len(ref_state_history)} states within duration")

    # Read comparison orbits
    comparison_data = []
    for filepath in args.files[1:]:
        print(f"Reading comparison orbit from {filepath}...")
        state_history = read_orbit_file(filepath)
        print(f"  Loaded {len(state_history)} states")

        label = Path(filepath).name
        comparison_data.append((label, state_history))

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
    ref_interpolator = create_state_interpolator(ref_state_history)

    # Plot orbits - save all output files by default
    print("Plotting absolute orbits in multiple views...")
    plot_orbits(ref_state_history, comparison_data, args.output)

    print("Plotting relative orbits in RTN coordinates...")
    relative_rtn_output = get_output_filename(args.output, "relative_rtn")
    plot_relative_rtn_orbits(ref_state_history, comparison_data, relative_rtn_output)

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
