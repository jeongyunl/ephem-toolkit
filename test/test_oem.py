"""Tests for :mod:`common.oem` — OEM parsing, writing, and class API."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from common.oem import CcsdsOem, OemHeader, OemMeta, OemStateVector, read_oem, write_oem

TEST_DIR = Path(__file__).parent
OEM_PATH = TEST_DIR / "ISS_2026-05-20.OEM"


# ===================================================================
# 1. Read OEM test file
# ===================================================================


def test_read_oem_from_test_file_returns_header_meta_states() -> None:
    """Should parse the sample OEM file into header, meta, and state dicts."""
    header, meta, states = read_oem(OEM_PATH)

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
    assert isinstance(first_epoch, datetime)
    assert isinstance(first_state, np.ndarray)
    assert first_state.shape == (6,)


# ===================================================================
# 2. Read OEM from stream
# ===================================================================


def test_read_oem_from_stream_matches_file_read() -> None:
    """Should produce identical parsed content from a text stream."""
    text = OEM_PATH.read_text(encoding="utf-8")

    header1, meta1, states1 = read_oem(OEM_PATH)
    header2, meta2, states2 = read_oem(io.StringIO(text))

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
    header1, meta1, states1 = read_oem(OEM_PATH)
    out_path = tmp_path / "roundtrip.oem"

    write_oem(out_path, header1, meta1, states1)
    header2, meta2, states2 = read_oem(out_path)

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
    oem = CcsdsOem.from_source(OEM_PATH)

    assert isinstance(oem.header, OemHeader)
    assert isinstance(oem.meta, OemMeta)
    assert len(oem) > 0
    assert len(oem.epochs) == len(oem)
    assert oem.state_vectors.shape == (len(oem), 6)
    assert oem.header.version == pytest.approx(2.0)
    assert oem.meta.object_name == "ISS"
    assert oem.meta.object_id == "1998-067-A"
    assert oem.meta.ref_frame == "EME2000"
    assert isinstance(oem.states[0], OemStateVector)
    assert isinstance(oem.states[0].epoch, datetime)
    assert oem.states[0].state.shape == (6,)


# ===================================================================
# 5. Structured class API write/read round-trip
# ===================================================================


def test_ccsds_oem_to_file_round_trip_preserves_structured_content(tmp_path: Path) -> None:
    """Should preserve structured OEM content through class-based serialization."""
    oem1 = CcsdsOem.from_source(OEM_PATH)
    out_path = tmp_path / "class_roundtrip.oem"

    oem1.to_file(out_path)
    oem2 = CcsdsOem.from_source(out_path)

    assert oem2.header == oem1.header
    assert oem2.meta == oem1.meta
    assert oem2.epochs == oem1.epochs
    assert np.allclose(oem2.state_vectors, oem1.state_vectors, atol=1e-9, rtol=0.0)


# ===================================================================
# 6. __repr__ includes key summary fields
# ===================================================================


def test_ccsds_oem_repr_contains_summary_information() -> None:
    """Should include object name, frame, and epoch count in repr output."""
    oem = CcsdsOem.from_source(OEM_PATH)
    text = repr(oem)

    assert "CcsdsOem" in text
    assert oem.meta.object_name in text
    assert oem.meta.ref_frame in text
    assert str(len(oem)) in text


# ===================================================================
# 7. Round-trip regression test using module helper
# ===================================================================


def _round_trip_test_oem(source: Path) -> dict:
    """Perform a read/write/read round-trip test for an OEM file."""
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        lowlevel_path = tmp / "roundtrip_lowlevel.oem"
        class_path = tmp / "roundtrip_class.oem"

        header, meta, states = read_oem(source)
        write_oem(lowlevel_path, header, meta, states)
        header2, meta2, states2 = read_oem(lowlevel_path)

        low_header_ok = header2 == header
        low_meta_ok = meta2 == meta
        low_state_count_ok = len(states2) == len(states)
        low_states_ok = low_state_count_ok
        if low_states_ok:
            for epoch in states:
                if not np.allclose(states[epoch], states2[epoch], atol=1e-9, rtol=0.0):
                    low_states_ok = False
                    break

        oem = CcsdsOem.from_source(source)
        oem.to_file(class_path)
        oem2 = CcsdsOem.from_source(class_path)

        class_header_ok = oem.header == oem2.header
        class_meta_ok = oem.meta == oem2.meta
        class_state_count_ok = len(oem.states) == len(oem2.states)
        class_states_ok = class_state_count_ok and np.allclose(
            oem.state_vectors,
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
