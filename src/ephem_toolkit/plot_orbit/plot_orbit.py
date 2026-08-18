#!/usr/bin/env python3
"""Plot a single OEM orbit and derived time-series diagnostics.

Usage:
    plot-orbit <input_oem> [-o output.png] [-d 6h] [--time-unit hours]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import ephem_toolkit.core.misc as misc
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.time_utils as time_utils
import ephem_toolkit.core.wgs as wgs

from .plot_orbit_cli import PlotOrbitArgs, parse_arguments

# ===================================================================
# Constants
# ===================================================================

KILOMETERS_PER_METER: float = 0.001
"""Length conversion factor from meters (m) to kilometers (km)."""


# ===================================================================
# Data structures
# ===================================================================


@dataclass
class OrbitSeries:
    """Derived single-orbit series used by plotting routines."""

    elapsed_time: np.ndarray
    """Elapsed time from first epoch in selected display unit."""

    position_km: np.ndarray
    """Cartesian position history with shape (N, 3) in kilometers (km)."""

    velocity_km_s: np.ndarray
    """Cartesian velocity history with shape (N, 3) in kilometers per second (km/s)."""

    velocity_magnitude_km_s: np.ndarray
    """Speed magnitude history with shape (N,) in kilometers per second (km/s)."""

    geocentric_distance_km: np.ndarray
    """Geocentric distance history with shape (N,) in kilometers (km)."""

    altitude_km: np.ndarray
    """Altitude above WGS84 ellipsoid with shape (N,) in kilometers (km)."""

    rtn_elapsed_time: np.ndarray
    """Elapsed time for RTN delta samples with shape (N-1,) in selected display unit."""

    rtn_delta_km: np.ndarray
    """RTN delta state history with shape (N-1, 6) in km and km/s."""

    direction_change_angle_deg: np.ndarray
    """Magnitude of the sample-to-sample direction change in degrees."""

    direction_change_rate_deg_s: np.ndarray
    """Sample-to-sample direction change rate in degrees per second."""

    angular_velocity_deg_s: np.ndarray
    """Angular velocity magnitude in degrees per second."""

    angular_velocity_rad_s: np.ndarray
    """Angular velocity magnitude in radians per second."""

    euler_angles_deg: np.ndarray
    """Euler-angle style direction series with shape (N, 3): [roll, pitch, yaw] in degrees."""

    euler_angle_rates_deg_s: np.ndarray
    """Time derivative of the Euler-angle series with shape (N, 3) in degrees per second."""


# ===================================================================
# Time unit enum
# ===================================================================


class TimeUnit(Enum):
    """Enumeration for time units used on time-series x-axes."""

    MINUTES = "minutes"
    """Time unit in minutes; divisor 60 s/min."""

    HOURS = "hours"
    """Time unit in hours; divisor 3600 s/h."""

    @classmethod
    def from_string(cls, value: str) -> TimeUnit:
        """Convert a string token to a TimeUnit.

        Parameters
        ----------
        value : str
            Time unit token: m/minute/minutes or h/hour/hours.

        Returns
        -------
        TimeUnit
            Parsed time unit enum.

        Raises
        ------
        ValueError
            If the input token is not recognized.
        """
        value_lower: str = value.lower()
        if value_lower in ["m", "minute", "minutes"]:
            return cls.MINUTES
        if value_lower in ["h", "hour", "hours"]:
            return cls.HOURS
        raise ValueError(
            f"Invalid time unit: {value}. "
            "Must be one of: m, minute, minutes, h, hour, hours"
        )

    def get_divisor_s(self) -> float:
        """Return divisor to convert seconds to this time unit.

        Returns
        -------
        float
            Divisor value in seconds.
        """
        if self == TimeUnit.MINUTES:
            return 60.0
        if self == TimeUnit.HOURS:
            return 3600.0
        raise ValueError(f"Unknown time unit: {self}")

    def get_axis_label(self) -> str:
        """Return x-axis label text for this time unit.

        Returns
        -------
        str
            Axis label for elapsed time.
        """
        if self == TimeUnit.MINUTES:
            return "Time from Start (minutes)"
        if self == TimeUnit.HOURS:
            return "Time from Start (hours)"
        raise ValueError(f"Unknown time unit: {self}")


# ===================================================================
# File I/O and preprocessing
# ===================================================================


def read_oem_states(
    source: str | Path,
) -> tuple[oem.CcsdsOem, list[float], list[np.ndarray]]:
    """Read a CCSDS OEM and return time-ordered states.

    Parameters
    ----------
    source : str | Path
        Path to input OEM file.

    Returns
    -------
    tuple[oem.CcsdsOem, list[float], list[np.ndarray]]
        Parsed OEM object, timestamps in POSIX seconds, and 6D states in SI units
        [x, y, z, vx, vy, vz] with meters (m) and m/s.

    Raises
    ------
    FileNotFoundError
        If the input file path does not exist.
    ValueError
        If the OEM contains no state samples.
    """
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")

    oem_data: oem.CcsdsOem = oem.CcsdsOem.read(source_path)
    if not oem_data.states:
        raise ValueError(f"No state data found in OEM file: {source_path}")

    timestamps_s: list[float] = [timestamp_s for timestamp_s, _ in oem_data.states]
    states_m: list[np.ndarray] = [state_m for _, state_m in oem_data.states]
    return oem_data, timestamps_s, states_m


def filter_states_by_duration(
    timestamps_s: list[float],
    states_m: list[np.ndarray],
    duration_s: float | None,
) -> tuple[list[float], list[np.ndarray]]:
    """Filter state history to [start, start + duration].

    Parameters
    ----------
    timestamps_s : list[float]
        State timestamps in POSIX seconds.
    states_m : list[np.ndarray]
        State vectors in SI units [x, y, z, vx, vy, vz].
    duration_s : float | None
        Duration from first timestamp in seconds, or None for full span.

    Returns
    -------
    tuple[list[float], list[np.ndarray]]
        Filtered timestamps and states.

    Raises
    ------
    ValueError
        If duration filtering removes all samples.
    """
    if duration_s is None:
        return timestamps_s, states_m

    start_time_s: float = timestamps_s[0]
    stop_time_s: float = start_time_s + duration_s

    filtered_timestamps_s: list[float] = []
    filtered_states_m: list[np.ndarray] = []

    for timestamp_s, state_m in zip(timestamps_s, states_m):
        if timestamp_s <= stop_time_s:
            filtered_timestamps_s.append(timestamp_s)
            filtered_states_m.append(state_m)

    if not filtered_timestamps_s:
        raise ValueError("No states remain after duration filtering.")

    return filtered_timestamps_s, filtered_states_m


def _compute_rtn_velocity_direction_vector(state_m: np.ndarray) -> np.ndarray:
    """Return the velocity direction expressed in the local RTN frame."""
    position_m: np.ndarray = state_m[0:3]
    velocity_m_s: np.ndarray = state_m[3:6]

    position_norm: float = np.linalg.norm(position_m)
    if position_norm <= 1e-30:
        return np.zeros(3, dtype=float)

    radial_unit_vector: np.ndarray = position_m / position_norm
    angular_momentum_vector: np.ndarray = np.cross(position_m, velocity_m_s)
    angular_momentum_norm: float = np.linalg.norm(angular_momentum_vector)

    if angular_momentum_norm <= 1e-30:
        normal_unit_vector: np.ndarray = np.array([0.0, 0.0, 1.0], dtype=float)
    else:
        normal_unit_vector = angular_momentum_vector / angular_momentum_norm

    transverse_unit_vector: np.ndarray = np.cross(
        normal_unit_vector, radial_unit_vector
    )
    velocity_rtn: np.ndarray = np.array(
        [
            np.dot(velocity_m_s, radial_unit_vector),
            np.dot(velocity_m_s, transverse_unit_vector),
            np.dot(velocity_m_s, normal_unit_vector),
        ],
        dtype=float,
    )

    velocity_norm: float = np.linalg.norm(velocity_rtn)
    if velocity_norm <= 1e-30:
        return np.zeros(3, dtype=float)

    return velocity_rtn / velocity_norm


def compute_orbit_series(
    timestamps_s: list[float],
    states_m: list[np.ndarray],
    time_unit: TimeUnit,
) -> OrbitSeries:
    """Compute all derived series needed by plotting routines.

    Parameters
    ----------
    timestamps_s : list[float]
        State timestamps in POSIX seconds.
    states_m : list[np.ndarray]
        State vectors in SI units [x, y, z, vx, vy, vz].
    time_unit : TimeUnit
        Display unit for elapsed time axis.

    Returns
    -------
    OrbitSeries
        Structured derived arrays for all requested plot products.
    """
    states_matrix_m: np.ndarray = np.array(states_m)
    position_m: np.ndarray = states_matrix_m[:, 0:3]
    velocity_m_s: np.ndarray = states_matrix_m[:, 3:6]

    start_time_s: float = timestamps_s[0]
    elapsed_time_s: np.ndarray = np.array(timestamps_s) - start_time_s
    elapsed_time: np.ndarray = elapsed_time_s / time_unit.get_divisor_s()

    position_km: np.ndarray = position_m * KILOMETERS_PER_METER
    velocity_km_s: np.ndarray = velocity_m_s * KILOMETERS_PER_METER

    velocity_magnitude_km_s: np.ndarray = (
        np.linalg.norm(velocity_m_s, axis=1) * KILOMETERS_PER_METER
    )
    geocentric_distance_km: np.ndarray = (
        np.linalg.norm(position_m, axis=1) * KILOMETERS_PER_METER
    )

    geodetic_coordinates: np.ndarray = wgs.ecef_to_lla(position_m)
    altitude_km: np.ndarray = geodetic_coordinates[:, 2] * KILOMETERS_PER_METER

    rtn_delta_list_km: list[np.ndarray] = []
    rtn_elapsed_time_list: list[float] = []
    for sample_index in range(1, len(states_m)):
        rtn_delta_m: np.ndarray = misc.transform_to_rtn(
            states_m[sample_index],
            states_m[sample_index - 1],
        )
        rtn_delta_list_km.append(rtn_delta_m * KILOMETERS_PER_METER)
        rtn_elapsed_time_list.append(float(elapsed_time[sample_index]))

    rtn_delta_km: np.ndarray
    if rtn_delta_list_km:
        rtn_delta_km = np.array(rtn_delta_list_km)
    else:
        rtn_delta_km = np.empty((0, 6))

    if len(states_m) >= 2:
        velocity_direction_vectors: np.ndarray = np.array(
            [_compute_rtn_velocity_direction_vector(state_m) for state_m in states_m],
            dtype=float,
        )
        direction_change_angle_deg: np.ndarray = np.zeros(len(states_m), dtype=float)
        direction_change_rate_deg_s: np.ndarray = np.zeros(len(states_m), dtype=float)
        angular_velocity_deg_s: np.ndarray = np.zeros(len(states_m), dtype=float)
        angular_velocity_rad_s: np.ndarray = np.zeros(len(states_m), dtype=float)

        for sample_index in range(1, len(states_m)):
            previous_direction = velocity_direction_vectors[sample_index - 1]
            current_direction = velocity_direction_vectors[sample_index]
            dot_product = np.dot(previous_direction, current_direction)
            dot_product = np.clip(dot_product, -1.0, 1.0)
            angle_rad = np.arccos(dot_product)
            angle_deg = np.degrees(angle_rad)
            direction_change_angle_deg[sample_index] = angle_deg
            delta_time_s = (
                elapsed_time_s[sample_index] - elapsed_time_s[sample_index - 1]
            )
            if delta_time_s > 0.0:
                direction_change_rate_deg_s[sample_index] = angle_deg / delta_time_s
                angular_velocity_deg_s[sample_index] = angle_deg / delta_time_s
                angular_velocity_rad_s[sample_index] = angle_rad / delta_time_s

        euler_angles_deg = np.zeros((len(states_m), 3), dtype=float)
        euler_angle_rates_deg_s = np.zeros_like(euler_angles_deg)

        for sample_index, direction_vector in enumerate(velocity_direction_vectors):
            radial_component = direction_vector[0]
            transverse_component = direction_vector[1]
            normal_component = direction_vector[2]
            roll_deg = 0.0
            pitch_deg = np.degrees(np.arctan2(radial_component, transverse_component))
            yaw_deg = np.degrees(
                np.arctan2(
                    normal_component, np.hypot(radial_component, transverse_component)
                )
            )
            euler_angles_deg[sample_index] = [roll_deg, pitch_deg, yaw_deg]

        for sample_index in range(1, len(states_m)):
            delta_time_s = (
                elapsed_time_s[sample_index] - elapsed_time_s[sample_index - 1]
            )
            if delta_time_s > 0.0:
                euler_angle_rates_deg_s[sample_index] = (
                    euler_angles_deg[sample_index] - euler_angles_deg[sample_index - 1]
                ) / delta_time_s
    else:
        direction_change_angle_deg = np.empty(0, dtype=float)
        direction_change_rate_deg_s = np.empty(0, dtype=float)
        angular_velocity_deg_s = np.empty(0, dtype=float)
        angular_velocity_rad_s = np.empty(0, dtype=float)
        euler_angles_deg = np.empty((0, 3), dtype=float)
        euler_angle_rates_deg_s = np.empty((0, 3), dtype=float)

    return OrbitSeries(
        elapsed_time=elapsed_time,
        position_km=position_km,
        velocity_km_s=velocity_km_s,
        velocity_magnitude_km_s=velocity_magnitude_km_s,
        geocentric_distance_km=geocentric_distance_km,
        altitude_km=altitude_km,
        rtn_elapsed_time=np.array(rtn_elapsed_time_list),
        rtn_delta_km=rtn_delta_km,
        direction_change_angle_deg=direction_change_angle_deg,
        direction_change_rate_deg_s=direction_change_rate_deg_s,
        angular_velocity_deg_s=angular_velocity_deg_s,
        angular_velocity_rad_s=angular_velocity_rad_s,
        euler_angles_deg=euler_angles_deg,
        euler_angle_rates_deg_s=euler_angle_rates_deg_s,
    )


def build_output_filename(base_output: str | None, suffix: str) -> str | None:
    """Generate output filename with suffix if output base path is provided.

    Parameters
    ----------
    base_output : str | None
        Base output filename path, or None.
    suffix : str
        Suffix to append to output stem.

    Returns
    -------
    str | None
        Generated output file path or None.
    """
    if base_output is None:
        return None
    output_path = Path(base_output)
    return str(output_path.parent / f"{output_path.stem}_{suffix}{output_path.suffix}")


def save_or_show_figure(figure: plt.Figure, output_file: str | None) -> None:
    """Save figure to file when requested, otherwise leave it for interactive show.

    Parameters
    ----------
    figure : plt.Figure
        Matplotlib figure object.
    output_file : str | None
        Output file path for save operation, or None.
    """
    figure.tight_layout()
    if output_file is None:
        return
    figure.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"Figure saved to {output_file}")
    plt.close(figure)


# ===================================================================
# Plotting
# ===================================================================


def plot_state_vectors(
    position_km: np.ndarray,
    orbit_label: str,
    output_file: str | None,
) -> None:
    """Plot absolute Cartesian state-vector trajectory in four views.

    Parameters
    ----------
    position_km : np.ndarray
        Position history with shape (N, 3) in kilometers (km).
    orbit_label : str
        Label used for legend entries.
    output_file : str | None
        Output image file path, or None.
    """
    figure = plt.figure(figsize=(16, 12))

    axis_3d = figure.add_subplot(2, 2, 1, projection="3d")
    axis_xy = figure.add_subplot(2, 2, 2)
    axis_xz = figure.add_subplot(2, 2, 3)
    axis_yz = figure.add_subplot(2, 2, 4)

    x_km = position_km[:, 0]
    y_km = position_km[:, 1]
    z_km = position_km[:, 2]

    axis_3d.plot(x_km, y_km, z_km, linewidth=2, label=orbit_label)
    axis_3d.scatter(x_km[0], y_km[0], z_km[0], c="g", s=80, marker="o", label="Start")
    axis_3d.scatter(x_km[-1], y_km[-1], z_km[-1], c="r", s=80, marker="x", label="End")
    axis_3d.set_xlabel("X (km)")
    axis_3d.set_ylabel("Y (km)")
    axis_3d.set_zlabel("Z (km)")
    axis_3d.set_title("3D Orbit Trajectory")
    axis_3d.grid(True)
    axis_3d.legend(loc="upper right")

    axis_xy.plot(x_km, y_km, linewidth=2, label=orbit_label)
    axis_xy.scatter(x_km[0], y_km[0], c="g", s=80, marker="o", label="Start")
    axis_xy.scatter(x_km[-1], y_km[-1], c="r", s=80, marker="x", label="End")
    axis_xy.set_xlabel("X (km)")
    axis_xy.set_ylabel("Y (km)")
    axis_xy.set_title("XY Plane")
    axis_xy.axis("equal")
    axis_xy.grid(True)
    axis_xy.legend(loc="upper right")

    axis_xz.plot(x_km, z_km, linewidth=2, label=orbit_label)
    axis_xz.scatter(x_km[0], z_km[0], c="g", s=80, marker="o", label="Start")
    axis_xz.scatter(x_km[-1], z_km[-1], c="r", s=80, marker="x", label="End")
    axis_xz.set_xlabel("X (km)")
    axis_xz.set_ylabel("Z (km)")
    axis_xz.set_title("XZ Plane")
    axis_xz.axis("equal")
    axis_xz.grid(True)
    axis_xz.legend(loc="upper right")

    axis_yz.plot(y_km, z_km, linewidth=2, label=orbit_label)
    axis_yz.scatter(y_km[0], z_km[0], c="g", s=80, marker="o", label="Start")
    axis_yz.scatter(y_km[-1], z_km[-1], c="r", s=80, marker="x", label="End")
    axis_yz.set_xlabel("Y (km)")
    axis_yz.set_ylabel("Z (km)")
    axis_yz.set_title("YZ Plane")
    axis_yz.axis("equal")
    axis_yz.grid(True)
    axis_yz.legend(loc="upper right")

    save_or_show_figure(figure, output_file)


def plot_rtn_delta_time_series(
    elapsed_time: np.ndarray,
    rtn_delta_km: np.ndarray,
    orbit_label: str,
    time_unit: TimeUnit,
    output_file: str | None,
) -> None:
    """Plot RTN position deltas versus previous state over time.

    Parameters
    ----------
    elapsed_time : np.ndarray
        Elapsed times for RTN deltas in selected display unit.
    rtn_delta_km : np.ndarray
        RTN delta state history with shape (N-1, 6) in km and km/s.
        Only position components [R, T, N] are plotted.
    orbit_label : str
        Label used for legend entries.
    time_unit : TimeUnit
        Time unit used on x-axis.
    output_file : str | None
        Output image file path, or None.
    """
    figure = plt.figure(figsize=(12, 9))

    axis_r = figure.add_subplot(3, 1, 1)
    axis_t = figure.add_subplot(3, 1, 2)
    axis_n = figure.add_subplot(3, 1, 3)

    for axis in [axis_r, axis_t, axis_n]:
        axis.grid(True)
        axis.ticklabel_format(style="plain", axis="y")

    if rtn_delta_km.size > 0:
        axis_r.plot(elapsed_time, rtn_delta_km[:, 0], linewidth=2, label=orbit_label)
        axis_t.plot(elapsed_time, rtn_delta_km[:, 1], linewidth=2, label=orbit_label)
        axis_n.plot(elapsed_time, rtn_delta_km[:, 2], linewidth=2, label=orbit_label)
    else:
        axis_r.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

    axis_r.set_ylabel("Radial Delta (km)")
    axis_r.set_title("Radial Position Delta vs Time")
    axis_r.legend(loc="upper right")

    axis_t.set_ylabel("Transverse Delta (km)")
    axis_t.set_title("Transverse Position Delta vs Time")
    axis_t.legend(loc="upper right")

    axis_n.set_xlabel(time_unit.get_axis_label())
    axis_n.set_ylabel("Normal Delta (km)")
    axis_n.set_title("Normal Position Delta vs Time")
    axis_n.legend(loc="upper right")

    save_or_show_figure(figure, output_file)


def plot_angular_velocity_time_series(
    elapsed_time: np.ndarray,
    angular_velocity_deg_s: np.ndarray,
    angular_velocity_rad_s: np.ndarray,
    orbit_label: str,
    time_unit: TimeUnit,
    output_file: str | None,
) -> None:
    """Plot angular velocity / attitude rate in deg/s and rad/s."""
    figure = plt.figure(figsize=(12, 8))

    axis_deg_s = figure.add_subplot(2, 1, 1)
    axis_rad_s = figure.add_subplot(2, 1, 2)

    for axis in [axis_deg_s, axis_rad_s]:
        axis.grid(True)
        axis.ticklabel_format(style="plain", axis="y")

    if angular_velocity_deg_s.size > 1:
        valid_mask = angular_velocity_deg_s != 0.0
        axis_deg_s.plot(
            elapsed_time[valid_mask],
            angular_velocity_deg_s[valid_mask],
            linewidth=2,
            label=f"{orbit_label} angular rate",
        )
    else:
        axis_deg_s.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

    axis_deg_s.set_xlabel(time_unit.get_axis_label())
    axis_deg_s.set_ylabel("Angular Velocity (deg/s)")
    axis_deg_s.set_title("Angular Velocity / Attitude Rate vs Time")
    axis_deg_s.legend(loc="upper right")

    if angular_velocity_rad_s.size > 1:
        valid_mask = angular_velocity_rad_s != 0.0
        axis_rad_s.plot(
            elapsed_time[valid_mask],
            angular_velocity_rad_s[valid_mask],
            linewidth=2,
            label=f"{orbit_label} angular rate",
        )
    else:
        axis_rad_s.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

    axis_rad_s.set_xlabel(time_unit.get_axis_label())
    axis_rad_s.set_ylabel("Angular Velocity (rad/s)")
    axis_rad_s.set_title("Angular Velocity / Attitude Rate (rad/s)")
    axis_rad_s.legend(loc="upper right")

    save_or_show_figure(figure, output_file)


def plot_direction_change_time_series(
    elapsed_time: np.ndarray,
    euler_angles_deg: np.ndarray,
    euler_angle_rates_deg_s: np.ndarray,
    orbit_label: str,
    time_unit: TimeUnit,
    output_file: str | None,
) -> None:
    """Plot Euler-angle direction series and their rates over time."""
    figure = plt.figure(figsize=(12, 8))

    axis_angle = figure.add_subplot(2, 1, 1)
    axis_rate = figure.add_subplot(2, 1, 2)

    for axis in [axis_angle, axis_rate]:
        axis.grid(True)
        axis.ticklabel_format(style="plain", axis="y")

    if euler_angles_deg.size > 0:
        axis_angle.plot(
            elapsed_time,
            euler_angles_deg[:, 0],
            linewidth=2,
            label=f"{orbit_label} roll",
        )
        axis_angle.plot(
            elapsed_time,
            euler_angles_deg[:, 1],
            linewidth=2,
            label=f"{orbit_label} pitch",
        )
        axis_angle.plot(
            elapsed_time,
            euler_angles_deg[:, 2],
            linewidth=2,
            label=f"{orbit_label} yaw",
        )
    else:
        axis_angle.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

    axis_angle.set_xlabel(time_unit.get_axis_label())
    axis_angle.set_ylabel("Euler Angle (deg)")
    axis_angle.set_title("Euler-Angle Direction Change vs Time")
    axis_angle.legend(loc="upper right")

    if euler_angle_rates_deg_s.size > 0:
        axis_rate.plot(
            elapsed_time,
            euler_angle_rates_deg_s[:, 0],
            linewidth=2,
            label=f"{orbit_label} roll rate",
        )
        axis_rate.plot(
            elapsed_time,
            euler_angle_rates_deg_s[:, 1],
            linewidth=2,
            label=f"{orbit_label} pitch rate",
        )
        axis_rate.plot(
            elapsed_time,
            euler_angle_rates_deg_s[:, 2],
            linewidth=2,
            label=f"{orbit_label} yaw rate",
        )
    else:
        axis_rate.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

    axis_rate.set_xlabel(time_unit.get_axis_label())
    axis_rate.set_ylabel("Euler Angle Rate (deg/s)")
    axis_rate.set_title("Euler-Angle Rate vs Time")
    axis_rate.legend(loc="upper right")

    save_or_show_figure(figure, output_file)


def plot_scalar_time_series(
    elapsed_time: np.ndarray,
    values: np.ndarray,
    orbit_label: str,
    title: str,
    y_label: str,
    time_unit: TimeUnit,
    output_file: str | None,
) -> None:
    """Plot a single scalar quantity over elapsed time.

    Parameters
    ----------
    elapsed_time : np.ndarray
        Elapsed times in selected display unit.
    values : np.ndarray
        Scalar series with shape (N,).
    orbit_label : str
        Label used for legend entries.
    title : str
        Figure title.
    y_label : str
        Y-axis label.
    time_unit : TimeUnit
        Time unit used on x-axis.
    output_file : str | None
        Output image file path, or None.
    """
    figure = plt.figure(figsize=(12, 5))
    axis = figure.add_subplot(1, 1, 1)

    axis.plot(elapsed_time, values, linewidth=2, label=orbit_label)
    axis.set_xlabel(time_unit.get_axis_label())
    axis.set_ylabel(y_label)
    axis.set_title(title)
    axis.grid(True)
    axis.ticklabel_format(style="plain", axis="y")
    axis.legend(loc="upper right")

    save_or_show_figure(figure, output_file)


def plot_geocentric_distance_with_delta(
    elapsed_time: np.ndarray,
    geocentric_distance_km: np.ndarray,
    orbit_label: str,
    time_unit: TimeUnit,
    output_file: str | None,
) -> None:
    """Plot geocentric distance and its sample-to-sample delta in one window.

    Parameters
    ----------
    elapsed_time : np.ndarray
        Elapsed times in selected display unit.
    geocentric_distance_km : np.ndarray
        Geocentric distance series with shape (N,) in kilometers (km).
    orbit_label : str
        Label used for legend entries.
    time_unit : TimeUnit
        Time unit used on x-axis.
    output_file : str | None
        Output image file path, or None.
    """
    figure = plt.figure(figsize=(12, 8))
    axis_distance = figure.add_subplot(2, 1, 1)
    axis_delta = figure.add_subplot(2, 1, 2)

    axis_distance.plot(
        elapsed_time,
        geocentric_distance_km,
        linewidth=2,
        label=orbit_label,
    )
    axis_distance.set_ylabel("Geocentric Distance (km)")
    axis_distance.set_title("Geocentric Distance vs Time")
    axis_distance.grid(True)
    axis_distance.ticklabel_format(style="plain", axis="y")
    axis_distance.legend(loc="upper right")

    if geocentric_distance_km.size > 1:
        geocentric_distance_delta_km: np.ndarray = np.diff(geocentric_distance_km)
        elapsed_time_delta: np.ndarray = elapsed_time[1:]
        axis_delta.plot(
            elapsed_time_delta,
            geocentric_distance_delta_km,
            linewidth=2,
            label=f"{orbit_label} delta",
        )
    else:
        axis_delta.text(0.5, 0.5, "Not enough samples", ha="center", va="center")

    axis_delta.set_xlabel(time_unit.get_axis_label())
    axis_delta.set_ylabel("Geocentric Distance Delta (km)")
    axis_delta.set_title("Geocentric Distance Delta vs Time")
    axis_delta.grid(True)
    axis_delta.ticklabel_format(style="plain", axis="y")
    axis_delta.legend(loc="upper right")

    save_or_show_figure(figure, output_file)


# ===================================================================
# Validation and CLI
# ===================================================================


def warn_if_altitude_frame_assumption_is_weak(oem_data: oem.CcsdsOem) -> None:
    """Print warning if metadata does not clearly indicate Earth-fixed frame.

    Parameters
    ----------
    oem_data : oem.CcsdsOem
        Parsed OEM object containing metadata.
    """
    reference_frame: str = (oem_data.meta.ref_frame or "").upper()
    center_name: str = (oem_data.meta.center_name or "").upper()

    ecef_frame_tokens: tuple[str, ...] = ("ITRF", "ITRS", "ECEF", "FIXED")
    is_ecef_like_frame: bool = any(
        token in reference_frame for token in ecef_frame_tokens
    )
    is_earth_centered: bool = "EARTH" in center_name

    if is_ecef_like_frame and is_earth_centered:
        return

    print(
        "Warning: altitude-from-WGS84 assumes Earth-fixed Cartesian coordinates. "
        f"OEM metadata is CENTER_NAME='{oem_data.meta.center_name}', "
        f"REF_FRAME='{oem_data.meta.ref_frame}'."
    )


def main() -> None:
    """Run CLI workflow to load one OEM and generate requested plots.

    Raises
    ------
    ValueError
        If parsed data is invalid for plotting.
    """
    cli_args: PlotOrbitArgs = parse_arguments()
    time_unit: TimeUnit = TimeUnit.from_string(cli_args.time_unit)

    duration_s: float | None = None
    if cli_args.duration is not None:
        try:
            duration_s = time_utils.parse_duration_to_seconds(cli_args.duration)
        except Exception as exception:
            print(
                f"Error: failed to parse duration '{cli_args.duration}': {exception}",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Reading OEM orbit from {cli_args.input_oem}...")
    oem_data, timestamps_s, states_m = read_oem_states(cli_args.input_oem)
    print(f"Loaded {len(states_m)} states")

    timestamps_s, states_m = filter_states_by_duration(
        timestamps_s,
        states_m,
        duration_s,
    )
    print(f"Using {len(states_m)} states after duration filtering")

    warn_if_altitude_frame_assumption_is_weak(oem_data)

    orbit_label: str = Path(cli_args.input_oem).name
    series: OrbitSeries = compute_orbit_series(timestamps_s, states_m, time_unit)

    print("Plotting state-vector trajectory views...")
    plot_state_vectors(
        series.position_km,
        orbit_label,
        build_output_filename(cli_args.output, "state_vectors"),
    )

    print("Plotting RTN deltas versus previous state...")
    plot_rtn_delta_time_series(
        series.rtn_elapsed_time,
        series.rtn_delta_km,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "rtn_deltas"),
    )

    print("Plotting velocity magnitude...")
    plot_scalar_time_series(
        series.elapsed_time,
        series.velocity_magnitude_km_s,
        orbit_label,
        "Velocity Magnitude vs Time",
        "Velocity Magnitude (km/s)",
        time_unit,
        build_output_filename(cli_args.output, "velocity_magnitude"),
    )

    print("Plotting angular velocity / attitude rate...")
    plot_angular_velocity_time_series(
        series.elapsed_time,
        series.angular_velocity_deg_s,
        series.angular_velocity_rad_s,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "angular_velocity"),
    )

    print("Plotting direction change metrics...")
    plot_direction_change_time_series(
        series.elapsed_time,
        series.euler_angles_deg,
        series.euler_angle_rates_deg_s,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "direction_change"),
    )

    print("Plotting geocentric distance...")
    plot_geocentric_distance_with_delta(
        series.elapsed_time,
        series.geocentric_distance_km,
        orbit_label,
        time_unit,
        build_output_filename(cli_args.output, "geocentric_distance"),
    )

    print("Plotting WGS84 altitude...")
    plot_scalar_time_series(
        series.elapsed_time,
        series.altitude_km,
        orbit_label,
        "Altitude above WGS84 Ellipsoid vs Time",
        "Altitude (km)",
        time_unit,
        build_output_filename(cli_args.output, "altitude_wgs84"),
    )

    if cli_args.output is None:
        plt.show()

    print("Done!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl-C)")
        sys.exit(0)
