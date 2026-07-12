"""Tests for common/slice_oem.py — OEM slicing utilities and CLI helper."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import common.oem as oem
import common.slice_oem as slice_oem
from common.oem import CcsdsOem

TEST_DIR: Path = Path(__file__).parent
"""Directory containing test modules."""

PROJECT_ROOT: Path = TEST_DIR.parent.parent
"""Repository root path."""


# ===================================================================
# Test helpers
# ===================================================================


def _build_env() -> dict[str, str]:
    """Build a test PYTHONPATH environment for running the helper script."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")
    return env


# ===================================================================
# CLI integration tests
# ===================================================================


def test_time_slice_prints_start_stop_step(tmp_path: Path) -> None:
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            "--interpolate",
            "--time-slice",
            "2026-05-20T12:00:00,2026-05-20T12:10:00,5m",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = result.stdout.strip().splitlines()
    assert lines == [
        "2026-05-20T12:00:00.000",
        "2026-05-20T12:10:00.000",
        "5m",
    ]


def test_time_slice_default_step_unit_is_minutes() -> None:
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            "--interpolate",
            "--time-slice",
            "2026-05-20T12:00:00,2026-05-20T12:10:00,5",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = result.stdout.strip().splitlines()
    assert lines == [
        "2026-05-20T12:00:00.000",
        "2026-05-20T12:10:00.000",
        "5m",
    ]


def test_time_slice_prints_empty_components_for_missing_values() -> None:
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            "--time-slice",
            ",2026-05-20T12:10:00",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = result.stdout.splitlines()
    assert lines == ["", "2026-05-20T12:10:00.000", ""]


def test_time_slice_missing_stop_returns_one_state_only() -> None:
    sample_oem: Path = TEST_DIR.parent / "data" / "ISS_2026-05-20.OEM"
    script: Path = PROJECT_ROOT / "bin" / "slice_oem.py"
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [
            sys.executable,
            str(script),
            str(sample_oem),
            "--time-slice",
            "2026-05-20T12:00:00,",
            "--raw",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )

    assert result.returncode == 0, f"slice_oem.py failed: {result.stderr}"
    lines: list[str] = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1


# ===================================================================
# slice_states() with list input
# ===================================================================


def test_slice_states_by_time_dict_ordered_and_filtered() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0

    # states is now a list of (POSIX timestamp, state) tuples, sorted by POSIX timestamp
    state1 = np.array([5.0, 4.0, 3.0, 2.0, 1.0, 0.0])
    state2 = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    state3 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    states: list[tuple[float, np.ndarray]] = [
        (ts1, state1),
        (ts2, state2),
        (ts3, state3),
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options: slice_oem.TimeSliceOptions = slice_oem.TimeSliceOptions(
        start_time=datetime.fromtimestamp(5.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(15.0, tz=timezone.utc),
    )
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    assert len(sliced_oem.states) == 2
    assert sliced_oem.states[0][0] == ts1
    assert sliced_oem.states[1][0] == ts2
    assert np.allclose(sliced_oem.states[0][1], state1, atol=1e-12, rtol=0.0)
    assert np.allclose(sliced_oem.states[1][1], state2, atol=1e-12, rtol=0.0)


def test_slice_states_with_slice_object() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0
    states: list[tuple[float, np.ndarray]] = [
        (ts1, np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])),
        (ts2, np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])),
        (ts3, np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0])),
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(1, 3))

    assert len(sliced_oem.states) == 2
    assert sliced_oem.states[0][0] == ts2
    assert sliced_oem.states[1][0] == ts3


def test_slice_states_with_time_slice_options() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0
    states: list[tuple[float, np.ndarray]] = [
        (ts1, np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])),
        (ts2, np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])),
        (ts3, np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0])),
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options: slice_oem.TimeSliceOptions = slice_oem.TimeSliceOptions(
        start_time=datetime.fromtimestamp(10.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(20.0, tz=timezone.utc),
    )
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    assert len(sliced_oem.states) == 2
    assert sliced_oem.states[0][0] == ts2
    assert sliced_oem.states[1][0] == ts3


def test_slice_states_by_time_accepts_time_slice_options() -> None:
    ts1: float = 5.0
    ts2: float = 10.0
    ts3: float = 20.0
    states: list[tuple[float, np.ndarray]] = [
        (ts1, np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])),
        (ts2, np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])),
        (ts3, np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0])),
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options: slice_oem.TimeSliceOptions = slice_oem.TimeSliceOptions(
        start_time=datetime.fromtimestamp(10.0, tz=timezone.utc),
        stop_time=datetime.fromtimestamp(20.0, tz=timezone.utc),
    )
    sliced_oem: CcsdsOem = slice_oem.extract_states_by_time(oem_obj, options)

    assert len(sliced_oem.states) == 2
    assert sliced_oem.states[0][0] == ts2
    assert sliced_oem.states[1][0] == ts3


# ===================================================================
# slice_states() with CcsdsOem input
# ===================================================================


