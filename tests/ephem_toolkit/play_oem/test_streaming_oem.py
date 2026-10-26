"""Tests for bounded background OEM reading."""

from __future__ import annotations

from pathlib import Path

import pytest
import numpy as np

from ephem_toolkit.core.ccsds.oem import CcsdsOem
from ephem_toolkit.play_oem.streaming_oem import (
    OemStreamComplete,
    OemStreamError,
    iter_oem_events,
)
from ephem_toolkit.play_oem.playback_data import AppendablePlaybackData
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


OEM_TEXT = """CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2026-01-01T00:00:00
ORIGINATOR = TEST
META_START
OBJECT_NAME = TEST
OBJECT_ID = 2026-001A
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:00:00 7000 0 0 0 7.5 0
2026-01-01T00:00:10 7000 1 0 0 7.5 0
2026-01-01T00:00:20 7000 2 0 0 7.5 0
META_START
OBJECT_NAME = TEST
OBJECT_ID = 2026-001A
CENTER_NAME = EARTH
REF_FRAME = GCRF
TIME_SYSTEM = UTC
META_STOP
2026-01-01T00:10:00 7000 3 0 0 7.5 0
"""


def test_stream_matches_whole_file_parse_across_segment_and_batch_boundaries(
    tmp_path: Path,
) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    parsed = CcsdsOem.from_file(source)

    events = list(iter_oem_events(source, batch_size=2, queue_size=1))
    batches = [event for event in events if not isinstance(event, OemStreamComplete)]
    completed = events[-1]

    assert isinstance(completed, OemStreamComplete)
    assert [len(batch.states) for batch in batches] == [2, 2]
    assert completed.state_count == len(parsed.states)
    assert dict(completed.meta)["OBJECT_NAME"] == parsed.meta.object_name
    assert [
        segment_id for batch in batches for segment_id in batch.segment_ids
    ] == parsed.segment_ids
    streamed_states = [state for batch in batches for state in batch.states]
    for actual, expected in zip(streamed_states, parsed.states):
        assert actual[0] == expected[0]
        assert (actual[1] == expected[1]).all()


def test_stream_yields_valid_prefix_before_late_parse_error(tmp_path: Path) -> None:
    source = tmp_path / "malformed.oem"
    source.write_text(OEM_TEXT + "COVARIANCE_STOP\n", encoding="utf-8")
    events = iter_oem_events(source, batch_size=2)

    first_batch = next(events)
    assert len(first_batch.states) == 2
    with pytest.raises(OemStreamError, match="COVARIANCE_STOP"):
        list(events)


def test_stream_validates_but_does_not_retain_comments_or_covariance(
    tmp_path: Path,
) -> None:
    source = tmp_path / "comments-and-covariance.oem"
    content = OEM_TEXT.replace(
        "CCSDS_OEM_VERS = 2.0\n",
        "CCSDS_OEM_VERS = 2.0\nCOMMENT header\n",
        1,
    ).replace(
        "META_START\nOBJECT_NAME = TEST\n",
        "META_START\nCOMMENT metadata\nOBJECT_NAME = TEST\n",
        1,
    ).replace(
        "META_STOP\n2026-01-01T00:00:00",
        "META_STOP\nCOMMENT ephemeris\n2026-01-01T00:00:00",
        1,
    )
    content += (
        "COVARIANCE_START\n"
        "COMMENT covariance\n"
        "EPOCH = 2026-01-01T00:00:00\n"
        "COV_REF_FRAME = GCRF\n"
        "1\n2 3\n4 5 6\n7 8 9 10\n11 12 13 14 15\n"
        "16 17 18 19 20 21\n"
        "COVARIANCE_STOP\n"
    )
    source.write_text(content, encoding="utf-8")
    parsed = CcsdsOem.from_file(source)
    assert parsed.header.comments == ["header"]
    assert parsed.meta.comments == ["metadata"]
    assert parsed.data_comments == ["ephemeris"]
    assert len(parsed.covariances) == 1

    events = list(iter_oem_events(source, batch_size=2))
    completion = events[-1]
    assert isinstance(completion, OemStreamComplete)
    assert "COMMENT" not in dict(completion.header)
    assert "COMMENT" not in dict(completion.meta)


def test_stream_iterator_close_cancels_backpressured_worker(tmp_path: Path) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    events = iter_oem_events(source, batch_size=1, queue_size=1)

    next(events)
    events.close()


