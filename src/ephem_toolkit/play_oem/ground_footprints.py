"""WGS-84 ellipsoid ground-footprint boundaries for playback samples."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from numbers import Integral
from typing import Any

import numpy as np

from .ground_track import GroundTrackPreparationError, _ecef_to_wgs84_geodetic

WGS84_SEMI_MAJOR_AXIS_M = 6_378_137.0
WGS84_FLATTENING = 1.0 / 298.257223563
MAX_GEODESIC_SEARCH_DISTANCE_M = 20_000_000.0
ROOT_ITERATIONS = 40
DEFAULT_AZIMUTH_COUNT = 72


class GroundFootprintError(ValueError):
    """Raised when a satellite position cannot produce a ground footprint."""


@dataclass(frozen=True)
class GroundFootprintBoundary:
    """A sampled geodetic boundary, or one point for a collapsed footprint."""

    latitude_rad: np.ndarray
    longitude_rad: np.ndarray
    collapsed: bool = False


@dataclass(frozen=True)
class GroundFootprints:
    """Current-time coverage boundaries on the WGS-84 ellipsoid."""

    horizon: GroundFootprintBoundary
    minimum_elevation: GroundFootprintBoundary | None
    minimum_elevation_deg: int


def _geod() -> Any:
    from pyproj import Geod

    return Geod(a=WGS84_SEMI_MAJOR_AXIS_M, f=WGS84_FLATTENING)


def _wgs84_geodetic_to_ecef(
    latitude_rad: np.ndarray, longitude_rad: np.ndarray
) -> np.ndarray:
    sin_lat = np.sin(latitude_rad)
    cos_lat = np.cos(latitude_rad)
    eccentricity_squared = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)
    prime_vertical = WGS84_SEMI_MAJOR_AXIS_M / np.sqrt(
        1.0 - eccentricity_squared * sin_lat**2
    )
    return np.column_stack(
        (
            prime_vertical * cos_lat * np.cos(longitude_rad),
            prime_vertical * cos_lat * np.sin(longitude_rad),
            prime_vertical * (1.0 - eccentricity_squared) * sin_lat,
        )
    )


def _ground_elevation_deg(
    satellite_ecef_m: np.ndarray,
    ground_latitude_rad: np.ndarray,
    ground_longitude_rad: np.ndarray,
) -> np.ndarray:
    ground_ecef_m = _wgs84_geodetic_to_ecef(ground_latitude_rad, ground_longitude_rad)
    line_of_sight = satellite_ecef_m[None, :] - ground_ecef_m
    line_of_sight_norm = np.linalg.norm(line_of_sight, axis=1)
    normals = np.column_stack(
        (
            np.cos(ground_latitude_rad) * np.cos(ground_longitude_rad),
            np.cos(ground_latitude_rad) * np.sin(ground_longitude_rad),
            np.sin(ground_latitude_rad),
        )
    )
    sine_elevation = np.sum(normals * line_of_sight, axis=1) / line_of_sight_norm
    return np.rad2deg(np.arcsin(np.clip(sine_elevation, -1.0, 1.0)))


def _boundary_at_elevation(
    satellite_ecef_m: np.ndarray,
    subpoint_latitude_rad: float,
    subpoint_longitude_rad: float,
    elevation_deg: int,
    azimuth_count: int,
) -> GroundFootprintBoundary:
    azimuths_deg = np.arange(azimuth_count, dtype=float) * (360.0 / azimuth_count)
    low_distance = np.zeros(azimuth_count, dtype=float)
    high_distance = np.full(azimuth_count, MAX_GEODESIC_SEARCH_DISTANCE_M, dtype=float)
    geod = _geod()
    subpoint_latitude_deg = float(np.rad2deg(subpoint_latitude_rad))
    subpoint_longitude_deg = float(np.rad2deg(subpoint_longitude_rad))

    for _ in range(ROOT_ITERATIONS):
        middle_distance = (low_distance + high_distance) * 0.5
        longitude_deg, latitude_deg, _ = geod.fwd(
            np.full(azimuth_count, subpoint_longitude_deg),
            np.full(azimuth_count, subpoint_latitude_deg),
            azimuths_deg,
            middle_distance,
        )
        latitude_rad = np.deg2rad(latitude_deg)
        longitude_rad = np.deg2rad(longitude_deg)
        visible = (
            _ground_elevation_deg(satellite_ecef_m, latitude_rad, longitude_rad)
            >= elevation_deg
        )
        low_distance = np.where(visible, middle_distance, low_distance)
        high_distance = np.where(visible, high_distance, middle_distance)

    longitude_deg, latitude_deg, _ = geod.fwd(
        np.full(azimuth_count, subpoint_longitude_deg),
        np.full(azimuth_count, subpoint_latitude_deg),
        azimuths_deg,
        (low_distance + high_distance) * 0.5,
    )
    return GroundFootprintBoundary(
        latitude_rad=np.deg2rad(np.asarray(latitude_deg, dtype=float)),
        longitude_rad=np.deg2rad(np.asarray(longitude_deg, dtype=float)),
    )


@lru_cache(maxsize=32)
def _compute_ground_footprints_cached(
    position: tuple[float, float, float], minimum_elevation_deg: int, azimuth_count: int
) -> GroundFootprints:
    satellite_ecef_m = np.asarray(position, dtype=float)
    try:
        geodetic = _ecef_to_wgs84_geodetic(satellite_ecef_m.reshape(1, 3))[0]
    except GroundTrackPreparationError as error:
        raise GroundFootprintError(str(error)) from error
    subpoint_latitude_rad, subpoint_longitude_rad, satellite_altitude_m = geodetic
    if not np.isfinite(geodetic).all() or satellite_altitude_m <= 0.0:
        raise GroundFootprintError(
            "A ground footprint requires a satellite position outside the WGS-84 ellipsoid"
        )

    horizon = _boundary_at_elevation(
        satellite_ecef_m,
        float(subpoint_latitude_rad),
        float(subpoint_longitude_rad),
        0,
        azimuth_count,
    )
    if minimum_elevation_deg == 0:
        minimum_boundary = None
    elif minimum_elevation_deg == 90:
        minimum_boundary = GroundFootprintBoundary(
            np.asarray([subpoint_latitude_rad], dtype=float),
            np.asarray([subpoint_longitude_rad], dtype=float),
            collapsed=True,
        )
    else:
        minimum_boundary = _boundary_at_elevation(
            satellite_ecef_m,
            float(subpoint_latitude_rad),
            float(subpoint_longitude_rad),
            minimum_elevation_deg,
            azimuth_count,
        )
    return GroundFootprints(horizon, minimum_boundary, minimum_elevation_deg)


def compute_ground_footprints(
    satellite_ecef_m: np.ndarray,
    minimum_elevation_deg: int,
    *,
    azimuth_count: int = DEFAULT_AZIMUTH_COUNT,
) -> GroundFootprints:
    """Compute WGS-84 horizon and mask boundaries, sharing repeated panel work."""
    if isinstance(minimum_elevation_deg, bool) or not isinstance(
        minimum_elevation_deg, Integral
    ):
        raise GroundFootprintError(
            "Minimum elevation must be an integer number of degrees"
        )
    minimum_elevation_deg = int(minimum_elevation_deg)
    if not 0 <= minimum_elevation_deg <= 90:
        raise GroundFootprintError("Minimum elevation must be from 0° through 90°")
    if isinstance(azimuth_count, bool) or not isinstance(azimuth_count, Integral):
        raise GroundFootprintError("Azimuth count must be an integer")
    azimuth_count = int(azimuth_count)
    if azimuth_count < 8:
        raise GroundFootprintError("Azimuth count must be at least 8")
    position = np.asarray(satellite_ecef_m, dtype=float)
    if position.shape != (3,) or not np.isfinite(position).all():
        raise GroundFootprintError("Satellite position must be a finite ECEF vector")
    return _compute_ground_footprints_cached(
        tuple(float(value) for value in position), minimum_elevation_deg, azimuth_count
    )
