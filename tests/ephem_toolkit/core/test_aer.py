"""Tests for core/aer.py — Coordinate conversion utilities for AER frames.

Validates ECEF-to-AER, AER-to-ECEF, ENU-to-AER, and AER-to-ENU conversions.
Includes round-trip tests, batch processing, and edge cases (zenith, nadir, cardinal directions).
"""

from __future__ import annotations

import numpy as np
import pytest

import core.aer as aer
import core.wgs as wgs

# ===================================================================
# Test Constants and Fixtures
# ===================================================================

REF_LLA_EQUATOR: np.ndarray = np.array([0.0, 0.0, 0.0])
"""Reference point at equator, prime meridian, sea level (lat, lon in rad, alt in m)."""

REF_LLA_ARBITRARY: np.ndarray = np.array([np.radians(45.0), np.radians(10.0), 100.0])
"""Reference point at arbitrary location: 45°N, 10°E, 100m altitude (lat, lon in rad, alt in m)."""

ATOL_POSITION_M: float = 1e-6
"""Tolerance for position comparisons (m)."""

ATOL_ANGLE_RAD: float = 1e-9
"""Tolerance for angle comparisons (rad)."""

ATOL_VELOCITY_M_S: float = 1e-9
"""Tolerance for velocity comparisons (m/s)."""


# ===================================================================
# 1. ecef_to_aer - Single position vector conversion
# ===================================================================


