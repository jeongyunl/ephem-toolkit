"""Station-profile tier storage and chunk computation."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from concurrent.futures import CancelledError
from threading import Event
from typing import TYPE_CHECKING, cast

import numpy as np

from ..chunk_memo import ChunkMemo
from ..ground_stations import GroundStation, StationMetrics
from ..station_access import (
    MAX_ACCESS_SAMPLES,
    MAX_SOURCE_SAMPLE_GAP_S,
    MAX_ACCESS_SAMPLE_STEP_S,
)
from .public_types import (
    LoadStatus,
    RowSpan,
    STATION_PROFILE_COLUMNS,
    StoreSnapshot,
    TierNotice,
)
from .internal_types import (
    _StationProfileTier,
    _StationSegmentLayout,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def profile_storage(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    station: GroundStation,
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
    with store._lock:
        if snapshot.epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        tier = store._station_profiles.get(key)
        if tier is not None:
            return tier, None
        layouts: list[_StationSegmentLayout] = []
        base_index = 0
        for raw_start_value, raw_stop_value in snapshot.segment_bounds:
            raw_start, raw_stop = int(raw_start_value), int(raw_stop_value)
            if raw_stop - raw_start < 2:
                empty = _StationProfileTier(
                    station_key,
                    np.empty((0, len(STATION_PROFILE_COLUMNS))),
                    ChunkMemo(),
                )
                return empty, (
                    "Access intervals unavailable: an OEM segment has fewer "
                    "than two samples."
                )
            maximum_source_gap = max(
                (
                    float(snapshot.raw[index + 1, 0] - snapshot.raw[index, 0])
                    for index in range(raw_start, raw_stop - 1)
                ),
                default=0.0,
            )
            if maximum_source_gap > MAX_SOURCE_SAMPLE_GAP_S:
                empty = _StationProfileTier(
                    station_key,
                    np.empty((0, len(STATION_PROFILE_COLUMNS))),
                    ChunkMemo(),
                )
                return empty, (
                    "Access intervals unavailable: OEM sample spacing exceeds "
                    "five minutes."
                )
            start_s = float(snapshot.raw[raw_start, 0])
            end_s = float(snapshot.raw[raw_stop - 1, 0])
            regular_count = max(
                2,
                math.ceil((end_s - start_s) / MAX_ACCESS_SAMPLE_STEP_S) + 1,
            )
            if base_index + regular_count > MAX_ACCESS_SAMPLES:
                empty = _StationProfileTier(
                    station_key,
                    np.empty((0, len(STATION_PROFILE_COLUMNS))),
                    ChunkMemo(),
                )
                return empty, (
                    "Access intervals unavailable: OEM coverage requires too "
                    "many samples."
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
        from .mapped_buffers import _mapped_float_array

        tier = _StationProfileTier(
            station_key,
            _mapped_float_array((base_index, len(STATION_PROFILE_COLUMNS))),
            ChunkMemo(),
            tuple(layouts),
            base_index,
            np.zeros(base_index, dtype=bool),
        )
        store._station_profiles[key] = tier
        return tier, None


def clear_station_profiles(store: OemDataStore) -> None:
    from .store_support import _mapped_buffer_id

    for tier in store._station_profiles.values():
        tier.memo.clear()
        buffer_id = _mapped_buffer_id(tier.buffer)
        for key in tuple(store._chunk_access_order):
            if key[0] == buffer_id:
                store._chunk_access_order.pop(key, None)
                store._chunk_ranges.pop(key, None)
    store._station_profiles.clear()
    store._station_interval_cache.clear()
    store._station_interval_layout_cache.clear()


def compute_profile_ranges(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    station: GroundStation,
    tier: _StationProfileTier,
    ranges: Sequence[tuple[_StationSegmentLayout, int, int]],
    *,
    cancel_event: Event | None,
) -> None:
    from .store_support import (
        _row_spans,
        _station_profile_row_time,
    )
    import ephem_toolkit.play_oem.oem_data_store as public_store

    ready = tier.ready
    if ready is None:
        raise RuntimeError("station profile readiness was not initialized")
    requested_by_chunk: dict[
        int,
        list[tuple[_StationSegmentLayout, int, int]],
    ] = {}
    for layout, first, stop in ranges:
        row_start = layout.base_index + first
        row_stop = layout.base_index + stop
        for chunk_index in range(
            row_start // public_store.DERIVED_CHUNK_SIZE,
            (row_stop - 1) // public_store.DERIVED_CHUNK_SIZE + 1,
        ):
            chunk_start = chunk_index * public_store.DERIVED_CHUNK_SIZE
            chunk_stop = min(
                chunk_start + public_store.DERIVED_CHUNK_SIZE,
                tier.row_count,
            )
            requested_by_chunk.setdefault(chunk_index, []).append(
                (
                    layout,
                    max(row_start, chunk_start),
                    min(row_stop, chunk_stop),
                )
            )

    with store._derived_compute_lock:
        for chunk_index, requested in sorted(requested_by_chunk.items()):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            chunk_start = chunk_index * public_store.DERIVED_CHUNK_SIZE
            chunk_stop = min(
                chunk_start + public_store.DERIVED_CHUNK_SIZE,
                tier.row_count,
            )
            missing = [
                (layout, span)
                for layout, first, stop in requested
                for span in _row_spans(
                    ready,
                    first,
                    stop,
                    ready_value=False,
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
                            layout,
                            row_index - layout.base_index,
                        )
                        state = store.earth_fixed_state_at(snapshot, epoch_s)
                        row = tier.buffer[row_index]
                        row[0] = epoch_s
                        if state.state_m is None:
                            row[1:] = np.nan
                        else:
                            metrics = cast(
                                Callable[
                                    [GroundStation, np.ndarray],
                                    StationMetrics,
                                ],
                                public_store.station_metrics_from_ecef,
                            )(
                                station,
                                state.state_m[:3],
                            )
                            row[1:] = (
                                metrics.azimuth_deg,
                                metrics.elevation_deg,
                                metrics.slant_range_km,
                            )
                    ready[span.first : span.stop] = True
                    store._publish_notice(
                        TierNotice(
                            snapshot.epoch,
                            "station-access",
                            None,
                            station.station_id,
                            span.first,
                            span.stop,
                            (
                                float(tier.buffer[span.first, 0]),
                                float(tier.buffer[span.stop - 1, 0]),
                            ),
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
                    and chunk_stop < chunk_start + public_store.DERIVED_CHUNK_SIZE
                ),
                cancel_event=cancel_event,
            )
