"""Tests for index-based slicing."""

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


def test_cli_index_slice_start_stop() -> None:
    """Test index-based slicing with start and stop."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "5:10"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
        assert output_oem.states[0][0] == original_oem.states[5][0]
        assert output_oem.states[-1][0] == original_oem.states[9][0]
    finally:
        temp_path.unlink()


def test_cli_index_slice_single_index() -> None:
    """Test index-based slicing with single index."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "5"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 1
        assert output_oem.states[0][0] == original_oem.states[5][0]
    finally:
        temp_path.unlink()


def test_cli_index_slice_with_step() -> None:
    """Test index-based slicing with step parameter."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "::2"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 10
        assert output_oem.states[0][0] == original_oem.states[0][0]
        assert output_oem.states[1][0] == original_oem.states[2][0]
    finally:
        temp_path.unlink()


def test_cli_index_slice_negative_indices() -> None:
    """Test index-based slicing with negative indices."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice=-5"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 1
        assert output_oem.states[0][0] == original_oem.states[-5][0]
    finally:
        temp_path.unlink()


def test_cli_index_slice_start_only() -> None:
    """Test index-based slicing with start only."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "10"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 1
        assert output_oem.states[0][0] == original_oem.states[10][0]
    finally:
        temp_path.unlink()


def test_cli_index_slice_stop_only() -> None:
    """Test index-based slicing with stop only."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", ":10"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 10
        assert output_oem.states[0][0] == original_oem.states[0][0]
        assert output_oem.states[-1][0] == original_oem.states[9][0]
    finally:
        temp_path.unlink()


def test_cli_out_of_range_slice() -> None:
    """Test handling of out-of-range slice indices."""
    temp_path, _ = _create_test_oem(num_states=10)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "100:200"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 0
    finally:
        temp_path.unlink()


def test_cli_negative_step_slice() -> None:
    """Test index slicing with negative step. Unsupported."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "10:0:-1"])
        assert result.returncode != 0
    finally:
        temp_path.unlink()


def test_cli_invalid_slice_format() -> None:
    """Test error handling for invalid slice format."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "invalid"])
        assert result.returncode != 0
    finally:
        temp_path.unlink()
