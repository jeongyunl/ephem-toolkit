"""Integration coverage for composed OPM-to-TLE workflows."""

from __future__ import annotations

import json
from pathlib import Path

from ephem_toolkit.core.ccsds.opm import CcsdsOpm, OpmHeader, OpmStateVector
from ephem_toolkit.oem_to_tle import main as oem_to_tle_main
from ephem_toolkit.propagate_kepler import main as propagate_kepler_main
from ephem_toolkit.propagate_orbit import main as propagate_orbit_main


def _write_j2000_opm(tmp_path: Path) -> Path:
    source = tmp_path / "source-j2000.opm"
    CcsdsOpm(
        header=OpmHeader(
            version=3.0,
            comments=["SOURCE_COMMENT: numerical OPM input"],
            creation_date="2026-05-20T00:00:00.000",
            originator="test",
        ),
        metadata={
            "OBJECT_NAME": "NUMERICAL TEST SAT",
            "OBJECT_ID": "2024-001A",
            "CENTER_NAME": "EARTH",
            "REF_FRAME": "J2000",
            "TIME_SYSTEM": "UTC",
        },
        state_vector=OpmStateVector(
            epoch="2026-05-20T12:00:00.000",
            x=6778.0,
            y=0.0,
            z=0.0,
            x_dot=0.0,
            y_dot=5.4,
            z_dot=5.4,
        ),
    ).to_file(source)
    return source


def _assert_valid_tle(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()[-2:]
    assert lines[0].startswith("1 ") and len(lines[0]) == 69
    assert lines[1].startswith("2 ") and len(lines[1]) == 69
    for line in lines:
        checksum = sum(int(character) for character in line[:68] if character.isdigit())
        checksum += line[:68].count("-")
        assert line[68] == str(checksum % 10)


def test_opm_to_tle_composes_kepler_propagation_and_sgp4_fit(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "opm/sample2.opm"
    reference_oem = tmp_path / "reference.oem"
    output_tle = tmp_path / "output.tle"
    fit_report = tmp_path / "output.fit.json"

    assert (
        propagate_kepler_main(
            [
                str(source),
                "--duration",
                "2h",
                "--step",
                "5m",
                "--output",
                str(reference_oem),
            ]
        )
        == 0
    )
    oem_to_tle_main(
        [
            str(reference_oem),
            "--fit-span",
            "2h",
            "--source-model",
            "two-body",
            "--fit-report",
            str(fit_report),
            "--output",
            str(output_tle),
        ]
    )

    _assert_valid_tle(output_tle)
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert report["status"] == "converged"
    assert report["provenance"]["source"] == "OEM/two-body"
    assert report["provenance"]["target_model"] == "SGP4"
    assert report["diagnostics"]["n_records"] == 25


def test_opm_to_tle_composes_numerical_propagation_and_sgp4_fit(tmp_path: Path) -> None:
    source = _write_j2000_opm(tmp_path)
    reference_oem = tmp_path / "numerical-reference.oem"
    output_tle = tmp_path / "numerical-output.tle"
    fit_report = tmp_path / "numerical-output.fit.json"

    propagate_orbit_main(
        [str(source), "--duration", "2h", "--output", str(reference_oem)]
    )
    oem_to_tle_main(
        [
            str(reference_oem),
            "--fit-span",
            "2h",
            "--source-model",
            "numerical",
            "--fit-report",
            str(fit_report),
            "--output",
            str(output_tle),
        ]
    )

    _assert_valid_tle(output_tle)
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert report["status"] == "converged"
    assert report["provenance"]["source"] == "OEM/numerical"
    assert report["provenance"]["target_model"] == "SGP4"
    assert report["diagnostics"]["n_records"] == 50