def test_stream_rejects_invalid_batch_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        list(iter_oem_events(tmp_path / "unused.oem", batch_size=0))


@pytest.mark.parametrize("batch_size", [1, 2, 3, 100])
def test_appendable_playback_data_matches_one_shot_series_and_cursor(
    tmp_path: Path, batch_size: int
) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    events = list(iter_oem_events(source, batch_size=batch_size))
    batches = [event for event in events if not isinstance(event, OemStreamComplete)]
    complete = events[-1]
    assert isinstance(complete, OemStreamComplete)

    first = batches[0]
    store = AppendablePlaybackData.from_batch(
        first,
        center_name=str(dict(first.meta)["CENTER_NAME"]),
        frame_name=str(dict(first.meta)["REF_FRAME"]),
        interpolation_method="linear",
    )
    for batch in batches[1:]:
        store.append_batch(batch)

    parsed = CcsdsOem.from_file(source)
    expected = compute_orbit_series(
        [timestamp for timestamp, _ in parsed.states],
        [state for _, state in parsed.states],
        TimeUnit.MINUTES,
        parsed.segment_ids,
    )
    for name in expected.__dataclass_fields__:
        np.testing.assert_allclose(
            getattr(store.series, name), getattr(expected, name), equal_nan=True
        )
    np.testing.assert_array_equal(
        store.timestamps_s, [timestamp for timestamp, _ in parsed.states]
    )
    np.testing.assert_array_equal(store.segment_ids, parsed.segment_ids)
    np.testing.assert_allclose(
        store.ground_track_source.states_m,
        np.asarray([state for _, state in parsed.states]),
    )
    assert store.cursor.lookup(parsed.states[1][0]).status.value == "exact_sample"
    assert store.cursor.lookup((parsed.states[0][0] + parsed.states[1][0]) / 2).status.value == "interpolated"


def test_appendable_cursor_matches_one_shot_hermite_interpolation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "stream.oem"
    source.write_text(OEM_TEXT, encoding="utf-8")
    events = list(iter_oem_events(source, batch_size=1))
    batches = [event for event in events if not isinstance(event, OemStreamComplete)]
    first = batches[0]
    store = AppendablePlaybackData.from_batch(
        first,
        center_name="EARTH",
        frame_name="GCRF",
        interpolation_method="hermite",
        interpolation_degree=5,
    )
    for batch in batches[1:]:
        store.append_batch(batch)

    parsed = CcsdsOem.from_file(source)
    expected_cursor = OemCursor(
        [timestamp for timestamp, _ in parsed.states],
        [state for _, state in parsed.states],
        interpolation="hermite",
        interpolation_degree=5,
        segment_ids=parsed.segment_ids,
    )
    query_time = (parsed.states[0][0] + parsed.states[1][0]) / 2
    np.testing.assert_allclose(
        store.cursor.lookup(query_time).state_m,
        expected_cursor.lookup(query_time).state_m,
        rtol=0.0,
        atol=1e-8,
    )


def test_appendable_store_switches_time_units_when_loaded_span_crosses_hour() -> None:
    from ephem_toolkit.core.ccsds.oem import OemStateBatch

    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    first = OemStateBatch(((0.0, state),), (0,), (), ())
    store = AppendablePlaybackData.from_batch(
        first, center_name="EARTH", frame_name="GCRF", interpolation_method="linear"
    )
    store.append_batch(OemStateBatch(((1800.0, state),), (0,), (), ()))
    assert store.time_unit is TimeUnit.MINUTES
    store.append_batch(OemStateBatch(((4000.0, state),), (0,), (), ()))
    assert store.time_unit is TimeUnit.HOURS
    np.testing.assert_allclose(store.series.elapsed_time, [0.0, 0.5, 4000.0 / 3600.0])


def test_appendable_store_rejects_out_of_order_batch_without_changing_count() -> None:
    from ephem_toolkit.core.ccsds.oem import OemStateBatch

    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    store = AppendablePlaybackData.from_batch(
        OemStateBatch(((10.0, state),), (0,), (), ()),
        center_name="EARTH",
        frame_name="GCRF",
        interpolation_method="linear",
    )
    with pytest.raises(ValueError, match="follow loaded timestamps"):
        store.append_batch(OemStateBatch(((10.0, state),), (0,), (), ()))
    assert store.source_sample_count == 1
