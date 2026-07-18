"""Tests for oem_to_tle/orbital_mechanics.py — Orbital mechanics utilities."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.tle as tle
import oem_to_tle.models as models
import oem_to_tle.orbital_mechanics as orbital_mechanics

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parent / "data"
"""Directory containing test data files (OEM, TLE, OMM samples)."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
"""Path to ISS OEM test file for 2026-05-20."""

JPSS1_OEM_PATH: Path = TEST_DATA_DIR / "JPSS-1.oem"
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
