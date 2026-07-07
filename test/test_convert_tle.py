"""Tests for :mod:`common.convert_tle` — TLE ↔ OMM conversion."""

from __future__ import annotations

from pathlib import Path

import pytest

import common.convert_tle as conv
import common.omm as omm
import common.tle as tle

TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = TEST_DIR / "data"

# Test data file paths
ISS_TLE_PATH = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.tle"
ISS_OMM_PATH = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.omm"
AMOS_TLE_PATH = TEST_DATA_DIR / "AMOS-17_2019-050A.tle"
AMOS_OMM_PATH = TEST_DATA_DIR / "AMOS-17_2019-050A.omm"
LEO_TLE_PATH = TEST_DATA_DIR / "LEO-3_2023-100G.tle"
LEO_OMM_PATH = TEST_DATA_DIR / "LEO-3_2023-100G.omm"

TLE_FILES = sorted(TEST_DATA_DIR.glob("*.tle"))
OMM_FILES = sorted(TEST_DATA_DIR.glob("*.omm"))


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
    assert omm_result.arg_of_pericenter == pytest.approx(
        omm_ref.arg_of_pericenter, abs=1e-4
    )
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
    assert (
        tle_result.int_designator_launch_number == tle_ref.int_designator_launch_number
    )
    assert tle_result.int_designator_piece == tle_ref.int_designator_piece
    assert tle_result.epoch_year == tle_ref.epoch_year
    assert tle_result.epoch_day == pytest.approx(tle_ref.epoch_day, abs=1e-6)
    assert tle_result.inclination_deg == pytest.approx(
        tle_ref.inclination_deg, abs=1e-4
    )
    assert tle_result.raan_deg == pytest.approx(tle_ref.raan_deg, abs=1e-4)
    assert tle_result.eccentricity == pytest.approx(tle_ref.eccentricity, abs=1e-7)
    assert tle_result.arg_perigee_deg == pytest.approx(
        tle_ref.arg_perigee_deg, abs=1e-4
    )
    assert tle_result.mean_anomaly_deg == pytest.approx(
        tle_ref.mean_anomaly_deg, abs=1e-4
    )
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
    assert (
        tle_recovered.int_designator_launch_number
        == tle_original.int_designator_launch_number
    )
    assert tle_recovered.int_designator_piece == tle_original.int_designator_piece
    assert tle_recovered.epoch_year == tle_original.epoch_year
    assert tle_recovered.epoch_day == pytest.approx(tle_original.epoch_day, abs=1e-6)
    assert tle_recovered.mean_motion_first_derivative == pytest.approx(
        tle_original.mean_motion_first_derivative, abs=1e-10
    )
    assert tle_recovered.inclination_deg == pytest.approx(
        tle_original.inclination_deg, abs=1e-4
    )
    assert tle_recovered.raan_deg == pytest.approx(tle_original.raan_deg, abs=1e-4)
    assert tle_recovered.eccentricity == pytest.approx(
        tle_original.eccentricity, abs=1e-7
    )
    assert tle_recovered.arg_perigee_deg == pytest.approx(
        tle_original.arg_perigee_deg, abs=1e-4
    )
    assert tle_recovered.mean_anomaly_deg == pytest.approx(
        tle_original.mean_anomaly_deg, abs=1e-4
    )
    assert tle_recovered.mean_motion_rev_per_day == pytest.approx(
        tle_original.mean_motion_rev_per_day, abs=1e-8
    )
    assert (
        tle_recovered.revolution_number_at_epoch
        == tle_original.revolution_number_at_epoch
    )


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
    assert omm_recovered.mean_motion == pytest.approx(
        omm_original.mean_motion, abs=1e-8
    )
    assert omm_recovered.eccentricity == pytest.approx(
        omm_original.eccentricity, abs=1e-7
    )
    assert omm_recovered.inclination == pytest.approx(
        omm_original.inclination, abs=1e-4
    )
    assert omm_recovered.ra_of_asc_node == pytest.approx(
        omm_original.ra_of_asc_node, abs=1e-4
    )
    assert omm_recovered.arg_of_pericenter == pytest.approx(
        omm_original.arg_of_pericenter, abs=1e-4
    )
    assert omm_recovered.mean_anomaly == pytest.approx(
        omm_original.mean_anomaly, abs=1e-4
    )
    assert omm_recovered.norad_cat_id == omm_original.norad_cat_id
    assert omm_recovered.rev_at_epoch == omm_original.rev_at_epoch
    assert omm_recovered.classification_type == omm_original.classification_type


