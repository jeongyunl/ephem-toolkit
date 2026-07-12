"""Tests for oem_to_tle/tle_builder.py — TLE construction from parameters."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common.tle as tle
import common.consts as consts
import common.oem as oem
import oem_to_tle.oem_to_tle as oem_to_tle
import oem_to_tle.models as models
import oem_to_tle.orbital_mechanics as orbital_mechanics
import oem_to_tle.tle_builder as tle_builder
import oem_to_tle.estimation as estimation

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test files."""

TEST_DATA_DIR: Path = TEST_DIR.parent / "data"
"""Directory containing test data files (OEM, TLE, OMM samples)."""

ISS_OEM_PATH: Path = TEST_DATA_DIR / "ISS_2026-05-20.OEM"
"""Path to ISS OEM test file for 2026-05-20."""

JPSS1_OEM_PATH: Path = TEST_DATA_DIR / "JPSS-1.oem"
"""Path to JPSS-1 OEM test file."""

# ===================================================================
# TLE builder
# ===================================================================


def test_build_tle_data_creates_valid_tle() -> None:
    """Should build valid TLE data structure from estimated elements."""
    content = ISS_OEM_PATH.read_text(encoding="utf-8")
    oem_data = oem.CcsdsOem.read(io.StringIO(content))
    records = oem_data.states
    estimated = estimation.estimate_tle_fields(records, use_state_match=False)

    args = MagicMock()
    args.name = "TEST SAT"
    args.satellite_number = 12345
    args.classification = "U"
    args.int_designator_year = 26
    args.int_designator_launch_number = 100
    args.int_designator_piece = "A"
    args.ephemeris_type = 0
    args.element_set_number = 1
    args.bstar = "00000+0"
    args.mean_motion_second_derivative = "00000+0"
    args.revolution_number_at_epoch = 0

    tle_data = tle_builder.build_tle_data(args, estimated)

    assert isinstance(tle_data, tle.Tle)
    assert tle_data.name == "TEST SAT"
    assert tle_data.satellite_number == 12345
    assert tle_data.classification == "U"
    assert 0 <= tle_data.inclination_deg <= 180
    assert 0 <= tle_data.raan_deg < 360
    assert 0 <= tle_data.eccentricity < 1
    assert 0 <= tle_data.arg_perigee_deg < 360
    assert 0 <= tle_data.mean_anomaly_deg < 360
    assert tle_data.mean_motion_rev_per_day > 0


def test_format_tle_exponential_from_float() -> None:
    """Should format float as TLE exponential notation."""
    # Positive: 0.00012345 = 1.2345e-4 → "12345-3" (TLE uses assumed decimal point)
    result = tle_builder.format_tle_exponential_from_float(0.00012345)
    assert result == "12345-3"

    # Negative: -0.00012345 = -1.2345e-4 → "-12345-3"
    result = tle_builder.format_tle_exponential_from_float(-0.00012345)
    assert result == "-12345-3"

    # Zero: special case → "00000+0"
    result = tle_builder.format_tle_exponential_from_float(0.0)
    assert result == "00000+0"

    # Larger: 0.12345 = 1.2345e-1 → "12345+0"
    result = tle_builder.format_tle_exponential_from_float(0.12345)
    assert result == "12345+0"
