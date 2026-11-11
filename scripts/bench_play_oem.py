"""Repeatable data-layer and optional wx event-loop benchmarks for play-oem."""

from __future__ import annotations

import argparse
from pathlib import Path
import math
import platform
import statistics
import sys
from threading import Event
import time
from typing import Callable, Optional, Sequence

try:
    import resource
except ImportError:
    resource = None

from ephem_toolkit.play_oem import time_range
from ephem_toolkit.play_oem.chunk_memo import ChunkMemo, ChunkState
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem.incremental_loader import (
    IncrementalLoader,
    LoadEventKind,
)
from ephem_toolkit.play_oem.oem_data_store import (
    DERIVED_CHUNK_SIZE,
    OemDataStore,
    RawAppendNotice,
    RowSpan,
    StoreSnapshot,
)
from ephem_toolkit.play_oem.streaming_oem import read_oem_into_store


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


def _print_peak_rss(label: str) -> None:
    if resource is not None and sys.platform in ("darwin", "linux"):
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_bytes = rss if sys.platform == "darwin" else rss * 1024
        print(f"{label}: {rss_bytes / 1048576:.1f} MiB")
    else:
        print(f"{label}: unavailable on this platform")


def _memo_accounted_bytes(
    memo: ChunkMemo[int, RowSpan],
    row_count: int,
    columns: int,
    epoch: int,
    policy_revision: int,
) -> int:
    accounted_bytes = 0
    chunk_count = math.ceil(row_count / DERIVED_CHUNK_SIZE)
    for chunk_index in range(chunk_count):
        state = memo.state(
            chunk_index, epoch=epoch, policy_revision=policy_revision
        )
        if state not in (ChunkState.COMPLETE, ChunkState.TENTATIVE):
            continue
        chunk_rows = min(
            DERIVED_CHUNK_SIZE,
            row_count - chunk_index * DERIVED_CHUNK_SIZE,
        )
        accounted_bytes += chunk_rows * columns * 8
    return accounted_bytes


def _store_memory_diagnostics(store: OemDataStore) -> dict[str, int]:
    """Report derived-cache bytes using the store's eviction-budget accounting."""
    with store._lock:
        resident_bytes = 0
        for group, buffer in store._series_buffers.items():
            resident_bytes += _memo_accounted_bytes(
                store._series_memos[group],
                len(buffer),
                buffer.shape[1],
                store._epoch,
                0,
            )
        if store._earth_fixed_buffer is not None:
            resident_bytes += _memo_accounted_bytes(
                store._earth_fixed_memo,
                len(store._earth_fixed_buffer),
                store._earth_fixed_buffer.shape[1],
                store._epoch,
                0,
            )
        for tier in store._station_profiles.values():
            resident_bytes += _memo_accounted_bytes(
                tier.memo,
                tier.row_count,
                tier.buffer.shape[1],
                store._epoch,
                store._policy_revision,
            )
        ground_track_bytes = sum(
            sum(group.values.nbytes for group in query.value)
            for query in store._ground_track_cache.values()
        )
        resident_bytes += ground_track_bytes
        pinned_chunks = len(store._pinned_chunks)
        pinned_references = sum(store._pinned_chunks.values())
        budget_bytes = store._derived_memory_budget_bytes
    return {
        "budget_accounted_derived_bytes": resident_bytes,
        "ground_track_cache_bytes": ground_track_bytes,
        "pinned_chunk_keys": pinned_chunks,
        "pinned_chunk_references": pinned_references,
        "derived_memory_budget_bytes": budget_bytes,
    }


def _store_scheduler_backlog(store: OemDataStore) -> tuple[int, bool]:
    with store._scheduler_lock:
        return len(store._work_queue), store._active_work is not None


def _plot_range_for_coverage(
    coverage: tuple[float, float],
) -> time_range.PlotTimeRange | None:
    start_s, end_s = coverage
    if end_s <= start_s:
        return None
    range_start_s = max(start_s, end_s - 86_400.0)
    return time_range.PlotTimeRange(
        enabled=True,
        start=time_range.TimeRangeEndpoint("fixed", range_start_s),
        end=time_range.TimeRangeEndpoint("fixed", end_s),
    )


