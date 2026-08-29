"""Tests for interpolation functionality."""

from __future__ import annotations

import io
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np

import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.time_utils as time_utils
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
            [
                str(temp_path),
                "--time-slice",
                "0,,1m",
                "--data-only",
                "--interpolate-type",
                "lagrange,8",
            ]
        )
        assert result.returncode == 0
        assert (
            "Warning: input contains 7 states, fewer than the requested "
            "interpolation degree 8"
        ) in result.stderr or (
            "the degree will be reduced to fit the available data"
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
        assert "NameError" not in result.stderr
        assert "Traceback" not in result.stderr
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
            [
                str(temp_path),
                "--time-slice",
                "0,20m,5m",
                "--interpolate-type",
                "lagrange,4",
            ]
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
            [
                str(temp_path),
                "--time-slice",
                "0,20m,5m",
                "--interpolate-type",
                "lagrange,0",
            ]
        )
        assert result.returncode != 0
        assert "must be greater than 0" in result.stderr
    finally:
        temp_path.unlink()
