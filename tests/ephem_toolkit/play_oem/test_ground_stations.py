"""Tests for ground-station validation and topocentric geometry."""

from __future__ import annotations

import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_stations import (
    GroundStation,
    create_ground_station,
    station_ecef_m,
    station_metrics,
)


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
    fields = dict(
        station_id="id",
        name="Site",
        latitude_deg=0.0,
        longitude_deg=0.0,
        altitude_m=0.0,
        minimum_elevation_deg=10,
    )
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

    metrics = station_metrics(station, state, "ITRF", 0.0)

    assert metrics.azimuth_deg == pytest.approx(expected_azimuth)
    assert metrics.elevation_deg == pytest.approx(expected_elevation)
    assert metrics.slant_range_km == pytest.approx(1000.0)
    assert metrics.access


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

    assert station_metrics(station, state, "ITRF", 0.0).access
