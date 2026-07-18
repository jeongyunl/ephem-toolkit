"""Tests for common.omm.py — OMM parsing, writing, and class API."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import common.omm as omm

TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = TEST_DIR.parent / "data"
ISS_OMM_PATH = TEST_DATA_DIR / "ISS-ZARYA_1998-067A.omm"
AMOS_OMM_PATH = TEST_DATA_DIR / "AMOS-17_2019-050A.omm"
LEO_OMM_PATH = TEST_DATA_DIR / "LEO-3_2023-100G.omm"

OMM_FILES = sorted(TEST_DATA_DIR.glob("*.omm"))


# ===================================================================
# 1. Read OMM test file and verify header/data separation
# ===================================================================


def test_read_omm_from_file_returns_header_and_data() -> None:
    """Should parse the sample OMM file into header and data dicts."""
    header, data = omm.read_omm(ISS_OMM_PATH)

    assert isinstance(header, dict)
    assert isinstance(data, dict)
    assert header["CCSDS_OMM_VERS"] == pytest.approx(2.0)
    assert "CREATION_DATE" in header
    assert "ORIGINATOR" in header
    assert data["OBJECT_NAME"] == "ISS (ZARYA)"
    assert data["OBJECT_ID"] == "1998-067A"
    assert data["CENTER_NAME"] == "EARTH"
    assert data["REF_FRAME"] == "TEME"
    assert data["TIME_SYSTEM"] == "UTC"
    assert data["MEAN_ELEMENT_THEORY"] == "SGP/SGP4"


# ===================================================================
# 2. Read OMM from stream matches file read
# ===================================================================


def test_read_omm_from_stream_matches_file_read() -> None:
    """Should produce identical parsed content from a text stream."""
    text = ISS_OMM_PATH.read_text(encoding="utf-8")

    header1, data1 = omm.read_omm(ISS_OMM_PATH)
    header2, data2 = omm.read_omm(io.StringIO(text))

    assert header2 == header1
    assert data2 == data1


# ===================================================================
# 3. Read OMM correctly parses mean Keplerian elements
# ===================================================================


def test_read_omm_parses_mean_elements() -> None:
    """Should correctly parse mean Keplerian elements as numeric values."""
    _, data = omm.read_omm(ISS_OMM_PATH)

    assert data["EPOCH"] == "2026-06-01T07:45:33.102720"
    assert data["MEAN_MOTION"] == pytest.approx(15.49538094, abs=1e-8)
    assert data["ECCENTRICITY"] == pytest.approx(0.00072029, abs=1e-8)
    assert data["INCLINATION"] == pytest.approx(51.6335, abs=1e-4)
    assert data["RA_OF_ASC_NODE"] == pytest.approx(18.6331, abs=1e-4)
    assert data["ARG_OF_PERICENTER"] == pytest.approx(121.2251, abs=1e-4)
    assert data["MEAN_ANOMALY"] == pytest.approx(238.9444, abs=1e-4)


# ===================================================================
# 4. Read OMM correctly parses TLE-related parameters
# ===================================================================


def test_read_omm_parses_tle_parameters() -> None:
    """Should correctly parse TLE-related parameters."""
    _, data = omm.read_omm(ISS_OMM_PATH)

    assert data["EPHEMERIS_TYPE"] == 0
    assert data["CLASSIFICATION_TYPE"] == "U"
    assert data["NORAD_CAT_ID"] == 25544
    assert data["ELEMENT_SET_NO"] == 999
    assert data["REV_AT_EPOCH"] == 56929
    assert data["MEAN_MOTION_DDOT"] == 0


# ===================================================================
# 5. Write/read round-trip with low-level API
# ===================================================================


@pytest.mark.parametrize("omm_path", OMM_FILES, ids=[p.name for p in OMM_FILES])
def test_write_omm_round_trip_preserves_content(tmp_path: Path, omm_path: Path) -> None:
    """Should preserve header and data through write/read round-trip."""
    header1, data1 = omm.read_omm(omm_path)
    out_path = tmp_path / "roundtrip.omm"

    omm.write_omm(out_path, header1, data1)
    header2, data2 = omm.read_omm(out_path)

    # Header version should match
    assert header2.get("CCSDS_OMM_VERS") == header1.get("CCSDS_OMM_VERS")

    # All data keys should be preserved
    for key in data1:
        assert key in data2, f"Missing key: {key}"
        if isinstance(data1[key], float):
            assert data2[key] == pytest.approx(data1[key], abs=1e-10)
        else:
            assert (
                data2[key] == data1[key]
            ), f"Mismatch for {key}: {data2[key]} != {data1[key]}"


# ===================================================================
# 6. CcsdsOmm structured class from source
# ===================================================================


def test_ccsds_omm_from_source_exposes_structured_fields() -> None:
    """Should load the sample OMM into the structured class representation."""
    ccsds_omm = omm.CcsdsOmm.from_source(ISS_OMM_PATH)

    assert isinstance(ccsds_omm, omm.CcsdsOmm)
    assert ccsds_omm.version == pytest.approx(2.0)
    assert ccsds_omm.object_name == "ISS (ZARYA)"
    assert ccsds_omm.object_id == "1998-067A"
    assert ccsds_omm.center_name == "EARTH"
    assert ccsds_omm.ref_frame == "TEME"
    assert ccsds_omm.time_system == "UTC"
    assert ccsds_omm.mean_element_theory == "SGP/SGP4"
    assert ccsds_omm.epoch == "2026-06-01T07:45:33.102720"
    assert ccsds_omm.mean_motion == pytest.approx(15.49538094, abs=1e-8)
    assert ccsds_omm.eccentricity == pytest.approx(0.00072029, abs=1e-8)
    assert ccsds_omm.inclination == pytest.approx(51.6335, abs=1e-4)
    assert ccsds_omm.ra_of_asc_node == pytest.approx(18.6331, abs=1e-4)
    assert ccsds_omm.arg_of_pericenter == pytest.approx(121.2251, abs=1e-4)
    assert ccsds_omm.mean_anomaly == pytest.approx(238.9444, abs=1e-4)
    assert ccsds_omm.tle_parameters is not None
    assert ccsds_omm.tle_parameters.norad_cat_id == 25544
    assert ccsds_omm.tle_parameters.classification_type == "U"


# ===================================================================
# 7. CcsdsOmm to_file round-trip preserves structured content
# ===================================================================


def test_ccsds_omm_to_file_round_trip(tmp_path: Path) -> None:
    """Should preserve structured OMM content through class-based serialization."""
    omm1 = omm.CcsdsOmm.from_source(ISS_OMM_PATH)
    out_path = tmp_path / "class_roundtrip.omm"

    omm1.to_file(out_path)
    omm2 = omm.CcsdsOmm.from_source(out_path)

    assert omm2.object_name == omm1.object_name
    assert omm2.object_id == omm1.object_id
    assert omm2.epoch == omm1.epoch
    assert omm2.mean_motion == pytest.approx(omm1.mean_motion, abs=1e-10)
    assert omm2.eccentricity == pytest.approx(omm1.eccentricity, abs=1e-10)
    assert omm2.inclination == pytest.approx(omm1.inclination, abs=1e-10)
    assert omm2.ra_of_asc_node == pytest.approx(omm1.ra_of_asc_node, abs=1e-10)
    assert omm2.arg_of_pericenter == pytest.approx(omm1.arg_of_pericenter, abs=1e-10)
    assert omm2.mean_anomaly == pytest.approx(omm1.mean_anomaly, abs=1e-10)
    assert omm2.tle_parameters is not None
    assert omm1.tle_parameters is not None
    assert omm2.tle_parameters.norad_cat_id == omm1.tle_parameters.norad_cat_id
    assert omm2.tle_parameters.rev_at_epoch == omm1.tle_parameters.rev_at_epoch
    assert omm2.tle_parameters.bstar == omm1.tle_parameters.bstar
    assert omm2.tle_parameters.mean_motion_dot == omm1.tle_parameters.mean_motion_dot
    assert omm2.tle_parameters.mean_motion_ddot == omm1.tle_parameters.mean_motion_ddot


# ===================================================================
# 8. CcsdsOmm __repr__ contains summary information
# ===================================================================


def test_ccsds_omm_repr_contains_summary_information() -> None:
    """Should include object name, NORAD ID, and epoch in repr output."""
    ccsds_omm = omm.CcsdsOmm.from_source(ISS_OMM_PATH)
    text = repr(ccsds_omm)

    assert "CcsdsOmm" in text
    assert ccsds_omm.object_name in text
    assert ccsds_omm.tle_parameters is not None
    assert str(ccsds_omm.tle_parameters.norad_cat_id) in text
    assert ccsds_omm.epoch in text


# ===================================================================
# 9. CcsdsOmm to_dict returns plain dictionary
# ===================================================================


def test_ccsds_omm_to_dict() -> None:
    """Should convert to a plain dictionary with all fields."""
    ccsds_omm = omm.CcsdsOmm.from_source(ISS_OMM_PATH)
    d = ccsds_omm.to_dict()

    assert isinstance(d, dict)
    assert d["object_name"] == "ISS (ZARYA)"
    assert d["tle_parameters"] is not None
    assert isinstance(d["tle_parameters"], dict)
    assert d["tle_parameters"]["norad_cat_id"] == 25544
    assert d["mean_motion"] == pytest.approx(15.49538094, abs=1e-8)
    assert d["eccentricity"] == pytest.approx(0.00072029, abs=1e-8)


# ===================================================================
# 10. Write OMM to stream (StringIO)
# ===================================================================


def test_write_omm_to_stream() -> None:
    """Should write OMM content to a StringIO stream."""
    header, data = omm.read_omm(ISS_OMM_PATH)
    buf = io.StringIO()

    omm.write_omm(buf, header, data)
    output = buf.getvalue()

    assert "CCSDS_OMM_VERS" in output
    assert "OBJECT_NAME" in output
    assert "ISS (ZARYA)" in output
    assert "EPOCH" in output
    assert "MEAN_MOTION" in output
    assert "NORAD_CAT_ID" in output


# ===================================================================
# 11. Read OMM handles COMMENT lines
# ===================================================================


def test_read_omm_handles_comment_lines() -> None:
    """Should parse COMMENT lines into the header dict."""
    omm_text = """\