def test_ecef_to_aer_single_position_returns_correct_shape() -> None:
    """Should return a single AER position vector with shape (3,)."""
    ref_ecef = wgs.lla_to_ecef(REF_LLA_EQUATOR)
    # Point 1000m east of reference
    ecef_pos = ref_ecef + np.array([0.0, 1000.0, 0.0])
    result = aer.ecef_to_aer(ecef_pos, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_ecef_to_aer_point_north_of_reference() -> None:
    """Should return azimuth=0 (North) for point directly north of reference."""
    ref_lla = REF_LLA_EQUATOR
    # Point 1000m north of reference (small latitude increase)
    point_lla = np.array([np.radians(0.01), 0.0, 0.0])
    point_ecef = wgs.lla_to_ecef(point_lla)

    result = aer.ecef_to_aer(point_ecef, ref_lla)

    # Azimuth should be close to 0 (North)
    assert result[0] == pytest.approx(0.0, abs=np.radians(1.0))
    # Elevation should be close to 0 (on horizon)
    assert abs(result[1]) < np.radians(1.0)
    # Range should be positive
    assert result[2] > 0.0


def test_ecef_to_aer_point_east_of_reference() -> None:
    """Should return azimuth=π/2 (East) for point directly east of reference."""
    ref_lla = REF_LLA_EQUATOR
    # Point east of reference (small longitude increase)
    point_lla = np.array([0.0, np.radians(0.01), 0.0])
    point_ecef = wgs.lla_to_ecef(point_lla)

    result = aer.ecef_to_aer(point_ecef, ref_lla)

    # Azimuth should be close to π/2 (East)
    assert result[0] == pytest.approx(np.pi / 2.0, abs=np.radians(1.0))
    # Elevation should be close to 0 (on horizon)
    assert abs(result[1]) < np.radians(1.0)
    # Range should be positive
    assert result[2] > 0.0


def test_ecef_to_aer_azimuth_in_valid_range() -> None:
    """Should return azimuth in range [0, 2π)."""
    ref_lla = REF_LLA_ARBITRARY
    # Multiple points around reference
    for lat_offset in [-0.01, 0.01]:
        for lon_offset in [-0.01, 0.01]:
            point_lla = ref_lla + np.array(
                [np.radians(lat_offset), np.radians(lon_offset), 0.0]
            )
            point_ecef = wgs.lla_to_ecef(point_lla)
            result = aer.ecef_to_aer(point_ecef, ref_lla)

            # Azimuth should be in [0, 2π)
            assert 0.0 <= result[0] < 2.0 * np.pi


# ===================================================================
# 2. Round-trip tests
# ===================================================================


def test_aer_to_ecef_round_trip_single() -> None:
    """Should round-trip ECEF -> AER -> ECEF with negligible error."""
    ref_lla = REF_LLA_ARBITRARY
    point_lla = ref_lla + np.array([np.radians(0.05), np.radians(0.05), 500.0])
    ecef_original = wgs.lla_to_ecef(point_lla)

    # Forward conversion
    aer_pos = aer.ecef_to_aer(ecef_original, ref_lla)

    # Inverse conversion
    ecef_recovered = aer.aer_to_ecef(aer_pos, ref_lla)

    np.testing.assert_allclose(
        ecef_recovered, ecef_original, rtol=1e-12, atol=ATOL_POSITION_M
    )


def test_aer_to_enu_round_trip_single() -> None:
    """Should round-trip ENU -> AER -> ENU with negligible error."""
    enu_original = np.array([1000.0, 500.0, 100.0])

    # Forward conversion
    aer_pos = aer.enu_to_aer(enu_original)

    # Inverse conversion
    enu_recovered = aer.aer_to_enu(aer_pos)

    np.testing.assert_allclose(
        enu_recovered, enu_original, rtol=1e-14, atol=ATOL_POSITION_M
    )


# ===================================================================
# 3. ENU to AER cardinal directions
# ===================================================================


def test_enu_to_aer_north_direction() -> None:
    """Should return azimuth=0 for point directly north."""
    enu_pos = np.array([0.0, 1000.0, 0.0])  # North
    result = aer.enu_to_aer(enu_pos)

    assert result[0] == pytest.approx(0.0, abs=ATOL_ANGLE_RAD)
    assert result[1] == pytest.approx(0.0, abs=ATOL_ANGLE_RAD)
    assert result[2] == pytest.approx(1000.0, abs=ATOL_POSITION_M)


def test_enu_to_aer_east_direction() -> None:
    """Should return azimuth=π/2 for point directly east."""
    enu_pos = np.array([1000.0, 0.0, 0.0])  # East
    result = aer.enu_to_aer(enu_pos)

    assert result[0] == pytest.approx(np.pi / 2.0, abs=ATOL_ANGLE_RAD)
    assert result[1] == pytest.approx(0.0, abs=ATOL_ANGLE_RAD)
    assert result[2] == pytest.approx(1000.0, abs=ATOL_POSITION_M)


def test_enu_to_aer_zenith_direction() -> None:
    """Should return elevation=π/2 for point directly up (zenith)."""
    enu_pos = np.array([0.0, 0.0, 1000.0])  # Up
    result = aer.enu_to_aer(enu_pos)

    # Azimuth is undefined at zenith, but set to 0 by convention
    assert result[0] == pytest.approx(0.0, abs=ATOL_ANGLE_RAD)
    assert result[1] == pytest.approx(np.pi / 2.0, abs=ATOL_ANGLE_RAD)
    assert result[2] == pytest.approx(1000.0, abs=ATOL_POSITION_M)


# ===================================================================
# 4. Batch processing tests
# ===================================================================


def test_ecef_to_aer_batch_positions_returns_correct_shape() -> None:
    """Should return batch of AER positions with shape (N, 3)."""
    ref_lla = REF_LLA_EQUATOR
    ecef_positions = np.array(
        [
            wgs.lla_to_ecef(np.array([np.radians(0.01), 0.0, 0.0])),
            wgs.lla_to_ecef(np.array([0.0, np.radians(0.01), 0.0])),
            wgs.lla_to_ecef(np.array([0.0, 0.0, 1000.0])),
        ]
    )
    result = aer.ecef_to_aer(ecef_positions, ref_lla)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 3)


def test_aer_to_ecef_round_trip_batch() -> None:
    """Should round-trip batch ECEF -> AER -> ECEF with negligible error."""
    ref_lla = REF_LLA_ARBITRARY
    ecef_original = np.array(
        [
            wgs.lla_to_ecef(ref_lla + np.array([np.radians(0.01), 0.0, 100.0])),
            wgs.lla_to_ecef(ref_lla + np.array([0.0, np.radians(0.01), 200.0])),
            wgs.lla_to_ecef(
                ref_lla + np.array([np.radians(0.01), np.radians(0.01), 300.0])
            ),
        ]
    )

    aer_positions = aer.ecef_to_aer(ecef_original, ref_lla)
    ecef_recovered = aer.aer_to_ecef(aer_positions, ref_lla)

    np.testing.assert_allclose(
        ecef_recovered, ecef_original, rtol=1e-12, atol=ATOL_POSITION_M
    )


# ===================================================================
# 5. State vector tests
# ===================================================================


def test_ecef_to_aer_state_single_returns_correct_shape() -> None:
    """Should return a single AER state vector with shape (6,)."""
    ref_lla = REF_LLA_ARBITRARY
    point_lla = ref_lla + np.array([np.radians(0.01), np.radians(0.01), 100.0])
    ecef_pos = wgs.lla_to_ecef(point_lla)
    ecef_state = np.concatenate([ecef_pos, np.array([100.0, 200.0, 50.0])])

    result = aer.ecef_to_aer_state(ecef_state, ref_lla)

    assert isinstance(result, np.ndarray)
    assert result.shape == (6,)


