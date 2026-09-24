"""Tests for the propagate-kepler CLI and migration conventions."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ephem_toolkit.core.ccsds import oem
from ephem_toolkit.core.ccsds import opm
from ephem_toolkit.core.propagator import kepler
import ephem_toolkit.core.cli as core_cli
import ephem_toolkit.propagate_kepler.__main__ as propagate_kepler_entry
from ephem_toolkit.propagate_kepler import (
    propagate_kepler_elements,
    read_kepler_input,
)
import ephem_toolkit.propagate_kepler.propagate_kepler_cli as propagate_kepler_cli


def test_parse_arguments_accepts_canonical_propagation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical Kepler command should accept the propagation-family flag names."""
    input_opm = "input.opm"

    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-kepler",
            input_opm,
            "--duration",
            "2h",
            "--output",
            "-",
        ],
    )
    args = propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())
    assert args.input_opm == input_opm
    assert args.duration_s == 7200.0
    assert args.output_oem == "-"

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-kepler", input_opm, "--output", "out.oem"],
    )
    args = propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())
    assert args.input_opm == input_opm
    assert args.output_oem == "out.oem"

    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-kepler",
            input_opm,
            "-d",
            "3h",
            "--output",
            "-",
        ],
    )
    args = propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())
    assert args.duration_s == 10800.0


def test_parse_arguments_help_uses_project_standard_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Kepler help output should advertise the shared propagation names."""
    monkeypatch.setattr("sys.argv", ["propagate-kepler", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "input_opm" in captured.out
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
        propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())

    monkeypatch.setattr(
        "sys.argv",
        ["propagate-kepler", "--input-file", state_line],
    )
    with pytest.raises(SystemExit):
        propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())


def test_script_parse_arguments_accepts_canonical_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The console entry script should expose the canonical propagation-family parser."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "propagate-kepler",
            "input.opm",
            "--duration",
            "2h",
            "--output",
            "-",
        ],
    )
    args = propagate_kepler_cli.parse_arguments(propagate_kepler_cli.build_arg_parser())
    assert args.input_opm == "input.opm"
    assert args.duration_s == 7200.0
    assert args.output_oem == "-"


def test_read_kepler_input_reads_opm_file() -> None:
    """OPM Keplerian elements should parse into the propagator's vector format."""
    opm_path = Path(__file__).parents[2] / "opm" / "sample4.opm"
    epoch_dt, kepler_km, output_metadata = read_kepler_input(str(opm_path))

    assert output_metadata == {
        "object_name": "EUTELSAT W4",
        "ref_frame": "TOD",
        "center_name": "EARTH",
        "time_system": "UTC",
    }
    assert kepler_km.shape == (6,)
    assert epoch_dt.tzinfo is not None
    assert kepler_km[0] == pytest.approx(41399.5123)
    assert kepler_km[1] == pytest.approx(0.020842611)
    assert kepler_km[2] == pytest.approx(0.117746 * 3.141592653589793 / 180.0)


