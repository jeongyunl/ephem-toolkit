"""Tests for src/plot_dep_vars/plot_dependent_variables.py — Dependent variable plotting utility script."""

from __future__ import annotations

import io
import sys

from ephem_toolkit.plot_dep_vars.plot_dependent_variables_cli import (
    build_arg_parser,
    parse_arguments,
)


def test_plot_dependent_variables_help_uses_command_name() -> None:
    """The CLI help should use the canonical command name."""
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
    assert "usage: plot-dependent-variables" in help_text
