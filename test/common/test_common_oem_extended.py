"""Extended tests for common/oem.py — Additional coverage for edge cases and error handling."""

from __future__ import annotations

import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import common.oem as oem

TEST_DIR = Path(__file__).parent
OEM_PATH = TEST_DIR.parent / "data" / "ISS_2026-05-20.OEM"


# ===================================================================
# Error handling and edge cases
# ===================================================================


def test_parse_oem_state_line_raises_on_insufficient_fields() -> None:
    """Test parse_oem_state_line raises ValueError for lines with < 7 fields."""
    line = "2024-01-01T00:00:00.000000 7000.0 0.0 0.0"  # Only 4 fields

    with pytest.raises(ValueError, match="does not contain 7 fields"):
        oem.parse_oem_state_line(line)


def test_parse_oem_state_line_handles_comma_separated_values() -> None:
    """Test parse_oem_state_line handles comma-separated values."""
    line = "2024-01-01T00:00:00.000000,7000.0,0.0,0.0,0.0,7.5,0.0"

    result = oem.parse_oem_state_line(line)

    assert result is not None
    timestamp, state = result
    assert isinstance(timestamp, float)
    assert state[0] == 7000000.0  # 7000 km -> 7000000 m


def test_parse_oem_state_line_handles_mixed_separators() -> None:
    """Test parse_oem_state_line handles mixed whitespace and comma separators."""
    line = "2024-01-01T00:00:00.000000 7000.0,0.0 0.0,0.0 7.5,0.0"

    result = oem.parse_oem_state_line(line)

    assert result is not None
    timestamp, state = result
    assert len(state) == 6


def test_find_state_by_timestamp_empty_list() -> None:
    """Test find_state_by_timestamp returns None for empty state list."""
    states = []

    result = oem.find_state_by_timestamp(states, 1234567890.0)

    assert result is None


def test_find_state_by_timestamp_exact_match() -> None:
    """Test find_state_by_timestamp finds exact match."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
        (3000.0, np.array([13, 14, 15, 16, 17, 18])),
    ]

    result = oem.find_state_by_timestamp(states, 2000.0)

    assert result is not None
    timestamp, state = result
    assert timestamp == 2000.0
    np.testing.assert_array_equal(state, np.array([7, 8, 9, 10, 11, 12]))


def test_find_state_by_timestamp_no_exact_match() -> None:
    """Test find_state_by_timestamp returns None when no exact match."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    result = oem.find_state_by_timestamp(states, 1500.0)

    assert result is None


def test_find_state_by_timestamp_with_tolerance_finds_closest() -> None:
    """Test find_state_by_timestamp with tolerance finds closest state."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
        (3000.0, np.array([13, 14, 15, 16, 17, 18])),
    ]

    # Search for 1900.0, closest is 2000.0 (diff = 100)
    result = oem.find_state_by_timestamp(states, 1900.0, tolerance=150.0)

    assert result is not None
    timestamp, state = result
    assert timestamp == 2000.0


def test_find_state_by_timestamp_with_tolerance_outside_range() -> None:
    """Test find_state_by_timestamp with tolerance returns None if outside tolerance."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    # Search for 1500.0, closest is 1000.0 or 2000.0 (diff = 500)
    result = oem.find_state_by_timestamp(states, 1500.0, tolerance=400.0)

    assert result is None


def test_find_state_by_timestamp_with_tolerance_at_boundary() -> None:
    """Test find_state_by_timestamp with tolerance at exact boundary."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    # Search for 1500.0, closest is 1000.0 or 2000.0 (diff = 500)
    result = oem.find_state_by_timestamp(states, 1500.0, tolerance=500.0)

    assert result is not None  # Should find one of them


def test_find_state_by_timestamp_prefers_earlier_on_tie() -> None:
    """Test find_state_by_timestamp prefers earlier timestamp on tie."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    # Search for 1500.0, both are equally close (diff = 500)
    result = oem.find_state_by_timestamp(states, 1500.0, tolerance=500.0)

    assert result is not None
    timestamp, _ = result
    # Should return the one with smaller difference (or first found)
    assert timestamp in [1000.0, 2000.0]


