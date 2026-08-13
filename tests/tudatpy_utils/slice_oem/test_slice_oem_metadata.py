"""Tests for metadata preservation and edge cases."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import tudatpy_utils.core.ccsds.oem as oem

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
SRC_DIR: Path = PROJECT_ROOT / "src"
SLICE_OEM_SCRIPT: Path = SRC_DIR / "tudatpy_utils" / "slice_oem" / "slice_oem.py"
TEST_DATA_DIR: Path = PROJECT_ROOT / "tests" / "data"


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


def test_cli_preserves_metadata() -> None:
    """Test that slicing preserves OEM metadata."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "5:10"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert output_oem.meta.object_name == original_oem.meta.object_name
        assert output_oem.meta.ref_frame == original_oem.meta.ref_frame
        assert output_oem.meta.center_name == original_oem.meta.center_name
        assert output_oem.meta.time_system == original_oem.meta.time_system
    finally:
        temp_path.unlink()


def test_cli_updates_time_range_metadata() -> None:
    """Test that slicing updates start/stop time metadata."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "5:10"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert output_oem.meta.start_time != original_oem.meta.start_time
        assert output_oem.meta.stop_time != original_oem.meta.stop_time
    finally:
        temp_path.unlink()


def test_cli_empty_slice_result() -> None:
    """Test handling of slice that results in no states."""
    temp_path, _ = _create_test_oem(num_states=10)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "100:200"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 0
    finally:
        temp_path.unlink()


def test_cli_single_state_slice() -> None:
    """Test slicing that results in a single state."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "10"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 1
        assert output_oem.states[0][0] == original_oem.states[10][0]
    finally:
        temp_path.unlink()


def test_cli_full_range_slice() -> None:
    """Test slicing entire range (no-op)."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", ":"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == len(original_oem.states)
    finally:
        temp_path.unlink()


def test_cli_with_real_oem_file() -> None:
    """Test CLI with a real OEM file from test data."""
    oem_file = TEST_DATA_DIR / "JPSS-1_small.oem"
    if not oem_file.exists():
        pytest.skip(f"Test data file not found: {oem_file}")

    result = _run_slice_oem([str(oem_file), "--slice", "0:10"])
    assert result.returncode == 0

    output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
    assert len(output_oem.states) == 10


def test_cli_time_slice_with_real_oem_file() -> None:
    """Test time-based slicing with a real OEM file."""
    oem_file = TEST_DATA_DIR / "JPSS-1_small.oem"
    if not oem_file.exists():
        pytest.skip(f"Test data file not found: {oem_file}")

    original_oem = oem.CcsdsOem.read(oem_file)
    if len(original_oem.states) < 2:
        pytest.skip("OEM file has insufficient states")

    result = _run_slice_oem([str(oem_file), "--time-slice", "0,1h"])
    assert result.returncode == 0

    output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
    assert len(output_oem.states) > 0


def test_cleanup_temp_files() -> None:
    """Ensure no temporary files are left behind."""
    temp_path, _ = _create_test_oem(num_states=5)
    assert temp_path.exists()
    temp_path.unlink()
    assert not temp_path.exists()
