"""Tests for src/plot_orbit_deltas/plot_orbit_deltas.py — Orbit plotting utility script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

from ephem_toolkit.plot_orbit_deltas.data_structures import StateHistory
from ephem_toolkit.plot_orbit_deltas.plot_orbit_deltas_cli import parse_arguments
from ephem_toolkit.plot_orbit_deltas.plotting import plot_orbits

PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent


def _build_env() -> dict[str, str]:
    """Build environment dictionary with PYTHONPATH set to the source root."""
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    source_root = PROJECT_ROOT / "src"
    env["PYTHONPATH"] = (
        os.pathsep.join([str(source_root), existing]) if existing else str(source_root)
    )
    return env


def test_plot_orbit_deltas_help_uses_command_name_and_output_placeholder() -> None:
    """The CLI help should use the canonical command name and output placeholder."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.plot_orbit_deltas.__main__",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
        check=False,
    )

    assert result.returncode == 0
    assert "usage: plot-orbit-deltas" in result.stdout
    assert "--output <output_plot>" in result.stdout


def test_plot_orbit_deltas_parse_arguments_sets_input_oem_files() -> None:
    """The positional OEM arguments should populate the expected attribute name."""
    sample_files = ["tmp/leo3_aug_aa.oem", "tmp/leo3_aug_ab.oem"]

    with patch.object(sys, "argv", ["plot-orbit-deltas", *sample_files]):
        args = parse_arguments()

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
