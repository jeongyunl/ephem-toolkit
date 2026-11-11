"""Test helpers for cursors backed by committed OEM store samples."""

from __future__ import annotations

from typing import Sequence
import weakref

import numpy as np

from ephem_toolkit.play_oem.cursor import StoreCursor
from ephem_toolkit.play_oem.oem_data_store import (
    InterpolationPolicy,
    OemDataStore,
)


def make_store_cursor(
    timestamps_s: Sequence[float],
    states_m: Sequence[np.ndarray],
    *,
    interpolation: str | None = None,
    interpolation_degree: int | None = None,
    segment_ids: Sequence[int] | None = None,
) -> tuple[OemDataStore, StoreCursor]:
    """Create a cursor over committed samples and close its store on collection."""
    timestamps = np.asarray(timestamps_s, dtype=float)
    states = np.asarray(states_m, dtype=float)
    segments = np.asarray(
        segment_ids if segment_ids is not None else np.zeros(len(timestamps)),
        dtype=int,
    )
    store = OemDataStore()
    epoch = store.begin(len(timestamps) + 1)
    reservation = store.reserve(len(timestamps), epoch=epoch)
    reservation.raw[:, 0] = timestamps
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = segments
    store.commit(reservation, len(timestamps))
    if interpolation is not None:
        store.set_interpolation(
            InterpolationPolicy(interpolation.lower(), interpolation_degree)
        )
    cursor = StoreCursor(store, store.snapshot())
    weakref.finalize(cursor, store.close)
    return store, cursor


def append_store_samples(
    store: OemDataStore,
    cursor: StoreCursor,
    timestamps_s: Sequence[float],
    states_m: Sequence[np.ndarray],
    segment_ids: Sequence[int],
) -> None:
    """Commit more raw samples and refresh their cursor."""
    timestamps = np.asarray(timestamps_s, dtype=float)
    states = np.asarray(states_m, dtype=float)
    segments = np.asarray(segment_ids, dtype=int)
    reservation = store.reserve(len(timestamps), epoch=store.epoch)
    reservation.raw[:, 0] = timestamps
    reservation.raw[:, 1:7] = states
    reservation.segment_ids[:] = segments
    store.commit(reservation, len(timestamps))
    cursor.refresh(store.snapshot())
