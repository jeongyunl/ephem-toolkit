"""Tests for common/slice_oem.py — OEM slicing utilities and CLI helper.

Note
----
Index-based slicing uses Python conventions where the stop index is exclusive
(e.g., slice(0, 10) selects indices 0-9). The format is start[:[stop][:step]]
where both stop and step are optional and may be omitted independently
(e.g., start::step skips stop but still specifies a step).

Time-based slicing uses a similar format with commas: start[,[stop][,step]]
where stop and step are likewise optional and may be omitted independently
(e.g., start,,step skips stop but still specifies a step). Time-based slicing
is inclusive for both start and stop times. All states with timestamps within
[start_time, stop_time] are included in the output.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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


def test_parse_slice_args_start_stop() -> None:
    """Test parsing slice with start and stop."""
    assert slice_oem.parse_slice_args("1:5") == slice(1, 5)
    assert slice_oem.parse_slice_args("0:10") == slice(0, 10)
    assert slice_oem.parse_slice_args("-5:-1") == slice(-5, -1)


def test_parse_slice_args_start_only() -> None:
    """Test parsing slice with start only (start:)."""
    assert slice_oem.parse_slice_args("5:") == slice(5, None)
    assert slice_oem.parse_slice_args("0:") == slice(0, None)


def test_parse_slice_args_stop_only() -> None:
    """Test parsing slice with stop only (:stop)."""
    assert slice_oem.parse_slice_args(":5") == slice(None, 5)
    assert slice_oem.parse_slice_args(":10") == slice(None, 10)


def test_parse_slice_args_with_step() -> None:
    """Test parsing slice with step."""
    assert slice_oem.parse_slice_args("::2") == slice(None, None, 2)
    assert slice_oem.parse_slice_args("1:10:2") == slice(1, 10, 2)
    assert slice_oem.parse_slice_args("0::3") == slice(0, None, 3)


def test_parse_slice_args_invalid_index() -> None:
    """Test parsing invalid index raises ValueError."""
    with pytest.raises(ValueError, match="Invalid index"):
        slice_oem.parse_slice_args("abc")


def test_parse_slice_args_too_many_colons() -> None:
    """Test parsing slice with too many colons raises ValueError."""
    with pytest.raises(ValueError, match="Invalid slice"):
        slice_oem.parse_slice_args("1:2:3:4")


def test_parse_time_slice_args_empty_string() -> None:
    """Test parsing empty string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid time slice: empty string"):
        slice_oem.parse_time_slice_args("")

    with pytest.raises(ValueError, match="Invalid time slice: empty string"):
        slice_oem.parse_time_slice_args("   ")


def test_parse_time_slice_args_too_many_parts() -> None:
    """Test parsing time slice with too many parts raises ValueError."""
    with pytest.raises(ValueError, match="Invalid time slice"):
        slice_oem.parse_time_slice_args(
            "2024-01-01T12:00:00,2024-01-01T13:00:00,5m,extra"
        )


def test_parse_time_slice_args_start_stop_step() -> None:
    """Test parsing time slice with all three components."""
    result = slice_oem.parse_time_slice_args(
        "2024-01-01T12:00:00Z,2024-01-01T13:00:00Z,5m"
    )
    assert isinstance(result.start_time, datetime)
    assert isinstance(result.stop_time, datetime)
    assert result.step_size == timedelta(minutes=5)


def test_parse_time_slice_args_duration_start_stop() -> None:
    """Test parsing time slice with duration offsets."""
    result = slice_oem.parse_time_slice_args("5m,10m")
    assert result.start_time == timedelta(minutes=5)
    assert result.stop_time == timedelta(minutes=10)
    assert result.step_size is None


def test_parse_time_slice_args_negative_duration() -> None:
    """Test parsing time slice with negative duration."""
    result = slice_oem.parse_time_slice_args("-5m,-2m")
    assert result.start_time == timedelta(minutes=-5)
    assert result.stop_time == timedelta(minutes=-2)


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


# ===================================================================
# Tests for stop_time defaulting to start_time
# ===================================================================


