"""Derived orbit series used by OEM playback and views."""

from __future__ import annotations

from dataclasses import dataclass, replace

import ephem_toolkit.core.misc as misc
import ephem_toolkit.core.wgs as wgs
import numpy as np

from .time_unit import TimeUnit

KILOMETERS_PER_METER: float = 0.001
"""Length conversion factor from meters (m) to kilometers (km)."""


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
    def _compute_rtn_velocity_direction_vector(state_m: np.ndarray) -> np.ndarray:
        """Return the velocity direction expressed in the local RTN frame."""
        position_m = state_m[0:3]
        velocity_m_s = state_m[3:6]
        position_norm = float(np.linalg.norm(position_m))
        if position_norm <= 1e-30:
            return np.zeros(3, dtype=float)
        radial_unit_vector = position_m / position_norm
        angular_momentum_vector = np.cross(position_m, velocity_m_s)
        angular_momentum_norm = float(np.linalg.norm(angular_momentum_vector))
        if angular_momentum_norm <= 1e-30:
            normal_unit_vector = np.array([0.0, 0.0, 1.0], dtype=float)
        else:
            normal_unit_vector = angular_momentum_vector / angular_momentum_norm
        transverse_unit_vector = np.cross(
            normal_unit_vector, radial_unit_vector
        )
        velocity_rtn = np.array(
            [
                np.dot(velocity_m_s, radial_unit_vector),
                np.dot(velocity_m_s, transverse_unit_vector),
                np.dot(velocity_m_s, normal_unit_vector),
            ],
            dtype=float,
        )
        velocity_norm = float(np.linalg.norm(velocity_rtn))
        if velocity_norm <= 1e-30:
            return np.zeros(3, dtype=float)
        return velocity_rtn / velocity_norm

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

        for sample_index in range(1, len(states_m)):
            if segments[sample_index] != segments[sample_index - 1]:
                continue
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
            if segments[sample_index] != segments[sample_index - 1]:
                continue
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
