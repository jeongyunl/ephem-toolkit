"""Tests for interpolation functionality."""

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


def test_cli_time_slice_with_step_size() -> None:
    """Test time-based slicing with step size (interpolation)."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "0,30m,5m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 7
    finally:
        temp_path.unlink()


def test_cli_time_slice_interpolation_enabled_by_default() -> None:
    """Test that interpolation is enabled by default when step size is provided."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem([str(temp_path), "--time-slice", "0,20m,10m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 3
    finally:
        temp_path.unlink()


def test_cli_warns_when_input_has_fewer_states_than_interpolation_degree() -> None:
    """Test warning for interpolation with fewer input states than requested degree."""
    temp_path, _ = _create_test_oem(num_states=7, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "0,,1m", "--data-only", "--interpolate-type", "lagrange,8"]
        )
        assert result.returncode == 0
        assert (
            "Warning: input contains 7 states, fewer than the requested "
            "interpolation degree 8"
        ) in result.stderr
    finally:
        temp_path.unlink()


def test_cli_time_slice_no_interpolate_flag() -> None:
    """Test that --no-interpolate flag disables interpolation."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "0,20m,10m", "--no-interpolate"]
        )
        assert result.returncode != 0
        assert "step_size requires --interpolate" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_time_slice_interpolate_flag_explicit() -> None:
    """Test explicit --interpolate flag."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "0,20m,5m", "--interpolate"]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()


def test_cli_interpolate_type_lagrange() -> None:
    """Test --interpolate-type=lagrange option."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [
                str(temp_path),
                "--time-slice",
                "0,20m,5m",
                "--interpolate-type",
                "lagrange",
            ]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()


def test_cli_interpolate_type_hermite() -> None:
    """Test --interpolate-type=hermite option."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [
                str(temp_path),
                "--time-slice",
                "0,20m,5m",
                "--interpolate-type",
                "hermite",
            ]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()


def test_cli_interpolate_degree() -> None:
    """Test --interpolate-type with custom degree."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "0,20m,5m", "--interpolate-type", "lagrange,4"]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()


def test_cli_interpolate_degree_invalid() -> None:
    """Test --interpolate-type with invalid degree value."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "0,20m,5m", "--interpolate-type", "lagrange,1"]
        )
        assert result.returncode != 0
        assert "must be 2 or greater" in result.stderr
    finally:
        temp_path.unlink()