# ===================================================================
# 6. Exponential notation conversion helpers — TLE ↔ float
# ===================================================================


def test_tle_exponential_to_float_positive() -> None:
    """Should convert positive TLE exponential notation to float."""
    result = conv._tle_exponential_to_float("17978-3")
    assert result == pytest.approx(0.17978e-3, rel=1e-10)


def test_tle_exponential_to_float_negative() -> None:
    """Should convert negative TLE exponential notation to float."""
    result = conv._tle_exponential_to_float("-12345-6")
    assert result == pytest.approx(-0.12345e-6, rel=1e-10)


def test_tle_exponential_to_float_zero() -> None:
    """Should handle zero values in TLE exponential notation."""
    assert conv._tle_exponential_to_float("00000+0") == 0.0
    assert conv._tle_exponential_to_float("00000-0") == 0.0


def test_float_to_tle_exponential_round_trip() -> None:
    """Should round-trip float ↔ TLE exponential notation."""
    original = 0.17978e-3
    tle_exp = conv._float_to_tle_exponential(original)
    recovered = conv._tle_exponential_to_float(tle_exp)
    assert recovered == pytest.approx(original, rel=1e-5)


def test_float_to_tle_exponential_zero() -> None:
    """Should convert zero to TLE exponential notation."""
    result = conv._float_to_tle_exponential(0.0)
    assert result == "00000+0"


# ===================================================================
# 7. OMM scientific notation conversion helpers — float ↔ OMM
# ===================================================================


def test_float_to_omm_scientific_positive() -> None:
    """Should convert positive float to OMM scientific notation."""
    result = conv._float_to_omm_scientific(0.17978e-3)
    assert "E" in result or "e" in result.upper()


def test_float_to_omm_scientific_zero() -> None:
    """Should convert zero to OMM scientific notation."""
    result = conv._float_to_omm_scientific(0.0)
    assert result == "0"


def test_omm_scientific_to_float_positive() -> None:
    """Should convert OMM scientific notation to float."""
    result = conv._omm_scientific_to_float(".1797805E-3")
    assert result == pytest.approx(0.1797805e-3, rel=1e-10)


def test_omm_scientific_to_float_negative() -> None:
    """Should convert negative OMM scientific notation to float."""
    result = conv._omm_scientific_to_float("-.25E-6")
    assert result == pytest.approx(-0.25e-6, rel=1e-10)


def test_omm_scientific_to_float_zero() -> None:
    """Should handle zero in OMM scientific notation."""
    assert conv._omm_scientific_to_float("0") == 0.0
    assert conv._omm_scientific_to_float("") == 0.0


# ===================================================================
# 8. Object ID conversion helpers — COSPAR ↔ TLE designator
# ===================================================================


def test_build_object_id() -> None:
    """Should build COSPAR Object ID from TLE designator components."""
    result = conv._build_object_id(98, 67, "A")
    assert result == "1998-067A"


def test_parse_object_id() -> None:
    """Should parse COSPAR Object ID into TLE designator components."""
    year, launch, piece = conv._parse_object_id("1998-067A")
    assert year == 98
    assert launch == 67
    assert piece == "A"


def test_parse_object_id_invalid() -> None:
    """Should return zeros for invalid Object ID."""
    year, launch, piece = conv._parse_object_id("invalid")
    assert year == 0
    assert launch == 0
    assert piece == ""
