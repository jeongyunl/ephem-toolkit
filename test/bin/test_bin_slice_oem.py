"""Tests for bin/slice_oem.py — OEM slicing utility script."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import common.oem as oem

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test modules."""

PROJECT_ROOT: Path = TEST_DIR.parent.parent
"""Repository root path."""

BIN_DIR: Path = PROJECT_ROOT / "bin"
"""Directory containing executable scripts."""

SLICE_OEM_SCRIPT: Path = BIN_DIR / "slice_oem.py"
"""Path to slice_oem.py script."""

TEST_DATA_DIR: Path = PROJECT_ROOT / "test" / "data"
"""Directory containing test data files."""


# ===================================================================
# Test helpers
# ===================================================================


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")
    return env


def _run_slice_oem(
    args: list[str], input_data: str | None = None
) -> subprocess.CompletedProcess:
    """Run slice_oem.py script with given arguments.

    Parameters
    ----------
    args : list[str]
        Command-line arguments to pass to the script.
    input_data : str | None
        Optional stdin input data.

    Returns
    -------
    subprocess.CompletedProcess
        Result of the subprocess execution.
    """
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
    """Create a temporary OEM file for testing.

    Parameters
    ----------
    num_states : int
        Number of states to include in the OEM.
    interval_seconds : int
        Time interval between states in seconds.

    Returns
    -------
    tuple[Path, oem.CcsdsOem]
        Path to the temporary OEM file and the OEM object.
    """
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

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".oem", delete=False, dir=TEST_DIR
    )
    temp_path = Path(temp_file.name)
    temp_file.close()

    oem_obj.write(temp_path)
    return temp_path, oem_obj


# ===================================================================
# CLI argument parsing tests
# ===================================================================


def test_cli_no_arguments() -> None:
    """Test that running script with no arguments exits successfully (no error)."""
    result = _run_slice_oem([])
    # Script exits successfully when no arguments provided (no OEM file to process)
    assert result.returncode == 0


def test_cli_help_flag() -> None:
    """Test that --help flag displays help message."""
    result = _run_slice_oem(["--help"])
    assert result.returncode == 0
    assert "Extract subsets of CCSDS OEM ephemeris data" in result.stdout
    assert "--slice" in result.stdout
    assert "--time-slice" in result.stdout


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


# ===================================================================
# Index-based slicing tests
# ===================================================================