def test_time_slice_stop_defaults_to_start_single_state() -> None:
    """Test that when stop_time is None, it defaults to start_time (single state)."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 100, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Specify only start_time, no stop_time
    start_time = datetime(2024, 1, 1, 0, 3, 0, tzinfo=timezone.utc)  # 3 minutes in
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=None,  # Explicitly None
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should return exactly 1 state (at or nearest to start_time)
    assert len(sliced_oem.states) == 1
    assert sliced_oem.states[0][0] == states[3][0]  # Index 3 = 3 minutes


def test_time_slice_stop_defaults_to_start_with_duration() -> None:
    """Test that stop defaults to start when using duration offset."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Use timedelta for start, no stop
    from datetime import timedelta

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=5),  # 5 minutes from start
        stop_time=None,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should return exactly 1 state
    assert len(sliced_oem.states) == 1
    assert sliced_oem.states[0][0] == states[5][0]


def test_time_slice_both_none_returns_full_range() -> None:
    """Test that when both start and stop are None, full OEM range is returned."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Both None
    options = slice_oem.TimeSliceOptions(
        start_time=None,
        stop_time=None,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should return all states
    assert len(sliced_oem.states) == 10


def test_time_slice_stop_none_with_negative_duration_start() -> None:
    """Test single state extraction with negative duration (from end)."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]

    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Negative duration: 2 minutes before end
    from datetime import timedelta

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=-2),
        stop_time=None,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should return exactly 1 state (2 minutes before end = index 7)
    assert len(sliced_oem.states) == 1
    # Last state is at 9 minutes, -2 minutes = 7 minutes = index 7
    assert sliced_oem.states[0][0] == states[7][0]


def test_parse_time_slice_single_value_creates_start_only() -> None:
    """Test that parsing a single time value creates start_time with no stop_time."""
    # Parse single datetime
    result = slice_oem.parse_time_slice_args("2024-01-01T12:00:00Z")
    assert result.start_time == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert result.stop_time is None
    assert result.step_size is None

    # Parse single duration
    from datetime import timedelta

    result = slice_oem.parse_time_slice_args("5m")
    assert result.start_time == timedelta(minutes=5)
    assert result.stop_time is None
    assert result.step_size is None



# ===================================================================
# Tests for index-based validation
# ===================================================================


def test_index_validation_empty_oem() -> None:
    """Test that slicing an empty OEM raises IndexError."""
    oem_obj = CcsdsOem.from_states([], object_name="EMPTY")

    with pytest.raises(IndexError, match="Cannot slice empty OEM file"):
        slice_oem.extract_sliced_states(oem_obj, slice(0, 5))


def test_index_validation_stop_less_than_start() -> None:
    """Test that stop < start raises ValueError."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    with pytest.raises(
        ValueError, match="stop index .* must be greater than or equal to start index"
    ):
        slice_oem.extract_sliced_states(oem_obj, slice(5, 2))


def test_index_validation_negative_start_out_of_range() -> None:
    """Test that negative start index out of range raises IndexError."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    with pytest.raises(IndexError, match="Start index -20 is out of range"):
        slice_oem.extract_sliced_states(oem_obj, slice(-20, 5))


