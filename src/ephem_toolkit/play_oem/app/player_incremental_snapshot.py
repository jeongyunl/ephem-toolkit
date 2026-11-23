"""Store snapshot installation for progressive play-oem loading."""

from __future__ import annotations

import os
import time

from .. import clock, cursor, playback_data
from ..display_time import format_tt
from ..oem_data_store import OemDataStore, StoreSnapshot
from ..saved_state import normalize_recent_path
from ..views.base import StoreViewContext
from .player_app_state import PlayerAppState
from .player_time_range_actions import playback_range_plot_rule


class PlayerIncrementalSnapshotMixin:
    """Install prefix snapshots and advance the active store-backed cursor."""

    def _install_store_snapshot(
        self: PlayerAppState,
        store: OemDataStore,
        snapshot: StoreSnapshot,
        path: str,
    ) -> None:
        first_append = not self._load_state.first_batch
        meta = dict(snapshot.meta)
        if first_append:
            self._install_first_store_snapshot(store, snapshot, path, meta)
        else:
            self._advance_store_snapshot(store, snapshot)
        self.time_unit = snapshot.time_unit
        loaded_name = str(meta.get("OBJECT_NAME", "")).strip()
        if loaded_name:
            self.object_name = loaded_name
        self.object_id = str(meta.get("OBJECT_ID", "")).strip()
        self.status_bar.set_object(self.object_name, self.object_id)
        self._dashboard_context.update(
            {
                "object": self.object_name,
                "sample_count": str(snapshot.sample_count),
                "time_span": (
                    f"{format_tt(self.clock.t_start, self._display_time_zone)} - "
                    f"{format_tt(self.clock.t_end, self._display_time_zone)}"
                ),
            }
        )
        self._store_state.view_context = StoreViewContext.capture(
            store,
            time_unit=self.time_unit,
            plot_range=self._resolved_plot_range(),
            coverage=(self.clock.t_start, self.clock.t_end),
        )
        self._publish_range_hint()
        self._oem_interpolation = str(meta.get("INTERPOLATION", "")) or None
        interpolation_degree = meta.get("INTERPOLATION_DEGREE")
        self._oem_interpolation_degree = (
            None if interpolation_degree is None else int(interpolation_degree)
        )
        self._update_time_display()
        if first_append and self._timeline_restore_state.viewport is None:
            timeline_slider = getattr(self.workspace, "timeline_slider", None)
            if timeline_slider is not None:
                timeline_slider.set_viewport((self.clock.t_start, self.clock.t_end))
                self._update_time_display()
        self._remember_recent_oem(path, save_file_ranges=False)

    def _install_first_store_snapshot(
        self: PlayerAppState,
        store: OemDataStore,
        snapshot: StoreSnapshot,
        path: str,
        meta: dict[str, object],
    ) -> None:
        previous_store = self._store_state.active
        rate = self.clock.rate
        self._clock_unsubscribe()
        self._store_notice_unsubscribe()
        self.time_unit = snapshot.time_unit
        self.clock = clock.PlaybackClock(
            float(snapshot.raw[0, 0]),
            float(snapshot.raw[-1, 0]),
            sample_times=store.sample_times,
            default_playback_span_s=clock.PlaybackClock.DEFAULT_PLAYBACK_SPAN_S,
        )
        self.clock.set_playback_bounds(
            self.clock.t_start,
            self.clock.playback_end,
            follow_coverage=True,
        )
        self.clock.set_speed(abs(rate))
        self.clock.set_direction(-1 if rate < 0.0 else 1)
        if rate < 0.0:
            self.clock.seek(self.clock.t_end)
        self._clock_unsubscribe = self.clock.subscribe(self._on_clock_time_changed)
        self._store_state.active = store
        self._store_state.active = store
        self._subscribe_store_notices(store)
        self._store_state.pending = store
        self._store_state.pending = store
        self._store_state.retired = previous_store
        self._store_state.retired = previous_store
        self.series = playback_data.empty_playback_data().series
        self._oem_loaded = True
        self.workspace.set_oem_loaded(True)
        self._current_oem_path = normalize_recent_path(path)
        self.plot_time_range = playback_range_plot_rule()
        self._restore_file_plot_range(self._current_oem_path)
        self._timeline_restore_state.playback_bounds = (
            self._timeline_restore_state.file_playback_bounds
        )
        self._playback_handle_bounds = self._timeline_restore_state.playback_bounds or (
            self.clock.playback_start,
            self.clock.playback_end,
        )
        self._apply_pending_playback_bounds()
        if self._timeline_restore_state.file_current_time_s is not None:
            self._load_state.cursor_anchor_s = (
                self._timeline_restore_state.file_current_time_s
            )
        self._timeline_restore_state.file_playback_bounds = None
        self._slider_bounds = playback_data.oem_slider_bounds(
            str(meta.get("START_TIME", "")),
            str(meta.get("STOP_TIME", "")),
            (self.clock.t_start, self.clock.t_end),
            time_system=str(meta.get("TIME_SYSTEM", "UTC")) or "UTC",
        )
        if self._load_state.pending_slider_bounds is not None:
            self._slider_bounds = (
                min(
                    self._slider_bounds[0],
                    self._load_state.pending_slider_bounds[0],
                ),
                max(
                    self._slider_bounds[1],
                    self._load_state.pending_slider_bounds[1],
                ),
            )
        self._load_state.pending_slider_bounds = None
        self._restore_scrubber_from_metadata(path, self._slider_bounds)
        self._loaded_file_name = os.path.basename(path)
        self.status_bar.set_file_name(self._loaded_file_name)
        self._load_state.first_batch = True
        self._load_state.coverage_complete = False
        self._last_frame_monotonic_s = time.monotonic()
        self.cursor = cursor.StoreCursor(store, snapshot)

    def _advance_store_snapshot(
        self: PlayerAppState,
        store: OemDataStore,
        snapshot: StoreSnapshot,
    ) -> None:
        if self._store_state.active is not store:
            raise RuntimeError("raw append belongs to a non-active store")
        if not self.cursor.is_bound_to(store):
            raise RuntimeError("active store has no store-backed cursor")
        if snapshot.sample_count > self.cursor.timestamps_s.size:
            with self._installing_incremental_update():
                self.clock.extend_coverage(float(snapshot.raw[-1, 0]))
                self.cursor.refresh(snapshot)
        else:
            self.cursor.refresh(snapshot)
        if self._timeline_restore_state.playback_bounds is None:
            if not self._playback_handles_fixed_during_load:
                self._playback_handle_bounds = (
                    self.clock.playback_start,
                    self.clock.playback_end,
                )
        else:
            self._apply_pending_playback_bounds()

    def _apply_pending_playback_bounds(self: PlayerAppState) -> None:
        bounds = self._timeline_restore_state.playback_bounds
        if bounds is None:
            return
        if self.clock.t_start <= bounds[0] and bounds[1] <= self.clock.t_end:
            self._timeline_restore_state.playback_bounds = None
            if self._timeline_restore_state.file_current_time_s is None:
                self._load_state.cursor_anchor_s = None
            self._playback_handle_bounds = bounds
            with self._installing_incremental_update():
                self.clock.set_playback_bounds(*bounds)
        elif (
            self.clock.t_start <= bounds[0] <= self.clock.t_end
            and self.clock.t_now != bounds[0]
        ):
            with self._installing_incremental_update():
                self.clock.seek(bounds[0])
            if self._timeline_restore_state.file_current_time_s is None:
                self._load_state.cursor_anchor_s = None

    def _close_pending_oem_store(self: PlayerAppState) -> None:
        store = self._store_state.pending
        if store is not None and store is not self._store_state.active:
            store.close()
        self._store_state.pending = None
