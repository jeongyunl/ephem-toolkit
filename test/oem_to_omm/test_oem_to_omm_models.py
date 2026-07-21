"""Tests for oem_to_omm/models.py — Orbital models for TLE conversion."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oem_to_omm.fit_tle.models as models

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parent / "data"
"""Directory containing test data files (OEM, TLE, OMM samples)."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
"""Path to ISS OEM test file for 2026-05-20."""

JPSS1_OEM_PATH: Path = TEST_DATA_DIR / "JPSS-1.oem"
"""Path to JPSS-1 OEM test file."""


# ===================================================================
# Models and data structures
# ===================================================================


def test_orbital_elements_dataclass() -> None:
    """Should create OrbitalElements dataclass with valid fields."""
    elements = models.OrbitalElements(
        semi_major_axis_m=7000000.0,
        eccentricity=0.001,
        inclination_deg=51.6,
        raan_deg=45.0,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
    )

    assert elements.semi_major_axis_m == 7000000.0
    assert elements.eccentricity == 0.001
    assert elements.inclination_deg == 51.6


def test_estimated_dataclass() -> None:
    """Should create Estimated dataclass with all required fields."""
    estimated = models.Estimated(
        epoch_datetime=datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc),
        epoch_year=26,
        epoch_day=140.0,
        inclination_deg=51.6,
        raan_deg=45.0,
        eccentricity=0.001,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
        inclination_deg_osculating_at_epoch=51.6,
        raan_deg_osculating_at_epoch=45.0,
        arg_perigee_deg_osculating_at_epoch=90.0,
        mean_anomaly_deg_osculating_at_epoch=30.0,
        mean_motion_rev_per_day_osculating_at_epoch=15.5,
        mean_motion_rev_per_day_regression_at_epoch=15.5,
        mean_argument_latitude_rate_rev_per_day=15.5,
        phase_match_count=0,
        phase_match_weight=0.0,
        mean_motion_first_derivative=0.0,
        mean_motion_first_derivative_raw=0.0,
        semi_major_axis_m=7000000.0,
        dataset_slope_rev_per_day2=0.0,
    )

    assert estimated.epoch_year == 26
    assert estimated.inclination_deg == 51.6


def test_tle_parameters_from_estimated() -> None:
    """Should create TleParameters from Estimated dataclass."""
    estimated = models.Estimated(
        epoch_datetime=datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc),
        epoch_year=26,
        epoch_day=140.0,
        inclination_deg=51.6,
        raan_deg=45.0,
        eccentricity=0.001,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
        inclination_deg_osculating_at_epoch=51.6,
        raan_deg_osculating_at_epoch=45.0,
        arg_perigee_deg_osculating_at_epoch=90.0,
        mean_anomaly_deg_osculating_at_epoch=30.0,
        mean_motion_rev_per_day_osculating_at_epoch=15.5,
        mean_motion_rev_per_day_regression_at_epoch=15.5,
        mean_argument_latitude_rate_rev_per_day=15.5,
        phase_match_count=0,
        phase_match_weight=0.0,
        mean_motion_first_derivative=0.0,
        mean_motion_first_derivative_raw=0.0,
        semi_major_axis_m=7000000.0,
        dataset_slope_rev_per_day2=0.0,
    )

    params = models.TleParameters.from_estimated(estimated)

    assert params.inclination_deg == 51.6
    assert params.raan_deg == 45.0
    assert params.eccentricity == 0.001


def test_tle_deltas_from_array() -> None:
    """Should create TleDeltas from numpy array."""
    arr = np.array([0.1, 0.2, 0.0001, 0.3, 0.4, 0.01])
    deltas = models.TleDeltas.from_array(arr)

    assert deltas.inclination_deg == pytest.approx(0.1)
    assert deltas.raan_deg == pytest.approx(0.2)
    assert deltas.eccentricity == pytest.approx(0.0001)
    assert deltas.arg_perigee_deg == pytest.approx(0.3)
    assert deltas.mean_anomaly_deg == pytest.approx(0.4)
    assert deltas.mean_motion_rev_per_day == pytest.approx(0.01)


def test_tle_parameters_apply_deltas() -> None:
    """Should apply deltas to TLE parameters."""
    params = models.TleParameters(
        inclination_deg=51.6,
        raan_deg=45.0,
        eccentricity=0.001,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=30.0,
        mean_motion_rev_per_day=15.5,
    )

    deltas = models.TleDeltas(
        inclination_deg=0.1,
        raan_deg=0.2,
        eccentricity=0.0001,
        arg_perigee_deg=0.3,
        mean_anomaly_deg=0.4,
        mean_motion_rev_per_day=0.01,
    )

    new_params = params.apply_deltas(deltas)

    assert new_params.inclination_deg == pytest.approx(51.7)
    assert new_params.raan_deg == pytest.approx(45.2)
    assert new_params.eccentricity == pytest.approx(0.0011)
