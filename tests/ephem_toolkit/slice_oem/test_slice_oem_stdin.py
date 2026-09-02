"""Tests for stdin input handling."""

from __future__ import annotations

import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

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
