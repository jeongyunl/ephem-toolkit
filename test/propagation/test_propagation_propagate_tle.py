"""Tests for propagation/propagate_tle.py — TLE propagation utility script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent
TEST_DATA_DIR: Path = TEST_DIR.parent / "data"

TLE_FILES: list[Path] = sorted(TEST_DATA_DIR.glob("*.tle"))


def _build_env() -> dict[str, str]:
    """Build environment dictionary with PYTHONPATH set to project root.

    Returns
    -------
    dict[str, str]
        Environment dictionary with updated PYTHONPATH.
    """
    env: dict[str, str] = os.environ.copy()
    existing: str = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + ((":" + existing) if existing else "")
    return env


def run_propagate_tle(tle_path: Path) -> str:
    """Run propagate_tle.py script and return output.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to propagate.

    Returns
    -------
    str
        Standard output from propagate_tle.py script.
    """
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "propagation" / "propagate_tle.py"),
            str(tle_path),
            "-d",
            "1d",
            "-s",
            "15m",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )
    assert (
        result.returncode == 0
    ), f"propagate_tle.py failed for {tle_path.name}:\n{result.stderr}"
    assert (
        result.stdout.strip()
    ), f"propagate_tle.py produced no output for {tle_path.name}"
    return result.stdout


@pytest.mark.parametrize("tle_path", TLE_FILES, ids=[p.name for p in TLE_FILES])
def test_propagate_tle_produces_valid_state_vectors(tle_path: Path) -> None:
    """Should propagate each TLE for 1 day and produce valid OEM-like state vectors.

    Parameters
    ----------
    tle_path : Path
        Path to TLE file to test.
    """
    oem_text: str = run_propagate_tle(tle_path)
    lines: list[str] = [line for line in oem_text.strip().splitlines() if line.strip()]
    assert (
        len(lines) >= 90
    ), f"Expected ~97 state lines, got {len(lines)} for {tle_path.name}"
    for line in lines[:5]:
        parts: list[str] = line.split()
        assert len(parts) == 7, f"Expected 7 fields per line, got {len(parts)}: {line}"
