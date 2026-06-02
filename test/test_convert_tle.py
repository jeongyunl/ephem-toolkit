"""Tests for :mod:`common.convert_tle` — TLE ↔ OMM conversion."""

from __future__ import annotations

from pathlib import Path

import pytest

import common.convert_tle as conv
import common.omm as omm
import common.tle as tle

TEST_DIR = Path(__file__).parent

# Test data file paths
ISS_TLE_PATH = TEST_DIR / "ISS-ZARYA_1998-067A.tle"
ISS_OMM_PATH = TEST_DIR / "ISS-ZARYA_1998-067A.omm"
AMOS_TLE_PATH = TEST_DIR / "AMOS-17_2019-050A.tle"
AMOS_OMM_PATH = TEST_DIR / "AMOS-17_2019-050A.omm"
LEO_TLE_PATH = TEST_DIR / "LEO-3_2023-100G.tle"
LEO_OMM_PATH = TEST_DIR / "LEO-3_2023-100G.omm"

TLE_FILES = sorted(TEST_DIR.glob("*.tle"))
OMM_FILES = sorted(TEST_DIR.glob("*.omm"))


# ===================================================================
# 1. TLE → OMM conversion preserves orbital elements (file-based)
# ===================================================================


@pytest.mark.parametrize(
    "tle_path,omm_path",
    [
        (ISS_TLE_PATH, ISS_OMM_PATH),
        (AMOS_TLE_PATH, AMOS_OMM_PATH),
        (LEO_TLE_PATH, LEO_OMM_PATH),
    ],
    ids=["ISS", "AMOS-17", "LEO-3"],
)
def test_tle_to_omm_matches_reference_file(tle_path: Path, omm_path: Path) -> None:
    """Should convert TLE to OMM with orbital elements matching the reference OMM file."""
    with open(tle_path, encoding="utf-8") as fh:
        tle_data = tle.read_tle(fh)

    omm_ref = omm.CcsdsOmm.from_source(omm_path)
    omm_result = conv.tle_to_omm(tle_data)

    assert omm_result.object_name == omm_ref.object_name
    assert omm_result.object_id == omm_ref.object_id
    assert omm_result.epoch == omm_ref.epoch
    assert omm_result.mean_motion == pytest.approx(omm_ref.mean_motion, abs=1e-8)
    assert omm_result.eccentricity == pytest.approx(omm_ref.eccentricity, abs=1e-7)
    assert omm_result.inclination == pytest.approx(omm_ref.inclination, abs=1e-4)
    assert omm_result.ra_of_asc_node == pytest.approx(omm_ref.ra_of_asc_node, abs=1e-4)
    assert omm_result.arg_of_pericenter == pytest.approx(omm_ref.arg_of_pericenter, abs=1e-4)
    assert omm_result.mean_anomaly == pytest.approx(omm_ref.mean_anomaly, abs=1e-4)
    assert omm_result.norad_cat_id == omm_ref.norad_cat_id
    assert omm_result.rev_at_epoch == omm_ref.rev_at_epoch
    assert omm_result.classification_type == omm_ref.classification_type
    assert omm_result.element_set_no == omm_ref.element_set_no


# ===================================================================
# 2. OMM → TLE conversion preserves orbital elements (file-based)
# ===================================================================


@pytest.mark.parametrize(
    "tle_path,omm_path",
    [
        (ISS_TLE_PATH, ISS_OMM_PATH),
        (AMOS_TLE_PATH, AMOS_OMM_PATH),
        (LEO_TLE_PATH, LEO_OMM_PATH),
    ],
    ids=["ISS", "AMOS-17", "LEO-3"],
)
def test_omm_to_tle_matches_reference_file(tle_path: Path, omm_path: Path) -> None:
    """Should convert OMM to TLE with orbital elements matching the reference TLE file."""
    omm_data = omm.CcsdsOmm.from_source(omm_path)

    with open(tle_path, encoding="utf-8") as fh:
        tle_ref = tle.read_tle(fh)

    tle_result = conv.omm_to_tle(omm_data)

    assert tle_result.name == tle_ref.name
    assert tle_result.satellite_number == tle_ref.satellite_number
    assert tle_result.classification == tle_ref.classification
    assert tle_result.int_designator_year == tle_ref.int_designator_year
    assert tle_result.int_designator_launch_number == tle_ref.int_designator_launch_number
    assert tle_result.int_designator_piece == tle_ref.int_designator_piece
    assert tle_result.epoch_year == tle_ref.epoch_year
    assert tle_result.epoch_day == pytest.approx(tle_ref.epoch_day, abs=1e-6)
    assert tle_result.inclination_deg == pytest.approx(tle_ref.inclination_deg, abs=1e-4)
    assert tle_result.raan_deg == pytest.approx(tle_ref.raan_deg, abs=1e-4)
    assert tle_result.eccentricity == pytest.approx(tle_ref.eccentricity, abs=1e-7)
    assert tle_result.arg_perigee_deg == pytest.approx(tle_ref.arg_perigee_deg, abs=1e-4)
    assert tle_result.mean_anomaly_deg == pytest.approx(tle_ref.mean_anomaly_deg, abs=1e-4)
    assert tle_result.mean_motion_rev_per_day == pytest.approx(
        tle_ref.mean_motion_rev_per_day, abs=1e-8
    )
    assert tle_result.revolution_number_at_epoch == tle_ref.revolution_number_at_epoch


