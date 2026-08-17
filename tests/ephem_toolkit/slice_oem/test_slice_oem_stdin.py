"""Tests for stdin input handling."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
SRC_DIR: Path = PROJECT_ROOT / "src"
SLICE_OEM_SCRIPT: Path = SRC_DIR / "ephem_toolkit" / "slice_oem" / "slice_oem.py"


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SRC_DIR)
        + os.pathsep
        + str(SRC_DIR / "ephem_toolkit")
        + (os.pathsep + existing if existing else "")
    )
    return env


def _run_slice_oem(
    args: list[str], input_data: str | None = None
) -> subprocess.CompletedProcess:
    """Run slice_oem.py script with given arguments."""
    cmd = [sys.executable, str(SLICE_OEM_SCRIPT)] + args
    env = _build_env()
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
        env=env,
    )


def _create_test_oem(
    num_states: int = 20, interval_seconds: int = 60
) -> tuple[Path, oem.CcsdsOem]:
    """Create a temporary OEM file for testing."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (
            base_time.timestamp() + i * interval_seconds,
            np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]),
        )
        for i in range(num_states)
    ]

    oem_obj = oem.CcsdsOem.from_states(
        states,
        object_name="TEST_SAT",
        ref_frame="GCRF",
        center_name="EARTH",
        time_system="UTC",
    )

    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".oem", delete=False, dir=TEST_DIR
    )
    temp_path = Path(temp_file.name)
    temp_file.close()

    oem_obj.write(temp_path)
    return temp_path, oem_obj


def test_cli_stdin_with_dash() -> None:
    """Test reading from stdin using '-' as filename."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        with open(temp_path, "r") as f:
            oem_content = f.read()

        result = _run_slice_oem(["-", "--slice", "5:10"], input_data=oem_content)
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
        assert output_oem.states[0][0] == original_oem.states[5][0]
        assert output_oem.states[-1][0] == original_oem.states[9][0]
    finally:
        temp_path.unlink()


def test_cli_stdin_without_filename() -> None:
    """Test that omitting filename fails because stdin requires an explicit '-'."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        with open(temp_path, "r") as f:
            oem_content = f.read()

        result = _run_slice_oem(["--slice", "5:10"], input_data=oem_content)
        assert result.returncode != 0
        assert "required" in result.stderr.lower()
        assert "<input_oem|->" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_stdin_with_time_slice() -> None:
    """Test reading from stdin with time-based slicing."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        with open(temp_path, "r") as f:
            oem_content = f.read()

        result = _run_slice_oem(["-", "--time-slice", "5m,10m"], input_data=oem_content)
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 11
    finally:
        temp_path.unlink()


def test_cli_stdin_with_data_only_output() -> None:
    """Test reading from stdin with data-only output format."""
    temp_path, _ = _create_test_oem(num_states=10)
    try:
        with open(temp_path, "r") as f:
            oem_content = f.read()

        result = _run_slice_oem(
            ["-", "--slice", "0:3", "--data-only"], input_data=oem_content
        )
        assert result.returncode == 0

        assert "CCSDS_OEM_VERS" not in result.stdout
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3
    finally:
        temp_path.unlink()


def test_cli_stdin_with_verbose() -> None:
    """Test reading from stdin with verbose output."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        with open(temp_path, "r") as f:
            oem_content = f.read()

        result = _run_slice_oem(
            ["-", "--slice", "0:10", "--verbose"], input_data=oem_content
        )
        assert result.returncode == 0

        assert "[slice_oem]" in result.stderr
        assert "File: <stdin>" in result.stderr
        assert "Input OEM:" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_stdin_with_interpolation() -> None:
    """Test reading from stdin with interpolation."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        with open(temp_path, "r") as f:
            oem_content = f.read()

        result = _run_slice_oem(
            ["-", "--time-slice", "0,20m,5m"], input_data=oem_content
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()


def test_cli_stdin_empty_input() -> None:
    """Test error handling for empty stdin input."""
    result = _run_slice_oem(["-", "--slice", "0:10"], input_data="")
    assert result.returncode != 0


def test_cli_stdin_invalid_oem_data() -> None:
    """Test error handling for invalid OEM data from stdin."""
    invalid_data = "This is not valid OEM data\nJust some random text\n"
    result = _run_slice_oem(["-", "--slice", "0:10"], input_data=invalid_data)
    assert result.returncode != 0
