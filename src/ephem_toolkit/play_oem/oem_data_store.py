"""Store-owned raw OEM storage with atomic prefix publication."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from collections import OrderedDict
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from enum import Enum
import heapq
from itertools import tee
import logging
import math
import mmap
import weakref
from pathlib import Path
from threading import Event, RLock
from types import MappingProxyType
from typing import Generic, Literal, TypeVar, Union, cast

import numpy as np

from ephem_toolkit.core import wgs
from ephem_toolkit.core.ccsds.odm import ODM_MAX_LINE_LENGTH
from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.core.interpolator.interpolator import Interpolator
from .chunk_memo import ChunkMemo, ChunkMemoCounters, ChunkState
from .clock import SampleTimes
from .ground_footprints import GroundFootprints, compute_ground_footprints
from .cursor import CursorState, CursorStatus
from .ground_stations import (
    GroundStation,
    StationMetrics,
    station_metrics,
)
from .ground_track import (
    EARTH_CENTERS,
    GroundTrackCoordinates,
    GroundTrackPreparationError,
    _ecef_to_wgs84_geodetic,
    _state_position_to_itrf_m_normalized,
    normalize_conversion_frame_name,
    split_ground_track_runs,
    state_position_to_itrf_m,
)
from .series import (
    DIRECTION_RATE_COLUMNS,
    DISTANCE_DELTA_COLUMNS,
    KINEMATICS_COLUMNS,
    RTN_COLUMNS,
    SERIES_GROUPS,
    OrbitSeries,
    SeriesGroupName,
    _SERIES_COLUMNS,
    compute_series_chunk,
)
from .station_access import (
    ACCESS_WINDOW_MARGIN_FRACTION,
    ACCESS_WINDOW_MIN_MARGIN_S,
    CROSSING_TIME_TOLERANCE_S,
    MAX_ACCESS_SAMPLE_STEP_S,
    MAX_ACCESS_SAMPLES,
    MAX_SOURCE_SAMPLE_GAP_S,
    AccessInterval,
    _intervals_for_segment,
    _refine_peak,
)
from .time_unit import TimeUnit

T = TypeVar("T")
TimeBounds = tuple[float, float]
DERIVED_CHUNK_SIZE = 4096
EARTH_FIXED_COLUMNS = ("t", "x_itrf", "y_itrf", "z_itrf")
GROUND_TRACK_COLUMNS = ("t", "longitude", "latitude")
STATION_PROFILE_COLUMNS = ("t", "azimuth_deg", "elevation_deg", "range_km")
TierName = Literal[
    "series", "earth-fixed", "ground-track", "station-access", "footprints"
]
_LOGGER = logging.getLogger(__name__)


class LoadStatus(str, Enum):
    """Lifecycle state for the raw tier in the current epoch."""

    EMPTY = "empty"
    LOADING = "loading"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class OemMetadata:
    """Immutable metadata values validated at OEM load completion."""

    header: tuple[tuple[str, object], ...] = ()
    meta: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class InterpolationPolicy:
    """Interpolation method and optional degree for point-state queries."""

    method: str = "linear"
    degree: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.method, str):
            raise ValueError("interpolation method must be a string")
        object.__setattr__(self, "method", self.method.strip().lower() or "linear")
        if self.degree is not None and (
            isinstance(self.degree, bool)
            or not isinstance(self.degree, int)
            or self.degree < 0
        ):
            raise ValueError("interpolation degree must be a non-negative integer")


def _freeze_metadata(
    fields: tuple[tuple[str, object], ...],
) -> tuple[tuple[str, object], ...]:
    return tuple(
        (key, tuple(value) if isinstance(value, list) else value)
        for key, value in fields
    )


_CAPACITY_SCAN_CHUNK_SIZE = 1024 * 1024
def _capacity_for_file(
    source: Path, cancel_event: Event | None
) -> int:
    line_count = 0
    in_covariance = False
    pending = ""

    with source.open("r", encoding="utf-8", newline=None) as stream:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("capacity scan cancelled")
        while chunk := stream.read(_CAPACITY_SCAN_CHUNK_SIZE):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("capacity scan cancelled")
            combined = pending + chunk
            lines = combined.split("\n")
            pending = lines.pop()
            if lines and max(map(len, lines)) > ODM_MAX_LINE_LENGTH:
                raise ValueError(
                    f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
                )
            complete_end = len(combined) - len(pending)
            position = 0
            search_position = 0
            while search_position < complete_end:
                start_index = combined.find(
                    "COVARIANCE_START", search_position, complete_end
                )
                stop_index = combined.find(
                    "COVARIANCE_STOP", search_position, complete_end
                )
                if start_index < 0:
                    marker_index, marker = stop_index, "COVARIANCE_STOP"
                elif stop_index < 0 or start_index < stop_index:
                    marker_index, marker = start_index, "COVARIANCE_START"
                else:
                    marker_index, marker = stop_index, "COVARIANCE_STOP"
                if marker_index < 0:
                    break
                line_start = combined.rfind("\n", 0, marker_index) + 1
                line_end = combined.find("\n", marker_index, complete_end)
                if combined[line_start:line_end].strip() == marker:
                    if not in_covariance:
                        line_count += combined.count("\n", position, line_start)
                    in_covariance = marker == "COVARIANCE_START"
                    position = line_end + 1
                    search_position = position
                else:
                    search_position = marker_index + len(marker)
            if not in_covariance:
                line_count += combined.count("\n", position, complete_end)
            if len(pending) > ODM_MAX_LINE_LENGTH:
                raise ValueError(
                    f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
                )
    if pending:
        if len(pending) > ODM_MAX_LINE_LENGTH:
            raise ValueError(
                f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
            )
        if pending.strip() == "COVARIANCE_START":
            in_covariance = True
        elif pending.strip() == "COVARIANCE_STOP":
            in_covariance = False
        elif not in_covariance:
            line_count += 1
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("capacity scan cancelled")
    return max(line_count, 1)


@dataclass(frozen=True)
class TimeCoverage:
    """Requested bounds and covered spans; None means no effective query range."""

    requested_s: TimeBounds | None
    covered_s: tuple[TimeBounds, ...]
    complete: bool


@dataclass(frozen=True)
class StoreQuery(Generic[T]):
    """A query result stamped with the store and policy revision it used."""

    epoch: int
    revision: int
    policy_revision: int
    value: T
    coverage: TimeCoverage


@dataclass(frozen=True)
class RowSpan:
    """Half-open row-index span in one tier."""

    first: int
    stop: int


@dataclass(frozen=True)
class _EvictionCandidate:
    access_order: int
    buffer_id: int
    kind: Literal["series", "earth-fixed", "station-access"]
    chunk_index: int
    buffer: np.ndarray
    memo: ChunkMemo[int, RowSpan]
    ready: np.ndarray
    row_count: int
    columns: int
    size_bytes: int


@dataclass(frozen=True)
class QueryRequest:
    """Request for a lazy derived-tier range."""

    tier: TierName
    bounds_s: TimeBounds
    station: GroundStation | None = None
    series_groups: tuple[SeriesGroupName, ...] = ()
    max_samples: int | None = None
    minimum_elevation_deg: float | None = None
    margin_s: float = 0.0
    center_longitude_deg: float = 0.0


def _expanded_request_bounds(request: QueryRequest) -> TimeBounds:
    bounds = _validate_time_bounds(request.bounds_s)
    if request.tier in ("earth-fixed", "ground-track"):
        margin = _validate_nonnegative_finite(request.margin_s, "margin_s")
    elif request.tier == "station-access":
        margin = max(
            ACCESS_WINDOW_MIN_MARGIN_S,
            ACCESS_WINDOW_MARGIN_FRACTION * (bounds[1] - bounds[0]),
        )
    else:
        return bounds
    return bounds[0] - margin, bounds[1] + margin


@dataclass(frozen=True)
class RangeHint:
    """Current plot and playback interest used to prioritize derived work."""

    plot: TimeBounds | None
    playback: TimeBounds
    now_s: float
    dragging: bool = False

    def __post_init__(self) -> None:
        if self.plot is not None:
            object.__setattr__(self, "plot", _validate_time_bounds(self.plot))
        object.__setattr__(self, "playback", _validate_time_bounds(self.playback))
        object.__setattr__(self, "now_s", _validate_query_time(self.now_s))
        if not isinstance(self.dragging, bool):
            raise ValueError("dragging must be a boolean")


class _PrefetchFuture(Future[None]):
    def __init__(self) -> None:
        super().__init__()
        self.cancel_event = Event()

    def cancel(self) -> bool:
        self.cancel_event.set()
        return super().cancel()


@dataclass(order=True)
class _ScheduledWork:
    priority: int
    sequence: int
    key: tuple[int, int, int, QueryRequest] = field(compare=False)
    snapshot: StoreSnapshot = field(compare=False)
    request: QueryRequest = field(compare=False)
    future: _PrefetchFuture = field(compare=False)
    generation: int = field(compare=False)


@dataclass(frozen=True)
class _StationSegmentLayout:
    segment_id: int
    raw_start: int
    raw_stop: int
    start_s: float
    end_s: float
    regular_count: int
    row_count: int
    base_index: int


@dataclass
class _StationProfileTier:
    station_key: tuple[str, float, float, float]
    buffer: np.ndarray
    memo: ChunkMemo[int, RowSpan]
    layouts: tuple[_StationSegmentLayout, ...] = ()
    row_count: int = 0
    ready: np.ndarray | None = None


class _StoreStationCursor:
    def __init__(
        self,
        store: OemDataStore,
        snapshot: StoreSnapshot,
        policy: InterpolationPolicy,
    ) -> None:
        self.store = store
        self.snapshot = snapshot
        self._interpolation = policy.method
        self._interpolation_degree = policy.degree

    def lookup(self, t_s: float) -> CursorState:
        return self.store.state_at(self.snapshot, t_s)


class _ChunkLease:
    def __init__(
        self,
        store: OemDataStore,
        chunk_keys: tuple[tuple[int, int], ...],
    ) -> None:
        self.chunk_keys = chunk_keys
        store._pin_chunks(chunk_keys)
        weakref.finalize(
            self,
            OemDataStore._release_chunks,
            weakref.ref(store),
            chunk_keys,
        )


class _LeasedArray(np.ndarray):
    def __array_finalize__(self, source: object) -> None:
        self._chunk_lease = (
            getattr(source, "_chunk_lease", None)
            if isinstance(source, np.ndarray) and np.may_share_memory(self, source)
            else None
        )


@dataclass(frozen=True, eq=False)
class ColumnGroupView:
    """Read-only view of a store-owned derived column group."""

    values: np.ndarray
    columns: tuple[str, ...]
    segment_bounds: tuple[RowSpan, ...]
    lease: _ChunkLease | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.values.ndim != 2 or self.values.shape[1] != len(self.columns):
            raise ValueError("column-group shape must match its column names")
        lease = self.lease or getattr(self.values, "_chunk_lease", None)
        view = np.asarray(memoryview(self.values).toreadonly()).view(_LeasedArray)
        view._chunk_lease = lease
        object.__setattr__(self, "values", view)
        object.__setattr__(self, "lease", lease)

    def pair(
        self,
        first: str,
        second: str,
        rows: slice = slice(None),
    ) -> np.ndarray:
        """Return a read-only two-column view without gathering or copying."""
        try:
            first_index = self.columns.index(first)
            second_index = self.columns.index(second)
        except ValueError as error:
            raise ValueError("pair columns must exist in this column group") from error
        if first_index == second_index:
            raise ValueError("pair columns must be distinct")

        lower_index = min(first_index, second_index)
        upper_index = max(first_index, second_index)
        step = upper_index - lower_index
        pair = self.values[rows, lower_index : upper_index + 1 : step]
        if first_index > second_index:
            pair = pair[:, ::-1]
        return pair


SeriesGroups = Mapping[SeriesGroupName, tuple[ColumnGroupView, ...]]
GroundTrackGroups = tuple[ColumnGroupView, ...]
EarthFixedPositions = tuple[ColumnGroupView, ...]


@dataclass(frozen=True)
class LookAngleProfileView:
    """Station look-angle columns shared by profile and pass views."""

    group: ColumnGroupView


@dataclass(frozen=True)
class StationAccessView:
    """Window-specific station intervals backed by shared profile views."""

    station: GroundStation
    profiles: tuple[LookAngleProfileView, ...]
    intervals: tuple[AccessInterval, ...]
    limitation: str | None


@dataclass(frozen=True)
class TierNotice:
    """Completed row range in a derived tier."""

    epoch: int
    tier: TierName
    group: SeriesGroupName | None
    station_id: str | None
    first_row: int
    stop_row: int


@dataclass(frozen=True)
class AppendNotice:
    """Newly committed raw rows in one store epoch."""

    epoch: int
    revision: int
    first_new_index: int
    sample_count: int
    time_span_s: TimeBounds

    @property
    def start_s(self) -> float:
        return self.time_span_s[0]

    @property
    def end_s(self) -> float:
        return self.time_span_s[1]


@dataclass(frozen=True)
class ResetNotice:
    """Invalidation of the previously active store epoch."""

    epoch: int


StoreNotice = Union[AppendNotice, ResetNotice, TierNotice]


@dataclass(frozen=True)
class StoreSnapshot:
    """Immutable views of one committed raw prefix and its store revisions."""

    epoch: int
    revision: int
    policy_revision: int
    sample_count: int
    metadata: OemMetadata
    time_unit: TimeUnit
    raw: np.ndarray
    segment_ids: np.ndarray
    segment_bounds: np.ndarray
    max_within_segment_gap_s: float
    status: LoadStatus
    failure: str | None

    @property
    def header(self) -> tuple[tuple[str, object], ...]:
        return self.metadata.header

    @property
    def meta(self) -> tuple[tuple[str, object], ...]:
        return self.metadata.meta

    @property
    def positions_m(self) -> np.ndarray:
        """Read-only raw-backed position columns in meters."""
        return np.asarray(memoryview(self.raw[:, 1:4]).toreadonly())

    @property
    def velocities_m_s(self) -> np.ndarray:
        """Read-only raw-backed velocity columns in meters per second."""
        return np.asarray(memoryview(self.raw[:, 4:7]).toreadonly())


RawSnapshot = StoreSnapshot


@dataclass(frozen=True)
class RawAppendNotice(AppendNotice):
    """Compatibility name for append notices emitted by raw ingestion."""


class RawReservation:
    """Exclusive unpublished suffix; the writer must relinquish views after use."""

    def __init__(
        self, epoch: int, first_index: int, raw: np.ndarray, segment_ids: np.ndarray
    ) -> None:
        self.epoch = epoch
        self.first_index = first_index
        self.raw = raw
        self.segment_ids = segment_ids

    def _close(self) -> None:
        self.raw.setflags(write=False)
        self.segment_ids.setflags(write=False)


class OemDataStore:
    """Fixed-capacity raw and lazily materialized derived storage.

    A single writer fills a reservation and must not mutate it during commit or
    retain writable aliases after commit or abort. Snapshots expose only committed
    rows; derived query buffers are allocated on first request and remain tied to
    the current epoch.
    """

    def __init__(
        self, derived_memory_budget_bytes: int = 256 * 1024 * 1024
    ) -> None:
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
        self._ground_track_cache: OrderedDict[
            tuple[object, ...], StoreQuery[GroundTrackGroups]
        ] = OrderedDict()
        self._station_profiles: dict[tuple[object, ...], _StationProfileTier] = {}
        self._station_interval_cache: dict[
            tuple[object, ...], tuple[AccessInterval, ...]
        ] = {}
        self._footprint_cache: OrderedDict[
            tuple[object, ...], GroundFootprints
        ] = OrderedDict()
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
        if tier not in ("series", "earth-fixed", "ground-track", "station-access", "footprints"):
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

    def prefetch(
        self, snapshot: StoreSnapshot, request: QueryRequest
    ) -> Future[None]:
        """Queue a prioritized, cancellable range request."""
        if not isinstance(request, QueryRequest):
            raise TypeError("request must be a QueryRequest")
        bounds = _validate_time_bounds(request.bounds_s)
        if request.tier == "series":
            groups = tuple(dict.fromkeys(request.series_groups))
            unknown_groups = set(groups).difference(SERIES_GROUPS)
            if unknown_groups:
                raise ValueError(f"unsupported series groups: {sorted(unknown_groups)}")
            if request.max_samples is not None and (
                isinstance(request.max_samples, bool)
                or not isinstance(request.max_samples, int)
                or request.max_samples < 1
            ):
                raise ValueError("max_samples must be a positive integer")
            request = QueryRequest(
                request.tier,
                bounds,
                request.station,
                groups,
                request.max_samples,
                request.minimum_elevation_deg,
                request.margin_s,
            )
        elif request.tier == "earth-fixed":
            margin = _validate_nonnegative_finite(request.margin_s, "margin_s")
            request = QueryRequest(
                request.tier,
                bounds,
                request.station,
                request.series_groups,
                request.max_samples,
                request.minimum_elevation_deg,
                margin,
            )
        elif request.tier == "station-access":
            if not isinstance(request.station, GroundStation):
                raise ValueError("station-access requests require a GroundStation")
            minimum_elevation = request.minimum_elevation_deg
            if minimum_elevation is None:
                minimum_elevation = float(request.station.minimum_elevation_deg)
            request = QueryRequest(
                request.tier,
                bounds,
                request.station,
                request.series_groups,
                request.max_samples,
                _validate_elevation_threshold(minimum_elevation),
                request.margin_s,
            )
        elif request.tier == "ground-track":
            margin = _validate_nonnegative_finite(request.margin_s, "margin_s")
            center = _normalize_longitude(request.center_longitude_deg)
            request = QueryRequest(
                request.tier,
                bounds,
                margin_s=margin,
                center_longitude_deg=center,
            )
        else:
            raise ValueError(f"prefetch does not support tier: {request.tier!r}")
        self._validate_snapshot_epoch(snapshot)
        policy_revision = (
            snapshot.policy_revision if request.tier == "station-access" else 0
        )
        key = (snapshot.epoch, snapshot.revision, policy_revision, request)
        with self._scheduler_lock:
            if self._scheduler_closed:
                raise RuntimeError("store scheduler is closed")
            existing = self._scheduled_work.get(key)
            if existing is not None:
                return existing.future
            future = _PrefetchFuture()
            self._task_sequence += 1
            work = _ScheduledWork(
                self._priority_for_request(request, self._range_hint),
                self._task_sequence,
                key,
                snapshot,
                request,
                future,
                self._range_generation,
            )
            self._scheduled_work[key] = work
            heapq.heappush(self._work_queue, work)
            self._start_scheduler_drain_locked()
            return future

    def close(self) -> None:
        """Cancel pending range work and stop the background worker."""
        with self._scheduler_lock:
            if self._scheduler_closed:
                return
            self._scheduler_closed = True
        self._cancel_scheduled_work()
        self._scheduler_executor.shutdown(wait=True, cancel_futures=True)

    def _priority_for_request(
        self, request: QueryRequest, hint: RangeHint | None
    ) -> int:
        if hint is None:
            return 4
        if self._tier_interest.get(request.tier, 0) == 0:
            return 4
        bounds = _expanded_request_bounds(request)
        if hint.plot is not None:
            plot = hint.plot
            width = max(plot[1] - plot[0], 1.0)
            if _ranges_intersect(bounds, plot):
                return 1
            expanded = (plot[0] - width, plot[1] + width)
            if _ranges_intersect(bounds, expanded) or (
                abs((bounds[0] + bounds[1]) / 2.0 - hint.now_s) <= width
            ):
                return 2
        if _ranges_intersect(bounds, hint.playback):
            return 3
        return 4

    def _reprioritize_queued_work_locked(self) -> None:
        for work in self._work_queue:
            work.priority = self._priority_for_request(work.request, self._range_hint)
            work.generation = self._range_generation
        heapq.heapify(self._work_queue)
        if self._active_work is not None:
            self._active_work.priority = self._priority_for_request(
                self._active_work.request, self._range_hint
            )
        self._start_scheduler_drain_locked()

    def _start_scheduler_drain_locked(self) -> None:
        if self._scheduler_closed or self._scheduler_drain_active or not self._work_queue:
            return
        self._scheduler_drain_active = True
        try:
            self._scheduler_executor.submit(self._drain_scheduler_queue)
        except RuntimeError:
            self._scheduler_drain_active = False
            raise

    def _drain_scheduler_queue(self) -> None:
        while True:
            with self._scheduler_lock:
                if self._scheduler_closed or not self._work_queue:
                    self._scheduler_drain_active = False
                    return
                eligible = [
                    work
                    for work in self._work_queue
                    if not work.future.cancelled()
                    and (
                        self._range_hint is None
                        or not self._range_hint.dragging
                        or (
                            work.priority == 1
                            and self._request_rows(work) <= DERIVED_CHUNK_SIZE
                        )
                    )
                ]
                if not eligible:
                    self._scheduler_drain_active = False
                    return
                work = min(eligible)
                self._work_queue.remove(work)
                heapq.heapify(self._work_queue)
                self._active_work = work
            if not work.future.set_running_or_notify_cancel():
                self._finish_scheduled_work(work)
                continue
            try:
                self._run_prefetch(work)
            except CancelledError as error:
                if not work.future.done():
                    work.future.set_exception(error)
            except Exception as error:
                if not work.future.done():
                    work.future.set_exception(error)
            else:
                if not work.future.done():
                    work.future.set_result(None)
            finally:
                self._finish_scheduled_work(work)

    @staticmethod
    def _request_rows(work: _ScheduledWork) -> int:
        snapshot = work.snapshot
        bounds = _expanded_request_bounds(work.request)
        if work.request.tier == "station-access":
            requested_rows = 0
            for raw_start_value, raw_stop_value in snapshot.segment_bounds:
                raw_start, raw_stop = int(raw_start_value), int(raw_stop_value)
                if raw_stop - raw_start < 2:
                    continue
                start_s = float(snapshot.raw[raw_start, 0])
                end_s = float(snapshot.raw[raw_stop - 1, 0])
                count = max(
                    2,
                    math.ceil((end_s - start_s) / MAX_ACCESS_SAMPLE_STEP_S) + 1,
                )
                layout = _StationSegmentLayout(
                    int(snapshot.segment_ids[raw_start]),
                    raw_start,
                    raw_stop,
                    start_s,
                    end_s,
                    count,
                    count,
                    0,
                )
                first, stop = _station_profile_row_range(layout, bounds)
                requested_rows += max(0, stop - first)
            return requested_rows
        start = int(np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left"))
        stop = int(np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right"))
        return stop - start

    def _run_prefetch(self, work: _ScheduledWork) -> None:
        if work.future.cancel_event.is_set():
            raise CancelledError()
        request = work.request
        if request.tier == "series":
            self.series(
                work.snapshot,
                request.bounds_s,
                groups=request.series_groups or None,
                max_samples=request.max_samples,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        elif request.tier == "earth-fixed":
            self.earth_fixed_positions(
                work.snapshot,
                request.bounds_s,
                request.margin_s,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        elif request.tier == "station-access":
            if request.station is None:
                raise ValueError("station-access requests require a GroundStation")
            self.station_access(
                work.snapshot,
                request.station,
                request.bounds_s,
                minimum_elevation_deg=request.minimum_elevation_deg,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        elif request.tier == "ground-track":
            self.ground_track(
                work.snapshot,
                request.bounds_s,
                margin_s=request.margin_s,
                center_longitude_deg=request.center_longitude_deg,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        else:
            raise ValueError(f"prefetch does not support tier: {request.tier!r}")

    def _finish_scheduled_work(self, work: _ScheduledWork) -> None:
        with self._scheduler_lock:
            if self._scheduled_work.get(work.key) is work:
                self._scheduled_work.pop(work.key, None)
            if self._active_work is work:
                self._active_work = None

    def _cancel_scheduled_work(self) -> None:
        with self._scheduler_lock:
            for work in tuple(self._scheduled_work.values()):
                work.future.cancel()
            self._work_queue.clear()
            self._scheduled_work = {
                key: work
                for key, work in self._scheduled_work.items()
                if work is self._active_work
            }

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
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        raw = np.empty((capacity, 7), dtype=np.float64)
        segment_ids = np.empty(capacity, dtype=np.int64)
        with self._lock:
            self._reset_locked()
            self._raw = raw
            self._segment_ids = segment_ids
            timestamp_view = raw[:, 0].view()
            timestamp_view.setflags(write=False)
            self._sample_times = SampleTimes(timestamp_view, 0)
            self._status = LoadStatus.LOADING
            return self._epoch

    def begin_loading(self) -> int:
        """Start a loading epoch before its fixed capacity is known."""
        with self._lock:
            self._reset_locked()
            self._status = LoadStatus.LOADING
            return self._epoch

    def allocate_if_epoch(self, epoch: int, capacity: int) -> bool:
        """Allocate fixed buffers if ``epoch`` remains the active loading epoch."""
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        with self._lock:
            if (
                epoch != self._epoch
                or self._status is not LoadStatus.LOADING
                or self._raw is not None
            ):
                return False
        raw = np.empty((capacity, 7), dtype=np.float64)
        segment_ids = np.empty(capacity, dtype=np.int64)
        with self._lock:
            if (
                epoch != self._epoch
                or self._status is not LoadStatus.LOADING
                or self._raw is not None
            ):
                return False
            self._raw = raw
            self._segment_ids = segment_ids
            timestamp_view = raw[:, 0].view()
            timestamp_view.setflags(write=False)
            self._sample_times = SampleTimes(timestamp_view, 0)
            return True

    def clear(self) -> None:
        """Invalidate the active epoch; existing snapshots retain their buffers."""
        with self._lock:
            self._reset_locked()

    def clear_if_epoch(self, epoch: int) -> bool:
        """Invalidate ``epoch`` only if it is still current."""
        with self._lock:
            if epoch != self._epoch:
                return False
            self._reset_locked()
            return True

    def cancel_if_epoch(self, epoch: int) -> bool:
        """Stop the active producer while preserving its committed prefix."""
        with self._lock:
            if epoch != self._epoch or self._status is not LoadStatus.LOADING:
                return False
            if self._reservation is not None:
                self._reservation._close()
                self._reservation = None
            self._validating = False
            self._status = LoadStatus.CANCELLED
            self._failure = None
            self._revision += 1
            return True

    def mark_complete(
        self,
        epoch: int,
        header: tuple[tuple[str, object], ...],
        meta: tuple[tuple[str, object], ...],
    ) -> None:
        """Publish EOF-validated metadata and mark the active epoch complete."""
        with self._lock:
            if epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if self._status is not LoadStatus.LOADING:
                raise RuntimeError("store is not loading")
            if self._reservation is not None:
                raise RuntimeError("cannot complete with an active reservation")
            self._header = _freeze_metadata(header)
            self._meta = _freeze_metadata(meta)
            self._failure = None
            self._status = LoadStatus.COMPLETE
            self._revision += 1

    def mark_failed(self, epoch: int, failure: Exception) -> bool:
        """Mark the current load failed and discard its unpublished suffix."""
        with self._lock:
            if epoch != self._epoch or self._status is not LoadStatus.LOADING:
                return False
            if self._reservation is not None:
                self._reservation._close()
                self._reservation = None
            self._validating = False
            self._status = LoadStatus.FAILED
            self._failure = str(failure)
            self._revision += 1
            return True

    def _reset_locked(self) -> None:
        self._cancel_scheduled_work()
        if self._reservation is not None:
            self._reservation._close()
        for memo in self._series_memos.values():
            memo.clear()
        self._earth_fixed_memo.clear()
        self._series_buffers.clear()
        self._series_ready.clear()
        self._earth_fixed_buffer = None
        self._earth_fixed_ready = None
        self._ground_track_cache.clear()
        self._clear_station_tiers_locked()
        self._footprint_cache.clear()
        self._chunk_access_order.clear()
        self._chunk_ranges.clear()
        self._epoch += 1
        self._revision = 0
        self._policy_revision = 0
        self._sample_count = 0
        self._raw = None
        self._segment_ids = None
        self._sample_times = None
        self._segment_bounds = []
        self._max_gap_s = 0.0
        self._status = LoadStatus.EMPTY
        self._header = ()
        self._meta = ()
        self._failure = None
        self._reservation = None
        self._validating = False

    def _clear_station_tiers_locked(self) -> None:
        for tier in self._station_profiles.values():
            tier.memo.clear()
            buffer_id = _mapped_buffer_id(tier.buffer)
            for key in tuple(self._chunk_access_order):
                if key[0] == buffer_id:
                    self._chunk_access_order.pop(key, None)
                    self._chunk_ranges.pop(key, None)
        self._station_profiles.clear()
        self._station_interval_cache.clear()

    def reserve(self, max_rows: int, *, epoch: int | None = None) -> RawReservation:
        """Reserve up to ``max_rows`` in the unpublished suffix."""
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
            raise ValueError("max_rows must be a positive integer")
        with self._lock:
            if epoch is not None and epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if self._raw is None or self._segment_ids is None:
                raise RuntimeError("store has no active epoch")
            if self._status is not LoadStatus.LOADING:
                raise RuntimeError(f"store is not loading: {self._status.value}")
            if self._reservation is not None:
                raise RuntimeError("a raw reservation is already active")
            stop = min(self._sample_count + max_rows, len(self._raw))
            if stop == self._sample_count:
                raise OverflowError("raw storage capacity exceeded")
            reservation = RawReservation(
                self._epoch,
                self._sample_count,
                self._raw[self._sample_count : stop],
                self._segment_ids[self._sample_count : stop],
            )
            self._reservation = reservation
            return reservation

    def abort(self, reservation: RawReservation) -> None:
        """Discard an unpublished reservation without changing coverage."""
        with self._lock:
            self._check_reservation_locked(reservation)
            if self._validating:
                raise RuntimeError("reservation validation is in progress")
            reservation._close()
            self._reservation = None

    def discard_if_active(self, reservation: RawReservation) -> bool:
        """Release a still-active reservation during producer cleanup."""
        with self._lock:
            if self._reservation is not reservation:
                return False
            if self._validating:
                raise RuntimeError("reservation validation is in progress")
            reservation._close()
            self._reservation = None
            return True

    def _check_reservation_locked(self, reservation: RawReservation) -> None:
        if (
            self._reservation is not reservation
            or reservation.epoch != self._epoch
            or reservation.first_index != self._sample_count
        ):
            raise RuntimeError("reservation is stale or does not belong to this store")

    def commit(self, reservation: RawReservation, count: int) -> RawAppendNotice:
        """Validate and atomically publish a populated reservation prefix."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("count must be a positive integer")
        with self._lock:
            self._check_reservation_locked(reservation)
            if self._validating:
                raise RuntimeError("reservation validation is in progress")
            if count > len(reservation.raw):
                raise ValueError("count exceeds reservation capacity")
            self._validating = True
            previous_time = (
                float(self._raw[self._sample_count - 1, 0])
                if self._sample_count and self._raw is not None
                else None
            )
            previous_segment = (
                int(self._segment_ids[self._sample_count - 1])
                if self._sample_count and self._segment_ids is not None
                else None
            )
        try:
            boundaries: list[tuple[int, int]] = []
            max_gap = 0.0
            for index in range(count):
                row = reservation.raw[index]
                segment = int(reservation.segment_ids[index])
                timestamp = float(row[0])
                if not all(math.isfinite(float(value)) for value in row):
                    raise ValueError("timestamps and states must be finite")
                if previous_time is not None and timestamp <= previous_time:
                    raise ValueError("timestamps must be strictly increasing")
                if previous_segment is not None and segment < previous_segment:
                    raise ValueError("segment IDs must be non-decreasing")
                if segment != previous_segment:
                    boundaries.append((reservation.first_index + index, segment))
                elif previous_time is not None:
                    max_gap = max(max_gap, timestamp - previous_time)
                previous_time = timestamp
                previous_segment = segment
            with self._lock:
                self._check_reservation_locked(reservation)
                if self._sample_times is None:
                    raise RuntimeError("store timestamps are not allocated")
                stop = self._sample_count + count
                for start, segment in boundaries:
                    if self._segment_bounds:
                        old_segment, old_start, _ = self._segment_bounds[-1]
                        self._segment_bounds[-1] = (old_segment, old_start, start)
                    self._segment_bounds.append((segment, start, stop))
                if self._segment_bounds:
                    segment, start, _ = self._segment_bounds[-1]
                    self._segment_bounds[-1] = (segment, start, stop)
                self._max_gap_s = max(self._max_gap_s, max_gap)
                self._sample_count = stop
                self._sample_times._publish_validated_count(stop)
                self._revision += 1
                self._clear_station_tiers_locked()
                self._ground_track_cache.clear()
                notice = RawAppendNotice(
                    self._epoch,
                    self._revision,
                    reservation.first_index,
                    stop,
                    (
                        float(reservation.raw[0, 0]),
                        float(reservation.raw[count - 1, 0]),
                    ),
                )
                reservation._close()
                self._reservation = None
                self._validating = False
                return notice
        finally:
            with self._lock:
                if self._reservation is reservation:
                    self._validating = False

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
            duration_s = (
                float(raw[-1, 0] - raw[0, 0]) if self._sample_count else 0.0
            )
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
        query_time = _validate_query_time(t_s)
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if snapshot.policy_revision != self._policy_revision:
                raise RuntimeError("interpolation policy has changed")
            interpolator = self._state_interpolator
        if snapshot.sample_count == 0:
            return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)

        raw = snapshot.raw
        times = raw[:, 0]
        if query_time < times[0] or query_time > times[-1]:
            return _unavailable_state(query_time, CursorStatus.OUT_OF_RANGE)

        upper_index = int(np.searchsorted(times, query_time))
        if upper_index < times.size and times[upper_index] == query_time:
            state_m = raw[upper_index, 1:7].copy()
            status = CursorStatus.EXACT_SAMPLE
            segment_id = int(snapshot.segment_ids[upper_index])
        else:
            lower_index = upper_index - 1
            segment_id = int(snapshot.segment_ids[lower_index])
            if segment_id != snapshot.segment_ids[upper_index]:
                return _unavailable_state(query_time, CursorStatus.GAP)
            state_m = interpolator.interpolate_view(
                times,
                raw[:, 1:7],
                query_time,
                snapshot.segment_ids,
            )
            if state_m is None:
                return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)
            if state_m.shape != (6,) or not np.all(np.isfinite(state_m)):
                raise ValueError("interpolator returned an invalid Cartesian state")
            state_m = state_m.copy()
            status = CursorStatus.INTERPOLATED

        position_km = state_m[:3] * 0.001
        velocity_km_s = state_m[3:] * 0.001
        return CursorState(
            t=query_time,
            state_m=state_m,
            r_km=position_km,
            v_kms=velocity_km_s,
            speed=float(np.linalg.norm(velocity_km_s)),
            altitude=float(wgs.ecef_to_lla(state_m[:3])[2] * 0.001),
            distance=float(np.linalg.norm(position_km)),
            status=status,
            segment_id=segment_id,
        )

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
        state = self.state_at(snapshot, query_time)
        if state.status not in (
            CursorStatus.EXACT_SAMPLE,
            CursorStatus.INTERPOLATED,
        ) or state.state_m is None:
            return None
        return station_metrics(station, state.state_m, frame_name, query_time)

    def footprints(
        self,
        snapshot: StoreSnapshot,
        t_s: float,
        min_elevation_deg: float,
    ) -> GroundFootprints | None:
        """Return current-time footprint boundaries, or ``None`` without a state."""
        self._validate_snapshot_epoch(snapshot)
        query_time = _validate_query_time(t_s)
        minimum_elevation = _validate_elevation_threshold(min_elevation_deg)
        frame_name = _earth_centered_frame_name(snapshot, "Footprints")
        if frame_name is None:
            return None
        state = self.state_at(snapshot, query_time)
        if state.status not in (
            CursorStatus.EXACT_SAMPLE,
            CursorStatus.INTERPOLATED,
        ) or state.state_m is None:
            return None
        position = state_position_to_itrf_m(state.state_m, frame_name, query_time)
        cache_key = (
            snapshot.epoch,
            query_time,
            tuple(float(value) for value in position),
            minimum_elevation,
        )
        with self._lock:
            cached = self._footprint_cache.get(cache_key)
            if cached is not None:
                self._footprint_cache.move_to_end(cache_key)
                return cached
        result = compute_ground_footprints(position, minimum_elevation)
        with self._lock:
            self._footprint_cache[cache_key] = result
            self._footprint_cache.move_to_end(cache_key)
            while len(self._footprint_cache) > 32:
                self._footprint_cache.popitem(last=False)
        return result

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
        bounds = _validate_time_bounds(bounds_s)
        self._validate_snapshot_epoch(snapshot)
        selected_groups: tuple[SeriesGroupName, ...] = (
            SERIES_GROUPS if groups is None else tuple(dict.fromkeys(groups))
        )
        unknown_groups = set(selected_groups).difference(SERIES_GROUPS)
        if unknown_groups:
            raise ValueError(f"unsupported series groups: {sorted(unknown_groups)}")
        if not isinstance(wait, bool):
            raise ValueError("wait must be a boolean")
        if max_samples is not None and (
            isinstance(max_samples, bool)
            or not isinstance(max_samples, int)
            or max_samples < 1
        ):
            raise ValueError("max_samples must be a positive integer")
        if _cancel_event is not None and _cancel_event.is_set():
            raise CancelledError()
        if snapshot.sample_count == 0:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                MappingProxyType(
                    {
                        group: ()
                        for group in selected_groups
                    }
                ),
                _time_coverage(snapshot, bounds),
            )

        start = int(np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left"))
        stop = int(np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right"))
        if not wait and start < stop and selected_groups:
            self.prefetch(
                snapshot,
                QueryRequest(
                    "series",
                    bounds,
                    series_groups=selected_groups,
                    max_samples=max_samples,
                ),
            )
        result: dict[SeriesGroupName, tuple[ColumnGroupView, ...]] = {}
        ready_by_group: list[tuple[RowSpan, ...]] = []
        for group in selected_groups:
            if _cancel_event is not None and _cancel_event.is_set():
                raise CancelledError()
            if start == stop:
                result[group] = ()
                ready_by_group.append(())
                continue
            if wait:
                buffer, memo, ready = self._series_storage(snapshot, group)
                self._compute_series_range(
                    snapshot,
                    group,
                    start,
                    stop,
                    buffer,
                    memo,
                    ready,
                    cancel_event=_cancel_event,
                    on_chunk=lambda span: self._publish_notice(
                        TierNotice(
                            snapshot.epoch,
                            "series",
                            cast(SeriesGroupName, group),
                            None,
                            span.first,
                            span.stop,
                        )
                    ),
                )
            else:
                with self._lock:
                    buffer = self._series_buffers.get(group)
                    memo = self._series_memos.get(group)
                    ready = self._series_ready.get(group)
            if buffer is None or memo is None or ready is None:
                ready_spans = ()
                group_views = ()
            else:
                stride = 1
                row_count = stop - start
                if max_samples is not None and row_count > max_samples:
                    stride = math.ceil(row_count / max_samples)
                with self._derived_compute_lock, self._lock:
                    self._touch_chunks_locked(buffer, start, stop, bounds)
                    ready_spans = _row_spans(
                        ready, start, stop, ready_value=True
                    )
                    group_views = tuple(
                        self._make_column_group_view(
                            buffer[
                                start
                                + math.ceil((span.first - start) / stride)
                                * stride : span.stop : stride
                            ],
                            _SERIES_COLUMNS[group],
                            _series_segment_spans(
                                snapshot,
                                group,
                                start
                                + math.ceil((span.first - start) / stride)
                                * stride,
                                span.stop,
                                stride,
                                origin=start,
                            ),
                            buffer,
                            span.first,
                            span.stop,
                        )
                        for span in ready_spans
                        if start
                        + math.ceil((span.first - start) / stride) * stride
                        < span.stop
                    )
            ready_by_group.append(ready_spans)
            result[group] = group_views

        base_coverage = _time_coverage(snapshot, bounds)
        if selected_groups:
            common_spans = ready_by_group[0]
            for spans in ready_by_group[1:]:
                common_spans = _intersect_row_spans(common_spans, spans)
            coverage = _coverage_for_rows(
                snapshot,
                bounds,
                common_spans,
                base_coverage.complete
                and sum(span.stop - span.first for span in common_spans)
                == stop - start,
            )
        else:
            coverage = base_coverage
        series_groups: SeriesGroups = MappingProxyType(result)
        query = StoreQuery[SeriesGroups](
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            series_groups,
            coverage,
        )
        self._evict_derived_buffers()
        return query

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
        bounds = _validate_time_bounds(bounds_s)
        self._validate_snapshot_epoch(snapshot)
        if not isinstance(wait, bool):
            raise ValueError("wait must be a boolean")
        if _cancel_event is not None and _cancel_event.is_set():
            raise CancelledError()
        margin = _validate_nonnegative_finite(margin_s, "margin_s")
        frame_name = _earth_centered_frame_name(snapshot, "Earth-fixed positions")
        if frame_name is None:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                (),
                TimeCoverage(bounds, (), False),
            )

        if snapshot.sample_count == 0:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                (),
                _time_coverage(snapshot, bounds),
            )

        expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
        start = int(
            np.searchsorted(snapshot.raw[:, 0], expanded_bounds[0], side="left")
        )
        stop = int(
            np.searchsorted(snapshot.raw[:, 0], expanded_bounds[1], side="right")
        )
        original_start = int(
            np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left")
        )
        original_stop = int(
            np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right")
        )
        if not wait and start < stop:
            self.prefetch(
                snapshot,
                QueryRequest(
                    "earth-fixed",
                    bounds,
                    margin_s=margin,
                ),
            )
        if start == stop:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                (),
                _time_coverage(snapshot, bounds),
            )
        if wait:
            buffer, memo, ready = self._earth_fixed_storage(snapshot)
            self._compute_earth_fixed_range(
                snapshot,
                frame_name,
                start,
                stop,
                buffer,
                memo,
                ready,
                cancel_event=_cancel_event,
                on_chunk=lambda span: self._publish_notice(
                    TierNotice(
                        snapshot.epoch,
                        "earth-fixed",
                        None,
                        None,
                        span.first,
                        span.stop,
                    )
                ),
            )
        else:
            with self._lock:
                buffer = self._earth_fixed_buffer
                memo = self._earth_fixed_memo if buffer is not None else None
                ready = self._earth_fixed_ready
        if buffer is None or memo is None or ready is None:
            ready_spans = ()
            groups = ()
        else:
            with self._derived_compute_lock, self._lock:
                self._touch_chunks_locked(
                    buffer,
                    start,
                    stop,
                    expanded_bounds,
                )
                ready_spans = _row_spans(
                    ready, start, stop, ready_value=True
                )
                groups = tuple(
                    self._make_column_group_view(
                        buffer[span.first : span.stop],
                        EARTH_FIXED_COLUMNS,
                        _point_segment_spans(snapshot, span.first, span.stop),
                        buffer,
                        span.first,
                        span.stop,
                    )
                    for span in ready_spans
                )
        in_bounds_spans = _intersect_row_spans(
            ready_spans,
            (RowSpan(original_start, original_stop),)
            if original_start < original_stop
            else (),
        )
        base_coverage = _time_coverage(snapshot, bounds)
        coverage = _coverage_for_rows(
            snapshot,
            bounds,
            in_bounds_spans,
            base_coverage.complete
            and sum(span.stop - span.first for span in in_bounds_spans)
            == original_stop - original_start,
        )
        query = StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            groups,
            coverage,
        )
        self._evict_derived_buffers()
        return query

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
        bounds = _validate_time_bounds(bounds_s)
        margin = _validate_nonnegative_finite(margin_s, "margin_s")
        center = _normalize_longitude(center_longitude_deg)
        self._validate_snapshot_epoch(snapshot)
        if not isinstance(wait, bool):
            raise ValueError("wait must be a boolean")
        if _cancel_event is not None and _cancel_event.is_set():
            raise CancelledError()

        key = (
            snapshot.epoch,
            snapshot.revision,
            bounds,
            margin,
            center,
        )
        with self._lock:
            cached = self._ground_track_cache.get(key)
            if cached is not None:
                self._ground_track_cache.move_to_end(key)
                if cached.policy_revision == snapshot.policy_revision:
                    return cached
                return StoreQuery(
                    snapshot.epoch,
                    snapshot.revision,
                    snapshot.policy_revision,
                    cached.value,
                    cached.coverage,
                )

        if snapshot.sample_count == 0:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                (),
                _time_coverage(snapshot, bounds),
            )

        frame_name = _earth_centered_frame_name(snapshot, "Ground Track")
        if frame_name is None:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                (),
                TimeCoverage(bounds, (), False),
            )

        if not wait:
            self.prefetch(
                snapshot,
                QueryRequest(
                    "ground-track",
                    bounds,
                    margin_s=margin,
                    center_longitude_deg=center,
                ),
            )
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                (),
                TimeCoverage(bounds, (), False),
            )

        earth_fixed = self.earth_fixed_positions(
            snapshot,
            bounds,
            margin,
            wait=True,
            _cancel_event=_cancel_event,
        )
        groups: list[ColumnGroupView] = []
        for earth_group in earth_fixed.value:
            ecef_values = earth_group.values
            geodetic = _ecef_to_wgs84_geodetic(ecef_values[:, 1:4])
            if not np.isfinite(geodetic).all():
                raise GroundTrackPreparationError(
                    "WGS-84 conversion returned non-finite geodetic coordinates"
                )
            if np.any(geodetic[:, 2] < -1.0e-3):
                raise GroundTrackPreparationError(
                    "OEM contains an Earth-fixed position inside the WGS-84 ellipsoid"
                )
            for segment in earth_group.segment_bounds:
                if segment.first >= segment.stop:
                    continue
                segment_values = ecef_values[segment.first : segment.stop]
                segment_geodetic = geodetic[segment.first : segment.stop]
                coordinates = GroundTrackCoordinates(
                    timestamps_s=segment_values[:, 0],
                    latitude_rad=segment_geodetic[:, 0],
                    longitude_rad=segment_geodetic[:, 1],
                    segment_ids=np.zeros(len(segment_values), dtype=np.int64),
                    source_frame=frame_name,
                )
                for run in split_ground_track_runs(coordinates, center):
                    run_values = np.column_stack(
                        (
                            run.timestamps_s,
                            run.longitude_relative_rad,
                            run.latitude_rad,
                        )
                    )
                    groups.append(
                        ColumnGroupView(
                            run_values,
                            GROUND_TRACK_COLUMNS,
                            (RowSpan(0, len(run_values)),),
                        )
                    )

        result = StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            tuple(groups),
            earth_fixed.coverage,
        )
        result_bytes = sum(group.values.nbytes for group in result.value)
        if (
            result.coverage.complete
            and result_bytes <= self._derived_memory_budget_bytes
        ):
            with self._lock:
                cached_bytes = sum(
                    sum(group.values.nbytes for group in cached_result.value)
                    for cached_result in self._ground_track_cache.values()
                )
                while (
                    self._ground_track_cache
                    and cached_bytes + result_bytes
                    > self._derived_memory_budget_bytes
                ):
                    _, evicted = self._ground_track_cache.popitem(last=False)
                    cached_bytes -= sum(
                        group.values.nbytes for group in evicted.value
                    )
                self._ground_track_cache[key] = result
                self._ground_track_cache.move_to_end(key)
                while len(self._ground_track_cache) > 4:
                    self._ground_track_cache.popitem(last=False)
            self._evict_derived_buffers()

        expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
        first_row = int(
            np.searchsorted(snapshot.raw[:, 0], expanded_bounds[0], side="left")
        )
        stop_row = int(
            np.searchsorted(snapshot.raw[:, 0], expanded_bounds[1], side="right")
        )
        if first_row < stop_row:
            self._publish_notice(
                TierNotice(
                    snapshot.epoch,
                    "ground-track",
                    None,
                    None,
                    first_row,
                    stop_row,
                )
            )
        return result

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
        """Return station profiles and access intervals, queueing missing work."""
        bounds = _validate_time_bounds(bounds_s)
        self._validate_snapshot_epoch(snapshot)
        if not isinstance(station, GroundStation):
            raise TypeError("station must be a GroundStation")
        if not isinstance(wait, bool):
            raise ValueError("wait must be a boolean")
        threshold = (
            station.minimum_elevation_deg
            if minimum_elevation_deg is None
            else _validate_elevation_threshold(minimum_elevation_deg)
        )
        selected_station = replace(station, minimum_elevation_deg=threshold)
        if _cancel_event is not None and _cancel_event.is_set():
            raise CancelledError()

        if snapshot.sample_count == 0:
            empty = StationAccessView(selected_station, (), (), None)
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                empty,
                _time_coverage(snapshot, bounds),
            )

        frame_name = _earth_centered_frame_name(snapshot, "Station access")
        if frame_name is None:
            value = StationAccessView(selected_station, (), (), None)
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                value,
                TimeCoverage(bounds, (), False),
            )

        margin = max(
            ACCESS_WINDOW_MIN_MARGIN_S,
            ACCESS_WINDOW_MARGIN_FRACTION * (bounds[1] - bounds[0]),
        )
        expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
        tier, limitation = self._station_profile_storage(snapshot, selected_station)
        if limitation is not None:
            value = StationAccessView(selected_station, (), (), limitation)
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                value,
                TimeCoverage(bounds, (), _time_coverage(snapshot, bounds).complete),
            )
        if not wait:
            self.prefetch(
                snapshot,
                QueryRequest(
                    "station-access",
                    bounds,
                    station=selected_station,
                    minimum_elevation_deg=float(threshold),
                ),
            )

        layout_ranges: list[tuple[_StationSegmentLayout, int, int]] = []
        for layout in tier.layouts:
            first, stop = _station_profile_row_range(layout, expanded_bounds)
            if first < stop:
                layout_ranges.append((layout, first, stop))
        with self._lock:
            for layout, first, stop in layout_ranges:
                self._touch_chunks_locked(
                    tier.buffer,
                    layout.base_index + first,
                    layout.base_index + stop,
                    expanded_bounds,
                )

        cache_key = (
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            tier.station_key,
            bounds,
            threshold,
        )
        with self._lock:
            cached_intervals = self._station_interval_cache.get(cache_key)

        if wait:
            self._compute_station_profile_ranges(
                snapshot,
                selected_station,
                tier,
                frame_name,
                layout_ranges,
                cancel_event=_cancel_event,
            )

        profile_views: list[LookAngleProfileView] = []
        intervals: list[AccessInterval] = []
        coverage_spans: list[TimeBounds] = []
        cursor = _StoreStationCursor(self, snapshot, self._interpolation_policy)
        ready_values: list[
            tuple[_StationSegmentLayout, int, int, np.ndarray]
        ] = []
        if tier.ready is not None:
            with self._derived_compute_lock, self._lock:
                for layout, first, stop in layout_ranges:
                    first_row = layout.base_index + first
                    stop_row = layout.base_index + stop
                    ready_spans = _row_spans(
                        tier.ready, first_row, stop_row, ready_value=True
                    )
                    for span in ready_spans:
                        values = tier.buffer[span.first : span.stop]
                        profile_views.append(
                            LookAngleProfileView(
                                self._make_column_group_view(
                                    values,
                                    STATION_PROFILE_COLUMNS,
                                    (RowSpan(0, len(values)),),
                                    tier.buffer,
                                    span.first,
                                    span.stop,
                                )
                            )
                        )
                        ready_values.append(
                            (
                                layout,
                                span.first - layout.base_index,
                                span.stop - layout.base_index,
                                values,
                            )
                        )

        for layout, first, stop, values in ready_values:
            first_time = float(values[0, 0])
            stop_time = float(values[-1, 0])
            covered_start = max(bounds[0], first_time)
            covered_stop = min(bounds[1], stop_time)
            if covered_start <= covered_stop:
                coverage_spans.append((covered_start, covered_stop))
            if len(values) < 2 or cached_intervals is not None:
                continue
            events = _station_profile_events(
                values,
                selected_station,
                cursor,
                frame_name,
                threshold,
            )
            timed_events, metric_events = tee(events)
            intervals.extend(
                _intervals_for_segment(
                    selected_station,
                    cursor,
                    frame_name,
                    (event[0] for event in timed_events),
                    (event[1] for event in metric_events),
                    starts_at_coverage=first == 0,
                    ends_at_coverage=stop == layout.row_count,
                    starts_after_gap=layout.raw_start > 0,
                    ends_before_gap=layout.raw_stop < snapshot.sample_count,
                )
            )

        base_coverage = _time_coverage(snapshot, bounds)
        if tier.ready is None:
            requested_rows_ready = not layout_ranges
        else:
            with self._derived_compute_lock:
                requested_rows_ready = all(
                    sum(
                        span.stop - span.first
                        for span in _row_spans(
                            tier.ready,
                            layout.base_index + first,
                            layout.base_index + stop,
                            ready_value=True,
                        )
                    )
                    == stop - first
                    for layout, first, stop in layout_ranges
                )
        coverage = TimeCoverage(
            bounds,
            tuple(coverage_spans),
            base_coverage.complete and requested_rows_ready,
        )
        value = StationAccessView(
            selected_station,
            tuple(profile_views),
            cached_intervals if cached_intervals is not None else tuple(intervals),
            (
                "An access interval reaches an OEM segment gap; "
                "its crossing is unavailable."
                if any(
                    interval.limited_by_gap_at_start
                    or interval.limited_by_gap_at_end
                    for interval in (
                        cached_intervals
                        if cached_intervals is not None
                        else intervals
                    )
                )
                else None
            ),
        )
        result = StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            value,
            coverage,
        )
        if requested_rows_ready and snapshot.status is LoadStatus.COMPLETE:
            with self._lock:
                self._station_interval_cache[cache_key] = value.intervals
                if len(self._station_interval_cache) > 128:
                    oldest = next(iter(self._station_interval_cache))
                    self._station_interval_cache.pop(oldest)
        self._evict_derived_buffers()
        return result

    def _station_profile_storage(
        self, snapshot: StoreSnapshot, station: GroundStation
    ) -> tuple[_StationProfileTier, str | None]:
        station_key = (
            station.station_id,
            station.latitude_deg,
            station.longitude_deg,
            station.altitude_m,
        )
        key = (
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            *station_key,
        )
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            tier = self._station_profiles.get(key)
            if tier is not None:
                return tier, None
            layouts: list[_StationSegmentLayout] = []
            base_index = 0
            for raw_start_value, raw_stop_value in snapshot.segment_bounds:
                raw_start, raw_stop = int(raw_start_value), int(raw_stop_value)
                if raw_stop - raw_start < 2:
                    empty_tier = _StationProfileTier(
                        station_key,
                        np.empty((0, len(STATION_PROFILE_COLUMNS))),
                        ChunkMemo(),
                    )
                    return (
                        empty_tier,
                        "Access intervals unavailable: an OEM segment has fewer "
                        "than two samples.",
                    )
                maximum_source_gap = max(
                    (
                        float(
                            snapshot.raw[index + 1, 0]
                            - snapshot.raw[index, 0]
                        )
                        for index in range(raw_start, raw_stop - 1)
                    ),
                    default=0.0,
                )
                if maximum_source_gap > MAX_SOURCE_SAMPLE_GAP_S:
                    empty_tier = _StationProfileTier(
                        station_key,
                        np.empty((0, len(STATION_PROFILE_COLUMNS))),
                        ChunkMemo(),
                    )
                    return (
                        empty_tier,
                        "Access intervals unavailable: OEM sample spacing exceeds "
                        "five minutes.",
                    )
                start_s = float(snapshot.raw[raw_start, 0])
                end_s = float(snapshot.raw[raw_stop - 1, 0])
                regular_count = max(
                    2,
                    math.ceil((end_s - start_s) / MAX_ACCESS_SAMPLE_STEP_S) + 1,
                )
                if base_index + regular_count > MAX_ACCESS_SAMPLES:
                    empty_tier = _StationProfileTier(
                        station_key,
                        np.empty((0, len(STATION_PROFILE_COLUMNS))),
                        ChunkMemo(),
                    )
                    return (
                        empty_tier,
                        "Access intervals unavailable: OEM coverage requires too "
                        "many samples.",
                    )
                layouts.append(
                    _StationSegmentLayout(
                        int(snapshot.segment_ids[raw_start]),
                        raw_start,
                        raw_stop,
                        start_s,
                        end_s,
                        regular_count,
                        regular_count,
                        base_index,
                    )
                )
                base_index += regular_count
            tier = _StationProfileTier(
                station_key,
                _mapped_float_array(
                    (base_index, len(STATION_PROFILE_COLUMNS))
                ),
                ChunkMemo(),
                tuple(layouts),
                base_index,
                np.zeros(base_index, dtype=bool),
            )
            self._station_profiles[key] = tier
            return tier, None

    def _compute_station_profile_ranges(
        self,
        snapshot: StoreSnapshot,
        station: GroundStation,
        tier: _StationProfileTier,
        frame_name: str,
        ranges: Sequence[tuple[_StationSegmentLayout, int, int]],
        *,
        cancel_event: Event | None,
    ) -> None:
        ready = tier.ready
        if ready is None:
            raise RuntimeError("station profile readiness was not initialized")
        requested_by_chunk: dict[
            int, list[tuple[_StationSegmentLayout, int, int]]
        ] = {}
        for layout, first, stop in ranges:
            row_start = layout.base_index + first
            row_stop = layout.base_index + stop
            for chunk_index in range(
                row_start // DERIVED_CHUNK_SIZE,
                (row_stop - 1) // DERIVED_CHUNK_SIZE + 1,
            ):
                chunk_start = chunk_index * DERIVED_CHUNK_SIZE
                chunk_stop = min(chunk_start + DERIVED_CHUNK_SIZE, tier.row_count)
                requested_by_chunk.setdefault(chunk_index, []).append(
                    (
                        layout,
                        max(row_start, chunk_start),
                        min(row_stop, chunk_stop),
                    )
                )

        with self._derived_compute_lock:
            for chunk_index, requested in sorted(requested_by_chunk.items()):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError()
                chunk_start = chunk_index * DERIVED_CHUNK_SIZE
                chunk_stop = min(chunk_start + DERIVED_CHUNK_SIZE, tier.row_count)
                missing = [
                    (layout, span)
                    for layout, first, stop in requested
                    for span in _row_spans(
                        ready, first, stop, ready_value=False
                    )
                ]
                if not missing:
                    tier.memo.record_hit()
                    continue
                tier.memo.discard(chunk_index)

                def compute() -> RowSpan:
                    for layout, span in missing:
                        for row_index in range(span.first, span.stop):
                            if cancel_event is not None and cancel_event.is_set():
                                raise CancelledError()
                            epoch_s = _station_profile_row_time(
                                layout, row_index - layout.base_index
                            )
                            state = self.state_at(snapshot, epoch_s)
                            row = tier.buffer[row_index]
                            row[0] = epoch_s
                            if state.state_m is None:
                                row[1:] = np.nan
                            else:
                                metrics = station_metrics(
                                    station,
                                    state.state_m,
                                    frame_name,
                                    epoch_s,
                                )
                                row[1:] = (
                                    metrics.azimuth_deg,
                                    metrics.elevation_deg,
                                    metrics.slant_range_km,
                                )
                        ready[span.first : span.stop] = True
                        self._publish_notice(
                            TierNotice(
                                snapshot.epoch,
                                "station-access",
                                None,
                                station.station_id,
                                span.first,
                                span.stop,
                            )
                        )
                    return RowSpan(chunk_start, chunk_stop)

                tier.memo.get_or_compute(
                    chunk_index,
                    compute,
                    epoch=snapshot.epoch,
                    policy_revision=snapshot.policy_revision,
                    tentative=(
                        snapshot.status is LoadStatus.LOADING
                        and chunk_stop < chunk_start + DERIVED_CHUNK_SIZE
                    ),
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
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if self._raw is None:
                raise RuntimeError("store has no active epoch")
            buffer = self._series_buffers.get(group)
            if buffer is None:
                buffer = _mapped_float_array(
                    (len(self._raw), len(_SERIES_COLUMNS[group])),
                )
                self._series_buffers[group] = buffer
                self._series_ready[group] = np.zeros(len(self._raw), dtype=bool)
            memo = self._series_memos.get(group)
            if memo is None:
                memo = ChunkMemo()
                self._series_memos[group] = memo
            return buffer, memo, self._series_ready[group]

    def _touch_chunks_locked(
        self,
        buffer: np.ndarray,
        first_row: int,
        stop_row: int,
        bounds: TimeBounds | None = None,
    ) -> None:
        if first_row >= stop_row:
            return
        buffer_id = _mapped_buffer_id(buffer)
        first_chunk = first_row // DERIVED_CHUNK_SIZE
        last_chunk = (stop_row - 1) // DERIVED_CHUNK_SIZE
        for chunk_index in range(first_chunk, last_chunk + 1):
            key = (buffer_id, chunk_index)
            self._buffer_touch_sequence += 1
            self._chunk_access_order[key] = self._buffer_touch_sequence
            if bounds is not None:
                self._chunk_ranges[key] = (bounds,)

    def _pin_chunks(self, chunk_keys: tuple[tuple[int, int], ...]) -> None:
        with self._lock:
            for key in chunk_keys:
                self._pinned_chunks[key] = self._pinned_chunks.get(key, 0) + 1

    @staticmethod
    def _release_chunks(
        store_ref: weakref.ReferenceType[OemDataStore],
        chunk_keys: tuple[tuple[int, int], ...],
    ) -> None:
        store = store_ref()
        if store is None:
            return
        with store._lock:
            for key in chunk_keys:
                count = store._pinned_chunks.get(key, 0)
                if count <= 1:
                    store._pinned_chunks.pop(key, None)
                else:
                    store._pinned_chunks[key] = count - 1

    def _make_column_group_view(
        self,
        values: np.ndarray,
        columns: tuple[str, ...],
        segment_bounds: tuple[RowSpan, ...],
        owner_buffer: np.ndarray,
        first_row: int,
        stop_row: int,
    ) -> ColumnGroupView:
        buffer_id = _mapped_buffer_id(owner_buffer)
        chunk_keys = tuple(
            (buffer_id, chunk_index)
            for chunk_index in range(
                first_row // DERIVED_CHUNK_SIZE,
                (stop_row - 1) // DERIVED_CHUNK_SIZE + 1,
            )
        )
        lease = _ChunkLease(self, chunk_keys)
        return ColumnGroupView(values, columns, segment_bounds, lease)

    def _evict_derived_buffers(self) -> None:
        with self._derived_compute_lock, self._lock:
            candidates: list[_EvictionCandidate] = []

            def add_candidates(
                kind: Literal["series", "earth-fixed", "station-access"],
                buffer: np.ndarray,
                memo: ChunkMemo[int, RowSpan],
                ready: np.ndarray | None,
                row_count: int,
                columns: int,
                policy_revision: int,
            ) -> None:
                if ready is None:
                    return
                buffer_id = _mapped_buffer_id(buffer)
                for chunk_index in range(
                    math.ceil(row_count / DERIVED_CHUNK_SIZE)
                ):
                    if memo.state(
                        chunk_index,
                        epoch=self._epoch,
                        policy_revision=policy_revision,
                    ) not in (ChunkState.COMPLETE, ChunkState.TENTATIVE):
                        continue
                    chunk_rows = min(
                        DERIVED_CHUNK_SIZE,
                        row_count - chunk_index * DERIVED_CHUNK_SIZE,
                    )
                    chunk_key = (buffer_id, chunk_index)
                    candidates.append(
                        _EvictionCandidate(
                            access_order=self._chunk_access_order.get(
                                chunk_key, 0
                            ),
                            buffer_id=buffer_id,
                            kind=kind,
                            chunk_index=chunk_index,
                            buffer=buffer,
                            memo=memo,
                            ready=ready,
                            row_count=row_count,
                            columns=columns,
                            size_bytes=(
                                chunk_rows
                                * columns
                                * np.dtype(np.float64).itemsize
                            ),
                        )
                    )

            for group, buffer in self._series_buffers.items():
                add_candidates(
                    "series",
                    buffer,
                    self._series_memos[group],
                    self._series_ready[group],
                    len(buffer),
                    len(_SERIES_COLUMNS[group]),
                    0,
                )
            if self._earth_fixed_buffer is not None:
                add_candidates(
                    "earth-fixed",
                    self._earth_fixed_buffer,
                    self._earth_fixed_memo,
                    self._earth_fixed_ready,
                    len(self._earth_fixed_buffer),
                    len(EARTH_FIXED_COLUMNS),
                    0,
                )
            for tier in self._station_profiles.values():
                add_candidates(
                    "station-access",
                    tier.buffer,
                    tier.memo,
                    tier.ready,
                    tier.row_count,
                    len(STATION_PROFILE_COLUMNS),
                    self._policy_revision,
                )
            resident_bytes = sum(candidate.size_bytes for candidate in candidates)
            resident_bytes += sum(
                sum(group.values.nbytes for group in query.value)
                for query in self._ground_track_cache.values()
            )
            if resident_bytes <= self._derived_memory_budget_bytes:
                return

            while (
                self._ground_track_cache
                and resident_bytes > self._derived_memory_budget_bytes
            ):
                _, evicted = self._ground_track_cache.popitem(last=False)
                resident_bytes -= sum(group.values.nbytes for group in evicted.value)
            if resident_bytes <= self._derived_memory_budget_bytes:
                return

            advice = getattr(mmap, "MADV_FREE", getattr(mmap, "MADV_DONTNEED", None))
            if advice is None or not hasattr(mmap.mmap, "madvise"):
                return

            for candidate in sorted(
                candidates,
                key=lambda item: (
                    item.access_order,
                    item.buffer_id,
                    item.kind,
                    item.chunk_index,
                ),
            ):
                if resident_bytes <= self._derived_memory_budget_bytes:
                    break
                chunk_key = (candidate.buffer_id, candidate.chunk_index)
                if self._pinned_chunks.get(chunk_key, 0):
                    continue
                if any(
                    _range_is_active(bounds, self._range_hint)
                    for bounds in self._chunk_ranges.get(chunk_key, ())
                ):
                    continue

                chunk_start = candidate.chunk_index * DERIVED_CHUNK_SIZE
                chunk_stop = min(
                    chunk_start + DERIVED_CHUNK_SIZE, candidate.row_count
                )

                def release_chunk() -> None:
                    _madvise_chunk(
                        candidate.buffer,
                        candidate.chunk_index,
                        candidate.row_count,
                        candidate.columns,
                        advice,
                    )
                    candidate.ready[chunk_start:chunk_stop] = False

                if not candidate.memo.evict(
                    candidate.chunk_index,
                    release_chunk,
                    epoch=self._epoch,
                    policy_revision=(
                        self._policy_revision
                        if candidate.kind == "station-access"
                        else 0
                    ),
                ):
                    continue
                if candidate.kind == "station-access":
                    self._station_interval_cache.clear()
                self._chunk_access_order.pop(chunk_key, None)
                self._chunk_ranges.pop(chunk_key, None)
                resident_bytes -= candidate.size_bytes

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
            first_chunk = start // DERIVED_CHUNK_SIZE
            last_chunk = (stop - 1) // DERIVED_CHUNK_SIZE
            for chunk_index in range(first_chunk, last_chunk + 1):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError()
                chunk_start = chunk_index * DERIVED_CHUNK_SIZE
                chunk_stop = min(
                    chunk_start + DERIVED_CHUNK_SIZE, snapshot.sample_count
                )
                requested_start = max(start, chunk_start)
                requested_stop = min(stop, chunk_stop)
                missing_spans = _row_spans(
                    ready, requested_start, requested_stop, ready_value=False
                )
                if not missing_spans:
                    memo.record_hit()
                    continue
                memo.discard(chunk_index)
                tentative = (
                    snapshot.status is LoadStatus.LOADING
                    and chunk_stop < chunk_start + DERIVED_CHUNK_SIZE
                )

                def compute() -> RowSpan:
                    for span in missing_spans:
                        if cancel_event is not None and cancel_event.is_set():
                            raise CancelledError()
                        _write_series_chunk(
                            snapshot, group, span.first, span.stop, buffer
                        )
                        ready[span.first : span.stop] = True
                        if on_chunk is not None:
                            on_chunk(span)
                    return RowSpan(requested_start, requested_stop)

                memo.get_or_compute(
                    chunk_index,
                    compute,
                    epoch=snapshot.epoch,
                    policy_revision=0,
                    tentative=tentative,
                    cancel_event=cancel_event,
                )

    def _compute_earth_fixed_range(
        self,
        snapshot: StoreSnapshot,
        frame_name: str,
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
            first_chunk = start // DERIVED_CHUNK_SIZE
            last_chunk = (stop - 1) // DERIVED_CHUNK_SIZE
            for chunk_index in range(first_chunk, last_chunk + 1):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError()
                chunk_start = chunk_index * DERIVED_CHUNK_SIZE
                chunk_stop = min(
                    chunk_start + DERIVED_CHUNK_SIZE, snapshot.sample_count
                )
                requested_start = max(start, chunk_start)
                requested_stop = min(stop, chunk_stop)
                missing_spans = _row_spans(
                    ready, requested_start, requested_stop, ready_value=False
                )
                if not missing_spans:
                    memo.record_hit()
                    continue
                memo.discard(chunk_index)
                tentative = (
                    snapshot.status is LoadStatus.LOADING
                    and chunk_stop < chunk_start + DERIVED_CHUNK_SIZE
                )

                def compute() -> RowSpan:
                    for span in missing_spans:
                        if cancel_event is not None and cancel_event.is_set():
                            raise CancelledError()
                        _write_earth_fixed_chunk(
                            snapshot, frame_name, span.first, span.stop, buffer
                        )
                        ready[span.first : span.stop] = True
                        if on_chunk is not None:
                            on_chunk(span)
                    return RowSpan(requested_start, requested_stop)

                memo.get_or_compute(
                    chunk_index,
                    compute,
                    epoch=snapshot.epoch,
                    policy_revision=0,
                    tentative=tentative,
                    cancel_event=cancel_event,
                )


def _validate_time_bounds(bounds_s: TimeBounds) -> TimeBounds:
    try:
        start_value, stop_value = bounds_s
    except (TypeError, ValueError) as error:
        raise ValueError("time bounds must contain exactly two finite values") from error
    if isinstance(start_value, bool) or isinstance(stop_value, bool):
        raise ValueError("time bounds must contain exactly two finite values")
    try:
        start = float(start_value)
        stop = float(stop_value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("time bounds must contain exactly two finite values") from error
    if not math.isfinite(start) or not math.isfinite(stop) or start > stop:
        raise ValueError("time bounds must be finite and ordered")
    return start, stop


def _normalize_longitude(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("center_longitude_deg must be finite")
    try:
        longitude = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("center_longitude_deg must be finite") from error
    if not math.isfinite(longitude):
        raise ValueError("center_longitude_deg must be finite")
    return ((longitude + 180.0) % 360.0) - 180.0


def _validate_nonnegative_finite(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite non-negative number") from error
    if not math.isfinite(converted) or converted < 0.0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return converted


def _mapped_float_array(shape: tuple[int, int]) -> np.ndarray:
    rows, columns = shape
    if rows < 1:
        return np.empty(shape, dtype=np.float64)
    flags = getattr(mmap, "MAP_PRIVATE", None)
    anonymous_flag = getattr(
        mmap,
        "MAP_ANONYMOUS",
        getattr(mmap, "MAP_ANON", None),
    )
    if flags is None or anonymous_flag is None:
        mapping = mmap.mmap(
            -1, rows * columns * np.dtype(np.float64).itemsize
        )
    else:
        mapping = mmap.mmap(
            -1,
            rows * columns * np.dtype(np.float64).itemsize,
            flags=flags | anonymous_flag,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
        )
    return np.ndarray(shape, dtype=np.float64, buffer=mapping)


def _mapping_for_buffer(buffer: np.ndarray) -> mmap.mmap | None:
    owner: object = buffer
    while isinstance(owner, np.ndarray):
        owner = owner.base
    return owner if isinstance(owner, mmap.mmap) else None


def _mapped_buffer_id(buffer: np.ndarray) -> int:
    mapping = _mapping_for_buffer(buffer)
    return id(mapping) if mapping is not None else id(buffer)


def _madvise_chunk(
    buffer: np.ndarray,
    chunk_index: int,
    row_count: int,
    columns: int,
    advice: int,
) -> None:
    mapping = _mapping_for_buffer(buffer)
    if mapping is None:
        raise RuntimeError("derived buffer is not backed by an mmap")
    bytes_per_row = columns * np.dtype(np.float64).itemsize
    start = chunk_index * DERIVED_CHUNK_SIZE * bytes_per_row
    rows = min(DERIVED_CHUNK_SIZE, row_count - chunk_index * DERIVED_CHUNK_SIZE)
    length = rows * bytes_per_row
    if length:
        mapping.madvise(advice, start, length)


def _range_is_active(bounds: TimeBounds, hint: RangeHint | None) -> bool:
    if hint is None:
        return False
    plot_width = (
        max(hint.plot[1] - hint.plot[0], 1.0)
        if hint.plot is not None
        else max(hint.playback[1] - hint.playback[0], 1.0)
    )
    active_ranges = [hint.playback, (hint.now_s - plot_width, hint.now_s + plot_width)]
    if hint.plot is not None:
        active_ranges.append(
            (hint.plot[0] - plot_width, hint.plot[1] + plot_width)
        )
    return any(_ranges_intersect(bounds, active) for active in active_ranges)


def _validate_elevation_threshold(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("minimum_elevation_deg must be an integer from 0 through 90")
    converted = float(value)
    if (
        not math.isfinite(converted)
        or converted < 0
        or converted > 90
        or not converted.is_integer()
    ):
        raise ValueError("minimum_elevation_deg must be an integer from 0 through 90")
    return int(converted)


def _station_profile_row_time(layout: _StationSegmentLayout, index: int) -> float:
    if index == layout.regular_count - 1:
        return layout.end_s
    step = (layout.end_s - layout.start_s) / (layout.regular_count - 1)
    return layout.start_s + index * step


def _station_profile_row_range(
    layout: _StationSegmentLayout, bounds: TimeBounds
) -> tuple[int, int]:
    def insertion_index(target: float, *, right: bool) -> int:
        low = 0
        high = layout.row_count
        while low < high:
            middle = (low + high) // 2
            value = _station_profile_row_time(layout, middle)
            if value < target or (right and value == target):
                low = middle + 1
            else:
                high = middle
        return low

    first = max(0, insertion_index(bounds[0], right=False) - 1)
    stop = min(layout.row_count, insertion_index(bounds[1], right=True) + 1)
    return first, stop


def _station_metrics_from_profile_row(
    row: np.ndarray, minimum_elevation_deg: int
) -> StationMetrics | None:
    if not np.isfinite(row).all():
        return None
    return StationMetrics(
        float(row[1]),
        float(row[2]),
        float(row[3]),
        float(row[2]) >= minimum_elevation_deg,
    )


def _station_profile_events(
    values: np.ndarray,
    station: GroundStation,
    cursor: _StoreStationCursor,
    frame_name: str,
    minimum_elevation_deg: int,
) -> Iterator[tuple[float, StationMetrics | None]]:
    def sample(index: int) -> tuple[float, StationMetrics | None]:
        row = values[index]
        return float(row[0]), _station_metrics_from_profile_row(
            row, minimum_elevation_deg
        )

    if len(values) == 0:
        return
    yield sample(0)
    last_peak_time: float | None = None
    for index in range(1, len(values) - 1):
        previous = sample(index - 1)
        current = sample(index)
        following = sample(index + 1)
        current_metrics = current[1]
        previous_metrics = previous[1]
        following_metrics = following[1]
        refined: tuple[float, StationMetrics] | None = None
        if (
            current_metrics is not None
            and not current_metrics.access
            and previous_metrics is not None
            and following_metrics is not None
            and current_metrics.elevation_deg >= previous_metrics.elevation_deg
            and current_metrics.elevation_deg >= following_metrics.elevation_deg
        ):
            peak_time, peak_metrics = _refine_peak(
                station,
                cursor,
                frame_name,
                previous[0],
                following[0],
            )
            peak_metrics = StationMetrics(
                peak_metrics.azimuth_deg,
                peak_metrics.elevation_deg,
                peak_metrics.slant_range_km,
                peak_metrics.elevation_deg >= minimum_elevation_deg,
            )
            if (
                peak_metrics.access
                and all(
                    abs(peak_time - sample_time) > CROSSING_TIME_TOLERANCE_S
                    for sample_time in (
                        previous[0],
                        current[0],
                        following[0],
                    )
                )
                and (
                    last_peak_time is None
                    or abs(peak_time - last_peak_time) > CROSSING_TIME_TOLERANCE_S
                )
            ):
                refined = peak_time, peak_metrics
                last_peak_time = peak_time
        if refined is not None and refined[0] < current[0]:
            yield refined
        yield current
        if refined is not None and refined[0] >= current[0]:
            yield refined
    if len(values) > 1:
        yield sample(len(values) - 1)


def _ranges_intersect(first: TimeBounds, second: TimeBounds) -> bool:
    return first[0] <= second[1] and second[0] <= first[1]


def _row_spans(
    ready: np.ndarray,
    start: int,
    stop: int,
    *,
    ready_value: bool,
) -> tuple[RowSpan, ...]:
    if start >= stop:
        return ()
    selected = ready[start:stop]
    transitions = np.flatnonzero(selected[1:] != selected[:-1]) + 1
    edges = np.concatenate(([0], transitions, [len(selected)]))
    return tuple(
        RowSpan(start + int(first), start + int(end))
        for first, end in zip(edges, edges[1:])
        if bool(selected[first]) is ready_value
    )


def _intersect_row_spans(
    first: Sequence[RowSpan],
    second: Sequence[RowSpan],
) -> tuple[RowSpan, ...]:
    intersections: list[RowSpan] = []
    left = right = 0
    while left < len(first) and right < len(second):
        start = max(first[left].first, second[right].first)
        stop = min(first[left].stop, second[right].stop)
        if start < stop:
            intersections.append(RowSpan(start, stop))
        if first[left].stop <= second[right].stop:
            left += 1
        else:
            right += 1
    return tuple(intersections)


def _coverage_for_rows(
    snapshot: StoreSnapshot,
    bounds: TimeBounds,
    spans: Sequence[RowSpan],
    complete: bool,
) -> TimeCoverage:
    covered: list[TimeBounds] = []
    for span in spans:
        for segment_start, segment_stop in snapshot.segment_bounds:
            first = max(span.first, int(segment_start))
            stop = min(span.stop, int(segment_stop))
            if first >= stop:
                continue
            start_s = max(bounds[0], float(snapshot.raw[first, 0]))
            stop_s = min(bounds[1], float(snapshot.raw[stop - 1, 0]))
            if start_s <= stop_s:
                if covered and covered[-1][1] == start_s:
                    covered[-1] = (covered[-1][0], stop_s)
                else:
                    covered.append((start_s, stop_s))
    return TimeCoverage(bounds, tuple(covered), complete)


def _earth_centered_frame_name(
    snapshot: StoreSnapshot, purpose: str
) -> str | None:
    metadata = dict(snapshot.meta)
    frame_name = metadata.get("REF_FRAME")
    center_name = metadata.get("CENTER_NAME")
    if not isinstance(frame_name, str) or not isinstance(center_name, str):
        if snapshot.status is LoadStatus.COMPLETE:
            raise GroundTrackPreparationError(
                f"{purpose} requires CENTER_NAME and REF_FRAME metadata"
            )
        return None
    if center_name.strip().upper() not in EARTH_CENTERS:
        raise GroundTrackPreparationError(
            f"{purpose} requires an Earth-centered OEM; found {center_name!r}"
        )
    return frame_name


def _validate_query_time(t_s: float) -> float:
    if isinstance(t_s, bool):
        raise ValueError("query time must be a finite number")
    try:
        query_time = float(t_s)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("query time must be a finite number") from error
    if not math.isfinite(query_time):
        raise ValueError("query time must be a finite number")
    return query_time


def _unavailable_state(t_s: float, status: CursorStatus) -> CursorState:
    return CursorState(
        t=t_s,
        state_m=None,
        r_km=None,
        v_kms=None,
        speed=None,
        altitude=None,
        distance=None,
        status=status,
    )


def _empty_column_group(columns: tuple[str, ...]) -> ColumnGroupView:
    return ColumnGroupView(
        np.empty((0, len(columns)), dtype=np.float64),
        columns,
        (),
    )


def _time_coverage(snapshot: StoreSnapshot, bounds: TimeBounds) -> TimeCoverage:
    if snapshot.sample_count == 0:
        return TimeCoverage(
            bounds,
            (),
            snapshot.status is LoadStatus.COMPLETE,
        )

    covered: list[TimeBounds] = []
    for first, stop in snapshot.segment_bounds:
        first_index = int(first)
        stop_index = int(stop)
        if first_index >= stop_index:
            continue
        start_s = max(bounds[0], float(snapshot.raw[first_index, 0]))
        stop_s = min(bounds[1], float(snapshot.raw[stop_index - 1, 0]))
        if start_s <= stop_s:
            covered.append((start_s, stop_s))

    if snapshot.status is LoadStatus.COMPLETE:
        complete = True
    else:
        complete = bounds[1] <= float(snapshot.raw[-1, 0])
    return TimeCoverage(bounds, tuple(covered), complete)


def _point_segment_spans(
    snapshot: StoreSnapshot, start: int, stop: int
) -> tuple[RowSpan, ...]:
    spans = []
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(start, int(segment_start))
        end = min(stop, int(segment_stop))
        if first < end:
            spans.append(RowSpan(first - start, end - start))
    return tuple(spans)


def _series_segment_spans(
    snapshot: StoreSnapshot,
    group: SeriesGroupName,
    start: int,
    stop: int,
    stride: int,
    *,
    origin: int | None = None,
) -> tuple[RowSpan, ...]:
    if origin is None:
        origin = start
    first_view_row = math.ceil((start - origin) / stride)
    spans = []
    delta_offset = 1 if group in ("rtn", "distance-delta") else 0
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(start, int(segment_start) + delta_offset)
        end = min(stop, int(segment_stop))
        if first >= end:
            continue
        first_in_view = math.ceil((first - origin) / stride) - first_view_row
        end_in_view = math.ceil((end - origin) / stride) - first_view_row
        if first_in_view < end_in_view:
            spans.append(RowSpan(first_in_view, end_in_view))
    return tuple(spans)


def _write_series_chunk(
    snapshot: StoreSnapshot,
    group: SeriesGroupName,
    start: int,
    stop: int,
    output: np.ndarray,
) -> None:
    output[start:stop] = compute_series_chunk(
        snapshot.raw,
        snapshot.segment_ids,
        group,
        start,
        stop,
    )


def _write_earth_fixed_chunk(
    snapshot: StoreSnapshot,
    frame_name: str,
    start: int,
    stop: int,
    output: np.ndarray,
) -> None:
    normalized_frame = normalize_conversion_frame_name(frame_name)
    for row in range(start, stop):
        output[row, 0] = snapshot.raw[row, 0]
        output[row, 1:4] = _state_position_to_itrf_m_normalized(
            snapshot.raw[row, 1:7],
            normalized_frame,
            float(snapshot.raw[row, 0]),
            source_frame_name=frame_name,
        )
