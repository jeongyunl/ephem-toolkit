"""Footprint query caching and computation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..cursor import CursorStatus
from ..ground_footprints import GroundFootprints, compute_ground_footprints
from ..ground_track import state_position_to_itrf_m
from .public_types import StoreSnapshot
from .store_support import (
    _earth_centered_frame_name,
    _validate_elevation_threshold,
    _validate_query_time,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def query_footprints(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    t_s: float,
    min_elevation_deg: float,
) -> GroundFootprints | None:
    store._validate_snapshot_epoch(snapshot)
    query_time = _validate_query_time(t_s)
    minimum_elevation = _validate_elevation_threshold(min_elevation_deg)
    frame_name = _earth_centered_frame_name(
        snapshot,
        "Footprints",
    )
    if frame_name is None:
        return None
    state = store.state_at(snapshot, query_time)
    if (
        state.status
        not in (
            CursorStatus.EXACT_SAMPLE,
            CursorStatus.INTERPOLATED,
        )
        or state.state_m is None
    ):
        return None
    position = state_position_to_itrf_m(
        state.state_m,
        frame_name,
        query_time,
    )
    cache_key = (
        snapshot.epoch,
        query_time,
        tuple(float(value) for value in position),
        minimum_elevation,
    )
    with store._lock:
        cached = store._footprint_cache.get(cache_key)
        if cached is not None:
            store._footprint_cache.move_to_end(cache_key)
            return cached
    result = compute_ground_footprints(
        position,
        minimum_elevation,
    )
    with store._lock:
        store._footprint_cache[cache_key] = result
        store._footprint_cache.move_to_end(cache_key)
        while len(store._footprint_cache) > 32:
            store._footprint_cache.popitem(last=False)
    return result
