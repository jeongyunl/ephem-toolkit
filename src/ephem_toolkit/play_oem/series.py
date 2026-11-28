"""Derived orbit series used by OEM playback and data_views."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal

import numpy as np

import ephem_toolkit.core.misc as misc
import ephem_toolkit.core.wgs as wgs

from .time_unit import TimeUnit

KILOMETERS_PER_METER: float = 0.001
"""Length conversion factor from meters (m) to kilometers (km)."""

SeriesGroupName = Literal[
    "kinematics", "rtn", "direction-rates", "distance-delta"
]
SERIES_GROUPS: tuple[SeriesGroupName, ...] = (
    "kinematics",
    "rtn",
    "direction-rates",
    "distance-delta",
)
KINEMATICS_COLUMNS = ("t", "speed_m_s", "distance_m", "altitude_m")
DISTANCE_DELTA_COLUMNS = ("t", "delta_distance_m")
RTN_COLUMNS = (
    "t",
    "delta_r_m",
    "delta_t_m",
    "delta_n_m",
    "delta_vr_m_s",
    "delta_vt_m_s",
    "delta_vn_m_s",
)
DIRECTION_RATE_COLUMNS = (
    "t",
    "direction_change_rad",
    "angular_velocity_rad_s",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
    "roll_rate_rad_s",
    "pitch_rate_rad_s",
    "yaw_rate_rad_s",
)
_SERIES_COLUMNS: Mapping[SeriesGroupName, tuple[str, ...]] = MappingProxyType(
    {
        "kinematics": KINEMATICS_COLUMNS,
        "rtn": RTN_COLUMNS,
        "direction-rates": DIRECTION_RATE_COLUMNS,
        "distance-delta": DISTANCE_DELTA_COLUMNS,
    }
)


@dataclass
class OrbitSeries:
    """Derived single-orbit series used by playback and plotting routines."""

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

    segment_ids: np.ndarray
    """OEM segment identifier for each sample."""

    rtn_segment_ids: np.ndarray
    """Segment identifier for each adjacent-sample RTN delta; -1 marks a boundary."""


    @staticmethod
    def _compute_rtn_velocity_direction_vectors(states_m: np.ndarray) -> np.ndarray:
        """Return velocity directions in the local RTN frame for many states."""
        positions_m = states_m[:, :3]
        velocities_m_s = states_m[:, 3:6]
        position_norms = np.linalg.norm(positions_m, axis=1)
        valid_positions = position_norms > 1e-30
        radial_unit_vectors = np.zeros_like(positions_m)
        radial_unit_vectors[valid_positions] = (
            positions_m[valid_positions] / position_norms[valid_positions, None]
        )

        angular_momentum_vectors = np.cross(positions_m, velocities_m_s)
        angular_momentum_norms = np.linalg.norm(angular_momentum_vectors, axis=1)
        valid_angular_momentum = angular_momentum_norms > 1e-30
        normal_unit_vectors = np.zeros_like(positions_m)
        normal_unit_vectors[:, 2] = 1.0
        normal_unit_vectors[valid_angular_momentum] = (
            angular_momentum_vectors[valid_angular_momentum]
            / angular_momentum_norms[valid_angular_momentum, None]
        )
        transverse_unit_vectors = np.cross(normal_unit_vectors, radial_unit_vectors)

        velocity_rtn = np.column_stack(
            (
                np.einsum("ij,ij->i", velocities_m_s, radial_unit_vectors),
                np.einsum("ij,ij->i", velocities_m_s, transverse_unit_vectors),
                np.einsum("ij,ij->i", velocities_m_s, normal_unit_vectors),
            )
        )
        velocity_norms = np.linalg.norm(velocity_rtn, axis=1)
        valid_velocities = valid_positions & (velocity_norms > 1e-30)
        directions = np.zeros_like(velocity_rtn)
        directions[valid_velocities] = (
            velocity_rtn[valid_velocities] / velocity_norms[valid_velocities, None]
        )
        return directions


def compute_series_chunk(
    raw: np.ndarray,
    segment_ids: np.ndarray,
    group: SeriesGroupName,
    start: int,
    stop: int,
) -> np.ndarray:
    """Compute one derived-series span without store or cache lifecycle state."""
    if group not in _SERIES_COLUMNS:
        raise ValueError(f"unsupported series group: {group}")
    output = np.empty((stop - start, len(_SERIES_COLUMNS[group])), dtype=float)
    if stop == start:
        return output

    output[:, 0] = raw[start:stop, 0]

    if group == "kinematics":
        states = raw[start:stop, 1:7]
        positions = states[:, 0:3]
        velocities = states[:, 3:6]
        output[:, 1] = np.linalg.norm(velocities, axis=1)
        output[:, 2] = np.linalg.norm(positions, axis=1)
        output[:, 3] = wgs.ecef_to_lla(positions)[:, 2]
        return output

    if group == "rtn":
        output[:, 1:] = np.nan
        same_segment = np.zeros(stop - start, dtype=bool)
        global_rows = np.arange(start, stop)
        valid = global_rows > 0
        same_segment[valid] = (
            segment_ids[global_rows[valid]] == segment_ids[global_rows[valid] - 1]
        )
        valid_rows = global_rows[same_segment]
        if valid_rows.size:
            output[same_segment, 1:] = misc.transform_to_rtn(
                raw[valid_rows, 1:7],
                raw[valid_rows - 1, 1:7],
            )
        return output

    if group == "distance-delta":
        output[:, 1] = 0.0
        distances = np.linalg.norm(raw[start:stop, 1:4], axis=1)
        if start > 0:
            previous_distances = np.linalg.norm(
                raw[start - 1 : stop - 1, 1:4],
                axis=1,
            )
        else:
            previous_distances = np.empty(0, dtype=float)

        global_rows = np.arange(start, stop)
        valid = global_rows > 0
        same_segment = np.zeros(stop - start, dtype=bool)
        same_segment[valid] = (
            segment_ids[global_rows[valid]] == segment_ids[global_rows[valid] - 1]
        )
        if np.any(same_segment):
            valid_indices = np.flatnonzero(same_segment)
            if start == 0:
                previous_distances = np.concatenate(
                    ([np.linalg.norm(raw[0, 1:4])],
                     np.linalg.norm(raw[start : stop - 1, 1:4], axis=1))
                )
            output[valid_indices, 1] = (
                distances[valid_indices] - previous_distances[valid_indices]
            )
        return output

    window_start = max(0, start - 1)
    window_states = raw[window_start:stop, 1:7]
    directions = OrbitSeries._compute_rtn_velocity_direction_vectors(window_states)
    output[:, 1:3] = 0.0
    output[:, 3:6] = 0.0
    output[:, 6:9] = 0.0

    radial = directions[:, 0]
    transverse = directions[:, 1]
    normal = directions[:, 2]
    pitch = np.arctan2(radial, transverse)
    yaw = np.arctan2(normal, np.hypot(radial, transverse))

    current_indices = np.arange(start, stop) - window_start
    output[:, 3] = 0.0
    output[:, 4] = pitch[current_indices]
    output[:, 5] = yaw[current_indices]

    global_rows = np.arange(start, stop)
    valid = global_rows > 0
    same_segment = np.zeros(stop - start, dtype=bool)
    same_segment[valid] = (
        segment_ids[global_rows[valid]] == segment_ids[global_rows[valid] - 1]
    )
    valid_indices = np.flatnonzero(same_segment)
    if valid_indices.size:
        global_valid_rows = global_rows[valid_indices]
        previous_indices = global_valid_rows - 1 - window_start
        current_window_indices = current_indices[valid_indices]
        dot_products = np.einsum(
            "ij,ij->i",
            directions[previous_indices],
            directions[current_window_indices],
        )
        angle_rad = np.arccos(np.clip(dot_products, -1.0, 1.0))
        delta_time_s = (
            raw[global_valid_rows, 0] - raw[global_valid_rows - 1, 0]
        )
        positive_delta = delta_time_s > 0.0
        output[valid_indices, 1] = angle_rad
        positive_indices = valid_indices[positive_delta]
        output[positive_indices, 2] = (
            angle_rad[positive_delta] / delta_time_s[positive_delta]
        )
        pitch_delta = pitch[current_window_indices] - pitch[previous_indices]
        yaw_delta = yaw[current_window_indices] - yaw[previous_indices]
        output[valid_indices, 6] = 0.0
        output[positive_indices, 7] = (
            pitch_delta[positive_delta] / delta_time_s[positive_delta]
        )
        output[positive_indices, 8] = (
            yaw_delta[positive_delta] / delta_time_s[positive_delta]
        )
    return output


def compute_orbit_series(
    timestamps_s: list[float],
    states_m: list[np.ndarray],
    time_unit: TimeUnit,
    segment_ids: list[int] | np.ndarray | None = None,
) -> OrbitSeries:
    """Compute all derived series needed by playback and plotting routines.

    Parameters
    ----------
    timestamps_s : list[float]
        State timestamps in TT seconds since J2000.
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
    segments = np.asarray(
        segment_ids if segment_ids is not None else np.zeros(len(states_m)),
        dtype=int,
    )
    if segments.shape != (len(states_m),) or np.any(np.diff(segments) < 0):
        raise ValueError("segment_ids must be non-decreasing and match states_m")
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

    rtn_delta_km: np.ndarray
    if len(states_m) >= 2:
        rtn_delta_km = np.full((len(states_m) - 1, 6), np.nan)
        same_segment = segments[1:] == segments[:-1]
        if np.any(same_segment):
            rtn_delta_km[same_segment] = (
                misc.transform_to_rtn(
                    states_matrix_m[1:][same_segment],
                    states_matrix_m[:-1][same_segment],
                )
                * KILOMETERS_PER_METER
            )
    else:
        rtn_delta_km = np.empty((0, 6))

    if len(states_m) >= 2:
        velocity_direction_vectors = OrbitSeries._compute_rtn_velocity_direction_vectors(
            states_matrix_m
        )
        direction_change_angle_deg: np.ndarray = np.zeros(len(states_m), dtype=float)
        direction_change_rate_deg_s: np.ndarray = np.zeros(len(states_m), dtype=float)
        angular_velocity_deg_s: np.ndarray = np.zeros(len(states_m), dtype=float)
        angular_velocity_rad_s: np.ndarray = np.zeros(len(states_m), dtype=float)

        indices = np.arange(1, len(states_m), dtype=np.intp)
        same_segment = segments[indices] == segments[indices - 1]
        valid_indices = indices[same_segment]
        if valid_indices.size:
            dot_products = np.einsum(
                "ij,ij->i",
                velocity_direction_vectors[valid_indices - 1],
                velocity_direction_vectors[valid_indices],
            )
            angle_rad = np.arccos(np.clip(dot_products, -1.0, 1.0))
            angle_deg = np.degrees(angle_rad)
            direction_change_angle_deg[valid_indices] = angle_deg
            delta_time_s = (
                elapsed_time_s[valid_indices] - elapsed_time_s[valid_indices - 1]
            )
            positive_delta = delta_time_s > 0.0
            positive_indices = valid_indices[positive_delta]
            direction_change_rate_deg_s[positive_indices] = (
                angle_deg[positive_delta] / delta_time_s[positive_delta]
            )
            angular_velocity_deg_s[positive_indices] = (
                angle_deg[positive_delta] / delta_time_s[positive_delta]
            )
            angular_velocity_rad_s[positive_indices] = (
                angle_rad[positive_delta] / delta_time_s[positive_delta]
            )

        radial = velocity_direction_vectors[:, 0]
        transverse = velocity_direction_vectors[:, 1]
        normal = velocity_direction_vectors[:, 2]
        pitch_deg = np.degrees(np.arctan2(radial, transverse))
        yaw_deg = np.degrees(
            np.arctan2(normal, np.hypot(radial, transverse))
        )
        euler_angles_deg = np.column_stack(
            (
                np.zeros(len(states_m), dtype=float),
                pitch_deg,
                yaw_deg,
            )
        )
        euler_angle_rates_deg_s = np.zeros_like(euler_angles_deg)
        if valid_indices.size:
            positive_delta = (
                elapsed_time_s[valid_indices] - elapsed_time_s[valid_indices - 1]
            ) > 0.0
            positive_indices = valid_indices[positive_delta]
            delta_time_s = (
                elapsed_time_s[positive_indices]
                - elapsed_time_s[positive_indices - 1]
            )
            euler_angle_rates_deg_s[positive_indices] = (
                euler_angles_deg[positive_indices]
                - euler_angles_deg[positive_indices - 1]
            ) / delta_time_s[:, np.newaxis]
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
        rtn_elapsed_time=np.array(elapsed_time[1:], dtype=float),
        rtn_delta_km=rtn_delta_km,
        direction_change_angle_deg=direction_change_angle_deg,
        direction_change_rate_deg_s=direction_change_rate_deg_s,
        angular_velocity_deg_s=angular_velocity_deg_s,
        angular_velocity_rad_s=angular_velocity_rad_s,
        euler_angles_deg=euler_angles_deg,
        euler_angle_rates_deg_s=euler_angle_rates_deg_s,
        segment_ids=segments,
        rtn_segment_ids=np.where(segments[1:] == segments[:-1], segments[1:], -1),
    )