def test_read_kepler_input_reads_opm_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The '-' input source should parse OPM content from stdin."""
    opm_path = Path(__file__).parents[2] / "opm" / "sample4.opm"
    monkeypatch.setattr("sys.stdin", io.StringIO(opm_path.read_text(encoding="utf-8")))

    _, kepler_km, output_metadata = read_kepler_input("-")

    assert output_metadata["object_name"] == "EUTELSAT W4"
    assert kepler_km[5] == pytest.approx(41.922339 * 3.141592653589793 / 180.0)


def test_read_kepler_input_rejects_tty_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

    with pytest.raises(ValueError, match="OPM input not provided"):
        read_kepler_input("-")


def test_read_kepler_input_rejects_empty_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(" \n"))

    with pytest.raises(ValueError, match="Empty stdin input"):
        read_kepler_input(None)


def test_read_kepler_input_requires_keplerian_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        opm.CcsdsOpm,
        "from_source",
        lambda _source: SimpleNamespace(keplerian_elements=None),
    )

    with pytest.raises(ValueError, match="does not contain Keplerian elements"):
        read_kepler_input("unused.opm")


def test_propagate_kepler_writes_cartesian_states_in_si_units(
    tmp_path: Path,
) -> None:
    """The OEM writer should receive propagated states in meters and m/s."""
    opm_path = Path(__file__).parents[2] / "opm" / "sample4.opm"
    epoch_dt, kepler_km, output_metadata = read_kepler_input(str(opm_path))
    expected_kepler_m = kepler_km.copy()
    expected_kepler_m[kepler.SEMI_MAJOR_AXIS_INDEX] *= 1000.0
    expected_state_m_m_s = kepler.keplerian_to_cartesian(expected_kepler_m)

    output_path = tmp_path / "propagated.oem"
    propagate_kepler_elements(
        initial_epoch=epoch_dt,
        initial_kepler_km=kepler_km,
        duration_s=900.0,
        step_s=900.0,
        data_only=False,
        output_metadata=output_metadata,
        output_path=str(output_path),
    )

    generated_oem = oem.CcsdsOem.read(output_path)
    _, generated_state_m_m_s = generated_oem.states[0]
    np.testing.assert_allclose(generated_state_m_m_s, expected_state_m_m_s, rtol=1e-12)
    assert (
        "EPHEMERIS_PROVENANCE: source=OPM; transformation=propagation; "
        "target_model=two-body-kepler" in generated_oem.meta.comments
    )


def test_propagate_kepler_main_routes_parsed_input_and_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_epoch = object()
    initial_elements = np.arange(6, dtype=float)
    metadata = {"object_name": "SATELLITE"}
    calls = []
    monkeypatch.setattr(
        propagate_kepler_entry.propagate_kepler_cli,
        "parse_arguments",
        lambda _parser, _argv: type(
            "Args",
            (),
            {
                "duration_s": 120.0,
                "step_s": 30.0,
                "input_opm": "input.opm",
                "output_oem": "output.oem",
                "data_only": True,
            },
        )(),
    )
    monkeypatch.setattr(
        propagate_kepler_entry,
        "read_kepler_input",
        lambda _source: (initial_epoch, initial_elements, metadata),
    )
    monkeypatch.setattr(
        propagate_kepler_entry,
        "propagate_kepler_elements",
        lambda **kwargs: calls.append(kwargs),
    )

    result = propagate_kepler_entry.main([])

    assert result == 0
    assert calls == [
        {
            "initial_epoch": initial_epoch,
            "initial_kepler_km": initial_elements,
            "duration_s": 120.0,
            "step_s": 30.0,
            "data_only": True,
            "output_metadata": metadata,
            "output_path": "output.oem",
        }
    ]


@pytest.mark.parametrize(
    ("duration_s", "step_s", "message"),
    [(0.0, 1.0, "--duration must be > 0"), (1.0, 0.0, "--step must be > 0")],
)
def test_propagate_kepler_main_rejects_nonpositive_duration_or_step(
    monkeypatch: pytest.MonkeyPatch, duration_s: float, step_s: float, message: str
) -> None:
    args = type("Args", (), {"duration_s": duration_s, "step_s": step_s})()
    monkeypatch.setattr(
        propagate_kepler_entry.propagate_kepler_cli,
        "parse_arguments",
        lambda _parser, _argv: args,
    )

    with pytest.raises(ValueError, match=message):
        propagate_kepler_entry.main([])


def test_propagate_kepler_cli_uses_shared_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_main = propagate_kepler_entry.main
    calls = []
    monkeypatch.setattr(
        core_cli,
        "run_cli",
        lambda main_func, argv: calls.append((main_func, argv)) or 23,
    )

    assert propagate_kepler_entry.cli(["input.opm"]) == 23
    assert calls == [(expected_main, ["input.opm"])]
