"""Public value types for Play-OEM OEM data storage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Literal, TYPE_CHECKING, TypeVar, Union
import weakref

import numpy as np

from ..ground_stations import GroundStation
from ..series import SeriesGroupName
from ..station_access import AccessInterval
from ..time_unit import TimeUnit

if TYPE_CHECKING:
    from .data_store import OemDataStore

T = TypeVar("T")
TimeBounds = tuple[float, float]
DERIVED_CHUNK_SIZE: int = 4096
"""Number of raw rows in one derived-data mmap chunk."""
EARTH_FIXED_COLUMNS: tuple[str, ...] = ("t", "x_itrf", "y_itrf", "z_itrf")
"""Column names for Earth-fixed Cartesian position data."""
GROUND_TRACK_COLUMNS: tuple[str, ...] = ("t", "longitude", "latitude")
"""Column names for ground-track longitude and latitude data."""
STATION_PROFILE_COLUMNS: tuple[str, ...] = (
    "t",
    "azimuth_deg",
    "elevation_deg",
    "range_km",
)
"""Column names for station look-angle profile data."""
TierName = Literal[
    "series",
    "earth-fixed",
    "ground-track",
    "station-access",
    "footprints",
]
"""Names of the store-derived data tiers."""


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
    """OEM header field entries."""
    meta: tuple[tuple[str, object], ...] = ()
    """OEM metadata field entries."""


@dataclass(frozen=True)
class InterpolationPolicy:
    """Interpolation method and optional degree for point-state queries."""

    method: str = "linear"
    """Interpolation method name."""
    degree: int | None = None
    """Optional interpolation polynomial degree."""

    def __post_init__(self) -> None:
        if not isinstance(self.method, str):
            raise ValueError("interpolation method must be a string")
        object.__setattr__(
            self,
            "method",
            self.method.strip().lower() or "linear",
        )
        if self.degree is not None and (
            isinstance(self.degree, bool)
            or not isinstance(self.degree, int)
            or self.degree < 0
        ):
            raise ValueError("interpolation degree must be a non-negative integer")


@dataclass(frozen=True)
class TimeCoverage:
    """Requested bounds and covered spans; None means no effective query range."""

    requested_s: TimeBounds | None
    """Requested time bounds."""
    covered_s: tuple[TimeBounds, ...]
    """Time spans covered by available data."""
    complete: bool
    """Whether the requested range is completely available."""


@dataclass(frozen=True)
class StoreQuery(Generic[T]):
    """A query result stamped with the store and policy revision it used."""

    epoch: int
    """Owning store epoch."""
    revision: int
    """Owning store data revision."""
    policy_revision: int
    """Owning store derived-policy revision."""
    value: T
    """Query result value."""
    coverage: TimeCoverage
    """Available coverage for the requested range."""


@dataclass(frozen=True)
class RowSpan:
    """Half-open row-index span in one tier."""

    first: int
    """First row index, inclusive."""
    stop: int
    """Stopping row index, exclusive."""


@dataclass(frozen=True)
class QueryRequest:
    """Request for a lazy derived-tier range."""

    tier: TierName
    """Requested derived tier."""
    bounds_s: TimeBounds
    """Requested time bounds."""
    station: GroundStation | None = None
    """Station for station-access requests."""
    series_groups: tuple[SeriesGroupName, ...] = ()
    """Requested series groups."""
    max_samples: int | None = None
    """Maximum requested output sample count."""
    minimum_elevation_deg: float | None = None
    """Minimum access elevation."""
    margin_s: float = 0.0
    """Time margin around the request."""
    center_longitude_deg: float = 0.0
    """Ground-track map center longitude."""


@dataclass(frozen=True)
class RangeHint:
    """Current plot and playback interest used to prioritize derived work."""

    plot: TimeBounds | None
    """Current plot viewport."""
    playback: TimeBounds
    """Current playback range."""
    now_s: float
    """Current playback time."""
    dragging: bool = False
    """Whether the plot viewport is being dragged."""

    def __post_init__(self) -> None:
        from .store_support import _validate_query_time, _validate_time_bounds

        if self.plot is not None:
            object.__setattr__(
                self,
                "plot",
                _validate_time_bounds(self.plot),
            )
        object.__setattr__(
            self,
            "playback",
            _validate_time_bounds(self.playback),
        )
        object.__setattr__(
            self,
            "now_s",
            _validate_query_time(self.now_s),
        )
        if not isinstance(self.dragging, bool):
            raise ValueError("dragging must be a boolean")


@dataclass(frozen=True)
class TierNotice:
    """Completed row range in a derived tier."""

    epoch: int
    """Owning store epoch."""
    tier: TierName
    """Derived tier name."""
    group: SeriesGroupName | None
    """Series group, if applicable."""
    station_id: str | None
    """Station identifier, if applicable."""
    first_row: int
    """First completed row."""
    stop_row: int
    """Stopping completed row."""


@dataclass(frozen=True)
class AppendNotice:
    """Newly committed raw rows in one store epoch."""

    epoch: int
    """Owning store epoch."""
    revision: int
    """Store revision after append."""
    first_new_index: int
    """First newly committed raw row."""
    sample_count: int
    """Committed sample count after append."""
    time_span_s: TimeBounds
    """Time span covered by appended rows."""

    @property
    def start_s(self) -> float:
        """First appended timestamp."""
        return self.time_span_s[0]

    @property
    def end_s(self) -> float:
        """Last appended timestamp."""
        return self.time_span_s[1]


@dataclass(frozen=True)
class ResetNotice:
    """Invalidation of the previously active store epoch."""

    epoch: int
    """Reset epoch identifier."""


StoreNotice = Union[AppendNotice, ResetNotice, TierNotice]


@dataclass(frozen=True)
class StoreSnapshot:
    """Immutable views of one committed raw prefix and its store revisions."""

    epoch: int
    """Owning store epoch."""
    revision: int
    """Owning store data revision."""
    policy_revision: int
    """Owning interpolation-policy revision."""
    sample_count: int
    """Number of committed samples."""
    metadata: OemMetadata
    """OEM metadata."""
    time_unit: TimeUnit
    """Normalized snapshot time unit."""
    raw: np.ndarray
    """Read-only raw Cartesian state buffer."""
    segment_ids: np.ndarray
    """Read-only segment identifier buffer."""
    segment_bounds: np.ndarray
    """Read-only segment row bounds."""
    max_within_segment_gap_s: float
    """Largest observed gap within a segment."""
    status: LoadStatus
    """Current epoch lifecycle status."""
    failure: str | None
    """Current epoch failure description."""

    @property
    def header(self) -> tuple[tuple[str, object], ...]:
        """OEM header field entries."""
        return self.metadata.header

    @property
    def meta(self) -> tuple[tuple[str, object], ...]:
        """OEM metadata field entries."""
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
    """Exclusive unpublished suffix; writer views become read-only after close."""

    def __init__(
        self,
        epoch: int,
        first_index: int,
        raw: np.ndarray,
        segment_ids: np.ndarray,
    ) -> None:
        self.epoch = epoch
        self.first_index = first_index
        self.raw = raw
        self.segment_ids = segment_ids

    def _close(self) -> None:
        self.raw.setflags(write=False)
        self.segment_ids.setflags(write=False)


class _LeasedArray(np.ndarray):
    """NumPy view retaining the chunk lease until all views are released."""

    def __array_finalize__(self, source: object) -> None:
        self._chunk_lease = (
            getattr(source, "_chunk_lease", None)
            if isinstance(source, np.ndarray) and np.may_share_memory(self, source)
            else None
        )


class _ChunkLease:
    """Lease pinning one or more derived buffer chunks."""

    def __init__(
        self,
        store: OemDataStore,
        chunk_keys: tuple[tuple[int, int], ...],
    ) -> None:
        from .derived_buffer_manager import DerivedBufferManager

        self.chunk_keys = chunk_keys
        store._pin_chunks(chunk_keys)
        weakref.finalize(
            self,
            DerivedBufferManager.release_chunks,
            weakref.ref(store),
            chunk_keys,
        )


@dataclass(frozen=True, eq=False)
class ColumnGroupView:
    """Read-only view of a store-owned derived column group."""

    values: np.ndarray
    """Read-only derived values."""
    columns: tuple[str, ...]
    """Derived column names."""
    segment_bounds: tuple[RowSpan, ...]
    """Segment-relative row bounds."""
    lease: _ChunkLease | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    """Chunk lease retaining derived buffers."""

    def __post_init__(self) -> None:
        if self.values.ndim != 2 or self.values.shape[1] != len(self.columns):
            raise ValueError("column-group shape must match its column names")
        lease = self.lease or getattr(
            self.values,
            "_chunk_lease",
            None,
        )
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
        """Return a read-only two-column view without copying."""
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
        pair = self.values[
            rows,
            lower_index : upper_index + 1 : step,
        ]
        if first_index > second_index:
            pair = pair[:, ::-1]
        return pair


@dataclass(frozen=True)
class LookAngleProfileView:
    """Station look-angle columns shared by profile and pass views."""

    group: ColumnGroupView
    """Station look-angle column group."""


@dataclass(frozen=True)
class StationAccessView:
    """Window-specific station intervals backed by shared profile views."""

    station: GroundStation
    """Selected ground station."""
    profiles: tuple[LookAngleProfileView, ...]
    """Look-angle profile views."""
    intervals: tuple[AccessInterval, ...]
    """Station access intervals."""
    limitation: str | None
    """Optional interval limitation description."""


SeriesGroups = Mapping[SeriesGroupName, tuple[ColumnGroupView, ...]]
GroundTrackGroups = tuple[ColumnGroupView, ...]
EarthFixedPositions = tuple[ColumnGroupView, ...]
