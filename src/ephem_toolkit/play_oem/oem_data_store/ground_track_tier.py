"""Ground-track query and cache implementation."""

from __future__ import annotations

from concurrent.futures import CancelledError
from threading import Event
from typing import TYPE_CHECKING

import numpy as np

from ..ground_track import (
    GroundTrackCoordinates,
    GroundTrackPreparationError,
    _ecef_to_wgs84_geodetic,
    split_ground_track_runs,
)
from .public_types import (
    GROUND_TRACK_COLUMNS,
    ColumnGroupView,
    GroundTrackGroups,
    QueryRequest,
    RowSpan,
    StoreQuery,
    StoreSnapshot,
    TierNotice,
    TimeCoverage,
)
from .store_support import (
    _earth_centered_frame_name,
    _normalize_longitude,
    _time_coverage,
    _validate_nonnegative_finite,
    _validate_time_bounds,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def query_ground_track(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    bounds_s: tuple[float, float],
    margin_s: float = 0.0,
    center_longitude_deg: float = 0.0,
    *,
    wait: bool = False,
    cancel_event: Event | None = None,
) -> StoreQuery[GroundTrackGroups]:
    bounds = _validate_time_bounds(bounds_s)
    margin = _validate_nonnegative_finite(margin_s, "margin_s")
    center = _normalize_longitude(center_longitude_deg)
    store._validate_snapshot_epoch(snapshot)
    if not isinstance(wait, bool):
        raise ValueError("wait must be a boolean")
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()

    key = (
        snapshot.epoch,
        snapshot.revision,
        bounds,
        margin,
        center,
    )
    with store._lock:
        cached = store._ground_track_cache.get(key)
        if cached is not None:
            store._ground_track_cache.move_to_end(key)
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
        store.prefetch(
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

    earth_fixed = store.earth_fixed_positions(
        snapshot,
        bounds,
        margin,
        wait=True,
        _cancel_event=cancel_event,
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
    if result.coverage.complete and result_bytes <= store._derived_memory_budget_bytes:
        with store._lock:
            cached_bytes = sum(
                sum(group.values.nbytes for group in cached_result.value)
                for cached_result in store._ground_track_cache.values()
            )
            while (
                store._ground_track_cache
                and cached_bytes + result_bytes > store._derived_memory_budget_bytes
            ):
                _, evicted = store._ground_track_cache.popitem(last=False)
                cached_bytes -= sum(group.values.nbytes for group in evicted.value)
            store._ground_track_cache[key] = result
            store._ground_track_cache.move_to_end(key)
            while len(store._ground_track_cache) > 4:
                store._ground_track_cache.popitem(last=False)
        store._evict_derived_buffers()

    expanded_bounds = (bounds[0] - margin, bounds[1] + margin)
    first_row = int(
        np.searchsorted(
            snapshot.raw[:, 0],
            expanded_bounds[0],
            side="left",
        )
    )
    stop_row = int(
        np.searchsorted(
            snapshot.raw[:, 0],
            expanded_bounds[1],
            side="right",
        )
    )
    if first_row < stop_row:
        store._publish_notice(
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
