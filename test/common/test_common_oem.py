"""Tests for common/oem.py — OEM parsing, writing, and class API."""

from __future__ import annotations

import io
import tempfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

import common.oem as oem

TEST_DIR = Path(__file__).parent
OEM_PATH = TEST_DIR.parent / "data" / "ISS_2026-05-20.OEM"


# ===================================================================
# 1. Read OEM test file (low-level)
# ===================================================================


def test_read_oem_from_test_file_returns_header_meta_states() -> None:
    """Should parse the sample OEM file into header, meta, and state list."""
    header, meta, states = oem.read_oem(OEM_PATH)

    assert isinstance(header, dict)
    assert isinstance(meta, dict)
    assert isinstance(states, list)
    assert header["CCSDS_OEM_VERS"] == pytest.approx(2.0)
    assert "CREATION_DATE" in header
    assert "ORIGINATOR" in header
    assert meta["OBJECT_NAME"] == "ISS"
    assert meta["OBJECT_ID"] == "1998-067-A"
    assert meta["CENTER_NAME"] == "Earth"
    assert meta["REF_FRAME"] == "EME2000"
    assert meta["TIME_SYSTEM"] == "UTC"
    assert len(states) > 0

    # states is now a list of (POSIX timestamp, state) tuples
    first_timestamp, first_state = states[0]
    assert isinstance(first_timestamp, float)
    assert isinstance(first_state, np.ndarray)
    assert first_state.shape == (6,)


# ===================================================================
# 2. Read OEM from stream (low-level)
# ===================================================================


def test_read_oem_from_stream_matches_file_read() -> None:
    """Should produce identical parsed content from a text stream."""
    text = OEM_PATH.read_text(encoding="utf-8")

    header1, meta1, states1 = oem.read_oem(OEM_PATH)
    header2, meta2, states2 = oem.read_oem(io.StringIO(text))

    assert header2 == header1
    assert meta2 == meta1
    assert len(states2) == len(states1)
    for (epoch1, state1), (epoch2, state2) in zip(states1, states2):
        assert epoch1 == epoch2
        assert np.allclose(state2, state1, atol=1e-12, rtol=0.0)


# ===================================================================
# 3. Write/read round-trip with low-level API
# ===================================================================


def test_write_oem_round_trip_preserves_content(tmp_path: Path) -> None:
    """Should preserve header, meta, and state vectors through write/read."""
    header1, meta1, states1 = oem.read_oem(OEM_PATH)
    out_path = tmp_path / "roundtrip.oem"

    oem.write_oem(out_path, header1, meta1, states1)
    header2, meta2, states2 = oem.read_oem(out_path)

    assert header2 == header1
    assert meta2 == meta1
    assert len(states2) == len(states1)
    for (epoch1, state1), (epoch2, state2) in zip(states1, states2):
        assert epoch1 == epoch2
        assert np.allclose(state2, state1, atol=1e-9, rtol=0.0)


# ===================================================================
# 4. CcsdsOem.read() — new primary API
# ===================================================================


def test_ccsds_oem_read_exposes_structured_fields() -> None:
    """CcsdsOem.read() should load the sample OEM into structured fields."""
    ccsds_oem = oem.CcsdsOem.read(OEM_PATH)

    assert isinstance(ccsds_oem.header, oem.OemHeader)
    assert isinstance(ccsds_oem.meta, oem.OemMeta)
    assert len(ccsds_oem) > 0
    assert len(ccsds_oem.epochs) == len(ccsds_oem)
    assert ccsds_oem.state_vectors.shape == (len(ccsds_oem), 6)
    assert ccsds_oem.header.version == pytest.approx(2.0)
    assert ccsds_oem.meta.object_name == "ISS"
    assert ccsds_oem.meta.object_id == "1998-067-A"
    assert ccsds_oem.meta.ref_frame == "EME2000"
    assert isinstance(ccsds_oem.states, list)
    assert len(ccsds_oem.states) == len(ccsds_oem)
    first_epoch, first_state = ccsds_oem.states[0]
    assert isinstance(first_epoch, float)
    assert isinstance(first_state, np.ndarray)
    assert first_state.shape == (6,)


