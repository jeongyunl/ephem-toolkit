"""Tests for portable ephemeris provenance and fit reports."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ephem_toolkit.core.provenance import (
    default_fit_report_path,
    fit_comment,
    provenance_comment,
    write_fit_report,
    resolve_source_model,
    comparison_residuals,
)


@dataclass
class Diagnostics:
    rms_position_m: float = 1.25
    iterations: int = 3
    n_records: int = 4
    span_s: float = 90.0


def test_comments_use_portable_format() -> None:
    assert provenance_comment(source="OEM/unknown", transformation="fit", target_model="SGP4") == (
        "EPHEMERIS_PROVENANCE: source=OEM/unknown; transformation=fit; target_model=SGP4"
    )
    assert fit_comment(span_s=90, samples=4, position_rms=1.25) == (
        "EPHEMERIS_FIT: span=90s; samples=4; position_rms=1.25; velocity_rms=unknown"
    )


def test_fit_report_is_json(tmp_path) -> None:
    report_path = tmp_path / "fit.json"
    write_fit_report(
        report_path,
        provenance={"source": "OEM/unknown", "target_model": "two-body-kepler"},
        diagnostics=Diagnostics(),
        configuration={"fit_span_s": 90},
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["diagnostics"]["n_records"] == 4
    assert report["configuration"]["fit_span_s"] == 90
    assert report["status"] == "converged"
    assert report["iterations"] == 3


def test_fit_report_retains_source_report(tmp_path) -> None:
    report_path = tmp_path / "fit.json"
    source_report = {"provenance": {"source": "OEM/SGP4"}, "diagnostics": {"status": "ok"}}
    write_fit_report(
        report_path,
        provenance={"source": "OEM/SGP4"},
        diagnostics=Diagnostics(),
        source_report=source_report,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["source_report"] == source_report


def test_fit_report_serializes_configuration_object(tmp_path) -> None:
    from ephem_toolkit.oem_to_opm.fit_numerical import NumericalFitConfig

    report_path = tmp_path / "fit.json"
    write_fit_report(
        report_path,
        provenance={"source": "OEM/unknown"},
        diagnostics=Diagnostics(),
        configuration=NumericalFitConfig(),
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["configuration"]["fit_model"] == "numerical"
    assert report["configuration"]["fixed_parameters"] == {}


def test_fit_report_accepts_mapping_diagnostics(tmp_path) -> None:
    report_path = tmp_path / "fit.json"
    write_fit_report(
        report_path,
        provenance={"source": "OEM/unknown"},
        diagnostics={"status": "ok"},
    )
    assert json.loads(report_path.read_text(encoding="utf-8"))["diagnostics"] == {"status": "ok"}


def test_fit_report_can_be_written_to_stdout(capsys) -> None:
    write_fit_report(
        "-",
        provenance={"source": "OEM/unknown"},
        diagnostics={"status": "ok"},
    )

    report = json.loads(capsys.readouterr().out)
    assert report["provenance"]["source"] == "OEM/unknown"


def test_fit_report_rejects_non_finite_values(tmp_path) -> None:
    import math
    import pytest

    with pytest.raises(ValueError):
        write_fit_report(
            tmp_path / "fit.json",
            provenance={"source": "OEM/unknown"},
            diagnostics={"rms": math.nan},
        )


def test_default_fit_report_path_prefers_output() -> None:
    assert default_fit_report_path("source.oem", "result.opm") == Path("result.fit.json")
    assert default_fit_report_path("source.oem", "-") == Path("source.fit.json")
    assert default_fit_report_path("-", "-") is None


def test_resolve_source_model_reads_report(tmp_path) -> None:
    report_path = tmp_path / "source.json"
    report_path.write_text(json.dumps({"provenance": {"source": "OEM/SGP4"}}), encoding="utf-8")

    source, report = resolve_source_model("auto", str(report_path))

    assert source == "OEM/SGP4"
    assert report["provenance"]["source"] == "OEM/SGP4"


@pytest.mark.parametrize(
    "source_report",
    [{}, {"provenance": {}}, {"provenance": {"source": ""}}],
)
def test_resolve_source_model_defaults_when_report_has_no_source(
    tmp_path, source_report
) -> None:
    report_path = tmp_path / "source.json"
    report_path.write_text(json.dumps(source_report), encoding="utf-8")

    source, report = resolve_source_model("auto", str(report_path))

    assert source == "unknown"
    assert report == source_report


def test_explicit_source_model_overrides_report(tmp_path) -> None:
    report_path = tmp_path / "source.json"
    report_path.write_text(json.dumps({"provenance": {"source": "OEM/SGP4"}}), encoding="utf-8")

    source, _ = resolve_source_model("numerical", str(report_path))

    assert source == "numerical"


def test_resolve_source_model_rejects_invalid_report(tmp_path) -> None:
    report_path = tmp_path / "source.json"
    report_path.write_text("not-json", encoding="utf-8")

    import pytest

    with pytest.raises(ValueError, match="not valid JSON"):
        resolve_source_model("auto", str(report_path))


def test_comparison_residuals_summarize_position_and_velocity() -> None:
    class Comparison:
        def __init__(self, position, velocity):
            self.pos_err_km = position
            self.vel_err_m_s = velocity

    residuals = comparison_residuals([Comparison(1.0, 2.0), Comparison(3.0, 4.0)])

    assert residuals["position_rms_m"] == 2236.06797749979
    assert residuals["position_max_m"] == 3000.0
    assert residuals["velocity_rms_m_s"] == 3.1622776601683795
    assert residuals["velocity_max_m_s"] == 4.0
