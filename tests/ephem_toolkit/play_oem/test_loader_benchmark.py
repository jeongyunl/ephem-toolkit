"""Checks for the headless direct-store loader benchmarks."""

from pathlib import Path
from threading import Event

import pytest

from scripts.bench_play_oem import (
    _percentile,
    _plot_range_for_coverage,
    _store_memory_diagnostics,
    measure_store_ingest,
    measure_store_session,
    run_parser_benchmarks,
)
from ephem_toolkit.play_oem import time_range
from ephem_toolkit.play_oem.oem_data_store import OemDataStore
from ephem_toolkit.play_oem.streaming_oem import read_oem_into_store


def test_direct_store_benchmarks_measure_real_session(tmp_path: Path) -> None:
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


def test_parser_benchmark_reports_direct_store_time(tmp_path: Path, capsys) -> None:
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
    assert "Direct raw-store parsing: median=" in capsys.readouterr().out


def test_percentile_interpolates_and_rejects_invalid_input() -> None:
    assert _percentile([3.0, 1.0, 2.0], 95) == pytest.approx(2.9)
    assert _percentile([4.0], 99) == 4.0
    with pytest.raises(ValueError):
        _percentile([], 95)
    with pytest.raises(ValueError):
        _percentile([1.0], 101)


def test_plot_range_probe_tracks_current_coverage_tail() -> None:
    rule = _plot_range_for_coverage((100.0, 43_300.0))
    assert rule == time_range.PlotTimeRange(
        enabled=True,
        start=time_range.TimeRangeEndpoint("fixed", 100.0),
        end=time_range.TimeRangeEndpoint("fixed", 43_300.0),
    )
    assert _plot_range_for_coverage((100.0, 100.0)) is None


def test_store_memory_diagnostics_match_derived_cache_accounting(
    tmp_path: Path,
) -> None:
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
    store = OemDataStore(derived_memory_budget_bytes=1024 * 1024)
    try:
        store.begin(3)
        read_oem_into_store(
            source,
            store,
            batch_size=3,
            on_append=lambda _notice: None,
            cancel_event=Event(),
        )
        snapshot = store.snapshot()
        store.ground_track(
            snapshot,
            (float(snapshot.raw[0, 0]), float(snapshot.raw[-1, 0])),
            wait=True,
        )
        series_query = store.series(
            snapshot,
            (float(snapshot.raw[0, 0]), float(snapshot.raw[-1, 0])),
            groups=("kinematics",),
            wait=True,
        )

        diagnostics = _store_memory_diagnostics(store)

        assert series_query.value
        assert diagnostics["budget_accounted_derived_bytes"] > 0
        assert diagnostics["ground_track_cache_bytes"] > 0
        assert diagnostics["pinned_chunk_references"] > 0
        assert diagnostics["derived_memory_budget_bytes"] == 1024 * 1024
    finally:
        store.close()