CCSDS_OMM_VERS = 2.0
COMMENT This is a test comment
COMMENT Another comment
CREATION_DATE  = 2026-06-01
ORIGINATOR     = TEST

OBJECT_NAME    = TEST-SAT
OBJECT_ID      = 2020-001A
CENTER_NAME    = EARTH
REF_FRAME      = TEME
TIME_SYSTEM    = UTC
MEAN_ELEMENT_THEORY = SGP/SGP4

EPOCH          = 2026-06-01T00:00:00.000000
MEAN_MOTION    = 15.0
ECCENTRICITY   = .001
INCLINATION    = 51.0
RA_OF_ASC_NODE = 100.0
ARG_OF_PERICENTER = 200.0
MEAN_ANOMALY   = 300.0

EPHEMERIS_TYPE = 0
CLASSIFICATION_TYPE = U
NORAD_CAT_ID   = 99999
ELEMENT_SET_NO = 999
REV_AT_EPOCH   = 100
BSTAR          = 0
MEAN_MOTION_DOT = 0
MEAN_MOTION_DDOT = 0
"""
    header, data = omm.read_omm(io.StringIO(omm_text))

    assert "COMMENT" in header
    assert len(header["COMMENT"]) == 2
    assert header["COMMENT"][0] == "This is a test comment"
    assert header["COMMENT"][1] == "Another comment"


# ===================================================================
# 12. CcsdsOmm without TLE parameters (non-SGP4 theories)
# ===================================================================


def test_ccsds_omm_without_tle_parameters() -> None:
    """Should handle OMM files without TLE-related parameters."""
    omm_text = """\