def test_cli_index_slice_start_stop() -> None:
    """Test index-based slicing with start and stop."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "5:10"])
        assert result.returncode == 0

        # Parse output OEM from string using StringIO
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
        assert len(output_oem.states) == 10  # Every other state
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


# ===================================================================
# Time-based slicing tests
# ===================================================================


def test_cli_time_slice_duration_offsets() -> None:
    """Test time-based slicing with duration offsets."""
    temp_path, original_oem = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Slice from 5 minutes to 10 minutes
        result = _run_slice_oem([str(temp_path), "--time-slice", "5m,10m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 6  # States at 5, 6, 7, 8, 9, 10 minutes
    finally:
        temp_path.unlink()


def test_cli_time_slice_negative_duration() -> None:
    """Test time-based slicing with negative duration (from end)."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Last 10 minutes
        result = _run_slice_oem([str(temp_path), "--time-slice=-10m,"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 11  # States from -10 to end (inclusive)
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
        # Use specific datetime range
        result = _run_slice_oem(
            [
                str(temp_path),
                "--time-slice",
                "2024-01-01T00:05:00Z,2024-01-01T00:10:00Z",
            ]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 6  # 5, 6, 7, 8, 9, 10 minutes
    finally:
        temp_path.unlink()


def test_cli_time_slice_mixed_datetime_and_duration() -> None:
    """Test time-based slicing with mixed datetime and duration."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Start at specific time, end at duration offset
        result = _run_slice_oem(
            [str(temp_path), "--time-slice", "2024-01-01T00:05:00Z,10m"]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 6  # From 5 to 10 minutes
    finally:
        temp_path.unlink()


# ===================================================================
# Interpolation tests
# ===================================================================


def test_cli_time_slice_with_step_size() -> None:
    """Test time-based slicing with step size (interpolation)."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Slice with 5-minute intervals
        result = _run_slice_oem([str(temp_path), "--time-slice", "0,30m,5m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        # Should have states at 0, 5, 10, 15, 20, 25, 30 minutes (7 states)
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
        assert len(output_oem.states) == 3  # 0, 10, 20 minutes
    finally:
        temp_path.unlink()


def test_cli_time_slice_no_interpolate_flag() -> None:
    """Test that --no-interpolate flag disables interpolation."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # This should fail because step_size requires interpolation
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
        assert len(output_oem.states) == 5  # 0, 5, 10, 15, 20 minutes
    finally:
        temp_path.unlink()


# ===================================================================
# Output format tests
# ===================================================================


def test_cli_raw_output_format() -> None:
    """Test --raw flag for raw state vector output."""
    temp_path, original_oem = _create_test_oem(num_states=10)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:3", "--raw"])
        assert result.returncode == 0

        # Raw output should be space-separated values, not OEM format
        assert "CCSDS_OEM_VERS" not in result.stdout
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3  # 3 states

        # Each line should have 7 values (timestamp + 6 state components)
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

        # Should be valid OEM format
        assert "CCSDS_OEM_VERS" in result.stdout
        assert "OBJECT_NAME" in result.stdout
        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 3
    finally:
        temp_path.unlink()


# ===================================================================
# Verbose output tests
# ===================================================================


def test_cli_verbose_flag() -> None:
    """Test --verbose flag produces debug output."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:10", "--verbose"])
        assert result.returncode == 0

        # Verbose output should go to stderr
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


# ===================================================================
# Error handling tests
# ===================================================================


def test_cli_invalid_slice_format() -> None:
    """Test error handling for invalid slice format."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "invalid"])
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


def test_cli_nonexistent_file() -> None:
    """Test error handling for nonexistent input file."""
    result = _run_slice_oem(["/nonexistent/file.oem", "--slice", "0:10"])
    assert result.returncode != 0


def test_cli_out_of_range_slice() -> None:
    """Test handling of out-of-range slice indices."""
    temp_path, _ = _create_test_oem(num_states=10)
    try:
        # This should succeed but return empty result
        result = _run_slice_oem([str(temp_path), "--slice", "100:200"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 0
    finally:
        temp_path.unlink()


def test_cli_time_slice_out_of_range() -> None:
    """Test error handling for time slice out of OEM range."""
    temp_path, _ = _create_test_oem(num_states=10, interval_seconds=60)
    try:
        # Try to slice beyond the OEM time range
        result = _run_slice_oem([str(temp_path), "--time-slice", "100h,200h"])
        assert result.returncode != 0
    finally:
        temp_path.unlink()


# ===================================================================
# Integration tests with real data
# ===================================================================


def test_cli_with_real_oem_file() -> None:
    """Test CLI with a real OEM file from test data."""
    oem_file = TEST_DATA_DIR / "LEO3.oem"
    if not oem_file.exists():
        pytest.skip(f"Test data file not found: {oem_file}")

    result = _run_slice_oem([str(oem_file), "--slice", "0:10"])
    assert result.returncode == 0

    output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
    assert len(output_oem.states) == 10


def test_cli_time_slice_with_real_oem_file() -> None:
    """Test time-based slicing with a real OEM file."""
    oem_file = TEST_DATA_DIR / "LEO3.oem"
    if not oem_file.exists():
        pytest.skip(f"Test data file not found: {oem_file}")

    # Read the file to get time range
    original_oem = oem.CcsdsOem.read(oem_file)
    if len(original_oem.states) < 2:
        pytest.skip("OEM file has insufficient states")

    # Slice first hour
    result = _run_slice_oem([str(oem_file), "--time-slice", "0,1h"])
    assert result.returncode == 0

    output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
    assert len(output_oem.states) > 0


# ===================================================================
# Metadata preservation tests
# ===================================================================


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
        # Start/stop times should be different from original
        assert output_oem.meta.start_time != original_oem.meta.start_time
        assert output_oem.meta.stop_time != original_oem.meta.stop_time
    finally:
        temp_path.unlink()


# ===================================================================
# Edge cases
# ===================================================================


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


# ===================================================================
# Complex scenarios
# ===================================================================


def test_cli_negative_step_slice() -> None:
    """Test index slicing with negative step. Unsupported."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "10:0:-1"])
        assert result.returncode != 0

    finally:
        temp_path.unlink()


def test_cli_time_slice_with_interpolation_at_boundaries() -> None:
    """Test time slicing with interpolation at non-aligned boundaries."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Use times that don't align with existing states
        result = _run_slice_oem(
            [
                str(temp_path),
                "--time-slice",
                "2024-01-01T00:02:30Z,2024-01-01T00:08:30Z",
            ]
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        # Should include interpolated boundaries plus existing states
        assert len(output_oem.states) > 6
    finally:
        temp_path.unlink()


def test_cli_large_step_size() -> None:
    """Test time slicing with large step size."""
    temp_path, _ = _create_test_oem(num_states=121, interval_seconds=60)
    try:
        # 2-hour range with 30-minute steps
        result = _run_slice_oem([str(temp_path), "--time-slice", "0,2h,30m"])
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        # Should have states at 0, 30, 60, 90, 120 minutes (5 states)
        assert len(output_oem.states) == 5
    finally:
        temp_path.unlink()


# ===================================================================
# Output redirection tests
# ===================================================================


def test_cli_output_can_be_redirected() -> None:
    """Test that output can be redirected to a file."""
    temp_path, _ = _create_test_oem(num_states=20)
    output_file = TEST_DIR / "test_output.oem"
    try:
        result = _run_slice_oem([str(temp_path), "--slice", "0:10"])
        assert result.returncode == 0

        # Write output to file
        output_file.write_text(result.stdout)

        # Read back and verify
        output_oem = oem.CcsdsOem.read(output_file)
        assert len(output_oem.states) == 10
    finally:
        temp_path.unlink()
        if output_file.exists():
            output_file.unlink()


# ===================================================================
# Cleanup
# ===================================================================


def test_cli_stdin_with_dash() -> None:
    """Test reading from stdin using '-' as filename."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        # Read the OEM file content
        with open(temp_path, "r") as f:
            oem_content = f.read()

        # Pass content via stdin with '-' as filename
        result = _run_slice_oem(["-", "--slice", "5:10"], input_data=oem_content)
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
        assert output_oem.states[0][0] == original_oem.states[5][0]
        assert output_oem.states[-1][0] == original_oem.states[9][0]
    finally:
        temp_path.unlink()


def test_cli_stdin_without_filename() -> None:
    """Test reading from stdin by omitting filename."""
    temp_path, original_oem = _create_test_oem(num_states=20)
    try:
        # Read the OEM file content
        with open(temp_path, "r") as f:
            oem_content = f.read()

        # Pass content via stdin without filename
        result = _run_slice_oem(["--slice", "5:10"], input_data=oem_content)
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5
        assert output_oem.states[0][0] == original_oem.states[5][0]
        assert output_oem.states[-1][0] == original_oem.states[9][0]
    finally:
        temp_path.unlink()


def test_cli_stdin_with_time_slice() -> None:
    """Test reading from stdin with time-based slicing."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Read the OEM file content
        with open(temp_path, "r") as f:
            oem_content = f.read()

        # Pass content via stdin with time slice
        result = _run_slice_oem(["--time-slice", "5m,10m"], input_data=oem_content)
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 6  # States at 5, 6, 7, 8, 9, 10 minutes
    finally:
        temp_path.unlink()


def test_cli_stdin_with_raw_output() -> None:
    """Test reading from stdin with raw output format."""
    temp_path, _ = _create_test_oem(num_states=10)
    try:
        # Read the OEM file content
        with open(temp_path, "r") as f:
            oem_content = f.read()

        # Pass content via stdin with raw output
        result = _run_slice_oem(["-", "--slice", "0:3", "--raw"], input_data=oem_content)
        assert result.returncode == 0

        # Raw output should not contain OEM headers
        assert "CCSDS_OEM_VERS" not in result.stdout
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3
    finally:
        temp_path.unlink()


def test_cli_stdin_with_verbose() -> None:
    """Test reading from stdin with verbose output."""
    temp_path, _ = _create_test_oem(num_states=20)
    try:
        # Read the OEM file content
        with open(temp_path, "r") as f:
            oem_content = f.read()

        # Pass content via stdin with verbose flag
        result = _run_slice_oem(["--slice", "0:10", "--verbose"], input_data=oem_content)
        assert result.returncode == 0

        # Verbose output should show <stdin> as file source
        assert "[slice_oem]" in result.stderr
        assert "File: <stdin>" in result.stderr
        assert "Input OEM:" in result.stderr
    finally:
        temp_path.unlink()


def test_cli_stdin_with_interpolation() -> None:
    """Test reading from stdin with interpolation."""
    temp_path, _ = _create_test_oem(num_states=60, interval_seconds=60)
    try:
        # Read the OEM file content
        with open(temp_path, "r") as f:
            oem_content = f.read()

        # Pass content via stdin with interpolation
        result = _run_slice_oem(
            ["-", "--time-slice", "0,20m,5m"], input_data=oem_content
        )
        assert result.returncode == 0

        output_oem = oem.CcsdsOem.read(io.StringIO(result.stdout))
        assert len(output_oem.states) == 5  # 0, 5, 10, 15, 20 minutes
    finally:
        temp_path.unlink()


def test_cli_stdin_empty_input() -> None:
    """Test error handling for empty stdin input."""
    result = _run_slice_oem(["-", "--slice", "0:10"], input_data="")
    # Should fail because no valid OEM data provided
    assert result.returncode != 0


def test_cli_stdin_invalid_oem_data() -> None:
    """Test error handling for invalid OEM data from stdin."""
    invalid_data = "This is not valid OEM data\nJust some random text\n"
    result = _run_slice_oem(["-", "--slice", "0:10"], input_data=invalid_data)
    # Should fail because data is not valid OEM format
    assert result.returncode != 0


def test_cleanup_temp_files() -> None:
    """Ensure no temporary files are left behind."""
    # This test just verifies the cleanup mechanism works
    temp_path, _ = _create_test_oem(num_states=5)
    assert temp_path.exists()
    temp_path.unlink()
    assert not temp_path.exists()
