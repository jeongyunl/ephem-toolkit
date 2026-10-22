"""Structural state contract shared by PlayerApp behavior mixins."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import wx
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg

from .. import (
    clock,
    control_window,
    cursor,
    playback_data,
    series,
    time_unit,
    workspace,
)
from ..views import base, registry
from .support import _OpenView


class PlayerAppState(Protocol):
    """Application data and operations required by the extracted mixins."""

    clock: clock.PlaybackClock
    control_window: control_window.ControlWindow
    cursor: cursor.OemCursor
    frame: wx.Frame
    frame_context: str
    object_name: str
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    workspace: workspace.Workspace
    wx_app: wx.App
    _closed: bool
    _in_timer_tick: bool
    _last_frame_monotonic_s: float | None
    """Time of the last consumed playback frame period, from a monotonic clock."""
    _fps: int
    """Requested frame rate used to calculate each playback time increment."""
    _oem_loaded: bool
    _on_open_file_callback: Callable[[str], playback_data.PlaybackData] | None
    _open_panels: dict[str, _OpenView]
    _open_views: dict[str, _OpenView]
    _panel_view_choices: tuple[tuple[str, str], ...]
    _plots: tuple[str, ...]
    _requested_3d_backend: str
    _selected_3d_backend: str | None
    _started: bool
    _tick_interval_ms: int
    _timer: wx.Timer
    _view_registry: registry.ViewRegistry

    def _open_view(
        self,
        name: str,
        create_view: Callable[[wx.Window], base.View],
        *,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def _open_matplotlib_trajectory_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def _set_3d_backend(self, backend_name: str) -> None: ...
    def _update_time_display(self) -> None: ...
    def open_trajectory_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_speed_altitude_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_state_components_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_rtn_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_angular_velocity_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_direction_change_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_distance_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_panel_view(
        self,
        name: str,
        panel_id: str,
        stack: str = "middle",
        *,
        force_replace: bool = False,
    ) -> None: ...
    def _select_panel_view(self, name: str, panel_id: str, stack: str) -> None: ...
    def _move_panel(self, panel_id: str, offset: int) -> None: ...
    def _duplicate_panel(self, panel_id: str) -> None: ...
    def close_panel(self, panel_id: str) -> None: ...
    def _panel_view_label(self, name: str) -> str: ...
    def _dispose_open_view(self, panel_id: str) -> None: ...
    def _release_open_view_resources(self, opened: _OpenView) -> None: ...
    def _on_plot_click(
        self, event: MouseEvent, toolbar: NavigationToolbar2WxAgg
    ) -> None: ...
    def _toggle_playback(self) -> None: ...
    def _seek_to_fraction(self, progress: float) -> None: ...
    def _timeline_tooltip_at(self, progress: float) -> str: ...
    def _set_playback_speed(self, speed: float) -> None: ...
    def _set_playback_fps(self, fps: int) -> None: ...
    def _set_transport_rate(self, rate: float) -> None: ...
    def _play_reverse_at_current_speed(self) -> None: ...
    def _play_forward_at_current_speed(self) -> None: ...
    def _reverse_playback(self) -> None: ...
    def _step_samples(self, count: int) -> None: ...
    def _step_seconds(self, amount_s: float) -> None: ...
    def _jump_to_start(self) -> None: ...
    def _jump_to_end(self) -> None: ...
    def _seek_to_time(self, time_entry_text: str) -> None: ...