def test_aer_to_ecef_state_round_trip() -> None:
    """Should round-trip ECEF state -> AER -> ECEF with negligible error."""
    ref_lla = REF_LLA_ARBITRARY
    point_lla = ref_lla + np.array([np.radians(0.05), np.radians(0.05), 500.0])
    ecef_pos = wgs.lla_to_ecef(point_lla)
    ecef_state_original = np.concatenate([ecef_pos, np.array([100.0, 200.0, 50.0])])

    aer_state = aer.ecef_to_aer_state(ecef_state_original, ref_lla)
    ecef_state_recovered = aer.aer_to_ecef_state(aer_state, ref_lla)

    np.testing.assert_allclose(
        ecef_state_recovered, ecef_state_original, rtol=1e-10, atol=ATOL_POSITION_M
    )


# ===================================================================
# 6. Velocity tests
# ===================================================================


def test_ecef_to_aer_velocity_single_returns_correct_shape() -> None:
    """Should return a single AER velocity vector with shape (3,)."""
    ref_lla = REF_LLA_EQUATOR
    ecef_pos = wgs.lla_to_ecef(np.array([0.0, np.radians(0.01), 0.0]))
    ecef_vel = np.array([100.0, 200.0, 50.0])

    result = aer.ecef_to_aer_velocity(ecef_pos, ecef_vel, ref_lla)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_enu_to_aer_velocity_radial_motion() -> None:
    """Should return zero azimuth and elevation rates for purely radial motion."""
    enu_pos = np.array([1000.0, 0.0, 0.0])  # East
    enu_vel = np.array([100.0, 0.0, 0.0])  # Velocity in same direction
    result = aer.enu_to_aer_velocity(enu_pos, enu_vel)

    assert abs(result[0]) < 1e-10  # az_rate should be zero
    assert abs(result[1]) < 1e-10  # el_rate should be zero
    assert result[2] > 0.0  # range_rate should be positive


# ===================================================================
# 7. Input validation tests
# ===================================================================


def test_ecef_to_aer_state_raises_on_invalid_shape() -> None:
    """Should raise ValueError for state with wrong shape."""
    ref_lla = REF_LLA_EQUATOR

    with pytest.raises(ValueError, match="shape"):
        aer.ecef_to_aer_state(np.array([1.0, 2.0, 3.0]), ref_lla)


def test_enu_to_aer_raises_on_invalid_shape() -> None:
    """Should raise ValueError for ENU position with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        aer.enu_to_aer(np.array([1.0, 2.0]))


def test_aer_to_enu_raises_on_invalid_shape() -> None:
    """Should raise ValueError for AER position with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        aer.aer_to_enu(np.array([1.0, 2.0]))


# ===================================================================
# 8. Edge cases
# ===================================================================


def test_enu_to_aer_at_origin() -> None:
    """Should handle origin (zero position) gracefully."""
    enu_pos = np.array([0.0, 0.0, 0.0])
    result = aer.enu_to_aer(enu_pos)

    assert result[0] == pytest.approx(0.0, abs=ATOL_ANGLE_RAD)
    assert abs(result[1]) < ATOL_ANGLE_RAD
    assert result[2] == pytest.approx(0.0, abs=ATOL_POSITION_M)


def test_aer_range_always_positive() -> None:
    """Should always return positive range values."""
    enu_positions = np.array(
        [
            [1000.0, 0.0, 0.0],
            [0.0, 1000.0, 0.0],
            [0.0, 0.0, 1000.0],
            [-1000.0, 0.0, 0.0],
            [0.0, -1000.0, 0.0],
        ]
    )

    results = aer.enu_to_aer(enu_positions)

    assert (results[:, 2] >= 0.0).all()


def test_aer_elevation_in_valid_range() -> None:
    """Should return elevation in range [-π/2, π/2]."""
    enu_positions = np.array(
        [
            [1000.0, 0.0, 0.0],
            [0.0, 1000.0, 0.0],
            [0.0, 0.0, 1000.0],
            [0.0, 0.0, -1000.0],
        ]
    )

    results = aer.enu_to_aer(enu_positions)

    assert (results[:, 1] >= -np.pi / 2.0).all()
    assert (results[:, 1] <= np.pi / 2.0).all()
