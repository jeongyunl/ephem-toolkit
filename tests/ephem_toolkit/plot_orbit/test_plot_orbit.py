"""Tests for src/plot_orbit/plot_orbit.py — orbit plotting utility script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ephem_toolkit.plot_orbit.plot_orbit_cli import parse_arguments

PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent


def _build_env() -> dict[str, str]:
    """Build environment dictionary with PYTHONPATH set to the source root."""
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    source_root = PROJECT_ROOT / "src"
    env["PYTHONPATH"] = os.pathsep.join([str(source_root), existing]) if existing else str(source_root)
    return env


def test_plot_orbit_help_uses_command_name_and_output_placeholder() -> None:
    """The CLI help should use the canonical command name and output placeholder."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.plot_orbit.plot_orbit",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
        check=False,
    )

    assert result.returncode == 0
    assert "usage: plot-orbit" in result.stdout
    assert "--output <output_plot|->" in result.stdout


def test_plot_orbit_uses_input_oem_attribute_name() -> None:
    """The parser should expose the positional input path under input_oem."""
    original_argv = sys.argv[:]
    try:
        sys.argv = ["plot-orbit", "orbit.oem", "-o", "orbit.png", "-d", "1h"]
        args = parse_arguments()
    finally:
        sys.argv = original_argv

    assert args.input_oem == "orbit.oem"
    assert args.output == "orbit.png"
    assert args.duration == "1h"
