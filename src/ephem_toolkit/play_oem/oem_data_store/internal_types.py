"""Internal scheduling, profile, lease, and eviction types."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from threading import Event
from typing import Literal, TYPE_CHECKING

import numpy as np

from ..chunk_memo import ChunkMemo
from ..cursor import CursorState
from .public_types import (
    InterpolationPolicy,
    QueryRequest,
    RowSpan,
    StoreSnapshot,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


@dataclass(frozen=True)
class _EvictionCandidate:
    access_order: int
    """Last access sequence."""
    buffer_id: int
    """Derived buffer mapping identifier."""
    kind: Literal["series", "earth-fixed", "station-access"]
    """Derived tier kind."""
    chunk_index: int
    """Chunk index within the tier buffer."""
    buffer: np.ndarray
    """Owning mapped buffer."""
    memo: ChunkMemo[int, RowSpan]
    """Chunk memo controlling readiness."""
    ready: np.ndarray
    """Per-row readiness buffer."""
    row_count: int
    """Total tier row count."""
    columns: int
    """Float column count."""
    size_bytes: int
    """Resident size of the chunk."""


class _PrefetchFuture(Future[None]):
    """Cancellable future carrying a derived-work cancellation event."""

    def __init__(self) -> None:
        super().__init__()
        self.cancel_event = Event()

    def cancel(self) -> bool:
        self.cancel_event.set()
        return super().cancel()


@dataclass(order=True)
class _ScheduledWork:
    priority: int
    """Queue priority."""
    sequence: int
    """Stable FIFO sequence."""
    key: tuple[int, int, int, QueryRequest] = field(compare=False)
    """Deduplication key."""
    snapshot: StoreSnapshot = field(compare=False)
    """Store snapshot for the work."""
    request: QueryRequest = field(compare=False)
    """Derived query request."""
    future: _PrefetchFuture = field(compare=False)
    """Caller future."""
    generation: int = field(compare=False)
    """Range-hint generation."""


@dataclass(frozen=True)
class _StationSegmentLayout:
    segment_id: int
    """OEM segment identifier."""
    raw_start: int
    """First raw row."""
    raw_stop: int
    """Stopping raw row."""
    start_s: float
    """First segment timestamp."""
    end_s: float
    """Last segment timestamp."""
    regular_count: int
    """Number of regularly spaced profile rows."""
    row_count: int
    """Number of profile rows."""
    base_index: int
    """First profile row in the tier buffer."""


@dataclass
class _StationProfileTier:
    station_key: tuple[str, float, float, float]
    """Station cache key."""
    buffer: np.ndarray
    """Mapped station profile buffer."""
    memo: ChunkMemo[int, RowSpan]
    """Profile chunk memo."""
    layouts: tuple[_StationSegmentLayout, ...] = ()
    """Segment layouts."""
    row_count: int = 0
    """Profile row count."""
    ready: np.ndarray | None = None
    """Per-row readiness buffer."""


class _StoreStationCursor:
    """Station cursor delegating lookups to a store snapshot."""

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
        """Resolve one cursor state at the requested timestamp."""
        return self.store.earth_fixed_state_at(self.snapshot, t_s)
