"""Tests for src/omm_to_tle/omm_to_tle.py — OMM to TLE conversion utility script."""

from __future__ import annotations

import argparse
import io
import sys

import pytest

import ephem_toolkit.core.ccsds.omm as omm
import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.tle as tle
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


@pytest.mark.parametrize(
    "unsupported_option",
    ["--fit-model", "--fit-report", "--source-model", "--refit-sgp4"],
)
def test_omm_to_tle_rejects_fit_and_provenance_options(unsupported_option: str) -> None:
    """Direct lossless conversion rejects options reserved for refitting."""
    with pytest.raises(SystemExit) as error:
        parse_arguments(
            build_arg_parser(),
            [unsupported_option, "value", "input.omm", "-o", "output.tle"],
        )

    assert error.value.code == 2


@pytest.mark.parametrize("theory", ["DSST", "BROUWER-LYDDANE"])
def test_omm_to_tle_rejects_non_sgp4_theory_before_writing(
    monkeypatch, tmp_path, theory, capsys
) -> None:
    """Direct conversion rejects non-SGP4 OMMs before output is created."""
    source = tmp_path / "input.omm"
    output = tmp_path / "output.tle"
    source.write_text("OMM", encoding="utf-8")
    non_sgp4 = omm.CcsdsOmm(mean_element_theory=theory)
    monkeypatch.setattr(omm.CcsdsOmm, "from_source", lambda *_args: non_sgp4)
    monkeypatch.setattr(
        convert_tle,
        "omm_to_tle",
        lambda *_args: pytest.fail("conversion must not run for a non-SGP4 OMM"),
    )

    with pytest.raises(SystemExit) as error:
        omm_to_tle.main([str(source), "-o", str(output)])

    assert error.value.code == 1
    assert not output.exists()
    diagnostic = capsys.readouterr().err
    assert theory in diagnostic
    assert "SGP4-compatible" in diagnostic
    assert "Propagate the OMM to an OEM" in diagnostic


@pytest.mark.parametrize("theory", ["SGP", "PPT3", "SGP4", "SGP/SGP4"])
def test_validate_sgp4_compatible_omm_accepts_supported_theory_aliases(theory) -> None:
    """All supported SGP4 theory labels pass direct-conversion validation."""
    compatible = omm.CcsdsOmm(mean_element_theory=theory, tle_parameters=object())

    convert_tle.validate_sgp4_compatible_omm(compatible)


def test_omm_to_tle_rejects_missing_tle_parameters_before_writing(
    monkeypatch, tmp_path, capsys
) -> None:
    """Direct SGP4 conversion rejects incomplete TLE metadata before output."""
    source = tmp_path / "input.omm"
    output = tmp_path / "output.tle"
    source.write_text("OMM", encoding="utf-8")
    incomplete = omm.CcsdsOmm(mean_element_theory="SGP4", tle_parameters=None)
    monkeypatch.setattr(omm.CcsdsOmm, "from_source", lambda *_args: incomplete)
    monkeypatch.setattr(
        convert_tle,
        "omm_to_tle",
        lambda *_args: pytest.fail("conversion must not run without TLE parameters"),
    )

    with pytest.raises(SystemExit) as error:
        omm_to_tle.main([str(source), "-o", str(output)])

    assert error.value.code == 1
    assert not output.exists()
    diagnostic = capsys.readouterr().err
    assert "TLE parameters" in diagnostic
    assert "MEAN_ELEMENT_THEORY='SGP4'" in diagnostic


@pytest.mark.parametrize("input_source", ["stdin", "file"])
@pytest.mark.parametrize("output_mode", ["stdout", "file", "implicit_stdout"])
def test_omm_to_tle_main_converts_and_writes_output(
    monkeypatch, tmp_path, input_source, output_mode
) -> None:
    converted_omm = omm.CcsdsOmm(mean_element_theory="SGP4", tle_parameters=object())
    tle_data = object()
    writes = []
    source_path = tmp_path / "input.omm"
    source_path.write_text("OMM", encoding="utf-8")
    monkeypatch.setattr(omm.CcsdsOmm, "from_source", lambda _source: converted_omm)
    monkeypatch.setattr(convert_tle, "validate_sgp4_compatible_omm", lambda _omm: None)
    monkeypatch.setattr(convert_tle, "omm_to_tle", lambda _omm: tle_data)
    monkeypatch.setattr(
        tle, "write_tle", lambda destination, data: writes.append((destination, data))
    )

    input_argument = "-" if input_source == "stdin" else str(source_path)
    if input_source == "stdin":
        monkeypatch.setattr(sys, "stdin", io.StringIO("OMM"))
    if output_mode == "stdout":
        output_argument = "-"
        expected_destination = sys.stdout
    elif output_mode == "file":
        output_argument = str(tmp_path / "output.tle")
        expected_destination = output_argument
    else:
        output_argument = ""
        expected_destination = sys.stdout

    omm_to_tle.main([input_argument, "-o", output_argument])

    assert writes == [(expected_destination, tle_data)]


def test_omm_to_tle_main_rejects_empty_stdin(capsys) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sys, "stdin", io.StringIO(" \n"))

    try:
        with pytest.raises(SystemExit) as error:
            omm_to_tle.main(["-", "-o", "-"])
    finally:
        monkeypatch.undo()

    assert error.value.code == 1
    assert "no input from stdin" in capsys.readouterr().err


def test_omm_to_tle_main_reports_input_and_parse_errors(
    monkeypatch, tmp_path, capsys
) -> None:
    source = tmp_path / "empty.omm"
    source.write_text("  \n", encoding="utf-8")
    with pytest.raises(SystemExit) as empty_error:
        omm_to_tle.main([str(source), "-o", "-"])
    assert empty_error.value.code == 1
    assert "is empty" in capsys.readouterr().err

    source.write_text("OMM", encoding="utf-8")
    monkeypatch.setattr(
        omm.CcsdsOmm,
        "from_source",
        lambda _source: (_ for _ in ()).throw(ValueError("invalid OMM")),
    )
    with pytest.raises(SystemExit) as parse_error:
        omm_to_tle.main([str(source), "-o", "-"])
    assert parse_error.value.code == 1
    assert "invalid OMM" in capsys.readouterr().err


def test_omm_to_tle_main_reports_file_read_and_conversion_errors(
    monkeypatch, tmp_path, capsys
) -> None:
    source = tmp_path / "input.omm"
    source.write_text("OMM", encoding="utf-8")
    original_open = open

    def failing_open(path, *args, **kwargs):
        if path == str(source):
            raise OSError("unreadable")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    with pytest.raises(SystemExit) as read_error:
        omm_to_tle.main([str(source), "-o", "-"])
    assert read_error.value.code == 1
    assert "could not read input file" in capsys.readouterr().err

    monkeypatch.setattr("builtins.open", original_open)
    monkeypatch.setattr(
        omm.CcsdsOmm,
        "from_source",
        lambda _source: omm.CcsdsOmm(
            mean_element_theory="SGP4", tle_parameters=object()
        ),
    )
    monkeypatch.setattr(convert_tle, "validate_sgp4_compatible_omm", lambda _omm: None)
    monkeypatch.setattr(
        convert_tle,
        "omm_to_tle",
        lambda _omm: (_ for _ in ()).throw(ValueError("conversion failed")),
    )
    with pytest.raises(SystemExit) as conversion_error:
        omm_to_tle.main([str(source), "-o", "-"])
    assert conversion_error.value.code == 1
    assert "conversion failed" in capsys.readouterr().err