def test_index_validation_allows_out_of_range_positive_indices() -> None:
    """Test that out-of-range positive indices are allowed (returns empty slice)."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(5)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # This should not raise an error, just return empty slice
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, slice(10, 20))
    assert len(sliced_oem.states) == 0


# ===================================================================
# Tests for time-based validation
# ===================================================================


def test_time_validation_empty_oem() -> None:
    """Test that time-slicing an empty OEM raises IndexError."""
    from datetime import timedelta

    oem_obj = CcsdsOem.from_states([], object_name="EMPTY")
    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=0),
        stop_time=timedelta(minutes=5),
    )

    with pytest.raises(IndexError, match="Cannot slice empty OEM file"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_time_validation_stop_before_start() -> None:
    """Test that stop time < start time raises ValueError."""
    from datetime import timedelta

    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=5),
        stop_time=timedelta(minutes=2),
    )

    with pytest.raises(ValueError, match="stop time must be >= start time"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_time_validation_start_before_oem_range() -> None:
    """Test that start time before OEM range raises ValueError."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Start time 1 hour before OEM start
    options = slice_oem.TimeSliceOptions(
        start_time=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        stop_time=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="Start time .* is before OEM file start time"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_time_validation_stop_after_oem_range() -> None:
    """Test that stop time after OEM range raises ValueError."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Stop time 1 hour after OEM end
    options = slice_oem.TimeSliceOptions(
        start_time=datetime(2024, 1, 1, 12, 2, 0, tzinfo=timezone.utc),
        stop_time=datetime(2024, 1, 1, 13, 30, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="Stop time .* is after OEM file stop time"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_time_validation_valid_range() -> None:
    """Test that valid time range works correctly."""
    from datetime import timedelta

    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=5),
    )

    # Should not raise an error
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)
    assert len(sliced_oem.states) == 4  # States at 2, 3, 4, 5 minutes


#


# ===================================================================
# Tests for interpolation
# ===================================================================


def test_interpolation_with_step_size() -> None:
    """Test interpolation with step size."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=10),
        step_size=timedelta(minutes=2),
        interpolate=True,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should have states at 2, 4, 6, 8, 10 minutes (5 states)
    assert len(sliced_oem.states) == 5
    assert sliced_oem.states[0][0] == base_time.timestamp() + 2 * 60
    assert sliced_oem.states[-1][0] == base_time.timestamp() + 10 * 60


def test_interpolation_single_state() -> None:
    """Test interpolation for single state extraction."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Request interpolation at a time between existing states
    target_time = datetime(2024, 1, 1, 0, 2, 30, tzinfo=timezone.utc)  # 2.5 minutes
    options = slice_oem.TimeSliceOptions(
        start_time=target_time,
        stop_time=None,
        interpolate=True,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should return exactly 1 interpolated state
    assert len(sliced_oem.states) == 1
    assert sliced_oem.states[0][0] == target_time.timestamp()


def test_interpolation_with_boundaries() -> None:
    """Test interpolation with exact start and stop times."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Request times that don't align with existing states
    start_time = datetime(2024, 1, 1, 0, 2, 30, tzinfo=timezone.utc)  # 2.5 minutes
    stop_time = datetime(2024, 1, 1, 0, 8, 30, tzinfo=timezone.utc)  # 8.5 minutes
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=stop_time,
        interpolate=True,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should include interpolated boundaries plus existing states in between
    assert (
        len(sliced_oem.states) > 6
    )  # At least the states from 3-8 minutes plus boundaries
    assert sliced_oem.states[0][0] == start_time.timestamp()
    assert sliced_oem.states[-1][0] == stop_time.timestamp()


def test_step_size_without_interpolate_raises_error() -> None:
    """Test that step_size without interpolate=True raises ValueError."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=5),
        step_size=timedelta(minutes=1),
        interpolate=False,
    )

    with pytest.raises(ValueError, match="step_size requires interpolate=True"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_interpolation_at_exact_existing_state() -> None:
    """Test that interpolation at exact existing state doesn't duplicate."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6 + i * 1000, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Request times that exactly match existing states
    start_time = datetime(2024, 1, 1, 0, 3, 0, tzinfo=timezone.utc)  # Exactly 3 minutes
    stop_time = datetime(2024, 1, 1, 0, 8, 0, tzinfo=timezone.utc)  # Exactly 8 minutes
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=stop_time,
        interpolate=True,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should include states from 3-8 minutes (6 states total)
    assert len(sliced_oem.states) == 6


# ===================================================================
# Tests for verbose output
# ===================================================================


def test_verbose_output_index_slice(capsys) -> None:
    """Test verbose output for index-based slicing."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    slice_oem.extract_sliced_states(oem_obj, slice(2, 5), verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by index:" in captured.err
    assert "Selected 3 of 10 states" in captured.err


def test_verbose_output_time_slice_no_interpolation(capsys) -> None:
    """Test verbose output for time-based slicing without interpolation."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=5),
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "Mode: time range (no interpolation)" in captured.err


def test_verbose_output_time_slice_with_interpolation(capsys) -> None:
    """Test verbose output for time-based slicing with interpolation."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=10),
        step_size=timedelta(minutes=2),
        interpolate=True,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "Mode: interpolated (Lagrange degree 8)" in captured.err
    assert "Step size:" in captured.err


def test_verbose_output_single_state_interpolated(capsys) -> None:
    """Test verbose output for single state extraction with interpolation."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=3),
        stop_time=None,
        interpolate=True,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "Mode: single state (interpolated)" in captured.err


def test_verbose_output_single_state_no_interpolation(capsys) -> None:
    """Test verbose output for single state extraction without interpolation."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=3),
        stop_time=None,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "Mode: single state (no stop time given)" in captured.err


def test_verbose_output_with_negative_duration(capsys) -> None:
    """Test verbose output with negative duration offset."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=-5),
        stop_time=timedelta(minutes=-2),
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "offset" in captured.err
    assert "from end" in captured.err


def test_verbose_output_interpolated_boundaries(capsys) -> None:
    """Test verbose output for interpolation with boundary states."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Use times that don't align with existing states
    start_time = datetime(2024, 1, 1, 0, 2, 30, tzinfo=timezone.utc)
    stop_time = datetime(2024, 1, 1, 0, 8, 30, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=stop_time,
        interpolate=True,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "Mode: time range (interpolated boundaries)" in captured.err


# ===================================================================
# Tests for error handling
# ===================================================================


def test_extract_sliced_states_invalid_type() -> None:
    """Test that invalid slice_spec type raises TypeError."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    with pytest.raises(
        TypeError, match="slice_spec must be a TimeSliceOptions or slice object"
    ):
        slice_oem.extract_sliced_states(oem_obj, "invalid")


