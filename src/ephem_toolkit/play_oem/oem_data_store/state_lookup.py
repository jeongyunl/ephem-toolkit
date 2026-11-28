"""Exact and interpolated raw OEM state lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..cursor import CursorState, CursorStatus
from ephem_toolkit.core import wgs
from .public_types import StoreSnapshot
from .store_support import (
    _unavailable_state,
    _validate_query_time,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def state_at(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    t_s: float,
    *,
    earth_fixed: bool = False,
) -> CursorState:
    query_time = _validate_query_time(t_s)
    with store._lock:
        if snapshot.epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        if snapshot.policy_revision != store._policy_revision:
            raise RuntimeError("interpolation policy has changed")
        interpolator = store._state_interpolator
        interpolation_policy = store._interpolation_policy
    earth_fixed_cursor_key = None
    if earth_fixed:
        earth_fixed_cursor_key = (
            snapshot.epoch,
            snapshot.policy_revision,
            str(interpolation_policy.method),
            0 if interpolation_policy.degree is None else int(interpolation_policy.degree),
            query_time,
        )
        with store._lock:
            cached = store._earth_fixed_cursor_cache.get(earth_fixed_cursor_key)
            if cached is not None:
                store._earth_fixed_cursor_cache.move_to_end(
                    earth_fixed_cursor_key
                )
                return cached
    frame_name = None
    if earth_fixed:
        from .frame_support import earth_centered_frame_name

        frame_name = earth_centered_frame_name(snapshot, "Earth-fixed state")
        if frame_name is None:
            return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)

    def sample(index: int) -> np.ndarray:
        if frame_name is None:
            return raw[index, 1:7]
        from ..ground_track import (
            _state_to_itrf_m_normalized,
            normalize_conversion_frame_name,
        )

        key = (snapshot.epoch, frame_name, index)
        with store._lock:
            if snapshot.epoch != store._epoch:
                raise RuntimeError("store epoch has changed")
            if snapshot.policy_revision != store._policy_revision:
                raise RuntimeError("interpolation policy has changed")
            cached = store._earth_fixed_state_cache.get(key)
            if cached is not None:
                store._earth_fixed_state_cache.move_to_end(key)
                return cached
            converted = _state_to_itrf_m_normalized(
                raw[index, 1:7],
                normalize_conversion_frame_name(frame_name),
                float(raw[index, 0]),
                source_frame_name=frame_name,
            )
            store._earth_fixed_state_cache[key] = converted
            if len(store._earth_fixed_state_cache) > 8192:
                store._earth_fixed_state_cache.popitem(last=False)
            return converted

    if snapshot.sample_count == 0:
        return _unavailable_state(
            query_time,
            CursorStatus.UNAVAILABLE,
        )

    raw = snapshot.raw
    times = raw[:, 0]
    if query_time < times[0] or query_time > times[-1]:
        return _unavailable_state(
            query_time,
            CursorStatus.OUT_OF_RANGE,
        )

    upper_index = int(np.searchsorted(times, query_time))
    if upper_index < times.size and times[upper_index] == query_time:
        state_m = sample(upper_index).copy()
        status = CursorStatus.EXACT_SAMPLE
        segment_id = int(snapshot.segment_ids[upper_index])
    else:
        lower_index = upper_index - 1
        segment_id = int(snapshot.segment_ids[lower_index])
        if segment_id != snapshot.segment_ids[upper_index]:
            return _unavailable_state(
                query_time,
                CursorStatus.GAP,
            )
        if earth_fixed:
            segment_start = int(
                np.searchsorted(snapshot.segment_ids, segment_id, side="left")
            )
            segment_stop = int(
                np.searchsorted(snapshot.segment_ids, segment_id, side="right")
            )
            count = min(
                segment_stop - segment_start, max(2, interpolator.required_points)
            )
            start = segment_start + max(
                0,
                min(
                    upper_index - segment_start - count // 2,
                    segment_stop - segment_start - count,
                ),
            )
            stop = start + count
            state_m = interpolator.interpolate_view(
                times[start:stop],
                np.stack([sample(i) for i in range(start, stop)]),
                query_time,
                snapshot.segment_ids[start:stop],
            )
        else:
            state_m = interpolator.interpolate_view(
                times,
                raw[:, 1:7],
                query_time,
                snapshot.segment_ids,
            )
        if state_m is None:
            return _unavailable_state(
                query_time,
                CursorStatus.UNAVAILABLE,
            )
        if state_m.shape != (6,) or not np.all(np.isfinite(state_m)):
            raise ValueError("interpolator returned an invalid Cartesian state")
        state_m = state_m.copy()
        status = CursorStatus.INTERPOLATED

    position_km = state_m[:3] * 0.001
    velocity_km_s = state_m[3:] * 0.001
    result = CursorState(
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
    if earth_fixed_cursor_key is not None:
        with store._lock:
            if (
                snapshot.epoch == store._epoch
                and snapshot.policy_revision == store._policy_revision
            ):
                store._earth_fixed_cursor_cache[
                    earth_fixed_cursor_key
                ] = result
                if len(store._earth_fixed_cursor_cache) > 8192:
                    store._earth_fixed_cursor_cache.popitem(last=False)
    return result
