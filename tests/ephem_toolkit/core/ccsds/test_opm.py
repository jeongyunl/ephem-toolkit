"""Tests for CCSDS Orbit Parameter Message parsing and writing."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import core.ccsds.opm as opm

OPM_DIR = Path(__file__).parents[3] / "opm"
OPM_FILES = sorted((*OPM_DIR.glob("*.opm"), *OPM_DIR.glob("*.kvn")))


def test_read_opm_parses_header_state_and_units() -> None:
    header, metadata, data = opm._read_opm(OPM_DIR / "sample2.opm")

    assert header["CCSDS_OPM_VERS"] == pytest.approx(3.0)
    assert header["ORIGINATOR"] == "GSOC"
    assert metadata["OBJECT_NAME"] == "EUTELSAT W4"
    assert data["X"] == pytest.approx(6655.9942)
    assert data["X_DOT"] == pytest.approx(3.11548208)
    assert len(data["MANEUVERS"]) == 2
    assert data["MANEUVERS"][0]["MAN_DURATION"] == pytest.approx(132.60)


def test_read_opm_parses_covariance_and_user_defined_values() -> None:
    _, _, data = opm._read_opm(OPM_DIR / "sample4.opm")

    assert data["COV_REF_FRAME"] == "RTN"
    assert data["CZ_DOT_Z_DOT"] == pytest.approx(6.2244443386355e-10)
    assert data["USER_DEFINED_EARTH_MODEL"] == "WGS-84"


def test_ccsds_opm_exposes_optional_blocks() -> None:
    message = opm.CcsdsOpm.from_file(OPM_DIR / "sample4.opm")

    assert message.keplerian_elements is not None
    assert message.keplerian_elements.true_anomaly == pytest.approx(41.922339)
    assert message.spacecraft_parameters is not None
    assert message.spacecraft_parameters.mass == pytest.approx(1913.0)
    assert message.covariance is not None
    assert message.covariance.ref_frame == "RTN"
    assert message.covariance.matrix.shape == (6, 6)
    assert message.covariance.matrix[5, 0] == pytest.approx(
        message.covariance.matrix[0, 5]
    )


def _minimal_opm(extra: str = "") -> io.StringIO:
    return io.StringIO("""\