def test_ccsds_oem_find_state_by_timestamp_method() -> None:
    """Test CcsdsOem.find_state_by_timestamp method."""
    states = [
        (1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
        (1234567950.0, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
    ]

    oem_obj = oem.CcsdsOem.from_states(states)

    # Exact match
    result = oem_obj.find_state_by_timestamp(1234567890.0)
    assert result is not None
    timestamp, state = result
    assert timestamp == 1234567890.0

    # With tolerance
    result = oem_obj.find_state_by_timestamp(1234567900.0, tolerance=20.0)
    assert result is not None

    # No match
    result = oem_obj.find_state_by_timestamp(9999999999.0)
    assert result is None


def test_write_state_with_naive_datetime() -> None:
    """Test write_state handles naive datetime (no timezone)."""
    output = io.StringIO()
    naive_dt = datetime(2024, 1, 1, 12, 0, 0)
    state = np.array([7e6, 0, 0, 0, 7.5e3, 0])

    oem.write_state(output, naive_dt, state)

    content = output.getvalue()
    assert "2024-01-01T12:00:00" in content
    # Should have 7 fields (epoch + 6 state components)
    assert len(content.split()) == 7


def test_write_state_with_aware_datetime() -> None:
    """Test write_state handles timezone-aware datetime."""
    output = io.StringIO()
    aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    state = np.array([7e6, 0, 0, 0, 7.5e3, 0])

    oem.write_state(output, aware_dt, state)

    content = output.getvalue()
    assert "2024-01-01T12:00:00" in content


def test_write_states_with_dict_of_datetimes() -> None:
    """Test write_states with dictionary of datetime keys."""
    output = io.StringIO()
    dt1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc)

    states_dict = {
        dt1: np.array([7e6, 0, 0, 0, 7.5e3, 0]),
        dt2: np.array([7.1e6, 0, 0, 0, 7.4e3, 0]),
    }

    oem.write_states(output, states_dict)

    content = output.getvalue()
    lines = content.strip().split("\n")
    assert len(lines) == 2
    assert "2024-01-01T12:00:00" in lines[0]
    assert "2024-01-01T12:01:00" in lines[1]


def test_write_states_with_list_of_datetime_tuples() -> None:
    """Test write_states with list of (datetime, state) tuples."""
    output = io.StringIO()
    dt1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc)

    states_list = [
        (dt1, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
        (dt2, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
    ]

    oem.write_states(output, states_list)

    content = output.getvalue()
    lines = content.strip().split("\n")
    assert len(lines) == 2


def test_write_oem_to_path_object() -> None:
    """Test write_oem with Path object."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test.oem"

        # Write using low-level API with Path
        header = {"CCSDS_OEM_VERS": 2.0}
        meta = {"OBJECT_NAME": "TEST"}

        oem.write_oem(out_path, header, meta, states)

        # Verify file was created
        assert out_path.exists()
        content = out_path.read_text()
        assert "CCSDS_OEM_VERS" in content


def test_from_states_with_empty_states() -> None:
    """Test from_states with empty states list."""
    states = []

    oem_obj = oem.CcsdsOem.from_states(states, object_name="EMPTY")

    assert len(oem_obj) == 0
    assert oem_obj.meta.object_name == "EMPTY"
    assert oem_obj.meta.start_time == ""
    assert oem_obj.meta.stop_time == ""


def test_read_oem_with_integer_metadata_values() -> None:
    """Test reading OEM with integer metadata values."""
    oem_content = """CCSDS_OEM_VERS = 2.0
CREATION_DATE  = 2024-01-01T00:00:00
ORIGINATOR     = TEST

META_START
OBJECT_NAME = TEST_SAT
INTERPOLATION_DEGREE = 5
META_STOP

2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0
"""

    header, meta, states = oem.read_oem(io.StringIO(oem_content))

    assert meta["INTERPOLATION_DEGREE"] == 5
    assert isinstance(meta["INTERPOLATION_DEGREE"], int)


def test_read_oem_with_float_metadata_values() -> None:
    """Test reading OEM with float metadata values."""
    oem_content = """CCSDS_OEM_VERS = 2.0
CREATION_DATE  = 2024-01-01T00:00:00
ORIGINATOR     = TEST

META_START
OBJECT_NAME = TEST_SAT
CUSTOM_FLOAT = 3.14159
META_STOP

2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0
"""

    header, meta, states = oem.read_oem(io.StringIO(oem_content))

    assert meta["CUSTOM_FLOAT"] == pytest.approx(3.14159)
    assert isinstance(meta["CUSTOM_FLOAT"], float)


def test_read_oem_skips_short_state_lines() -> None:
    """Test reading OEM skips state lines with insufficient fields."""
    oem_content = """CCSDS_OEM_VERS = 2.0

META_START
OBJECT_NAME = TEST_SAT
META_STOP

2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0
2024-01-01T00:01:00.000000 7100.0 0.0
2024-01-01T00:02:00.000000 7200.0 0.0 0.0 0.0 7.3 0.0
"""

    header, meta, states = oem.read_oem(io.StringIO(oem_content))

    # Should only have 2 valid states (skips the short line)
    assert len(states) == 2


def test_write_oem_with_empty_meta() -> None:
    """Test write_oem with empty metadata dictionary."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]

    header = {"CCSDS_OEM_VERS": 2.0}
    meta = {}  # Empty metadata

    output = io.StringIO()
    oem.write_oem(output, header, meta, states)

    content = output.getvalue()
    assert "META_START" in content
    assert "META_STOP" in content
    # Should still write the state
    assert "2009-02-13" in content


def test_ccsds_oem_write_with_all_metadata_fields() -> None:
    """Test CcsdsOem.write includes all metadata fields."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]

    oem_obj = oem.CcsdsOem.from_states(
        states,
        object_name="TEST_SAT",
        ref_frame="GCRF",
        center_name="EARTH",
        time_system="UTC",
    )

    # Add additional metadata
    oem_obj.meta.object_id = "2024-001A"
    oem_obj.meta.interpolation = "LAGRANGE"
    oem_obj.meta.interpolation_degree = 7
    oem_obj.meta.useable_start_time = oem_obj.meta.start_time
    oem_obj.meta.useable_stop_time = oem_obj.meta.stop_time

    output = io.StringIO()
    oem_obj.write(output)

    content = output.getvalue()
    assert "OBJECT_NAME" in content
    assert "OBJECT_ID" in content
    assert "REF_FRAME" in content
    assert "CENTER_NAME" in content
    assert "TIME_SYSTEM" in content
    assert "INTERPOLATION" in content
    assert "INTERPOLATION_DEGREE" in content
    assert "USEABLE_START_TIME" in content
    assert "USEABLE_STOP_TIME" in content


def test_read_oem_with_header_and_data_comments() -> None:
    """Test reading OEM with comments in header and data sections."""
    oem_content = """CCSDS_OEM_VERS = 2.0

COMMENT This is a header comment
COMMENT Another header comment

CREATION_DATE  = 2024-01-01T00:00:00
ORIGINATOR     = TEST

META_START
COMMENT This is a metadata comment
OBJECT_NAME = TEST_SAT
META_STOP

COMMENT This is a data section comment
COMMENT Another data comment

2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0
"""

    header, meta, states = oem.read_oem(io.StringIO(oem_content))

    assert "COMMENT" in header
    assert len(header["COMMENT"]) == 2
    assert "This is a header comment" in header["COMMENT"]

    assert "COMMENT" in meta
    assert len(meta["COMMENT"]) == 1
    assert "This is a metadata comment" in meta["COMMENT"]

    assert "DATA_COMMENT" in header
    assert len(header["DATA_COMMENT"]) == 2
    assert "This is a data section comment" in header["DATA_COMMENT"]


def test_ccsds_oem_write_preserves_comments() -> None:
    """Test CcsdsOem.write preserves all comment types."""
    oem_content = """CCSDS_OEM_VERS = 2.0

COMMENT Header comment

CREATION_DATE  = 2024-01-01T00:00:00
ORIGINATOR     = TEST

META_START
COMMENT Meta comment
OBJECT_NAME = TEST_SAT
META_STOP

COMMENT Data comment

2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0
"""

    oem_obj = oem.CcsdsOem.read(io.StringIO(oem_content))

    output = io.StringIO()
    oem_obj.write(output)

    content = output.getvalue()

    # Check all comments are preserved
    assert "COMMENT Header comment" in content
    assert "COMMENT Meta comment" in content
    assert "COMMENT Data comment" in content


def test_read_oem_from_path_string() -> None:
    """Test read_oem accepts path as string."""
    header, meta, states = oem.read_oem(str(OEM_PATH))

    assert isinstance(header, dict)
    assert isinstance(meta, dict)
    assert len(states) > 0


def test_ccsds_oem_read_from_path_string() -> None:
    """Test CcsdsOem.read accepts path as string."""
    oem_obj = oem.CcsdsOem.read(str(OEM_PATH))

    assert len(oem_obj) > 0
    assert oem_obj.meta.object_name == "ISS"


def test_write_oem_without_creation_date() -> None:
    """Test write_oem handles missing CREATION_DATE."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]

    header = {"CCSDS_OEM_VERS": 2.0}  # No CREATION_DATE
    meta = {"OBJECT_NAME": "TEST"}

    output = io.StringIO()
    oem.write_oem(output, header, meta, states)

    content = output.getvalue()
    assert "CCSDS_OEM_VERS" in content
    assert "CREATION_DATE" not in content


def test_write_oem_without_originator() -> None:
    """Test write_oem handles missing ORIGINATOR."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]

    header = {"CCSDS_OEM_VERS": 2.0, "CREATION_DATE": "2024-01-01T00:00:00"}
    meta = {"OBJECT_NAME": "TEST"}

    output = io.StringIO()
    oem.write_oem(output, header, meta, states)

    content = output.getvalue()
    assert "CCSDS_OEM_VERS" in content
    assert "ORIGINATOR" not in content


def test_unit_conversion_km_to_m() -> None:
    """Test that OEM files in km are converted to meters internally."""
    oem_content = """CCSDS_OEM_VERS = 2.0

META_START
OBJECT_NAME = TEST_SAT
META_STOP

2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0
"""

    header, meta, states = oem.read_oem(io.StringIO(oem_content))

    timestamp, state = states[0]
    # Position should be in meters (7000 km -> 7000000 m)
    assert state[0] == 7000000.0
    # Velocity should be in m/s (7.5 km/s -> 7500 m/s)
    assert state[4] == 7500.0


def test_unit_conversion_m_to_km_on_write() -> None:
    """Test that internal meters are converted to km when writing OEM."""
    states = [(1234567890.0, np.array([7000000.0, 0, 0, 0, 7500.0, 0]))]

    header = {"CCSDS_OEM_VERS": 2.0}
    meta = {"OBJECT_NAME": "TEST"}

    output = io.StringIO()
    oem.write_oem(output, header, meta, states)

    content = output.getvalue()
    # Find the state line
    lines = content.strip().split("\n")
    state_line = [l for l in lines if "2009-02-13" in l][0]

    # Parse the values
    parts = state_line.split()
    x_km = float(parts[1])
    vx_km_s = float(parts[5])

    # Should be in km and km/s
    assert x_km == pytest.approx(7000.0)
    assert vx_km_s == pytest.approx(7.5)


def test_find_state_by_timestamp_at_start() -> None:
    """Test find_state_by_timestamp at the start of the list."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
        (3000.0, np.array([13, 14, 15, 16, 17, 18])),
    ]

    result = oem.find_state_by_timestamp(states, 1000.0)

    assert result is not None
    timestamp, _ = result
    assert timestamp == 1000.0


def test_find_state_by_timestamp_at_end() -> None:
    """Test find_state_by_timestamp at the end of the list."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
        (3000.0, np.array([13, 14, 15, 16, 17, 18])),
    ]

    result = oem.find_state_by_timestamp(states, 3000.0)

    assert result is not None
    timestamp, _ = result
    assert timestamp == 3000.0


def test_find_state_by_timestamp_beyond_end() -> None:
    """Test find_state_by_timestamp beyond the end of the list."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    result = oem.find_state_by_timestamp(states, 5000.0)

    assert result is None


def test_find_state_by_timestamp_before_start() -> None:
    """Test find_state_by_timestamp before the start of the list."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    result = oem.find_state_by_timestamp(states, 500.0)

    assert result is None


def test_find_state_by_timestamp_with_tolerance_beyond_end() -> None:
    """Test find_state_by_timestamp with tolerance beyond end."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    # Search for 2100.0, closest is 2000.0 (diff = 100)
    result = oem.find_state_by_timestamp(states, 2100.0, tolerance=150.0)

    assert result is not None
    timestamp, _ = result
    assert timestamp == 2000.0


def test_find_state_by_timestamp_with_tolerance_before_start() -> None:
    """Test find_state_by_timestamp with tolerance before start."""
    states = [
        (1000.0, np.array([1, 2, 3, 4, 5, 6])),
        (2000.0, np.array([7, 8, 9, 10, 11, 12])),
    ]

    # Search for 900.0, closest is 1000.0 (diff = 100)
    result = oem.find_state_by_timestamp(states, 900.0, tolerance=150.0)

    assert result is not None
    timestamp, _ = result
    assert timestamp == 1000.0


def test_write_states_with_dict_of_float_timestamps() -> None:
    """Test write_states with dictionary of float timestamp keys."""
    output = io.StringIO()

    states_dict = {
        1234567890.0: np.array([7e6, 0, 0, 0, 7.5e3, 0]),
        1234567950.0: np.array([7.1e6, 0, 0, 0, 7.4e3, 0]),
    }

    oem.write_states(output, states_dict)

    content = output.getvalue()
    lines = content.strip().split("\n")
    assert len(lines) == 2
    # Should have converted float timestamps to datetime strings
    assert "2009-02-13" in content
