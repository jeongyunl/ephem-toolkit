"""Tests for the propagate-orbit CLI and migration conventions."""

from __future__ import annotations

import pytest

from ephem_toolkit.propagate_orbit import propagate_orbit_cli


def test_parse_arguments_accepts_canonical_input_and_output_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical propagation CLI should accept positional input_opm, --output, and --duration."""
    input_opm = "input.opm"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", input_opm, "--duration", "2h"],
    )
    args = propagate_orbit_cli.parse_arguments()
    assert args.input_opm == input_opm
    assert args.output_oem is None
    assert args.duration == 7200.0

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", input_opm, "--duration", "2h", "--output", "-"],
    )
    args = propagate_orbit_cli.parse_arguments()
    assert args.input_opm == input_opm
    assert args.output_oem == "-"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", input_opm, "--output", "out.oem"],
    )
    args = propagate_orbit_cli.parse_arguments()
    assert args.input_opm == input_opm
    assert args.output_oem == "out.oem"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "-", "-d", "3h"],
    )
    args = propagate_orbit_cli.parse_arguments()
    assert args.input_opm == "-"
    assert args.duration == 10800.0


def test_parse_arguments_help_uses_project_standard_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real propagate-orbit help output should advertise the standardized names."""
    monkeypatch.setattr("sys.argv", ["propagate-orbit", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        propagate_orbit_cli.parse_arguments()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "input_opm" in captured.out
    assert "--output" in captured.out
    assert "--duration" in captured.out
    assert "-d" in captured.out
    parser = propagate_orbit_cli.parse_arguments.__globals__["cli"].create_parser(
        "demo tool"
    )
    parser.add_argument("-d", "--duration")
    parser.add_argument("-o", "--output")
    parser.add_argument("input_opm")
    option_strings = {
        opt for action in parser._actions for opt in action.option_strings
    }
    assert "--oem" not in option_strings
    assert "-d" in option_strings


def test_parse_arguments_rejects_legacy_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy propagation aliases should no longer be accepted by the CLI."""
    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "input.opm", "--oem", "out.oem"],
    )
    with pytest.raises(SystemExit):
        propagate_orbit_cli.parse_arguments()

    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-orbit",
            "--initial-state",
            "2023-04-10T00:00:00 7000 0 0 0 7.5 1.0",
        ],
    )
    with pytest.raises(SystemExit):
        propagate_orbit_cli.parse_arguments()

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "--input-state", "input.opm"],
    )
    with pytest.raises(SystemExit):
        propagate_orbit_cli.parse_arguments()
