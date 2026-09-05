"""Integration coverage for composed OPM-to-OMM workflows."""

from __future__ import annotations

import json
from pathlib import Path

from ephem_toolkit.oem_to_omm import main as oem_to_omm_main
from ephem_toolkit.propagate_kepler import main as propagate_kepler_main
from ephem_toolkit.propagate_orbit import main as propagate_orbit_main


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
    assert "MEAN_ELEMENT_THEORY = DSST" in output_text
    assert "target_model=two-body-kepler" in output_text
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
    source = Path(__file__).parents[2] / "opm/sample2.opm"
    reference_oem = tmp_path / "numerical-reference.oem"
    output_omm = tmp_path / "numerical-output.omm"
    fit_report = tmp_path / "numerical-output.fit.json"

    propagate_orbit_main(
        [
            str(source),
            "--duration",
            "2h",
            "--output",
            str(reference_oem),
        ]
    )
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
    assert "MEAN_ELEMENT_THEORY = DSST" in output_text
    assert "EPHEMERIS_PROPAGATION" in output_text
    report = json.loads(fit_report.read_text(encoding="utf-8"))
    assert report["status"] == "converged"
    assert report["configuration"]["fit_model"] == "dsst"
    assert report["provenance"]["source"] == "OEM/numerical"
    assert report["diagnostics"]["n_records"] == 27
    assert report["provenance"]["target_model"] == "DSST"
    assert any(
        "EPHEMERIS_PROPAGATION" in comment
        for comment in report["configuration"]["source_comments"]
    )
