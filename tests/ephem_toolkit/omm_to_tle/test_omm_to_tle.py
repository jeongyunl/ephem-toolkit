"""Tests for src/omm_to_tle/omm_to_tle.py — OMM to TLE conversion utility script."""

from __future__ import annotations

import argparse
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


def test_omm_to_tle_help_uses_command_name_and_format_aware_output() -> None:
    """The CLI help should use the canonical command name and output placeholder."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.omm_to_tle.omm_to_tle",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
        check=False,
    )

    assert result.returncode == 0
    assert "usage: omm-to-tle" in result.stdout
    assert "--output <output_tle|->" in result.stdout


def test_omm_to_tle_cli_uses_typed_namespace(monkeypatch) -> None:
    """The parser should return a typed Namespace subclass with the parsed fields."""
    from ephem_toolkit.omm_to_tle.omm_to_tle_cli import OmmToTleArgs, parse_arguments

    monkeypatch.setattr(sys, "argv", ["omm-to-tle", "input.omm", "-o", "output.tle"])

    args = parse_arguments()

    assert issubclass(OmmToTleArgs, argparse.Namespace)
    assert isinstance(args, OmmToTleArgs)
    assert args.input_omm == "input.omm"
    assert args.output_tle == "output.tle"
