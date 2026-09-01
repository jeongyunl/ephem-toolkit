"""Tests for src/plot_orbit/plot_orbit.py — orbit plotting utility script."""

from __future__ import annotations

import io
import sys

from ephem_toolkit.plot_orbit.plot_orbit_cli import build_arg_parser, parse_arguments


def test_plot_orbit_help_uses_command_name_and_output_placeholder() -> None:
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
    assert "usage: plot-orbit" in help_text
    assert "--output <output_plot>" in help_text


def test_plot_orbit_uses_input_oem_attribute_name() -> None:
    """The parser should expose the positional input path under input_oem."""
    original_argv = sys.argv[:]
    try:
        sys.argv = ["plot-orbit", "orbit.oem", "-o", "orbit.png", "-d", "1h"]
        args = parse_arguments(build_arg_parser())
    finally:
        sys.argv = original_argv

    assert args.input_oem == "orbit.oem"
    assert args.output == "orbit.png"
    assert args.duration == "1h"
