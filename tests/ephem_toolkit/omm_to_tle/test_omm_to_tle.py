"""Tests for src/omm_to_tle/omm_to_tle.py — OMM to TLE conversion utility script."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pytest

import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.tle as tle
import ephem_toolkit.oem_to_omm.fit_common as fit_common
import ephem_toolkit.omm_to_tle as omm_to_tle
from ephem_toolkit.omm_to_tle.omm_to_tle_cli import build_arg_parser, parse_arguments


def test_omm_to_tle_help_uses_command_name_and_format_aware_output() -> None:
    """The CLI help should use the canonical command name and output placeholder."""
    old_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    help_text = captured_output.getvalue()
    assert "usage: omm-to-tle" in help_text
    assert "--output <output_tle|->" in help_text


def test_omm_to_tle_cli_uses_typed_namespace(monkeypatch) -> None:
    """The parser should return a typed Namespace subclass with the parsed fields."""
    from ephem_toolkit.omm_to_tle.omm_to_tle_cli import (
        OmmToTleArgs,
        build_arg_parser,
        parse_arguments,
    )

    monkeypatch.setattr(sys, "argv", ["omm-to-tle", "input.omm", "-o", "output.tle"])

    args = parse_arguments(build_arg_parser())

    assert issubclass(OmmToTleArgs, argparse.Namespace)
    assert isinstance(args, OmmToTleArgs)
    assert args.input_omm == "input.omm"
    assert args.output_tle == "output.tle"


@pytest.mark.parametrize("unsupported_option", ["--fit-model", "--fit-report", "--source-model"])
def test_omm_to_tle_rejects_fit_and_provenance_options(unsupported_option: str) -> None:
    """Direct lossless conversion rejects options reserved for refitting."""
    with pytest.raises(SystemExit) as error:
        args = [unsupported_option, "value", "input.omm", "-o", "output.tle"]
        omm_to_tle.main(args)

    assert error.value.code == 2


def test_omm_to_tle_rejects_non_sgp4_theory_before_writing(
    monkeypatch, tmp_path
) -> None:
    """Direct conversion rejects non-SGP4 OMMs before output is created."""
    source = tmp_path / "input.omm"
    output = tmp_path / "output.tle"
    source.write_text("OMM", encoding="utf-8")
    non_sgp4 = omm.CcsdsOmm(mean_element_theory="DSST")
    monkeypatch.setattr(omm.CcsdsOmm, "from_source", lambda *_args: non_sgp4)

    with pytest.raises(SystemExit) as error:
        omm_to_tle.main([str(source), "-o", str(output)])

    assert error.value.code == 1
    assert not output.exists()


def test_omm_to_tle_parser_accepts_refit_controls() -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["--refit-sgp4", "--fit-span", "90m", "input.omm", "-o", "output.tle"],
    )

    assert args.refit_sgp4 is True
    assert args.fit_span.total_seconds() == 5400.0


def test_omm_to_tle_refit_writes_tle_and_report(monkeypatch, tmp_path: Path) -> None:
    """The refit path propagates the source model and reports the transformation."""
    source = tmp_path / "input.omm"
    output = tmp_path / "output.tle"
    report = tmp_path / "refit.json"
    source.write_text("OMM", encoding="utf-8")
    source_omm = omm.CcsdsOmm(
        object_name="TEST",
        object_id="2024-001A",
        epoch="2026-01-01T00:00:00.000000",
        mean_element_theory="DSST",
    )
    monkeypatch.setattr(omm.CcsdsOmm, "from_source", lambda *_args: source_omm)

    import ephem_toolkit.core.convert_tle as convert_tle
    import ephem_toolkit.propagate_omm.propagation as propagation
    import ephem_toolkit.oem_to_omm.fit_tle_main as fit_tle_main

    monkeypatch.setattr(
        propagation,
        "propagate_omm_dsst",
        lambda *_args: print("OEM"),
    )
    monkeypatch.setattr(
        oem.CcsdsOem,
        "read",
        lambda *_args: type("ReferenceOem", (), {"states": [(0.0, [0.0] * 6), (600.0, [0.0] * 6)]})(),
    )
    with (Path(__file__).parents[2] / "data/ISS-ZARYA_1998-067A.tle").open() as stream:
        fitted_tle = tle.read_tle(stream)
    monkeypatch.setattr(
        fit_tle_main,
        "fit_tle",
        lambda *_args, **_kwargs: (
            fitted_tle,
            fit_common.FitDiagnostics(
                rms_position_m=12.0,
                iterations=2,
                n_records=2,
                span_s=600.0,
                fit_method="tle_cartesian",
            ),
        ),
    )

    omm_to_tle.main(
        [
            "--refit-sgp4",
            "--fit-span",
            "10m",
            "--fit-report",
            str(report),
            str(source),
            "-o",
            str(output),
        ]
    )

    assert output.exists()
    report_data = json.loads(report.read_text(encoding="utf-8"))
    assert report_data["provenance"] == {
        "source": "OMM/unknown",
        "transformation": "SGP4 refit",
        "target_model": "SGP4",
    }
    assert report_data["configuration"]["fit_model"] == "sgp4"
