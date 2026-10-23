"""Application actions for independent playback and plot time ranges."""

from __future__ import annotations

from .. import time_range
from .state import PlayerAppState


def full_coverage_plot_rule(coverage: tuple[float, float]) -> time_range.PlotTimeRange:
    """Return the session default: disabled filtering with fixed OEM endpoints."""
    start, end = coverage
    return time_range.PlotTimeRange(
        enabled=False,
        start=time_range.TimeRangeEndpoint("fixed", start),
        end=time_range.TimeRangeEndpoint("fixed", end),
    )


class TimeRangeActionsMixin:
    """Validate and apply independent range edits owned by ``PlayerApp``."""

    def _begin_time_range_edit(self: PlayerAppState) -> None:
        self.clock.pause()
        self._last_frame_monotonic_s = None
        self._update_time_display()

    def _apply_playback_bounds(
        self: PlayerAppState, start_s: float, end_s: float
    ) -> None:
        bounds = time_range.validate_playback_range(
            (start_s, end_s), (self.clock.t_start, self.clock.t_end)
        )
        self._begin_time_range_edit()
        self.clock.set_playback_bounds(bounds.start_s, bounds.end_s)
        self._update_time_display()

    def _reset_playback_bounds(self: PlayerAppState) -> None:
        self._apply_playback_bounds(self.clock.t_start, self.clock.t_end)

    def _apply_plot_time_range(
        self: PlayerAppState, rule: time_range.PlotTimeRange
    ) -> None:
        checked = time_range.validate_plot_range(rule)
        coverage = (self.clock.t_start, self.clock.t_end)
        resolved = time_range.resolve_plot_range(checked, coverage, self.clock.t_now)
        # Empty intersections are valid. Validate completely before changing the
        # applied value so a malformed edit cannot expose a half-updated rule.
        self._begin_time_range_edit()
        self.plot_time_range = checked
        self._dispatch_time_range(resolved, self.clock.t_now)
        self._update_time_display()

    def _show_all_oem_data(self: PlayerAppState) -> None:
        current = self.plot_time_range
        self._apply_plot_time_range(
            time_range.PlotTimeRange(False, current.start, current.end)
        )

    def _drag_plot_endpoint(
        self: PlayerAppState, name: str, requested_s: float
    ) -> None:
        """Apply an absolute handle position while retaining endpoint mode."""
        current = self.plot_time_range
        endpoint = getattr(current, name)
        value = (
            requested_s if endpoint.mode == "fixed" else requested_s - self.clock.t_now
        )
        replacement = time_range.TimeRangeEndpoint(endpoint.mode, value)
        self._apply_plot_time_range(
            time_range.PlotTimeRange(
                current.enabled,
                replacement if name == "start" else current.start,
                replacement if name == "end" else current.end,
            )
        )

    def _dispatch_time_range(
        self: PlayerAppState,
        resolved: time_range.ResolvedTimeRange | None,
        time_s: float | None = None,
    ) -> None:
        """Apply range and cursor state to visible views, deferring hidden panels."""
        coverage = (self.clock.t_start, self.clock.t_end)
        selected_time = self.clock.t_now if time_s is None else time_s
        for opened in tuple(self._open_panels.values()):
            if not self._is_time_range_panel_visible(opened.panel):
                opened.pending_range = resolved
                opened.has_pending_range = True
                opened.pending_time_s = selected_time
                continue
            setter = getattr(opened.view, "set_time_range", None)
            if callable(setter):
                setter(resolved, coverage)
            opened.range_initialized = True
            opened.view.update(selected_time)
            self._queue_time_range_redraw(opened.panel)

    def _is_time_range_panel_visible(self: PlayerAppState, panel: object) -> bool:
        checker = getattr(self.workspace, "is_graph_panel_visible", None)
        return bool(checker(panel)) if callable(checker) else True

    def _queue_time_range_redraw(self: PlayerAppState, panel: object) -> None:
        queue = getattr(self.workspace, "queue_graph_redraw", None)
        if callable(queue):
            queue(panel)
        else:
            request = getattr(panel, "request_redraw", None)
            if callable(request):
                request()

    def _sync_open_panel(self: PlayerAppState, panel_id: str) -> None:
        opened = self._open_panels.get(panel_id)
        if opened is None or not self._is_time_range_panel_visible(opened.panel):
            return
        resolved = time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            self.clock.t_now,
        )
        setter = getattr(opened.view, "set_time_range", None)
        if callable(setter):
            setter(resolved, (self.clock.t_start, self.clock.t_end))
        opened.range_initialized = True
        opened.view.update(self.clock.t_now)
        opened.pending_time_s = None
        opened.pending_range = None
        opened.has_pending_range = False
        self._queue_time_range_redraw(opened.panel)
