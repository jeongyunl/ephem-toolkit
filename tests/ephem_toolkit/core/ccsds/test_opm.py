"""Tests for CCSDS Orbit Parameter Message parsing and writing."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import core.ccsds.opm as opm

OPM_DIR = Path(__file__).parents[3] / "opm"
OPM_FILES = sorted((*OPM_DIR.glob("*.opm"), *OPM_DIR.glob("*.kvn")))


def test_read_opm_parses_header_state_and_units() -> None:
    header, metadata, data = opm.read_opm(OPM_DIR / "sample2.opm")

    assert header["CCSDS_OPM_VERS"] == pytest.approx(3.0)
    assert header["ORIGINATOR"] == "GSOC"
    assert metadata["OBJECT_NAME"] == "EUTELSAT W4"
    assert data["X"] == pytest.approx(6655.9942)
    assert data["X_DOT"] == pytest.approx(3.11548208)
    assert len(data["MANEUVERS"]) == 2
    assert data["MANEUVERS"][0]["MAN_DURATION"] == pytest.approx(132.60)


def test_read_opm_parses_covariance_and_user_defined_values() -> None:
    _, _, data = opm.read_opm(OPM_DIR / "sample4.opm")

    assert data["COV_REF_FRAME"] == "RTN"
    assert data["CZ_DOT_Z_DOT"] == pytest.approx(6.2244443386355e-10)
    assert data["USER_DEFINED_EARTH_MODEL"] == "WGS-84"


def test_ccsds_opm_exposes_optional_blocks() -> None:
    message = opm.CcsdsOpm.from_source(OPM_DIR / "sample4.opm")

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
        opm.read_opm(_minimal_opm("ECCENTRICITY = 0.1\n"))


def test_read_opm_rejects_partial_covariance_matrix() -> None:
    with pytest.raises(ValueError, match="Incomplete OPM covariance"):
        opm.read_opm(_minimal_opm("CX_X = 1\n"))


def test_read_opm_requires_mass_and_negative_delta_mass_for_maneuvers() -> None:
    maneuver = "MAN_EPOCH_IGNITION = 2026-01-01T00:00:00\n"
    with pytest.raises(ValueError, match="MASS"):
        opm.read_opm(_minimal_opm(maneuver))

    invalid_mass_change = "MASS = 100\n" + maneuver + "MAN_DELTA_MASS = 1\n"
    with pytest.raises(ValueError, match="must be negative"):
        opm.read_opm(_minimal_opm(invalid_mass_change))


@pytest.mark.parametrize("path", OPM_FILES, ids=lambda p: p.name)
def test_opm_dictionary_round_trip(path: Path) -> None:
    header, metadata, data = opm.read_opm(path)
    output = io.StringIO()

    opm.write_opm(output, header, metadata, data)
    parsed_header, parsed_metadata, parsed_data = opm.read_opm(
        io.StringIO(output.getvalue())
    )

    assert parsed_header == header
    assert parsed_metadata == metadata
    assert parsed_data == data


def test_ccsds_opm_structured_api() -> None:
    message = opm.CcsdsOpm.from_source(OPM_DIR / "sample2.opm")

    assert message.state_vector.values.tolist() == pytest.approx(
        [6655.9942, -40218.5751, -82.9177, 3.11548208, 0.47042605, -0.00101495]
    )
    assert len(message.maneuvers) == 2
    assert message.maneuvers[1].man_ref_frame == "RTN"
