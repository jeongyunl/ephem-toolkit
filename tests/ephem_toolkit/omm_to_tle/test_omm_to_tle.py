"""Tests for src/omm_to_tle/omm_to_tle.py — OMM to TLE conversion utility script."""

from __future__ import annotations

import argparse
import io
import sys

import pytest

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
        parse_arguments(
            build_arg_parser(),
            [unsupported_option, "value", "input.omm", "-o", "output.tle"],
        )

    assert error.value.code == 2
