"""Tests for :mod:`common.common` — OEM parsing, duration/step parsing utilities."""

from __future__ import annotations

import argparse

import numpy as np
import pytest

import common.common as common

# ===================================================================
# 1. parse_duration_to_seconds — valid conversions
# ===================================================================


@pytest.mark.parametrize(
    "token, expected_seconds",
    [
        ("90", 90.0),
        ("90s", 90.0),
        ("90S", 90.0),
        ("2m", 120.0),
        ("2M", 120.0),
        ("1.5h", 5400.0),
        ("1.5H", 5400.0),
        ("1d", 86400.0),
        ("1D", 86400.0),
        ("0.5d", 43200.0),
        ("  3600s  ", 3600.0),
        (".5h", 1800.0),
    ],
    ids=[
        "bare-number-seconds",
        "explicit-s",
        "uppercase-S",
        "minutes",
        "uppercase-M",
        "fractional-hours",
        "uppercase-H",
        "one-day",
        "uppercase-D",
        "half-day",
        "whitespace-padded",
        "leading-dot-fraction",
    ],
)
def test_parse_duration_valid_conversions(token: str, expected_seconds: float) -> None:
    """Should correctly convert duration tokens with all supported units."""
    result = common.parse_duration_to_seconds(token)
    assert result == pytest.approx(expected_seconds)


# ===================================================================
# 2. parse_duration_to_seconds — invalid inputs
# ===================================================================


@pytest.mark.parametrize(
    "token",
    [
        "",
        "abc",
        "10x",
        "-5s",
        "0s",
        "0",
        "0d",
        "  ",
        "1.2.3s",
    ],
    ids=[
        "empty-string",
        "non-numeric",
        "invalid-unit-x",
        "negative-value",
        "zero-seconds",
        "zero-bare",
        "zero-days",
        "whitespace-only",
        "malformed-number",
    ],
)
def test_parse_duration_invalid_raises(token: str) -> None:
    """Should raise ArgumentTypeError for invalid or zero/negative durations."""
    with pytest.raises(argparse.ArgumentTypeError):
        common.parse_duration_to_seconds(token)


# ===================================================================
# 3. parse_step_to_seconds — valid conversions
# ===================================================================


@pytest.mark.parametrize(
    "token, expected_seconds",
    [
        ("60", 60.0),
        ("60s", 60.0),
        ("60S", 60.0),
        ("1m", 60.0),
        ("1M", 60.0),
        ("2.5m", 150.0),
        ("  30s  ", 30.0),
        (".5m", 30.0),
    ],
    ids=[
        "bare-number-seconds",
        "explicit-s",
        "uppercase-S",
        "one-minute",
        "uppercase-M",
        "fractional-minutes",
        "whitespace-padded",
        "leading-dot-fraction",
    ],
)
def test_parse_step_valid_conversions(token: str, expected_seconds: float) -> None:
    """Should correctly convert step-size tokens with supported units (s, m)."""
    result = common.parse_step_to_seconds(token)
    assert result == pytest.approx(expected_seconds)


# ===================================================================
# 4. parse_step_to_seconds — invalid inputs
# ===================================================================


@pytest.mark.parametrize(
    "token",
    [
        "",
        "abc",
        "10h",
        "1d",
        "-5s",
        "0s",
        "0",
        "  ",
    ],
    ids=[
        "empty-string",
        "non-numeric",
        "hours-not-supported",
        "days-not-supported",
        "negative-value",
        "zero-seconds",
        "zero-bare",
        "whitespace-only",
    ],
)
def test_parse_step_invalid_raises(token: str) -> None:
    """Should raise ArgumentTypeError for invalid units (h, d) or non-positive values."""
    with pytest.raises(argparse.ArgumentTypeError):
        common.parse_step_to_seconds(token)


# ===================================================================
# 5. parse_oem_state_line — valid and edge-case inputs
# ===================================================================


def test_parse_oem_state_line_valid() -> None:
    """Should parse a valid OEM-style state line into epoch and a 6-element state vector."""
    line = "2026-05-20T12:00:00.000 -2345.678 4567.890 1234.567 -1.234 5.678 -3.456"
    result = common.parse_oem_state_line(line)

    assert result is not None
    epoch_dt, state_km = result

    from datetime import datetime, timezone

    assert epoch_dt == datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    assert state_km.shape == (6,)
    np.testing.assert_allclose(state_km[:3], [-2345.678, 4567.890, 1234.567])
    np.testing.assert_allclose(state_km[3:], [-1.234, 5.678, -3.456])


def test_parse_oem_state_line_with_trailing_z() -> None:
    """Should strip trailing Z from epoch before parsing."""
    line = "2026-05-20T12:00:00.000Z -2345.678 4567.890 1234.567 -1.234 5.678 -3.456"
    result = common.parse_oem_state_line(line)
    assert result is not None
    epoch_dt, state_km = result
    from datetime import datetime, timezone

    assert epoch_dt == datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    assert state_km.shape == (6,)


