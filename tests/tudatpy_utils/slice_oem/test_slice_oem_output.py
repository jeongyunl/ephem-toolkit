"""Tests for output formats and options."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import tudatpy_utils.core.ccsds.oem as oem

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
SRC_DIR: Path = PROJECT_ROOT / "src"
SLICE_OEM_SCRIPT: Path = SRC_DIR / "tudatpy_utils" / "slice_oem" / "slice_oem.py"


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SRC_DIR)
        + os.pathsep
        + str(SRC_DIR / "tudatpy_utils")
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


def test_cli_data_only_output_format() -> None:
    """Test --data-only flag for state vector output."""
    temp_path, original_oem = _create_test_oem(num_states=10)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:3", "--data-only"])
        assert result.returncode == 0

        assert "CCSDS_OEM_VERS" not in result.stdout
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            values = line.split()
            assert len(values) == 7
    finally:
        temp_path.unlink()


def test_cli_default_oem_output_format() -> None:
    """Test default OEM format output."""
    temp_path, _ = _create_test_oem(num_states=10)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:3"])
        assert result.returncode == 0

        assert "CCSDS_OEM_VERS" in result.stdout
        assert "OBJECT_NAME" in result.stdout
        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 3
    finally:
        temp_path.unlink()


def test_cli_verbose_flag() -> None:
    """Test --verbose flag produces debug output."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:10", "--verbose"])
        assert result.returncode == 0

        assert "[slice_oem]" in result.stderr
        assert "Input OEM:" in result.stderr
        assert "States:" in result.stderr
        assert "Slicing by index:" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_verbose_shows_time_range() -> None:
    """Test verbose output shows time range information."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:10", "-v"])
        assert result.returncode == 0

        assert "Start:" in result.stderr
        assert "End:" in result.stderr
        assert "Span:" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_output_can_be_redirected() -> None:
    """Test that output can be redirected to a file."""
    temp_path, _ = _create_test_oem(num_states=20)
    output_file = TEST_DIR / "test_output.oem"
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:10"])
        assert result.returncode == 0

        output_file.write_text(result.stdout)

        output_oem = oem.CcsdsOem.read(output_file)
        assert len(output_oem.states) == 10
    finally:
        temp_path.unlink()
        if output_file.exists():
            output_file.unlink()


def test_cli_output_flag_to_file() -> None:
    """Test --output flag writes to specified file."""
    temp_path, _ = _create_test_oem(num_states=20)
    output_file = TEST_DIR / "test_output_flag.oem"
    try:
        result = _run_slice_oem(
            [str(temp_path), "--slice", "0:10", "-o", str(output_file)]
        )
        assert result.returncode == 0
        assert output_file.exists()

        output_oem = oem.CcsdsOem.read(output_file)
        assert len(output_oem.states) == 10
    finally:
        temp_path.unlink()
        if output_file.exists():
            output_file.unlink()


def test_cli_output_flag_stdout() -> None:
    """Test --output=- writes to stdout."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:10", "--output", "-"])
        assert result.returncode == 0
        assert "CCSDS_OEM_VERS" in result.stdout

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 10
    finally:
        temp_path.unlink()
