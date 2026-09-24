"""Tests for oem_to_omm/orbital_mechanics.py — Orbital mechanics utilities."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import ephem_toolkit.oem_to_omm.fit_tle.models as models
import ephem_toolkit.oem_to_omm.fit_tle.orbital_mechanics as orbital_mechanics

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parents[2] / "data"
"""Directory containing test data files (OEM, TLE, OMM samples)."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20_small.OEM"
"""Path to ISS OEM test file for 2026-05-20."""

JPSS1_OEM_PATH: Path = TEST_DATA_DIR / "JPSS-1_small.oem"
"""Path to JPSS-1 OEM test file."""


# ===================================================================
# Orbital mechanics utilities
# ===================================================================


def test_state_to_orbital_elements_returns_valid_elements() -> None:
    """Should convert Cartesian state to orbital elements."""
    # Circular orbit at 7000 km radius (6378 km Earth radius + ~622 km altitude)
    # Velocity computed for circular orbit: v = sqrt(mu/r) ≈ 7546 m/s
    state_vector_m = np.array(
        [7000000.0, 0.0, 0.0, 0.0, 7546.0, 0.0]
    )  # (6,) [x, y, z, vx, vy, vz] in SI units (m, m/s)

    elements = orbital_mechanics.state_to_orbital_elements(state_vector_m)

    assert isinstance(elements, models.OrbitalElements)
    assert elements.semi_major_axis_m > 0
    assert 0 <= elements.eccentricity < 1
    assert 0 <= elements.inclination_deg <= 180
    assert 0 <= elements.raan_deg < 360
    assert 0 <= elements.arg_perigee_deg < 360
    assert 0 <= elements.mean_anomaly_deg < 360
    assert elements.mean_motion_rev_per_day > 0


def test_linear_regression_slope_and_intercept() -> None:
    """Should compute linear regression slope and intercept correctly."""
    # Test data follows linear relationship: y = 2x + 1
    time_values = [0.0, 1.0, 2.0, 3.0, 4.0]
    data_values = [1.0, 3.0, 5.0, 7.0, 9.0]

    slope = orbital_mechanics.linear_regression_slope(time_values, data_values)
    intercept = orbital_mechanics.linear_regression_intercept(time_values, data_values)

    # Expected: slope = 2.0, intercept = 1.0
    assert slope == pytest.approx(2.0, abs=1e-10)
    assert intercept == pytest.approx(1.0, abs=1e-10)


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (np.zeros(6), "position norm is zero"),
        (np.array([7.0e6, 0.0, 0.0, 1.0, 0.0, 0.0]), "angular momentum norm is zero"),
    ],
)
def test_state_to_orbital_elements_rejects_degenerate_states(state, message) -> None:
    with pytest.raises(ValueError, match=message):
        orbital_mechanics.state_to_orbital_elements(state)


@pytest.mark.parametrize(
    ("speed", "message"),
    [(np.sqrt(2.0), "Parabolic trajectory"), (2.0, "Hyperbolic trajectory")],
)
def test_state_to_orbital_elements_rejects_unbound_states(
    monkeypatch, speed: float, message: str
) -> None:
    monkeypatch.setattr(
        orbital_mechanics.consts, "EARTH_GRAVITATIONAL_PARAMETER_M3_S2", 1.0
    )

    with pytest.raises(ValueError, match=message):
        orbital_mechanics.state_to_orbital_elements(
            np.array([1.0, 0.0, 0.0, 0.0, speed, 0.0])
        )


def test_state_to_orbital_elements_handles_circular_equatorial_orbit() -> None:
    mu = orbital_mechanics.consts.EARTH_GRAVITATIONAL_PARAMETER_M3_S2
    radius = 7.0e6
    state = np.array([radius, 0.0, 0.0, 0.0, np.sqrt(mu / radius), 0.0])

    elements = orbital_mechanics.state_to_orbital_elements(state)

    assert elements.eccentricity == pytest.approx(0.0, abs=1e-12)
    assert elements.raan_deg == 0.0
    assert elements.arg_perigee_deg == 0.0


def test_linear_regression_handles_empty_and_constant_inputs() -> None:
    assert orbital_mechanics.linear_regression_slope([], []) == 0.0
    assert orbital_mechanics.linear_regression_slope([1.0, 1.0], [2.0, 3.0]) == 0.0
    assert orbital_mechanics.linear_regression_intercept([], []) == 0.0
    assert orbital_mechanics.linear_regression_intercept([4.0], [7.0]) == 7.0


def test_phase_match_epoch_angles_returns_matched_mean_angles() -> None:
    records = [
        models.OrbitalRecord(0.0, 0.1, 0.2, 0.3, 0.5),
        models.OrbitalRecord(1.0, 0.2, 0.3, 0.4, 0.5),
    ]

    result = orbital_mechanics.phase_match_epoch_angles(records, 0.5, 1.0)

    assert result is not None
    assert result.count == 2
    assert result.raan_rad == pytest.approx(0.15)


def test_phase_match_epoch_angles_rejects_nonpositive_period() -> None:
    assert orbital_mechanics.phase_match_epoch_angles([], 0.0, 0.0) is None
