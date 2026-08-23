"""Integration tests for OEM to OPM conversion."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
TEST_DATA_DIR: Path = TEST_DIR.parent.parent / "data"


def _build_env() -> dict[str, str]:
    """Build an environment with the project source roots on PYTHONPATH."""
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    source_roots = [
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "src" / "ephem_toolkit",
    ]
    env["PYTHONPATH"] = os.pathsep.join(
        [*(str(path) for path in source_roots), existing]
        if existing
        else [*(str(path) for path in source_roots)]
    )
    return env


def test_oem_to_opm_requires_input_file_name() -> None:
    """The CLI should require an explicit input filename or '-' for stdin."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.oem_to_opm.oem_to_opm",
            "-o",
            "-",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode != 0
    assert "required: <input_oem|->" in result.stderr.lower()

    stdin_oem = (TEST_DATA_DIR / "ISS_2026-05-20_small.OEM").read_text(encoding="utf-8")
    stdin_result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            "-m",
            "ephem_toolkit.oem_to_opm.oem_to_opm",
            "-",
            "--output",
            "-",
        ],
        input=stdin_oem,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert stdin_result.returncode == 0, stdin_result.stderr
    assert "CCSDS_OPM_VERS" in stdin_result.stdout
