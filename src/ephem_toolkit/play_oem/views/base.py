"""Toolkit-neutral interface for playback plot views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from matplotlib.axes import Axes
from matplotlib.lines import Line2D

from matplotlib.figure import Figure

from ..series import OrbitSeries
from ..time_range import ResolvedTimeRange
from ..time_unit import TimeUnit
from .plotting import SegmentedPlotHistory, set_shared_x_limits, time_bounds_to_axis

if TYPE_CHECKING:
    import wx


class View(Protocol):
    """Lifecycle shared by all playback views."""

    name: str

    def build(self, series: OrbitSeries, time_unit: TimeUnit, /) -> Figure | wx.Window:
        """Build the view content and its initial cursor state."""
        ...

    def update(self, t_s: float, /) -> None:
        """Move the view's cursor to an absolute OEM time."""
        ...

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        """Select displayed samples; None clears data for an empty effective range."""
        ...

    def close(self) -> None:
        """Release the view's plot resources."""
        ...


class TimeRangeSupport:
    """Shared time-axis, range filtering, and cursor-visibility behavior."""

    # Views whose per-tick update changes only animated cursor artists.
    animated_cursor_updates: bool = False

    def _configure_time_range(
        self,
        axes: tuple[Axes, ...],
        histories: tuple[SegmentedPlotHistory, ...],
        cursor_artists: tuple[Line2D, ...],
        start_time_s: float,
        divisor_s: float,
    ) -> None:
        self._range_axes = axes
        self._range_histories = histories
        self._range_cursors = cursor_artists
        self._range_start_time_s = start_time_s
        self._range_divisor_s = divisor_s
        self._range_bounds: ResolvedTimeRange | None = None
        self._range_coverage = (start_time_s, start_time_s)
        self._last_cursor_time_s = start_time_s
        self._range_applied = False
        self._range_active = False
        self._range_changed = True
        self._setting_shared_xlim = False
        self._range_xlim_callbacks = [
            (
                axis,
                cast(Any, axis).callbacks.connect(
                    "xlim_changed", self._on_range_xlim_changed
                ),
            )
            for axis in axes
        ]
        self._full_y_limits = tuple(axis.get_ylim() for axis in axes)

    def _on_range_xlim_changed(self, _axis: Axes) -> None:
        if self._setting_shared_xlim or not self._range_active:
            return
        if not self._range_axes:
            return
        expected = time_bounds_to_axis(
            self._range_bounds,
            self._range_coverage,
            self._range_start_time_s,
            self._range_divisor_s,
        )
        self._setting_shared_xlim = True
        try:
            set_shared_x_limits(self._range_axes, expected)
        finally:
            self._setting_shared_xlim = False

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, coverage: tuple[float, float], /
    ) -> None:
        if not hasattr(self, "_range_axes"):
            return
        if bounds != self._range_bounds or coverage != self._range_coverage:
            self._range_changed = True
        self._range_bounds = bounds
        self._range_coverage = coverage
        self._range_applied = True
        self._range_active = bounds is None or (
            bounds.start_s > coverage[0] or bounds.end_s < coverage[1]
        )
        limits = time_bounds_to_axis(
            bounds, coverage, self._range_start_time_s, self._range_divisor_s
        )
        has_samples = False
        for history in self._range_histories:
            has_samples = (
                history.update(
                    None if bounds is None else limits,
                    empty_range=bounds is None,
                )
                or has_samples
            )
        self._setting_shared_xlim = True
        try:
            set_shared_x_limits(self._range_axes, limits)
        finally:
            self._setting_shared_xlim = False
        if bounds is None:
            for cursor in self._range_cursors:
                cursor.set_visible(False)
        else:
            self._set_cursor_visibility(self._last_cursor_time_s)
        # Keep the current vertical zoom. Home on the navigation toolbar returns
        # to its captured full-data limits; this explicit hook serves other UIs.

    def consume_cursor_only_update(self) -> bool:
        """Return whether the time range is unchanged since the previous call.

        Callers pair this with a cursor ``update``; a True result means the only
        change was to animated cursors, so a cached background can be reused.
        """
        range_changed = self._range_changed
        self._range_changed = False
        return self.animated_cursor_updates and not range_changed

    def restore_full_y_limits(self) -> None:
        """Restore build-time full-history Y bounds without changing shared X."""
        for axis, limits in zip(self._range_axes, self._full_y_limits):
            axis.set_ylim(*limits)

    def _close_time_range(self) -> None:
        for axis, callback_id in getattr(self, "_range_xlim_callbacks", ()):
            cast(Any, axis).callbacks.disconnect(callback_id)
        self._range_xlim_callbacks = []

    def _set_cursor_visibility(self, time_s: float) -> None:
        self._last_cursor_time_s = time_s
        if not self._range_applied:
            return
        visible = (
            self._range_bounds is not None
            and self._range_bounds.start_s <= time_s <= self._range_bounds.end_s
        )
        for cursor in self._range_cursors:
            cursor.set_visible(visible)