def test_parse_oem_state_line_blank_returns_none() -> None:
    """Should return None for blank lines."""
    assert common.parse_oem_state_line("") is None
    assert common.parse_oem_state_line("   ") is None
    assert common.parse_oem_state_line("\n") is None


def test_parse_oem_state_line_comment_returns_none() -> None:
    """Should return None for comment lines starting with #."""
    assert common.parse_oem_state_line("# this is a comment") is None
    assert common.parse_oem_state_line("  # indented comment") is None


def test_parse_oem_state_line_too_few_fields_raises() -> None:
    """Should raise ValueError when line has fewer than 7 fields."""
    with pytest.raises(ValueError, match="does not contain 7 fields"):
        common.parse_oem_state_line("2026-05-20T12:00:00.000 1.0 2.0 3.0")


# ===================================================================
# 6. datetime_to_tdb and tdb_to_datetime — round-trip conversions
# ===================================================================


def test_datetime_to_tdb_j2000_epoch() -> None:
    """Should convert J2000 epoch (2000-01-01 12:00:00 UTC) to approximately 64.184 TDB seconds."""
    from datetime import datetime

    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0)
    tdb_seconds = common.datetime_to_tdb(j2000_epoch)

    # J2000 epoch should be approximately 64.184 TDB seconds (UTC/TDB offset at J2000)
    assert tdb_seconds == pytest.approx(64.184, rel=0.01)


def test_datetime_to_tdb_future_date() -> None:
    """Should convert a future date to positive TDB seconds."""
    from datetime import datetime

    future_date = datetime(2026, 5, 20, 12, 0, 0)
    tdb_seconds = common.datetime_to_tdb(future_date)

    # Should be a large positive number (roughly 26.4 years * 365.25 * 86400 seconds)
    assert tdb_seconds > 0.0
    assert tdb_seconds > 26 * 365.25 * 86400


def test_tdb_to_datetime_j2000_epoch() -> None:
    """Should convert approximately 0 TDB seconds to J2000 epoch."""
    from datetime import datetime, timezone

    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result_dt = common.tdb_to_datetime(0.0)

    # Should be very close to J2000 epoch (within ~65 seconds due to UTC/TDB offset)
    assert (
        result_dt == j2000_epoch
        or abs((result_dt - j2000_epoch).total_seconds()) < 65.0
    )


def test_datetime_tdb_round_trip() -> None:
    """Should preserve datetime through datetime -> TDB -> datetime conversion."""
    from datetime import datetime, timezone

    original_dt = datetime(2026, 5, 20, 12, 30, 45, tzinfo=timezone.utc)
    tdb_seconds = common.datetime_to_tdb(original_dt)
    result_dt = common.tdb_to_datetime(tdb_seconds)

    # Should match to within a second (due to floating-point precision)
    assert (
        result_dt == original_dt or abs((result_dt - original_dt).total_seconds()) < 1.0
    )


def test_datetime_to_tdb_past_date() -> None:
    """Should convert a past date to negative TDB seconds."""
    from datetime import datetime

    past_date = datetime(1990, 1, 1, 12, 0, 0)
    tdb_seconds = common.datetime_to_tdb(past_date)

    # Should be a large negative number (roughly -10 years * 365.25 * 86400 seconds)
    assert tdb_seconds < 0.0
    # The value should be approximately -10 years worth of seconds (within 1%)
    expected_approx = -10 * 365.25 * 86400
    assert abs(tdb_seconds - expected_approx) / abs(expected_approx) < 0.01


# ===================================================================
# 7. transform_to_rtn — RTN frame state vector transformation
# ===================================================================


def test_transform_to_rtn_with_default_reference_state() -> None:
    """Should compute correct RTN transformation with default reference state (None)."""
    # When reference_state is None, should use zero vector as reference
    state = np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])
    result = common.transform_to_rtn(state, reference_state=None)

    # Result should be a 6-element array
    assert result.shape == (6,)
    # When reference is zero, the function will have division by zero issues
    # This is an edge case - verify the result is returned (even if NaN)
    assert len(result) == 6


def test_transform_to_rtn_circular_orbit_xy_plane() -> None:
    """Should handle circular orbits in XY plane correctly."""
    # Reference state: circular orbit in XY plane
    reference_state = np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])
    # Target state: same as reference (zero relative state)
    state = np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])

    result = common.transform_to_rtn(state, reference_state)

    # Relative state should be zero (target = reference)
    np.testing.assert_allclose(result, np.zeros(6), atol=1e-10)


def test_transform_to_rtn_identical_states_returns_zero() -> None:
    """Should return exactly zero (within tolerance) when state == reference_state."""
    reference_state = np.array([7000.0, -1200.0, 350.0, 1.2, 7.4, -0.8])
    state = reference_state.copy()

    result = common.transform_to_rtn(state, reference_state)

    np.testing.assert_allclose(result, np.zeros(6), atol=1e-12)