def test_slice_states_with_ccsds_oem_preserves_metadata() -> None:
    """Test that slicing a CcsdsOem preserves metadata."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(
        states,
        object_name="TEST_SAT",
        ref_frame="GCRF",
        center_name="EARTH",
        time_system="UTC",
    )

    # Slice the OEM
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(2, 5))

    # Check that it's a CcsdsOem
    assert isinstance(sliced_oem, CcsdsOem)

    # Check that metadata is preserved
    assert sliced_oem.meta.object_name == "TEST_SAT"
    assert sliced_oem.meta.ref_frame == "GCRF"
    assert sliced_oem.meta.center_name == "EARTH"
    assert sliced_oem.meta.time_system == "UTC"

    # Check that states are sliced correctly
    assert len(sliced_oem) == 3
    assert sliced_oem.states[0][0] == states[2][0]
    assert sliced_oem.states[2][0] == states[4][0]


def test_slice_states_with_ccsds_oem_returns_ccsds_oem() -> None:
    """Test that slicing a CcsdsOem returns a CcsdsOem."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(5)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="SAT")
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(0, 3))

    assert isinstance(sliced_oem, CcsdsOem)
    assert len(sliced_oem) == 3


def test_slice_states_with_ccsds_oem_negative_indices() -> None:
    """Test slicing CcsdsOem with negative indices."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="SAT")

    # Last 3 states
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(-3, None))

    assert isinstance(sliced_oem, CcsdsOem)
    assert len(sliced_oem) == 3
    assert sliced_oem.states[0][0] == states[-3][0]


def test_slice_states_with_ccsds_oem_step() -> None:
    """Test slicing CcsdsOem with step parameter."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="SAT")

    # Every other state
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(None, None, 2))

    assert isinstance(sliced_oem, CcsdsOem)
    assert len(sliced_oem) == 5
    assert sliced_oem.states[0][0] == states[0][0]
    assert sliced_oem.states[1][0] == states[2][0]


def test_slice_states_with_ccsds_oem_empty_slice() -> None:
    """Test slicing CcsdsOem with empty result."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(5)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="SAT")

    # Empty slice
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(10, 20))

    assert isinstance(sliced_oem, CcsdsOem)
    assert len(sliced_oem) == 0


def test_slice_states_with_ccsds_oem_preserves_all_metadata_fields() -> None:
    """Test that all metadata fields are preserved during slicing."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(5)
    ]

    oem_obj = CcsdsOem.from_states(
        states,
        object_name="COMPLEX_SAT",
        ref_frame="J2000",
        center_name="MARS",
        time_system="GPS",
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(1, 4))

    # Verify all metadata fields
    assert sliced_oem.meta.object_name == "COMPLEX_SAT"
    assert sliced_oem.meta.ref_frame == "J2000"
    assert sliced_oem.meta.center_name == "MARS"
    assert sliced_oem.meta.time_system == "GPS"


def test_slice_states_with_ccsds_oem_updates_start_stop_times() -> None:
    """Test that start/stop times are updated based on sliced states."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="SAT")
    original_start = oem_obj.meta.start_time
    original_stop = oem_obj.meta.stop_time

    # Slice to middle portion
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(3, 7))

    # Start/stop times should be updated
    assert sliced_oem.meta.start_time != original_start
    assert sliced_oem.meta.stop_time != original_stop

    # Should correspond to sliced states
    assert "2009-02-13" in sliced_oem.meta.start_time  # Timestamp 1234567890 + 3*60


def test_slice_states_with_time_slice_options_on_ccsds_oem() -> None:
    """Test slicing CcsdsOem with TimeSliceOptions."""
    # Create states with known timestamps
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="SAT")

    # Create time slice options
    start_time = datetime(2024, 1, 1, 0, 2, 0, tzinfo=timezone.utc)  # 2 minutes in
    stop_time = datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)  # 5 minutes in

    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=stop_time,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    assert isinstance(sliced_oem, CcsdsOem)
    assert sliced_oem.meta.object_name == "SAT"
    # Should include states at indices 2, 3, 4, 5 (4 states)
    assert len(sliced_oem) == 4


# ===================================================================
# parse_slice_args() utility
# ===================================================================


def test_parse_slice_single_index_returns_slice() -> None:
    assert slice_oem.parse_slice_args("5") == slice(5, 6)
    assert slice_oem.parse_slice_args("-2") == slice(-2, -1)
    assert slice_oem.parse_slice_args("-1") == slice(-1, None)


# ===================================================================
# Integration tests
# ===================================================================


def test_integration_read_slice_write() -> None:
    """Test complete workflow: read OEM, slice, write."""
    # Create original OEM
    states = [
        (1234567890.0 + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]

    oem_obj = CcsdsOem.from_states(
        states,
        object_name="INTEGRATION_TEST",
        ref_frame="GCRF",
    )

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".oem", delete=False) as f:
        temp_path = Path(f.name)

    try:
        oem_obj.write(temp_path)

        # Read back
        oem_read = CcsdsOem.read(temp_path)

        # Slice
        sliced_oem = slice_oem.extract_sliced_states(oem_read, slice(5, 15))

        # Write sliced version
        sliced_path = temp_path.with_suffix(".sliced.oem")
        sliced_oem.write(sliced_path)

        # Read sliced version
        final_oem = CcsdsOem.read(sliced_path)

        # Verify
        assert len(final_oem) == 10
        assert final_oem.meta.object_name == "INTEGRATION_TEST"
        assert final_oem.meta.ref_frame == "GCRF"

        # Clean up
        sliced_path.unlink()
    finally:
        temp_path.unlink()