def append_orbit_series(
    previous: OrbitSeries,
    previous_timestamp_s: float,
    previous_state_m: np.ndarray,
    previous_segment_id: int,
    timestamps_s: list[float],
    states_m: list[np.ndarray],
    segment_ids: list[int] | np.ndarray,
    time_unit: TimeUnit,
) -> OrbitSeries:
    """Append derived samples, computing only the new batch and its boundary delta."""
    if not timestamps_s:
        return previous
    local_timestamps = [previous_timestamp_s, *timestamps_s]
    local_states = [previous_state_m, *states_m]
    local_segments = [previous_segment_id, *np.asarray(segment_ids, dtype=int).tolist()]
    local = compute_orbit_series(
        local_timestamps, local_states, time_unit, local_segments
    )
    elapsed_offset = float(previous.elapsed_time[-1])
    local.elapsed_time += elapsed_offset
    local.rtn_elapsed_time += elapsed_offset

    sample_fields = (
        "elapsed_time",
        "position_km",
        "velocity_km_s",
        "velocity_magnitude_km_s",
        "geocentric_distance_km",
        "altitude_km",
        "direction_change_angle_deg",
        "direction_change_rate_deg_s",
        "angular_velocity_deg_s",
        "angular_velocity_rad_s",
        "euler_angles_deg",
        "euler_angle_rates_deg_s",
        "segment_ids",
    )
    delta_fields = ("rtn_elapsed_time", "rtn_delta_km", "rtn_segment_ids")
    updates: dict[str, np.ndarray] = {}
    for field_name in sample_fields:
        old = getattr(previous, field_name)
        new = getattr(local, field_name)[1:]
        updates[field_name] = np.concatenate((old, new), axis=0)
    for field_name in delta_fields:
        old = getattr(previous, field_name)
        new = getattr(local, field_name)
        updates[field_name] = np.concatenate((old, new), axis=0)
    return replace(previous, **updates)


def align_single_sample_series(orbit_series: OrbitSeries) -> OrbitSeries:
    """Fill sample-derived fields for a one-sample prefix with their neutral values."""
    if len(orbit_series.elapsed_time) != 1 or len(orbit_series.direction_change_angle_deg):
        return orbit_series
    return replace(
        orbit_series,
        direction_change_angle_deg=np.zeros(1, dtype=float),
        direction_change_rate_deg_s=np.zeros(1, dtype=float),
        angular_velocity_deg_s=np.zeros(1, dtype=float),
        angular_velocity_rad_s=np.zeros(1, dtype=float),
        euler_angles_deg=np.zeros((1, 3), dtype=float),
        euler_angle_rates_deg_s=np.zeros((1, 3), dtype=float),
    )
