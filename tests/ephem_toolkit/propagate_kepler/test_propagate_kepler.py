"""Tests for the propagate-kepler CLI and migration conventions."""

from __future__ import annotations

import pytest

from ephem_toolkit.propagate_kepler import propagate_kepler
from ephem_toolkit.propagate_kepler import propagate_kepler_cli


def test_parse_arguments_accepts_canonical_propagation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical Kepler command should accept the propagation-family flag names."""
    state_line = "2026-05-29T00:00:00.000000 6793.456 0.001234 0.9013 4.094 2.155 0.797"

    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-kepler",
            "--initial-state",
            state_line,
            "--duration",
            "2h",
            "--output",
            "-",
        ],
    )
    args = propagate_kepler_cli.parse_arguments()
    assert args.initial_state == state_line
    assert args.duration_s == 7200.0
    assert args.output_oem == "-"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-kepler", "--initial-state", state_line, "--output", "out.oem"],
    )
    args = propagate_kepler_cli.parse_arguments()
    assert args.initial_state == state_line
    assert args.output_oem == "out.oem"

    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-kepler",
            "--initial-state",
            state_line,
            "-d",
            "3h",
            "--output",
            "-",
        ],
    )
    args = propagate_kepler_cli.parse_arguments()
    assert args.duration_s == 10800.0


def test_parse_arguments_help_uses_project_standard_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Kepler help output should advertise the shared propagation names."""
    monkeypatch.setattr("sys.argv", ["propagate-kepler", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        propagate_kepler_cli.parse_arguments()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--initial-state" in captured.out
    assert "--output" in captured.out
    assert "--duration" in captured.out
    assert "-d" in captured.out
    assert "--input-file" not in captured.out


def test_parse_arguments_rejects_legacy_kepler_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy positional and old-style Kepler aliases should no longer be accepted."""
    state_line = "2026-05-29T00:00:00.000000 6793.456 0.001234 0.9013 4.094 2.155 0.797"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-kepler", "kepler_state.txt", "--duration", "2h"],
    )
    with pytest.raises(SystemExit):
        propagate_kepler_cli.parse_arguments()

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-kepler", "--input-file", state_line],
    )
    with pytest.raises(SystemExit):
        propagate_kepler_cli.parse_arguments()


def test_script_parse_arguments_accepts_canonical_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The console entry script should expose the canonical propagation-family parser."""
    state_line = "2026-05-29T00:00:00.000000 6793.456 0.001234 0.9013 4.094 2.155 0.797"

    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-kepler",
            "--initial-state",
            state_line,
            "--duration",
            "2h",
            "--output",
            "-",
        ],
    )
    args = propagate_kepler.parse_arguments()
    assert args.initial_state == state_line
    assert args.duration_s == 7200.0
    assert args.output_oem == "-"


def test_read_kepler_input_accepts_inline_state_line() -> None:
    """Inline Kepler states should parse into a datetime and a 6-element vector."""
    state_line = "2026-05-29T00:00:00.000000 6793.456 0.001234 0.9013 4.094 2.155 0.797"
    epoch_dt, kepler_km, object_name = propagate_kepler.read_kepler_input(state_line)

    assert object_name == "INITIAL_STATE"
    assert kepler_km.shape == (6,)
    assert epoch_dt.tzinfo is not None
    assert kepler_km[0] == pytest.approx(6793.456)
    assert kepler_km[1] == pytest.approx(0.001234)
    assert kepler_km[2] == pytest.approx(0.9013)
