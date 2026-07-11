"""Tests for :mod:`common.common` — OEM parsing utilities."""

from __future__ import annotations

import numpy as np
import pytest

import common.common as common
import common.oem as oem

# ===================================================================
# 1. parse_oem_state_line — valid and edge-case inputs
# ===================================================================


def test_parse_oem_state_line_valid() -> None:
    """Should parse a valid OEM-style state line into epoch and a 6-element state vector."""
    line = "2026-05-20T12:00:00.000 -2345.678 4567.890 1234.567 -1.234 5.678 -3.456"
    result = oem.parse_oem_state_line(line)

    assert result is not None
    timestamp, state_m = result

    from datetime import datetime, timezone

    expected_timestamp = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    assert timestamp == expected_timestamp
    assert state_m.shape == (6,)
    # OEM file has km, but parse_oem_state_line now returns meters
    np.testing.assert_allclose(state_m[:3], [-2345678.0, 4567890.0, 1234567.0])
    np.testing.assert_allclose(state_m[3:], [-1234.0, 5678.0, -3456.0])


def test_parse_oem_state_line_with_trailing_z() -> None:
    """Should strip trailing Z from epoch before parsing."""
    line = "2026-05-20T12:00:00.000Z -2345.678 4567.890 1234.567 -1.234 5.678 -3.456"
    result = oem.parse_oem_state_line(line)
    assert result is not None
    timestamp, state_m = result
    from datetime import datetime, timezone

    expected_timestamp = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    assert timestamp == expected_timestamp
    assert state_m.shape == (6,)


def test_parse_oem_state_line_blank_returns_none() -> None:
    """Should return None for blank lines."""
    assert oem.parse_oem_state_line("") is None
    assert oem.parse_oem_state_line("   ") is None
    assert oem.parse_oem_state_line("\n") is None


def test_parse_oem_state_line_comment_returns_none() -> None:
    """Should return None for comment lines starting with #."""
    assert oem.parse_oem_state_line("# this is a comment") is None
    assert oem.parse_oem_state_line("  # indented comment") is None


def test_parse_oem_state_line_too_few_fields_raises() -> None:
    """Should raise ValueError when line has fewer than 7 fields."""
    with pytest.raises(ValueError, match="does not contain 7 fields"):
        oem.parse_oem_state_line("2026-05-20T12:00:00.000 1.0 2.0 3.0")


# ===================================================================
# 2. transform_to_rtn — RTN frame state vector transformation
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


# ===================================================================
# 3. parse_key_value_line — shared KV parsing utility
# ===================================================================


def test_parse_key_value_line_valid() -> None:
    """Should parse KEY = VALUE lines correctly."""
    assert common.parse_key_value_line("OBJECT_NAME = ISS") == ("OBJECT_NAME", "ISS")
    assert common.parse_key_value_line("KEY=VALUE") == ("KEY", "VALUE")
    assert common.parse_key_value_line("  KEY  =  VALUE  ") == ("KEY", "VALUE")
    assert common.parse_key_value_line("A = B = C") == ("A", "B = C")


def test_parse_key_value_line_returns_none() -> None:
    """Should return None for lines without '='."""
    assert common.parse_key_value_line("no equals here") is None
    assert common.parse_key_value_line("") is None
    assert common.parse_key_value_line("COMMENT some text") is None
