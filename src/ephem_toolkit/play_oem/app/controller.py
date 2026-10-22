"""wxPython application shell for OEM playback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import gc
import math
import os
import signal
import time
from typing import cast

import wx

import ephem_toolkit.core.time_utils as time_utils

from .. import clock, control_window, cursor, series, time_unit, workspace
from .. import playback_data
from ..views import registry
from ..views.trajectory3d import selection as trajectory3d_selection

from .support import (
    DEFAULT_TICK_INTERVAL_MS,
    ELAPSED_TIME_DECIMAL_PLACES,
    EMPTY_GRAPH_LABEL,
    EMPTY_GRAPH_VIEW,
    PLAYER_FRAME_MIN_SIZE,
    PLAYER_FRAME_SIZE,
    _configure_settings_backend_without_session_bus,
    _OpenView,
)
from .view_factory import ViewFactoryMixin
from .playback_actions import PlaybackActionsMixin
from .panel_management import PanelManagementMixin
from .status_bar import PlaybackStatusBar

MILLISECONDS_PER_SECOND = 1000
"""Conversion factor between playback seconds and wx timer milliseconds."""

FRAME_COUNT_EPSILON: float = 1e-9
"""Tolerance in seconds for counting a frame at a timer deadline."""


class PlayerApp(ViewFactoryMixin, PlaybackActionsMixin, PanelManagementMixin):
    """Own the wx application, playback timer and playback windows."""

    def __init__(
        self,
        clock: clock.PlaybackClock,
        series: series.OrbitSeries,
        time_unit: time_unit.TimeUnit,
        cursor: cursor.OemCursor,
        object_name: str,
        frame_context: str,
        *,
        dashboard_context: dict[str, str] | None = None,
        metadata_details: Sequence[tuple[str, str]] = (),
        plots: Sequence[str] = ("overview",),
        three_d_backend: str = "auto",
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
        on_open_file: Callable[[str], playback_data.PlaybackData] | None = None,
        oem_loaded: bool = True,
        loaded_file_name: str | None = None,
    ) -> None:
        """Create the wx playback application.

        Parameters
        ----------
        clock : clock.PlaybackClock
            Playback state and observer source.
        series : series.OrbitSeries
            Computed OEM data shared by plot views.
        time_unit : time_unit.TimeUnit
            Display unit for plotted values.
        cursor : cursor.OemCursor
            OEM state lookup used by the 3D orbit view.
        object_name : str
            Object name used in plot titles and labels.
        frame_context : str
            Reference-frame context used by plot views.
        plots : Sequence[str], optional
            Plot names and groups to open when the application starts.
        three_d_backend : str, default="auto"
            Backend used for the 3D trajectory view.
        tick_interval_ms : int, default=DEFAULT_TICK_INTERVAL_MS
            Interval between playback timer events, in milliseconds.

        Raises
        ------
        ValueError
            If ``tick_interval_ms`` is less than one or the 3D backend is invalid.
        """
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        if three_d_backend not in trajectory3d_selection.THREE_D_BACKEND_CHOICES:
            raise ValueError(
                "three_d_backend must be one of "
                f"{', '.join(trajectory3d_selection.THREE_D_BACKEND_CHOICES)}"
            )

        self.clock = clock
        self.series = series
        self.time_unit = time_unit
        self.cursor = cursor
        self.object_name = object_name
        self.object_id = dict(metadata_details).get("Object ID", "").strip()
        self._loaded_file_name = loaded_file_name
        self.frame_context = frame_context
        self._tick_interval_ms = tick_interval_ms
        # Infer the initial slider value from the existing timer interval API.
        # Keep FPS separately so millisecond rounding does not affect clock steps.
        self._fps = min(
            control_window.FPS_MAX,
            max(
                control_window.FPS_MIN,
                round(MILLISECONDS_PER_SECOND / tick_interval_ms),
            ),
        )
        self._last_frame_monotonic_s: float | None = None
        self._on_open_file_callback = on_open_file
        self._oem_loaded = oem_loaded
        self._requested_3d_backend = three_d_backend
        self._selected_3d_backend: str | None = (
            "matplotlib" if three_d_backend == "matplotlib" else None
        )

        self._view_registry = registry.ViewRegistry()
        self._view_registry.register_view("trajectory-3d", self.open_trajectory_view)
        self._view_registry.register_view(
            "speed-altitude", self.open_speed_altitude_view
        )
        self._view_registry.register_view(
            "state-components", self.open_state_components_view
        )
        self._view_registry.register_view("rtn", self.open_rtn_view)
        self._view_registry.register_view(
            "angular-velocity", self.open_angular_velocity_view
        )
        self._view_registry.register_view(
            "direction-change", self.open_direction_change_view
        )
        self._view_registry.register_view("distance", self.open_distance_view)
        self._plots = self._view_registry.expand(plots)
        self._panel_view_choices = ((EMPTY_GRAPH_VIEW, EMPTY_GRAPH_LABEL),) + tuple(
            (name, self._view_registry.label_for(name))
            for name in self._view_registry.registered_views
        )

        _configure_settings_backend_without_session_bus()
        self.wx_app: wx.App = cast(wx.App, wx.GetApp())
        if self.wx_app is None:
            self.wx_app = wx.App(False)

        self.frame: wx.Frame = wx.Frame(
            None,
            title=f"play-oem (3D backend: {three_d_backend})",
        )
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Open File...\tCtrl+O")
        menu_bar.Append(file_menu, "&File")
        self.frame.SetMenuBar(menu_bar)
        self.status_bar = PlaybackStatusBar(self.frame)
        self.status_bar.set_file_name(loaded_file_name)
        if oem_loaded:
            self.status_bar.set_object(self.object_name, self.object_id)
        self.frame.Bind(wx.EVT_MENU, self._on_open_file, id=wx.ID_OPEN)
        self.workspace: workspace.Workspace = workspace.Workspace(
            self.frame,
            self._seek_to_fraction,
            on_toggle_play=self._toggle_playback,
            on_play_reverse=self._play_reverse_at_current_speed,
            on_play_forward=self._play_forward_at_current_speed,
            on_set_transport_rate=self._set_transport_rate,
            on_step_samples=self._step_samples,
            timeline_enabled=clock.t_start < clock.t_end,
            timeline_start_utc=time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(clock.t_start)
            ),
            timeline_end_utc=time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(clock.t_end)
            ),
            on_seek_to_time=self._seek_to_time,
            timeline_tooltip_at=self._timeline_tooltip_at,
            context=dashboard_context,
            details=metadata_details,
            view_choices=self._panel_view_choices,
            on_add_graph=self._add_graph_panel,
            status_bar=self.status_bar,
        )
        self.control_window: control_window.ControlWindow = (
            control_window.ControlWindow(
                self.workspace.playback_page,
                self._toggle_playback,
                self._set_playback_speed,
                self._reverse_playback,
                on_set_fps=self._set_playback_fps,
                fps=self._fps,
                on_step_samples=self._step_samples,
                on_step_seconds=self._step_seconds,
                on_jump_to_start=self._jump_to_start,
                on_jump_to_end=self._jump_to_end,
                accelerator_parent=self.frame,
                state_parent=self.workspace.state_page,
            )
        )
        self.control_window.bind_time_entry(self.workspace.timeline_time_entry)
        self.workspace.set_playback_content(self.control_window.playback_scroller)
        self.workspace.set_state_content(self.control_window.state_scroller)
        self.frame.SetMinSize(PLAYER_FRAME_MIN_SIZE)
        self.frame.SetSize(PLAYER_FRAME_SIZE)
        self.frame.Bind(wx.EVT_CLOSE, self._on_frame_close)

        self._timer: wx.Timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._in_timer_tick = False
        self._started = False
        self._closed = False
        self._open_views: dict[str, _OpenView] = {}
        self._open_panels: dict[str, _OpenView] = {}
        self.workspace.set_oem_loaded(oem_loaded)
        self.control_window.set_playback_enabled(oem_loaded)
        if not oem_loaded:
            self.status_bar.set_message("Open an OEM file to begin playback.")

    def run(self) -> None:
        """Run the wx event loop and restore the prior SIGINT handler on exit."""
        previous_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            self.start()
            self.wx_app.MainLoop()
        finally:
            try:
                self.close()
            finally:
                try:
                    signal.signal(signal.SIGINT, previous_sigint_handler)
                finally:
                    self._release_wx_resources()
                    # Dispose wx/Matplotlib wrapper cycles before wx teardown at exit.
                    gc.collect()

    def start(self) -> None:
        """Show the application, open the selected plots and start playback ticks."""
        if self._closed:
            raise RuntimeError("cannot start a closed PlayerApp")
        if self._started:
            return

        self._started = True
        self._last_frame_monotonic_s = time.monotonic()
        self._update_time_display()
        self.frame.Show()
        if self._oem_loaded:
            self.open_plots(self._plots)
        self.workspace.draw_initial_graphs()
        # The shown frame's final client size is not available until layout settles;
        # refresh then so each stack gets the correct viewport-sized scroll tail.
        self.frame.Layout()
        wx.CallAfter(self._refresh_graph_stack_layouts)
        if not self._timer.Start(self._tick_interval_ms):
            raise RuntimeError("could not start the wx playback timer")

    def close(self) -> None:
        """Close all playback windows and stop the wx timer."""
        if self._closed:
            return
        if not self.frame.Close(force=True) and not self._closed:
            raise RuntimeError("could not close the play-oem frame")

    def _on_open_file(self, _event: wx.CommandEvent) -> None:
        """Select an OEM and load it into this playback window."""
        dialog = wx.FileDialog(
            self.frame,
            message="Open OEM file",
            wildcard="OEM files (*.oem, *.OEM)|*.oem;*.OEM|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        finally:
            dialog.Destroy()

        if self._on_open_file_callback is None:
            self.status_bar.set_message("Opening another OEM is unavailable.")
            return
        try:
            loaded_data = self._on_open_file_callback(path)
        except Exception as error:
            self.status_bar.set_message(f"Could not open OEM: {error}")
            return

        self._replace_playback_data(loaded_data, os.path.basename(path))

    def _replace_playback_data(
        self, loaded: playback_data.PlaybackData, file_name: str | None = None
    ) -> None:
        """Replace file-dependent state while retaining the frame and workspace."""
        # Keep each graph's identity, type and stack so only its data is refreshed.
        panel_layout = tuple(
            (opened.panel_id, opened.view_name, opened.stack)
            for opened in self._open_panels.values()
        )

        self.clock = loaded.clock
        self.series = loaded.series
        self.time_unit = loaded.time_unit
        self.cursor = loaded.cursor
        self.object_name = loaded.object_name
        self.object_id = dict(loaded.metadata_details).get("Object ID", "").strip()
        if file_name is not None:
            self._loaded_file_name = file_name
        self.status_bar.set_file_name(self._loaded_file_name)
        self.status_bar.set_object(self.object_name, self.object_id)
        self.status_bar.set_message("")
        self.frame_context = loaded.frame_context
        # Start the new file's playback schedule at its load time.
        self._last_frame_monotonic_s = time.monotonic()
        self.workspace.update_oem_information(
            loaded.dashboard_context,
            loaded.metadata_details,
            time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(self.clock.t_start)
            ),
            time_utils.datetime_to_iso8601(
                time_utils.tt_s_to_datetime(self.clock.t_end)
            ),
            self.clock.t_start < self.clock.t_end,
        )
        self.frame.Layout()
        self._oem_loaded = True
        self.workspace.set_oem_loaded(True)
        self.control_window.set_playback_enabled(True)
        self._update_time_display()
        if panel_layout:
            for panel_id, view_name, stack in panel_layout:
                # Replace each view in its existing stack slot. Clearing the
                # whole stack first briefly exposes its empty state and forces
                # GTK to relayout every off-screen splitter at the bottom edge.
                self.open_panel_view(view_name, panel_id, stack, force_replace=True)
        else:
            self.open_plots(self._plots)
        self.workspace.draw_initial_graphs()
        wx.CallAfter(self._refresh_graph_stack_layouts)

    def _release_wx_resources(self) -> None:
        """Drop wx wrappers and callbacks after the event loop has stopped."""
        self._view_registry.clear()
        self.control_window = cast(control_window.ControlWindow, None)
        self.status_bar = cast(PlaybackStatusBar, None)
        self.workspace = cast(workspace.Workspace, None)
        self._timer = cast(wx.Timer, None)
        self.frame = cast(wx.Frame, None)
        self.wx_app = cast(wx.App, None)

    def _on_frame_close(self, event: wx.CloseEvent) -> None:
        if not self._closed:
            self._closed = True
            self._timer.Stop()
            try:
                # Releasing panels one by one mutates the scrolling splitter tree
                # while its frame is closing. Let the frame destroy its child
                # windows after their non-window resources have been released.
                for opened in tuple(self._open_panels.values()):
                    self._release_open_view_resources(opened)
                self._open_panels.clear()
                self._open_views.clear()
            finally:
                self.workspace.close()
        event.Skip()

    def _on_timer(self, _event: wx.TimerEvent) -> None:
        if self._closed:
            return
        current_time_s = time.monotonic()
        if self._last_frame_monotonic_s is None or not self.clock.playing:
            self._last_frame_monotonic_s = current_time_s
        else:
            elapsed_s = current_time_s - self._last_frame_monotonic_s
            # Count elapsed frame periods and carry the remainder forward. A
            # slow redraw advances through missed periods once, then draws once.
            frames_due = math.floor(elapsed_s * self._fps + FRAME_COUNT_EPSILON)
            if frames_due > 0:
                frame_time_s = frames_due / self._fps
                self._last_frame_monotonic_s += frame_time_s
                self._in_timer_tick = True
                try:
                    self.clock.tick(frame_time_s)
                finally:
                    self._in_timer_tick = False
        self._update_time_display()

    def _set_playback_fps(self, fps: int) -> None:
        """Set the wx timer interval from the requested playback frame rate."""
        if not control_window.FPS_MIN <= fps <= control_window.FPS_MAX:
            raise ValueError("fps must be between 1 and 30")
        self._fps = fps
        # Round the scheduling interval upward to whole milliseconds; the clock
        # still uses the exact requested frame period above.
        self._tick_interval_ms = (MILLISECONDS_PER_SECOND + fps - 1) // fps
        if self._started and not self._closed:
            # Apply the new cadence immediately while preserving playback state.
            self._timer.Stop()
            if not self._timer.Start(self._tick_interval_ms):
                raise RuntimeError("could not update the wx playback timer")
            self._last_frame_monotonic_s = time.monotonic()

    def _refresh_graph_stack_layouts(self) -> None:
        """Refresh stack scroll ranges after startup layout, unless closing."""
        if self._closed:
            return
        refresh = getattr(self.workspace, "refresh_graph_stack_layouts", None)
        if callable(refresh):
            refresh()

    def _update_time_display(self) -> None:
        if not self._oem_loaded:
            return
        elapsed_s = self.clock.t_now - self.clock.t_start
        utc_timestamp = time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(self.clock.t_now)
        )
        span_s = self.clock.t_end - self.clock.t_start
        progress = (
            0.0 if span_s == 0.0 else (self.clock.t_now - self.clock.t_start) / span_s
        )
        self.control_window.update_playback_state(
            f"Elapsed: {elapsed_s:.{ELAPSED_TIME_DECIMAL_PLACES}f} s\n"
            f"UTC: {utc_timestamp}",
            self.clock.playing,
            self.clock.rate,
        )
        self.workspace.update_timeline(
            progress, utc_timestamp, playing=self.clock.playing
        )
        self.workspace.update_transport_state(self.clock.playing, self.clock.rate)
        self.control_window.update_current_state(self.cursor.lookup(self.clock.t_now))

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
