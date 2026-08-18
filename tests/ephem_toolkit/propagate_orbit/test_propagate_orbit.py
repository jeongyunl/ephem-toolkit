"""Tests for the propagate-orbit CLI and migration conventions."""

from __future__ import annotations

import pytest

from ephem_toolkit.propagate_orbit import propagate_orbit_cli


def test_parse_arguments_accepts_canonical_input_and_output_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical propagation CLI should accept --initial-state, --output, and --duration."""
    state_line = "2023-04-10T00:00:00 7000 0 0 0 7.5 1.0"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "--initial-state", state_line, "--duration", "2h"],
    )
    args = propagate_orbit_cli.parse_arguments()
    assert args.initial_state == state_line
    assert args.output_oem == "-"
    assert args.duration == 7200.0

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "--initial-state", state_line, "--output", "out.oem"],
    )
    args = propagate_orbit_cli.parse_arguments()
    assert args.initial_state == state_line
    assert args.output_oem == "out.oem"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "--initial-state", state_line, "-d", "3h"],
    )
    args = propagate_orbit_cli.parse_arguments()
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
    assert "--initial-state" in captured.out
    assert "--output" in captured.out
    assert "--duration" in captured.out
    assert "-d" in captured.out
    parser = propagate_orbit_cli.parse_arguments.__globals__["cli"].create_parser(
        "demo tool"
    )
    parser.add_argument("-d", "--duration")
    parser.add_argument("-o", "--output")
    parser.add_argument("-i", "--initial-state")
    option_strings = {
        opt for action in parser._actions for opt in action.option_strings
    }
    assert "--oem" not in option_strings
    assert "-d" in option_strings


def test_parse_arguments_rejects_legacy_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy propagation aliases should no longer be accepted by the CLI."""
    state_line = "2023-04-10T00:00:00 7000 0 0 0 7.5 1.0"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "--oem", "out.oem", "--initial-state", state_line],
    )
    with pytest.raises(SystemExit):
        propagate_orbit_cli.parse_arguments()

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-orbit", "--input-state", state_line],
    )
    with pytest.raises(SystemExit):
        propagate_orbit_cli.parse_arguments()
