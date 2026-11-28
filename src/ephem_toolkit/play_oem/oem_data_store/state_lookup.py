"""Exact and interpolated raw OEM state lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ephem_toolkit.core import wgs

from ..cursor import CursorState, CursorStatus
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
        raw = snapshot.raw
        if snapshot.sample_count == 0:
            return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)
        times = raw[:, 0]
        if query_time < times[0] or query_time > times[-1]:
            return _unavailable_state(query_time, CursorStatus.OUT_OF_RANGE)
        upper_index = int(np.searchsorted(times, query_time))
        if upper_index < times.size and times[upper_index] == query_time:
            status = CursorStatus.EXACT_SAMPLE
            segment_id = int(snapshot.segment_ids[upper_index])
        else:
            lower_index = upper_index - 1
            if lower_index < 0 or upper_index >= times.size:
                return _unavailable_state(query_time, CursorStatus.OUT_OF_RANGE)
            segment_id = int(snapshot.segment_ids[lower_index])
            if segment_id != snapshot.segment_ids[upper_index]:
                return _unavailable_state(query_time, CursorStatus.GAP)
            status = CursorStatus.INTERPOLATED
        state_m = earth_fixed_states_at(
            store,
            snapshot,
            np.asarray([query_time], dtype=float),
        )[0].copy()
        if not np.isfinite(state_m).all():
            return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)
    else:
        earth_fixed_cursor_key = None
        if snapshot.sample_count == 0:
            return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)
        raw = snapshot.raw
        times = raw[:, 0]
        if query_time < times[0] or query_time > times[-1]:
            return _unavailable_state(query_time, CursorStatus.OUT_OF_RANGE)
        upper_index = int(np.searchsorted(times, query_time))
        if upper_index < times.size and times[upper_index] == query_time:
            state_m = raw[upper_index, 1:7].copy()
            status = CursorStatus.EXACT_SAMPLE
            segment_id = int(snapshot.segment_ids[upper_index])
        else:
            lower_index = upper_index - 1
            if lower_index < 0 or upper_index >= times.size:
                return _unavailable_state(query_time, CursorStatus.OUT_OF_RANGE)
            segment_id = int(snapshot.segment_ids[lower_index])
            if segment_id != snapshot.segment_ids[upper_index]:
                return _unavailable_state(query_time, CursorStatus.GAP)
            state_m = interpolator.interpolate_view(
                times,
                raw[:, 1:7],
                query_time,
                snapshot.segment_ids,
            )
            if state_m is None:
                return _unavailable_state(query_time, CursorStatus.UNAVAILABLE)
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


def earth_fixed_states_at(
    store: OemDataStore,
    snapshot: StoreSnapshot,
    query_times_s: np.ndarray,
) -> np.ndarray:
    """Resolve many Earth-fixed states while sharing sample conversions."""
    queries = np.asarray(query_times_s, dtype=float)
    if queries.ndim != 1:
        raise ValueError("Earth-fixed query times must be one-dimensional")
    if not np.isfinite(queries).all():
        raise ValueError("Earth-fixed query times must be finite")
    with store._lock:
        if snapshot.epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        if snapshot.policy_revision != store._policy_revision:
            raise RuntimeError("interpolation policy has changed")
        interpolator = store._state_interpolator
        interpolation_policy = store._interpolation_policy

    states = np.full((len(queries), 6), np.nan, dtype=float)
    if snapshot.sample_count == 0:
        return states

    from ..ground_track import (
        states_to_itrf_m_batch,
    )
    from .frame_support import earth_centered_frame_name

    frame_name = earth_centered_frame_name(snapshot, "Earth-fixed states")
    if frame_name is None:
        return states

    raw = snapshot.raw
    times = raw[:, 0]
    if len(queries) == 0:
        return states

    upper_indices = np.searchsorted(times, queries, side="left")
    exact = (
        (upper_indices < times.size)
        & (upper_indices >= 0)
        & (times[np.clip(upper_indices, 0, times.size - 1)] == queries)
    )
    exact_indices = upper_indices[exact]
    if exact_indices.size:
        unique_exact_indices = np.unique(exact_indices)
        exact_states = {}
        uncached_exact_indices = []
        for index in unique_exact_indices:
            key = (snapshot.epoch, frame_name, int(index))
            with store._lock:
                converted = store._earth_fixed_state_cache.get(key)
            if converted is not None:
                exact_states[int(index)] = converted
            else:
                uncached_exact_indices.append(int(index))
        if uncached_exact_indices:
            uncached_array = np.asarray(uncached_exact_indices, dtype=np.intp)
            batch_converted = states_to_itrf_m_batch(
                raw[uncached_array, 1:7],
                frame_name,
                raw[uncached_array, 0],
            )
            for index, converted in zip(uncached_exact_indices, batch_converted):
                key = (snapshot.epoch, frame_name, index)
                with store._lock:
                    store._earth_fixed_state_cache[key] = converted
                    if len(store._earth_fixed_state_cache) > 8192:
                        store._earth_fixed_state_cache.popitem(last=False)
                exact_states[index] = converted
        for query_index, raw_index in zip(
            np.flatnonzero(exact),
            exact_indices,
        ):
            states[query_index] = exact_states[int(raw_index)]

    lower_indices = upper_indices - 1
    interpolated = (
        (upper_indices > 0)
        & (upper_indices < times.size)
        & (queries >= times[0])
        & (queries <= times[-1])
        & (
            snapshot.segment_ids[np.clip(lower_indices, 0, times.size - 1)]
            == snapshot.segment_ids[np.clip(upper_indices, 0, times.size - 1)]
        )
    )
    interpolated_query_indices = np.flatnonzero(interpolated)
    if interpolated_query_indices.size:
        lower = lower_indices[interpolated]
        upper = upper_indices[interpolated]
        if interpolation_policy.method == "linear":
            fractions = (
                (queries[interpolated] - times[lower])
                / (times[upper] - times[lower])
            )

            unique_indices = np.unique(
                np.concatenate((lower, upper))
            )
            converted_by_index = {}
            uncached_indices = []
            for index in unique_indices:
                key = (snapshot.epoch, frame_name, int(index))
                with store._lock:
                    converted = store._earth_fixed_state_cache.get(key)
                if converted is not None:
                    converted_by_index[int(index)] = converted
                else:
                    uncached_indices.append(int(index))
            if uncached_indices:
                uncached_array = np.asarray(uncached_indices, dtype=np.intp)
                batch_converted = states_to_itrf_m_batch(
                    raw[uncached_array, 1:7],
                    frame_name,
                    raw[uncached_array, 0],
                )
                for index, converted in zip(uncached_indices, batch_converted):
                    key = (snapshot.epoch, frame_name, index)
                    with store._lock:
                        store._earth_fixed_state_cache[key] = converted
                        if len(store._earth_fixed_state_cache) > 8192:
                            store._earth_fixed_state_cache.popitem(last=False)
                    converted_by_index[index] = converted

            lower_states = np.stack(
                [converted_by_index[int(index)] for index in lower]
            )
            upper_states = np.stack(
                [converted_by_index[int(index)] for index in upper]
            )
            states[interpolated_query_indices] = (
                lower_states
                + fractions[:, np.newaxis] * (upper_states - lower_states)
            )
        else:
            support_ranges = []
            support_indices = []
            for query_index, query_time in zip(
                interpolated_query_indices,
                queries[interpolated],
            ):
                upper_index = int(np.searchsorted(times, query_time))
                lower_index = upper_index - 1
                segment_id = int(snapshot.segment_ids[lower_index])
                segment_start = int(
                    np.searchsorted(snapshot.segment_ids, segment_id, side="left")
                )
                segment_stop = int(
                    np.searchsorted(snapshot.segment_ids, segment_id, side="right")
                )
                count = min(
                    segment_stop - segment_start,
                    max(2, interpolator.required_points),
                )
                start = segment_start + max(
                    0,
                    min(
                        upper_index - segment_start - count // 2,
                        segment_stop - segment_start - count,
                    ),
                )
                stop = start + count
                support_ranges.append((int(query_index), start, stop))
                support_indices.extend(range(start, stop))

            converted_support_by_index = {}
            uncached_support_indices = []
            for index in np.unique(np.asarray(support_indices, dtype=np.intp)):
                index_value = int(index)
                key = (snapshot.epoch, frame_name, index_value)
                with store._lock:
                    converted = store._earth_fixed_state_cache.get(key)
                if converted is not None:
                    converted_support_by_index[index_value] = converted
                else:
                    uncached_support_indices.append(index_value)
            if uncached_support_indices:
                uncached_array = np.asarray(uncached_support_indices, dtype=np.intp)
                batch_converted = states_to_itrf_m_batch(
                    raw[uncached_array, 1:7],
                    frame_name,
                    raw[uncached_array, 0],
                )
                for index, converted in zip(
                    uncached_support_indices,
                    batch_converted,
                ):
                    key = (snapshot.epoch, frame_name, index)
                    with store._lock:
                        store._earth_fixed_state_cache[key] = converted
                        if len(store._earth_fixed_state_cache) > 8192:
                            store._earth_fixed_state_cache.popitem(last=False)
                    converted_support_by_index[index] = converted

            query_times_by_window: dict[tuple[int, int], list[tuple[int, float]]] = {}
            for query_index, start, stop in support_ranges:
                query_times_by_window.setdefault((start, stop), []).append(
                    (
                        query_index,
                        float(queries[query_index]),
                    )
                )
            for (start, stop), window_queries in query_times_by_window.items():
                support_states = np.stack(
                    [
                        converted_support_by_index[index]
                        for index in range(start, stop)
                    ]
                )
                for query_index, query_time in window_queries:
                    interpolated_state = interpolator.interpolate_view(
                        times[start:stop],
                        support_states,
                        query_time,
                        snapshot.segment_ids[start:stop],
                    )
                    if interpolated_state is not None:
                        states[query_index] = interpolated_state

    return states
