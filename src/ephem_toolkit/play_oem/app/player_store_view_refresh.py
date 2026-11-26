"""Store notice draining and store-bound view refresh for PlayerApp."""

from __future__ import annotations

import time
from queue import Empty

import wx

from .. import time_range
from ..oem_data_store import (
    AppendNotice,
    OemDataStore,
    ResetNotice,
    StoreSnapshot,
    TierNotice,
)
from .player_app_state import PlayerAppState

INCREMENTAL_VIEW_REFRESH_INTERVAL_S: float = 5.0
"""Maximum refresh interval for partial incremental plot rebuilds."""


def _append_affects_plot(
    notice: AppendNotice, plot: time_range.ResolvedTimeRange | None
) -> bool:
    return bool(
        plot is not None
        and notice.start_s <= plot.end_s
        and notice.end_s >= plot.start_s
    )


def _tier_affects_display(
    notice: TierNotice,
    snapshot: StoreSnapshot,
    plot: time_range.ResolvedTimeRange | None,
    now_s: float,
) -> bool:
    """Keep notices that touch the plotted interval or the playback cursor."""
    span = notice.time_span_s
    if span is None and notice.tier != "station-access":
        first = max(0, notice.first_row - 1)
        stop = min(snapshot.sample_count, notice.stop_row + 1)
        if first < stop:
            span = (float(snapshot.raw[first, 0]), float(snapshot.raw[stop - 1, 0]))
    if span is None:
        return True
    start, end = span
    return (start <= now_s <= end) or (
        plot is not None and start <= plot.end_s and end >= plot.start_s
    )


