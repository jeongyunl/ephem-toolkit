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
    TierNotice,
)
from .player_app_state import PlayerAppState

INCREMENTAL_VIEW_REFRESH_INTERVAL_S: float = 5.0
"""Maximum refresh interval for partial incremental plot rebuilds."""


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
            if isinstance(notice, (AppendNotice, ResetNotice)):
                refresh_all = True
            elif isinstance(notice, TierNotice):
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
            return set(group_views.get(notice.group, ()))
        if notice.tier in ("earth-fixed", "ground-track", "footprints"):
            return {"ground-track", "pass-ground-track"}
        if notice.tier == "station-access":
            return {
                "station-status",
                "pass-strip",
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
        if view_ids is None:
            self._refresh_state.pending_store_view_ids.update(self._open_panels)
        else:
            self._refresh_state.pending_store_view_ids.update(
                panel_id
                for panel_id, opened in self._open_panels.items()
                if opened.view_name in view_ids
            )

    def _refresh_store_views(self: PlayerAppState) -> None:
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
        if self._should_defer_incremental_view_refresh():
            self._refresh_state.incremental_view_refresh_pending = True
            return
        if self._store_state.active is not None:
            if not self._open_panels and self._oem_loaded:
                self.open_plots(self._plots)
                self.workspace.draw_initial_graphs()
                wx.CallAfter(self._refresh_graph_stack_layouts)
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
