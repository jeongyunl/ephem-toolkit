"""Tests for src/tle_to_omm/tle_to_omm.py — TLE to OMM conversion utility script."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import ephem_toolkit.core.convert_tle as convert_tle
import ephem_toolkit.core.tle as tle
import ephem_toolkit.tle_to_omm.__main__ as tle_to_omm_entry
from ephem_toolkit.tle_to_omm.tle_to_omm_cli import build_arg_parser, parse_arguments


def test_tle_to_omm_help_uses_command_name_and_format_aware_output() -> None:
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
    assert "usage: tle-to-omm" in help_text
    assert "--output <output_omm|->" in help_text


def test_main_reads_stdin_converts_tle_and_writes_to_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parsed_input = []
    tle_object = object()

    def read_tle(stream):
        parsed_input.append(stream.read())
        return tle_object

    monkeypatch.setattr(tle, "read_tle", read_tle)
    monkeypatch.setattr(
        convert_tle,
        "tle_to_omm",
        lambda parsed_tle: SimpleNamespace(
            to_file=lambda output: output.write("OMM output\n")
        )
        if parsed_tle is tle_object
        else None,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("TLE input\n"))

    tle_to_omm_entry.main(["-", "--output", "-"])

    assert parsed_input == ["TLE input\n"]
    assert capsys.readouterr().out == "OMM output\n"


def test_main_reads_file_and_writes_omm_to_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    input_path = tmp_path / "source.tle"
    output_path = tmp_path / "converted.omm"
    input_path.write_text("TLE file data\n", encoding="utf-8")
    parsed_input = []

    def read_tle(stream):
        parsed_input.append(stream.read())
        return object()

    monkeypatch.setattr(tle, "read_tle", read_tle)
    monkeypatch.setattr(
        convert_tle,
        "tle_to_omm",
        lambda _tle: SimpleNamespace(
            to_file=lambda destination: Path(destination).write_text(
                "OMM file data\n", encoding="utf-8"
            )
        ),
    )

    tle_to_omm_entry.main([str(input_path), "--output", str(output_path)])

    assert parsed_input == ["TLE file data\n"]
    assert output_path.read_text(encoding="utf-8") == "OMM file data\n"


@pytest.mark.parametrize(
    ("source", "stdin_text", "error_text"),
    [
        ("-", "  \n", "no input from stdin"),
        ("missing.tle", None, "could not read input file 'missing.tle'"),
    ],
)
def test_main_reports_unreadable_or_empty_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: str,
    stdin_text: str | None,
    error_text: str,
) -> None:
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))

    with pytest.raises(SystemExit) as error:
        tle_to_omm_entry.main([source, "--output", "-"])

    assert error.value.code == 1
    assert error_text in capsys.readouterr().err
