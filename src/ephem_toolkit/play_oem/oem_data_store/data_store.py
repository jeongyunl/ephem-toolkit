"""Store-owned raw OEM storage with atomic prefix publication."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
import heapq
import logging
from pathlib import Path
from threading import Event, RLock
from typing import cast
import weakref

import numpy as np

from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.core.interpolator.interpolator import Interpolator
from ..chunk_memo import ChunkMemo, ChunkMemoCounters
from ..clock import SampleTimes
from ..ground_footprints import GroundFootprints
from ..cursor import CursorState, CursorStatus
from ..ground_stations import GroundStation, StationMetrics
from ..series import (
    SERIES_GROUPS,
    SeriesGroupName,
)
from ..station_access import AccessInterval
from ..time_unit import TimeUnit
import ephem_toolkit.play_oem.oem_data_store as public_store
from .store_support import (
    _earth_centered_frame_name,
    _capacity_for_file,
    _mapped_float_array,
    _validate_query_time,
)
from .public_types import (
    EARTH_FIXED_COLUMNS,
    TierName,
    TimeBounds,
    LoadStatus,
    OemMetadata,
    InterpolationPolicy,
    StoreQuery,
    RowSpan,
    QueryRequest,
    RangeHint,
    ColumnGroupView,
    StationAccessView,
    TierNotice,
    StoreNotice,
    StoreSnapshot,
    RawAppendNotice,
    RawReservation,
    SeriesGroups,
    GroundTrackGroups,
    EarthFixedPositions,
)
from .internal_types import (
    _ScheduledWork,
    _StationProfileTier,
    _StationSegmentLayout,
)
from .derived_range_compute import compute_missing_chunk_ranges
from .raw_reservation import (
    abort as abort_raw_reservation,
    check_reservation,
    commit as commit_raw_reservation,
    discard_if_active as discard_raw_reservation,
    reserve as reserve_raw,
)
from .prefetch_scheduling import (
    PrefetchScheduler,
    priority_for_request,
    request_rows,
)
from .station_profile_tier import (
    clear_station_profiles,
    compute_profile_ranges,
    profile_storage,
)
from .derived_buffer_manager import DerivedBufferManager
from .series_tier import query_series, series_storage
from .earth_fixed_tier import query_earth_fixed
from .ground_track_tier import query_ground_track
from .station_access_tier import query_station_access
from .state_lookup import (
    earth_fixed_states_at as lookup_earth_fixed_states,
    state_at as lookup_state,
)
from .footprint_tier import query_footprints
from .raw_epoch_lifecycle import (
    allocate_if_epoch as allocate_raw_epoch,
    begin as begin_raw_epoch,
    begin_loading as begin_raw_loading,
    cancel_if_epoch as cancel_raw_epoch,
    clear_if_epoch as clear_raw_epoch,
    mark_complete as mark_raw_complete,
    mark_failed as mark_raw_failed,
    reset_locked as reset_raw_epoch,
)

_LOGGER = logging.getLogger(__name__)


class OemDataStore:
    """Fixed-capacity raw and lazily materialized derived storage.

    A single writer fills a reservation and must not mutate it during commit or
    retain writable aliases after commit or abort. Snapshots expose only committed
    rows; derived query buffers are allocated on first request and remain tied to
    the current epoch.
    """

    def __init__(self, derived_memory_budget_bytes: int = 256 * 1024 * 1024) -> None:
        if (
            isinstance(derived_memory_budget_bytes, bool)
            or not isinstance(derived_memory_budget_bytes, int)
            or derived_memory_budget_bytes < 1
        ):
            raise ValueError("derived_memory_budget_bytes must be a positive integer")
        self._lock = RLock()
        self._derived_compute_lock = RLock()
        self._derived_memory_budget_bytes = derived_memory_budget_bytes
        self._chunk_access_order: dict[tuple[int, int], int] = {}
        self._chunk_ranges: dict[tuple[int, int], tuple[TimeBounds, ...]] = {}
        self._buffer_touch_sequence = 0
        self._pinned_chunks: dict[tuple[int, int], int] = {}
        self._derived_buffer_manager = DerivedBufferManager(self)
        self._epoch = 0
        self._revision = 0
        self._policy_revision = 0
        self._interpolation_policy = InterpolationPolicy()
        self._state_interpolator = self._make_state_interpolator(
            self._interpolation_policy
        )
        self._sample_count = 0
        self._raw: np.ndarray | None = None
        self._segment_ids: np.ndarray | None = None
        self._sample_times: SampleTimes | None = None
        self._segment_bounds: list[tuple[int, int, int]] = []
        self._max_gap_s = 0.0
        self._status = LoadStatus.EMPTY
        self._header: tuple[tuple[str, object], ...] = ()
        self._meta: tuple[tuple[str, object], ...] = ()
        self._failure: str | None = None
        self._reservation: RawReservation | None = None
        self._validating = False
        self._series_buffers: dict[SeriesGroupName, np.ndarray] = {}
        self._series_ready: dict[SeriesGroupName, np.ndarray] = {}
        self._series_memos: dict[SeriesGroupName, ChunkMemo[int, RowSpan]] = {}
        self._earth_fixed_buffer: np.ndarray | None = None
        self._earth_fixed_ready: np.ndarray | None = None
        self._earth_fixed_memo: ChunkMemo[int, RowSpan] = ChunkMemo()
        self._earth_fixed_state_cache: OrderedDict[tuple[int, str, int], np.ndarray] = (
            OrderedDict()
        )
        self._earth_fixed_cursor_cache: OrderedDict[
            tuple[int, int, str, int, float],
            CursorState,
        ] = OrderedDict()
        self._ground_track_cache: OrderedDict[
            tuple[object, ...], StoreQuery[GroundTrackGroups]
        ] = OrderedDict()
        self._station_profiles: dict[tuple[object, ...], _StationProfileTier] = {}
        self._station_interval_cache: dict[
            tuple[object, ...], tuple[AccessInterval, ...]
        ] = {}
        self._station_interval_layout_cache: dict[
            tuple[object, ...], tuple[AccessInterval, ...]
        ] = {}
        self._footprint_cache: OrderedDict[tuple[object, ...], GroundFootprints] = (
            OrderedDict()
        )
        self._scheduler_lock = RLock()
        self._scheduler_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="oem-derived",
        )
        self._scheduled_work: dict[
            tuple[int, int, int, QueryRequest], _ScheduledWork
        ] = {}
        self._work_queue: list[_ScheduledWork] = []
        self._active_work: _ScheduledWork | None = None
        self._scheduler_drain_active = False
        self._scheduler_closed = False
        self._prefetch_scheduler = PrefetchScheduler(self)
        self._task_sequence = 0
        self._range_generation = 0
        self._range_hint: RangeHint | None = None
        self._tier_interest: dict[TierName, int] = {}
        self._notice_subscribers: list[Callable[[StoreNotice], None]] = []

    @staticmethod
    def _make_state_interpolator(policy: InterpolationPolicy) -> Interpolator:
        if policy.method == "linear":
            spec = None
        else:
            try:
                interpolation_type = InterpolationType(policy.method)
            except ValueError as error:
                raise ValueError(
                    f"unsupported OEM interpolation type: {policy.method!r}"
                ) from error
            spec = InterpolationSpec(
                interpolation_type,
                degree=policy.degree or None,
            )
        return InterpolatorFactory.create(
            spec=spec,
            dimension=6,
            is_cartesian_state=policy.method == "hermite",
            stateless=True,
        )

    def set_interpolation(self, policy: InterpolationPolicy) -> None:
        """Set the point-query interpolation policy for subsequent snapshots."""
        if not isinstance(policy, InterpolationPolicy):
            raise TypeError("policy must be an InterpolationPolicy")
        with self._lock:
            if policy == self._interpolation_policy:
                return
            interpolator = self._make_state_interpolator(policy)
            self._interpolation_policy = policy
            self._state_interpolator = interpolator
            self._policy_revision += 1
            self._clear_station_tiers_locked()

    def set_range_hint(self, hint: RangeHint) -> None:
        """Replace current range interest and cancel stale queued work."""
        if not isinstance(hint, RangeHint):
            raise TypeError("hint must be a RangeHint")
        with self._scheduler_lock:
            if hint == self._range_hint:
                return
            self._range_generation += 1
            self._range_hint = hint
            for key, work in tuple(self._scheduled_work.items()):
                priority = self._priority_for_request(work.request, hint)
                stale_during_drag = hint.dragging and priority > 1
                stale_range = priority > 2
                if work.generation < self._range_generation and (
                    stale_during_drag or stale_range
                ):
                    work.future.cancel()
                    if work is not self._active_work:
                        self._scheduled_work.pop(key, None)
                    continue
                work.priority = priority
                work.generation = self._range_generation
            heapq.heapify(self._work_queue)
            self._start_scheduler_drain_locked()

    def subscribe_tier(self, tier: TierName) -> Callable[[], None]:
        """Register an open view's interest in a derived tier."""
        if tier not in (
            "series",
            "earth-fixed",
            "ground-track",
            "station-access",
            "footprints",
        ):
            raise ValueError(f"unsupported derived tier: {tier!r}")
        with self._scheduler_lock:
            self._tier_interest[tier] = self._tier_interest.get(tier, 0) + 1
            self._reprioritize_queued_work_locked()

        def unsubscribe() -> None:
            with self._scheduler_lock:
                count = self._tier_interest.get(tier, 0)
                if count <= 1:
                    self._tier_interest.pop(tier, None)
                else:
                    self._tier_interest[tier] = count - 1
                self._reprioritize_queued_work_locked()

        return unsubscribe

    def subscribe(self, callback: Callable[[StoreNotice], None]) -> Callable[[], None]:
        """Subscribe to append, reset, and derived-tier notices."""
        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._scheduler_lock:
            self._notice_subscribers.append(callback)

        def unsubscribe() -> None:
            with self._scheduler_lock:
                if callback in self._notice_subscribers:
                    self._notice_subscribers.remove(callback)

        return unsubscribe

    def prefetch(self, snapshot: StoreSnapshot, request: QueryRequest) -> Future[None]:
        """Queue a prioritized, cancellable range request."""
        return self._prefetch_scheduler.prefetch(snapshot, request)

    def close(self) -> None:
        """Cancel pending range work and stop the background worker."""
        self._prefetch_scheduler.close()

    def _priority_for_request(
        self, request: QueryRequest, hint: RangeHint | None
    ) -> int:
        return priority_for_request(self, request, hint)

    def _reprioritize_queued_work_locked(self) -> None:
        self._prefetch_scheduler.reprioritize_locked()

    def _start_scheduler_drain_locked(self) -> None:
        self._prefetch_scheduler.start_drain_locked()

    def _drain_scheduler_queue(self) -> None:
        self._prefetch_scheduler.drain_queue()

    @staticmethod
    def _request_rows(work: _ScheduledWork) -> int:
        return request_rows(work)

    def _run_prefetch(self, work: _ScheduledWork) -> None:
        self._prefetch_scheduler.run_prefetch(work)

    def _finish_scheduled_work(self, work: _ScheduledWork) -> None:
        self._prefetch_scheduler.finish_scheduled_work(work)

    def _cancel_scheduled_work(self) -> None:
        self._prefetch_scheduler.cancel_scheduled_work()

    def _publish_notice(self, notice: TierNotice) -> None:
        with self._scheduler_lock:
            subscribers = tuple(self._notice_subscribers)
        for callback in subscribers:
            try:
                callback(notice)
            except Exception:
                _LOGGER.exception("Store notice subscriber failed")

    @property
    def capacity(self) -> int:
        """Maximum raw rows allocated for the current epoch, or zero when empty."""
        with self._lock:
            return len(self._raw) if self._raw is not None else 0

    @property
    def epoch(self) -> int:
        """Current epoch, including while its capacity is being determined."""
        with self._lock:
            return self._epoch

    @property
    def status(self) -> LoadStatus:
        """Lifecycle state of the current epoch."""
        with self._lock:
            return self._status

    @property
    def sample_times(self) -> SampleTimes:
        """Return the live read-only timestamp view for the active epoch."""
        with self._lock:
            if self._sample_times is None:
                raise RuntimeError("store timestamps are not allocated")
            return self._sample_times

    @staticmethod
    def capacity_for_file(
        source: str | Path, *, cancel_event: Event | None = None
    ) -> int:
        """Return a safe row-capacity bound from non-covariance OEM lines.

        State rows are outside covariance blocks and the parser accepts at most one
        state row per physical input line. Counting every other line as well keeps
        this a safe upper bound without reserving for covariance matrices. Universal
        newlines and a final unterminated line are supported. Files are scanned as
        strict UTF-8 text in bounded chunks. An optional cancellation event is
        checked before scanning and between bounded reads.
        """
        path = Path(source)
        return _capacity_for_file(path, cancel_event)

    def begin(self, capacity: int) -> int:
        """Start a new epoch with a caller-provided maximum number of rows."""
        return begin_raw_epoch(self, capacity)

    def begin_loading(self) -> int:
        """Start a loading epoch before its fixed capacity is known."""
        return begin_raw_loading(self)

    def allocate_if_epoch(self, epoch: int, capacity: int) -> bool:
        """Allocate fixed buffers if ``epoch`` remains the active loading epoch."""
        return allocate_raw_epoch(self, epoch, capacity)

    def clear(self) -> None:
        """Invalidate the active epoch; existing snapshots retain their buffers."""
        with self._lock:
            self._reset_locked()

    def clear_if_epoch(self, epoch: int) -> bool:
        """Invalidate ``epoch`` only if it is still current."""
        return clear_raw_epoch(self, epoch)

    def cancel_if_epoch(self, epoch: int) -> bool:
        """Stop the active producer while preserving its committed prefix."""
        return cancel_raw_epoch(self, epoch)

    def mark_complete(
        self,
        epoch: int,
        header: tuple[tuple[str, object], ...],
        meta: tuple[tuple[str, object], ...],
    ) -> None:
        """Publish EOF-validated metadata and mark the active epoch complete."""
        mark_raw_complete(self, epoch, header, meta)

    def publish_loading_metadata(
        self, epoch: int, meta: tuple[tuple[str, object], ...]
    ) -> None:
        """Publish provisional first-segment metadata for loading queries."""
        from .store_support import _freeze_metadata

        with self._lock:
            if epoch != self._epoch or self._status is not LoadStatus.LOADING:
                raise RuntimeError("store epoch is no longer loading")
            self._meta = _freeze_metadata(meta)
            self._revision += 1

    def mark_failed(self, epoch: int, failure: Exception) -> bool:
        """Mark the current load failed and discard its unpublished suffix."""
        return mark_raw_failed(self, epoch, failure)

    def _reset_locked(self) -> None:
        reset_raw_epoch(self)

    def _clear_station_tiers_locked(self) -> None:
        clear_station_profiles(self)

    def reserve(self, max_rows: int, *, epoch: int | None = None) -> RawReservation:
        """Reserve up to ``max_rows`` in the unpublished suffix."""
        return reserve_raw(self, max_rows, epoch=epoch)

    def abort(self, reservation: RawReservation) -> None:
        """Discard an unpublished reservation without changing coverage."""
        abort_raw_reservation(self, reservation)

    def discard_if_active(self, reservation: RawReservation) -> bool:
        """Release a still-active reservation during producer cleanup."""
        return discard_raw_reservation(self, reservation)

    def _check_reservation_locked(self, reservation: RawReservation) -> None:
        check_reservation(self, reservation)

    def commit(self, reservation: RawReservation, count: int) -> RawAppendNotice:
        """Validate and atomically publish a populated reservation prefix."""
        return commit_raw_reservation(self, reservation, count)

    def snapshot(self) -> StoreSnapshot:
        """Capture a stable, read-only view of the committed prefix."""
        with self._lock:
            if self._raw is None or self._segment_ids is None:
                raise RuntimeError("store has no active epoch")
            raw = np.frombuffer(
                memoryview(self._raw).toreadonly(),
                dtype=np.float64,
                count=self._sample_count * 7,
            ).reshape((-1, 7))
            segments = np.frombuffer(
                memoryview(self._segment_ids).toreadonly(),
                dtype=np.int64,
                count=self._sample_count,
            )
            bounds = np.asarray(
                [(start, stop) for _, start, stop in self._segment_bounds],
                dtype=np.int64,
            ).reshape((-1, 2))
            bounds.setflags(write=False)
            duration_s = float(raw[-1, 0] - raw[0, 0]) if self._sample_count else 0.0
            return StoreSnapshot(
                epoch=self._epoch,
                revision=self._revision,
                policy_revision=self._policy_revision,
                sample_count=self._sample_count,
                metadata=OemMetadata(self._header, self._meta),
                time_unit=TimeUnit.for_duration(duration_s),
                raw=raw,
                segment_ids=segments,
                segment_bounds=bounds,
                max_within_segment_gap_s=self._max_gap_s,
                status=self._status,
                failure=self._failure,
            )

    def state_at(self, snapshot: StoreSnapshot, t_s: float) -> CursorState:
        """Resolve an exact or interpolated state without copying the raw history."""
        return lookup_state(self, snapshot, t_s)

    def earth_fixed_state_at(self, snapshot: StoreSnapshot, t_s: float) -> CursorState:
        """Resolve a state by interpolating Earth-fixed OEM samples."""
        return lookup_state(self, snapshot, t_s, earth_fixed=True)

    def earth_fixed_states_at(
        self,
        snapshot: StoreSnapshot,
        query_times_s: np.ndarray,
    ) -> np.ndarray:
        """Resolve many Earth-fixed states with shared sample conversions."""
        return lookup_earth_fixed_states(self, snapshot, query_times_s)

    def station_metrics_at(
        self,
        snapshot: StoreSnapshot,
        station: GroundStation,
        t_s: float,
    ) -> StationMetrics | None:
        """Return station metrics at a valid current state without extrapolation."""
        self._validate_snapshot_epoch(snapshot)
        if not isinstance(station, GroundStation):
            raise TypeError("station must be a GroundStation")
        query_time = _validate_query_time(t_s)
        frame_name = _earth_centered_frame_name(snapshot, "Station metrics")
        if frame_name is None:
            return None
        state = self.earth_fixed_state_at(snapshot, query_time)
        if (
            state.status
            not in (
                CursorStatus.EXACT_SAMPLE,
                CursorStatus.INTERPOLATED,
            )
            or state.state_m is None
        ):
            return None
        metrics = cast(
            Callable[[GroundStation, np.ndarray], StationMetrics],
            public_store.station_metrics_from_ecef,
        )
        return metrics(station, state.state_m[:3])

    def footprints(
        self,
        snapshot: StoreSnapshot,
        t_s: float,
        min_elevation_deg: float,
    ) -> GroundFootprints | None:
        """Return current-time footprint boundaries, or ``None`` without a state."""
        return query_footprints(
            self,
            snapshot,
            t_s,
            min_elevation_deg,
        )

    def series(
        self,
        snapshot: StoreSnapshot,
        bounds_s: TimeBounds,
        groups: Sequence[SeriesGroupName] | None = None,
        max_samples: int | None = None,
        *,
        wait: bool = False,
        _cancel_event: Event | None = None,
    ) -> StoreQuery[SeriesGroups]:
        """Return available group slices and queue missing chunks unless ``wait``."""
        return query_series(
            self,
            snapshot,
            bounds_s,
            groups,
            max_samples,
            wait=wait,
            cancel_event=_cancel_event,
        )

    def earth_fixed_positions(
        self,
        snapshot: StoreSnapshot,
        bounds_s: TimeBounds,
        margin_s: float = 0.0,
        *,
        wait: bool = False,
        _cancel_event: Event | None = None,
    ) -> StoreQuery[EarthFixedPositions]:
        """Return available ITRF slices and queue missing chunks unless ``wait``."""
        return query_earth_fixed(
            self,
            snapshot,
            bounds_s,
            margin_s,
            wait=wait,
            cancel_event=_cancel_event,
        )

    def ground_track(
        self,
        snapshot: StoreSnapshot,
        bounds_s: TimeBounds,
        margin_s: float = 0.0,
        center_longitude_deg: float = 0.0,
        *,
        wait: bool = False,
        _cancel_event: Event | None = None,
    ) -> StoreQuery[GroundTrackGroups]:
        """Return map-centered, seam-split coordinates for the requested range."""
        return query_ground_track(
            self,
            snapshot,
            bounds_s,
            margin_s,
            center_longitude_deg,
            wait=wait,
            cancel_event=_cancel_event,
        )

    def station_access(
        self,
        snapshot: StoreSnapshot,
        station: GroundStation,
        bounds_s: TimeBounds,
        minimum_elevation_deg: float | None = None,
        *,
        wait: bool = False,
        _cancel_event: Event | None = None,
    ) -> StoreQuery[StationAccessView]:
        """Return station profiles and access intervals."""
        return query_station_access(
            self,
            snapshot,
            station,
            bounds_s,
            minimum_elevation_deg,
            wait=wait,
            cancel_event=_cancel_event,
        )

    def _station_profile_storage(
        self, snapshot: StoreSnapshot, station: GroundStation
    ) -> tuple[_StationProfileTier, str | None]:
        return profile_storage(self, snapshot, station)

    def _compute_station_profile_ranges(
        self,
        snapshot: StoreSnapshot,
        station: GroundStation,
        tier: _StationProfileTier,
        ranges: Sequence[tuple[_StationSegmentLayout, int, int]],
        *,
        cancel_event: Event | None,
    ) -> None:
        compute_profile_ranges(
            self,
            snapshot,
            station,
            tier,
            ranges,
            cancel_event=cancel_event,
        )

    def _validate_snapshot_epoch(self, snapshot: StoreSnapshot) -> None:
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")

    def series_chunk_counters(self, group: SeriesGroupName) -> ChunkMemoCounters:
        """Return observable memo counters for one derived series group."""
        if group not in SERIES_GROUPS:
            raise ValueError(f"unsupported series group: {group!r}")
        with self._lock:
            memo = self._series_memos.get(group)
        return ChunkMemoCounters(0, 0, 0, 0) if memo is None else memo.counters

    @property
    def earth_fixed_chunk_counters(self) -> ChunkMemoCounters:
        """Return observable memo counters for the Earth-fixed tier."""
        return self._earth_fixed_memo.counters

    def _series_storage(
        self, snapshot: StoreSnapshot, group: SeriesGroupName
    ) -> tuple[np.ndarray, ChunkMemo[int, RowSpan], np.ndarray]:
        return series_storage(self, snapshot, group)

    def _touch_chunks_locked(
        self,
        buffer: np.ndarray,
        first_row: int,
        stop_row: int,
        bounds: TimeBounds | None = None,
    ) -> None:
        self._derived_buffer_manager.touch_chunks_locked(
            buffer,
            first_row,
            stop_row,
            bounds,
        )

    def _pin_chunks(self, chunk_keys: tuple[tuple[int, int], ...]) -> None:
        self._derived_buffer_manager.pin_chunks(chunk_keys)

    @staticmethod
    def _release_chunks(
        store_ref: weakref.ReferenceType[OemDataStore],
        chunk_keys: tuple[tuple[int, int], ...],
    ) -> None:
        DerivedBufferManager.release_chunks(store_ref, chunk_keys)

    def _make_column_group_view(
        self,
        values: np.ndarray,
        columns: tuple[str, ...],
        segment_bounds: tuple[RowSpan, ...],
        owner_buffer: np.ndarray,
        first_row: int,
        stop_row: int,
    ) -> ColumnGroupView:
        return self._derived_buffer_manager.make_column_group_view(
            values,
            columns,
            segment_bounds,
            owner_buffer,
            first_row,
            stop_row,
        )

    def _evict_derived_buffers(self) -> None:
        self._derived_buffer_manager.evict_derived_buffers()

    def _earth_fixed_storage(
        self, snapshot: StoreSnapshot
    ) -> tuple[np.ndarray, ChunkMemo[int, RowSpan], np.ndarray]:
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if self._raw is None:
                raise RuntimeError("store has no active epoch")
            if self._earth_fixed_buffer is None:
                self._earth_fixed_buffer = _mapped_float_array(
                    (len(self._raw), len(EARTH_FIXED_COLUMNS))
                )
                self._earth_fixed_ready = np.zeros(len(self._raw), dtype=bool)
            assert self._earth_fixed_ready is not None
            return (
                self._earth_fixed_buffer,
                self._earth_fixed_memo,
                self._earth_fixed_ready,
            )

    def _compute_series_range(
        self,
        snapshot: StoreSnapshot,
        group: SeriesGroupName,
        start: int,
        stop: int,
        buffer: np.ndarray,
        memo: ChunkMemo[int, RowSpan],
        ready: np.ndarray,
        *,
        cancel_event: Event | None = None,
        on_chunk: Callable[[RowSpan], None] | None = None,
    ) -> None:
        with self._derived_compute_lock:
            compute_missing_chunk_ranges(
                snapshot,
                ready,
                start,
                stop,
                memo,
                public_store.DERIVED_CHUNK_SIZE,
                lambda span: cast(
                    Callable[
                        [StoreSnapshot, SeriesGroupName, int, int, np.ndarray], None
                    ],
                    public_store._write_series_chunk,
                )(
                    snapshot,
                    group,
                    span.first,
                    span.stop,
                    buffer,
                ),
                cancel_event=cancel_event,
                on_chunk=on_chunk,
            )

    def _compute_earth_fixed_range(
        self,
        snapshot: StoreSnapshot,
        start: int,
        stop: int,
        buffer: np.ndarray,
        memo: ChunkMemo[int, RowSpan],
        ready: np.ndarray,
        *,
        cancel_event: Event | None = None,
        on_chunk: Callable[[RowSpan], None] | None = None,
    ) -> None:
        with self._derived_compute_lock:
            compute_missing_chunk_ranges(
                snapshot,
                ready,
                start,
                stop,
                memo,
                public_store.DERIVED_CHUNK_SIZE,
                lambda span: cast(
                    Callable[[StoreSnapshot, int, int, np.ndarray], None],
                    public_store._write_earth_fixed_chunk,
                )(
                    snapshot,
                    span.first,
                    span.stop,
                    buffer,
                ),
                cancel_event=cancel_event,
                on_chunk=on_chunk,
            )
