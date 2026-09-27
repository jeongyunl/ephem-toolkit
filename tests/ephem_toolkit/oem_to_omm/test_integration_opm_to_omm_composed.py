"""Integration coverage for composed OPM-to-OMM workflows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ephem_toolkit.core.ccsds.omm import CcsdsOmm
from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.core.ccsds.opm import CcsdsOpm, OpmHeader, OpmStateVector
from ephem_toolkit.oem_to_omm import main as oem_to_omm_main
from ephem_toolkit.propagate_kepler import main as propagate_kepler_main
from ephem_toolkit.propagate_orbit import main as propagate_orbit_main


def _write_numerical_reference_oem(tmp_path: Path) -> tuple[CcsdsOpm, Path]:
    source = tmp_path / "source-j2000.opm"
    source_opm = CcsdsOpm(
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
    )
    source_opm.to_file(source)
    reference_oem = tmp_path / "numerical-reference.oem"
    propagate_orbit_main(
        [str(source), "--duration", "2h", "--output", str(reference_oem)]
    )
    return source_opm, reference_oem


def test_opm_to_omm_composes_kepler_propagation_and_dsst_fit(tmp_path: Path) -> None:
    """Propagate an OPM to OEM, then fit the Cartesian arc to DSST elements."""
    source = Path(__file__).parents[2] / "opm/sample2.opm"
    reference_oem = tmp_path / "reference.oem"
    output_omm = tmp_path / "output.omm"
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
    oem_to_omm_main(
        [
            str(reference_oem),
            "--fit-model",
            "dsst",
            "--fit-span",
            "2h",
            "--fit-report",
            str(fit_report),
            "--output",
            str(output_omm),
        ]
    )

    output_text = output_omm.read_text(encoding="utf-8")
    source_id = CcsdsOpm.from_source(source).metadata["OBJECT_ID"]
    converted_omm = CcsdsOmm.from_source(output_omm)
    assert "MEAN_ELEMENT_THEORY = DSST" in output_text
    assert "target_model=two-body-kepler" in output_text
    assert converted_omm.object_id == source_id
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert report["status"] == "converged"
    assert report["configuration"]["fit_model"] == "dsst"
    assert report["diagnostics"]["n_records"] == 25
    assert report["provenance"]["target_model"] == "DSST"
    assert any(
        "target_model=two-body-kepler" in comment
        for comment in report["configuration"]["source_comments"]
    )


def test_opm_to_omm_composes_numerical_propagation_and_dsst_fit(tmp_path: Path) -> None:
    """Propagate an OPM numerically, then fit the Cartesian arc to DSST elements."""
    source_opm, reference_oem = _write_numerical_reference_oem(tmp_path)
    output_omm = tmp_path / "numerical-output.omm"
    fit_report = tmp_path / "numerical-output.fit.json"

    generated_oem = CcsdsOem.read(reference_oem)
    assert generated_oem.meta.object_name == source_opm.metadata["OBJECT_NAME"]
    assert generated_oem.meta.object_id == source_opm.metadata["OBJECT_ID"]
    assert "SOURCE_COMMENT: numerical OPM input" in generated_oem.meta.comments
    oem_to_omm_main(
        [
            str(reference_oem),
            "--fit-model",
            "dsst",
            "--fit-span",
            "2h",
            "--source-model",
            "numerical",
            "--fit-report",
            str(fit_report),
            "--output",
            str(output_omm),
        ]
    )

    output_text = output_omm.read_text(encoding="utf-8")
    converted_omm = CcsdsOmm.from_source(output_omm)
    assert "MEAN_ELEMENT_THEORY = DSST" in output_text
    assert "EPHEMERIS_PROPAGATION" in output_text
    assert converted_omm.object_id == source_opm.metadata["OBJECT_ID"]
    assert "SOURCE_COMMENT: numerical OPM input" in converted_omm.comments
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert report["status"] == "converged"
    assert report["configuration"]["fit_model"] == "dsst"
    assert report["provenance"]["source"] == "OEM/numerical"
    assert report["diagnostics"]["n_records"] == 50
    assert report["provenance"]["target_model"] == "DSST"
    assert any(
        "EPHEMERIS_PROPAGATION" in comment
        for comment in report["configuration"]["source_comments"]
    )


@pytest.mark.parametrize(
    ("fit_model", "expected_theory", "expected_frame", "report_target_model"),
    [
        ("brouwer", "BROUWER-LYDDANE", "ICRF", "BROUWER-LYDDANE"),
        ("sgp4", "SGP/SGP4", "TEME", "SGP4"),
    ],
)
def test_opm_numerical_fit_variants_preserve_metadata(
    tmp_path: Path,
    fit_model: str,
    expected_theory: str,
    expected_frame: str,
    report_target_model: str,
) -> None:
    source_opm, reference_oem = _write_numerical_reference_oem(tmp_path)
    output_omm = tmp_path / f"{fit_model}-output.omm"
    fit_report = tmp_path / f"{fit_model}-output.fit.json"

    oem_to_omm_main(
        [
            str(reference_oem),
            "--fit-model",
            fit_model,
            "--fit-span",
            "2h",
            "--source-model",
            "numerical",
            "--fit-report",
            str(fit_report),
            "--output",
            str(output_omm),
        ]
    )

    converted_omm = CcsdsOmm.from_source(output_omm)
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert converted_omm.object_name == source_opm.metadata["OBJECT_NAME"]
    assert converted_omm.object_id == source_opm.metadata["OBJECT_ID"]
    assert converted_omm.mean_element_theory == expected_theory
    assert converted_omm.originator == "oem_to_omm"
    assert converted_omm.creation_date
    assert converted_omm.center_name == "EARTH"
    assert converted_omm.ref_frame == expected_frame
    assert converted_omm.time_system == "UTC"
    assert "SOURCE_COMMENT: numerical OPM input" in converted_omm.comments
    assert any("source=OEM/numerical" in comment for comment in converted_omm.comments)
    assert report["provenance"]["source"] == "OEM/numerical"
    assert report["provenance"]["target_model"] == report_target_model
    assert (
        "SOURCE_COMMENT: numerical OPM input"
        in report["configuration"]["source_comments"]
    )
