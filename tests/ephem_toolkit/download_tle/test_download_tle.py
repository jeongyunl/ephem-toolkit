"""Tests for src/download_tle/download_tle.py — TLE download utility script."""

from __future__ import annotations

import io
import sys

from ephem_toolkit.download_tle.download_tle_cli import (
    build_arg_parser,
    parse_arguments,
)


def test_download_tle_help_uses_command_name_and_positional_satellite_ids() -> None:
    """The CLI help should show positional satellite IDs."""
    captured_output = io.StringIO()

    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass

    # Capture help output by redirecting stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output
    try:
        parse_arguments(build_arg_parser(), ["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    help_text = captured_output.getvalue()
    assert "usage: download-tle" in help_text
    assert "<id> [<id> ...]" in help_text
