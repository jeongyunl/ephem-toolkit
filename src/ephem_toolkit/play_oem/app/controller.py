"""wxPython application shell for OEM playback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import gc
import math
import os
from pathlib import Path
import signal
import time
import warnings
from typing import cast

import wx

import ephem_toolkit.core.time_utils as time_utils

from .. import (
    clock,
    config,
    control_window,
    cursor,
    series,
    time_range,
    time_unit,
    workspace,
)
from .. import playback_data
from ..ground_track import GroundTrackCoordinates
from ..saved_state import (
    MAX_RECENT_FILES,
    MAX_STORED_WINDOW_DIMENSION,
    MAX_STORED_WINDOW_POSITION,
    MIN_STORED_WINDOW_DIMENSION,
    MIN_STORED_WINDOW_POSITION,
    RecentFileSettings,
    SavedAppState,
    normalize_recent_path,
    remember_recent_file,
    save_saved_state,
)
from ..views import registry
from ..views.ground_track import GroundTrackView
from ..views.trajectory3d import selection as trajectory3d_selection

from .support import (
    DEFAULT_TICK_INTERVAL_MS,
    EMPTY_GRAPH_LABEL,
    EMPTY_GRAPH_VIEW,
    PLAYER_FRAME_MIN_SIZE,
    PLAYER_FRAME_SIZE,
    _configure_settings_backend_without_session_bus,
    _OpenView,
)
from .view_factory import ViewFactoryMixin
from .playback_actions import PlaybackActionsMixin
from .time_range_actions import TimeRangeActionsMixin, playback_range_plot_rule
from .panel_management import PanelManagementMixin
from .status_bar import PlaybackStatusBar

MILLISECONDS_PER_SECOND = 1000
"""Conversion factor between playback seconds and wx timer milliseconds."""

FRAME_COUNT_EPSILON: float = 1e-9
"""Tolerance in seconds for counting a frame at a timer deadline."""


class PlayerApp(
    ViewFactoryMixin,
    PlaybackActionsMixin,
    TimeRangeActionsMixin,
    PanelManagementMixin,
):
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
        render_rate_fps: int | None = None,
        on_open_file: Callable[[str], playback_data.PlaybackData] | None = None,
        saved_state: SavedAppState | None = None,
        config_path: str | Path | None = None,
        ground_track_source: playback_data.GroundTrackSource | None = None,
        initial_file_path: str | None = None,
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
        render_rate_fps : int | None, optional
            Exact initial render rate; when omitted, infer it from the timer interval.
        saved_state : SavedAppState | None, optional
            App-maintained window and recent-file state to restore and persist.
        config_path : str | Path | None, optional
            User configuration file to update when the render rate changes.
        initial_file_path : str | None, optional
            Path to the successfully loaded initial OEM, added to recent files.

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
        self.clock.set_playback_bounds(self.clock.t_start, self.clock.t_end)
        self.series = series
        self.time_unit = time_unit
        self.cursor = cursor
        self.object_name = object_name
        self.object_id = dict(metadata_details).get("Object ID", "").strip()
        self._loaded_file_name = loaded_file_name
        self.frame_context = frame_context
        self._ground_track_source = ground_track_source
        self._ground_track_coordinates: GroundTrackCoordinates | None = None
        self._tick_interval_ms = tick_interval_ms
        self._config_path = config_path
        self._render_rate_config_dirty = False
        # Keep render-rate FPS separately so timer rounding does not affect clock steps.
        if render_rate_fps is not None and (
            isinstance(render_rate_fps, bool)
            or not isinstance(render_rate_fps, int)
            or not control_window.RENDER_RATE_FPS_MIN
            <= render_rate_fps
            <= control_window.RENDER_RATE_FPS_MAX
        ):
            raise ValueError(
                "render_rate_fps must be between "
                f"{control_window.RENDER_RATE_FPS_MIN} and "
                f"{control_window.RENDER_RATE_FPS_MAX}"
            )
        self._render_rate_fps = (
            render_rate_fps
            if render_rate_fps is not None
            else min(
                control_window.RENDER_RATE_FPS_MAX,
                max(
                    control_window.RENDER_RATE_FPS_MIN,
                    round(MILLISECONDS_PER_SECOND / tick_interval_ms),
                ),
            )
        )
        self._last_frame_monotonic_s: float | None = None
        self._on_open_file_callback = on_open_file
        self._saved_state = saved_state
        self._persist_saved_state = saved_state is not None
        self._recent_oem_paths = (
            list(saved_state.recent_files[:MAX_RECENT_FILES])
            if saved_state is not None
            else []
        )
        if initial_file_path is not None:
            if self._saved_state is not None:
                remember_recent_file(self._saved_state, initial_file_path)
                self._recent_oem_paths = list(self._saved_state.recent_files)
            else:
                normalized_initial_path = normalize_recent_path(initial_file_path)
                self._recent_oem_paths = [
                    normalized_initial_path,
                    *(
                        path
                        for path in self._recent_oem_paths
                        if normalize_recent_path(path) != normalized_initial_path
                    ),
                ][:MAX_RECENT_FILES]
        self._current_oem_path = (
            normalize_recent_path(initial_file_path)
            if initial_file_path is not None and oem_loaded
            else None
        )
        if self._current_oem_path is not None:
            self._restore_recent_file_playback_range(self.clock, self._current_oem_path)
        self.plot_time_range = playback_range_plot_rule()
        if self._current_oem_path is not None:
            self._restore_recent_file_plot_range(self._current_oem_path)
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
        self._view_registry.register_view("ground-track", self.open_ground_track_view)
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
        self._recent_oem_menu: wx.Menu = wx.Menu()
        self._recent_menu_parent: wx.Menu = self._recent_oem_menu
        if hasattr(file_menu, "AppendSubMenu"):
            file_menu.AppendSubMenu(self._recent_oem_menu, "Open &Recent")
        else:
            self._recent_menu_parent = file_menu
        menu_bar.Append(file_menu, "&File")
        self.frame.SetMenuBar(menu_bar)
        self.status_bar = PlaybackStatusBar(self.frame)
        self.status_bar.set_file_name(loaded_file_name)
        if oem_loaded:
            self.status_bar.set_object(self.object_name, self.object_id)
        self.frame.Bind(wx.EVT_MENU, self._on_open_file, id=wx.ID_OPEN)
        self._recent_menu_item_ids: list[int] = []
        self._refresh_recent_files_menu()
        self.workspace: workspace.Workspace = workspace.Workspace(
            self.frame,
            self._seek_to_fraction,
            on_toggle_play=self._toggle_playback,
            on_play_reverse=self._play_reverse_at_current_speed,
            on_play_forward=self._play_forward_at_current_speed,
            on_set_playback_rate=self._set_playback_rate,
            on_step_samples=self._step_samples,
            timeline_enabled=clock.t_start < clock.t_end,
            on_seek_to_time=self._seek_to_time,
            timeline_tooltip_at=self._timeline_tooltip_at,
            context=dashboard_context,
            details=metadata_details,
            view_choices=self._panel_view_choices,
            on_add_graph=self._add_graph_panel,
            status_bar=self.status_bar,
            playback_bounds=(clock.playback_start, clock.playback_end),
            oem_coverage=(clock.t_start, clock.t_end),
            plot_time_range=self.plot_time_range,
            now_s=lambda: self.clock.t_now,
            on_playback_bounds=self._apply_playback_bounds,
            on_plot_endpoint=self._drag_plot_endpoint,
            on_plot_endpoint_mode=self._set_plot_endpoint_mode,
            on_begin_time_range_edit=self._begin_time_range_edit,
        )
        self.control_window: control_window.ControlWindow = (
            control_window.ControlWindow(
                self.workspace.settings_page,
                self._toggle_playback,
                self._reverse_playback,
                on_set_render_rate_fps=self._set_render_rate_fps,
                render_rate_fps=self._render_rate_fps,
                on_step_samples=self._step_samples,
                on_step_seconds=self._step_seconds,
                on_jump_to_start=self._jump_to_start,
                on_jump_to_end=self._jump_to_end,
                accelerator_parent=self.frame,
                state_parent=self.workspace.state_page,
            )
        )
        self.control_window.bind_time_entry(self.workspace.timeline_time_entry)
        self.workspace.set_settings_content(self.control_window.settings_scroller)
        self.workspace.set_state_content(self.control_window.state_scroller)
        self.frame.SetMinSize(PLAYER_FRAME_MIN_SIZE)
        self._restore_saved_window_size()
        self.frame.SetSize(
            self._saved_state_size()
            if self._saved_state is not None
            else PLAYER_FRAME_SIZE
        )
        self._restore_saved_window_position()
        if self._saved_state is not None and self._saved_state.maximized:
            self.frame.Maximize(True)
        self.frame.Bind(wx.EVT_CLOSE, self._on_frame_close)

        self._timer: wx.Timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._in_timer_tick = False
        self._started = False
        self._closed = False
        self._open_views: dict[str, _OpenView] = {}
        self._open_panels: dict[str, _OpenView] = {}
        self._clock_unsubscribe = self.clock.subscribe(self._on_clock_time_changed)
        self.workspace.set_oem_loaded(oem_loaded)
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
        if self._oem_loaded and self._saved_state is not None:
            self._save_application_state(save_geometry=False)
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

    def _on_clock_time_changed(self, time_s: float) -> None:
        """Resolve one shared interval before updating any live view cursors."""
        if self._closed:
            return
        resolved = time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            time_s,
        )
        self._dispatch_time_range(resolved, time_s)

    def _saved_state_size(self) -> tuple[int, int]:
        if self._saved_state is None:
            return PLAYER_FRAME_SIZE
        return self._saved_state.width, self._saved_state.height

    def _restore_saved_window_size(self) -> None:
        """Clamp saved dimensions to the current display before applying them."""
        if self._saved_state is None:
            return
        try:
            area = wx.Display(0).GetClientArea()
            display_width = int(area.width)
            display_height = int(area.height)
        except (AttributeError, RuntimeError, TypeError):
            return
        if display_width <= 0 or display_height <= 0:
            return
        min_width = min(PLAYER_FRAME_MIN_SIZE[0], display_width)
        min_height = min(PLAYER_FRAME_MIN_SIZE[1], display_height)
        self.frame.SetMinSize((min_width, min_height))
        self._saved_state.width = min(
            display_width, max(min_width, self._saved_state.width)
        )
        self._saved_state.height = min(
            display_height, max(min_height, self._saved_state.height)
        )

    def _restore_saved_window_position(self) -> None:
        """Restore the saved position, keeping the window inside a connected display."""
        if self._saved_state is None or self._saved_state.position is None:
            return
        try:
            displays = [
                wx.Display(index).GetClientArea()
                for index in range(wx.Display.GetCount())
            ]
            size = self.frame.GetSize()
            width, height = int(size.width), int(size.height)
        except (AttributeError, RuntimeError, TypeError):
            return
        if not displays or width <= 0 or height <= 0:
            return

        saved_x, saved_y = self._saved_state.position

        def overlap_area(area: object) -> int:
            area_x = int(getattr(area, "x"))
            area_y = int(getattr(area, "y"))
            area_width = int(getattr(area, "width"))
            area_height = int(getattr(area, "height"))
            overlap_width = max(
                0, min(saved_x + width, area_x + area_width) - max(saved_x, area_x)
            )
            overlap_height = max(
                0, min(saved_y + height, area_y + area_height) - max(saved_y, area_y)
            )
            return overlap_width * overlap_height

        try:
            area = max(displays, key=overlap_area)
            area_x, area_y = int(area.x), int(area.y)
            area_width, area_height = int(area.width), int(area.height)
        except (AttributeError, TypeError, ValueError):
            return
        if area_width <= 0 or area_height <= 0:
            return
        x = min(saved_x, area_x + max(0, area_width - width))
        y = min(saved_y, area_y + max(0, area_height - height))
        x = max(area_x, x)
        y = max(area_y, y)
        self.frame.SetPosition((x, y))
        self._saved_state.position = (x, y)

    def _save_application_state(self, *, save_geometry: bool = True) -> None:
        """Persist state safely without allowing a state-file error to close the app."""
        self._save_render_rate_config()
        if not self._persist_saved_state or self._saved_state is None:
            return
        self._save_current_playback_range()
        self._save_current_plot_range()
        if save_geometry:
            self._saved_state.maximized = self.frame.IsMaximized()
            if not self._saved_state.maximized:
                position = self.frame.GetPosition()
                x, y = int(position.x), int(position.y)
                if (
                    MIN_STORED_WINDOW_POSITION
                    <= x
                    <= MAX_STORED_WINDOW_POSITION
                    and MIN_STORED_WINDOW_POSITION
                    <= y
                    <= MAX_STORED_WINDOW_POSITION
                ):
                    self._saved_state.position = (x, y)
                size = self.frame.GetSize()
                width, height = int(size.width), int(size.height)
                if width > 0 and height > 0:
                    self._saved_state.width = min(
                        MAX_STORED_WINDOW_DIMENSION,
                        max(MIN_STORED_WINDOW_DIMENSION, width),
                    )
                    self._saved_state.height = min(
                        MAX_STORED_WINDOW_DIMENSION,
                        max(MIN_STORED_WINDOW_DIMENSION, height),
                    )
        self._saved_state.recent_files = list(self._recent_oem_paths[:MAX_RECENT_FILES])
        for opened in self._open_panels.values():
            view = opened.view
            if isinstance(view, GroundTrackView) and view._axes is not None:
                self._saved_state.ground_track_projection = view.projection_name
                self._saved_state.ground_track_background = view.background_style
                self._saved_state.ground_track_center_longitude_deg = (
                    view.center_longitude_deg
                )
                xlim = view._axes.get_xlim()
                ylim = view._axes.get_ylim()
                self._saved_state.ground_track_xlim = (float(xlim[0]), float(xlim[1]))
                self._saved_state.ground_track_ylim = (float(ylim[0]), float(ylim[1]))
            setter = getattr(opened.view, "set_minimum_elevation", None)
            if setter is not None:
                minimum_elevation = getattr(opened.view, "minimum_elevation_deg", None)
                if isinstance(minimum_elevation, int):
                    self._saved_state.minimum_elevation_deg = minimum_elevation
                break
        if self._oem_loaded:
            self._saved_state.open_plots = [
                opened.view_name
                for opened in self._open_panels.values()
                if opened.view_name != EMPTY_GRAPH_VIEW
            ]
        try:
            save_saved_state(self._saved_state)
        except OSError as error:
            warnings.warn(
                f"Could not save play-oem state: {error}",
                RuntimeWarning,
                stacklevel=2,
            )

    def _save_render_rate_config(self) -> None:
        """Persist a changed render rate to the selected user configuration."""
        if not self._render_rate_config_dirty:
            return
        try:
            config.save_render_rate_fps(
                self._render_rate_fps, self._config_path
            )
        except (OSError, config.ConfigError) as error:
            warnings.warn(
                f"Could not save play-oem render rate: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            self._render_rate_config_dirty = False

    def _save_current_playback_range(self) -> None:
        if (
            self._saved_state is None
            or not self._oem_loaded
            or self._current_oem_path is None
        ):
            return
        settings = self._saved_state.recent_file_settings.setdefault(
            self._current_oem_path, RecentFileSettings()
        )
        settings.playback_range = (
            self.clock.playback_start,
            self.clock.playback_end,
        )

    def _save_current_plot_range(self) -> None:
        if (
            self._saved_state is None
            or not self._oem_loaded
            or self._current_oem_path is None
        ):
            return
        settings = self._saved_state.recent_file_settings.setdefault(
            self._current_oem_path, RecentFileSettings()
        )
        settings.plot_range = self.plot_time_range

    def _restore_recent_file_playback_range(
        self, target_clock: clock.PlaybackClock, path: str
    ) -> None:
        if self._saved_state is None:
            return
        settings = self._saved_state.recent_file_settings.get(path)
        if settings is None or settings.playback_range is None:
            return
        try:
            bounds = time_range.validate_playback_range(
                settings.playback_range, (target_clock.t_start, target_clock.t_end)
            )
        except ValueError as error:
            settings.playback_range = None
            warnings.warn(
                f"Ignoring saved playback range for {path}: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        target_clock.set_playback_bounds(bounds.start_s, bounds.end_s)

    def _restore_recent_file_plot_range(self, path: str) -> None:
        if self._saved_state is None:
            return
        settings = self._saved_state.recent_file_settings.get(path)
        if settings is None or settings.plot_range is None:
            return
        try:
            plot_range = time_range.validate_plot_range(settings.plot_range)
        except ValueError as error:
            settings.plot_range = None
            warnings.warn(
                f"Ignoring saved plot range for {path}: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        self.plot_time_range = plot_range

    def _set_ground_track_minimum_elevation(self, value: int) -> None:
        """Apply the shared mask setting to every open Ground Track panel."""
        if self._saved_state is not None:
            self._saved_state.minimum_elevation_deg = int(value)
        for opened in self._open_panels.values():
            setter = getattr(opened.view, "set_minimum_elevation", None)
            if setter is not None:
                setter(value)

    def _refresh_recent_files_menu(self) -> None:
        """Rebuild recent-file menu items from the current state list."""
        for item_id in self._recent_menu_item_ids:
            self._recent_menu_parent.Delete(item_id)
        self._recent_menu_item_ids.clear()
        for path in self._recent_oem_paths[:MAX_RECENT_FILES]:
            label = f"{os.path.basename(path)} — {path}".replace("&", "&&")
            item = self._recent_menu_parent.Append(wx.ID_ANY, label)
            item_id = item.GetId()
            self._recent_menu_item_ids.append(item_id)
            self.frame.Bind(
                wx.EVT_MENU,
                lambda _event, recent_path=path: self._load_oem_file(recent_path),
                id=item_id,
            )

    def _remember_recent_oem(self, path: str) -> None:
        """Record a successfully loaded OEM and update its menu entry."""
        if self._saved_state is not None:
            remember_recent_file(self._saved_state, path)
            self._recent_oem_paths = list(self._saved_state.recent_files)
        else:
            normalized = normalize_recent_path(path)
            self._recent_oem_paths = [
                normalized,
                *(
                    item
                    for item in self._recent_oem_paths
                    if normalize_recent_path(item) != normalized
                ),
            ][:MAX_RECENT_FILES]
        self._refresh_recent_files_menu()
        self._save_application_state(save_geometry=False)

    def _load_oem_file(self, path: str) -> None:
        """Load an OEM path through the shared open and recent-file workflow."""
        if self._on_open_file_callback is None:
            self.status_bar.set_message("Opening another OEM is unavailable.")
            return
        try:
            loaded_data = self._on_open_file_callback(path)
        except Exception as error:
            self.status_bar.set_message(f"Could not open OEM: {error}")
            return
        self._replace_playback_data(loaded_data, os.path.basename(path), path)
        self._remember_recent_oem(path)

    def _on_open_file(self, _event: wx.CommandEvent) -> None:
        """Select an OEM and load it into this playback window."""
        dialog = wx.FileDialog(
            self.frame,
            message="Open OEM file",
            wildcard="OEM files (*.oem, *.OEM)|*.oem;*.OEM|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            defaultDir=(
                os.path.dirname(self._recent_oem_paths[0])
                if self._recent_oem_paths
                else ""
            ),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        finally:
            dialog.Destroy()

        self._load_oem_file(path)

    def _replace_playback_data(
        self,
        loaded: playback_data.PlaybackData,
        file_name: str | None = None,
        file_path: str | None = None,
    ) -> None:
        """Replace file-dependent state while retaining the frame and workspace."""
        self._save_application_state(save_geometry=False)
        rate = self.clock.rate
        loaded.clock.set_playback_bounds(loaded.clock.t_start, loaded.clock.t_end)
        if file_path is not None:
            self._restore_recent_file_playback_range(
                loaded.clock, normalize_recent_path(file_path)
            )
        loaded.clock.set_speed(abs(rate))
        loaded.clock.set_direction(-1 if rate < 0.0 else 1)
        if rate < 0.0:
            loaded.clock.seek(loaded.clock.t_end)
        # Keep each graph's identity, type and stack so only its data is refreshed.
        panel_layout = tuple(
            (opened.panel_id, opened.view_name, opened.stack)
            for opened in self._open_panels.values()
        )

        self._clock_unsubscribe()
        self.clock = loaded.clock
        self._current_oem_path = (
            normalize_recent_path(file_path) if file_path is not None else None
        )
        self._clock_unsubscribe = self.clock.subscribe(self._on_clock_time_changed)
        self.plot_time_range = playback_range_plot_rule()
        if self._current_oem_path is not None:
            self._restore_recent_file_plot_range(self._current_oem_path)
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
        self._ground_track_source = loaded.ground_track_source
        self._ground_track_coordinates = None
        # Start the new file's playback schedule at its load time.
        self._last_frame_monotonic_s = time.monotonic()
        self.workspace.update_oem_information(
            loaded.dashboard_context,
            loaded.metadata_details,
            self.clock.t_start < self.clock.t_end,
        )
        self.frame.Layout()
        self._oem_loaded = True
        self.workspace.set_oem_loaded(True)
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
            self._clock_unsubscribe()
            self._timer.Stop()
            self._save_application_state()
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
            frames_due = math.floor(
                elapsed_s * self._render_rate_fps + FRAME_COUNT_EPSILON
            )
            if frames_due > 0:
                frame_time_s = frames_due / self._render_rate_fps
                self._last_frame_monotonic_s += frame_time_s
                self._in_timer_tick = True
                try:
                    self.clock.tick(frame_time_s)
                finally:
                    self._in_timer_tick = False
        self._update_time_display()

    def _set_render_rate_fps(self, render_rate_fps: int) -> None:
        """Set the wx timer interval from the requested render rate."""
        if not (
            control_window.RENDER_RATE_FPS_MIN
            <= render_rate_fps
            <= control_window.RENDER_RATE_FPS_MAX
        ):
            raise ValueError("render_rate_fps must be between 1 and 30")
        if render_rate_fps != self._render_rate_fps:
            self._render_rate_config_dirty = True
        self._render_rate_fps = render_rate_fps
        # Round the scheduling interval upward to whole milliseconds; the clock
        # still uses the exact requested frame period above.
        self._tick_interval_ms = (
            MILLISECONDS_PER_SECOND + render_rate_fps - 1
        ) // render_rate_fps
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
        utc_timestamp = time_utils.datetime_to_iso8601(
            time_utils.tt_s_to_datetime(self.clock.t_now)
        )
        span_s = self.clock.t_end - self.clock.t_start
        progress = (
            0.0 if span_s == 0.0 else (self.clock.t_now - self.clock.t_start) / span_s
        )
        self.workspace.update_timeline(
            progress, utc_timestamp, playing=self.clock.playing
        )
        self.workspace.set_time_range_controls(
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            self.plot_time_range,
            self.clock.t_now,
        )
        self.workspace.update_playback_state(self.clock.playing, self.clock.rate)
        self.control_window.update_current_state(self.cursor.lookup(self.clock.t_now))

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