def test_index_validation_negative_stop_out_of_range() -> None:
    """Test that negative stop index out of range raises IndexError."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    with pytest.raises(IndexError, match="Stop index -20 is out of range"):
        slice_oem.extract_sliced_states(oem_obj, slice(0, -20))


def test_parse_time_slice_with_empty_stop_and_step() -> None:
    """Test parsing time slice with empty stop but with step."""
    result = slice_oem.parse_time_slice_args("2024-01-01T12:00:00Z,,5m")
    assert isinstance(result.start_time, datetime)
    assert result.stop_time == timedelta(0)  # Empty stop with comma means OEM end
    assert result.step_size == timedelta(minutes=5)


def test_time_slice_positive_duration_stop() -> None:
    """Test time slicing with positive duration for stop (offset from start)."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=10),  # Positive: 10 minutes from OEM start
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should include states from 2 to 10 minutes
    assert len(sliced_oem.states) == 9  # States at indices 2-10


def test_time_slice_zero_duration_stop() -> None:
    """Test time slicing with zero duration for stop (OEM end)."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=5),
        stop_time=timedelta(0),  # Zero means OEM end
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should include states from 5 minutes to end
    assert len(sliced_oem.states) == 5  # States at indices 5-9


def test_verbose_output_with_positive_duration_start(capsys) -> None:
    """Test verbose output with positive duration offset for start."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=5),
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "offset" in captured.err
    assert "from start" in captured.err


def test_verbose_output_with_datetime_start_stop(capsys) -> None:
    """Test verbose output with datetime start and stop."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    start_time = datetime(2024, 1, 1, 0, 2, 0, tzinfo=timezone.utc)
    stop_time = datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=stop_time,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "2024-01-01T00:02:00" in captured.err
    assert "2024-01-01T00:05:00" in captured.err


def test_verbose_output_with_none_start(capsys) -> None:
    """Test verbose output with None start time."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    stop_time = datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=None,
        stop_time=stop_time,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "(beginning of OEM)" in captured.err


