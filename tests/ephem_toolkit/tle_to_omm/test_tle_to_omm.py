"""Tests for src/tle_to_omm/tle_to_omm.py — TLE to OMM conversion utility script."""

from __future__ import annotations

import io
import sys

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
