"""Chunk leasing, touch tracking, view creation, and derived-buffer eviction."""

from __future__ import annotations

import math
import mmap
import weakref
from typing import Literal

import numpy as np

from ..chunk_memo import ChunkMemo, ChunkState
from .public_types import (
    EARTH_FIXED_COLUMNS,
    STATION_PROFILE_COLUMNS,
    ColumnGroupView,
    RowSpan,
    _ChunkLease,
)
from .internal_types import (
    _EvictionCandidate,
)


class DerivedBufferManager:
    def __init__(self, store) -> None:
        self.store = store

    def touch_chunks_locked(
        self,
        buffer: np.ndarray,
        first_row: int,
        stop_row: int,
        bounds: tuple[float, float] | None = None,
    ) -> None:
        if first_row >= stop_row:
            return
        from .mapped_buffers import _mapped_buffer_id
        import ephem_toolkit.play_oem.oem_data_store as public_store

        buffer_id = _mapped_buffer_id(buffer)
        first_chunk = first_row // public_store.DERIVED_CHUNK_SIZE
        last_chunk = (stop_row - 1) // public_store.DERIVED_CHUNK_SIZE
        for chunk_index in range(first_chunk, last_chunk + 1):
            key = (buffer_id, chunk_index)
            self.store._buffer_touch_sequence += 1
            self.store._chunk_access_order[key] = self.store._buffer_touch_sequence
            if bounds is not None:
                self.store._chunk_ranges[key] = (bounds,)

    def pin_chunks(self, chunk_keys: tuple[tuple[int, int], ...]) -> None:
        with self.store._lock:
            for key in chunk_keys:
                count = self.store._pinned_chunks.get(key, 0)
                self.store._pinned_chunks[key] = count + 1

    @staticmethod
    def release_chunks(
        store_ref: weakref.ReferenceType,
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

    def make_column_group_view(
        self,
        values: np.ndarray,
        columns: tuple[str, ...],
        segment_bounds: tuple[RowSpan, ...],
        owner_buffer: np.ndarray,
        first_row: int,
        stop_row: int,
    ) -> ColumnGroupView:
        from .mapped_buffers import _mapped_buffer_id
        import ephem_toolkit.play_oem.oem_data_store as public_store

        buffer_id = _mapped_buffer_id(owner_buffer)
        chunk_keys = tuple(
            (buffer_id, chunk_index)
            for chunk_index in range(
                first_row // public_store.DERIVED_CHUNK_SIZE,
                (stop_row - 1) // public_store.DERIVED_CHUNK_SIZE + 1,
            )
        )
        lease = _ChunkLease(self.store, chunk_keys)
        return ColumnGroupView(values, columns, segment_bounds, lease)

    def evict_derived_buffers(self) -> None:
        from .store_support import _mapped_buffer_id, _range_is_active
        import ephem_toolkit.play_oem.oem_data_store as public_store

        store = self.store
        with store._derived_compute_lock, store._lock:
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
                    math.ceil(row_count / public_store.DERIVED_CHUNK_SIZE)
                ):
                    if memo.state(
                        chunk_index,
                        epoch=store._epoch,
                        policy_revision=policy_revision,
                    ) not in (ChunkState.COMPLETE, ChunkState.TENTATIVE):
                        continue
                    chunk_rows = min(
                        public_store.DERIVED_CHUNK_SIZE,
                        row_count - chunk_index * public_store.DERIVED_CHUNK_SIZE,
                    )
                    chunk_key = (buffer_id, chunk_index)
                    candidates.append(
                        _EvictionCandidate(
                            access_order=store._chunk_access_order.get(
                                chunk_key,
                                0,
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
                                chunk_rows * columns * np.dtype(np.float64).itemsize
                            ),
                        )
                    )

            from ..series import _SERIES_COLUMNS

            for group, buffer in store._series_buffers.items():
                add_candidates(
                    "series",
                    buffer,
                    store._series_memos[group],
                    store._series_ready[group],
                    len(buffer),
                    len(_SERIES_COLUMNS[group]),
                    0,
                )
            if store._earth_fixed_buffer is not None:
                add_candidates(
                    "earth-fixed",
                    store._earth_fixed_buffer,
                    store._earth_fixed_memo,
                    store._earth_fixed_ready,
                    len(store._earth_fixed_buffer),
                    len(EARTH_FIXED_COLUMNS),
                    0,
                )
            for tier in store._station_profiles.values():
                add_candidates(
                    "station-access",
                    tier.buffer,
                    tier.memo,
                    tier.ready,
                    tier.row_count,
                    len(STATION_PROFILE_COLUMNS),
                    store._policy_revision,
                )

            resident_bytes = sum(candidate.size_bytes for candidate in candidates)
            resident_bytes += sum(
                sum(group.values.nbytes for group in query.value)
                for query in store._ground_track_cache.values()
            )
            if resident_bytes <= store._derived_memory_budget_bytes:
                return

            while (
                store._ground_track_cache
                and resident_bytes > store._derived_memory_budget_bytes
            ):
                _, evicted = store._ground_track_cache.popitem(last=False)
                resident_bytes -= sum(group.values.nbytes for group in evicted.value)
            if resident_bytes <= store._derived_memory_budget_bytes:
                return

            advice = getattr(
                mmap,
                "MADV_FREE",
                getattr(mmap, "MADV_DONTNEED", None),
            )
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
                if resident_bytes <= store._derived_memory_budget_bytes:
                    break
                chunk_key = (candidate.buffer_id, candidate.chunk_index)
                if store._pinned_chunks.get(chunk_key, 0):
                    continue
                if any(
                    _range_is_active(bounds, store._range_hint)
                    for bounds in store._chunk_ranges.get(chunk_key, ())
                ):
                    continue

                chunk_start = candidate.chunk_index * public_store.DERIVED_CHUNK_SIZE
                chunk_stop = min(
                    chunk_start + public_store.DERIVED_CHUNK_SIZE,
                    candidate.row_count,
                )

                def release_chunk() -> None:
                    public_store._madvise_chunk(
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
                    epoch=store._epoch,
                    policy_revision=(
                        store._policy_revision
                        if candidate.kind == "station-access"
                        else 0
                    ),
                ):
                    continue
                if candidate.kind == "station-access":
                    store._station_interval_cache.clear()
                store._chunk_access_order.pop(chunk_key, None)
                store._chunk_ranges.pop(chunk_key, None)
                resident_bytes -= candidate.size_bytes
