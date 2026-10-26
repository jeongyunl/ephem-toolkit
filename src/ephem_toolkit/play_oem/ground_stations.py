"""Ground-station definitions and WGS-84 topocentric geometry."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from uuid import uuid4

import numpy as np
from numpy.typing import ArrayLike

from .ground_track import GroundTrackPreparationError, state_position_to_itrf_m


@dataclass(frozen=True)
class GroundStation:
    """An immutable ground station using WGS-84 geodetic coordinates."""

    station_id: str
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    minimum_elevation_deg: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.station_id, str) or not self.station_id.strip():
            raise ValueError("station_id must be a non-empty string")
        object.__setattr__(self, "station_id", self.station_id.strip())
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        object.__setattr__(self, "name", self.name.strip())
        for field_name in ("latitude_deg", "longitude_deg", "altitude_m"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be a finite number")
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be a finite number")
            object.__setattr__(self, field_name, value)
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg must be from -90 through 90")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("longitude_deg must be from -180 through 180")
        object.__setattr__(
            self, "longitude_deg", ((self.longitude_deg + 180.0) % 360.0) - 180.0
        )
        if (
            isinstance(self.minimum_elevation_deg, bool)
            or not isinstance(self.minimum_elevation_deg, int)
            or not 0 <= self.minimum_elevation_deg <= 90
        ):
            raise ValueError(
                "minimum_elevation_deg must be an integer from 0 through 90"
            )


def parse_ground_station_records(
    value: object, field_name: str = "ground_stations.stations"
) -> list[GroundStation]:
    """Validate a TOML array of ground-station records."""
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    stations: list[GroundStation] = []
    station_ids: set[str] = set()
    required = {
        "id",
        "name",
        "latitude_deg",
        "longitude_deg",
        "altitude_m",
        "minimum_elevation_deg",
    }
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(f"{field_name}[{index}] must be a table")
        if set(record) != required:
            missing = sorted(required - set(record))
            extra = sorted(set(record) - required)
            detail = (
                f"missing {missing[0]!r}" if missing else f"unknown key {extra[0]!r}"
            )
            raise ValueError(f"{field_name}[{index}] has {detail}")
        try:
            station = GroundStation(
                station_id=record["id"],
                name=record["name"],
                latitude_deg=record["latitude_deg"],
                longitude_deg=record["longitude_deg"],
                altitude_m=record["altitude_m"],
                minimum_elevation_deg=record["minimum_elevation_deg"],
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid {field_name}[{index}]: {error}") from error
        if station.station_id in station_ids:
            raise ValueError(
                f"{field_name} contains duplicate id {station.station_id!r}"
            )
        station_ids.add(station.station_id)
        stations.append(station)
    return stations


def create_ground_station(
    name: str,
    latitude_deg: float,
    longitude_deg: float,
    altitude_m: float,
    minimum_elevation_deg: int = 10,
) -> GroundStation:
    """Create a station with a new stable identity."""
    return GroundStation(
        uuid4().hex,
        name,
        latitude_deg,
        longitude_deg,
        altitude_m,
        minimum_elevation_deg,
    )


@lru_cache(maxsize=1)
def _wgs84_geodetic_transformer():
    from pyproj import Transformer

    return Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)


@lru_cache(maxsize=256)
def station_ecef_m(station: GroundStation) -> np.ndarray:
    """Return the station's WGS-84 ellipsoid location in ECEF meters."""
    try:
        x, y, z = _wgs84_geodetic_transformer().transform(
            station.longitude_deg,
            station.latitude_deg,
            station.altitude_m,
            errcheck=True,
        )
    except Exception as error:
        raise GroundTrackPreparationError(
            f"Cannot convert ground station {station.name!r} to ECEF: {error}"
        ) from error
    result = np.asarray((x, y, z), dtype=float)
    if not np.isfinite(result).all():
        raise GroundTrackPreparationError(
            f"Ground station {station.name!r} produced invalid ECEF coordinates"
        )
    return result


@dataclass(frozen=True)
class StationMetrics:
    """Topocentric view of one spacecraft state from a station."""

    azimuth_deg: float
    elevation_deg: float
    slant_range_km: float
    access: bool


def station_metrics(
    station: GroundStation,
    spacecraft_state_m: ArrayLike,
    frame_name: str,
    epoch_tt_s: float,
) -> StationMetrics:
    """Calculate station-relative azimuth, elevation, range, and access."""
    spacecraft_ecef_m = state_position_to_itrf_m(
        np.asarray(spacecraft_state_m, dtype=float), frame_name, epoch_tt_s
    )[:3]
    return station_metrics_from_ecef(station, spacecraft_ecef_m)


def station_metrics_from_ecef(
    station: GroundStation, spacecraft_ecef_m: ArrayLike
) -> StationMetrics:
    """Calculate station-relative metrics from a spacecraft ECEF position."""
    spacecraft_ecef_m = np.asarray(spacecraft_ecef_m, dtype=float)
    if spacecraft_ecef_m.shape != (3,) or not np.isfinite(spacecraft_ecef_m).all():
        raise GroundTrackPreparationError("Earth-fixed spacecraft position is invalid")
    east_north_up_m = spacecraft_ecef_m - station_ecef_m(station)
    latitude = math.radians(station.latitude_deg)
    longitude = math.radians(station.longitude_deg)
    sin_lat, cos_lat = math.sin(latitude), math.cos(latitude)
    sin_lon, cos_lon = math.sin(longitude), math.cos(longitude)
    x, y, z = (float(value) for value in east_north_up_m)
    east = -sin_lon * x + cos_lon * y
    north = -sin_lat * cos_lon * x - sin_lat * sin_lon * y + cos_lat * z
    up = cos_lat * cos_lon * x + cos_lat * sin_lon * y + sin_lat * z
    horizontal = math.hypot(east, north)
    elevation = math.degrees(math.atan2(up, horizontal))
    azimuth = math.degrees(math.atan2(east, north)) % 360.0
    slant_range = float(np.linalg.norm(east_north_up_m)) / 1000.0
    return StationMetrics(
        azimuth,
        elevation,
        slant_range,
        elevation >= station.minimum_elevation_deg - 1.0e-12,
    )