def test_ccsds_oem_read_from_stream() -> None:
    """CcsdsOem.read() should accept a text stream."""
    text = OEM_PATH.read_text(encoding="utf-8")
    ccsds_oem = oem.CcsdsOem.read(io.StringIO(text))

    assert len(ccsds_oem) > 0
    assert ccsds_oem.meta.object_name == "ISS"


# ===================================================================
# 5. CcsdsOem.write() — new primary API
# ===================================================================


def test_ccsds_oem_write_round_trip_preserves_structured_content(
    tmp_path: Path,
) -> None:
    """CcsdsOem.write() should preserve structured OEM content through serialization."""
    oem1 = oem.CcsdsOem.read(OEM_PATH)
    out_path = tmp_path / "class_roundtrip.oem"

    oem1.write(out_path)
    oem2 = oem.CcsdsOem.read(out_path)

    assert oem2.header == oem1.header
    assert oem2.meta == oem1.meta
    assert oem2.epochs == oem1.epochs
    assert np.allclose(oem2.state_vectors, oem1.state_vectors, atol=1e-9, rtol=0.0)


def test_ccsds_oem_write_to_stream() -> None:
    """CcsdsOem.write() should write to a text stream."""
    oem1 = oem.CcsdsOem.read(OEM_PATH)
    output = io.StringIO()
    oem1.write(output)
    content = output.getvalue()

    assert "CCSDS_OEM_VERS" in content
    assert "META_START" in content
    assert "ISS" in content


# ===================================================================
# 6. Deprecated API still works (backward compatibility)
# ===================================================================


# ===================================================================
# 7. __repr__ includes key summary fields
# ===================================================================


def test_ccsds_oem_repr_contains_summary_information() -> None:
    """Should include object name, frame, and epoch count in repr output."""
    ccsds_oem = oem.CcsdsOem.read(OEM_PATH)
    text = repr(ccsds_oem)

    assert "CcsdsOem" in text
    assert ccsds_oem.meta.object_name in text
    assert ccsds_oem.meta.ref_frame in text
    assert str(len(ccsds_oem)) in text


# ===================================================================
# 8. Round-trip regression test using module helper
# ===================================================================


def _round_trip_test_oem(source: Path) -> dict:
    """Perform a read/write/read round-trip test for an OEM file.

    Parameters
    ----------
    source : Path
        Path to the OEM file to test.

    Returns
    -------
    dict
        Dictionary with key ``'overall_ok'`` (bool) indicating whether all
        round-trip checks passed (header, metadata, and state vectors).
    """
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        lowlevel_path = tmp / "roundtrip_lowlevel.oem"
        class_path = tmp / "roundtrip_class.oem"

        # Low-level round-trip
        header, meta, states = oem.read_oem(source)
        oem.write_oem(lowlevel_path, header, meta, states)
        header2, meta2, states2 = oem.read_oem(lowlevel_path)

        low_header_ok = header2 == header
        low_meta_ok = meta2 == meta
        low_state_count_ok = len(states2) == len(states)
        low_states_ok = low_state_count_ok
        if low_states_ok:
            for (epoch1, state1), (epoch2, state2) in zip(states, states2):
                if epoch1 != epoch2 or not np.allclose(
                    state1, state2, atol=1e-9, rtol=0.0
                ):
                    low_states_ok = False
                    break

        # Class-based round-trip using new read()/write() API
        ccsds_oem = oem.CcsdsOem.read(source)
        ccsds_oem.write(class_path)
        oem2 = oem.CcsdsOem.read(class_path)

        class_header_ok = ccsds_oem.header == oem2.header
        class_meta_ok = ccsds_oem.meta == oem2.meta
        class_state_count_ok = len(ccsds_oem.states) == len(oem2.states)
        class_states_ok = class_state_count_ok and np.allclose(
            ccsds_oem.state_vectors,
            oem2.state_vectors,
            atol=1e-9,
            rtol=0.0,
        )

        return {
            "overall_ok": all(
                [
                    low_header_ok,
                    low_meta_ok,
                    low_states_ok,
                    class_header_ok,
                    class_meta_ok,
                    class_states_ok,
                ]
            ),
        }


