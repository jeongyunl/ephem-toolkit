"""Tests for src/tle_info/tle_info.py — TLE information utility script."""

from __future__ import annotations

import io
import sys

from ephem_toolkit.tle_info.tle_info_cli import parse_arguments


def test_tle_info_help_uses_command_name() -> None:
    """The CLI help should use the canonical command name."""
    old_stdout = sys.stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    try:
        parse_arguments(["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    help_text = captured_output.getvalue()
    assert "usage: tle-info" in help_text
