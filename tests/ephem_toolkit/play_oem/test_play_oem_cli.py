"""Tests for the play-oem command-line scaffold."""

from __future__ import annotations

from pathlib import Path

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


def test_duration_and_time_unit_options_are_accepted() -> None:
    args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", "-d", "90m", "--time-unit", "minutes"],
    )

    assert args.input_oem == "orbit.oem"
    assert args.duration == "90m"
    assert args.time_unit == "minutes"


def test_static_output_option_is_not_supported() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments(build_arg_parser(), ["orbit.oem", "-o", "orbit.png"])

    assert exc_info.value.code == 2


def test_cli_reports_missing_input_file(
    capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    result = cli([str(tmp_path / "missing.oem")])

    assert result == 1
    assert "File not found" in capsys.readouterr().err


def test_cli_loads_and_prepares_oem_data(capsys: pytest.CaptureFixture[str]) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )

    main([str(input_oem), "--duration", "1h", "--time-unit", "minutes"])

    output = capsys.readouterr().out
    assert "Loaded 721 states" in output
    assert "Using 16 states after duration filtering" in output
    assert "Prepared orbit series with 16 samples using minutes." in output


def test_cli_reports_invalid_duration(capsys: pytest.CaptureFixture[str]) -> None:
    input_oem = (
        Path(__file__).resolve().parents[2] / "data" / "ISS_2026-05-20_small.OEM"
    )

    with pytest.raises(SystemExit) as exc_info:
        main([str(input_oem), "--duration", "not-a-duration"])

    assert exc_info.value.code == 1
    assert "failed to parse duration" in capsys.readouterr().err