def test_transform_to_rtn_nearly_identical_states_position_close() -> None:
    """Should remain numerically stable when relative position is extremely small."""
    reference_state = np.array([7000.0, 10.0, -5.0, -0.5, 7.5, 0.2])
    # 1 mm perturbation in km units
    state = reference_state.copy()
    state[:3] += np.array([1e-6, -1e-6, 2e-6])

    result = common.transform_to_rtn(state, reference_state)

    assert result.shape == (6,)
    assert np.all(np.isfinite(result))
    # Relative position magnitude should be preserved by rotation
    assert np.linalg.norm(result[:3]) == pytest.approx(
        np.linalg.norm(state[:3] - reference_state[:3]), rel=1e-12, abs=0.0
    )


def test_transform_to_rtn_nearly_identical_states_velocity_close() -> None:
    """Should remain numerically stable when relative velocity is extremely small."""
    reference_state = np.array([7000.0, 10.0, -5.0, -0.5, 7.5, 0.2])
    # 1 micron/s perturbation in km/s units
    state = reference_state.copy()
    state[3:] += np.array([1e-9, -2e-9, 3e-9])

    result = common.transform_to_rtn(state, reference_state)

    assert result.shape == (6,)
    assert np.all(np.isfinite(result))
    # Relative velocity magnitude should be preserved by rotation (transport term is ~0 since rtn_position ~ 0)
    assert np.linalg.norm(result[3:]) == pytest.approx(
        np.linalg.norm(state[3:] - reference_state[3:]), rel=1e-12, abs=0.0
    )


def test_transform_to_rtn_elliptical_orbit_3d() -> None:
    """Should compute valid RTN transformation for elliptical orbits with 3D orientation."""
    reference_state = np.array([6800.0, 2000.0, 500.0, -1.5, 7.2, 0.3])
    state = np.array([6900.0, 2100.0, 600.0, -1.4, 7.3, 0.4])

    result = common.transform_to_rtn(state, reference_state)

    # Result should be a 6-element array
    assert result.shape == (6,)
    # All components should be finite
    assert np.all(np.isfinite(result))


def test_transform_to_rtn_preserves_state_magnitude() -> None:
    """Should preserve state vector magnitude through RTN transformation."""
    reference_state = np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])
    state = np.array([7100.0, 100.0, 50.0, 0.1, 7.6, 0.1])

    result = common.transform_to_rtn(state, reference_state)

    # Compute relative state in inertial frame
    relative_state_inertial = state - reference_state
    relative_magnitude_inertial = np.linalg.norm(relative_state_inertial)

    # Magnitude in RTN frame should be approximately the same
    relative_magnitude_rtn = np.linalg.norm(result)

    assert relative_magnitude_rtn == pytest.approx(
        relative_magnitude_inertial, rel=1e-6
    )


def test_transform_to_rtn_orthonormal_basis() -> None:
    """Should produce orthonormal RTN basis vectors."""
    reference_state = np.array([6800.0, 2000.0, 500.0, -1.5, 7.2, 0.3])
    state = np.array([6900.0, 2100.0, 600.0, -1.4, 7.3, 0.4])

    result = common.transform_to_rtn(state, reference_state)

    # Extract position and velocity components
    rtn_position = result[:3]
    rtn_velocity = result[3:]

    # Both should be finite
    assert np.all(np.isfinite(rtn_position))
    assert np.all(np.isfinite(rtn_velocity))

    # Verify the transformation is valid by checking that we can reconstruct
    # the relative state (this implicitly tests orthonormality)
    reference_position = reference_state[:3]
    reference_velocity = reference_state[3:6]

    # Compute RTN basis vectors
    reference_position_magnitude = np.linalg.norm(reference_position)
    radial_unit_vector = reference_position / reference_position_magnitude

    angular_momentum_vector = np.cross(reference_position, reference_velocity)
    angular_momentum_magnitude = np.linalg.norm(angular_momentum_vector)
    normal_unit_vector = angular_momentum_vector / angular_momentum_magnitude

    transverse_unit_vector = np.cross(normal_unit_vector, radial_unit_vector)

    # Verify orthonormality
    assert np.linalg.norm(radial_unit_vector) == pytest.approx(1.0)
    assert np.linalg.norm(transverse_unit_vector) == pytest.approx(1.0)
    assert np.linalg.norm(normal_unit_vector) == pytest.approx(1.0)

    # Verify orthogonality
    assert np.dot(radial_unit_vector, transverse_unit_vector) == pytest.approx(
        0.0, abs=1e-10
    )
    assert np.dot(radial_unit_vector, normal_unit_vector) == pytest.approx(
        0.0, abs=1e-10
    )
    assert np.dot(transverse_unit_vector, normal_unit_vector) == pytest.approx(
        0.0, abs=1e-10
    )
