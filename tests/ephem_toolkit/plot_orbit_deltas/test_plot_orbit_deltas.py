"""Tests for src/plot_orbit_deltas/plot_orbit_deltas.py — Orbit plotting utility script."""

from __future__ import annotations

import io
import sys
from unittest.mock import patch

import numpy as np

from ephem_toolkit.plot_orbit_deltas.data_structures import StateHistory
from ephem_toolkit.plot_orbit_deltas.plot_orbit_deltas_cli import (
    build_arg_parser,
    parse_arguments,
)
from ephem_toolkit.plot_orbit_deltas.plotting import plot_orbits


def test_plot_orbit_deltas_help_uses_command_name_and_output_placeholder() -> None:
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
    assert "usage: plot-orbit-deltas" in help_text
    assert "--output <output_plot>" in help_text


def test_plot_orbit_deltas_parse_arguments_sets_input_oem_files() -> None:
    """The positional OEM arguments should populate the expected attribute name."""
    sample_files = ["tmp/leo3_aug_aa.oem", "tmp/leo3_aug_ab.oem"]

    with patch.object(sys, "argv", ["plot-orbit-deltas", *sample_files]):
        args = parse_arguments(build_arg_parser())

    assert args.input_oem_files == sample_files


def test_plot_orbits_skips_empty_comparison_histories() -> None:
    """Comparison orbits with no valid timestamps should not crash the absolute orbit plot."""
    reference_state_history = StateHistory(
        label="reference",
        state_history={
            0.0: np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            1.0: np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        },
    )
    empty_comparison = StateHistory(label="empty", state_history={})

    plot_orbits(reference_state_history, [empty_comparison], output_file=None)