def test_round_trip_oem() -> None:
    """Basic regression test for OEM read/write round-tripping."""
    result = _round_trip_test_oem(OEM_PATH)
    assert result["overall_ok"], result


# ===================================================================
# 9. Edge cases and additional coverage
# ===================================================================


def test_ccsds_oem_len_matches_state_count() -> None:
    """Should return correct length via __len__."""
    ccsds_oem = oem.CcsdsOem.read(OEM_PATH)

    assert len(ccsds_oem) == len(ccsds_oem.states)
    assert len(ccsds_oem) > 0


def test_ccsds_oem_epochs_property() -> None:
    """Should extract epochs list from states."""
    ccsds_oem = oem.CcsdsOem.read(OEM_PATH)

    epochs = ccsds_oem.epochs
    assert len(epochs) == len(ccsds_oem.states)
    assert all(isinstance(e, float) for e in epochs)


def test_ccsds_oem_state_vectors_property() -> None:
    """Should extract state vectors as numpy array."""
    ccsds_oem = oem.CcsdsOem.read(OEM_PATH)

    state_vecs = ccsds_oem.state_vectors
    assert isinstance(state_vecs, np.ndarray)
    assert state_vecs.shape == (len(ccsds_oem), 6)


def test_ccsds_oem_epochs_and_state_vectors_sorted() -> None:
    """Should return epochs and state vectors ordered by increasing epoch."""
    ccsds_oem = oem.CcsdsOem.read(OEM_PATH)

    epochs = ccsds_oem.epochs
    assert epochs == sorted(epochs)
    assert len(epochs) == len(ccsds_oem)

    state_vecs = ccsds_oem.state_vectors
    assert state_vecs.shape == (len(ccsds_oem), 6)

    for idx, (epoch, state) in enumerate(ccsds_oem.states):
        assert epochs[idx] == epoch
        assert np.allclose(state_vecs[idx], state, atol=1e-12, rtol=0.0)


def test_read_oem_raw_state_list_returns_empty_header_and_meta() -> None:
    """Should return empty dicts for header and meta when reading a raw state list."""
    raw_states = (
        "2026-05-20T12:00:00.000 6800.0 0.0 0.0 0.0 7.5 0.0\n"
        "2026-05-20T12:01:00.000 6850.0 100.0 50.0 0.1 7.4 0.05\n"
        "2026-05-20T12:02:00.000 6900.0 200.0 100.0 0.2 7.3 0.1\n"
    )

    header, meta, states = oem.read_oem(io.StringIO(raw_states))

    assert isinstance(header, dict)
    assert isinstance(meta, dict)
    assert header == {}
    assert meta == {}
    assert isinstance(states, list)
    assert len(states) == 3
    first_ts, first_state = states[0]
    assert isinstance(first_ts, float)
    assert first_state.shape == (6,)


def test_ccsds_oem_read_handles_raw_state_list() -> None:
    """CcsdsOem.read() should construct an OEM with empty header/meta from a raw state list."""
    raw_states = (
        "2026-05-20T12:00:00.000 6800.0 0.0 0.0 0.0 7.5 0.0\n"
        "2026-05-20T12:01:00.000 6850.0 100.0 50.0 0.1 7.4 0.05\n"
    )

    ccsds_oem = oem.CcsdsOem.read(io.StringIO(raw_states))

    assert isinstance(ccsds_oem.header, oem.OemHeader)
    assert isinstance(ccsds_oem.meta, oem.OemMeta)
    assert len(ccsds_oem) == 2
    # All header/meta fields should be at their defaults
    assert ccsds_oem.header.version == 0.0
    assert ccsds_oem.header.creation_date == ""
    assert ccsds_oem.meta.object_name == ""
    assert ccsds_oem.meta.ref_frame == ""


