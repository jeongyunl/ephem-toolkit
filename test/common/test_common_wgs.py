"""Tests for common/wgs.py — Coordinate conversion utilities for LLA and ENU frames.

Validates ECEF-to-ENU, ENU-to-ECEF, LLA-to-ECEF, and ECEF-to-LLA conversions.
Includes round-trip tests, batch processing, and edge cases (poles, equator).
"""

from __future__ import annotations

import numpy as np
import pytest

import common.wgs as wgs
import common.consts as consts

# ===================================================================
# Test Constants and Fixtures
# ===================================================================

REF_LLA_EQUATOR: np.ndarray = np.array([0.0, 0.0, 0.0])
"""Reference point at equator, prime meridian, sea level."""

REF_LLA_NORTH_POLE: np.ndarray = np.array([np.pi / 2.0, 0.0, 0.0])
"""Reference point at North Pole, sea level."""

REF_LLA_ARBITRARY: np.ndarray = np.array([np.radians(45.0), np.radians(10.0), 100.0])
"""Reference point at arbitrary location (45°N, 10°E, 100m altitude)."""

STATE_ISS_ECEF: np.ndarray = np.array(
    [
        -2700816.14,
        -3314092.80,
        5266346.42,  # position [m]
        5168.606550,
        -5597.546618,
        -2131.981798,  # velocity [m/s]
    ]
)
"""ISS-like orbit state in ECEF."""


# ===================================================================
# 1. ecef_to_enu - Single position vector conversion
# ===================================================================


