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
import bisect
import csv
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Add parent directory to path to import common utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

import common.common as common
import common.oem as oem
import interpolator.lagrange as lagrange

INTERPOLATOR_NUMBER_OF_POINTS: int = 6
"""Polynomial degree for Lagrange interpolation of reference orbit states."""


def _sanitize_filename_component(value: str) -> str:
    """Sanitize a string for safe use as a filename component.

    Parameters
    ----------
    value : str
        String to sanitize.

    Returns
    -------
    str
        Sanitized string safe for use in filenames.
    """
    safe: list[str] = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")

    result: str = "".join(safe).strip("._")
    return result or "data"


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    """Write rows to CSV with a header.

    Parameters
    ----------
    path : Path
        Output CSV file path.
    header : list[str]
        Column header names.
    rows : list[list[object]]
        Data rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _default_csv_path(
    output_file: str | None,
    plot_suffix: str,
    dataset_label: str,
) -> Path | None:
    """Create a CSV output path derived from the plot output filename.

    Parameters
    ----------
    output_file : str | None
        Base output filename, or None to skip CSV generation.
    plot_suffix : str
        Suffix identifying the plot type.
    dataset_label : str
        Label identifying the dataset.

    Returns
    -------
    Path | None
        Generated CSV path, or None if output_file is None.
    """
    if output_file is None:
        return None

    out_path = Path(output_file)
    base_dir = out_path.parent
    base_stem = out_path.stem

    label_part = _sanitize_filename_component(dataset_label)
    suffix_part = _sanitize_filename_component(plot_suffix)

    return base_dir / f"{base_stem}_{suffix_part}_{label_part}.csv"


@dataclass
class StateHistory:
    """Orbit trajectory with state history and optional interpolator."""

    label: str
    """Label or identifier for the orbit (e.g., filename)."""

    state_history: dict[float, np.ndarray]
    """Mapping of POSIX epoch timestamps (seconds) to 6-element state vectors [x, y, z, vx, vy, vz] (km, km/s)."""

    interpolator: lagrange.LagrangeInterpolator | None = None
    """Lagrange interpolator for querying state at arbitrary timestamps; initialised lazily on first use."""

    timestamps: list[float] | None = None
    """Sorted list of epoch timestamps from state_history keys; populated automatically in __post_init__."""

    def __post_init__(self) -> None:
        """Initialize epochs field from state_history keys."""
        if not self.timestamps:
            self.timestamps = list(self.state_history.keys())

    def get_start_time(self) -> float:
        """Return the earliest timestamp in the stored state history.

        Returns
        -------
        float
            Earliest timestamp (seconds since epoch).
        """
        return self.timestamps[0]

    def get_stop_time(self) -> float:
        """Return the latest timestamp in the stored state history.

        Returns
        -------
        float
            Latest timestamp (seconds since epoch).
        """
        return self.timestamps[-1]

    def get_interpolated_state(self, timestamp: float) -> np.ndarray | None:
        """Get interpolated state at a given timestamp.

        Parameters
        ----------
        timestamp : float
            Timestamp to interpolate at (seconds since epoch).

        Returns
        -------
        np.ndarray | None
            Interpolated state vector [x, y, z, vx, vy, vz] if timestamp is within
            interpolator bounds, None otherwise.

        Raises
        ------
        ValueError
            If no interpolator has been set for this StateHistory object.
        """

        if self.interpolator is None:
            interp: lagrange.LagrangeInterpolator = lagrange.LagrangeInterpolator(
                dimension=6, degree=INTERPOLATOR_NUMBER_OF_POINTS
            )
            interp.set_data(self.state_history)
            self.interpolator = interp

        if (
            timestamp < self.interpolator.independent_values[2]
            or timestamp > self.interpolator.independent_values[-3]
        ):
            return None

        interpolated_state: np.ndarray | None = None
        interpolated_state = self.interpolator.interpolate(timestamp)

        return interpolated_state


class TimeUnit(Enum):
    """Enumeration for time units in plots."""

    MINUTES = "minutes"
    """Time unit in minutes; divisor 60 s/min."""

    HOURS = "hours"
    """Time unit in hours; divisor 3600 s/h."""

    @classmethod
    def from_string(cls, value: str) -> TimeUnit:
        """Convert string to TimeUnit enum.

        Parameters
        ----------
        value : str
            String representation: 'm', 'minute', 'minutes', 'h', 'hour', or 'hours'.

        Returns
        -------
        TimeUnit
            Corresponding TimeUnit enum value.

        Raises
        ------
        ValueError
            If the string doesn't match any known time unit.
        """
        value_lower: str = value.lower()
        if value_lower in ["m", "minute", "minutes"]:
            return cls.MINUTES
        elif value_lower in ["h", "hour", "hours"]:
            return cls.HOURS
        else:
            raise ValueError(
                f"Invalid time unit: {value}. Must be one of: m, minute, minutes, h, hour, hours"
            )

    def get_divisor(self) -> float:
        """Get the divisor to convert seconds to this time unit.

        Returns
        -------
        float
            Divisor value (60 for minutes, 3600 for hours).
        """
        if self == TimeUnit.MINUTES:
            return 60.0
        elif self == TimeUnit.HOURS:
            return 3600.0
        else:
            raise ValueError(f"Unknown time unit: {self}")

    def get_label(self) -> str:
        """Get the label for this time unit.

        Returns
        -------
        str
            Label string for use in plot axes.
        """
        if self == TimeUnit.MINUTES:
            return "Time from Start (minutes)"
        elif self == TimeUnit.HOURS:
            return "Time from Start (hours)"
        else:
            raise ValueError(f"Unknown time unit: {self}")


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
    filepath_obj: Path = Path(filepath)

    if not filepath_obj.exists():
        raise FileNotFoundError(f"File not found: {filepath_obj}")

    state_history: dict[float, np.ndarray] = {}

    # Try reading as OEM file first (more robust)
    try:
        header: dict
        meta: dict
        raw_states: dict
        header, meta, raw_states = oem.read_oem(filepath_obj)
        # raw_states is now dict[float, np.ndarray] (POSIX timestamps)
        state_history = raw_states
        return state_history
    except Exception:
        pass

    # Fall back to line-by-line parsing for raw state files
    with open(filepath_obj, "r", encoding="utf-8") as f:
        for line in f:
            try:
                result: tuple | None = oem.parse_oem_state_line(line)
                if result is not None:
                    epoch_dt, state_km = result
                    timestamp: float = epoch_dt.timestamp()
                    state_history[timestamp] = state_km
            except ValueError:
                # Skip lines that don't parse (headers, comments, etc.)
                continue

    if not state_history:
        raise ValueError(f"Could not parse any state data from {filepath_obj}")

    return state_history


def plot_orbits(
    reference_state_history: StateHistory,
    comparison_data: list[StateHistory],
    output_file: str | None = None,
) -> None:
    """Plot multiple orbits in various views.

    Parameters
    ----------
    reference_state_history : StateHistory
        StateHistory object for reference orbit.
    comparison_data : list[StateHistory]
        List of StateHistory objects for comparison orbits.
    output_file : str | None, optional
        Path to save the figure. If None, displays interactively.
    """
    # Create figure with subplots
    fig: plt.Figure = plt.figure(figsize=(16, 12))

    # Extract reference positions and states
    ref_pos: np.ndarray = np.array(
        [
            reference_state_history.state_history[ts][:3]
            for ts in reference_state_history.timestamps
        ]
    )

    # Save plot data to CSV (one file per dataset) if output_file is provided
    csv_path: Path | None = _default_csv_path(
        output_file, "absolute_orbits", "reference"
    )
    if csv_path is not None:
        rows: list[list[object]] = [
            [ts, *reference_state_history.state_history[ts].tolist()]
            for ts in reference_state_history.timestamps
        ]
        _write_csv(
            csv_path,
            ["epoch_s", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"],
            rows,
        )
        print(f"CSV saved to {csv_path}")

    # Create all axes
    ax1 = fig.add_subplot(2, 2, 1, projection="3d")
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 3)
    ax4 = fig.add_subplot(2, 2, 4)

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

    # Plot comparison data in a single loop
    for orbit in comparison_data:
        # Save plot data to CSV (one file per dataset) if output_file is provided
        csv_path: Path | None = _default_csv_path(
            output_file, "absolute_orbits", orbit.label
        )
        if csv_path is not None:
            rows: list[list[object]] = [
                [ts, *orbit.state_history[ts].tolist()] for ts in orbit.timestamps
            ]
            _write_csv(
                csv_path,
                [
                    "epoch_s",
                    "x_km",
                    "y_km",
                    "z_km",
                    "vx_km_s",
                    "vy_km_s",
                    "vz_km_s",
                ],
                rows,
            )
            print(f"CSV saved to {csv_path}")

        # Extract positions for Cartesian plots
        pos_data: np.ndarray = np.array(
            [orbit.state_history[ts][:3] for ts in orbit.timestamps]
        )

        # Plot on all axes
        ax1.plot(
            pos_data[:, 0],
            pos_data[:, 1],
            pos_data[:, 2],
            linewidth=2,
            label=orbit.label,
        )
        ax2.plot(pos_data[:, 0], pos_data[:, 1], linewidth=2, label=orbit.label)
        ax3.plot(pos_data[:, 0], pos_data[:, 2], linewidth=2, label=orbit.label)
        ax4.plot(pos_data[:, 1], pos_data[:, 2], linewidth=2, label=orbit.label)

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

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_relative_cartesian_timeseries(
    reference_state_history: StateHistory,
    comparison_data: list[StateHistory],
    output_file: str | None = None,
    time_unit: TimeUnit = TimeUnit.HOURS,
) -> None:
    """Plot time series of relative position and velocity in Cartesian coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit
    as a function of time in Cartesian coordinates.

    Parameters
    ----------
    reference_state_history : StateHistory
        StateHistory object for reference orbit.
    comparison_data : list[StateHistory]
        List of StateHistory objects for comparison orbits.
    output_file : str | None, optional
        Path to save the figure. If None, displays interactively.
    time_unit : TimeUnit, optional
        Time unit for x-axis (default: TimeUnit.HOURS).
    """
    fig = plt.figure(figsize=(16, 12))

    # Create all axes
    # Position plots on left, velocity plots on right
    ax1 = fig.add_subplot(3, 2, 1)  # Top-left: X position
    ax2 = fig.add_subplot(3, 2, 3)  # Middle-left: Y position
    ax3 = fig.add_subplot(3, 2, 5)  # Bottom-left: Z position
    ax4 = fig.add_subplot(3, 2, 2)  # Top-right: Vx velocity
    ax5 = fig.add_subplot(3, 2, 4)  # Middle-right: Vy velocity
    ax6 = fig.add_subplot(3, 2, 6)  # Bottom-right: Vz velocity

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
    for orbit in comparison_data:
        # Compute deltas for all 6 components
        delta_times = []
        deltas = [[], [], [], [], [], []]  # x, y, z, vx, vy, vz

        for ts in orbit.timestamps:
            ref_state = reference_state_history.get_interpolated_state(ts)
            if ref_state is not None:
                comp_state = orbit.state_history[ts]
                delta_times.append(ts)

                for i in range(6):
                    deltas[i].append(comp_state[i] - ref_state[i])

        # Plot on all axes if data exists
        if delta_times:
            # Convert times from seconds to desired unit, relative to reference start time
            reference_start_time = reference_state_history.get_start_time()
            delta_times_array = np.array(delta_times) - reference_start_time
            delta_times_converted = delta_times_array / time_unit.get_divisor()

            # Save plot data to CSV (one file per dataset) if output_file is provided
            csv_path = _default_csv_path(
                output_file, "relative_cartesian_timeseries", orbit.label
            )
            if csv_path is not None:
                rows = [
                    [
                        t_abs,
                        t_rel,
                        dx,
                        dy,
                        dz,
                        dvx,
                        dvy,
                        dvz,
                    ]
                    for t_abs, t_rel, dx, dy, dz, dvx, dvy, dvz in zip(
                        delta_times,
                        delta_times_converted,
                        deltas[0],
                        deltas[1],
                        deltas[2],
                        deltas[3],
                        deltas[4],
                        deltas[5],
                    )
                ]
                _write_csv(
                    csv_path,
                    [
                        "epoch_s",
                        f"t_from_start_{time_unit.value}",
                        "dx_km",
                        "dy_km",
                        "dz_km",
                        "dvx_km_s",
                        "dvy_km_s",
                        "dvz_km_s",
                    ],
                    rows,
                )
                print(f"CSV saved to {csv_path}")

            time_label = time_unit.get_label()

            ax1.plot(
                delta_times_converted,
                deltas[0],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax2.plot(
                delta_times_converted,
                deltas[1],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax3.plot(
                delta_times_converted,
                deltas[2],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax4.plot(
                delta_times_converted,
                deltas[3],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax5.plot(
                delta_times_converted,
                deltas[4],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax6.plot(
                delta_times_converted,
                deltas[5],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )

    # Configure all axes
    ax1.set_ylabel("X Position Delta (km)")
    ax1.set_title("X Position Delta vs Time")
    ax1.legend()
    ax1.grid(True)

    ax2.set_ylabel("Y Position Delta (km)")
    ax2.set_title("Y Position Delta vs Time")
    ax2.legend()
    ax2.grid(True)

    ax3.set_xlabel(time_unit.get_label())
    ax3.set_ylabel("Z Position Delta (km)")
    ax3.set_title("Z Position Delta vs Time")
    ax3.legend()
    ax3.grid(True)

    ax4.set_ylabel("Vx Velocity Delta (km/s)")
    ax4.set_title("Vx Velocity Delta vs Time")
    ax4.legend()
    ax4.grid(True)

    ax5.set_ylabel("Vy Velocity Delta (km/s)")
    ax5.set_title("Vy Velocity Delta vs Time")
    ax5.legend()
    ax5.grid(True)

    ax6.set_xlabel(time_unit.get_label())
    ax6.set_ylabel("Vz Velocity Delta (km/s)")
    ax6.set_title("Vz Velocity Delta vs Time")
    ax6.legend()
    ax6.grid(True)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_relative_rtn_timeseries(
    reference_state_history: StateHistory,
    comparison_data: list[StateHistory],
    output_file: str | None = None,
    time_unit: TimeUnit = TimeUnit.HOURS,
) -> None:
    """Plot time series of relative position and velocity in RTN coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit
    as a function of time in RTN coordinates.

    Parameters
    ----------
    reference_state_history : StateHistory
        StateHistory object for reference orbit.
    comparison_data : list[StateHistory]
        List of StateHistory objects for comparison orbits.
    output_file : str | None, optional
        Path to save the figure. If None, displays interactively.
    time_unit : TimeUnit, optional
        Time unit for x-axis (default: TimeUnit.HOURS).
    """
    fig = plt.figure(figsize=(16, 12))

    # Create all axes
    # Position plots on left, velocity plots on right
    ax1 = fig.add_subplot(3, 2, 1)  # Top-left: Radial position
    ax2 = fig.add_subplot(3, 2, 3)  # Middle-left: Transverse position
    ax3 = fig.add_subplot(3, 2, 5)  # Bottom-left: Normal position
    ax4 = fig.add_subplot(3, 2, 2)  # Top-right: Radial velocity
    ax5 = fig.add_subplot(3, 2, 4)  # Middle-right: Transverse velocity
    ax6 = fig.add_subplot(3, 2, 6)  # Bottom-right: Normal velocity

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
    for orbit in comparison_data:
        # Compute deltas for all 6 RTN components
        delta_times = []
        deltas = [[], [], [], [], [], []]  # r, t, n, vr, vt, vn

        for ts in orbit.timestamps:
            ref_state = reference_state_history.get_interpolated_state(ts)
            if ref_state is not None:
                comp_state = orbit.state_history[ts]
                delta_times.append(ts)

                # Transform to RTN
                delta_rtn = common.transform_to_rtn(comp_state, ref_state)
                for i in range(6):
                    deltas[i].append(delta_rtn[i])

        # Plot on all axes if data exists
        if delta_times:
            # Convert times from seconds to desired unit, relative to reference start time
            reference_start_time = reference_state_history.get_start_time()
            delta_times_array = np.array(delta_times) - reference_start_time
            delta_times_converted = delta_times_array / time_unit.get_divisor()

            # Save plot data to CSV (one file per dataset) if output_file is provided
            csv_path = _default_csv_path(
                output_file, "relative_rtn_timeseries", orbit.label
            )
            if csv_path is not None:
                rows = [
                    [
                        t_abs,
                        t_rel,
                        dr,
                        dt,
                        dn,
                        dvr,
                        dvt,
                        dvn,
                    ]
                    for t_abs, t_rel, dr, dt, dn, dvr, dvt, dvn in zip(
                        delta_times,
                        delta_times_converted,
                        deltas[0],
                        deltas[1],
                        deltas[2],
                        deltas[3],
                        deltas[4],
                        deltas[5],
                    )
                ]
                _write_csv(
                    csv_path,
                    [
                        "epoch_s",
                        f"t_from_start_{time_unit.value}",
                        "dr_km",
                        "dt_km",
                        "dn_km",
                        "dvr_km_s",
                        "dvt_km_s",
                        "dvn_km_s",
                    ],
                    rows,
                )
                print(f"CSV saved to {csv_path}")

            time_label = time_unit.get_label()

            ax1.plot(
                delta_times_converted,
                deltas[0],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax2.plot(
                delta_times_converted,
                deltas[1],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax3.plot(
                delta_times_converted,
                deltas[2],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax4.plot(
                delta_times_converted,
                deltas[3],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax5.plot(
                delta_times_converted,
                deltas[4],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax6.plot(
                delta_times_converted,
                deltas[5],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )

    # Configure all axes
    ax1.set_ylabel("Radial Delta (km)")
    ax1.set_title("Radial Position Delta vs Time")
    ax1.legend()
    ax1.grid(True)

    ax2.set_ylabel("Transverse Delta (km)")
    ax2.set_title("Transverse Position Delta vs Time")
    ax2.legend()
    ax2.grid(True)

    ax3.set_xlabel(time_unit.get_label())
    ax3.set_ylabel("Normal Delta (km)")
    ax3.set_title("Normal Position Delta vs Time")
    ax3.legend()
    ax3.grid(True)

    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Radial Velocity Delta vs Time")
    ax4.legend()
    ax4.grid(True)

    ax5.set_ylabel("Transverse Velocity Delta (km/s)")
    ax5.set_title("Transverse Velocity Delta vs Time")
    ax5.legend()
    ax5.grid(True)

    ax6.set_xlabel(time_unit.get_label())
    ax6.set_ylabel("Normal Velocity Delta (km/s)")
    ax6.set_title("Normal Velocity Delta vs Time")
    ax6.legend()
    ax6.grid(True)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_relative_rtn_orbits(
    reference_state_history: StateHistory,
    comparison_data: list[StateHistory],
    output_file: str | None = None,
) -> None:
    """Plot relative RTN orbits (deltas) in RTN coordinates.

    Computes and plots the differences between comparison orbits and the reference orbit.

    Parameters
    ----------
    reference_state_history : StateHistory
        StateHistory object for reference orbit.
    comparison_data : list[StateHistory]
        List of StateHistory objects for comparison orbits.
    output_file : str | None, optional
        Path to save the figure. If None, displays interactively.
    """
    fig = plt.figure(figsize=(14, 10))

    # Create all axes
    # Position plots on left, velocity plots on right
    ax1 = fig.add_subplot(2, 2, 1)  # Top-left: Radial-Transverse position
    ax2 = fig.add_subplot(2, 2, 3)  # Bottom-left: Radial-Normal position
    ax3 = fig.add_subplot(2, 2, 2)  # Top-right: Radial-Transverse velocity
    ax4 = fig.add_subplot(2, 2, 4)  # Bottom-right: Radial-Normal velocity

    ax1.ticklabel_format(style="plain", axis="both")
    ax2.ticklabel_format(style="plain", axis="both")
    ax3.ticklabel_format(style="plain", axis="both")
    ax4.ticklabel_format(style="plain", axis="both")

    # Add reference points
    ax1.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)
    ax2.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)
    ax3.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)
    ax4.scatter(0, 0, c="b", s=200, marker="*", label="Reference", zorder=5)

    # Plot comparison data in a single loop
    for orbit in comparison_data:
        # Compute all deltas for all 4 plots
        deltas_rt = []  # Radial-Transverse position
        deltas_rn = []  # Radial-Normal position
        deltas_vrt = []  # Radial-Transverse velocity
        deltas_vrn = []  # Radial-Normal velocity

        for ts in orbit.timestamps:
            ref_state = reference_state_history.get_interpolated_state(ts)
            if ref_state is not None:
                comp_state = orbit.state_history[ts]

                # Transform to RTN
                delta_rtn = common.transform_to_rtn(comp_state, ref_state)
                deltas_rt.append([delta_rtn[1], delta_rtn[0]])
                deltas_rn.append([delta_rtn[2], delta_rtn[0]])
                deltas_vrt.append([delta_rtn[4], delta_rtn[3]])
                deltas_vrn.append([delta_rtn[5], delta_rtn[3]])

        # Convert to arrays and plot on all axes if data exists
        if deltas_rt:
            deltas_rt = np.array(deltas_rt)
            deltas_rn = np.array(deltas_rn)
            deltas_vrt = np.array(deltas_vrt)
            deltas_vrn = np.array(deltas_vrn)

            # Save plot data to CSV (one file per dataset) if output_file is provided
            csv_path = _default_csv_path(
                output_file, "relative_rtn_orbits", orbit.label
            )
            if csv_path is not None:
                rows = [
                    [
                        ts,
                        rt[0],
                        rt[1],
                        rn[0],
                        rn[1],
                        vrt[0],
                        vrt[1],
                        vrn[0],
                        vrn[1],
                    ]
                    for ts, rt, rn, vrt, vrn in zip(
                        orbit.timestamps,
                        deltas_rt,
                        deltas_rn,
                        deltas_vrt,
                        deltas_vrn,
                    )
                ]
                _write_csv(
                    csv_path,
                    [
                        "epoch_s",
                        "dt_km",
                        "dr_km",
                        "dn_km",
                        "dn_km_rn",
                        "dvt_km_s",
                        "dvr_km_s",
                        "dvn_km_s",
                        "dvn_km_s_vrn",
                    ],
                    rows,
                )
                print(f"CSV saved to {csv_path}")

            ax1.plot(
                deltas_rt[:, 0],
                deltas_rt[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=orbit.label,
                alpha=0.7,
            )
            ax2.plot(
                deltas_rn[:, 0],
                deltas_rn[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=orbit.label,
                alpha=0.7,
            )
            ax3.plot(
                deltas_vrt[:, 0],
                deltas_vrt[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=orbit.label,
                alpha=0.7,
            )
            ax4.plot(
                deltas_vrn[:, 0],
                deltas_vrn[:, 1],
                "o-",
                linewidth=2,
                markersize=4,
                label=orbit.label,
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
    ax3.axis("equal")

    ax4.set_xlabel("Normal Velocity Delta (km/s)")
    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Relative Velocity Delta: Radial-Normal")
    ax4.legend()
    ax4.grid(True)
    ax4.axis("equal")

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def main() -> None:
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
    duration_seconds: float | None = None
    if args.duration:
        try:
            duration_seconds = common.parse_duration_to_seconds(args.duration)
            print(
                f"Analyzing data for duration: {args.duration} ({duration_seconds:.0f} seconds)"
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
    start_timestamp: float = ref_timestamps_sorted[0]

    if duration_seconds is not None:
        end_timestamp: float = start_timestamp + duration_seconds
    else:
        end_timestamp: float = ref_timestamps_sorted[-1]

    print(f"Reference orbit end timestamp: {end_timestamp}")

    # Filter reference and comparison data using end timestamp
    # Include up to interpolator_number_of_points/2 additional states past end_timestamp for reference orbit
    end_idx: int = bisect.bisect_left(ref_timestamps_sorted, end_timestamp)

    # Include states up to end_timestamp plus up to interpolator_number_of_points more states
    include_count: int = min(
        int(INTERPOLATOR_NUMBER_OF_POINTS / 2), len(ref_timestamps_sorted) - end_idx
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
            if ts <= end_timestamp
        }
        filtered_comparison_data.append(
            StateHistory(label=orbit.label, state_history=filtered_state_history)
        )
    comparison_data = filtered_comparison_data

    # Determine output files
    def get_output_filename(base_output: str | None, suffix: str) -> str | None:
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

    time_unit: TimeUnit = TimeUnit.from_string(args.time_unit)

    print(
        "Plotting time series of relative position and velocity in RTN coordinates..."
    )
    relative_rtn_timeseries_output: str | None = get_output_filename(
        args.output, "relative_rtn_timeseries"
    )
    plot_relative_rtn_timeseries(
        reference_state_history_obj,
        comparison_data,
        relative_rtn_timeseries_output,
        time_unit,
    )

    print("Plotting relative orbits in RTN coordinates...")
    relative_rtn_output: str | None = get_output_filename(args.output, "relative_rtn")
    plot_relative_rtn_orbits(
        reference_state_history_obj, comparison_data, relative_rtn_output
    )

    print(
        "Plotting time series of relative position and velocity in Cartesian coordinates..."
    )
    relative_cartesian_timeseries_output: str | None = get_output_filename(
        args.output, "relative_cartesian_timeseries"
    )

    plot_relative_cartesian_timeseries(
        reference_state_history_obj,
        comparison_data,
        relative_cartesian_timeseries_output,
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