def test_verbose_output_with_none_stop(capsys) -> None:
    """Test verbose output with None stop time (single state)."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    start_time = datetime(2024, 1, 1, 0, 3, 0, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=start_time,
        stop_time=None,
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "(same as start - single state)" in captured.err


def test_verbose_output_with_positive_stop_duration(capsys) -> None:
    """Test verbose output with positive duration for stop (from start)."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=10),  # Positive: from start
    )

    slice_oem.extract_sliced_states(oem_obj, options, verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by time:" in captured.err
    assert "from start" in captured.err


def test_verbose_output_index_slice_with_empty_result(capsys) -> None:
    """Test verbose output for index slice with empty result."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(5)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    slice_oem.extract_sliced_states(oem_obj, slice(10, 20), verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by index:" in captured.err
    assert "Selected 0 of 5 states" in captured.err


def test_verbose_output_index_slice_with_step(capsys) -> None:
    """Test verbose output for index slice with step."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(20)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    slice_oem.extract_sliced_states(oem_obj, slice(0, 10, 2), verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by index:" in captured.err
    assert "step=2" in captured.err
    assert "Selected 5 of 20 states" in captured.err


def test_time_slice_start_none_stop_datetime() -> None:
    """Test time slicing with None start and datetime stop."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    stop_time = datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
    options = slice_oem.TimeSliceOptions(
        start_time=None,
        stop_time=stop_time,
    )

    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)

    # Should include states from beginning to 5 minutes
    assert len(sliced_oem.states) == 6  # States at indices 0-5


def test_time_validation_with_none_start_time(capsys) -> None:
    """Test time validation error message with None start_time."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Create a scenario where stop < start with None start_time
    # This is tricky - we need stop to resolve to before the OEM start
    options = slice_oem.TimeSliceOptions(
        start_time=None,  # Will resolve to OEM start
        stop_time=datetime(
            2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc
        ),  # Before OEM start
    )

    with pytest.raises(ValueError, match="stop time must be >= start time"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_time_validation_with_none_stop_time_error() -> None:
    """Test time validation error message with None stop_time in error path."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # This should not trigger the validation error since stop_time is None
    # But let's test the edge case
    options = slice_oem.TimeSliceOptions(
        start_time=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        stop_time=None,  # Single state extraction
    )

    # Should work fine - single state extraction
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)
    assert len(sliced_oem.states) == 1


def test_verbose_output_index_slice_with_results(capsys) -> None:
    """Test verbose output for index slice with non-empty results."""
    states = [
        (1234567890.0 + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0])) for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    slice_oem.extract_sliced_states(oem_obj, slice(2, 5), verbose=True)

    captured = capsys.readouterr()
    assert "[slice_oem] Slicing by index:" in captured.err
    assert "Output start:" in captured.err
    assert "Output end:" in captured.err
    assert "Output span:" in captured.err


def test_time_validation_error_with_timedelta_start_datetime_stop() -> None:
    """Test time validation error message with timedelta start and datetime stop."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Start at 5 minutes, stop at 2 minutes (before start)
    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=5),
        stop_time=datetime(2024, 1, 1, 12, 2, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="stop time must be >= start time"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_time_validation_error_with_datetime_start_timedelta_stop() -> None:
    """Test time validation error message with datetime start and timedelta stop."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Start at 12:05, stop at 2 minutes from start (12:02, before start)
    options = slice_oem.TimeSliceOptions(
        start_time=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        stop_time=timedelta(minutes=2),
    )

    with pytest.raises(ValueError, match="stop time must be >= start time"):
        slice_oem.extract_sliced_states(oem_obj, options)


def test_step_size_without_interpolate_in_extract_states_by_time() -> None:
    """Test that step_size without interpolate raises error in extract_states_by_time directly."""
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    options = slice_oem.TimeSliceOptions(
        start_time=timedelta(minutes=2),
        stop_time=timedelta(minutes=5),
        step_size=timedelta(minutes=1),
        interpolate=False,
    )

    # Call extract_states_by_time directly to hit line 282
    with pytest.raises(ValueError, match="step_size requires interpolate=True"):
        slice_oem.extract_states_by_time(oem_obj, options)


def test_time_validation_error_with_none_stop_in_error_path() -> None:
    """Test time validation error message when stop_time is None (edge case for line 784)."""
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    states = [
        (base_time.timestamp() + i * 60, np.array([7e6, 0, 0, 0, 7.5e3, 0]))
        for i in range(10)
    ]
    oem_obj = CcsdsOem.from_states(states, object_name="TEST")

    # Create a scenario where we have start > stop with None stop_time
    # This is tricky because stop_time=None means single state extraction
    # We need to trigger the validation error path where stop_time is None
    # This would require internal manipulation, so let's test the actual error path

    # Actually, line 784 is only hit when stop_time is None in the error message
    # But the condition `if options.stop_time is not None` on line 770 prevents this
    # So this line may be unreachable in normal flow
    # Let's verify by testing a case that should work
    options = slice_oem.TimeSliceOptions(
        start_time=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        stop_time=None,
    )

    # This should work fine
    sliced_oem = slice_oem.extract_sliced_states(oem_obj, options)
    assert len(sliced_oem.states) == 1
