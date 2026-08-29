"""Tests for metadata preservation and edge cases."""

from __future__ import annotations

import io
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.slice_oem.__main__ import main

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent
TEST_DATA_DIR: Path = TEST_DIR.parent.parent / "data"


class CliResult:
    """Mock subprocess.CompletedProcess for direct function calls."""

    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_slice_oem(args: list[str], input_data: str | None = None) -> CliResult:
    """Run slice_oem main function with given arguments."""
    output_args = [] if "--output" in args or "-o" in args else ["--output", "-"]
    argv = args + output_args

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with (
        patch("sys.stdout", stdout_capture),
        patch("sys.stderr", stderr_capture),
        patch("sys.stdin", io.StringIO(input_data or "")),
    ):
        try:
            main(argv)
            returncode = 0
        except SystemExit as e:
            if isinstance(e.code, str):
                stderr_capture.write(e.code + "\n")
                returncode = 1
            else:
                returncode = e.code if isinstance(e.code, int) else (1 if e.code else 0)
        except Exception as ex:
            stderr_capture.write(str(ex) + "\n")
            returncode = 1

    return CliResult(returncode, stdout_capture.getvalue(), stderr_capture.getvalue())


def _create_test_oem(
    num_states: int = 20, interval_seconds: int = 60
) -> tuple[Path, oem.CcsdsOem]:
    """Create a temporary OEM file for testing."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (
            time_utils.datetime_to_tt_s(base_time) + i * interval_seconds,
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
