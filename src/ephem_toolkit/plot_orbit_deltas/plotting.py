"""Plotting functions for orbit delta visualization."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import ephem_toolkit.core.misc as misc

from .constants import METERS_TO_KILOMETERS
from .csv_utils import generate_csv_path, write_csv
from .data_structures import StateHistory, TimeUnit

# ===================================================================
# Helper functions
# ===================================================================


def convert_state_to_km(state_m: np.ndarray) -> np.ndarray:
    """Convert state vector from meters to kilometers.

    Parameters
    ----------
    state_m : np.ndarray
        State vector in meters and m/s: [x, y, z, vx, vy, vz].

    Returns
    -------
    np.ndarray
        State vector in kilometers and km/s: [x, y, z, vx, vy, vz].
    """
    return state_m * METERS_TO_KILOMETERS


# ===================================================================
# Plotting functions
# ===================================================================


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

    # Extract reference positions and states (convert from m to km)
    ref_pos: np.ndarray = np.array(
        [
            convert_state_to_km(reference_state_history.state_history[ts])[:3]
            for ts in reference_state_history.timestamps
        ]
    )

    # Save plot data to CSV (one file per dataset) if output_file is provided
    csv_path = generate_csv_path(output_file, "absolute_orbits", "reference")
    if csv_path is not None:
        rows: list[list[object]] = [
            [
                ts,
                *convert_state_to_km(
                    reference_state_history.state_history[ts]
                ).tolist(),
            ]
            for ts in reference_state_history.timestamps
        ]
        write_csv(
            csv_path,
            ["epoch_s", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"],
            rows,
        )
        print(f"CSV saved to {csv_path}")

    # Create all axes
    ax_3d = fig.add_subplot(2, 2, 1, projection="3d")
    ax_xy_plane = fig.add_subplot(2, 2, 2)
    ax_xz_plane = fig.add_subplot(2, 2, 3)
    ax_yz_plane = fig.add_subplot(2, 2, 4)

    # Plot reference data on all axes
    ref_label: str = reference_state_history.label
    ax_3d.plot(
        ref_pos[:, 0],
        ref_pos[:, 1],
        ref_pos[:, 2],
        "b-",
        linewidth=2,
        label=ref_label,
    )
    ax_3d.scatter(
        ref_pos[0, 0],
        ref_pos[0, 1],
        ref_pos[0, 2],
        c="b",
        s=100,
        marker="o",
        label="Start",
    )
    ax_3d.scatter(
        ref_pos[-1, 0],
        ref_pos[-1, 1],
        ref_pos[-1, 2],
        c="b",
        s=100,
        marker="x",
        label="End",
    )

    ax_xy_plane.plot(ref_pos[:, 0], ref_pos[:, 1], "b-", linewidth=2, label=ref_label)
    ax_xy_plane.scatter(
        ref_pos[0, 0], ref_pos[0, 1], c="b", s=100, marker="o", label="Start"
    )
    ax_xy_plane.scatter(
        ref_pos[-1, 0], ref_pos[-1, 1], c="b", s=100, marker="x", label="End"
    )

    ax_xz_plane.plot(ref_pos[:, 0], ref_pos[:, 2], "b-", linewidth=2, label=ref_label)
    ax_xz_plane.scatter(
        ref_pos[0, 0], ref_pos[0, 2], c="b", s=100, marker="o", label="Start"
    )
    ax_xz_plane.scatter(
        ref_pos[-1, 0], ref_pos[-1, 2], c="b", s=100, marker="x", label="End"
    )

    ax_yz_plane.plot(ref_pos[:, 1], ref_pos[:, 2], "b-", linewidth=2, label=ref_label)
    ax_yz_plane.scatter(
        ref_pos[0, 1], ref_pos[0, 2], c="b", s=100, marker="o", label="Start"
    )
    ax_yz_plane.scatter(
        ref_pos[-1, 1], ref_pos[-1, 2], c="b", s=100, marker="x", label="End"
    )

    # Plot comparison data in a single loop
    for orbit in comparison_data:
        if not orbit.timestamps:
            print(f"Skipping comparison orbit with no valid timestamps: {orbit.label}")
            continue

        # Save plot data to CSV (one file per dataset) if output_file is provided
        csv_path = generate_csv_path(output_file, "absolute_orbits", orbit.label)
        if csv_path is not None:
            rows: list[list[object]] = [
                [ts, *convert_state_to_km(orbit.state_history[ts]).tolist()]
                for ts in orbit.timestamps
            ]
            write_csv(
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

        # Extract positions for Cartesian plots (convert from m to km)
        pos_data: np.ndarray = np.array(
            [
                convert_state_to_km(orbit.state_history[ts])[:3]
                for ts in orbit.timestamps
            ]
        )

        # Plot on all axes
        ax_3d.plot(
            pos_data[:, 0],
            pos_data[:, 1],
            pos_data[:, 2],
            linewidth=2,
            label=orbit.label,
        )
        ax_xy_plane.plot(pos_data[:, 0], pos_data[:, 1], linewidth=2, label=orbit.label)
        ax_xz_plane.plot(pos_data[:, 0], pos_data[:, 2], linewidth=2, label=orbit.label)
        ax_yz_plane.plot(pos_data[:, 1], pos_data[:, 2], linewidth=2, label=orbit.label)

    # Configure all axes
    ax_3d.set_xlabel("X (km)")
    ax_3d.set_ylabel("Y (km)")
    ax_3d.set_zlabel("Z (km)")
    ax_3d.set_title("3D Orbit Trajectory")
    ax_3d.legend(loc="upper right")
    ax_3d.grid(True)

    ax_xy_plane.set_xlabel("X (km)")
    ax_xy_plane.set_ylabel("Y (km)")
    ax_xy_plane.set_title("XY Plane")
    ax_xy_plane.legend(loc="upper right")
    ax_xy_plane.grid(True)
    ax_xy_plane.axis("equal")

    ax_xz_plane.set_xlabel("X (km)")
    ax_xz_plane.set_ylabel("Z (km)")
    ax_xz_plane.set_title("XZ Plane")
    ax_xz_plane.legend(loc="upper right")
    ax_xz_plane.grid(True)
    ax_xz_plane.axis("equal")

    ax_yz_plane.set_xlabel("Y (km)")
    ax_yz_plane.set_ylabel("Z (km)")
    ax_yz_plane.set_title("YZ Plane")
    ax_yz_plane.legend(loc="upper right")
    ax_yz_plane.grid(True)
    ax_yz_plane.axis("equal")

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
    ax_x_pos_delta = fig.add_subplot(3, 2, 1)  # Top-left: X position
    ax_y_pos_delta = fig.add_subplot(3, 2, 3)  # Middle-left: Y position
    ax_z_pos_delta = fig.add_subplot(3, 2, 5)  # Bottom-left: Z position
    ax_vx_vel_delta = fig.add_subplot(3, 2, 2)  # Top-right: Vx velocity
    ax_vy_vel_delta = fig.add_subplot(3, 2, 4)  # Middle-right: Vy velocity
    ax_vz_vel_delta = fig.add_subplot(3, 2, 6)  # Bottom-right: Vz velocity

    ax_x_pos_delta.ticklabel_format(style="plain", axis="y")
    ax_y_pos_delta.ticklabel_format(style="plain", axis="y")
    ax_z_pos_delta.ticklabel_format(style="plain", axis="y")
    ax_vx_vel_delta.ticklabel_format(style="plain", axis="y")
    ax_vy_vel_delta.ticklabel_format(style="plain", axis="y")
    ax_vz_vel_delta.ticklabel_format(style="plain", axis="y")

    # Add reference lines
    ref_label: str = reference_state_history.label
    ax_x_pos_delta.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_y_pos_delta.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_z_pos_delta.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_vx_vel_delta.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_vy_vel_delta.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_vz_vel_delta.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )

    # Track max absolute deltas per component for annotation
    max_abs_deltas: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

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

                # Compute delta and convert from m to km
                delta_state = comp_state - ref_state
                delta_state_km = convert_state_to_km(delta_state)
                for i in range(6):
                    deltas[i].append(delta_state_km[i])

        # Update max absolute deltas
        for i in range(6):
            if deltas[i]:
                component_max = max(abs(v) for v in deltas[i])
                max_abs_deltas[i] = max(max_abs_deltas[i], component_max)

        # Plot on all axes if data exists
        if delta_times:
            # Convert times from seconds to desired unit, relative to reference start time
            reference_start_time = reference_state_history.get_start_time()
            delta_times_array = np.array(delta_times) - reference_start_time
            delta_times_converted = delta_times_array / time_unit.get_divisor()

            # Save plot data to CSV (one file per dataset) if output_file is provided
            csv_path = generate_csv_path(
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
                write_csv(
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

            ax_x_pos_delta.plot(
                delta_times_converted,
                deltas[0],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_y_pos_delta.plot(
                delta_times_converted,
                deltas[1],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_z_pos_delta.plot(
                delta_times_converted,
                deltas[2],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_vx_vel_delta.plot(
                delta_times_converted,
                deltas[3],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_vy_vel_delta.plot(
                delta_times_converted,
                deltas[4],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_vz_vel_delta.plot(
                delta_times_converted,
                deltas[5],
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )

    # Configure all axes
    ax_x_pos_delta.set_ylabel("X Position Delta (km)")
    ax_x_pos_delta.set_title("X Position Delta vs Time")
    ax_x_pos_delta.legend(loc="upper right")
    ax_x_pos_delta.grid(True)

    ax_y_pos_delta.set_ylabel("Y Position Delta (km)")
    ax_y_pos_delta.set_title("Y Position Delta vs Time")
    ax_y_pos_delta.legend(loc="upper right")
    ax_y_pos_delta.grid(True)

    ax_z_pos_delta.set_xlabel(time_unit.get_label())
    ax_z_pos_delta.set_ylabel("Z Position Delta (km)")
    ax_z_pos_delta.set_title("Z Position Delta vs Time")
    ax_z_pos_delta.legend(loc="upper right")
    ax_z_pos_delta.grid(True)

    ax_vx_vel_delta.set_ylabel("Vx Velocity Delta (km/s)")
    ax_vx_vel_delta.set_title("Vx Velocity Delta vs Time")
    ax_vx_vel_delta.legend(loc="upper right")
    ax_vx_vel_delta.grid(True)

    ax_vy_vel_delta.set_ylabel("Vy Velocity Delta (km/s)")
    ax_vy_vel_delta.set_title("Vy Velocity Delta vs Time")
    ax_vy_vel_delta.legend(loc="upper right")
    ax_vy_vel_delta.grid(True)

    ax_vz_vel_delta.set_xlabel(time_unit.get_label())
    ax_vz_vel_delta.set_ylabel("Vz Velocity Delta (km/s)")
    ax_vz_vel_delta.set_title("Vz Velocity Delta vs Time")
    ax_vz_vel_delta.legend(loc="upper right")
    ax_vz_vel_delta.grid(True)

    # Annotate max absolute deltas on each subplot
    all_axes = [
        ax_x_pos_delta,
        ax_y_pos_delta,
        ax_z_pos_delta,
        ax_vx_vel_delta,
        ax_vy_vel_delta,
        ax_vz_vel_delta,
    ]
    units = ["km", "km", "km", "km/s", "km/s", "km/s"]
    for ax, max_val, unit in zip(all_axes, max_abs_deltas, units):
        ax.text(
            0.98,
            0.05,
            f"max: {max_val:.4g} {unit}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="red",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7),
        )

    # Unify y-axis scale across position delta subplots
    pos_axes = [ax_x_pos_delta, ax_y_pos_delta, ax_z_pos_delta]
    max_pos_range: float = max(ax.get_ylim()[1] - ax.get_ylim()[0] for ax in pos_axes)
    max_pos_range = max(max_pos_range, 2.0)  # Minimum range of 2 km
    for ax in pos_axes:
        ylim = ax.get_ylim()
        center = (ylim[0] + ylim[1]) / 2
        ax.set_ylim(center - max_pos_range / 2, center + max_pos_range / 2)

    # Unify y-axis scale across velocity delta subplots
    vel_axes = [ax_vx_vel_delta, ax_vy_vel_delta, ax_vz_vel_delta]
    max_vel_range: float = max(ax.get_ylim()[1] - ax.get_ylim()[0] for ax in vel_axes)
    for ax in vel_axes:
        ylim = ax.get_ylim()
        center = (ylim[0] + ylim[1]) / 2
        ax.set_ylim(center - max_vel_range / 2, center + max_vel_range / 2)

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
    ref_label: str = reference_state_history.label
    ax1.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label)
    ax2.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label)
    ax3.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label)
    ax4.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label)
    ax5.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label)
    ax6.axhline(y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label)

    # Track max absolute deltas per component for annotation
    max_abs_deltas: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

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

                # Transform to RTN and convert from m to km
                delta_rtn = misc.transform_to_rtn(comp_state, ref_state)
                delta_rtn_km = convert_state_to_km(delta_rtn)
                for i in range(6):
                    deltas[i].append(delta_rtn_km[i])

        # Update max absolute deltas
        for i in range(6):
            if deltas[i]:
                component_max = max(abs(v) for v in deltas[i])
                max_abs_deltas[i] = max(max_abs_deltas[i], component_max)

        # Plot on all axes if data exists
        if delta_times:
            # Convert times from seconds to desired unit, relative to reference start time
            reference_start_time = reference_state_history.get_start_time()
            delta_times_array = np.array(delta_times) - reference_start_time
            delta_times_converted = delta_times_array / time_unit.get_divisor()

            # Save plot data to CSV (one file per dataset) if output_file is provided
            csv_path = generate_csv_path(
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
                write_csv(
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
    ax1.legend(loc="upper right")
    ax1.grid(True)

    ax2.set_ylabel("Transverse Delta (km)")
    ax2.set_title("Transverse Position Delta vs Time")
    ax2.legend(loc="upper right")
    ax2.grid(True)

    ax3.set_xlabel(time_unit.get_label())
    ax3.set_ylabel("Normal Delta (km)")
    ax3.set_title("Normal Position Delta vs Time")
    ax3.legend(loc="upper right")
    ax3.grid(True)

    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Radial Velocity Delta vs Time")
    ax4.legend(loc="upper right")
    ax4.grid(True)

    ax5.set_ylabel("Transverse Velocity Delta (km/s)")
    ax5.set_title("Transverse Velocity Delta vs Time")
    ax5.legend(loc="upper right")
    ax5.grid(True)

    ax6.set_xlabel(time_unit.get_label())
    ax6.set_ylabel("Normal Velocity Delta (km/s)")
    ax6.set_title("Normal Velocity Delta vs Time")
    ax6.legend(loc="upper right")
    ax6.grid(True)

    # Annotate max absolute deltas on each subplot
    all_axes = [ax1, ax2, ax3, ax4, ax5, ax6]
    units = ["km", "km", "km", "km/s", "km/s", "km/s"]
    for ax, max_val, unit in zip(all_axes, max_abs_deltas, units):
        ax.text(
            0.98,
            0.05,
            f"max: {max_val:.4g} {unit}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="red",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7),
        )

    # Unify y-axis scale across position delta subplots (ax1, ax2, ax3)
    pos_axes = [ax1, ax2, ax3]
    max_pos_range: float = max(ax.get_ylim()[1] - ax.get_ylim()[0] for ax in pos_axes)
    max_pos_range = max(max_pos_range, 2.0)  # Minimum range of 2 km
    for ax in pos_axes:
        ylim = ax.get_ylim()
        center = (ylim[0] + ylim[1]) / 2
        ax.set_ylim(center - max_pos_range / 2, center + max_pos_range / 2)

    # Unify y-axis scale across velocity delta subplots (ax4, ax5, ax6)
    vel_axes = [ax4, ax5, ax6]
    max_vel_range: float = max(ax.get_ylim()[1] - ax.get_ylim()[0] for ax in vel_axes)
    for ax in vel_axes:
        ylim = ax.get_ylim()
        center = (ylim[0] + ylim[1]) / 2
        ax.set_ylim(center - max_vel_range / 2, center + max_vel_range / 2)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")


def plot_angular_separation(
    reference_state_history: StateHistory,
    comparison_data: list[StateHistory],
    output_file: str | None = None,
    time_unit: TimeUnit = TimeUnit.HOURS,
) -> None:
    """Plot angular separation, longitude separation, and latitude separation in one window.

    Computes and plots three angular metrics between comparison orbits and the reference
    orbit as viewed from Earth's center:
      - Total angular separation (3D angle between position vectors)
      - Longitude separation (difference in azimuthal angle in the equatorial plane)
      - Latitude separation (difference in elevation angle above/below equatorial plane)

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
    fig = plt.figure(figsize=(16, 14))

    # Create three subplots stacked vertically
    ax_angular_sep = fig.add_subplot(3, 1, 1)  # Total angular separation
    ax_longitude = fig.add_subplot(3, 1, 2)  # Longitude separation
    ax_latitude = fig.add_subplot(3, 1, 3)  # Latitude separation

    ax_angular_sep.ticklabel_format(style="plain", axis="y")
    ax_longitude.ticklabel_format(style="plain", axis="y")
    ax_latitude.ticklabel_format(style="plain", axis="y")

    # Add reference lines at zero
    ref_label: str = reference_state_history.label
    ax_angular_sep.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_longitude.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )
    ax_latitude.axhline(
        y=0, color="b", linestyle="--", linewidth=1, alpha=0.5, label=ref_label
    )

    # Track max values for annotation
    max_angular_sep: float = 0.0
    max_lon_sep: float = 0.0
    max_lat_sep: float = 0.0

    # Plot comparison data
    for orbit in comparison_data:
        # Compute all three angular metrics per timestamp
        delta_times = []
        angular_seps = []
        lon_seps = []
        lat_seps = []

        for ts in orbit.timestamps:
            ref_state = reference_state_history.get_interpolated_state(ts)
            if ref_state is not None:
                comp_state = orbit.state_history[ts]
                delta_times.append(ts)

                # Extract position vectors (first 3 components)
                ref_pos = ref_state[:3]
                comp_pos = comp_state[:3]

                ref_norm = np.linalg.norm(ref_pos)
                comp_norm = np.linalg.norm(comp_pos)

                # --- Total angular separation ---
                # angle = arccos(dot(v1, v2) / (|v1| * |v2|))
                if ref_norm > 0 and comp_norm > 0:
                    cos_angle = np.dot(ref_pos, comp_pos) / (ref_norm * comp_norm)
                    cos_angle = np.clip(cos_angle, -1.0, 1.0)
                    angular_seps.append(np.degrees(np.arccos(cos_angle)))
                else:
                    angular_seps.append(0.0)

                # --- Longitude separation ---
                # Longitude: atan2(y, x); normalize difference to [-π, π]
                ref_lon = np.arctan2(ref_pos[1], ref_pos[0])
                comp_lon = np.arctan2(comp_pos[1], comp_pos[0])
                lon_diff = comp_lon - ref_lon
                lon_diff = np.arctan2(np.sin(lon_diff), np.cos(lon_diff))
                lon_seps.append(np.degrees(lon_diff))

                # --- Latitude separation ---
                # Latitude: asin(z / r)
                ref_lat = (
                    np.arcsin(np.clip(ref_pos[2] / ref_norm, -1.0, 1.0))
                    if ref_norm > 0
                    else 0.0
                )
                comp_lat = (
                    np.arcsin(np.clip(comp_pos[2] / comp_norm, -1.0, 1.0))
                    if comp_norm > 0
                    else 0.0
                )
                lat_seps.append(np.degrees(comp_lat - ref_lat))

        # Update max values
        if angular_seps:
            max_angular_sep = max(max_angular_sep, max(angular_seps))
        if lon_seps:
            max_lon_sep = max(max_lon_sep, max(abs(v) for v in lon_seps))
        if lat_seps:
            max_lat_sep = max(max_lat_sep, max(abs(v) for v in lat_seps))

        # Plot if data exists
        if delta_times:
            # Convert times from seconds to desired unit, relative to reference start time
            reference_start_time = reference_state_history.get_start_time()
            delta_times_converted = (
                np.array(delta_times) - reference_start_time
            ) / time_unit.get_divisor()

            # Save plot data to CSV if output_file is provided
            csv_path = generate_csv_path(output_file, "angular_separation", orbit.label)
            if csv_path is not None:
                rows = [
                    [t_abs, t_rel, ang_sep, lon_sep, lat_sep]
                    for t_abs, t_rel, ang_sep, lon_sep, lat_sep in zip(
                        delta_times,
                        delta_times_converted,
                        angular_seps,
                        lon_seps,
                        lat_seps,
                    )
                ]
                write_csv(
                    csv_path,
                    [
                        "epoch_s",
                        f"t_from_start_{time_unit.value}",
                        "angular_separation_deg",
                        "longitude_separation_deg",
                        "latitude_separation_deg",
                    ],
                    rows,
                )
                print(f"CSV saved to {csv_path}")

            ax_angular_sep.plot(
                delta_times_converted,
                angular_seps,
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_longitude.plot(
                delta_times_converted,
                lon_seps,
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )
            ax_latitude.plot(
                delta_times_converted,
                lat_seps,
                linewidth=2,
                label=orbit.label,
                alpha=0.7,
            )

    # Configure total angular separation axis
    ax_angular_sep.set_ylabel("Angular Separation (degrees)")
    ax_angular_sep.set_title("Total Angular Separation from Reference Orbit vs Time")
    ax_angular_sep.legend(loc="upper right")
    ax_angular_sep.grid(True)

    # Configure longitude separation axis
    ax_longitude.set_ylabel("Longitude Separation (degrees)")
    ax_longitude.set_title("Longitude Separation from Reference Orbit vs Time")
    ax_longitude.legend(loc="upper right")
    ax_longitude.grid(True)

    # Configure latitude separation axis
    ax_latitude.set_xlabel(time_unit.get_label())
    ax_latitude.set_ylabel("Latitude Separation (degrees)")
    ax_latitude.set_title("Latitude Separation from Reference Orbit vs Time")
    ax_latitude.legend(loc="upper right")
    ax_latitude.grid(True)

    # Annotate max values on each subplot (bottom-right, consistent with other plots)
    all_axes = [ax_angular_sep, ax_longitude, ax_latitude]
    max_vals = [max_angular_sep, max_lon_sep, max_lat_sep]
    for ax, max_val in zip(all_axes, max_vals):
        ax.text(
            0.98,
            0.05,
            f"max: {max_val:.4g}°",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="red",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7),
        )

    # Unify y-axis scale across all three angular separation subplots
    max_range: float = max(ax.get_ylim()[1] - ax.get_ylim()[0] for ax in all_axes)
    for ax in all_axes:
        ylim = ax.get_ylim()
        center = (ylim[0] + ylim[1]) / 2
        ax.set_ylim(center - max_range / 2, center + max_range / 2)

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
    ref_label: str = reference_state_history.label
    ax1.scatter(0, 0, c="b", s=200, marker="*", label=ref_label, zorder=5)
    ax2.scatter(0, 0, c="b", s=200, marker="*", label=ref_label, zorder=5)
    ax3.scatter(0, 0, c="b", s=200, marker="*", label=ref_label, zorder=5)
    ax4.scatter(0, 0, c="b", s=200, marker="*", label=ref_label, zorder=5)

    # Track max distance from origin for each subplot
    max_dist: list[float] = [0.0, 0.0, 0.0, 0.0]  # rt_pos, rn_pos, rt_vel, rn_vel

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

                # Transform to RTN and convert from m to km
                delta_rtn = misc.transform_to_rtn(comp_state, ref_state)
                delta_rtn_km = convert_state_to_km(delta_rtn)
                deltas_rt.append([delta_rtn_km[1], delta_rtn_km[0]])
                deltas_rn.append([delta_rtn_km[2], delta_rtn_km[0]])
                deltas_vrt.append([delta_rtn_km[4], delta_rtn_km[3]])
                deltas_vrn.append([delta_rtn_km[5], delta_rtn_km[3]])

        # Convert to arrays and plot on all axes if data exists
        if deltas_rt:
            deltas_rt = np.array(deltas_rt)
            deltas_rn = np.array(deltas_rn)
            deltas_vrt = np.array(deltas_vrt)
            deltas_vrn = np.array(deltas_vrn)

            # Update max distances from origin
            rt_dists = np.sqrt(deltas_rt[:, 0] ** 2 + deltas_rt[:, 1] ** 2)
            rn_dists = np.sqrt(deltas_rn[:, 0] ** 2 + deltas_rn[:, 1] ** 2)
            vrt_dists = np.sqrt(deltas_vrt[:, 0] ** 2 + deltas_vrt[:, 1] ** 2)
            vrn_dists = np.sqrt(deltas_vrn[:, 0] ** 2 + deltas_vrn[:, 1] ** 2)
            max_dist[0] = max(max_dist[0], float(rt_dists.max()))
            max_dist[1] = max(max_dist[1], float(rn_dists.max()))
            max_dist[2] = max(max_dist[2], float(vrt_dists.max()))
            max_dist[3] = max(max_dist[3], float(vrn_dists.max()))

            # Save plot data to CSV (one file per dataset) if output_file is provided
            csv_path = generate_csv_path(
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
                write_csv(
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
    ax1.legend(loc="upper right")
    ax1.grid(True)
    ax1.axis("equal")

    ax2.set_xlabel("Normal Delta (km)")
    ax2.set_ylabel("Radial Delta (km)")
    ax2.set_title("Relative Position Delta: Radial-Normal")
    ax2.legend(loc="upper right")
    ax2.grid(True)
    ax2.axis("equal")

    ax3.set_xlabel("Transverse Velocity Delta (km/s)")
    ax3.set_ylabel("Radial Velocity Delta (km/s)")
    ax3.set_title("Relative Velocity Delta: Radial-Transverse")
    ax3.legend(loc="upper right")
    ax3.grid(True)
    ax3.axis("equal")

    ax4.set_xlabel("Normal Velocity Delta (km/s)")
    ax4.set_ylabel("Radial Velocity Delta (km/s)")
    ax4.set_title("Relative Velocity Delta: Radial-Normal")
    ax4.legend(loc="upper right")
    ax4.grid(True)
    ax4.axis("equal")

    # Annotate max distance from origin on each subplot
    all_axes = [ax1, ax2, ax3, ax4]
    units = ["km", "km", "km/s", "km/s"]
    for ax, max_val, unit in zip(all_axes, max_dist, units):
        ax.text(
            0.98,
            0.05,
            f"max: {max_val:.4g} {unit}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="red",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.7),
        )

    # Unify axis scale across position delta subplots (ax1, ax2)
    pos_axes = [ax1, ax2]
    max_pos_range: float = max(
        max(ax.get_xlim()[1] - ax.get_xlim()[0], ax.get_ylim()[1] - ax.get_ylim()[0])
        for ax in pos_axes
    )
    max_pos_range = max(max_pos_range, 2.0)  # Minimum range of 2 km
    for ax in pos_axes:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        ax.set_xlim(x_center - max_pos_range / 2, x_center + max_pos_range / 2)
        ax.set_ylim(y_center - max_pos_range / 2, y_center + max_pos_range / 2)

    # Unify axis scale across velocity delta subplots (ax3, ax4)
    vel_axes = [ax3, ax4]
    max_vel_range: float = max(
        max(ax.get_xlim()[1] - ax.get_xlim()[0], ax.get_ylim()[1] - ax.get_ylim()[0])
        for ax in vel_axes
    )
    for ax in vel_axes:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        ax.set_xlim(x_center - max_vel_range / 2, x_center + max_vel_range / 2)
        ax.set_ylim(y_center - max_vel_range / 2, y_center + max_vel_range / 2)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Figure saved to {output_file}")
