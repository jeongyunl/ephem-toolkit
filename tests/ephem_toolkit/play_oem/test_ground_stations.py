"""Tests for ground-station validation and topocentric geometry."""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_stations import (
    GroundStation,
    create_ground_station,
    station_ecef_m,
    station_metrics,
    station_metrics_from_ecef_batch,
)


class StationFields(TypedDict):
    station_id: str
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    minimum_elevation_deg: int


def test_station_normalizes_name_and_longitude_and_generates_id() -> None:
    station = create_ground_station("  Site A  ", 45.0, 180.0, -5.0)

    assert station.name == "Site A"
    assert station.longitude_deg == -180.0
    assert station.station_id


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"name": " "}, "name"),
        ({"latitude_deg": 90.1}, "latitude"),
        ({"longitude_deg": 180.1}, "longitude"),
        ({"altitude_m": float("nan")}, "altitude"),
        ({"minimum_elevation_deg": True}, "minimum_elevation"),
    ],
)
def test_station_rejects_invalid_fields(values, message: str) -> None:
    fields: StationFields = {
        "station_id": "id",
        "name": "Site",
        "latitude_deg": 0.0,
        "longitude_deg": 0.0,
        "altitude_m": 0.0,
        "minimum_elevation_deg": 10,
    }
    fields.update(values)

    with pytest.raises(ValueError, match=message):
        GroundStation(**fields)


@pytest.mark.parametrize(
    ("enu", "expected_azimuth", "expected_elevation"),
    [
        ((0.0, 0.0, 1_000_000.0), 0.0, 90.0),
        ((1_000_000.0, 0.0, 0.0), 90.0, 0.0),
        ((0.0, 1_000_000.0, 0.0), 0.0, 0.0),
        ((-1_000_000.0, 0.0, 0.0), 270.0, 0.0),
    ],
)
def test_station_metrics_known_enu_directions(
    enu: tuple[float, float, float],
    expected_azimuth: float,
    expected_elevation: float,
) -> None:
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 0)
    station_position = station_ecef_m(station)
    # At latitude/longitude zero, ENU axes map to ECEF y, z, and x.
    state = np.array(
        [
            station_position[0] + enu[2],
            station_position[1] + enu[0],
            station_position[2] + enu[1],
            0.0,
            0.0,
            0.0,
        ]
    )

    metrics = station_metrics(station, state)

    assert metrics.azimuth_deg == pytest.approx(expected_azimuth)
    assert metrics.elevation_deg == pytest.approx(expected_elevation)
    assert metrics.slant_range_km == pytest.approx(1000.0)
    assert metrics.access


def test_station_metrics_batch_matches_scalar_for_finite_positions() -> None:
    station = GroundStation("id", "Site", 35.0, -117.0, 100.0)
    station_position = station_ecef_m(station)
    positions = np.array(
        [
            station_position,
            station_position + np.array([1_000.0, 2_000.0, 3_000.0]),
            np.array([np.nan, 0.0, 0.0]),
        ],
        dtype=float,
    )

    batched = station_metrics_from_ecef_batch(station, positions)

    assert batched[0] is not None
    assert batched[0].slant_range_km == pytest.approx(0.0)
    assert batched[1] is not None
    scalar = station_metrics(station, np.concatenate((positions[1], (0.0, 0.0, 0.0))))
    assert batched[1].azimuth_deg == pytest.approx(scalar.azimuth_deg)
    assert batched[1].elevation_deg == pytest.approx(scalar.elevation_deg)
    assert batched[1].slant_range_km == pytest.approx(scalar.slant_range_km)
    assert batched[2] is None


def test_station_access_uses_inclusive_mask_boundary() -> None:
    station = GroundStation("id", "Site", 0.0, 0.0, 0.0, 30)
    base = station_ecef_m(station)
    elevation = np.deg2rad(30.0)
    state = np.array(
        [
            base[0] + np.sin(elevation) * 1_000_000.0,
            base[1] + np.cos(elevation) * 1_000_000.0,
            base[2],
            0.0,
            0.0,
            0.0,
        ]
    )

    assert station_metrics(station, state).access
