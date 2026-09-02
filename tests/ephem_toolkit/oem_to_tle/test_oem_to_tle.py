"""Tests for the OEM-to-TLE command wrapper."""

from __future__ import annotations

import pytest

from ephem_toolkit.oem_to_omm.oem_to_omm_cli import build_common_arg_parser
from ephem_toolkit.oem_to_tle import __main__ as oem_to_tle


@pytest.mark.parametrize("help_argument", ["-h", "--help"])
def test_help_uses_oem_to_tle_command_name(help_argument: str, capsys) -> None:
    """Help should describe the wrapper without exposing a mode option."""
    with pytest.raises(SystemExit) as error:
        oem_to_tle.main([help_argument])

    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: oem-to-tle" in help_text
    assert "--output <output_tle|->" in help_text
    assert "--mode" not in help_text


def test_build_common_arg_parser_exposes_shared_oem_tle_options() -> None:
    """The shared parser should include the OEM/TLE options used by both commands."""
    parser = build_common_arg_parser(
        prog="oem-to-tle",
        description="Convert OEM state vectors to a TLE.",
        output_dest="output_tle",
    )

    args = parser.parse_args(
        [
            "input.oem",
            "--output",
            "output.tle",
            "--fit-span",
            "90m",
            "--object-name",
            "ISS",
            "--object-id",
            "1998-067A",
            "--tle-refinement",
            "cartesian",
        ]
    )

    assert args.input_oem == "input.oem"
    assert args.output_tle == "output.tle"
    assert args.fit_span.total_seconds() == 5400
    assert args.object_name == "ISS"
    assert args.object_id == "1998-067A"
    assert args.tle_refinement == "cartesian"


def test_main_delegates_to_oem_to_omm_in_tle_mode(monkeypatch) -> None:
    """The wrapper should add the TLE conversion mode and preserve arguments."""
    delegated_arguments: list[list[str]] = []
    tle_arguments: list[list[str]] = []

    def fake_main(argv) -> None:
        delegated_arguments.append(argv)

    monkeypatch.setattr(oem_to_tle.oem_to_omm, "main", fake_main)
    monkeypatch.setattr(
        oem_to_tle.omm_to_tle,
        "main",
        lambda argv: tle_arguments.append(argv),
    )

    oem_to_tle.main(["input.oem", "-o", "output.omm", "--fit-span", "2h"])

    assert delegated_arguments == [
        ["--mode", "tle", "input.oem", "-o", "-", "--fit-span", "2h"]
    ]
    assert tle_arguments == [["-", "-o", "output.omm"]]


@pytest.mark.parametrize("mode_argument", ["--mode", "--mode=brouwer"])
def test_main_rejects_mode_argument(mode_argument: str) -> None:
    """The wrapper should rely on argparse to reject delegated mode arguments."""
    with pytest.raises(SystemExit) as error:
        oem_to_tle.main([mode_argument, "brouwer", "input.oem"])

    assert error.value.code == 2
