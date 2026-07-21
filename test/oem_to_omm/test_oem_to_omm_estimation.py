"""Tests for oem_to_omm/estimation.py — TLE parameter estimation from OEM data."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from unittest.mock import patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.oem as oem
import oem_to_omm.fit_tle.estimation as estimation
import oem_to_omm.fit_tle.models as models
import oem_to_omm.fit_tle.constants as constants

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parent / "data"
"""Directory containing test data files."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
"""Path to ISS OEM test data file."""

# ===================================================================
# 5. TLE element estimation
# ===================================================================


def test_estimate_tle_fields_returns_estimated_dataclass() -> None:
    """Should return Estimated dataclass with all required fields."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    assert isinstance(estimated, models.Estimated)
    assert isinstance(estimated.epoch_datetime, datetime)
    assert isinstance(estimated.epoch_year, int)
    assert isinstance(estimated.epoch_day, float)
    assert 0 <= estimated.inclination_deg <= 180
    assert 0 <= estimated.raan_deg < 360
    assert 0 <= estimated.eccentricity < 1
    assert 0 <= estimated.arg_perigee_deg < 360
    assert 0 <= estimated.mean_anomaly_deg < 360
    assert estimated.mean_motion_rev_per_day > 0


def test_estimate_tle_fields_produces_reasonable_iss_orbit() -> None:
    """Should produce physically reasonable orbital elements for ISS."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # ISS orbit characteristics: convert semi-major axis from m to km for validation
    semi_major_axis_km = estimated.semi_major_axis_m / 1000.0
    assert 6500.0 < semi_major_axis_km < 7200.0  # Semi-major axis range for ISS
    assert estimated.eccentricity < 0.01  # Nearly circular
    assert 50.0 < estimated.inclination_deg < 52.0  # ISS inclination ~51.6°
    assert 14.0 < estimated.mean_motion_rev_per_day < 16.0  # ~15 orbits/day


def test_estimate_tle_fields_with_state_match_uses_osculating_values() -> None:
    """Should use osculating values as initial guess when use_state_match=True."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

    estimated = estimation.estimate_tle_fields(records, use_state_match=True)

    # With state_match, should use osculating values at epoch
    # These should be close to the osculating_at_epoch fields
    assert abs(estimated.raan_deg - estimated.raan_deg_osculating_at_epoch) < 1.0
    assert (
        abs(estimated.mean_anomaly_deg - estimated.mean_anomaly_deg_osculating_at_epoch)
        < 5.0
    )


def test_estimate_tle_fields_computes_mean_motion_derivative() -> None:
    """Should compute mean motion first derivative from dataset slope."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states

    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # Mean motion derivative should be computed and clamped if necessary
    assert estimated.mean_motion_first_derivative is not None
    assert (
        abs(estimated.mean_motion_first_derivative)
        <= constants.MAX_TLE_MEAN_MOTION_FIRST_DERIVATIVE
    )


# ===================================================================
# 6. B* drag term estimation
# ===================================================================


def test_select_bstar_fit_samples_returns_subset() -> None:
    """Should select evenly spaced samples for B* fitting."""
    # Create dummy records with float timestamps and 6-element state vectors
    base_timestamp = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_timestamp + i * 60.0, np.zeros(6)) for i in range(20)]

    samples = estimation.select_bstar_fit_samples(records)

    assert len(samples) > 0
    assert len(samples) <= constants.BSTAR_SAMPLE_COUNT
    # First record should not be included (epoch is excluded)
    assert samples[0][0] != records[0][0]


def test_select_bstar_fit_samples_handles_small_dataset() -> None:
    """Should handle datasets smaller than BSTAR_SAMPLE_COUNT."""
    base_timestamp = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_timestamp + i * 60.0, np.zeros(6)) for i in range(5)]

    samples = estimation.select_bstar_fit_samples(records)

    # Should return all records except the first (epoch)
    assert len(samples) == 4


def test_select_bstar_fit_samples_returns_empty_for_single_record() -> None:
    """Should return empty list for single record."""
    base_timestamp = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    records = [(base_timestamp, np.zeros(6))]

    samples = estimation.select_bstar_fit_samples(records)

    assert len(samples) == 0


def test_estimate_bstar_preserves_user_provided_value() -> None:
    """Should preserve user-provided B* value without estimation."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    # Create args with custom bstar
    args = MagicMock()
    args.bstar = "12345-3"

    result = estimation.estimate_bstar_from_arc(args, estimated, records)

    assert result.bstar == "12345-3"
    assert result.bstar_source == "input"
