"""Tests for time-based slicing."""

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


def test_cli_time_slice_duration_offsets() -> None:
    """Test time-based slicing with duration offsets."""
    temp_path, original_oem = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "5m,10m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 11
    finally:
        temp_path.unlink()


def test_cli_time_slice_negative_duration() -> None:
    """Test time-based slicing with negative duration (from end)."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice=-10m,"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 11
    finally:
        temp_path.unlink()


def test_cli_time_slice_single_time() -> None:
    """Test time-based slicing with single time (single state)."""
    temp_path, original_oem = _create_test_oem(num_states=20, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "5m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 1
        assert output_oem.states[0][0] == original_oem.states[5][0]
    finally:
        temp_path.unlink()


def test_cli_time_slice_iso8601_datetime() -> None:
    """Test time-based slicing with ISO 8601 datetime strings."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [
                str(temp_path),
                "--time-slice",
                "2024-01-01T00:05:00Z,2024-01-01T00:10:00Z",
            ]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 6
    finally:
        temp_path.unlink()


def test_cli_time_slice_mixed_datetime_and_duration() -> None:
    """Test time-based slicing with mixed datetime and duration."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "2024-01-01T00:05:00Z,10m"]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 11
    finally:
        temp_path.unlink()


def test_cli_time_slice_out_of_range() -> None:
    """Test error handling for time slice out of OEM range."""
    temp_path, _ = _create_test_oem(num_states=10, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "100h,200h"])
        assert result.returncode != 0
    finally:
        temp_path.unlink()


def test_cli_invalid_time_slice_format() -> None:
    """Test error handling for invalid time slice format."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "invalid,format"])
        assert result.returncode != 0
    finally:
        temp_path.unlink()


def test_cli_time_slice_with_interpolation_at_boundaries() -> None:
    """Test time slicing with interpolation at non-aligned boundaries."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [
                str(temp_path),
                "--time-slice",
                "2024-01-01T00:02:30Z,2024-01-01T00:08:30Z",
            ]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) > 6
    finally:
        temp_path.unlink()


def test_cli_large_step_size() -> None:
    """Test time slicing with large step size."""
    temp_path, _ = _create_test_oem(num_states=121, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "0,2h,30m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()
