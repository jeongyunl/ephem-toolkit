"""Numerical checks for Ground Track's WGS-84 coverage boundaries."""

from __future__ import annotations

import numpy as np
import pytest
from pyproj import Geod

from ephem_toolkit.play_oem import ground_footprints


def _satellite_ecef(
    latitude_deg: float, longitude_deg: float, altitude_m: float
) -> np.ndarray:
    latitude_rad = np.deg2rad(latitude_deg)
    longitude_rad = np.deg2rad(longitude_deg)
    flattening = ground_footprints.WGS84_FLATTENING
    eccentricity_squared = flattening * (2.0 - flattening)
    prime_vertical = ground_footprints.WGS84_SEMI_MAJOR_AXIS_M / np.sqrt(
        1.0 - eccentricity_squared * np.sin(latitude_rad) ** 2
    )
    return np.array(
        [
            (prime_vertical + altitude_m)
            * np.cos(latitude_rad)
            * np.cos(longitude_rad),
            (prime_vertical + altitude_m)
            * np.cos(latitude_rad)
            * np.sin(longitude_rad),
            (prime_vertical * (1.0 - eccentricity_squared) + altitude_m)
            * np.sin(latitude_rad),
        ]
    )


def test_horizon_and_minimum_boundary_meet_their_elevation_angles() -> None:
    satellite = _satellite_ecef(20.0, 179.0, 420_000.0)

    footprints = ground_footprints.compute_ground_footprints(satellite, 10)

    horizon_elevation = ground_footprints._ground_elevation_deg(
        satellite, footprints.horizon.latitude_rad, footprints.horizon.longitude_rad
    )
    mask = footprints.minimum_elevation
    assert mask is not None
    mask_elevation = ground_footprints._ground_elevation_deg(
        satellite, mask.latitude_rad, mask.longitude_rad
    )
    np.testing.assert_allclose(horizon_elevation, 0.0, atol=1e-6)
    np.testing.assert_allclose(mask_elevation, 10.0, atol=1e-6)
    assert footprints.horizon.latitude_rad.shape == (72,)


def test_minimum_boundary_is_inside_horizon_and_zero_reuses_horizon() -> None:
    satellite = _satellite_ecef(-35.0, -40.0, 700_000.0)
    ten_degree = ground_footprints.compute_ground_footprints(satellite, 10)
    minimum = ten_degree.minimum_elevation
    assert minimum is not None
    geod = Geod(
        a=ground_footprints.WGS84_SEMI_MAJOR_AXIS_M,
        f=ground_footprints.WGS84_FLATTENING,
    )
    _, _, horizon_distances = geod.inv(
        np.full(72, -40.0),
        np.full(72, -35.0),
        np.rad2deg(ten_degree.horizon.longitude_rad),
        np.rad2deg(ten_degree.horizon.latitude_rad),
    )
    _, _, mask_distances = geod.inv(
        np.full(72, -40.0),
        np.full(72, -35.0),
        np.rad2deg(minimum.longitude_rad),
        np.rad2deg(minimum.latitude_rad),
    )
    assert np.all(mask_distances < horizon_distances)

    zero_degree = ground_footprints.compute_ground_footprints(satellite, 0)

    assert zero_degree.minimum_elevation is None
    assert zero_degree.minimum_elevation_deg == 0
    np.testing.assert_array_equal(
        zero_degree.horizon.latitude_rad, ten_degree.horizon.latitude_rad
    )


def test_ninety_degrees_collapses_to_subsatellite_point() -> None:
    satellite = _satellite_ecef(67.0, 115.0, 500_000.0)

    footprints = ground_footprints.compute_ground_footprints(satellite, 90)

    minimum = footprints.minimum_elevation
    assert minimum is not None and minimum.collapsed
    assert minimum.latitude_rad.shape == (1,)
    assert minimum.longitude_rad.shape == (1,)
    assert minimum.latitude_rad[0] == pytest.approx(np.deg2rad(67.0), abs=1e-8)
    assert minimum.longitude_rad[0] == pytest.approx(np.deg2rad(115.0), abs=1e-8)


def test_polar_satellite_has_finite_boundaries() -> None:
    satellite = _satellite_ecef(90.0, 0.0, 800_000.0)

    footprints = ground_footprints.compute_ground_footprints(
        satellite, 15, azimuth_count=36
    )

    assert np.isfinite(footprints.horizon.latitude_rad).all()
    assert np.isfinite(footprints.horizon.longitude_rad).all()
    assert footprints.minimum_elevation is not None
    assert np.isfinite(footprints.minimum_elevation.latitude_rad).all()


@pytest.mark.parametrize("minimum", [-1, 91, 10.5, True])
def test_invalid_minimum_elevation_is_rejected(minimum: object) -> None:
    with pytest.raises(ground_footprints.GroundFootprintError):
        ground_footprints.compute_ground_footprints(
            _satellite_ecef(0.0, 0.0, 400_000.0), minimum  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "position",
    [np.zeros(3), np.array([np.nan, 0.0, 0.0]), np.array([1.0, 2.0])],
)
def test_invalid_satellite_position_has_no_footprint(position: np.ndarray) -> None:
    with pytest.raises(ground_footprints.GroundFootprintError):
        ground_footprints.compute_ground_footprints(position, 10)


def test_azimuth_count_must_support_a_closed_outline() -> None:
    with pytest.raises(ground_footprints.GroundFootprintError, match="at least 8"):
        ground_footprints.compute_ground_footprints(
            _satellite_ecef(0.0, 0.0, 400_000.0), 10, azimuth_count=4
        )