def test_ecef_to_enu_single_position_returns_correct_shape() -> None:
    """Should return a single ENU position vector with shape (3,)."""
    ecef_pos = np.array([consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0])
    result = wgs.ecef_to_enu(ecef_pos, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_ecef_to_enu_at_reference_point_is_zero() -> None:
    """Should return [0, 0, 0] when ECEF position equals reference point."""
    ref_ecef = wgs.lla_to_ecef(REF_LLA_EQUATOR)
    result = wgs.ecef_to_enu(ref_ecef, REF_LLA_EQUATOR)

    np.testing.assert_allclose(result, np.zeros(3), atol=1e-6)


def test_ecef_to_enu_point_east_of_reference() -> None:
    """Should return positive East component for point east of reference."""
    # Reference at equator, prime meridian
    ref_lla = REF_LLA_EQUATOR
    # Point slightly east (0.01 degrees longitude)
    point_lla = np.array([0.0, np.radians(0.01), 0.0])
    point_ecef = wgs.lla_to_ecef(point_lla)

    result = wgs.ecef_to_enu(point_ecef, ref_lla)

    # East component should be positive
    assert result[0] > 0.0
    # North and Up should be near zero
    assert abs(result[1]) < 100.0  # within 100m
    assert abs(result[2]) < 100.0


def test_ecef_to_enu_point_north_of_reference() -> None:
    """Should return positive North component for point north of reference."""
    # Reference at equator, prime meridian
    ref_lla = REF_LLA_EQUATOR
    # Point slightly north (0.01 degrees latitude)
    point_lla = np.array([np.radians(0.01), 0.0, 0.0])
    point_ecef = wgs.lla_to_ecef(point_lla)

    result = wgs.ecef_to_enu(point_ecef, ref_lla)

    # North component should be positive
    assert result[1] > 0.0
    # East and Up should be near zero
    assert abs(result[0]) < 100.0
    assert abs(result[2]) < 100.0


def test_ecef_to_enu_point_above_reference() -> None:
    """Should return positive Up component for point above reference."""
    # Reference at sea level
    ref_lla = REF_LLA_EQUATOR
    # Point 1000m above reference
    point_lla = np.array([0.0, 0.0, 1000.0])
    point_ecef = wgs.lla_to_ecef(point_lla)

    result = wgs.ecef_to_enu(point_ecef, ref_lla)

    # Up component should be approximately 1000m
    assert result[2] == pytest.approx(1000.0, abs=1.0)
    # East and North should be near zero
    assert abs(result[0]) < 1.0
    assert abs(result[1]) < 1.0


# ===================================================================
# 2. ecef_to_enu - Batch processing
# ===================================================================


def test_ecef_to_enu_batch_positions_returns_correct_shape() -> None:
    """Should return batch of ENU positions with shape (N, 3)."""
    ecef_positions = np.array(
        [
            [consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0],
            [0.0, consts.EARTH_EQUATORIAL_RADIUS_M, 0.0],
            [0.0, 0.0, consts.EARTH_EQUATORIAL_RADIUS_M],
        ]
    )
    result = wgs.ecef_to_enu(ecef_positions, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 3)


def test_ecef_to_enu_batch_consistent_with_single() -> None:
    """Should produce same results for batch and single conversions."""
    ecef_positions = np.array(
        [
            [consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0],
            [0.0, consts.EARTH_EQUATORIAL_RADIUS_M, 0.0],
        ]
    )

    # Batch conversion
    result_batch = wgs.ecef_to_enu(ecef_positions, REF_LLA_EQUATOR)

    # Single conversions
    result_single_0 = wgs.ecef_to_enu(ecef_positions[0], REF_LLA_EQUATOR)
    result_single_1 = wgs.ecef_to_enu(ecef_positions[1], REF_LLA_EQUATOR)

    np.testing.assert_allclose(result_batch[0], result_single_0, rtol=1e-14)
    np.testing.assert_allclose(result_batch[1], result_single_1, rtol=1e-14)


# ===================================================================
# 3. ecef_to_enu - Input validation
# ===================================================================


def test_ecef_to_enu_raises_on_invalid_ecef_shape() -> None:
    """Should raise ValueError for ECEF position with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_enu(np.array([1.0, 2.0]), REF_LLA_EQUATOR)

    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_enu(np.array([1.0, 2.0, 3.0, 4.0]), REF_LLA_EQUATOR)


def test_ecef_to_enu_raises_on_invalid_reference_lla_shape() -> None:
    """Should raise ValueError for reference LLA with wrong shape."""
    ecef_pos = np.array([consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0])

    with pytest.raises(ValueError, match="Reference LLA"):
        wgs.ecef_to_enu(ecef_pos, np.array([0.0, 0.0]))

    with pytest.raises(ValueError, match="Reference LLA"):
        wgs.ecef_to_enu(ecef_pos, np.array([[0.0, 0.0, 0.0]]))


def test_ecef_to_enu_raises_on_3d_array() -> None:
    """Should raise ValueError for 3D array input."""
    ecef_positions = np.zeros((2, 3, 3))

    with pytest.raises(ValueError, match="1D or 2D"):
        wgs.ecef_to_enu(ecef_positions, REF_LLA_EQUATOR)


# ===================================================================
# 4. ecef_to_enu_velocity - Velocity conversion (rotation only)
# ===================================================================


def test_ecef_to_enu_velocity_single_returns_correct_shape() -> None:
    """Should return a single ENU velocity vector with shape (3,)."""
    ecef_vel = np.array([100.0, 200.0, 300.0])
    result = wgs.ecef_to_enu_velocity(ecef_vel, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_ecef_to_enu_velocity_preserves_magnitude() -> None:
    """Should preserve velocity magnitude (pure rotation)."""
    ecef_vel = np.array([100.0, 200.0, 300.0])
    result = wgs.ecef_to_enu_velocity(ecef_vel, REF_LLA_EQUATOR)

    original_magnitude = np.linalg.norm(ecef_vel)
    result_magnitude = np.linalg.norm(result)

    assert result_magnitude == pytest.approx(original_magnitude, rel=1e-14)


def test_ecef_to_enu_velocity_batch_returns_correct_shape() -> None:
    """Should return batch of ENU velocities with shape (N, 3)."""
    ecef_velocities = np.array(
        [[100.0, 200.0, 300.0], [50.0, 100.0, 150.0], [10.0, 20.0, 30.0]]
    )
    result = wgs.ecef_to_enu_velocity(ecef_velocities, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 3)


def test_ecef_to_enu_velocity_raises_on_invalid_shape() -> None:
    """Should raise ValueError for velocity with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_enu_velocity(np.array([1.0, 2.0]), REF_LLA_EQUATOR)


# ===================================================================
# 5. ecef_to_enu_state - Combined state vector conversion
# ===================================================================


def test_ecef_to_enu_state_single_returns_correct_shape() -> None:
    """Should return a single ENU state vector with shape (6,)."""
    ecef_state = STATE_ISS_ECEF
    result = wgs.ecef_to_enu_state(ecef_state, REF_LLA_ARBITRARY)

    assert isinstance(result, np.ndarray)
    assert result.shape == (6,)


def test_ecef_to_enu_state_batch_returns_correct_shape() -> None:
    """Should return batch of ENU states with shape (N, 6)."""
    ecef_states = np.array([STATE_ISS_ECEF, STATE_ISS_ECEF * 1.1])
    result = wgs.ecef_to_enu_state(ecef_states, REF_LLA_ARBITRARY)

    assert isinstance(result, np.ndarray)
    assert result.shape == (2, 6)


def test_ecef_to_enu_state_consistent_with_separate_conversions() -> None:
    """Should produce same results as separate position and velocity conversions."""
    ecef_state = STATE_ISS_ECEF
    ref_lla = REF_LLA_ARBITRARY

    # Combined conversion
    result_combined = wgs.ecef_to_enu_state(ecef_state, ref_lla)

    # Separate conversions
    enu_pos = wgs.ecef_to_enu(ecef_state[0:3], ref_lla)
    enu_vel = wgs.ecef_to_enu_velocity(ecef_state[3:6], ref_lla)

    np.testing.assert_allclose(result_combined[0:3], enu_pos, rtol=1e-14)
    np.testing.assert_allclose(result_combined[3:6], enu_vel, rtol=1e-14)


def test_ecef_to_enu_state_raises_on_invalid_shape() -> None:
    """Should raise ValueError for state with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_enu_state(np.array([1.0, 2.0, 3.0]), REF_LLA_EQUATOR)

    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_enu_state(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), REF_LLA_EQUATOR)


# ===================================================================
# 6. enu_to_ecef - Inverse of ecef_to_enu (round-trip test)
# ===================================================================


def test_enu_to_ecef_single_returns_correct_shape() -> None:
    """Should return a single ECEF position vector with shape (3,)."""
    enu_pos = np.array([1000.0, 500.0, 100.0])
    result = wgs.enu_to_ecef(enu_pos, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_enu_to_ecef_round_trip_single() -> None:
    """Should round-trip ECEF -> ENU -> ECEF with negligible error."""
    ecef_original = np.array([consts.EARTH_EQUATORIAL_RADIUS_M + 1000.0, 500.0, 100.0])
    ref_lla = REF_LLA_EQUATOR

    # Forward conversion
    enu_pos = wgs.ecef_to_enu(ecef_original, ref_lla)

    # Inverse conversion
    ecef_recovered = wgs.enu_to_ecef(enu_pos, ref_lla)

    np.testing.assert_allclose(ecef_recovered, ecef_original, rtol=1e-12, atol=1e-6)


def test_enu_to_ecef_round_trip_batch() -> None:
    """Should round-trip batch ECEF -> ENU -> ECEF with negligible error."""
    ecef_original = np.array(
        [
            [consts.EARTH_EQUATORIAL_RADIUS_M + 1000.0, 500.0, 100.0],
            [consts.EARTH_EQUATORIAL_RADIUS_M - 1000.0, -500.0, 200.0],
            [1000.0, consts.EARTH_EQUATORIAL_RADIUS_M, 300.0],
        ]
    )
    ref_lla = REF_LLA_ARBITRARY

    # Forward conversion
    enu_positions = wgs.ecef_to_enu(ecef_original, ref_lla)

    # Inverse conversion
    ecef_recovered = wgs.enu_to_ecef(enu_positions, ref_lla)

    np.testing.assert_allclose(ecef_recovered, ecef_original, rtol=1e-12, atol=1e-6)


def test_enu_to_ecef_raises_on_invalid_shape() -> None:
    """Should raise ValueError for ENU position with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        wgs.enu_to_ecef(np.array([1.0, 2.0]), REF_LLA_EQUATOR)


# ===================================================================
# 7. enu_to_ecef_velocity - Inverse of ecef_to_enu_velocity
# ===================================================================


def test_enu_to_ecef_velocity_single_returns_correct_shape() -> None:
    """Should return a single ECEF velocity vector with shape (3,)."""
    enu_vel = np.array([100.0, 50.0, 10.0])
    result = wgs.enu_to_ecef_velocity(enu_vel, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_enu_to_ecef_velocity_round_trip() -> None:
    """Should round-trip ECEF velocity -> ENU -> ECEF with negligible error."""
    ecef_vel_original = np.array([5168.606550, -5597.546618, -2131.981798])
    ref_lla = REF_LLA_ARBITRARY

    # Forward conversion
    enu_vel = wgs.ecef_to_enu_velocity(ecef_vel_original, ref_lla)

    # Inverse conversion
    ecef_vel_recovered = wgs.enu_to_ecef_velocity(enu_vel, ref_lla)

    np.testing.assert_allclose(
        ecef_vel_recovered, ecef_vel_original, rtol=1e-12, atol=1e-9
    )


def test_enu_to_ecef_velocity_preserves_magnitude() -> None:
    """Should preserve velocity magnitude (pure rotation)."""
    enu_vel = np.array([100.0, 200.0, 300.0])
    result = wgs.enu_to_ecef_velocity(enu_vel, REF_LLA_EQUATOR)

    original_magnitude = np.linalg.norm(enu_vel)
    result_magnitude = np.linalg.norm(result)

    assert result_magnitude == pytest.approx(original_magnitude, rel=1e-14)


# ===================================================================
# 8. enu_to_ecef_state - Inverse of ecef_to_enu_state
# ===================================================================


def test_enu_to_ecef_state_single_returns_correct_shape() -> None:
    """Should return a single ECEF state vector with shape (6,)."""
    enu_state = np.array([1000.0, 500.0, 100.0, 10.0, 5.0, 1.0])
    result = wgs.enu_to_ecef_state(enu_state, REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (6,)


def test_enu_to_ecef_state_round_trip() -> None:
    """Should round-trip ECEF state -> ENU -> ECEF with negligible error."""
    ecef_state_original = STATE_ISS_ECEF
    ref_lla = REF_LLA_ARBITRARY

    # Forward conversion
    enu_state = wgs.ecef_to_enu_state(ecef_state_original, ref_lla)

    # Inverse conversion
    ecef_state_recovered = wgs.enu_to_ecef_state(enu_state, ref_lla)

    np.testing.assert_allclose(
        ecef_state_recovered, ecef_state_original, rtol=1e-12, atol=1e-6
    )


def test_enu_to_ecef_state_batch_round_trip() -> None:
    """Should round-trip batch ECEF states -> ENU -> ECEF with negligible error."""
    ecef_states_original = np.array([STATE_ISS_ECEF, STATE_ISS_ECEF * 1.1])
    ref_lla = REF_LLA_ARBITRARY

    # Forward conversion
    enu_states = wgs.ecef_to_enu_state(ecef_states_original, ref_lla)

    # Inverse conversion
    ecef_states_recovered = wgs.enu_to_ecef_state(enu_states, ref_lla)

    np.testing.assert_allclose(
        ecef_states_recovered, ecef_states_original, rtol=1e-12, atol=1e-6
    )


# ===================================================================
# 9. lla_to_ecef - Geodetic to ECEF conversion
# ===================================================================


def test_lla_to_ecef_single_returns_correct_shape() -> None:
    """Should return a single ECEF position vector with shape (3,)."""
    result = wgs.lla_to_ecef(REF_LLA_EQUATOR)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_lla_to_ecef_equator_prime_meridian_sea_level() -> None:
    """Should return [a, 0, 0] for equator, prime meridian, sea level."""
    result = wgs.lla_to_ecef(REF_LLA_EQUATOR)

    expected = np.array([consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0])
    np.testing.assert_allclose(result, expected, rtol=1e-12, atol=1e-6)


def test_lla_to_ecef_north_pole_sea_level() -> None:
    """Should return [0, 0, b] for North Pole at sea level (b = polar radius)."""
    result = wgs.lla_to_ecef(REF_LLA_NORTH_POLE)

    # Polar radius b = a * (1 - f)
    b = consts.EARTH_EQUATORIAL_RADIUS_M * (1.0 - wgs.EARTH_FLATTENING)
    expected = np.array([0.0, 0.0, b])

    np.testing.assert_allclose(result, expected, rtol=1e-12, atol=1e-3)


def test_lla_to_ecef_equator_90_degrees_east() -> None:
    """Should return [0, a, 0] for equator at 90°E, sea level."""
    lla = np.array([0.0, np.pi / 2.0, 0.0])
    result = wgs.lla_to_ecef(lla)

    expected = np.array([0.0, consts.EARTH_EQUATORIAL_RADIUS_M, 0.0])
    np.testing.assert_allclose(result, expected, rtol=1e-12, atol=1e-6)


def test_lla_to_ecef_altitude_increases_radius() -> None:
    """Should increase ECEF magnitude when altitude increases."""
    lla_sea_level = REF_LLA_EQUATOR
    lla_altitude = np.array([0.0, 0.0, 1000.0])

    ecef_sea_level = wgs.lla_to_ecef(lla_sea_level)
    ecef_altitude = wgs.lla_to_ecef(lla_altitude)

    magnitude_sea_level = np.linalg.norm(ecef_sea_level)
    magnitude_altitude = np.linalg.norm(ecef_altitude)

    assert magnitude_altitude > magnitude_sea_level
    assert magnitude_altitude == pytest.approx(magnitude_sea_level + 1000.0, abs=1.0)


def test_lla_to_ecef_batch_returns_correct_shape() -> None:
    """Should return batch of ECEF positions with shape (N, 3)."""
    lla_batch = np.array(
        [
            [0.0, 0.0, 0.0],
            [np.pi / 4.0, np.pi / 4.0, 100.0],
            [np.pi / 2.0, 0.0, 0.0],
        ]
    )
    result = wgs.lla_to_ecef(lla_batch)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 3)


def test_lla_to_ecef_raises_on_invalid_shape() -> None:
    """Should raise ValueError for LLA with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        wgs.lla_to_ecef(np.array([0.0, 0.0]))

    with pytest.raises(ValueError, match="shape"):
        wgs.lla_to_ecef(np.array([0.0, 0.0, 0.0, 0.0]))


# ===================================================================
# 10. ecef_to_lla - ECEF to geodetic conversion
# ===================================================================


def test_ecef_to_lla_single_returns_correct_shape() -> None:
    """Should return a single LLA coordinate with shape (3,)."""
    ecef = np.array([consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0])
    result = wgs.ecef_to_lla(ecef)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3,)


def test_ecef_to_lla_equator_prime_meridian() -> None:
    """Should return [0, 0, 0] for ECEF [a, 0, 0]."""
    ecef = np.array([consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0])
    result = wgs.ecef_to_lla(ecef)

    expected = np.array([0.0, 0.0, 0.0])
    np.testing.assert_allclose(result, expected, atol=1e-9)


def test_ecef_to_lla_north_pole() -> None:
    """Should return [π/2, lon, 0] for North Pole (lon is arbitrary)."""
    b = consts.EARTH_EQUATORIAL_RADIUS_M * (1.0 - wgs.EARTH_FLATTENING)
    ecef = np.array([0.0, 0.0, b])
    result = wgs.ecef_to_lla(ecef)

    # Latitude should be π/2
    assert result[0] == pytest.approx(np.pi / 2.0, abs=1e-9)
    # Altitude should be near 0
    assert abs(result[2]) < 1.0


def test_ecef_to_lla_south_pole() -> None:
    """Should return [-π/2, lon, 0] for South Pole (lon is arbitrary)."""
    b = consts.EARTH_EQUATORIAL_RADIUS_M * (1.0 - wgs.EARTH_FLATTENING)
    ecef = np.array([0.0, 0.0, -b])
    result = wgs.ecef_to_lla(ecef)

    # Latitude should be -π/2
    assert result[0] == pytest.approx(-np.pi / 2.0, abs=1e-9)
    # Altitude should be near 0
    assert abs(result[2]) < 1.0


def test_ecef_to_lla_round_trip_single() -> None:
    """Should round-trip LLA -> ECEF -> LLA with negligible error."""
    lla_original = REF_LLA_ARBITRARY

    # Forward conversion
    ecef = wgs.lla_to_ecef(lla_original)

    # Inverse conversion
    lla_recovered = wgs.ecef_to_lla(ecef)

    np.testing.assert_allclose(lla_recovered, lla_original, rtol=1e-10, atol=1e-8)


def test_ecef_to_lla_round_trip_batch() -> None:
    """Should round-trip batch LLA -> ECEF -> LLA with negligible error."""
    lla_original = np.array(
        [
            [0.0, 0.0, 0.0],
            [np.radians(45.0), np.radians(10.0), 100.0],
            [np.radians(-30.0), np.radians(-120.0), 5000.0],
            [np.radians(89.0), np.radians(0.0), 0.0],  # Near pole
        ]
    )

    # Forward conversion
    ecef = wgs.lla_to_ecef(lla_original)

    # Inverse conversion
    lla_recovered = wgs.ecef_to_lla(ecef)

    np.testing.assert_allclose(lla_recovered, lla_original, rtol=1e-12, atol=1e-9)


def test_ecef_to_lla_batch_returns_correct_shape() -> None:
    """Should return batch of LLA coordinates with shape (N, 3)."""
    ecef_batch = np.array(
        [
            [consts.EARTH_EQUATORIAL_RADIUS_M, 0.0, 0.0],
            [0.0, consts.EARTH_EQUATORIAL_RADIUS_M, 0.0],
            [1000.0, 1000.0, 1000.0],
        ]
    )
    result = wgs.ecef_to_lla(ecef_batch)

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 3)


def test_ecef_to_lla_convergence_tolerance() -> None:
    """Should converge within specified tolerance."""
    ecef = np.array([consts.EARTH_EQUATORIAL_RADIUS_M + 1000.0, 500.0, 100.0])

    # Default tolerance
    result_default = wgs.ecef_to_lla(ecef)

    # Stricter tolerance
    result_strict = wgs.ecef_to_lla(ecef, tolerance=1e-15)

    # Results should be very close
    np.testing.assert_allclose(result_default, result_strict, rtol=1e-10, atol=1e-12)


def test_ecef_to_lla_max_iterations() -> None:
    """Should respect max_iterations parameter."""
    ecef = np.array([consts.EARTH_EQUATORIAL_RADIUS_M + 1000.0, 500.0, 100.0])

    # Should still converge with fewer iterations for this simple case
    result = wgs.ecef_to_lla(ecef, max_iterations=5)

    # Verify result is reasonable
    assert 0.0 <= abs(result[0]) < np.pi / 2.0  # Valid latitude
    assert -np.pi <= result[1] <= np.pi  # Valid longitude
    assert result[2] > 0.0  # Positive altitude


def test_ecef_to_lla_raises_on_invalid_shape() -> None:
    """Should raise ValueError for ECEF with wrong shape."""
    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_lla(np.array([1.0, 2.0]))

    with pytest.raises(ValueError, match="shape"):
        wgs.ecef_to_lla(np.array([1.0, 2.0, 3.0, 4.0]))


# ===================================================================
# 11. Edge cases and special scenarios
# ===================================================================


def test_ecef_to_enu_at_north_pole_reference() -> None:
    """Should handle North Pole as reference point correctly."""
    ref_lla = REF_LLA_NORTH_POLE
    ref_ecef = wgs.lla_to_ecef(ref_lla)

    # Point slightly away from pole
    point_lla = np.array([np.radians(89.9), 0.0, 0.0])
    point_ecef = wgs.lla_to_ecef(point_lla)

    result = wgs.ecef_to_enu(point_ecef, ref_lla)

    # Should produce valid ENU coordinates
    assert np.isfinite(result).all()


def test_round_trip_with_high_altitude() -> None:
    """Should handle high altitude points correctly (e.g., GEO satellites)."""
    # GEO altitude ~35,786 km
    lla_geo = np.array([0.0, 0.0, 35786000.0])

    # Round-trip LLA -> ECEF -> LLA
    ecef = wgs.lla_to_ecef(lla_geo)
    lla_recovered = wgs.ecef_to_lla(ecef)

    np.testing.assert_allclose(lla_recovered, lla_geo, rtol=1e-10, atol=1.0)


def test_round_trip_with_negative_altitude() -> None:
    """Should handle negative altitude (below sea level) correctly."""
    # Dead Sea is ~430m below sea level
    lla_below = np.array([np.radians(31.5), np.radians(35.5), -430.0])

    # Round-trip LLA -> ECEF -> LLA
    ecef = wgs.lla_to_ecef(lla_below)
    lla_recovered = wgs.ecef_to_lla(ecef)

    np.testing.assert_allclose(lla_recovered, lla_below, rtol=1e-12, atol=1e-6)


def test_enu_coordinate_system_orthogonality() -> None:
    """Should produce orthogonal ENU axes (rotation matrix is orthogonal)."""
    ref_lla = REF_LLA_ARBITRARY

    # Create three orthogonal unit vectors in ENU
    enu_east = np.array([1.0, 0.0, 0.0])
    enu_north = np.array([0.0, 1.0, 0.0])
    enu_up = np.array([0.0, 0.0, 1.0])

    # Convert to ECEF
    ecef_east = wgs.enu_to_ecef_velocity(enu_east, ref_lla)
    ecef_north = wgs.enu_to_ecef_velocity(enu_north, ref_lla)
    ecef_up = wgs.enu_to_ecef_velocity(enu_up, ref_lla)

    # Check orthogonality in ECEF
    assert abs(np.dot(ecef_east, ecef_north)) < 1e-12
    assert abs(np.dot(ecef_east, ecef_up)) < 1e-12
    assert abs(np.dot(ecef_north, ecef_up)) < 1e-12

    # Check unit magnitude preserved
    assert np.linalg.norm(ecef_east) == pytest.approx(1.0, rel=1e-14)
    assert np.linalg.norm(ecef_north) == pytest.approx(1.0, rel=1e-14)
    assert np.linalg.norm(ecef_up) == pytest.approx(1.0, rel=1e-14)
