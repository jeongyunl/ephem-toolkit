"""Tests for src/plot_dep_vars/plot_dependent_variables.py — Dependent variable plotting utility script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent


def _build_env() -> dict[str, str]:
    """Build environment dictionary with PYTHONPATH set to the source root."""
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    source_root = PROJECT_ROOT / "src"
    env["PYTHONPATH"] = os.pathsep.join([str(source_root), existing]) if existing else str(source_root)
    return env


def test_plot_dependent_variables_help_uses_command_name() -> None:
    """The CLI help should use the canonical command name."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.plot_dep_vars.plot_dependent_variables",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
        check=False,
    )

    assert result.returncode == 0
    assert "usage: plot-dependent-variables" in result.stdout
