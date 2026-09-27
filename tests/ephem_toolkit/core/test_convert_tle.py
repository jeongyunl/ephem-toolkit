"""Tests for core/convert_tle.py — TLE ↔ OMM conversion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import core.convert_tle as conv
import core.ccsds.omm as omm
import core.tle as tle

TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = TEST_DIR.parent.parent / "data"

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
def test_tle_to_omm_matches_reference_file(
    tle_path: Path, omm_path: Path, tmp_path: Path
) -> None:
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
    assert omm_result.tle_parameters.norad_cat_id == omm_ref.tle_parameters.norad_cat_id
    assert omm_result.tle_parameters.rev_at_epoch == omm_ref.tle_parameters.rev_at_epoch
    assert (
        omm_result.tle_parameters.classification_type
        == omm_ref.tle_parameters.classification_type
    )
    assert (
        omm_result.tle_parameters.element_set_no
        == omm_ref.tle_parameters.element_set_no
    )

    output_path = tmp_path / "converted.omm"
    omm_result.to_file(output_path)
    serialized_omm = omm.CcsdsOmm.from_source(output_path)
    assert serialized_omm.object_name == omm_result.object_name
    assert serialized_omm.object_id == omm_result.object_id
    assert serialized_omm.epoch == omm_result.epoch
    assert serialized_omm.mean_motion == pytest.approx(omm_result.mean_motion)
    assert serialized_omm.eccentricity == pytest.approx(omm_result.eccentricity)
    assert serialized_omm.inclination == pytest.approx(omm_result.inclination)
    assert serialized_omm.ra_of_asc_node == pytest.approx(omm_result.ra_of_asc_node)
    assert serialized_omm.arg_of_pericenter == pytest.approx(
        omm_result.arg_of_pericenter
    )
    assert serialized_omm.mean_anomaly == pytest.approx(omm_result.mean_anomaly)
    assert serialized_omm.center_name == "EARTH"
    assert serialized_omm.ref_frame == "TEME"
    assert serialized_omm.time_system == "UTC"
    assert serialized_omm.mean_element_theory == "SGP/SGP4"
    assert serialized_omm.comments == []
    assert serialized_omm.creation_date == ""
    assert serialized_omm.originator == ""
    assert serialized_omm.tle_parameters.ephemeris_type == (
        omm_result.tle_parameters.ephemeris_type
    )
    assert serialized_omm.tle_parameters.classification_type == (
        omm_result.tle_parameters.classification_type
    )
    assert serialized_omm.tle_parameters.norad_cat_id == (
        omm_result.tle_parameters.norad_cat_id
    )
    assert serialized_omm.tle_parameters.element_set_no == (
        omm_result.tle_parameters.element_set_no
    )
    assert serialized_omm.tle_parameters.rev_at_epoch == (
        omm_result.tle_parameters.rev_at_epoch
    )
    for field in ("bstar", "mean_motion_dot", "mean_motion_ddot"):
        assert conv._omm_scientific_to_float(
            getattr(serialized_omm.tle_parameters, field)
        ) == pytest.approx(
            conv._omm_scientific_to_float(getattr(omm_result.tle_parameters, field))
        )


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
def test_omm_to_tle_matches_reference_file(
    tle_path: Path, omm_path: Path, tmp_path: Path
) -> None:
    """Should convert OMM to TLE with orbital elements matching the reference TLE file."""
    source_omm = omm.CcsdsOmm.from_source(omm_path)
    source_omm.message_id = "SOURCE-MESSAGE-42"
    source_omm.ref_frame_epoch = "2026-06-01T07:45:33.102720"
    source_omm.comments.append("SOURCE_COMMENT: OMM-only metadata")
    source_omm.spacecraft_parameters = omm.OmmSpacecraftParameters(
        mass=420.0, drag_area=12.0, drag_coeff=2.2
    )
    source_omm.covariance = omm.OmmCovariance(np.eye(6), ref_frame="TEME")
    source_omm.data["USER_DEFINED_AUDIT"] = "OMM-only value"
    source_path = tmp_path / "metadata-source.omm"
    source_omm.to_file(source_path)
    omm_data = omm.CcsdsOmm.from_source(source_path)

    with open(tle_path, encoding="utf-8") as fh:
        tle_ref = tle.read_tle(fh)

    tle_result = conv.omm_to_tle(omm_data)

    assert tle_result.object_name == tle_ref.object_name
    assert tle_result.norad_cat_id == tle_ref.norad_cat_id
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

    output_path = tmp_path / "converted.tle"
    tle.write_tle(output_path, tle_result)
    serialized_tle = output_path.read_text(encoding="utf-8")
    with output_path.open(encoding="utf-8") as tle_file:
        serialized_tle_data = tle.read_tle(tle_file)
    assert serialized_tle_data.object_name == omm_data.object_name
    assert serialized_tle_data.get_object_id() == omm_data.object_id
    assert serialized_tle_data.epoch_year == tle_result.epoch_year
    assert serialized_tle_data.epoch_day == pytest.approx(tle_result.epoch_day)
    assert serialized_tle_data.norad_cat_id == omm_data.tle_parameters.norad_cat_id
    assert (
        serialized_tle_data.classification
        == omm_data.tle_parameters.classification_type
    )
    assert (
        serialized_tle_data.element_set_number == omm_data.tle_parameters.element_set_no
    )
    assert (
        serialized_tle_data.revolution_number_at_epoch
        == omm_data.tle_parameters.rev_at_epoch
    )
    assert serialized_tle_data.bstar == tle_result.bstar
    assert serialized_tle_data.mean_motion_first_derivative == pytest.approx(
        tle_result.mean_motion_first_derivative
    )
    assert serialized_tle_data.mean_motion_second_derivative == (
        tle_result.mean_motion_second_derivative
    )
    assert serialized_tle_data.mean_motion_rev_per_day == pytest.approx(
        tle_result.mean_motion_rev_per_day
    )
    assert (
        serialized_tle_data.line1_checksum
        == serialized_tle_data.line1_checksum_expected
    )
    assert (
        serialized_tle_data.line2_checksum
        == serialized_tle_data.line2_checksum_expected
    )
    assert "SOURCE-MESSAGE-42" not in serialized_tle
    assert "SOURCE_COMMENT: OMM-only metadata" not in serialized_tle
    for field in (
        "CREATION_DATE",
        "ORIGINATOR",
        "CLASSIFICATION",
        "REF_FRAME_EPOCH",
        "MASS",
        "SOLAR_RAD_AREA",
        "SOLAR_RAD_COEFF",
        "DRAG_AREA",
        "DRAG_COEFF",
    ):
        assert field not in serialized_tle
    assert "COV_REF_FRAME" not in serialized_tle
    assert "USER_DEFINED_AUDIT" not in serialized_tle
    assert "MASS" not in serialized_tle


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

    assert tle_recovered.norad_cat_id == tle_original.norad_cat_id
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
    assert (
        omm_recovered.tle_parameters.norad_cat_id
        == omm_original.tle_parameters.norad_cat_id
    )
    assert (
        omm_recovered.tle_parameters.rev_at_epoch
        == omm_original.tle_parameters.rev_at_epoch
    )
    assert (
        omm_recovered.tle_parameters.classification_type
        == omm_original.tle_parameters.classification_type
    )


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


def test_parse_object_id_rejects_non_tle_year_and_suffix() -> None:
    """Should reject placeholders and malformed suffixes."""
    assert conv._parse_object_id("9999-999-A") == (0, 0, "")
    assert conv._parse_object_id("1998-067A-extra") == (0, 0, "")
