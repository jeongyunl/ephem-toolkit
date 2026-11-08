"""Store-owned raw OEM storage with atomic prefix publication."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
from threading import Event, RLock
from types import MappingProxyType
from typing import Generic, Literal, TypeVar, Union, TYPE_CHECKING

import numpy as np

from ephem_toolkit.core import misc, wgs
from ephem_toolkit.core.ccsds.odm import ODM_MAX_LINE_LENGTH
from ephem_toolkit.core.interpolator.factory import InterpolatorFactory
from ephem_toolkit.core.interpolator.interpolation_spec import (
    InterpolationSpec,
    InterpolationType,
)
from ephem_toolkit.core.interpolator.interpolator import Interpolator
from .chunk_memo import ChunkMemo, ChunkMemoCounters
from .cursor import CursorState, CursorStatus
from .ground_track import (
    EARTH_CENTERS,
    GroundTrackPreparationError,
    state_position_to_itrf_m,
)
from .series import OrbitSeries
from .time_unit import TimeUnit

if TYPE_CHECKING:
    from .ground_stations import GroundStation
    from .station_access import AccessInterval


T = TypeVar("T")
TimeBounds = tuple[float, float]
SeriesGroupName = Literal["kinematics", "rtn", "direction-rates"]
SERIES_GROUPS: tuple[SeriesGroupName, ...] = (
    "kinematics",
    "rtn",
    "direction-rates",
)
DERIVED_CHUNK_SIZE = 4096
KINEMATICS_COLUMNS = ("t", "speed_m_s", "distance_m", "altitude_m")
RTN_COLUMNS = (
    "t",
    "delta_r_m",
    "delta_t_m",
    "delta_n_m",
    "delta_vr_m_s",
    "delta_vt_m_s",
    "delta_vn_m_s",
)
DIRECTION_RATE_COLUMNS = (
    "t",
    "direction_change_rad",
    "angular_velocity_rad_s",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
    "roll_rate_rad_s",
    "pitch_rate_rad_s",
    "yaw_rate_rad_s",
)
EARTH_FIXED_COLUMNS = ("t", "x_itrf", "y_itrf", "z_itrf")
_SERIES_COLUMNS: Mapping[SeriesGroupName, tuple[str, ...]] = MappingProxyType(
    {
        "kinematics": KINEMATICS_COLUMNS,
        "rtn": RTN_COLUMNS,
        "direction-rates": DIRECTION_RATE_COLUMNS,
    }
)
TierName = Literal[
    "series", "earth-fixed", "ground-track", "station-access", "footprints"
]


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


@dataclass(frozen=True)
class TimeCoverage:
    """Requested time bounds and the spans currently covered by a query."""

    requested_s: TimeBounds
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
class QueryRequest:
    """Request for a lazy derived-tier range."""

    tier: TierName
    bounds_s: TimeBounds
    station: GroundStation | None = None
    series_groups: tuple[SeriesGroupName, ...] = ()
    max_samples: int | None = None
    minimum_elevation_deg: float | None = None


@dataclass(frozen=True)
class ColumnGroupView:
    """Read-only view of a store-owned derived column group."""

    values: np.ndarray
    columns: tuple[str, ...]
    segment_bounds: tuple[RowSpan, ...]

    def __post_init__(self) -> None:
        if self.values.ndim != 2 or self.values.shape[1] != len(self.columns):
            raise ValueError("column-group shape must match its column names")
        view = np.asarray(memoryview(self.values).toreadonly())
        object.__setattr__(self, "values", view)

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


SeriesGroups = Mapping[SeriesGroupName, ColumnGroupView]
GroundTrackGroups = tuple[ColumnGroupView, ...]
EarthFixedPositions = ColumnGroupView


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

    def __init__(self) -> None:
        self._lock = RLock()
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
        self._segment_bounds: list[tuple[int, int, int]] = []
        self._max_gap_s = 0.0
        self._status = LoadStatus.EMPTY
        self._header: tuple[tuple[str, object], ...] = ()
        self._meta: tuple[tuple[str, object], ...] = ()
        self._failure: str | None = None
        self._reservation: RawReservation | None = None
        self._validating = False
        self._series_buffers: dict[SeriesGroupName, np.ndarray] = {}
        self._series_memos: dict[SeriesGroupName, ChunkMemo[int, RowSpan]] = {}
        self._earth_fixed_buffer: np.ndarray | None = None
        self._earth_fixed_memo: ChunkMemo[int, RowSpan] = ChunkMemo()

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

    @staticmethod
    def capacity_for_file(
        source: str | Path, *, cancel_event: Event | None = None
    ) -> int:
        """Return a safe row-capacity bound from non-covariance OEM lines.

        State rows are outside covariance blocks and the parser accepts at most one
        state row per physical input line. Counting every other line as well keeps
        this a safe upper bound without reserving for covariance matrices. Universal
        newlines and a final unterminated line are supported. An optional
        cancellation event is checked between bounded reads.
        """
        line_count = 0
        in_covariance = False
        pending = ""

        def count_line(line: str) -> None:
            nonlocal in_covariance, line_count
            if len(line) > ODM_MAX_LINE_LENGTH:
                raise ValueError(
                    f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
                )
            content = line.strip()
            if content == "COVARIANCE_START":
                in_covariance = True
            elif content == "COVARIANCE_STOP":
                in_covariance = False
            elif not in_covariance:
                line_count += 1

        with Path(source).open("r", encoding="utf-8", newline=None) as stream:
            while chunk := stream.read(1024 * 1024):
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("capacity scan cancelled")
                lines = (pending + chunk).split("\n")
                pending = lines.pop()
                for line in lines:
                    count_line(line)
                if len(pending) > ODM_MAX_LINE_LENGTH:
                    raise ValueError(
                        f"OEM exceeds {ODM_MAX_LINE_LENGTH}-character line limit"
                    )
        if pending:
            count_line(pending)
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("capacity scan cancelled")
        return max(line_count, 1)

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
        if self._reservation is not None:
            self._reservation._close()
        for memo in self._series_memos.values():
            memo.clear()
        self._earth_fixed_memo.clear()
        self._series_buffers.clear()
        self._earth_fixed_buffer = None
        self._epoch += 1
        self._revision = 0
        self._policy_revision = 0
        self._sample_count = 0
        self._raw = None
        self._segment_ids = None
        self._segment_bounds = []
        self._max_gap_s = 0.0
        self._status = LoadStatus.EMPTY
        self._header = ()
        self._meta = ()
        self._failure = None
        self._reservation = None
        self._validating = False

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
                self._revision += 1
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

    def series(
        self,
        snapshot: StoreSnapshot,
        bounds_s: TimeBounds,
        groups: Sequence[SeriesGroupName] | None = None,
        max_samples: int | None = None,
    ) -> StoreQuery[SeriesGroups]:
        """Lazily compute requested series groups and return read-only range views."""
        bounds = _validate_time_bounds(bounds_s)
        self._validate_snapshot_epoch(snapshot)
        selected_groups = SERIES_GROUPS if groups is None else tuple(dict.fromkeys(groups))
        unknown_groups = set(selected_groups).difference(SERIES_GROUPS)
        if unknown_groups:
            raise ValueError(f"unsupported series groups: {sorted(unknown_groups)}")
        if max_samples is not None and (
            isinstance(max_samples, bool)
            or not isinstance(max_samples, int)
            or max_samples < 1
        ):
            raise ValueError("max_samples must be a positive integer")
        if snapshot.sample_count == 0:
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                MappingProxyType(
                    {
                        group: _empty_column_group(_SERIES_COLUMNS[group])
                        for group in selected_groups
                    }
                ),
                _time_coverage(snapshot, bounds),
            )

        start = int(np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left"))
        stop = int(np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right"))
        result: dict[SeriesGroupName, ColumnGroupView] = {}
        for group in selected_groups:
            if start == stop:
                result[group] = _empty_column_group(_SERIES_COLUMNS[group])
                continue
            buffer, memo = self._series_storage(snapshot, group)
            self._compute_series_range(snapshot, group, start, stop, buffer, memo)
            stride = 1
            row_count = stop - start
            if max_samples is not None and row_count > max_samples:
                stride = math.ceil(row_count / max_samples)
            values = buffer[start:stop:stride]
            spans = _series_segment_spans(snapshot, group, start, stop, stride)
            result[group] = ColumnGroupView(
                values,
                _SERIES_COLUMNS[group],
                spans,
            )

        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            MappingProxyType(result),
            _time_coverage(snapshot, bounds),
        )

    def earth_fixed_positions(
        self,
        snapshot: StoreSnapshot,
        bounds_s: TimeBounds,
        margin_s: float = 0.0,
    ) -> StoreQuery[EarthFixedPositions]:
        """Lazily materialize ITRF sample positions for a requested time range."""
        bounds = _validate_time_bounds(bounds_s)
        self._validate_snapshot_epoch(snapshot)
        if isinstance(margin_s, bool):
            raise ValueError("margin_s must be a finite non-negative number")
        try:
            margin = float(margin_s)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                "margin_s must be a finite non-negative number"
            ) from error
        if not math.isfinite(margin) or margin < 0.0:
            raise ValueError("margin_s must be a finite non-negative number")
        metadata = dict(snapshot.meta)
        frame_name = metadata.get("REF_FRAME")
        center_name = metadata.get("CENTER_NAME")
        if not isinstance(frame_name, str) or not isinstance(center_name, str):
            if snapshot.status is LoadStatus.COMPLETE:
                raise GroundTrackPreparationError(
                    "Earth-fixed positions require CENTER_NAME and REF_FRAME metadata"
                )
            empty = _empty_column_group(EARTH_FIXED_COLUMNS)
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                empty,
                TimeCoverage(bounds, (), False),
            )
        if center_name.strip().upper() not in EARTH_CENTERS:
            raise GroundTrackPreparationError(
                f"Earth-fixed positions require an Earth-centered OEM; found {center_name!r}"
            )

        if snapshot.sample_count == 0:
            empty = _empty_column_group(EARTH_FIXED_COLUMNS)
            return StoreQuery(
                snapshot.epoch,
                snapshot.revision,
                snapshot.policy_revision,
                empty,
                _time_coverage(snapshot, bounds),
            )

        expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
        start = int(
            np.searchsorted(snapshot.raw[:, 0], expanded_bounds[0], side="left")
        )
        stop = int(
            np.searchsorted(snapshot.raw[:, 0], expanded_bounds[1], side="right")
        )
        if start == stop:
            group = _empty_column_group(EARTH_FIXED_COLUMNS)
        else:
            buffer, memo = self._earth_fixed_storage(snapshot)
            self._compute_earth_fixed_range(
                snapshot, frame_name, start, stop, buffer, memo
            )
            group = ColumnGroupView(
                buffer[start:stop],
                EARTH_FIXED_COLUMNS,
                _point_segment_spans(snapshot, start, stop),
            )

        return StoreQuery(
            snapshot.epoch,
            snapshot.revision,
            snapshot.policy_revision,
            group,
            _time_coverage(snapshot, bounds),
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
    ) -> tuple[np.ndarray, ChunkMemo[int, RowSpan]]:
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if self._raw is None:
                raise RuntimeError("store has no active epoch")
            buffer = self._series_buffers.get(group)
            if buffer is None:
                buffer = np.empty(
                    (len(self._raw), len(_SERIES_COLUMNS[group])),
                    dtype=np.float64,
                )
                self._series_buffers[group] = buffer
            memo = self._series_memos.get(group)
            if memo is None:
                memo = ChunkMemo()
                self._series_memos[group] = memo
            return buffer, memo

    def _earth_fixed_storage(
        self, snapshot: StoreSnapshot
    ) -> tuple[np.ndarray, ChunkMemo[int, RowSpan]]:
        with self._lock:
            if snapshot.epoch != self._epoch:
                raise RuntimeError("store epoch has changed")
            if self._raw is None:
                raise RuntimeError("store has no active epoch")
            if self._earth_fixed_buffer is None:
                self._earth_fixed_buffer = np.empty(
                    (len(self._raw), len(EARTH_FIXED_COLUMNS)),
                    dtype=np.float64,
                )
            return self._earth_fixed_buffer, self._earth_fixed_memo

    def _compute_series_range(
        self,
        snapshot: StoreSnapshot,
        group: SeriesGroupName,
        start: int,
        stop: int,
        buffer: np.ndarray,
        memo: ChunkMemo[int, RowSpan],
    ) -> None:
        first_chunk = start // DERIVED_CHUNK_SIZE
        last_chunk = (stop - 1) // DERIVED_CHUNK_SIZE
        for chunk_index in range(first_chunk, last_chunk + 1):
            chunk_start = chunk_index * DERIVED_CHUNK_SIZE
            chunk_stop = min(chunk_start + DERIVED_CHUNK_SIZE, snapshot.sample_count)
            tentative = (
                snapshot.status is LoadStatus.LOADING
                and chunk_stop < chunk_start + DERIVED_CHUNK_SIZE
            )

            def compute() -> RowSpan:
                _write_series_chunk(snapshot, group, chunk_start, chunk_stop, buffer)
                return RowSpan(chunk_start, chunk_stop)

            span = memo.get_or_compute(
                chunk_index,
                compute,
                epoch=snapshot.epoch,
                policy_revision=0,
                tentative=tentative,
            )
            if span.stop < chunk_stop:
                memo.invalidate(chunk_index)
                span = memo.get_or_compute(
                    chunk_index,
                    compute,
                    epoch=snapshot.epoch,
                    policy_revision=0,
                    tentative=tentative,
                )
                if span.stop < chunk_stop:
                    raise RuntimeError("series chunk is not fully computed")

    def _compute_earth_fixed_range(
        self,
        snapshot: StoreSnapshot,
        frame_name: str,
        start: int,
        stop: int,
        buffer: np.ndarray,
        memo: ChunkMemo[int, RowSpan],
    ) -> None:
        first_chunk = start // DERIVED_CHUNK_SIZE
        last_chunk = (stop - 1) // DERIVED_CHUNK_SIZE
        for chunk_index in range(first_chunk, last_chunk + 1):
            chunk_start = chunk_index * DERIVED_CHUNK_SIZE
            chunk_stop = min(chunk_start + DERIVED_CHUNK_SIZE, snapshot.sample_count)
            tentative = (
                snapshot.status is LoadStatus.LOADING
                and chunk_stop < chunk_start + DERIVED_CHUNK_SIZE
            )

            def compute() -> RowSpan:
                _write_earth_fixed_chunk(
                    snapshot, frame_name, chunk_start, chunk_stop, buffer
                )
                return RowSpan(chunk_start, chunk_stop)

            span = memo.get_or_compute(
                chunk_index,
                compute,
                epoch=snapshot.epoch,
                policy_revision=0,
                tentative=tentative,
            )
            if span.stop < chunk_stop:
                memo.invalidate(chunk_index)
                span = memo.get_or_compute(
                    chunk_index,
                    compute,
                    epoch=snapshot.epoch,
                    policy_revision=0,
                    tentative=tentative,
                )
                if span.stop < chunk_stop:
                    raise RuntimeError("Earth-fixed chunk is not fully computed")


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
) -> tuple[RowSpan, ...]:
    spans = []
    delta_offset = 1 if group == "rtn" else 0
    for segment_start, segment_stop in snapshot.segment_bounds:
        first = max(start, int(segment_start) + delta_offset)
        end = min(stop, int(segment_stop))
        if first >= end:
            continue
        first_in_view = math.ceil((first - start) / stride)
        end_in_view = math.ceil((end - start) / stride)
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
    raw = snapshot.raw
    segments = snapshot.segment_ids
    if group == "kinematics":
        for row in range(start, stop):
            state = raw[row, 1:7]
            output[row, 0] = raw[row, 0]
            output[row, 1] = np.linalg.norm(state[3:6])
            output[row, 2] = np.linalg.norm(state[0:3])
            output[row, 3] = wgs.ecef_to_lla(state[0:3])[2]
        return

    if group == "rtn":
        for row in range(start, stop):
            output[row, 0] = raw[row, 0]
            output[row, 1:] = np.nan
            if row > 0 and segments[row] == segments[row - 1]:
                output[row, 1:] = misc.transform_to_rtn(
                    raw[row, 1:7],
                    raw[row - 1, 1:7],
                )
        return

    for row in range(start, stop):
        state = raw[row, 1:7]
        direction = OrbitSeries._compute_rtn_velocity_direction_vector(state)
        radial, transverse, normal = direction
        pitch = math.atan2(float(radial), float(transverse))
        yaw = math.atan2(float(normal), math.hypot(float(radial), float(transverse)))
        output[row, 0] = raw[row, 0]
        output[row, 1:3] = 0.0
        output[row, 3:6] = (0.0, pitch, yaw)
        output[row, 6:9] = 0.0
        if row == 0 or segments[row] != segments[row - 1]:
            continue

        previous_direction = OrbitSeries._compute_rtn_velocity_direction_vector(
            raw[row - 1, 1:7]
        )
        dot_product = float(np.dot(previous_direction, direction))
        angle_rad = math.acos(float(np.clip(dot_product, -1.0, 1.0)))
        delta_time_s = float(raw[row, 0] - raw[row - 1, 0])
        output[row, 1] = angle_rad
        if delta_time_s > 0.0:
            output[row, 2] = angle_rad / delta_time_s
            previous_pitch = math.atan2(
                float(previous_direction[0]), float(previous_direction[1])
            )
            previous_yaw = math.atan2(
                float(previous_direction[2]),
                math.hypot(float(previous_direction[0]), float(previous_direction[1])),
            )
            output[row, 6:9] = (
                0.0,
                (pitch - previous_pitch) / delta_time_s,
                (yaw - previous_yaw) / delta_time_s,
            )


def _write_earth_fixed_chunk(
    snapshot: StoreSnapshot,
    frame_name: str,
    start: int,
    stop: int,
    output: np.ndarray,
) -> None:
    for row in range(start, stop):
        output[row, 0] = snapshot.raw[row, 0]
        output[row, 1:4] = state_position_to_itrf_m(
            snapshot.raw[row, 1:7],
            frame_name,
            float(snapshot.raw[row, 0]),
        )
