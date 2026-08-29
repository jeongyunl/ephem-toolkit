"""Tests for CLI argument parsing and basic functionality."""

from __future__ import annotations

import io
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem
from ephem_toolkit.slice_oem.__main__ import main

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
            # Capture the error message if it's a string
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


def test_cli_no_arguments() -> None:
    """Test that running script with no arguments fails because OEM input is required."""
    result = _run_slice_oem([])
    assert result.returncode != 0
    assert "required" in result.stderr.lower()
    assert "<input_oem|->" in result.stderr


def test_cli_help_flag() -> None:
    """Test that --help flag displays help message."""
    result = _run_slice_oem(["--help"])
    assert result.returncode == 0
    assert "Extract subsets of CCSDS OEM ephemeris data" in result.stdout
    assert "--slice" in result.stdout
    assert "--time-slice" in result.stdout
    assert "--opm" in result.stdout


def test_cli_missing_slice_argument() -> None:
    """Test that providing OEM file without slice argument fails."""
    temp_path, _ = _create_test_oem()
    try:
        result = _run_slice_oem([str(temp_path)])
        assert result.returncode != 0
        assert "either -s/--slice or -t/--time-slice must be provided" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_mutually_exclusive_slice_options() -> None:
    """Test that --slice and --time-slice cannot be used together."""
    temp_path, _ = _create_test_oem()
    try:
        result = _run_slice_oem(
            [str(temp_path), "--slice", "0:10", "--time-slice", "0,1h"]
        )
        assert result.returncode != 0
        assert "not allowed with argument" in result.stderr.lower()
    finally:
        temp_path.unlink()


def test_cli_nonexistent_file() -> None:
    """Test error handling for nonexistent input file."""
    result = _run_slice_oem(["/nonexistent/file.oem", "--slice", "0:10"])
    assert result.returncode != 0