CCSDS_OPM_VERS = 3.0
CREATION_DATE = 2026-01-01T00:00:00
ORIGINATOR = TEST
OBJECT_NAME = TEST
OBJECT_ID = 2026-001A
CENTER_NAME = EARTH
REF_FRAME = ICRF
TIME_SYSTEM = UTC
EPOCH = 2026-01-01T00:00:00
X = 1
Y = 2
Z = 3
X_DOT = 4
Y_DOT = 5
Z_DOT = 6
""" + extra)


def test_read_opm_rejects_partial_keplerian_elements() -> None:
    with pytest.raises(ValueError, match="Incomplete OPM Keplerian"):
        opm._read_opm(_minimal_opm("ECCENTRICITY = 0.1\n"))


def test_read_opm_rejects_partial_covariance_matrix() -> None:
    with pytest.raises(ValueError, match="Incomplete OPM covariance"):
        opm._read_opm(_minimal_opm("CX_X = 1\n"))


def test_read_opm_requires_mass_and_negative_delta_mass_for_maneuvers() -> None:
    maneuver = "MAN_EPOCH_IGNITION = 2026-01-01T00:00:00\n"
    with pytest.raises(ValueError, match="MASS"):
        opm._read_opm(_minimal_opm(maneuver))

    invalid_mass_change = "MASS = 100\n" + maneuver + "MAN_DELTA_MASS = 1\n"
    with pytest.raises(ValueError, match="must be negative"):
        opm._read_opm(_minimal_opm(invalid_mass_change))


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("CENTER_NAME", "   ", "CENTER_NAME"),
        ("REF_FRAME", "UNKNOWN", "REF_FRAME"),
        ("TIME_SYSTEM", "UNKNOWN", "TIME_SYSTEM"),
    ],
)
def test_read_opm_rejects_invalid_context(key: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        opm._read_opm(_minimal_opm(f"{key} = {value}\n"))


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ("UNRECOGNIZED_KEY = value\n", "Unsupported OPM keyword"),
        ("not a KVN assignment\n", "Invalid OPM KVN assignment"),
        ("x = 7\n", "uppercase"),
        ("X = 7\n", "Duplicate OPM keyword X"),
        ("X = 1 [m]\n", "Invalid unit for OPM keyword X"),
    ],
)
def test_read_opm_rejects_invalid_syntax(extra: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        opm._read_opm(_minimal_opm(extra), validate=False)


def test_read_opm_rejects_out_of_order_data_keywords() -> None:
    content = _minimal_opm().getvalue().replace("X = 1\nY = 2\n", "Y = 2\nX = 1\n")

    with pytest.raises(ValueError, match="out of order"):
        opm._read_opm(io.StringIO(content), validate=False)


def test_read_opm_requires_version_as_first_nonblank_line() -> None:
    content = (
        _minimal_opm()
        .getvalue()
        .replace("CCSDS_OPM_VERS = 3.0\n", "CREATION_DATE = 2026-01-01T00:00:00\n")
    )
    content = content.replace(
        "CREATION_DATE = 2026-01-01T00:00:00\n",
        "CREATION_DATE = 2026-01-01T00:00:00\nCCSDS_OPM_VERS = 3.0\n",
        1,
    )

    with pytest.raises(ValueError, match="CCSDS_OPM_VERS must be the first"):
        opm._read_opm(io.StringIO(content), validate=False)


def test_read_opm_rejects_non_ascii_and_overlong_lines() -> None:
    for content, message in (
        (_minimal_opm("COMMENT café\n"), "not ASCII"),
        (_minimal_opm(f"COMMENT {'x' * 250}\n"), "exceeds 254"),
    ):
        with pytest.raises(ValueError, match=message):
            opm._read_opm(content, validate=False)


def test_write_opm_rejects_unknown_data_keywords() -> None:
    header, metadata, data = opm._read_opm(OPM_DIR / "sample1.opm")
    data["NOT_A_STANDARD_KEY"] = 1

    with pytest.raises(ValueError, match="Unsupported OPM data keyword"):
        opm._write_opm(io.StringIO(), header, metadata, data)


def test_write_opm_limits_float_precision_to_ccsds_maximum() -> None:
    header, metadata, data = opm._read_opm(_minimal_opm())
    data["X"] = 1756.1529363008328
    output = io.StringIO()

    opm._write_opm(output, header, metadata, data)

    assert "X = 1756.152936300833 [km]" in output.getvalue()


@pytest.mark.parametrize("path", OPM_FILES, ids=lambda p: p.name)
def test_opm_dictionary_round_trip(path: Path) -> None:
    header, metadata, data = opm._read_opm(path)
    output = io.StringIO()

    opm._write_opm(output, header, metadata, data)
    parsed_header, parsed_metadata, parsed_data = opm._read_opm(
        io.StringIO(output.getvalue())
    )

    assert parsed_header == header
    assert parsed_metadata == metadata
    assert parsed_data == data


def test_ccsds_opm_structured_api() -> None:
    message = opm.CcsdsOpm.from_file(OPM_DIR / "sample2.opm")

    assert message.state_vector.values.tolist() == pytest.approx(
        [6655.9942, -40218.5751, -82.9177, 3.11548208, 0.47042605, -0.00101495]
    )
    assert len(message.maneuvers) == 2
    assert message.maneuvers[1].man_ref_frame == "RTN"


def test_opm_comments_survive_structured_round_trip() -> None:
    message = opm.CcsdsOpm.from_file(OPM_DIR / "sample2.opm")
    comment = "EPHEMERIS_PROVENANCE: source=OEM/DSST; target_model=numerical"
    message.header.comments.append(comment)

    output = io.StringIO()
    message.write(output)
    round_tripped = opm.CcsdsOpm.read(io.StringIO(output.getvalue()))

    assert comment in round_tripped.header.comments
