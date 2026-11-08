"""Checks for the headless incremental loader benchmark."""

from pathlib import Path

import pytest

from scripts.bench_play_oem import (
    _percentile,
    measure_backpressure_cancellation,
    measure_incremental_load,
    measure_phase_cancellation,
    measure_replacement,
    measure_store_ingest,
    measure_store_session,
    run_parser_benchmarks,
)
from ephem_toolkit.play_oem.oem_data_store import OemDataStore


def test_incremental_benchmark_measures_real_session(tmp_path: Path) -> None:
    source = tmp_path / "small.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = TEST\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n"
        "2026-01-01T00:00:20 7000 2 0 0 7.5 0\n",
        encoding="utf-8",
    )
    result = measure_incremental_load(source, batch_size=1, queue_size=1)
    assert result.state_count == 3
    assert result.batch_sizes == (1, 1, 1)
    assert 0 < result.first_batch_s <= result.completion_s
    assert 0 < result.first_publish_attempt_s <= result.first_batch_s
    assert result.first_handoff_s == pytest.approx(
        result.first_batch_s - result.first_publish_attempt_s
    )
    assert result.preparation_s > 0
    assert result.publish_s >= 0
    assert result.cpu_s > 0
    assert 0 <= measure_backpressure_cancellation(source) < 30
    for phase in ("parsing", "preparation"):
        assert 0 <= measure_phase_cancellation(source, phase) < 30
    replacement = measure_replacement(source, source, batch_size=1, queue_size=1)
    assert replacement.state_count == 3
    assert 0 < replacement.first_batch_s <= replacement.completion_s
    assert replacement.old_worker_observed_finished_s >= 0
    first, completion, count = measure_store_ingest(source, 3)
    assert 0 < first <= completion
    assert count == 3
    with pytest.raises(OverflowError, match="capacity"):
        measure_store_ingest(source, 2)
    first, completion, count, notices, capacity = measure_store_session(source, 3)
    assert 0 < first <= completion
    assert count == 3
    assert notices == 1
    assert capacity == 3
    _, _, auto_count, _, auto_capacity = measure_store_session(source, None)
    assert auto_count == 3
    assert auto_capacity == OemDataStore.capacity_for_file(source)
    with pytest.raises(RuntimeError, match="direct store session failed"):
        measure_store_session(source, 2)


def test_parser_benchmark_reports_streaming_time(tmp_path: Path, capsys) -> None:
    source = tmp_path / "small.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = TEST\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n",
        encoding="utf-8",
    )
    run_parser_benchmarks(source, repeats=2)
    assert "Streaming parser only: median=" in capsys.readouterr().out


def test_incremental_benchmark_reports_load_failure(tmp_path: Path) -> None:
    source = tmp_path / "bad.oem"
    source.write_text("invalid\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="incremental load failed"):
        measure_incremental_load(source)
    with pytest.raises(RuntimeError, match="incremental load failed"):
        measure_backpressure_cancellation(source)
    with pytest.raises(RuntimeError, match="incremental load failed"):
        measure_phase_cancellation(source, "preparation")
    with pytest.raises(RuntimeError, match="initial incremental load failed"):
        measure_replacement(source, source)
    with pytest.raises(ValueError, match="phase must be"):
        measure_phase_cancellation(source, "invalid")


def test_replacement_benchmark_reports_short_and_invalid_replacements(tmp_path: Path) -> None:
    source = tmp_path / "small.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = TEST\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n",
        encoding="utf-8",
    )
    invalid = tmp_path / "invalid.oem"
    invalid.write_text("invalid\n", encoding="utf-8")
    replacement = tmp_path / "replacement.oem"
    replacement.write_text(
        source.read_text(encoding="utf-8").replace(
            "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n", ""
        ),
        encoding="utf-8",
    )
    result = measure_replacement(source, replacement, batch_size=1)
    assert result.state_count == 1
    with pytest.raises(
        RuntimeError, match="initial load needs at least two batches|initial loader stopped"
    ):
        measure_replacement(source, source, batch_size=512)
    with pytest.raises(RuntimeError, match="replacement incremental load failed"):
        measure_replacement(source, invalid, batch_size=1)


def test_percentile_interpolates_and_rejects_invalid_input() -> None:
    assert _percentile([3.0, 1.0, 2.0], 95) == pytest.approx(2.9)
    assert _percentile([4.0], 99) == 4.0
    with pytest.raises(ValueError):
        _percentile([], 95)
    with pytest.raises(ValueError):
        _percentile([1.0], 101)