CCSDS_OMM_VERS = 3.0
CREATION_DATE  = 2026-06-01T00:00:00.000Z
ORIGINATOR     = TEST

OBJECT_NAME    = TEST-SAT
OBJECT_ID      = 2020-001A
CENTER_NAME    = EARTH
REF_FRAME      = ICRF
TIME_SYSTEM    = UTC
MEAN_ELEMENT_THEORY = DSST

EPOCH          = 2026-06-01T00:00:00.000000
MEAN_MOTION    = 15.0
ECCENTRICITY   = 0.001
INCLINATION    = 51.0
RA_OF_ASC_NODE = 100.0
ARG_OF_PERICENTER = 200.0
MEAN_ANOMALY   = 300.0
"""
    ccsds_omm = omm.CcsdsOmm.from_source(io.StringIO(omm_text))

    assert ccsds_omm.object_name == "TEST-SAT"
    assert ccsds_omm.mean_element_theory == "DSST"
    assert ccsds_omm.ref_frame == "ICRF"
    assert ccsds_omm.tle_parameters is None


# ===================================================================
# 13. keplerian_to_omm conversion function
# ===================================================================


def test_keplerian_to_omm() -> None:
    """Should convert Keplerian elements to OMM format."""
    import numpy as np
    from datetime import datetime, timezone

    # Define test Keplerian elements (ISS-like orbit)
    # [a, e, i, omega, RAAN, theta] in SI units (m, rad)
    keplerian_elements = np.array(
        [
            6778137.0,  # semi-major axis (m) - ~400 km altitude
            0.0007,  # eccentricity
            np.radians(51.6),  # inclination (rad)
            np.radians(120.0),  # argument of periapsis (rad)
            np.radians(20.0),  # RAAN (rad)
            np.radians(240.0),  # true anomaly (rad)
        ]
    )

    epoch = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    omm_obj = omm.keplerian_to_omm(
        epoch=epoch,
        keplerian_elements=keplerian_elements,
        object_name="TEST-SAT",
        object_id="2020-001A",
    )

    assert isinstance(omm_obj, omm.CcsdsOmm)
    assert omm_obj.object_name == "TEST-SAT"
    assert omm_obj.object_id == "2020-001A"
    assert omm_obj.center_name == "EARTH"
    assert omm_obj.ref_frame == "ICRF"
    assert omm_obj.time_system == "UTC"
    assert omm_obj.mean_element_theory == "DSST"
    assert omm_obj.version == 3.0
    assert omm_obj.originator == "tudatpy-utils"

    # Check that mean motion is reasonable for ISS-like orbit (~15.5 rev/day)
    assert 15.0 < omm_obj.mean_motion < 16.0

    # Check that angles are in degrees
    assert omm_obj.eccentricity == pytest.approx(0.0007, abs=1e-6)
    assert omm_obj.inclination == pytest.approx(51.6, abs=1e-4)
    assert omm_obj.arg_of_pericenter == pytest.approx(120.0, abs=1e-4)
    assert omm_obj.ra_of_asc_node == pytest.approx(20.0, abs=1e-4)

    # TLE parameters should not be present for non-SGP4 OMM
    assert omm_obj.tle_parameters is None

    # Check that comments are present
    assert len(omm_obj.comments) > 0


# ===================================================================
# 14. keplerian_to_omm round-trip test
# ===================================================================


def test_keplerian_to_omm_round_trip(tmp_path: Path) -> None:
    """Should preserve OMM content through keplerian_to_omm and file I/O."""
    import numpy as np
    from datetime import datetime, timezone

    keplerian_elements = np.array(
        [
            7000000.0,  # semi-major axis (m)
            0.001,  # eccentricity
            np.radians(45.0),  # inclination (rad)
            np.radians(90.0),  # argument of periapsis (rad)
            np.radians(180.0),  # RAAN (rad)
            np.radians(270.0),  # true anomaly (rad)
        ]
    )

    epoch = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    omm1 = omm.keplerian_to_omm(
        epoch=epoch,
        keplerian_elements=keplerian_elements,
        object_name="ROUND-TRIP-TEST",
        object_id="2026-001A",
        ref_frame="J2000",
        mean_element_theory="USM",
    )

    # Write to file
    out_path = tmp_path / "keplerian_roundtrip.omm"
    omm1.to_file(out_path)

    # Read back
    omm2 = omm.CcsdsOmm.from_source(out_path)

    # Verify key fields are preserved
    assert omm2.object_name == "ROUND-TRIP-TEST"
    assert omm2.object_id == "2026-001A"
    assert omm2.ref_frame == "J2000"
    assert omm2.mean_element_theory == "USM"
    assert omm2.mean_motion == pytest.approx(omm1.mean_motion, abs=1e-10)
    assert omm2.eccentricity == pytest.approx(omm1.eccentricity, abs=1e-10)
    assert omm2.inclination == pytest.approx(omm1.inclination, abs=1e-10)
    assert omm2.ra_of_asc_node == pytest.approx(omm1.ra_of_asc_node, abs=1e-10)
    assert omm2.arg_of_pericenter == pytest.approx(omm1.arg_of_pericenter, abs=1e-10)
    assert omm2.mean_anomaly == pytest.approx(omm1.mean_anomaly, abs=1e-10)
    assert omm2.tle_parameters is None
