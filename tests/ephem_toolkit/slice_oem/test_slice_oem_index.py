"""Tests for index-based slicing."""

from __future__ import annotations

import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.slice_oem import main

TEST_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = TEST_DIR.parent.parent.parent


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


def test_cli_index_slice_opm_first_state_only() -> None:
    """Test --opm emits only the first state from an index slice selection."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "5:10", "--opm"])
        assert result.returncode == 0

        _, _, output_data = opm.read_opm(io.StringIO(result.stdout), validate=False)
        assert output_data["EPOCH"].startswith("2024-01-01T00:05:00")
        assert output_data["X"] == original_oem.states[5][1][0] / 1000
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
