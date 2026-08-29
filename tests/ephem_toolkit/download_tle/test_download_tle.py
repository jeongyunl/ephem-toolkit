"""Tests for src/download_tle/download_tle.py — TLE download utility script."""

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


def test_download_tle_help_uses_command_name_and_satellite_id_option() -> None:
    """The CLI help should use the canonical command name and satellite-id option."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.download_tle.__main__",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
        check=False,
    )

    assert result.returncode == 0
    assert "usage: download-tle" in result.stdout
    assert "--satellite-id <id>" in result.stdout