def run_parser_benchmarks(source: Path, repeats: int) -> None:
    """Measure direct parsing and raw-store ingestion without GUI handoff."""
    def parse() -> None:
        store = OemDataStore()
        store.begin(OemDataStore.capacity_for_file(source))
        completion = read_oem_into_store(
            source,
            store,
            batch_size=512,
            on_append=lambda notice: None,
            cancel_event=Event(),
        )
        if completion.state_count == 0:
            raise RuntimeError("parser completed without states")

    parse()
    print(f"Direct-store parser input: {source}; bytes={source.stat().st_size}")
    _print_measurement("Direct raw-store parsing", _measure(parse, repeats))


def run_data_benchmarks(source: Path, repeats: int, range_days: float) -> None:
    """Measure direct-store ingestion and lazy, range-bound analysis queries."""

    def read_store() -> tuple[OemDataStore, StoreSnapshot]:
        store = OemDataStore()
        store.begin(OemDataStore.capacity_for_file(source))
        completion = read_oem_into_store(
            source,
            store,
            batch_size=512,
            on_append=lambda _notice: None,
            cancel_event=Event(),
        )
        snapshot = store.snapshot()
        if completion.state_count != snapshot.sample_count:
            store.close()
            raise RuntimeError("store and completion counts do not match")
        return store, snapshot

    ingest_samples = _measure(
        lambda: measure_store_ingest(source, OemDataStore.capacity_for_file(source)),
        repeats,
    )
    store, snapshot = read_store()
    try:
        start_s = float(snapshot.raw[0, 0])
        end_s = float(snapshot.raw[-1, 0])
        range_end_s = min(start_s + range_days * 86_400.0, end_s)
        if range_end_s <= start_s:
            raise ValueError("the OEM must span a positive time range")
        bounds = (start_s, range_end_s)
    finally:
        store.close()

    def measure_queries(
        query: Callable[
            [OemDataStore, StoreSnapshot, tuple[float, float]], None
        ],
    ) -> list[float]:
        samples = []
        for _ in range(repeats):
            query_store, query_snapshot = read_store()
            started = time.perf_counter()
            try:
                query(query_store, query_snapshot, bounds)
                samples.append(time.perf_counter() - started)
            finally:
                query_store.close()
        return samples

    ground_track_samples = measure_queries(
        lambda query_store, query_snapshot, query_bounds: query_store.ground_track(
            query_snapshot, query_bounds, wait=True
        )
    )
    print(f"Input: {source}")
    print(
        f"Samples: {snapshot.sample_count}; "
        f"coverage: {(end_s - start_s) / 86_400.0:.3f} days; "
        f"range: {(range_end_s - start_s) / 86_400.0:.3f} days"
    )
    _print_measurement("Direct raw-store ingestion", ingest_samples)
    _print_measurement("Lazy Ground Track range query", ground_track_samples)

    for station_count in (1, 3, 10):
        stations = _stations(station_count)

        def prepare_access(
            query_store: OemDataStore,
            query_snapshot: StoreSnapshot,
            query_bounds: tuple[float, float],
        ) -> None:
            for station in stations:
                query_store.station_access(
                    query_snapshot, station, query_bounds, wait=True
                )

        _print_measurement(
            f"Lazy station access ({station_count} stations)",
            measure_queries(prepare_access),
        )


