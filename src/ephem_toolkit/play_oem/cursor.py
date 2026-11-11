"""Direction-independent state lookup for OEM playback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .oem_data_store import OemDataStore, StoreSnapshot


class CursorStatus(str, Enum):
    """Resolution status for a cursor time."""

    EXACT_SAMPLE = "exact_sample"
    INTERPOLATED = "interpolated"
    OUT_OF_RANGE = "out_of_range"
    UNAVAILABLE = "unavailable"
    GAP = "gap"


@dataclass(frozen=True)
class CursorState:
    """State and derived values resolved at one OEM timeline time."""

    t: float
    state_m: np.ndarray | None
    r_km: np.ndarray | None
    v_kms: np.ndarray | None
    speed: float | None
    altitude: float | None
    distance: float | None
    status: CursorStatus
    segment_id: int | None = None


class StoreCursor:
    """Resolve point queries over a store snapshot or an inert empty state."""

    def __init__(
        self,
        store: OemDataStore | None = None,
        snapshot: StoreSnapshot | None = None,
    ) -> None:
        if store is None and snapshot is None:
            self._store = None
            self._snapshot = None
            return
        if store is None or snapshot is None:
            raise ValueError("store and snapshot must either both be set or both be empty")
        if snapshot.epoch != store.epoch:
            raise RuntimeError("store epoch has changed")
        self._store = store
        self._snapshot = snapshot

    @classmethod
    def empty(cls) -> StoreCursor:
        """Create an inert cursor for the app before an OEM store is installed."""
        return cls()

    def is_bound_to(self, store: OemDataStore) -> bool:
        """Return whether this cursor is backed by ``store``."""
        return self._store is store and self._snapshot is not None

    @property
    def t_start(self) -> float:
        if self._snapshot is None:
            return 0.0
        if self._snapshot.sample_count == 0:
            raise ValueError("store snapshot has no samples")
        return float(self._snapshot.raw[0, 0])

    @property
    def t_end(self) -> float:
        if self._snapshot is None:
            return 0.0
        if self._snapshot.sample_count == 0:
            raise ValueError("store snapshot has no samples")
        return float(self._snapshot.raw[-1, 0])

    @property
    def timestamps_s(self) -> np.ndarray:
        """Return the snapshot's read-only timestamps without copying them."""
        if self._snapshot is None:
            values = np.empty(0, dtype=float)
            values.setflags(write=False)
            return values
        return self._snapshot.raw[:, 0]

    @property
    def states_m(self) -> np.ndarray:
        """Return a read-only strided view of the snapshot's raw SI states."""
        if self._snapshot is None:
            values = np.empty((0, 6), dtype=float)
            values.setflags(write=False)
            return values
        return self._snapshot.raw[:, 1:7]

    @property
    def segment_ids(self) -> np.ndarray:
        """Return the snapshot's read-only segment IDs."""
        if self._snapshot is None:
            values = np.empty(0, dtype=int)
            values.setflags(write=False)
            return values
        return self._snapshot.segment_ids

    def refresh(self, snapshot: StoreSnapshot) -> None:
        """Advance to a newer committed prefix of the same store epoch."""
        if self._snapshot is None:
            raise RuntimeError("empty cursor must be replaced with a store-backed cursor")
        if snapshot.epoch != self._snapshot.epoch:
            raise RuntimeError("store epoch has changed")
        if snapshot.sample_count < self._snapshot.sample_count:
            raise ValueError("store snapshot cannot move backwards")
        self._snapshot = snapshot

    def set_interpolation(
        self, interpolation: str | None, interpolation_degree: int | None
    ) -> None:
        """Update the store policy used by subsequent state queries."""
        if self._store is None or self._snapshot is None:
            raise RuntimeError("cannot set interpolation on an empty cursor")
        from .oem_data_store import InterpolationPolicy

        self._store.set_interpolation(
            InterpolationPolicy(interpolation or "linear", interpolation_degree)
        )
        self.refresh(self._store.snapshot())

    def lookup(self, t: float) -> CursorState:
        """Resolve a point query against the currently bound store snapshot."""
        if self._snapshot is None:
            query_time = _validate_query_time(t)
            return CursorState(
                t=query_time,
                state_m=None,
                r_km=None,
                v_kms=None,
                speed=None,
                altitude=None,
                distance=None,
                status=CursorStatus.UNAVAILABLE,
            )
        if self._store is None:
            raise RuntimeError("cursor snapshot has no backing store")
        return self._store.state_at(self._snapshot, t)


def _validate_query_time(t: float) -> float:
    if isinstance(t, bool):
        raise ValueError("query time must be a finite number")
    try:
        query_time = float(t)
    except (TypeError, ValueError) as error:
        raise ValueError("query time must be a finite number") from error
    if not math.isfinite(query_time):
        raise ValueError("query time must be a finite number")
    return query_time