# ===================================================================
# 3. TLE → OMM → TLE round-trip preserves all elements (file-based)
# ===================================================================


@pytest.mark.parametrize("tle_path", TLE_FILES, ids=[p.name for p in TLE_FILES])
def test_tle_to_omm_to_tle_round_trip(tle_path: Path) -> None:
    """Should preserve all orbital elements through a TLE → OMM → TLE round-trip."""
    with open(tle_path, encoding="utf-8") as fh:
        tle_original = tle.read_tle(fh)

    omm_converted = conv.tle_to_omm(tle_original)
    tle_recovered = conv.omm_to_tle(omm_converted)

    assert tle_recovered.satellite_number == tle_original.satellite_number
    assert tle_recovered.classification == tle_original.classification
    assert tle_recovered.int_designator_year == tle_original.int_designator_year
    assert tle_recovered.int_designator_launch_number == tle_original.int_designator_launch_number
    assert tle_recovered.int_designator_piece == tle_original.int_designator_piece
    assert tle_recovered.epoch_year == tle_original.epoch_year
    assert tle_recovered.epoch_day == pytest.approx(tle_original.epoch_day, abs=1e-6)
    assert tle_recovered.mean_motion_first_derivative == pytest.approx(
        tle_original.mean_motion_first_derivative, abs=1e-10
    )
    assert tle_recovered.inclination_deg == pytest.approx(tle_original.inclination_deg, abs=1e-4)
    assert tle_recovered.raan_deg == pytest.approx(tle_original.raan_deg, abs=1e-4)
    assert tle_recovered.eccentricity == pytest.approx(tle_original.eccentricity, abs=1e-7)
    assert tle_recovered.arg_perigee_deg == pytest.approx(tle_original.arg_perigee_deg, abs=1e-4)
    assert tle_recovered.mean_anomaly_deg == pytest.approx(tle_original.mean_anomaly_deg, abs=1e-4)
    assert tle_recovered.mean_motion_rev_per_day == pytest.approx(
        tle_original.mean_motion_rev_per_day, abs=1e-8
    )
    assert tle_recovered.revolution_number_at_epoch == tle_original.revolution_number_at_epoch


# ===================================================================
# 4. OMM → TLE → OMM round-trip preserves all elements (file-based)
# ===================================================================


@pytest.mark.parametrize("omm_path", OMM_FILES, ids=[p.name for p in OMM_FILES])
def test_omm_to_tle_to_omm_round_trip(omm_path: Path) -> None:
    """Should preserve all orbital elements through an OMM → TLE → OMM round-trip."""
    omm_original = omm.CcsdsOmm.from_source(omm_path)

    tle_converted = conv.omm_to_tle(omm_original)
    omm_recovered = conv.tle_to_omm(tle_converted)

    assert omm_recovered.object_name == omm_original.object_name
    assert omm_recovered.object_id == omm_original.object_id
    assert omm_recovered.epoch == omm_original.epoch
    assert omm_recovered.mean_motion == pytest.approx(omm_original.mean_motion, abs=1e-8)
    assert omm_recovered.eccentricity == pytest.approx(omm_original.eccentricity, abs=1e-7)
    assert omm_recovered.inclination == pytest.approx(omm_original.inclination, abs=1e-4)
    assert omm_recovered.ra_of_asc_node == pytest.approx(omm_original.ra_of_asc_node, abs=1e-4)
    assert omm_recovered.arg_of_pericenter == pytest.approx(
        omm_original.arg_of_pericenter, abs=1e-4
    )
    assert omm_recovered.mean_anomaly == pytest.approx(omm_original.mean_anomaly, abs=1e-4)
    assert omm_recovered.norad_cat_id == omm_original.norad_cat_id
    assert omm_recovered.rev_at_epoch == omm_original.rev_at_epoch
    assert omm_recovered.classification_type == omm_original.classification_type


# ===================================================================
# 5. Epoch conversion helpers produce correct ISO 8601 strings
# ===================================================================


def test_epoch_to_iso8601_iss() -> None:
    """Should convert ISS TLE epoch to the expected ISO 8601 datetime string."""
    # ISS epoch: year=26, day=152.32329980
    result = conv._epoch_to_iso8601(26, 152.32329980)
    assert result == "2026-06-01T07:45:33.102720"


def test_epoch_to_iso8601_handles_year_boundary() -> None:
    """Should correctly resolve 2-digit years across the 57/00 boundary."""
    # Year 99 → 1999
    result_99 = conv._epoch_to_iso8601(99, 1.0)
    assert result_99.startswith("1999-01-01")

    # Year 0 → 2000
    result_00 = conv._epoch_to_iso8601(0, 1.0)
    assert result_00.startswith("2000-01-01")

    # Year 56 → 2056
    result_56 = conv._epoch_to_iso8601(56, 1.0)
    assert result_56.startswith("2056-01-01")

    # Year 57 → 1957
    result_57 = conv._epoch_to_iso8601(57, 1.0)
    assert result_57.startswith("1957-01-01")


def test_iso8601_to_epoch_round_trip() -> None:
    """Should round-trip ISO 8601 ↔ TLE epoch without loss of precision."""
    original_year = 26
    original_day = 152.32329980

    iso_str = conv._epoch_to_iso8601(original_year, original_day)
    recovered_year, recovered_day = conv._iso8601_to_epoch(iso_str)

    assert recovered_year == original_year
    assert recovered_day == pytest.approx(original_day, abs=1e-6)
