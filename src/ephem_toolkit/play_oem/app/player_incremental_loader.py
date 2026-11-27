"""Incremental OEM load event handling for the play-oem player."""

from __future__ import annotations

import os

from .. import clock, time_range

from ..incremental_loader import LoadEvent, LoadEventKind
from ..oem_data_store import (
    InterpolationPolicy,
    LoadStatus,
    OemDataStore,
)
from ..playback_data import oem_declared_slider_bounds
from ..saved_state import normalize_recent_path
from .player_app_state import PlayerAppState
from .player_store_data_view_refresh import _append_affects_plot

MAX_INCREMENTAL_LOAD_EVENTS_PER_TICK: int = 64
"""Maximum queued load events handled by one wx timer tick."""



class PlayerIncrementalLoadingMixin:
    """Dispatch progressive OEM load events on the wx application thread."""

    def _load_oem_file(self: PlayerAppState, path: str) -> None:
        self._start_incremental_load(path)

    def _start_incremental_load(self: PlayerAppState, path: str) -> None:
        if self._range_dragging:
            self._set_range_dragging(False)
        if self._current_oem_path is not None:
            self._capture_current_file_settings()
        normalized_path = normalize_recent_path(path)
        previous_pending_store = self._store_state.pending
        store = OemDataStore()
        try:
            if not self._use_oem_interpolation:
                store.set_interpolation(
                    InterpolationPolicy(
                        self._interpolation_method,
                        self._interpolation_degree,
                    )
                )
            self._timeline_restore_state.file_playback_bounds = None
            if self._saved_state is not None:
                settings = self._saved_state.file_settings.get(normalized_path)
                if settings is not None:
                    self._timeline_restore_state.file_playback_bounds = (
                        settings.playback_range
                    )
            self._playback_handles_fixed_during_load = (
                self._timeline_restore_state.file_playback_bounds is not None
            )
            if (
                not self._oem_loaded
                and self._timeline_restore_state.file_playback_bounds is not None
            ):
                self._playback_handle_bounds = (
                    self._timeline_restore_state.file_playback_bounds
                )
            self._incremental_loader.start(path, store=store)
        except Exception:
            store.close()
            raise
        if (
            previous_pending_store is not None
            and previous_pending_store is not self._store_state.active
        ):
            previous_pending_store.close()
        self._store_state.pending = store
        self._load_state.generation = self._incremental_loader.generation
        self._load_state.path = path
        self._load_state.first_batch = False
        self._load_state.initial_range_waiting = False
        self._load_state.initial_range_ready = False
        self._load_state.failed = False
        self._load_state.cursor_anchor_s = None
        self._load_state.pending_slider_bounds = None
        self._timeline_restore_state.file_current_time_s = None
        self._timeline_restore_state.viewport = None
        self._timeline_restore_state.metadata_restored = False
        self._timeline_restore_state.metadata_coverage = None
        self._timeline_restore_state.metadata_playback = None
        self._timeline_restore_state.metadata_viewport = None
        self._timeline_restore_state.loading_locked = False
        self._refresh_state.last_incremental_view_refresh_monotonic_s = None
        if (
            previous_pending_store is self._store_state.active
            and previous_pending_store is not None
        ):
            snapshot = previous_pending_store.snapshot()
            if snapshot.status is LoadStatus.CANCELLED:
                if self._store_state.view_context is not None:
                    self._store_state.view_context = (
                        self._store_state.view_context.refresh()
                    )
                    self._queue_store_view_refresh()
                    self._refresh_store_data_views()
        self.status_bar.set_message(f"Loading {os.path.basename(path)}…")

    def _poll_incremental_load(self: PlayerAppState) -> None:
        data_changed = False
        for event in self._incremental_loader.drain(
            limit=MAX_INCREMENTAL_LOAD_EVENTS_PER_TICK
        ):
            if event.generation != self._load_state.generation:
                continue
            path = self._load_state.path
            if path is None:
                continue
            if event.kind is LoadEventKind.STARTED:
                continue
            if event.kind is LoadEventKind.SEGMENT_METADATA:
                self._handle_segment_metadata_event(event, path)
            elif event.kind is LoadEventKind.RAW_APPEND:
                data_changed |= self._handle_raw_append_event(event, path)
                # Request producer flow control before processing more queued
                # append notices or refreshing unrelated app state.
                self._advance_initial_plot()
            elif event.kind is LoadEventKind.COMPLETE:
                changed, _ = self._handle_load_complete_event(event)
                data_changed |= changed
            elif event.kind is LoadEventKind.FAILED:
                data_changed |= self._handle_load_failed_event(event)
            if event.kind in (LoadEventKind.COMPLETE, LoadEventKind.FAILED):
                if self._range_dragging:
                    self._range_dragging = False
                    self._publish_range_hint()
        if data_changed and self._oem_loaded:
            self.workspace.update_oem_information(
                self._formatted_dashboard_context(),
                self._formatted_metadata_details(),
                self.clock.t_start < self.clock.t_end,
            )
            self._update_time_display()
        if self._refresh_state.incremental_view_refresh_pending:
            self._refresh_incremental_data_views()
        self._advance_initial_plot()

    def _advance_initial_plot(self: PlayerAppState) -> None:
        """Pause at requested-range coverage, draw the first data_views, then resume."""
        session = self._incremental_loader.session
        store = self._store_state.active
        if (
            session is None
            or store is None
            or not self._load_state.first_batch
            or self._load_state.initial_range_ready
        ):
            return
        if not self._load_state.initial_range_waiting:
            coverage = self._timeline_restore_state.metadata_coverage
            if coverage is None:
                coverage = self._slider_bounds
            playback = self._timeline_restore_state.playback_bounds
            if playback is None and self._playback_handles_fixed_during_load:
                playback = self._playback_handle_bounds
            if playback is None:
                playback = (
                    coverage[0],
                    min(
                        coverage[1],
                        coverage[0] + clock.PlaybackClock.DEFAULT_PLAYBACK_SPAN_S,
                    ),
                )
            # Saved endpoints can extend slightly beyond metadata rounded to
            # milliseconds, while still matching the actual final sample.
            coverage = (min(coverage[0], playback[0]), max(coverage[1], playback[1]))
            now = self._timeline_restore_state.file_current_time_s
            if now is None:
                now = playback[0]
            try:
                plot = time_range.resolve_plot_range(
                    self.plot_time_range, coverage, playback, now
                )
            except ValueError:
                return
            required_end = max(playback[1], plot.end_s if plot else playback[1])
            if (
                self.clock.t_end < required_end
                and not self._load_state.coverage_complete
            ):
                return
            if not self._load_state.coverage_complete:
                # Ask the producer to stop after publishing the next committed
                # batch. Earlier batches are allowed to stream without per-batch
                # pause/resume cycles.
                session.pause()
            self._load_state.initial_range_waiting = True
            self._restore_completed_scrubber_state()
            self._update_time_display()
            self._refresh_state.incremental_view_refresh_pending = True
            self._refresh_incremental_data_views(force=True)
            return
        if (
            not self._load_state.coverage_complete
            and not session.paused
        ):
            return
        if (
            self._range_dragging
            or self._refresh_state.incremental_view_refresh_pending
        ):
            return
        with store._scheduler_lock:
            busy = bool(store._scheduled_work)
        if busy:
            return
        self._queue_store_view_refresh()
        self._refresh_store_data_views()
        for opened in self._open_panels.values():
            canvas = opened.canvas or getattr(opened.data_view, "_canvas", None)
            if canvas is not None:
                canvas.draw()
            else:
                opened.panel.request_redraw()
        self.workspace.draw_initial_data_views()
        self._load_state.initial_range_ready = True
        session.resume()

    def _handle_segment_metadata_event(
        self: PlayerAppState, event: LoadEvent, path: str
    ) -> None:
        segment_meta = dict(event.segment_metadata or ())
        declared_bounds = oem_declared_slider_bounds(
            str(segment_meta.get("START_TIME", "")),
            str(segment_meta.get("STOP_TIME", "")),
            time_system=str(segment_meta.get("TIME_SYSTEM", "")),
        )
        if declared_bounds is None:
            return
        if self._load_state.first_batch:
            self._slider_bounds = (
                min(self._slider_bounds[0], declared_bounds[0]),
                max(self._slider_bounds[1], declared_bounds[1]),
            )
            self._restore_scrubber_from_metadata(path, self._slider_bounds)
        elif self._load_state.pending_slider_bounds is None:
            self._load_state.pending_slider_bounds = declared_bounds
        else:
            self._load_state.pending_slider_bounds = (
                min(
                    self._load_state.pending_slider_bounds[0],
                    declared_bounds[0],
                ),
                max(
                    self._load_state.pending_slider_bounds[1],
                    declared_bounds[1],
                ),
            )
        self._load_state.pending_slider_bounds = self._load_state.pending_slider_bounds

    def _handle_raw_append_event(
        self: PlayerAppState, event: LoadEvent, path: str
    ) -> bool:
        store = self._store_state.pending
        notice = event.raw_notice
        if store is None or notice is None:
            self.status_bar.set_message(
                "Could not install OEM data: missing store append notice."
            )
            self._load_state.failed = True
            return False
        try:
            snapshot = store.snapshot()
            if (
                notice.epoch != snapshot.epoch
                or notice.revision > snapshot.revision
                or notice.sample_count > snapshot.sample_count
            ):
                raise RuntimeError("raw append notice does not match store snapshot")
            self._install_store_snapshot(store, snapshot, path)
        except Exception as error:
            self._load_state.failed = True
            self.clock.pause()
            self.status_bar.set_message(f"Could not install OEM data: {error}")
            return False
        self._load_state.loading_progress_s = notice.end_s
        plot_range = self._resolved_plot_range()
        if (
            not self._load_state.initial_range_ready
            or _append_affects_plot(notice, plot_range)
        ):
            self._refresh_state.incremental_view_refresh_pending = True
        self.status_bar.set_message(
            f"Loading {os.path.basename(path)}: "
            f"{snapshot.sample_count:,} states (partial coverage)"
        )
        return True

    def _handle_load_complete_event(
        self: PlayerAppState, event: LoadEvent
    ) -> tuple[bool, bool]:
        if not self._load_state.first_batch:
            self.status_bar.set_message("OEM contains no state data.")
            self._close_pending_oem_store()
            return True, True
        self._finish_incremental_metadata(event.completion)
        self._load_state.coverage_complete = True
        self._apply_pending_playback_bounds()
        if self._current_oem_path is not None:
            self._restore_scrubber_from_metadata(
                self._current_oem_path,
                self._slider_bounds,
                use_defaults_for_invalid_state=True,
            )
        self._restore_completed_scrubber_state()
        self._timeline_restore_state.file_current_time_s = None
        self._timeline_restore_state.viewport = None
        self._load_state.loading_progress_s = None
        self._load_state.cursor_anchor_s = None
        self._load_state.failed = False
        if self._store_state.pending is self._store_state.active:
            self._store_state.pending = None
        self.status_bar.set_message("")
        return True, True

    def _restore_completed_scrubber_state(self: PlayerAppState) -> None:
        if not self._timeline_restore_state.metadata_restored:
            return
        timeline_slider = getattr(self.workspace, "timeline_slider", None)
        viewport = self._timeline_restore_state.metadata_viewport
        if (
            not self._load_state.initial_range_ready
            and timeline_slider is not None
            and viewport is not None
        ):
            set_viewport = getattr(timeline_slider, "set_viewport", None)
            if callable(set_viewport):
                set_viewport(viewport)
        target = self._timeline_restore_state.file_current_time_s
        if target is not None and self.clock.t_start <= target <= self.clock.t_end:
            if self.clock.playback_start <= target <= self.clock.playback_end:
                with self._installing_incremental_update():
                    self.clock.seek(target)
                self._timeline_restore_state.file_current_time_s = None
                self._load_state.cursor_anchor_s = None

    def _handle_load_failed_event(self: PlayerAppState, event: LoadEvent) -> bool:
        message = str(event.error) if event.error is not None else "unknown error"
        prefix = (
            "Loaded a valid prefix, but could not finish reading OEM: "
            if self._load_state.first_batch
            else "Could not open OEM: "
        )
        self.clock.pause()
        self._load_state.failed = True
        self.status_bar.set_message(prefix + message)
        if not self._load_state.first_batch:
            self._close_pending_oem_store()
        elif self._store_state.pending is self._store_state.active:
            self._store_state.pending = None
        if self._store_state.view_context is not None:
            self._store_state.view_context = self._store_state.view_context.refresh()
            self._queue_store_view_refresh()
            self._refresh_state.incremental_view_refresh_pending = True
        return True
