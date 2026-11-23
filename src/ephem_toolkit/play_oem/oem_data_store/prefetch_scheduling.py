"""Pure request-priority and request-size helpers."""

from __future__ import annotations

from concurrent.futures import CancelledError, Future
import heapq
import math
from typing import TYPE_CHECKING

import numpy as np

from ..station_access import MAX_ACCESS_SAMPLE_STEP_S
from .public_types import (
    QueryRequest,
    RangeHint,
    StoreSnapshot,
)
from .internal_types import (
    _ScheduledWork,
    _StationSegmentLayout,
)

if TYPE_CHECKING:
    from .data_store import OemDataStore


def _ranges_intersect(
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    return first[0] <= second[1] and second[0] <= first[1]


def priority_for_request(
    store: OemDataStore,
    request: QueryRequest,
    hint: RangeHint | None,
) -> int:
    if hint is None:
        return 4
    if store._tier_interest.get(request.tier, 0) == 0:
        return 4
    bounds = expanded_request_bounds(request)
    if hint.plot is not None:
        plot = hint.plot
        width = max(plot[1] - plot[0], 1.0)
        if _ranges_intersect(bounds, plot):
            return 1
        expanded = (plot[0] - width, plot[1] + width)
        if _ranges_intersect(bounds, expanded) or (
            abs((bounds[0] + bounds[1]) / 2.0 - hint.now_s) <= width
        ):
            return 2
    if _ranges_intersect(bounds, hint.playback):
        return 3
    return 4


def expanded_request_bounds(request: QueryRequest) -> tuple[float, float]:
    from .store_support import (
        _expanded_request_bounds,
    )

    return _expanded_request_bounds(request)


def request_rows(
    work: _ScheduledWork,
) -> int:
    snapshot = work.snapshot
    bounds = expanded_request_bounds(work.request)
    if work.request.tier == "station-access":
        requested_rows = 0
        for raw_start_value, raw_stop_value in snapshot.segment_bounds:
            raw_start, raw_stop = int(raw_start_value), int(raw_stop_value)
            if raw_stop - raw_start < 2:
                continue
            start_s = float(snapshot.raw[raw_start, 0])
            end_s = float(snapshot.raw[raw_stop - 1, 0])
            count = max(
                2,
                math.ceil((end_s - start_s) / MAX_ACCESS_SAMPLE_STEP_S) + 1,
            )
            layout = _StationSegmentLayout(
                int(snapshot.segment_ids[raw_start]),
                raw_start,
                raw_stop,
                start_s,
                end_s,
                count,
                count,
                0,
            )
            from .store_support import _station_profile_row_range

            first, stop = _station_profile_row_range(layout, bounds)
            requested_rows += max(0, stop - first)
        return requested_rows
    start = int(np.searchsorted(snapshot.raw[:, 0], bounds[0], side="left"))
    stop = int(np.searchsorted(snapshot.raw[:, 0], bounds[1], side="right"))
    return stop - start


class PrefetchScheduler:
    """Own prioritized derived-tier work queue and worker-drain lifecycle."""

    def __init__(self, store: OemDataStore) -> None:
        self.store = store

    def prefetch(
        self,
        snapshot: StoreSnapshot,
        request: QueryRequest,
    ) -> Future[None]:
        import ephem_toolkit.play_oem.oem_data_store as public_store
        from .store_support import (
            _normalize_longitude,
            _validate_elevation_threshold,
            _validate_nonnegative_finite,
            _validate_time_bounds,
        )
        from .public_types import QueryRequest

        if not isinstance(request, QueryRequest):
            raise TypeError("request must be a QueryRequest")
        bounds = _validate_time_bounds(request.bounds_s)
        if request.tier == "series":
            groups = tuple(dict.fromkeys(request.series_groups))
            from ..series import SERIES_GROUPS

            unknown = set(groups).difference(SERIES_GROUPS)
            if unknown:
                raise ValueError(f"unsupported series groups: {sorted(unknown)}")
            if request.max_samples is not None and (
                isinstance(request.max_samples, bool)
                or not isinstance(request.max_samples, int)
                or request.max_samples < 1
            ):
                raise ValueError("max_samples must be a positive integer")
            request = QueryRequest(
                request.tier,
                bounds,
                request.station,
                groups,
                request.max_samples,
                request.minimum_elevation_deg,
                request.margin_s,
            )
        elif request.tier == "earth-fixed":
            margin = _validate_nonnegative_finite(
                request.margin_s,
                "margin_s",
            )
            request = QueryRequest(
                request.tier,
                bounds,
                request.station,
                request.series_groups,
                request.max_samples,
                request.minimum_elevation_deg,
                margin,
            )
        elif request.tier == "station-access":
            from ..ground_stations import GroundStation

            if not isinstance(request.station, GroundStation):
                raise ValueError("station-access requests require a GroundStation")
            minimum_elevation = request.minimum_elevation_deg
            if minimum_elevation is None:
                minimum_elevation = float(request.station.minimum_elevation_deg)
            request = QueryRequest(
                request.tier,
                bounds,
                request.station,
                request.series_groups,
                request.max_samples,
                _validate_elevation_threshold(minimum_elevation),
                request.margin_s,
            )
        elif request.tier == "ground-track":
            margin = _validate_nonnegative_finite(
                request.margin_s,
                "margin_s",
            )
            center = _normalize_longitude(request.center_longitude_deg)
            request = QueryRequest(
                request.tier,
                bounds,
                margin_s=margin,
                center_longitude_deg=center,
            )
        else:
            raise ValueError(f"prefetch does not support tier: {request.tier!r}")

        store = self.store
        store._validate_snapshot_epoch(snapshot)
        policy_revision = (
            snapshot.policy_revision if request.tier == "station-access" else 0
        )
        key = (
            snapshot.epoch,
            snapshot.revision,
            policy_revision,
            request,
        )
        with store._scheduler_lock:
            if store._scheduler_closed:
                raise RuntimeError("store scheduler is closed")
            existing = store._scheduled_work.get(key)
            if existing is not None:
                return existing.future
            future = public_store._PrefetchFuture()
            store._task_sequence += 1
            work = public_store._ScheduledWork(
                store._priority_for_request(
                    request,
                    store._range_hint,
                ),
                store._task_sequence,
                key,
                snapshot,
                request,
                future,
                store._range_generation,
            )
            store._scheduled_work[key] = work
            heapq.heappush(store._work_queue, work)
            store._start_scheduler_drain_locked()
            return future

    def close(self) -> None:
        store = self.store
        with store._scheduler_lock:
            if store._scheduler_closed:
                return
            store._scheduler_closed = True
        self.cancel_scheduled_work()
        store._scheduler_executor.shutdown(
            wait=True,
            cancel_futures=True,
        )

    def reprioritize_locked(self) -> None:
        store = self.store
        for work in store._work_queue:
            work.priority = store._priority_for_request(
                work.request,
                store._range_hint,
            )
            work.generation = store._range_generation
        heapq.heapify(store._work_queue)
        if store._active_work is not None:
            store._active_work.priority = store._priority_for_request(
                store._active_work.request,
                store._range_hint,
            )
        store._start_scheduler_drain_locked()

    def start_drain_locked(self) -> None:
        store = self.store
        if (
            store._scheduler_closed
            or store._scheduler_drain_active
            or not store._work_queue
        ):
            return
        store._scheduler_drain_active = True
        try:
            store._scheduler_executor.submit(self.drain_queue)
        except RuntimeError:
            store._scheduler_drain_active = False
            raise

    def drain_queue(self) -> None:
        import ephem_toolkit.play_oem.oem_data_store as public_store

        store = self.store
        while True:
            with store._scheduler_lock:
                if store._scheduler_closed or not store._work_queue:
                    store._scheduler_drain_active = False
                    return
                eligible = [
                    work
                    for work in store._work_queue
                    if not work.future.cancelled()
                    and (
                        store._range_hint is None
                        or not store._range_hint.dragging
                        or (
                            work.priority == 1
                            and store._request_rows(work)
                            <= public_store.DERIVED_CHUNK_SIZE
                        )
                    )
                ]
                if not eligible:
                    store._scheduler_drain_active = False
                    return
                work = min(eligible)
                store._work_queue.remove(work)
                heapq.heapify(store._work_queue)
                store._active_work = work
            if not work.future.set_running_or_notify_cancel():
                self.finish_scheduled_work(work)
                continue
            try:
                self.run_prefetch(work)
            except CancelledError as error:
                if not work.future.done():
                    work.future.set_exception(error)
            except Exception as error:
                if not work.future.done():
                    work.future.set_exception(error)
            else:
                if not work.future.done():
                    work.future.set_result(None)
            finally:
                self.finish_scheduled_work(work)

    def run_prefetch(self, work: _ScheduledWork) -> None:
        store = self.store
        if work.future.cancel_event.is_set():
            raise CancelledError()
        request = work.request
        if request.tier == "series":
            store.series(
                work.snapshot,
                request.bounds_s,
                groups=request.series_groups or None,
                max_samples=request.max_samples,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        elif request.tier == "earth-fixed":
            store.earth_fixed_positions(
                work.snapshot,
                request.bounds_s,
                request.margin_s,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        elif request.tier == "station-access":
            if request.station is None:
                raise ValueError("station-access requests require a GroundStation")
            store.station_access(
                work.snapshot,
                request.station,
                request.bounds_s,
                minimum_elevation_deg=request.minimum_elevation_deg,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        elif request.tier == "ground-track":
            store.ground_track(
                work.snapshot,
                request.bounds_s,
                margin_s=request.margin_s,
                center_longitude_deg=request.center_longitude_deg,
                wait=True,
                _cancel_event=work.future.cancel_event,
            )
        else:
            raise ValueError(f"prefetch does not support tier: {request.tier!r}")

    def finish_scheduled_work(self, work: _ScheduledWork) -> None:
        store = self.store
        with store._scheduler_lock:
            if store._scheduled_work.get(work.key) is work:
                store._scheduled_work.pop(work.key, None)
            if store._active_work is work:
                store._active_work = None

    def cancel_scheduled_work(self) -> None:
        store = self.store
        with store._scheduler_lock:
            for work in tuple(store._scheduled_work.values()):
                work.future.cancel()
            store._work_queue.clear()
            store._scheduled_work = {
                key: work
                for key, work in store._scheduled_work.items()
                if work is store._active_work
            }
