"""Tests for :mod:`common.oem` — OEM parsing, writing, and class API."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

import common.oem as oem

TEST_DIR = Path(__file__).parent
OEM_PATH = TEST_DIR / "data" / "ISS_2026-05-20.OEM"


# ===================================================================
# 1. Read OEM test file
# ===================================================================


def test_read_oem_from_test_file_returns_header_meta_states() -> None:
    """Should parse the sample OEM file into header, meta, and state dicts."""
    header, meta, states = oem.read_oem(OEM_PATH)

    assert isinstance(header, dict)
    assert isinstance(meta, dict)
    assert isinstance(states, dict)
    assert header["CCSDS_OEM_VERS"] == pytest.approx(2.0)
    assert "CREATION_DATE" in header
    assert "ORIGINATOR" in header
    assert meta["OBJECT_NAME"] == "ISS"
    assert meta["OBJECT_ID"] == "1998-067-A"
    assert meta["CENTER_NAME"] == "Earth"
    assert meta["REF_FRAME"] == "EME2000"
    assert meta["TIME_SYSTEM"] == "UTC"
    assert len(states) > 0

    first_epoch = min(states)
    first_state = states[first_epoch]
    assert isinstance(first_epoch, float)
    assert isinstance(first_state, np.ndarray)
    assert first_state.shape == (6,)


# ===================================================================
# 2. Read OEM from stream
# ===================================================================


def test_read_oem_from_stream_matches_file_read() -> None:
    """Should produce identical parsed content from a text stream."""
    text = OEM_PATH.read_text(encoding="utf-8")

    header1, meta1, states1 = oem.read_oem(OEM_PATH)
    header2, meta2, states2 = oem.read_oem(io.StringIO(text))

    assert header2 == header1
    assert meta2 == meta1
    assert list(states2.keys()) == list(states1.keys())
    for epoch in states1:
        assert np.allclose(states2[epoch], states1[epoch], atol=1e-12, rtol=0.0)


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
    assert list(states2.keys()) == list(states1.keys())
    for epoch in states1:
        assert np.allclose(states2[epoch], states1[epoch], atol=1e-9, rtol=0.0)


# ===================================================================
# 4. Structured class API from source
# ===================================================================


def test_ccsds_oem_from_source_exposes_structured_fields() -> None:
    """Should load the sample OEM into the structured class representation."""
    ccsds_oem = oem.CcsdsOem.from_source(OEM_PATH)

    assert isinstance(ccsds_oem.header, oem.OemHeader)
    assert isinstance(ccsds_oem.meta, oem.OemMeta)
    assert len(ccsds_oem) > 0
    assert len(ccsds_oem.epochs) == len(ccsds_oem)
    assert ccsds_oem.state_vectors.shape == (len(ccsds_oem), 6)
    assert ccsds_oem.header.version == pytest.approx(2.0)
    assert ccsds_oem.meta.object_name == "ISS"
    assert ccsds_oem.meta.object_id == "1998-067-A"
    assert ccsds_oem.meta.ref_frame == "EME2000"
    assert isinstance(ccsds_oem.states, dict)
    assert len(ccsds_oem.states) == len(ccsds_oem)
    first_epoch = next(iter(ccsds_oem.states))
    first_state = ccsds_oem.states[first_epoch]
    assert isinstance(first_epoch, float)
    assert isinstance(first_state, np.ndarray)
    assert first_state.shape == (6,)


# ===================================================================
# 5. Structured class API write/read round-trip
# ===================================================================


def test_ccsds_oem_to_file_round_trip_preserves_structured_content(
    tmp_path: Path,
) -> None:
    """Should preserve structured OEM content through class-based serialization."""
    oem1 = oem.CcsdsOem.from_source(OEM_PATH)
    out_path = tmp_path / "class_roundtrip.oem"

    oem1.to_file(out_path)
    oem2 = oem.CcsdsOem.from_source(out_path)

    assert oem2.header == oem1.header
    assert oem2.meta == oem1.meta
    assert oem2.epochs == oem1.epochs
    assert np.allclose(oem2.state_vectors, oem1.state_vectors, atol=1e-9, rtol=0.0)


# ===================================================================
# 6. __repr__ includes key summary fields
# ===================================================================


def test_ccsds_oem_repr_contains_summary_information() -> None:
    """Should include object name, frame, and epoch count in repr output."""
    ccsds_oem = oem.CcsdsOem.from_source(OEM_PATH)
    text = repr(ccsds_oem)

    assert "CcsdsOem" in text
    assert ccsds_oem.meta.object_name in text
    assert ccsds_oem.meta.ref_frame in text
    assert str(len(ccsds_oem)) in text


# ===================================================================
# 7. Round-trip regression test using module helper
# ===================================================================


def _round_trip_test_oem(source: Path) -> dict:
    """Perform a read/write/read round-trip test for an OEM file."""
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        lowlevel_path = tmp / "roundtrip_lowlevel.oem"
        class_path = tmp / "roundtrip_class.oem"

        header, meta, states = oem.read_oem(source)
        oem.write_oem(lowlevel_path, header, meta, states)
        header2, meta2, states2 = oem.read_oem(lowlevel_path)

        low_header_ok = header2 == header
        low_meta_ok = meta2 == meta
        low_state_count_ok = len(states2) == len(states)
        low_states_ok = low_state_count_ok
        if low_states_ok:
            for epoch in states:
                if not np.allclose(states[epoch], states2[epoch], atol=1e-9, rtol=0.0):
                    low_states_ok = False
                    break

        ccsds_oem = oem.CcsdsOem.from_source(source)
        ccsds_oem.to_file(class_path)
        oem2 = oem.CcsdsOem.from_source(class_path)

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
# 8. Edge cases and additional coverage
# ===================================================================


def test_ccsds_oem_len_matches_state_count() -> None:
    """Should return correct length via __len__."""
    ccsds_oem = oem.CcsdsOem.from_source(OEM_PATH)

    assert len(ccsds_oem) == len(ccsds_oem.states)
    assert len(ccsds_oem) > 0


def test_ccsds_oem_epochs_property() -> None:
    """Should extract epochs list from states."""
    ccsds_oem = oem.CcsdsOem.from_source(OEM_PATH)

    epochs = ccsds_oem.epochs
    assert len(epochs) == len(ccsds_oem.states)
    assert all(isinstance(e, float) for e in epochs)


def test_ccsds_oem_state_vectors_property() -> None:
    """Should extract state vectors as numpy array."""
    ccsds_oem = oem.CcsdsOem.from_source(OEM_PATH)

    state_vecs = ccsds_oem.state_vectors
    assert isinstance(state_vecs, np.ndarray)
    assert state_vecs.shape == (len(ccsds_oem), 6)


def test_ccsds_oem_epochs_and_state_vectors_sorted() -> None:
    """Should return epochs and state vectors ordered by increasing epoch."""
    ccsds_oem = oem.CcsdsOem.from_source(OEM_PATH)

    epochs = ccsds_oem.epochs
    assert epochs == sorted(epochs)
    assert len(epochs) == len(ccsds_oem)

    state_vecs = ccsds_oem.state_vectors
    assert state_vecs.shape == (len(ccsds_oem), 6)

    for idx, epoch in enumerate(epochs):
        assert np.allclose(
            state_vecs[idx], ccsds_oem.states[epoch], atol=1e-12, rtol=0.0
        )


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