def test_write_states_to_stream() -> None:
    """Should write state vectors to a file handle."""
    header, meta, states = oem.read_oem(OEM_PATH)

    output = io.StringIO()
    oem.write_states(output, states)
    content = output.getvalue()

    # Should have written multiple lines (one per state)
    lines = content.strip().split("\n")
    assert len(lines) == len(states)
    # Each line should have 7 fields (epoch + 6 state components)
    for line in lines:
        assert len(line.split()) == 7


# ===================================================================
# 10. CcsdsOem.from_states() — factory method
# ===================================================================


def test_from_states_creates_oem_with_minimal_metadata() -> None:
    """Test CcsdsOem.from_states() creates OEM with minimal metadata."""
    states = [
        (1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
        (1234567950.0, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
    ]

    oem_obj = oem.CcsdsOem.from_states(
        states,
        object_name="TEST_SAT",
        ref_frame="GCRF",
        center_name="EARTH",
    )

    assert len(oem_obj) == 2
    assert oem_obj.meta.object_name == "TEST_SAT"
    assert oem_obj.meta.ref_frame == "GCRF"
    assert oem_obj.meta.center_name == "EARTH"
    assert oem_obj.meta.time_system == "UTC"
    assert oem_obj.header.version == 2.0
    assert oem_obj.header.originator == "tudatpy-utils"


def test_from_states_sorts_states_by_timestamp() -> None:
    """Test CcsdsOem.from_states() sorts states by timestamp."""
    # Provide states out of order
    states = [
        (1234567950.0, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
        (1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
    ]

    oem_obj = oem.CcsdsOem.from_states(states)

    # Should be sorted
    assert oem_obj.states[0][0] == 1234567890.0
    assert oem_obj.states[1][0] == 1234567950.0


def test_from_states_sets_start_stop_times() -> None:
    """Test CcsdsOem.from_states() sets start/stop times from states."""
    states = [
        (1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
        (1234567950.0, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
    ]

    oem_obj = oem.CcsdsOem.from_states(states)

    assert oem_obj.meta.start_time != ""
    assert oem_obj.meta.stop_time != ""
    assert "2009-02-13" in oem_obj.meta.start_time  # Timestamp 1234567890


def test_from_states_round_trip() -> None:
    """Test CcsdsOem.from_states() creates OEM that can be written and read."""
    states = [
        (1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
        (1234567950.0, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
    ]

    oem_obj = oem.CcsdsOem.from_states(
        states,
        object_name="TEST_SAT",
        ref_frame="GCRF",
    )

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".oem", delete=False) as f:
        temp_path = Path(f.name)

    try:
        oem_obj.write(temp_path)
        oem_read = oem.CcsdsOem.read(temp_path)

        assert len(oem_read) == 2
        assert oem_read.meta.object_name == "TEST_SAT"
        assert oem_read.meta.ref_frame == "GCRF"

        # Check states match
        for (t1, s1), (t2, s2) in zip(oem_obj.states, oem_read.states):
            assert abs(t1 - t2) < 1e-6
            np.testing.assert_array_almost_equal(s1, s2)
    finally:
        temp_path.unlink()


# ===================================================================
# 11. CcsdsOem.parse_state_line() — parsing utility
# ===================================================================


def test_parse_state_line_parses_valid_line() -> None:
    """Test CcsdsOem.parse_state_line() parses valid OEM line."""
    line = "2024-01-01T00:00:00.000000 7000.0 0.0 0.0 0.0 7.5 0.0"

    result = oem.CcsdsOem.parse_state_line(line)

    assert result is not None
    timestamp, state = result
    assert isinstance(timestamp, float)
    assert isinstance(state, np.ndarray)
    assert len(state) == 6
    # Check unit conversion (km to m)
    assert state[0] == 7000000.0  # 7000 km -> 7000000 m
    assert state[4] == 7500.0  # 7.5 km/s -> 7500 m/s


def test_parse_state_line_returns_none_for_blank_line() -> None:
    """Test CcsdsOem.parse_state_line() returns None for blank lines."""
    assert oem.CcsdsOem.parse_state_line("") is None
    assert oem.CcsdsOem.parse_state_line("   ") is None


def test_parse_state_line_returns_none_for_comment() -> None:
    """Test CcsdsOem.parse_state_line() returns None for comment lines."""
    assert oem.CcsdsOem.parse_state_line("# This is a comment") is None


# ===================================================================
# 12. update_metadata() and with_metadata() — metadata modification
# ===================================================================


def test_update_metadata_modifies_in_place() -> None:
    """Test update_metadata() modifies OEM metadata in-place."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]
    oem_obj = oem.CcsdsOem.from_states(states, object_name="ORIGINAL")

    oem_obj.update_metadata(object_name="UPDATED", ref_frame="J2000")

    assert oem_obj.meta.object_name == "UPDATED"
    assert oem_obj.meta.ref_frame == "J2000"


def test_update_metadata_raises_on_unknown_field() -> None:
    """Test update_metadata() raises ValueError for unknown fields."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]
    oem_obj = oem.CcsdsOem.from_states(states)

    with pytest.raises(ValueError, match="Unknown metadata field"):
        oem_obj.update_metadata(invalid_field="value")


def test_with_metadata_returns_new_instance() -> None:
    """Test with_metadata() returns new OEM instance."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]
    oem_obj = oem.CcsdsOem.from_states(states, object_name="ORIGINAL")

    new_oem = oem_obj.with_metadata(object_name="UPDATED")

    # New instance has updated metadata
    assert new_oem.meta.object_name == "UPDATED"

    # Original is unchanged
    assert oem_obj.meta.object_name == "ORIGINAL"

    # They are different objects
    assert new_oem is not oem_obj


def test_with_metadata_deep_copies() -> None:
    """Test with_metadata() creates deep copy."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]
    oem_obj = oem.CcsdsOem.from_states(states, object_name="ORIGINAL")

    new_oem = oem_obj.with_metadata(object_name="UPDATED")

    # Modify new OEM's state
    new_oem.states[0] = (9999999.0, np.array([1, 2, 3, 4, 5, 6]))

    # Original should be unchanged
    assert oem_obj.states[0][0] == 1234567890.0


def test_with_metadata_raises_on_unknown_field() -> None:
    """Test with_metadata() raises ValueError for unknown fields."""
    states = [(1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0]))]
    oem_obj = oem.CcsdsOem.from_states(states)

    with pytest.raises(ValueError, match="Unknown metadata field"):
        oem_obj.with_metadata(invalid_field="value")


# ===================================================================
# 13. Integration workflow test
# ===================================================================


def test_integration_workflow() -> None:
    """Test complete workflow with new methods."""
    # Create OEM from states
    states = [
        (1234567890.0, np.array([7e6, 0, 0, 0, 7.5e3, 0])),
        (1234567950.0, np.array([7.1e6, 0, 0, 0, 7.4e3, 0])),
        (1234568010.0, np.array([7.2e6, 0, 0, 0, 7.3e3, 0])),
    ]

    oem_obj = oem.CcsdsOem.from_states(
        states,
        object_name="SAT_A",
        ref_frame="GCRF",
        center_name="EARTH",
    )

    # Update metadata
    oem_updated = oem_obj.with_metadata(object_name="SAT_B")

    # Write to file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".oem", delete=False) as f:
        temp_path = Path(f.name)

    try:
        oem_updated.write(temp_path)

        # Read back
        oem_final = oem.CcsdsOem.read(temp_path)

        # Verify
        assert len(oem_final) == 3
        assert oem_final.meta.object_name == "SAT_B"
        assert oem_final.meta.ref_frame == "GCRF"
        assert oem_final.meta.center_name == "EARTH"

        # Original unchanged
        assert oem_obj.meta.object_name == "SAT_A"
    finally:
        temp_path.unlink()