def run_gui_stall_probe(
    source: Path, *, range_probe: bool = False, drive_ranges: bool = True
) -> None:
    """Measure wx load responsiveness, optionally changing Ground Track ranges."""
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
    original_install_snapshot = player._install_store_snapshot
    original_set_loaded = [player.workspace.set_oem_loaded]
    first_installed_at: list[Optional[float]] = [None]
    request_at: list[Optional[float]] = [None]
    playable_at: list[Optional[float]] = [None]
    first_plot: list[Optional[tuple[float, str]]] = [None]
    draw_connections = []
    initial_install_s: list[float] = []
    initial_open_view_s: dict[str, list[float]] = {}
    inside_initial_install = [False]
    range_view_opened = [False]
    range_probe_replaced_view: list[Optional[str]] = [None]
    probe_views_closed = [False]
    range_milestones = (0.25, 0.5, 0.75)
    next_range_milestone = [0]
    range_requests: list[tuple[float, int, int, bool]] = []
    range_render_observations: list[tuple[str, float]] = []
    pending_range_render_at: list[Optional[float]] = [None]
    memory_samples: list[tuple[str, dict[str, int]]] = []
    queue_maxima = {
        "loader_events": 0,
        "store_notices": 0,
        "store_work": 0,
        "store_active_work": 0,
    }
    queue_sample_count = [0]
    last_queue_sample_at = [0.0]
    retained_memory_sampled = [False]
    post_close_memory_sampled = [False]
    view_closed_at: list[Optional[float]] = [None]

    def current_store() -> Optional[OemDataStore]:
        context = player._store_view_context
        if context is not None:
            return context.store
        return player._oem_store

    def record_memory_sample(label: str) -> None:
        store = current_store()
        if store is not None:
            metrics = _store_memory_diagnostics(store)
            queued_work, active_work = _store_scheduler_backlog(store)
            metrics["derived_queued_work"] = queued_work
            metrics["derived_active_work"] = int(active_work)
            memory_samples.append((label, metrics))

    def sample_queues(now: float) -> None:
        if not range_probe or now - last_queue_sample_at[0] < 0.1:
            return
        last_queue_sample_at[0] = now
        session = player._incremental_loader.session
        loader_events = 0 if session is None else session._events.qsize()
        store_notices = player._store_notice_queue.qsize()
        store = current_store()
        store_work = 0
        store_active_work = False
        if store is not None:
            store_work, store_active_work = _store_scheduler_backlog(store)
        queue_maxima["loader_events"] = max(
            queue_maxima["loader_events"], loader_events
        )
        queue_maxima["store_notices"] = max(
            queue_maxima["store_notices"], store_notices
        )
        queue_maxima["store_work"] = max(queue_maxima["store_work"], store_work)
        queue_maxima["store_active_work"] = max(
            queue_maxima["store_active_work"], int(store_active_work)
        )
        queue_sample_count[0] += 1

    def observe_panel_draw(name: str, panel_id: str, opened) -> None:
        canvas = getattr(opened, "canvas", None)
        if canvas is None and range_probe and name == "ground-track":
            canvas = getattr(opened.view, "_canvas", None)
        if canvas is None:
            return

        def observe_draw(_event: object) -> None:
            if (
                request_at[0] is not None
                and first_plot[0] is None
                and opened.panel.IsShownOnScreen()
            ):
                first_plot[0] = (time.perf_counter(), name)
            if (
                range_probe
                and name == "ground-track"
                and pending_range_render_at[0] is not None
                and opened.panel.IsShownOnScreen()
            ):
                range_render_observations.append(
                    (name, time.perf_counter() - pending_range_render_at[0])
                )
                pending_range_render_at[0] = None

        connection = canvas.mpl_connect("draw_event", observe_draw)
        draw_connections.append((canvas, connection, panel_id))

    def drive_range_probe() -> None:
        if (
            not range_probe
            or not player._active_load_first_batch
            or player._oem_coverage_complete
        ):
            return
        if not range_view_opened[0]:
            record_memory_sample("before-ground-track-open")
            visible_panel = next(
                (
                    opened
                    for opened in player._open_panels.values()
                    if opened.view_name == "speed-altitude"
                    and opened.panel.IsShownOnScreen()
                ),
                None,
            )
            if visible_panel is None:
                visible_panel = next(
                    (
                        opened
                        for opened in player._open_panels.values()
                        if opened.panel.IsShownOnScreen()
                    ),
                    None,
                )
            if visible_panel is None:
                raise RuntimeError(
                    "no visible graph panel is available for the Ground Track probe"
                )
            range_panel_id = visible_panel.panel_id
            range_probe_replaced_view[0] = visible_panel.view_name
            player.open_ground_track_view(
                panel_id=range_panel_id,
                stack=visible_panel.stack,
                force_replace=True,
            )
            range_view_opened[0] = True
            opened = player._open_panels.get(range_panel_id)
            if opened is None or opened.view_name != "ground-track":
                raise RuntimeError("Ground Track probe view was not installed")
            observe_panel_draw("ground-track", range_panel_id, opened)
            record_memory_sample("after-ground-track-open")
        if not drive_ranges:
            return
        if pending_range_render_at[0] is not None:
            return
        store = current_store()
        if store is None or next_range_milestone[0] >= len(range_milestones):
            return
        capacity = store.capacity
        if capacity <= 0:
            return
        sample_count = store.snapshot().sample_count
        fraction = range_milestones[next_range_milestone[0]]
        if sample_count < int(capacity * fraction):
            return
        coverage = (player.clock.t_start, player.clock.t_end)
        rule = _plot_range_for_coverage(coverage)
        next_range_milestone[0] += 1
        if rule is None:
            return
        request_time = time.perf_counter()
        pending_range_render_at[0] = request_time
        player._apply_plot_time_range(rule)
        work_count, work_active = _store_scheduler_backlog(store)
        range_requests.append((fraction, sample_count, work_count, work_active))
        record_memory_sample(f"range-{int(fraction * 100)}%-requested")
        if work_count or work_active:
            queue_maxima["store_work"] = max(
                queue_maxima["store_work"], work_count
            )
            queue_maxima["store_active_work"] = max(
                queue_maxima["store_active_work"], int(work_active)
            )

    def close_probe_views() -> None:
        if not range_view_opened[0] or probe_views_closed[0]:
            return
        record_memory_sample("before-closing-views")
        for panel_id, opened in tuple(player._open_panels.items()):
            view_name = opened.view_name
            player.close_panel(panel_id)
            for canvas, connection, connected_panel_id in tuple(draw_connections):
                if connected_panel_id == panel_id:
                    canvas.mpl_disconnect(connection)
                    draw_connections.remove(
                        (canvas, connection, connected_panel_id)
                    )
            record_memory_sample(f"after-close-{view_name}")
        probe_views_closed[0] = True
        view_closed_at[0] = time.perf_counter()

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

    def observe_install_snapshot(*args, **kwargs) -> None:
        started = time.perf_counter()
        inside_initial_install[0] = True
        try:
            original_install_snapshot(*args, **kwargs)
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
        if opened is not None and (player._oem_loaded or range_probe):
            observe_panel_draw(name, panel_id, opened)
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
    player._install_store_snapshot = observe_install_snapshot
    player.workspace.set_oem_loaded = observe_set_loaded
    result = {"failed": False, "timed_out": False}
    started_at = time.perf_counter()

    def on_probe_tick(_event: wx.TimerEvent) -> None:
        del _event
        now = time.perf_counter()
        sample_queues(now)
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

        if (
            range_probe
            and load_finished_at[0] is None
            and not result["failed"]
            and not result["timed_out"]
        ):
            drive_range_probe()

        if range_probe and load_finished_at[0] is not None:
            elapsed_since_finish = now - load_finished_at[0]
            if elapsed_since_finish >= 0.5 and not retained_memory_sampled[0]:
                record_memory_sample("load-complete-view-retained")
                retained_memory_sampled[0] = True
                close_probe_views()
            if view_closed_at[0] is not None and not post_close_memory_sampled[0]:
                store = current_store()
                queued_work, active_work = (
                    (0, False)
                    if store is None
                    else _store_scheduler_backlog(store)
                )
                elapsed_since_close = now - view_closed_at[0]
                if (
                    (elapsed_since_close >= 0.5 and queued_work == 0 and not active_work)
                    or elapsed_since_close >= 5.0
                ):
                    record_memory_sample("after-close-settle")
                    post_close_memory_sampled[0] = True

        shutdown_delay_s = 6.0 if range_probe else 2.0
        if (
            load_finished_at[0] is not None
            and now - load_finished_at[0] >= shutdown_delay_s
        ):
            close_probe_views()
            timer.Stop()
            for canvas, connection, _panel_id in draw_connections:
                canvas.mpl_disconnect(connection)
            draw_connections.clear()
            del player._refresh_incremental_views
            del player.open_panel_view
            del player._poll_incremental_load
            del player._start_incremental_load
            del player._install_store_snapshot
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
    if range_probe:
        if drive_ranges:
            print(
                f"overlap range requests: {len(range_requests)}/{len(range_milestones)}"
            )
        else:
            print("Ground Track range baseline: range changes not driven")
        if range_probe_replaced_view[0] is not None:
            print(
                "Ground Track probe replaced visible panel: "
                f"{range_probe_replaced_view[0]}"
            )
        for fraction, sample_count, work_count, work_active in range_requests:
            print(
                f"range request at {fraction:.0%} load progress: "
                f"samples={sample_count}, queued_work={work_count}, "
                f"active_work={work_active}"
            )
        if range_render_observations:
            print(
                "Ground Track range request-to-visible-render: "
                f"samples={len(range_render_observations)}, "
                f"median={statistics.median(latency for _, latency in range_render_observations) * 1000.0:.1f}ms, "
                f"max={max(latency for _, latency in range_render_observations) * 1000.0:.1f}ms, "
                "panels="
                + ",".join(name for name, _ in range_render_observations)
            )
        else:
            print("Ground Track range request-to-visible-render: not observed")
        print(
            "approximate maximum queue depth: "
            f"load events={queue_maxima['loader_events']}, "
            f"store notices={queue_maxima['store_notices']}, "
            f"derived queued={queue_maxima['store_work']}, "
            f"derived active={queue_maxima['store_active_work']} "
            f"(samples={queue_sample_count[0]})"
        )
        for label, metrics in memory_samples:
            print(
                f"store derived memory ({label}): "
                f"accounted={metrics['budget_accounted_derived_bytes'] / 1048576:.1f}MiB, "
                f"ground_track={metrics['ground_track_cache_bytes'] / 1048576:.1f}MiB, "
                f"store_pinned_chunks={metrics['pinned_chunk_keys']} "
                f"({metrics['pinned_chunk_references']} references), "
                f"budget={metrics['derived_memory_budget_bytes'] / 1048576:.1f}MiB, "
                f"queued_work={metrics['derived_queued_work']}, "
                f"active_work={bool(metrics['derived_active_work'])}"
            )
        print(
            "Store pin counts are aggregate and not attributable to a specific "
            "view; derived bytes follow eviction-budget accounting, not RSS."
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
        "--gui-overlap-probe",
        action="store_true",
        help="drive Ground Track range changes during incremental loading",
    )
    parser.add_argument(
        "--gui-range-baseline-probe",
        action="store_true",
        help="load with a Ground Track view open but do not change its range",
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
        help="benchmark direct-to-store parsing without GUI handoff",
    )
    parser.add_argument(
        "--skip-data-benchmarks",
        action="store_true",
        help="skip one-shot data benchmarks (requires another probe)",
    )
    args = parser.parse_args(argv)
    gui_probe_count = sum(
        (
            args.gui_stall_probe,
            args.gui_overlap_probe,
            args.gui_range_baseline_probe,
        )
    )
    if gui_probe_count > 1:
        parser.error("select only one GUI probe mode")
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
    print(
        f"Environment: Python {platform.python_version()}, "
        f"{platform.platform()}, repeats={args.repeats}"
    )
    if not args.skip_data_benchmarks:
        run_data_benchmarks(args.oem, args.repeats, args.range_days)
    if args.store_ingest_bench is not None:
        run_store_ingest_benchmarks(args.oem, args.store_ingest_bench, args.repeats)
    if store_session_requested:
        run_store_session_benchmarks(args.oem, store_session_capacity, args.repeats)
    if args.parser_bench:
        run_parser_benchmarks(args.oem, args.repeats)
    if args.gui_overlap_probe:
        run_gui_stall_probe(args.oem, range_probe=True)
    elif args.gui_range_baseline_probe:
        run_gui_stall_probe(args.oem, range_probe=True, drive_ranges=False)
    elif args.gui_stall_probe:
        run_gui_stall_probe(args.oem)
    elif args.skip_data_benchmarks and not (
        args.store_ingest_bench is not None
        or store_session_requested
        or args.parser_bench
        or args.gui_stall_probe
        or args.gui_overlap_probe
        or args.gui_range_baseline_probe
    ):
        parser.error("--skip-data-benchmarks requires another probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
