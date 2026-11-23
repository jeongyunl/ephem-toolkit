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
) -> CursorState:
    query_time = _validate_query_time(t_s)
    with store._lock:
        if snapshot.epoch != store._epoch:
            raise RuntimeError("store epoch has changed")
        if snapshot.policy_revision != store._policy_revision:
            raise RuntimeError("interpolation policy has changed")
        interpolator = store._state_interpolator
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
        state_m = raw[upper_index, 1:7].copy()
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
    return CursorState(
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