class PlayerStoreViewRefreshMixin:
    """Route store notices to the graph panels affected by a store revision."""

    def _subscribe_store_notices(self: PlayerAppState, store: OemDataStore) -> None:
        self._store_notice_unsubscribe()
        self._store_notice_unsubscribe = store.subscribe(
            lambda notice: self._store_notice_queue.put((store, notice))
        )

    def _drain_store_notices(self: PlayerAppState) -> None:
        store = self._store_state.active
        if store is None:
            while True:
                try:
                    self._store_notice_queue.get_nowait()
                except Empty:
                    break
            return

        snapshot = store.snapshot()
        refresh_all = False
        affected: set[str] = set()
        while True:
            try:
                notice_store, notice = self._store_notice_queue.get_nowait()
            except Empty:
                break
            if notice_store is not store or notice.epoch != snapshot.epoch:
                continue
            if isinstance(notice, ResetNotice):
                refresh_all = True
            elif isinstance(notice, AppendNotice):
                plot_range = self._resolved_plot_range()
                if (
                    not self._load_state.initial_range_ready
                    or _append_affects_plot(notice, plot_range)
                ):
                    refresh_all = True
            elif isinstance(notice, TierNotice):
                if _tier_affects_display(
                    notice, snapshot, self._resolved_plot_range(), self.clock.t_now
                ):
                    affected.update(self._views_for_tier_notice(notice))

        if refresh_all:
            self._queue_store_view_refresh()
        elif affected:
            self._queue_store_view_refresh(affected)
        if self._refresh_state.pending_store_view_ids:
            self._refresh_store_views()

    @staticmethod
    def _views_for_tier_notice(notice: TierNotice) -> set[str]:
        if notice.tier == "series":
            group_views = {
                "kinematics": {"speed-altitude", "distance"},
                "rtn": {"rtn"},
                "direction-rates": {"angular-velocity", "direction-change"},
                "distance-delta": {"distance"},
            }
            if notice.group is None:
                return set()
            return set(group_views.get(notice.group, ()))
        if notice.tier in ("earth-fixed", "ground-track", "footprints"):
            return {"ground-track", "pass-ground-track"}
        if notice.tier == "station-access":
            return {
                "station-status",
                "elevation-profile",
                "azimuth-profile",
                "range-profile",
                "pass-list",
                "sky-view",
                "pass-ground-track",
            }
        return set()

    def _queue_store_view_refresh(
        self: PlayerAppState, view_ids: set[str] | None = None
    ) -> None:
        if self._should_suppress_partial_store_view_refresh():
            return
        if view_ids is None:
            candidates = self._open_panels
        else:
            candidates = {
                panel_id: opened
                for panel_id, opened in self._open_panels.items()
                if opened.view_name in view_ids
            }
        self._refresh_state.pending_store_view_ids.update(
            candidates
        )

    def _should_suppress_partial_store_view_refresh(
        self: PlayerAppState,
    ) -> bool:
        """Keep every loaded view stable until full OEM coverage completes."""
        return (
            self._load_state.initial_range_ready
            and not self._load_state.coverage_complete
        )

    def _refresh_store_views(self: PlayerAppState) -> None:
        if self._should_suppress_partial_store_view_refresh():
            self._refresh_state.incremental_view_refresh_pending = True
            return
        if self._should_defer_incremental_view_refresh():
            self._refresh_state.incremental_view_refresh_pending = True
            return
        context = self._store_state.view_context
        if context is None:
            return
        if self._store_state.active is not None:
            snapshot = self._store_state.active.snapshot()
            if (
                context.snapshot.epoch != snapshot.epoch
                or context.snapshot.revision != snapshot.revision
                or context.snapshot.policy_revision != snapshot.policy_revision
            ):
                context = context.refresh()
                self._store_state.view_context = context
        panel_ids = tuple(self._refresh_state.pending_store_view_ids)
        self._refresh_state.pending_store_view_ids.clear()
        for panel_id in panel_ids:
            opened = self._open_panels.get(panel_id)
            if opened is None:
                continue
            if opened.requires_store_rebuild:
                self.open_panel_view(
                    opened.view_name,
                    panel_id=panel_id,
                    stack=opened.stack,
                    force_replace=True,
                )
                continue
            view_context = context.with_range(
                self._resolved_plot_range(),
                (self.clock.t_start, self.clock.t_end),
            )
            update = getattr(opened.view, "update_from_store", None)
            try:
                if callable(update):
                    update(view_context)
                    set_time_range = getattr(opened.view, "set_time_range", None)
                    if callable(set_time_range):
                        set_time_range(view_context.plot_range, view_context.coverage)
                    opened.applied_range = view_context.plot_range
                    opened.applied_coverage = view_context.coverage
                    opened.range_initialized = True
                    opened.view.update(self.clock.t_now)
                    if opened.canvas is not None:
                        opened.canvas.draw_idle()
                    else:
                        opened.panel.request_redraw()
                else:
                    self.open_panel_view(
                        opened.view_name,
                        panel_id=panel_id,
                        stack=opened.stack,
                        force_replace=True,
                    )
            except Exception as error:
                self.status_bar.set_message(f"Could not refresh OEM views: {error}")

        if self._refresh_state.pending_store_view_ids:
            return
        retired_store = self._store_state.retired
        if retired_store is not None and retired_store is not self._store_state.active:
            self._store_state.retired = None
            retired_store.close()

    def _should_defer_incremental_view_refresh(
        self: PlayerAppState,
    ) -> bool:
        if (
            self._load_state.first_batch
            and not self._load_state.coverage_complete
            and not self._load_state.initial_range_ready
            and (
                not self._load_state.initial_range_waiting
                or not getattr(self._incremental_loader, "paused", False)
            )
        ):
            return True
        return (
            self._range_dragging
            and self._load_state.first_batch
            and (
                not self._load_state.coverage_complete
                or self._refresh_state.incremental_view_refresh_pending
            )
        )

    def _refresh_incremental_views(
        self: PlayerAppState, *, force: bool = False
    ) -> None:
        """Rebuild plots at a bounded rate, or immediately when loading ends."""
        if self._should_suppress_partial_store_view_refresh():
            self._refresh_state.incremental_view_refresh_pending = True
            return
        if self._should_defer_incremental_view_refresh():
            self._refresh_state.incremental_view_refresh_pending = True
            return
        if self._store_state.active is not None:
            if not self._open_panels and self._oem_loaded:
                self.open_plots(self._plots)
                self.workspace.draw_initial_graphs()
                wx.CallAfter(self._refresh_graph_stack_layouts)
            if not self._refresh_state.pending_store_view_ids:
                self._queue_store_view_refresh()
            self._refresh_store_views()
            self._refresh_state.incremental_view_refresh_pending = bool(
                self._refresh_state.pending_store_view_ids
            )
            return
        now = time.monotonic()
        last_refresh = self._refresh_state.last_incremental_view_refresh_monotonic_s
        if (
            not force
            and last_refresh is not None
            and now - last_refresh < INCREMENTAL_VIEW_REFRESH_INTERVAL_S
        ):
            return
        panel_layout = tuple(
            (opened.panel_id, opened.view_name, opened.stack)
            for opened in self._open_panels.values()
        )
        for context in self._station_analysis_contexts.values():
            context.select_interval(None)
        refresh_succeeded = False
        try:
            if panel_layout:
                for panel_id, view_name, stack in panel_layout:
                    if self._update_incremental_panel_data(panel_id):
                        continue
                    self.open_panel_view(
                        view_name,
                        panel_id=panel_id,
                        stack=stack,
                        force_replace=True,
                    )
            elif self._oem_loaded:
                self.open_plots(self._plots)
            self.workspace.draw_initial_graphs()
            wx.CallAfter(self._refresh_graph_stack_layouts)
            self._refresh_state.last_incremental_view_refresh_monotonic_s = now
            refresh_succeeded = True
        except Exception as error:
            self.status_bar.set_message(f"Could not refresh OEM views: {error}")
        finally:
            self._refresh_state.incremental_view_refresh_pending = not refresh_succeeded
        retired_store = self._store_state.retired
        if (
            refresh_succeeded
            and retired_store is not None
            and retired_store is not self._store_state.active
        ):
            retired_store.close()

    def _update_incremental_panel_data(self: PlayerAppState, panel_id: str) -> bool:
        opened = self._open_panels.get(panel_id)
        if opened is None:
            return False
        update_data = getattr(opened.view, "update_data", None)
        if not callable(update_data) or not update_data(self.series, self.time_unit):
            return False

        resolved_range = time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            self.clock.t_now,
        )
        coverage = (self.clock.t_start, self.clock.t_end)
        set_time_range = getattr(opened.view, "set_time_range", None)
        if callable(set_time_range):
            set_time_range(resolved_range, coverage)
        opened.applied_range = resolved_range
        opened.applied_coverage = coverage
        opened.range_initialized = True
        opened.view.update(self.clock.t_now)
        if opened.canvas is not None:
            opened.canvas.draw_idle()
        else:
            opened.panel.request_redraw()
        return True
