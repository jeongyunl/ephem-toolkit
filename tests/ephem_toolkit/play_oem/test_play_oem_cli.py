"""Tests for the play-oem command-line scaffold."""

from __future__ import annotations

import pytest

from ephem_toolkit.play_oem import cli, main
from ephem_toolkit.play_oem.play_oem_cli import build_arg_parser, parse_arguments


def test_help_shows_command_and_input(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    help_output = capsys.readouterr().out
    assert "play-oem" in help_output
    assert "<input_oem>" in help_output


def test_input_path_is_parsed() -> None:
    args = parse_arguments(build_arg_parser(), ["orbit.oem"])

    assert args.input_oem == "orbit.oem"


def test_missing_input_reports_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2
    error_output = capsys.readouterr().err
    assert "usage:" in error_output
    assert "<input_oem>" in error_output


def test_cli_reports_unimplemented_playback(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli(["orbit.oem"])

    assert exc_info.value.code == 2
    error_output = capsys.readouterr().err
    assert "play-oem is not implemented yet" in error_output
