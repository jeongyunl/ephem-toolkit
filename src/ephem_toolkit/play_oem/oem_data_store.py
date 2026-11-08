"""Store-owned raw OEM storage with atomic prefix publication."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
from threading import Event, RLock
from typing import Generic, Literal, TypeVar, Union, TYPE_CHECKING

import numpy as np

from ephem_toolkit.core.ccsds.odm import ODM_MAX_LINE_LENGTH
from .time_unit import TimeUnit

if TYPE_CHECKING:
    from .ground_stations import GroundStation
    from .station_access import AccessInterval


T = TypeVar("T")
TimeBounds = tuple[float, float]
SeriesGroupName = Literal["kinematics", "rtn", "direction-rates"]
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
    """Raw tier of the planned store; each epoch has fixed-capacity buffers.

    A single writer fills a reservation and must not mutate it during commit or
    retain writable aliases after commit or abort. Snapshots expose only committed
    rows. Derived tiers and lazy query evaluation are not implemented yet.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._epoch = 0
        self._revision = 0
        self._policy_revision = 0
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
