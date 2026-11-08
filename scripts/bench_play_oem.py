"""Repeatable data-layer and optional wx event-loop benchmarks for play-oem."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import platform
from queue import Queue
import statistics
import sys
from threading import Condition, Event
import time
from typing import Callable, Optional, Sequence
from unittest.mock import patch

try:
    import resource
except ImportError:
    resource = None

from ephem_toolkit.core.ccsds.oem import OemStateBatch
import ephem_toolkit.core.ccsds.odm as odm
from ephem_toolkit.play_oem.data import read_oem_states
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.ground_track import (
    EarthFixedPositionCache,
    prepare_ground_track,
    state_position_to_itrf_m,
)
from ephem_toolkit.play_oem.incremental_loader import (
    IncrementalLoader,
    IncrementalLoadSession,
    LoadEvent,
    LoadEventKind,
)
from ephem_toolkit.play_oem.oem_data_store import OemDataStore, RawAppendNotice
from ephem_toolkit.play_oem.playback_data import (
    IncrementalPlaybackPreparer,
    PreparedPlaybackBatch,
    load_playback_data,
)
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.station_access import StationAccessCache
from ephem_toolkit.play_oem.streaming_oem import read_oem_batches, read_oem_into_store
from ephem_toolkit.play_oem.time_unit import TimeUnit


_STATION_LOCATIONS = (
    (0.0, 0.0),
    (35.68, 139.69),
    (-35.3, 149.1),
    (40.7, -74.0),
    (51.5, 0.0),
    (-33.9, 151.2),
    (28.6, 77.2),
    (37.8, -122.4),
    (-23.5, -46.6),
    (64.1, -21.9),
)


def _measure(function: Callable[[], object], repeats: int) -> list[float]:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        samples.append(time.perf_counter() - started)
    return samples


def _print_measurement(name: str, samples: list[float]) -> None:
    print(
        f"{name}: median={statistics.median(samples):.6f}s "
        f"samples={[round(sample, 6) for sample in samples]}"
    )


def _parse_store_capacity(value: str) -> int | None:
    if value.lower() == "auto":
        return None
    try:
        capacity = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "capacity must be a positive integer or 'auto'"
        ) from error
    if capacity < 1:
        raise argparse.ArgumentTypeError("capacity must be positive")
    return capacity


def _percentile(samples: list[float], percentile: float) -> float:
    """Return a linearly interpolated percentile of nonempty samples."""
    if not samples or not 0 <= percentile <= 100:
        raise ValueError("percentile requires nonempty samples and a value from 0 to 100")
    ordered = sorted(samples)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _stations(count: int) -> list[GroundStation]:
    return [
        GroundStation(
            station_id=f"benchmark-{index + 1:02d}",
            name=f"Benchmark station {index + 1:02d}",
            latitude_deg=latitude,
            longitude_deg=longitude,
            altitude_m=0.0,
        )
        for index, (latitude, longitude) in enumerate(_STATION_LOCATIONS[:count])
    ]


@dataclass(frozen=True)
class IncrementalMeasurement:
    first_batch_s: float
    first_publish_attempt_s: float
    first_handoff_s: float
    completion_s: float
    preparation_s: float
    publish_s: float
    cpu_s: float
    state_count: int
    batch_sizes: tuple[int, ...]


@dataclass(frozen=True)
class ReplacementMeasurement:
    first_batch_s: float
    completion_s: float
    old_worker_observed_finished_s: float
    state_count: int


class _MeasuredLoadSession(IncrementalLoadSession):
    """Measure publisher time, including any wait for the bounded queue."""

    def __init__(
        self,
        source: Path,
        prepare_batch: Callable[[OemStateBatch], PreparedPlaybackBatch],
        *,
        batch_size: int,
        batch_interval_s: float,
        queue_size: int,
    ) -> None:
        super().__init__(
            source,
            generation=1,
            prepare_batch=prepare_batch,
            batch_size=batch_size,
            batch_interval_s=batch_interval_s,
            queue_size=queue_size,
        )
        self.publish_s = 0.0
        self.first_batch_publish_started: float | None = None

    def _publish(self, event: LoadEvent) -> None:
        started = time.perf_counter()
        if event.kind is LoadEventKind.BATCH and self.first_batch_publish_started is None:
            self.first_batch_publish_started = started
        try:
            super()._publish(event)
        finally:
            self.publish_s += time.perf_counter() - started

    def wait_finished(self, timeout_s: float) -> bool:
        return self._finished.wait(timeout_s)


class _ObservedWaitCondition(Condition):
    def __init__(self, lock, waiting: Event) -> None:
        super().__init__(lock)
        self._waiting = waiting

    def wait(self, timeout: float | None = None) -> bool:
        self._waiting.set()
        return super().wait(timeout)


def measure_incremental_load(
    source: Path,
    *,
    batch_size: int = 512,
    batch_interval_s: float = 0.1,
    queue_size: int = 2,
    poll_interval_s: float = 0.001,
    timeout_s: float = 300.0,
) -> IncrementalMeasurement:
    """Measure a real incremental session with a headless, promptly draining consumer."""
    if poll_interval_s <= 0 or timeout_s <= 0:
        raise ValueError("poll_interval_s and timeout_s must be positive")
    preparer = IncrementalPlaybackPreparer(source)
    preparation_s = 0.0

    def prepare(batch: OemStateBatch) -> PreparedPlaybackBatch:
        nonlocal preparation_s
        started = time.perf_counter()
        try:
            return preparer(batch)
        finally:
            preparation_s += time.perf_counter() - started

    session = _MeasuredLoadSession(
        source,
        prepare,
        batch_size=batch_size,
        batch_interval_s=batch_interval_s,
        queue_size=queue_size,
    )
    started = time.perf_counter()
    cpu_started = time.process_time()
    first_batch_s: float | None = None
    batch_sizes: list[int] = []
    session.start()
    try:
        while True:
            events = session.drain()
            if not events and session.finished:
                # Check once more after observing termination; publication precedes it.
                events = session.drain()
                if not events:
                    raise RuntimeError("incremental loader exited without completion")
            for event in events:
                if event.kind is LoadEventKind.BATCH:
                    if event.batch is None:
                        raise RuntimeError("batch event has no batch")
                    if first_batch_s is None:
                        first_batch_s = time.perf_counter() - started
                    batch_sizes.append(len(event.batch.states))
                elif event.kind is LoadEventKind.FAILED:
                    raise RuntimeError("incremental load failed") from event.error
                elif event.kind is LoadEventKind.COMPLETE:
                    if first_batch_s is None or event.completion is None:
                        raise RuntimeError("completion without a prepared batch")
                    if event.completion.state_count != sum(batch_sizes):
                        raise RuntimeError("batch and completion counts do not match")
                    if session.first_batch_publish_started is None:
                        raise RuntimeError("batch was delivered without publication")
                    completion_s = time.perf_counter() - started
                    if not session.wait_finished(timeout_s):
                        raise TimeoutError("incremental worker did not terminate")
                    first_publish_attempt_s = session.first_batch_publish_started - started
                    return IncrementalMeasurement(
                        first_batch_s=first_batch_s,
                        first_publish_attempt_s=first_publish_attempt_s,
                        first_handoff_s=first_batch_s - first_publish_attempt_s,
                        completion_s=completion_s,
                        preparation_s=preparation_s,
                        publish_s=session.publish_s,
                        cpu_s=time.process_time() - cpu_started,
                        state_count=event.completion.state_count,
                        batch_sizes=tuple(batch_sizes),
                    )
            if time.perf_counter() - started >= timeout_s:
                raise TimeoutError("incremental loader did not complete in time")
            time.sleep(poll_interval_s)
    finally:
        session.cancel()


def run_incremental_benchmarks(source: Path, repeats: int) -> None:
    """Report headless incremental timings; these are not GUI latency measurements."""
    measure_incremental_load(source)
    samples = [measure_incremental_load(source) for _ in range(repeats)]
    print(f"Incremental input: {source}; bytes={source.stat().st_size}")
    print("Incremental settings: batch=512, flush=0.1s, queue=2, headless poll=0.001s")
    for label, values in (
        ("First batch", [sample.first_batch_s for sample in samples]),
        ("First batch publish attempt", [sample.first_publish_attempt_s for sample in samples]),
        ("First batch handoff since publish attempt", [sample.first_handoff_s for sample in samples]),
        ("Validated completion", [sample.completion_s for sample in samples]),
        ("Preparation (worker)", [sample.preparation_s for sample in samples]),
        ("Publish including queue wait (worker)", [sample.publish_s for sample in samples]),
        ("Process CPU", [sample.cpu_s for sample in samples]),
    ):
        _print_measurement(label, values)
    for index, sample in enumerate(samples, 1):
        print(
            f"Run {index}: states={sample.state_count}, batches={len(sample.batch_sizes)}, "
            f"batch_size_min/max={min(sample.batch_sizes)}/{max(sample.batch_sizes)}, "
            f"states/s={sample.state_count / sample.completion_s:.0f}"
        )
    _print_peak_rss("Process peak RSS including startup and warm-up")
    print("GUI first-playable, first-plot, UI stalls: not measured")


def measure_store_ingest(source: Path, capacity: int) -> tuple[float, float, int]:
    """Measure direct parsing and raw publication without derived preparation."""
    store = OemDataStore()
    started = time.perf_counter()
    store.begin(capacity)
    first_batch_s: float | None = None

    def observe(notice: RawAppendNotice) -> None:
        nonlocal first_batch_s
        if first_batch_s is None:
            first_batch_s = time.perf_counter() - started

    completion = read_oem_into_store(
        source, store, batch_size=512, on_append=observe, cancel_event=Event()
    )
    if first_batch_s is None:
        raise RuntimeError("store ingestion completed without states")
    if completion.state_count != store.snapshot().sample_count:
        raise RuntimeError("store and completion counts do not match")
    return first_batch_s, time.perf_counter() - started, completion.state_count


def run_store_ingest_benchmarks(source: Path, capacity: int, repeats: int) -> None:
    measure_store_ingest(source, capacity)
    samples = [measure_store_ingest(source, capacity) for _ in range(repeats)]
    print(f"Raw store input: {source}; bytes={source.stat().st_size}; capacity={capacity}")
    print("Settings: batch=512, flush=0.1s, synchronous producer; no derived preparation")
    _print_measurement("First raw commit", [sample[0] for sample in samples])
    _print_measurement("Validated raw completion", [sample[1] for sample in samples])
    print(f"State counts: {[sample[2] for sample in samples]}")
    _print_peak_rss("Process peak RSS including startup and warm-up")
    print("Playback, plot, GUI and derived preparation: not measured")


def measure_store_session(
    source: Path,
    capacity: int | None,
    *,
    poll_interval_s: float = 0.001,
    timeout_s: float = 300.0,
) -> tuple[float, float, int, int, int]:
    """Measure direct raw ingestion through the bounded incremental-session queue."""
    store = OemDataStore()
    loader = IncrementalLoader(batch_size=512, queue_size=2)
    started = time.perf_counter()
    session = loader.start(source, store=store, store_capacity=capacity)
    first_append_s: float | None = None
    completion_s: float | None = None
    state_count = 0
    append_count = 0
    deadline = started + timeout_s

    def consume_events() -> None:
        nonlocal first_append_s, completion_s, state_count, append_count
        for event in loader.drain():
            if event.kind is LoadEventKind.RAW_APPEND:
                append_count += 1
                if first_append_s is None:
                    first_append_s = time.perf_counter() - started
                state_count = event.loaded_state_count
            elif event.kind is LoadEventKind.COMPLETE:
                completion_s = time.perf_counter() - started
                state_count = event.loaded_state_count
            elif event.kind is LoadEventKind.FAILED:
                raise RuntimeError("direct store session failed") from event.error

    try:
        while not session.finished and time.perf_counter() < deadline:
            consume_events()
            time.sleep(poll_interval_s)
        consume_events()
        if not session.finished:
            raise TimeoutError("direct store session did not finish")
        if completion_s is None or first_append_s is None:
            raise RuntimeError(
                "direct store session completed without append and completion events"
            )
        if state_count != store.snapshot().sample_count:
            raise RuntimeError("store and direct session state counts do not match")
        return first_append_s, completion_s, state_count, append_count, store.capacity
    finally:
        if not session.finished:
            session.cancel()
            session._finished.wait(5.0)


def run_store_session_benchmarks(
    source: Path, capacity: int | None, repeats: int
) -> None:
    """Report headless timings through the bounded incremental-session queue."""
    measure_store_session(source, capacity)
    samples = [measure_store_session(source, capacity) for _ in range(repeats)]
    print(
        f"Raw store session input: {source}; bytes={source.stat().st_size}; "
        f"capacity={'auto' if capacity is None else capacity}"
    )
    print("Settings: batch=512, flush=0.1s, queue=2, headless poll=0.001s")
    _print_measurement("First raw append delivered", [sample[0] for sample in samples])
    _print_measurement("Validated completion delivered", [sample[1] for sample in samples])
    print(
        f"State counts: {[sample[2] for sample in samples]}; "
        f"append notices: {[sample[3] for sample in samples]}; "
        f"allocated capacities: {[sample[4] for sample in samples]}"
    )
    _print_peak_rss("Process peak RSS including startup and warm-up")
    print("Playback, derived preparation, plot and GUI responsiveness: not measured")


def measure_replacement(
    source: Path,
    replacement: Path,
    *,
    batch_size: int = 512,
    queue_size: int = 2,
    poll_interval_s: float = 0.001,
    timeout_s: float = 300.0,
) -> ReplacementMeasurement:
    """Replace a session after its first batch, holding its second preparation."""
    if poll_interval_s <= 0 or timeout_s <= 0:
        raise ValueError("poll_interval_s and timeout_s must be positive")
    entered = Event()
    release = Event()
    old_preparer = IncrementalPlaybackPreparer(source)
    calls = 0

    def prepare_old(batch: OemStateBatch) -> PreparedPlaybackBatch:
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            if not release.wait(timeout_s):
                raise TimeoutError("replacement probe did not release preparation")
        return old_preparer(batch)

    loader = IncrementalLoader(batch_size=batch_size, queue_size=queue_size)
    old_session = loader.start(source, prepare_batch=prepare_old)
    new_session: IncrementalLoadSession | None = None
    try:
        deadline = time.perf_counter() + timeout_s
        old_first_batch = False
        while not (old_first_batch and entered.is_set()):
            for event in loader.drain():
                if event.kind is LoadEventKind.FAILED:
                    raise RuntimeError("initial incremental load failed") from event.error
                if event.kind is LoadEventKind.COMPLETE:
                    raise RuntimeError("initial load needs at least two batches")
                if event.kind is LoadEventKind.BATCH:
                    if event.batch is None or event.prepared is None:
                        raise RuntimeError("initial batch was not prepared")
                    old_first_batch = True
            if old_session.finished:
                # The worker may finish between draining its queue and checking its state.
                for event in loader.drain():
                    if event.kind is LoadEventKind.FAILED:
                        raise RuntimeError("initial incremental load failed") from event.error
                raise RuntimeError("initial loader stopped before replacement")
            if time.perf_counter() >= deadline:
                raise TimeoutError("initial loader did not reach replacement point")
            if not (old_first_batch and entered.is_set()):
                time.sleep(poll_interval_s)

        started = time.perf_counter()
        new_session = loader.start(
            replacement, prepare_batch=IncrementalPlaybackPreparer(replacement)
        )
        release.set()
        first_batch_s: float | None = None
        old_finished_s: float | None = None
        state_count = 0
        while True:
            if old_finished_s is None and old_session.finished:
                old_finished_s = time.perf_counter() - started
            events = loader.drain()
            if not events and new_session.finished:
                events = loader.drain()
                if not events:
                    raise RuntimeError("replacement loader exited without completion")
            for event in events:
                if event.generation != new_session.generation:
                    raise RuntimeError("stale event escaped the replacement loader")
                if event.kind is LoadEventKind.FAILED:
                    raise RuntimeError("replacement incremental load failed") from event.error
                if event.kind is LoadEventKind.BATCH:
                    if event.batch is None or event.prepared is None:
                        raise RuntimeError("replacement batch was not prepared")
                    if first_batch_s is None:
                        first_batch_s = time.perf_counter() - started
                    state_count += len(event.batch.states)
                if event.kind is LoadEventKind.COMPLETE:
                    if first_batch_s is None or event.completion is None:
                        raise RuntimeError("replacement completed without a prepared batch")
                    if state_count != event.completion.state_count:
                        raise RuntimeError("replacement batch and completion counts differ")
                    completion_s = time.perf_counter() - started
                    while old_finished_s is None:
                        if old_session.finished:
                            old_finished_s = time.perf_counter() - started
                            break
                        if time.perf_counter() - started >= timeout_s:
                            raise TimeoutError("old worker did not terminate")
                        time.sleep(poll_interval_s)
                    return ReplacementMeasurement(
                        first_batch_s, completion_s, old_finished_s, state_count
                    )
            if time.perf_counter() - started >= timeout_s:
                raise TimeoutError("replacement loader did not complete in time")
            time.sleep(poll_interval_s)
    finally:
        loader.cancel()
        release.set()
        for session in (old_session, new_session):
            if session is not None and not session._finished.wait(timeout_s):
                raise TimeoutError("replacement worker did not terminate during cleanup")


def run_replacement_benchmarks(source: Path, replacement: Path, repeats: int) -> None:
    measure_replacement(source, replacement)
    samples = [measure_replacement(source, replacement) for _ in range(repeats)]
    print(f"Replacement input: {source} -> {replacement}")
    print("Settings: batch=512, flush=0.1s, queue=2, headless poll=0.001s")
    for label, values in (
        ("Replacement first batch", [sample.first_batch_s for sample in samples]),
        ("Replacement validated completion", [sample.completion_s for sample in samples]),
        (
            "Old worker observed finished",
            [sample.old_worker_observed_finished_s for sample in samples],
        ),
    ):
        _print_measurement(label, values)
    print(f"Replacement state counts: {[sample.state_count for sample in samples]}")
    _print_peak_rss("Process peak RSS including startup and warm-up")


def _print_peak_rss(label: str) -> None:
    if resource is not None and sys.platform in ("darwin", "linux"):
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_bytes = rss if sys.platform == "darwin" else rss * 1024
        print(f"{label}: {rss_bytes / 1048576:.1f} MiB")
    else:
        print(f"{label}: unavailable on this platform")


def run_parser_benchmarks(source: Path, repeats: int) -> None:
    """Measure the streaming parser without playback preparation or GUI handoff."""
    def parse() -> None:
        completion = read_oem_batches(
            source, batch_size=512, on_batch=lambda batch: None, cancel_event=Event()
        )
        if completion.state_count == 0:
            raise RuntimeError("parser completed without states")

    parse()
    print(f"Streaming parser input: {source}; bytes={source.stat().st_size}")
    _print_measurement("Streaming parser only", _measure(parse, repeats))


def measure_backpressure_cancellation(source: Path, timeout_s: float = 30.0) -> float:
    """Measure termination after cancellation while publication waits on a full queue."""
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    consumer_ready = Event()
    waiting = Event()
    preparer = IncrementalPlaybackPreparer(source)

    def prepare(batch: OemStateBatch) -> PreparedPlaybackBatch:
        if not consumer_ready.wait(timeout_s):
            raise TimeoutError("consumer did not drain the initial event")
        return preparer(batch)

    session = _MeasuredLoadSession(
        source,
        prepare,
        batch_size=1,
        batch_interval_s=0.1,
        queue_size=1,
    )
    observed_queue: Queue[LoadEvent] = Queue(maxsize=1)
    observed_queue.not_full = _ObservedWaitCondition(observed_queue.mutex, waiting)
    session._events = observed_queue
    try:
        session.start()
        initial_events = session.drain()
        consumer_ready.set()
        for event in initial_events:
            if event.kind is LoadEventKind.FAILED:
                raise RuntimeError("incremental load failed") from event.error
            if event.kind is LoadEventKind.COMPLETE:
                raise RuntimeError("loader completed before cancellation")
        deadline = time.perf_counter() + timeout_s
        while not waiting.wait(0.001):
            if session.finished:
                for event in session.drain():
                    if event.kind is LoadEventKind.FAILED:
                        raise RuntimeError("incremental load failed") from event.error
                raise RuntimeError("loader finished before waiting on a full event queue")
            if time.perf_counter() >= deadline:
                raise TimeoutError("loader did not wait on a full event queue")
        started = time.perf_counter()
        session.cancel()
        if not session.wait_finished(timeout_s):
            raise TimeoutError("cancelled incremental worker did not terminate")
        elapsed = time.perf_counter() - started
        events = session.drain()
        if not events or events[0].kind is not LoadEventKind.BATCH:
            raise RuntimeError("back-pressure probe did not queue a prepared batch")
        for event in events:
            if event.kind is LoadEventKind.FAILED:
                raise RuntimeError("incremental load failed") from event.error
            if event.kind is LoadEventKind.COMPLETE:
                raise RuntimeError("completion was queued before cancellation")
        return elapsed
    finally:
        session.cancel()
        consumer_ready.set()


def measure_phase_cancellation(
    source: Path, phase: str, timeout_s: float = 30.0
) -> float:
    """Measure termination after releasing a cancelled parser or preparation callback."""
    if phase not in ("parsing", "preparation"):
        raise ValueError("phase must be parsing or preparation")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    entered = Event()
    release = Event()
    original_validate = odm.validate_odm_line
    preparer = IncrementalPlaybackPreparer(source)

    def pause() -> None:
        entered.set()
        if not release.wait(timeout_s):
            raise TimeoutError(f"{phase} probe was not released")

    def validate(
        line: str,
        message_type: str,
        *,
        printable_ascii: bool = True,
        line_number: int | None = None,
    ) -> None:
        if phase == "parsing" and not entered.is_set():
            pause()
        original_validate(
            line, message_type, printable_ascii=printable_ascii, line_number=line_number
        )

    def prepare(batch: OemStateBatch) -> PreparedPlaybackBatch:
        if phase == "preparation":
            pause()
        return preparer(batch)

    session = _MeasuredLoadSession(
        source, prepare, batch_size=1, batch_interval_s=0.1, queue_size=2
    )
    with patch.object(odm, "validate_odm_line", validate):
        session.start()
        try:
            deadline = time.perf_counter() + timeout_s
            while not entered.wait(0.001):
                if session.finished:
                    for event in session.drain():
                        if event.kind is LoadEventKind.FAILED:
                            raise RuntimeError("incremental load failed") from event.error
                    raise RuntimeError(f"loader exited before entering {phase}")
                if time.perf_counter() >= deadline:
                    raise TimeoutError(f"loader did not enter {phase}")
            started = time.perf_counter()
            session.cancel()
            release.set()
            if not session.wait_finished(timeout_s):
                raise TimeoutError("cancelled incremental worker did not terminate")
            elapsed = time.perf_counter() - started
            for event in session.drain():
                if event.kind is LoadEventKind.FAILED:
                    raise RuntimeError("incremental load failed") from event.error
                if event.kind is not LoadEventKind.STARTED:
                    raise RuntimeError("cancelled session published an unexpected event")
            return elapsed
        finally:
            session.cancel()
            release.set()
            if not session.wait_finished(timeout_s):
                raise TimeoutError("incremental worker did not terminate during cleanup")


def run_data_benchmarks(source: Path, repeats: int, range_days: float) -> None:
    """Measure parser, derived-series, range conversion, and station access costs."""
    parsed_oem, timestamps_s, states_m = read_oem_states(source)
    segment_ids = parsed_oem.segment_ids[: len(timestamps_s)]
    selected_time_unit = TimeUnit.for_duration(timestamps_s[-1] - timestamps_s[0])

    parse_samples = _measure(lambda: read_oem_states(source), repeats)
    series_samples = _measure(
        lambda: compute_orbit_series(
            timestamps_s, states_m, selected_time_unit, segment_ids
        ),
        repeats,
    )
    preparation_samples = _measure(lambda: load_playback_data(source), repeats)

    playback_data = load_playback_data(source)
    source_track = playback_data.ground_track_source
    if source_track is None:
        raise RuntimeError("loaded playback data has no Ground Track source")
    start_s = float(playback_data.cursor.timestamps_s[0])
    end_s = float(playback_data.cursor.timestamps_s[-1])
    range_end_s = min(start_s + range_days * 86_400.0, end_s)
    bounds = (start_s, range_end_s)
    if range_end_s <= start_s:
        raise ValueError("the OEM must span a positive time range")

    sample_index = len(playback_data.cursor.timestamps_s) // 2
    state_position_to_itrf_m(
        playback_data.cursor.states_m[sample_index],
        source_track.frame_name,
        float(playback_data.cursor.timestamps_s[sample_index]),
    )
    ground_track_samples = _measure(
        lambda: prepare_ground_track(
            source_track,
            position_cache=EarthFixedPositionCache(),
            bounds=bounds,
        ),
        repeats,
    )

    print(f"Input: {source}")
    print(
        f"Samples: {playback_data.source_sample_count}; "
        f"coverage: {(end_s - start_s) / 86_400.0:.3f} days; "
        f"range: {(range_end_s - start_s) / 86_400.0:.3f} days"
    )
    _print_measurement("OEM parse", parse_samples)
    _print_measurement("compute_orbit_series", series_samples)
    _print_measurement("Full playback preparation", preparation_samples)
    _print_measurement("Ground Track range conversion", ground_track_samples)

    for station_count in (1, 3, 10):
        stations = _stations(station_count)

        def prepare_access() -> None:
            cache = StationAccessCache()
            for station in stations:
                cache.prepare(
                    source_track,
                    playback_data.cursor,
                    station,
                    bounds,
                )

        samples = _measure(prepare_access, repeats)
        _print_measurement(f"Access analysis ({station_count} stations)", samples)


def run_gui_stall_probe(source: Path) -> None:
    """Measure wx timer delays while the real play-oem app incrementally loads a file."""
    import wx

    from ephem_toolkit.play_oem import playback_data
    from ephem_toolkit.play_oem.app import PlayerApp

    initial_data = playback_data.empty_playback_data()
    player = PlayerApp(
        initial_data.clock,
        initial_data.series,
        initial_data.time_unit,
        initial_data.cursor,
        initial_data.object_name,
        initial_data.frame_context,
        dashboard_context=initial_data.dashboard_context,
        metadata_details=initial_data.metadata_details,
        ground_track_source=initial_data.ground_track_source,
        initial_file_path=str(source),
        oem_loaded=False,
    )
    timer = wx.Timer(player.frame)
    last_tick: list[Optional[float]] = [None]
    load_finished_at: list[Optional[float]] = [None]
    load_timer_gaps_s = []
    idle_timer_gaps_s = []
    refresh_metrics = {
        "calls": 0,
        "retained_views": 0,
        "replaced_views": 0,
        "retained_figures": 0,
        "replaced_figures": 0,
        "durations_s": [],
    }
    open_view_durations: dict[str, list[float]] = {}
    inside_refresh = [False]
    original_refresh = player._refresh_incremental_views
    original_open_panel_view = player.open_panel_view
    original_poll = player._poll_incremental_load
    original_start_load = player._start_incremental_load
    original_replace_data = player._replace_playback_data
    original_set_loaded = [player.workspace.set_oem_loaded]
    first_installed_at: list[Optional[float]] = [None]
    request_at: list[Optional[float]] = [None]
    playable_at: list[Optional[float]] = [None]
    first_plot: list[Optional[tuple[float, str]]] = [None]
    draw_connections = []
    initial_install_s: list[float] = []
    initial_open_view_s: dict[str, list[float]] = {}
    inside_initial_install = [False]

    def observe_start_load(path: str) -> None:
        request_at[0] = time.perf_counter()
        original_start_load(path)

    def observe_set_loaded(loaded: bool) -> None:
        original_set_loaded[0](loaded)
        if loaded and request_at[0] is not None and playable_at[0] is None:
            playable_at[0] = time.perf_counter()

    def observe_poll() -> None:
        original_poll()
        if player._active_load_first_batch and first_installed_at[0] is None:
            first_installed_at[0] = time.perf_counter()

    def observe_replace_data(*args, **kwargs) -> None:
        started = time.perf_counter()
        inside_initial_install[0] = True
        try:
            original_replace_data(*args, **kwargs)
        finally:
            inside_initial_install[0] = False
            initial_install_s.append(time.perf_counter() - started)

    def observe_open_panel_view(
        name: str, panel_id: str, stack: str = "middle", *, force_replace: bool = False
    ) -> None:
        started = time.perf_counter()
        original_open_panel_view(
            name, panel_id, stack, force_replace=force_replace
        )
        opened = player._open_panels.get(panel_id)
        if opened is not None and opened.canvas is not None and player._oem_loaded:
            def observe_draw(_event: object) -> None:
                if (
                    request_at[0] is not None
                    and first_plot[0] is None
                    and opened.panel.IsShownOnScreen()
                ):
                    first_plot[0] = (time.perf_counter(), name)

            connection = opened.canvas.mpl_connect("draw_event", observe_draw)
            draw_connections.append((opened.canvas, connection))
        if inside_refresh[0]:
            open_view_durations.setdefault(name, []).append(
                time.perf_counter() - started
            )
        if inside_initial_install[0]:
            initial_open_view_s.setdefault(name, []).append(
                time.perf_counter() - started
            )

    def observe_refresh(*, force: bool = False) -> None:
        before = {
            panel_id: (
                id(opened.view),
                None if opened.canvas is None else id(opened.canvas),
            )
            for panel_id, opened in player._open_panels.items()
        }
        refresh_started = time.perf_counter()
        inside_refresh[0] = True
        try:
            original_refresh(force=force)
        finally:
            inside_refresh[0] = False
        refresh_metrics["durations_s"].append(time.perf_counter() - refresh_started)
        after = {
            panel_id: (id(opened.view), None if opened.canvas is None else id(opened.canvas))
            for panel_id, opened in player._open_panels.items()
        }
        for panel_id in before.keys() & after.keys():
            old_view, old_figure = before[panel_id]
            new_view, new_figure = after[panel_id]
            if old_view == new_view:
                refresh_metrics["retained_views"] += 1
            else:
                refresh_metrics["replaced_views"] += 1
            if old_figure == new_figure:
                refresh_metrics["retained_figures"] += 1
            else:
                refresh_metrics["replaced_figures"] += 1
        refresh_metrics["calls"] += 1

    player._refresh_incremental_views = observe_refresh
    player.open_panel_view = observe_open_panel_view
    player._poll_incremental_load = observe_poll
    player._start_incremental_load = observe_start_load
    player._replace_playback_data = observe_replace_data
    player.workspace.set_oem_loaded = observe_set_loaded
    result = {"failed": False, "timed_out": False}
    started_at = time.perf_counter()

    def on_probe_tick(_event: wx.TimerEvent) -> None:
        del _event
        now = time.perf_counter()
        previous = last_tick[0]
        if (
            previous is not None
            and player._active_load_path is not None
        ):
            if player._oem_coverage_complete:
                idle_timer_gaps_s.append(now - previous)
            else:
                load_timer_gaps_s.append(now - previous)
        last_tick[0] = now

        if player._active_load_failed:
            result["failed"] = True
            if load_finished_at[0] is None:
                load_finished_at[0] = now
        elif player._oem_coverage_complete:
            if load_finished_at[0] is None:
                load_finished_at[0] = now
        elif now - started_at > 300.0:
            result["timed_out"] = True
            load_finished_at[0] = now

        if load_finished_at[0] is not None and now - load_finished_at[0] >= 2.0:
            timer.Stop()
            for canvas, connection in draw_connections:
                canvas.mpl_disconnect(connection)
            draw_connections.clear()
            del player._refresh_incremental_views
            del player.open_panel_view
            del player._poll_incremental_load
            del player._start_incremental_load
            del player._replace_playback_data
            del player.workspace.set_oem_loaded
            original_set_loaded.clear()
            player.frame.Close(force=True)

    player.frame.Bind(wx.EVT_TIMER, on_probe_tick, timer)
    if not timer.Start(10):
        raise RuntimeError("could not start wx benchmark timer")
    player.run()

    if not load_timer_gaps_s:
        raise RuntimeError(
            "wx timer probe recorded no intervals during incremental loading"
        )
    max_gap_ms = max(load_timer_gaps_s) * 1000.0
    median_gap_ms = statistics.median(load_timer_gaps_s) * 1000.0
    print(
        f"wx load timer gaps: samples={len(load_timer_gaps_s)}, "
        f"median={median_gap_ms:.1f}ms, "
        f"p95={_percentile(load_timer_gaps_s, 95) * 1000:.1f}ms, "
        f"p99={_percentile(load_timer_gaps_s, 99) * 1000:.1f}ms, "
        f"max={max_gap_ms:.1f}ms, "
        f"over_100ms={sum(gap > 0.1 for gap in load_timer_gaps_s)}"
    )
    if first_installed_at[0] is not None:
        print(f"First batch installed: {first_installed_at[0] - started_at:.3f}s")
    else:
        print("First batch installed: not observed")
    if initial_install_s:
        print(f"First playback-data installation: {initial_install_s[0]:.3f}s")
        for name, durations in initial_open_view_s.items():
            print(f"Initial panel construction ({name}): {sum(durations):.3f}s")
    if request_at[0] is not None and playable_at[0] is not None:
        print(f"First playback controls enabled: {playable_at[0] - request_at[0]:.3f}s")
    else:
        print("First playback controls enabled: not observed")
    if request_at[0] is not None and first_plot[0] is not None:
        print(
            f"First observed visible canvas render: {first_plot[0][0] - request_at[0]:.3f}s "
            f"(wxAgg draw event, panel={first_plot[0][1]})"
        )
    else:
        print("First observed visible canvas render: not observed")
    if (
        request_at[0] is not None
        and load_finished_at[0] is not None
        and not result["failed"]
        and not result["timed_out"]
    ):
        print(f"GUI observed completion: {load_finished_at[0] - request_at[0]:.3f}s")
    _print_peak_rss("GUI process peak RSS including startup")
    if idle_timer_gaps_s:
        print(
            f"wx post-load timer gaps: samples={len(idle_timer_gaps_s)}, "
            f"median={statistics.median(idle_timer_gaps_s) * 1000.0:.1f}ms, "
            f"max={max(idle_timer_gaps_s) * 1000.0:.1f}ms, "
            f"over_100ms={sum(gap > 0.1 for gap in idle_timer_gaps_s)}"
        )
    print(
        f"incremental refreshes: {refresh_metrics['calls']}, "
        f"retained/replaced views: {refresh_metrics['retained_views']}/"
        f"{refresh_metrics['replaced_views']}, retained/replaced figures: "
        f"{refresh_metrics['retained_figures']}/{refresh_metrics['replaced_figures']}, "
        f"max refresh: {max(refresh_metrics['durations_s'], default=0.0) * 1000.0:.1f}ms"
    )
    slowest_open = max(
        (
            (max(durations), name)
            for name, durations in open_view_durations.items()
            if durations
        ),
        default=(0.0, "none"),
    )
    print(
        f"slowest panel construction during refresh: {slowest_open[1]} "
        f"{slowest_open[0] * 1000.0:.1f}ms"
    )
    if result["timed_out"]:
        raise TimeoutError("incremental GUI load did not finish within 300 seconds")
    if result["failed"]:
        raise RuntimeError("incremental GUI load failed; inspect the play-oem status")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "oem",
        nargs="?",
        type=Path,
        default=Path("tests/data/JPSS-1.oem"),
        help="OEM fixture to benchmark (default: tests/data/JPSS-1.oem)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="number of unprofiled measurements per data benchmark (default: 3)",
    )
    parser.add_argument(
        "--range-days",
        type=float,
        default=1.0,
        help="Ground Track and Access plot range in days (default: 1)",
    )
    parser.add_argument(
        "--gui-stall-probe",
        action="store_true",
        help="open play-oem and measure wx timer delays during incremental loading",
    )
    parser.add_argument(
        "--incremental-bench",
        action="store_true",
        help="benchmark a real incremental session with a headless consumer",
    )
    parser.add_argument(
        "--replacement-bench",
        type=Path,
        metavar="OEM",
        help="benchmark replacing the positional OEM with this OEM, headlessly",
    )
    parser.add_argument(
        "--store-ingest-bench",
        type=int,
        metavar="CAPACITY",
        help="benchmark direct raw-store ingestion with this row capacity",
    )
    parser.add_argument(
        "--store-session-bench",
        type=str,
        metavar="CAPACITY",
        help="benchmark a bounded headless direct store session (CAPACITY or auto)",
    )
    parser.add_argument(
        "--parser-bench",
        action="store_true",
        help="benchmark streaming parsing without playback preparation",
    )
    parser.add_argument(
        "--cancellation-probe",
        action="store_true",
        help="measure worker cancellation while waiting on a full event queue",
    )
    parser.add_argument(
        "--phase-cancellation-probe",
        action="store_true",
        help="measure cancellation during synchronized parsing and preparation",
    )
    parser.add_argument(
        "--skip-data-benchmarks",
        action="store_true",
        help="skip one-shot data benchmarks (requires another probe)",
    )
    args = parser.parse_args(argv)
    store_session_requested = args.store_session_bench is not None
    store_session_capacity = None
    if store_session_requested:
        try:
            store_session_capacity = _parse_store_capacity(args.store_session_bench)
        except argparse.ArgumentTypeError as error:
            parser.error(str(error))
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.range_days <= 0.0:
        parser.error("--range-days must be positive")
    if args.store_ingest_bench is not None and args.store_ingest_bench < 1:
        parser.error("--store-ingest-bench capacity must be positive")
    if not args.oem.is_file():
        parser.error(f"OEM file does not exist: {args.oem}")
    if args.replacement_bench is not None and not args.replacement_bench.is_file():
        parser.error(f"replacement OEM file does not exist: {args.replacement_bench}")

    print(
        f"Environment: Python {platform.python_version()}, "
        f"{platform.platform()}, repeats={args.repeats}"
    )
    if not args.skip_data_benchmarks:
        run_data_benchmarks(args.oem, args.repeats, args.range_days)
    if args.incremental_bench:
        run_incremental_benchmarks(args.oem, args.repeats)
    if args.replacement_bench is not None:
        run_replacement_benchmarks(args.oem, args.replacement_bench, args.repeats)
    if args.store_ingest_bench is not None:
        run_store_ingest_benchmarks(args.oem, args.store_ingest_bench, args.repeats)
    if store_session_requested:
        run_store_session_benchmarks(args.oem, store_session_capacity, args.repeats)
    if args.parser_bench:
        run_parser_benchmarks(args.oem, args.repeats)
    if args.cancellation_probe:
        cancellation_samples = [
            measure_backpressure_cancellation(args.oem) for _ in range(args.repeats)
        ]
        _print_measurement("Waiting-on-full-queue cancellation", cancellation_samples)
    if args.phase_cancellation_probe:
        for phase in ("parsing", "preparation"):
            samples = [
                measure_phase_cancellation(args.oem, phase) for _ in range(args.repeats)
            ]
            _print_measurement(f"Cancellation during {phase} (immediate release)", samples)
    if args.gui_stall_probe:
        run_gui_stall_probe(args.oem)
    elif args.skip_data_benchmarks and not (
        args.incremental_bench
        or args.replacement_bench is not None
        or args.store_ingest_bench is not None
        or store_session_requested
        or args.cancellation_probe
        or args.phase_cancellation_probe
        or args.parser_bench
    ):
        parser.error("--skip-data-benchmarks requires another probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
