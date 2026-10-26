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

from ephem_toolkit.core.interpolator.interpolation_spec import (
    DEFAULT_HERMITE_DEGREE,
    InterpolationSpec,
    InterpolationType,
)

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
from ..incremental_loader import (
    IncrementalLoader,
    LoadEventKind,
)
from ..ground_track import GroundTrackCoordinates
from ..ground_stations import GroundStation
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
from ..display_time import DISPLAY_TIME_ZONES, format_timestamp_text, format_tt
from ..views import registry
from ..views.ground_track import GroundTrackView
from ..station_access import StationAccessCache
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

INCREMENTAL_VIEW_REFRESH_INTERVAL_S: float = 5.0
"""Maximum rate for rebuilding plots while incremental OEM data is arriving."""

INCREMENTAL_PLOT_MAX_SAMPLES: int = 2_000
"""Point limit used for responsive plot previews during incremental loading."""


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
        display_time_zone: str = "UTC",
        use_oem_interpolation: bool = False,
        interpolation_method: str = InterpolationType.HERMITE.value,
        interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
        oem_interpolation: str | None = None,
        oem_interpolation_degree: int | None = None,
        ground_stations: Sequence[GroundStation] | None = None,
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
        ground_stations : Sequence[GroundStation] | None, optional
            Station definitions loaded from the user configuration file.
        config_path : str | Path | None, optional
            User configuration file to update when settings or stations change.
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
        self._slider_bounds = (clock.t_start, clock.t_end)
        self._playback_handle_bounds = (clock.playback_start, clock.playback_end)
        self._pending_file_playback_bounds: tuple[float, float] | None = None
        self._pending_playback_bounds: tuple[float, float] | None = None
        if display_time_zone not in DISPLAY_TIME_ZONES:
            raise ValueError("display_time_zone must be 'UTC' or 'local'")
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
        self._display_time_zone = display_time_zone
        self._dashboard_context = dict(dashboard_context or {})
        self._metadata_details = tuple(metadata_details)
        self._display_time_zone_config_dirty = False
        self._render_rate_config_dirty = False
        self._interpolation_config_dirty = False
        self._ground_stations_config_dirty = False
        self._use_oem_interpolation = use_oem_interpolation
        self._interpolation_method = interpolation_method
        self._interpolation_degree = interpolation_degree
        self._oem_interpolation = oem_interpolation
        self._oem_interpolation_degree = oem_interpolation_degree
        if oem_loaded:
            self.cursor.set_interpolation(
                (
                    self._oem_interpolation
                    if self._use_oem_interpolation
                    else self._interpolation_method
                ),
                (
                    self._oem_interpolation_degree
                    if self._use_oem_interpolation
                    else self._interpolation_degree
                ),
            )
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
        self._incremental_loader = IncrementalLoader()
        self._incremental_store: playback_data.AppendablePlaybackData | None = None
        self._active_load_generation: int | None = None
        self._active_load_path: str | None = None
        self._active_load_first_batch = False
        self._active_load_failed = False
        self._installing_incremental_batch = False
        self._oem_coverage_complete = oem_loaded
        self._incremental_view_refresh_pending = False
        self._last_incremental_view_refresh_monotonic_s: float | None = None
        self._startup_file_path = initial_file_path if not oem_loaded else None
        self._saved_state = saved_state
        self._ground_stations = (
            list(ground_stations)
            if ground_stations is not None
            else (list(saved_state.ground_stations) if saved_state is not None else [])
        )
        self._station_access_cache = StationAccessCache()
        self._persist_saved_state = saved_state is not None
        self._recent_oem_paths = (
            list(saved_state.recent_files[:MAX_RECENT_FILES])
            if saved_state is not None
            else []
        )
        if initial_file_path is not None and oem_loaded:
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
        self._playback_handle_bounds = (
            self.clock.playback_start,
            self.clock.playback_end,
        )
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
        self._view_registry.register_view(
            "ground-station-access", self.open_ground_station_access_view
        )
        self._view_registry.register_view(
            "ground-station-passes", self.open_ground_station_passes_view
        )
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
            context=self._formatted_dashboard_context(),
            details=self._formatted_metadata_details(),
            view_choices=self._panel_view_choices,
            on_add_graph=self._add_graph_panel,
            status_bar=self.status_bar,
            playback_bounds=(clock.playback_start, clock.playback_end),
            oem_coverage=(clock.t_start, clock.t_end),
            slider_bounds=self._slider_bounds,
            playback_handle_bounds=self._playback_handle_bounds,
            plot_time_range=self.plot_time_range,
            now_s=lambda: self.clock.t_now,
            on_playback_bounds=self._apply_playback_bounds,
            on_plot_endpoint=self._drag_plot_endpoint,
            on_plot_endpoint_mode=self._set_plot_endpoint_mode,
            on_begin_time_range_edit=self._begin_time_range_edit,
            display_time_zone=self._display_time_zone,
            ground_stations=self._ground_stations,
            on_ground_stations_changed=self._update_ground_stations,
        )
        self.control_window: control_window.ControlWindow = (
            control_window.ControlWindow(
                self.workspace.settings_page,
                self._toggle_playback,
                self._reverse_playback,
                on_set_render_rate_fps=self._set_render_rate_fps,
                render_rate_fps=self._render_rate_fps,
                on_set_interpolation=self._set_interpolation_settings,
                use_oem_interpolation=self._use_oem_interpolation,
                interpolation_method=self._interpolation_method,
                interpolation_degree=self._interpolation_degree,
                active_interpolation=self._active_interpolation_summary(),
                display_time_zone=self._display_time_zone,
                on_set_display_time_zone=self._set_display_time_zone,
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
        else:
            self.open_pending_plots(self._plots)
        if self._oem_loaded and self._saved_state is not None:
            self._save_application_state(save_geometry=False)
        self.workspace.draw_initial_graphs()
        # The shown frame's final client size is not available until layout settles;
        # refresh then so each stack gets the correct viewport-sized scroll tail.
        self.frame.Layout()
        wx.CallAfter(self._refresh_graph_stack_layouts)
        wx.CallAfter(self.workspace.focus_neutral_target)
        if self._startup_file_path is not None:
            self._start_incremental_load(self._startup_file_path)
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
        if self._active_load_first_batch and not self._oem_coverage_complete:
            # Coverage extension and playback ticks both notify clock observers.
            # Defer all plot range/cursor updates to the throttled view refresh,
            # which rebuilds each plot from the latest prepared batch.
            if not self._installing_incremental_batch:
                self._incremental_view_refresh_pending = True
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

    def _save_application_state(
        self,
        *,
        save_geometry: bool = True,
        save_file_ranges: bool = True,
    ) -> None:
        """Persist state safely without allowing a state-file error to close the app."""
        self._save_render_rate_config()
        self._save_display_time_zone_config()
        self._save_interpolation_config()
        self._save_ground_stations_config()
        if not self._persist_saved_state or self._saved_state is None:
            return
        if save_file_ranges:
            self._save_current_playback_range()
            self._save_current_plot_range()
        if save_geometry:
            self._saved_state.maximized = self.frame.IsMaximized()
            if not self._saved_state.maximized:
                position = self.frame.GetPosition()
                x, y = int(position.x), int(position.y)
                if (
                    MIN_STORED_WINDOW_POSITION <= x <= MAX_STORED_WINDOW_POSITION
                    and MIN_STORED_WINDOW_POSITION <= y <= MAX_STORED_WINDOW_POSITION
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
            config.save_render_rate_fps(self._render_rate_fps, self._config_path)
        except (OSError, config.ConfigError) as error:
            warnings.warn(
                f"Could not save play-oem render rate: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            self._render_rate_config_dirty = False

    def _save_display_time_zone_config(self) -> None:
        if not self._display_time_zone_config_dirty:
            return
        try:
            config.save_display_time_zone(self._display_time_zone, self._config_path)
        except (OSError, config.ConfigError) as error:
            warnings.warn(
                f"Could not save play-oem display time zone: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            self._display_time_zone_config_dirty = False

    def _set_display_time_zone(self, display_time_zone: str) -> None:
        if display_time_zone == self._display_time_zone:
            return
        self._display_time_zone = display_time_zone
        self._display_time_zone_config_dirty = True
        self.workspace.set_display_time_zone(display_time_zone)
        self.workspace.update_oem_information(
            self._formatted_dashboard_context(),
            self._formatted_metadata_details(),
            self.clock.t_start < self.clock.t_end,
        )
        self._update_time_display()
        for opened in (*self._open_views.values(), *self._open_panels.values()):
            setter = getattr(opened.view, "set_display_time_zone", None)
            if callable(setter):
                setter(display_time_zone)

    def _formatted_dashboard_context(self) -> dict[str, str]:
        context = dict(self._dashboard_context)
        if self._oem_loaded:
            context["time_span"] = (
                f"{format_tt(self.clock.t_start, self._display_time_zone)} – "
                f"{format_tt(self.clock.t_end, self._display_time_zone)}"
            )
        return context

    def _formatted_metadata_details(self) -> tuple[tuple[str, str], ...]:
        timestamp_fields = {"Frame epoch", "Usable start", "Usable stop"}
        return tuple(
            (
                name,
                format_timestamp_text(value, self._display_time_zone)
                if name in timestamp_fields
                else value,
            )
            for name, value in self._metadata_details
        )

    def _save_interpolation_config(self) -> None:
        """Persist changed interpolation settings to the user configuration."""
        if not self._interpolation_config_dirty:
            return
        try:
            config.save_interpolation_settings(
                self._use_oem_interpolation,
                self._interpolation_method,
                self._interpolation_degree,
                self._config_path,
            )
        except (OSError, config.ConfigError) as error:
            warnings.warn(
                f"Could not save play-oem interpolation settings: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            self._interpolation_config_dirty = False

    def _save_ground_stations_config(self) -> None:
        """Persist edited station definitions to the selected user configuration."""
        if not self._ground_stations_config_dirty:
            return
        try:
            config.save_ground_stations(self._ground_stations, self._config_path)
        except (OSError, config.ConfigError) as error:
            warnings.warn(
                f"Could not save play-oem ground stations: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            self._ground_stations_config_dirty = False

    def _save_current_playback_range(self) -> None:
        if (
            self._saved_state is None
            or not self._oem_loaded
            or self._current_oem_path is None
            or self._pending_playback_bounds is not None
            or (
                not self._oem_coverage_complete
                and self._active_load_path is not None
                and normalize_recent_path(self._active_load_path)
                == self._current_oem_path
            )
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

    def _update_ground_stations(self, stations: list[GroundStation]) -> None:
        """Persist station definitions and refresh only already-open access panels."""
        ids = [station.station_id for station in stations]
        if len(ids) != len(set(ids)):
            raise ValueError("ground station IDs must be unique")
        self._ground_stations = list(stations)
        self._ground_stations_config_dirty = True
        self._save_ground_stations_config()
        self._station_access_cache.retain_stations(stations)
        self._refresh_open_ground_station_access()

    def _refresh_open_ground_station_access(self) -> None:
        """Refresh station-aware panels already open in the graph workspace."""
        for opened in tuple(self._open_panels.values()):
            setter = getattr(opened.view, "set_stations", None)
            if callable(setter):
                setter(self._ground_stations)

    def _seek_from_ground_station_timeline(self, time_s: float) -> None:
        """Seek playback from an access timeline click."""
        self.clock.seek(time_s)
        self._update_time_display()

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

    def _remember_recent_oem(
        self, path: str, *, save_file_ranges: bool = True
    ) -> None:
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
        self._save_application_state(
            save_geometry=False, save_file_ranges=save_file_ranges
        )

    def _load_oem_file(self, path: str) -> None:
        """Load an OEM path through the shared open and recent-file workflow."""
        if self._on_open_file_callback is None:
            self._start_incremental_load(path)
            return
        try:
            loaded_data = self._on_open_file_callback(path)
            self._configure_cursor_interpolation(loaded_data.cursor, loaded_data)
        except Exception as error:
            self.status_bar.set_message(f"Could not open OEM: {error}")
            return
        self._replace_playback_data(loaded_data, os.path.basename(path), path)
        self._remember_recent_oem(path)

    def _start_incremental_load(self, path: str) -> None:
        """Start a replacement session while keeping the active OEM installed."""
        preparer = playback_data.IncrementalPlaybackPreparer(
            path,
            use_oem_interpolation=self._use_oem_interpolation,
            interpolation_method=self._interpolation_method,
            interpolation_degree=self._interpolation_degree,
            display_time_zone=self._display_time_zone,
        )
        self._pending_file_playback_bounds = None
        if self._saved_state is not None:
            settings = self._saved_state.recent_file_settings.get(
                normalize_recent_path(path)
            )
            if settings is not None:
                self._pending_file_playback_bounds = settings.playback_range
        session = self._incremental_loader.start(path, prepare_batch=preparer)
        self._active_load_generation = session.generation
        self._active_load_path = path
        self._active_load_first_batch = False
        self._active_load_failed = False
        self._last_incremental_view_refresh_monotonic_s = None
        self.status_bar.set_message(f"Loading {os.path.basename(path)}…")

    def _poll_incremental_load(self) -> None:
        """Install parser events on the wx thread and accumulate progressive data."""
        data_changed = False
        load_completed = False
        for event in self._incremental_loader.drain():
            if event.generation != self._active_load_generation:
                continue
            path = self._active_load_path
            if path is None:
                continue
            if event.kind is LoadEventKind.STARTED:
                continue
            if event.kind is LoadEventKind.BATCH:
                prepared = event.prepared
                if not isinstance(prepared, playback_data.PreparedPlaybackBatch):
                    continue
                try:
                    if not self._active_load_first_batch:
                        loaded = prepared.initial_data
                        if loaded is None:
                            raise RuntimeError("first prepared OEM batch has no initial data")
                        self._incremental_store = prepared.incremental_store
                        self._slider_bounds = prepared.slider_bounds
                        self._replace_playback_data(
                            loaded, os.path.basename(path), path
                        )
                        # The initial panel replacement is also a graph refresh.
                        self._last_incremental_view_refresh_monotonic_s = (
                            time.monotonic()
                        )
                        self._pending_playback_bounds = (
                            self._pending_file_playback_bounds
                        )
                        self._playback_handle_bounds = (
                            self._pending_playback_bounds
                            or (self.clock.playback_start, self.clock.playback_end)
                        )
                        if self._pending_playback_bounds is not None and (
                            self.clock.t_start
                            <= self._pending_playback_bounds[0]
                            and self._pending_playback_bounds[1] <= self.clock.t_end
                        ):
                            self._playback_handle_bounds = (
                                self._pending_playback_bounds
                            )
                            self.clock.set_playback_bounds(
                                *self._pending_playback_bounds
                            )
                            self._pending_playback_bounds = None
                        self._pending_file_playback_bounds = None
                        self._update_time_display()
                        self._active_load_first_batch = True
                        # The incremental clock only covers the loaded prefix.
                        # Do not persist that temporary range over the saved
                        # full-file range before EOF makes it valid to restore.
                        self._remember_recent_oem(path, save_file_ranges=False)
                        self._oem_coverage_complete = False
                    else:
                        self._installing_incremental_batch = True
                        try:
                            self.clock.extend_coverage(prepared.timestamps_s)
                        finally:
                            self._installing_incremental_batch = False
                        self._slider_bounds = prepared.slider_bounds
                        pending_bounds = self._pending_playback_bounds
                        if pending_bounds is not None and (
                            self.clock.t_start <= pending_bounds[0]
                            and pending_bounds[1] <= self.clock.t_end
                        ):
                            self._pending_playback_bounds = None
                            self._playback_handle_bounds = pending_bounds
                            self._installing_incremental_batch = True
                            try:
                                self.clock.set_playback_bounds(*pending_bounds)
                            finally:
                                self._installing_incremental_batch = False
                        elif pending_bounds is None:
                            self._playback_handle_bounds = (
                                self.clock.playback_start,
                                self.clock.playback_end,
                            )
                        self.series = prepared.series
                        self.time_unit = prepared.time_unit
                        self.cursor = prepared.cursor
                        self._ground_track_source = prepared.ground_track_source
                        self._dashboard_context["sample_count"] = str(
                            prepared.source_sample_count
                        )
                        self._dashboard_context["time_span"] = (
                            f"{format_tt(self.clock.t_start, self._display_time_zone)} – "
                            f"{format_tt(self.clock.t_end, self._display_time_zone)}"
                        )
                        self._ground_track_coordinates = None
                        self._station_access_cache.clear()
                        data_changed = True
                        if self._batch_intersects_plot_range(prepared.timestamps_s):
                            self._incremental_view_refresh_pending = True
                except Exception as error:
                    self._active_load_failed = True
                    self._incremental_loader.cancel()
                    self.clock.pause()
                    prefix = (
                        "Loaded a valid prefix, but could not prepare more OEM data: "
                        if self._active_load_first_batch
                        else "Could not open OEM: "
                    )
                    self.status_bar.set_message(prefix + str(error))
                    continue
                self.status_bar.set_message(
                    f"Loading {os.path.basename(path)}: "
                    f"{event.loaded_state_count:,} states (partial coverage)"
                )
            elif event.kind is LoadEventKind.COMPLETE:
                if not self._active_load_first_batch:
                    self.status_bar.set_message("OEM contains no state data.")
                else:
                    self._finish_incremental_metadata(event.completion)
                    self._oem_coverage_complete = True
                    self._active_load_failed = False
                    self.status_bar.set_message("")
                    data_changed = True
                    load_completed = True
            elif event.kind is LoadEventKind.FAILED:
                message = str(event.error) if event.error is not None else "unknown error"
                prefix = (
                    "Loaded a valid prefix, but could not finish reading OEM: "
                    if self._active_load_first_batch
                    else "Could not open OEM: "
                )
                self.clock.pause()
                self._active_load_failed = True
                self.status_bar.set_message(prefix + message)
        if data_changed and self._oem_loaded:
            self.workspace.update_oem_information(
                self._formatted_dashboard_context(),
                self._formatted_metadata_details(),
                self.clock.t_start < self.clock.t_end,
            )
            self._update_time_display()
        if self._incremental_view_refresh_pending:
            self._refresh_incremental_views(force=load_completed)

    def _batch_intersects_plot_range(self, timestamps_s: Sequence[float]) -> bool:
        """Return whether this batch contributes samples to the visible range."""
        bounds = time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            self.clock.t_now,
        )
        return bounds is not None and any(
            bounds.start_s <= timestamp_s <= bounds.end_s
            for timestamp_s in timestamps_s
        )

    def _finish_incremental_metadata(self, completion) -> None:
        """Apply final segment metadata after the stream passes full-file validation."""
        if completion is None:
            return
        meta = dict(completion.meta)
        center_name = str(meta.get("CENTER_NAME", ""))
        frame_name = str(meta.get("REF_FRAME", ""))
        self._oem_interpolation = str(meta.get("INTERPOLATION", "")) or None
        interpolation_degree = meta.get("INTERPOLATION_DEGREE")
        self._oem_interpolation_degree = (
            None if interpolation_degree is None else int(interpolation_degree)
        )
        self._metadata_details = (
            ("Object ID", str(meta.get("OBJECT_ID", ""))),
            ("Time system", str(meta.get("TIME_SYSTEM", ""))),
            ("Frame epoch", str(meta.get("REF_FRAME_EPOCH", ""))),
            ("Usable start", str(meta.get("USEABLE_START_TIME", ""))),
            ("Usable stop", str(meta.get("USEABLE_STOP_TIME", ""))),
            ("Interpolation", self._oem_interpolation or ""),
            (
                "Interpolation degree",
                ""
                if self._oem_interpolation_degree is None
                else str(self._oem_interpolation_degree),
            ),
        )
        self.object_id = dict(self._metadata_details).get("Object ID", "").strip()
        metadata_slider_bounds = playback_data.oem_slider_bounds(
            str(meta.get("START_TIME", "")),
            str(meta.get("STOP_TIME", "")),
            (self.clock.t_start, self.clock.t_end),
        )
        self._slider_bounds = (
            min(self._slider_bounds[0], metadata_slider_bounds[0]),
            max(self._slider_bounds[1], metadata_slider_bounds[1]),
        )
        final_object_name = str(meta.get("OBJECT_NAME", "")).strip()
        if final_object_name:
            self.object_name = final_object_name
        self.status_bar.set_object(self.object_name, self.object_id)
        if self._incremental_store is not None:
            self._incremental_store.center_name = center_name
            self._incremental_store.frame_name = frame_name
            self._incremental_store.ground_track_source = (
                playback_data.GroundTrackSource(
                    self._incremental_store.timestamps_s,
                    self._incremental_store.states_m,
                    self._incremental_store.segment_ids,
                    center_name,
                    frame_name,
                )
            )
            self._ground_track_source = self._incremental_store.ground_track_source
        self.frame_context = " / ".join(
            value for value in (frame_name.strip(), center_name.strip()) if value
        ) or "Frame metadata unavailable"
        self._dashboard_context.update(
            {
                "object": self.object_name,
                "frame": frame_name,
                "center": center_name,
                "time_span": (
                    f"{format_tt(self.clock.t_start, self._display_time_zone)} – "
                    f"{format_tt(self.clock.t_end, self._display_time_zone)}"
                ),
                "sample_count": str(completion.state_count),
            }
        )
        if self._use_oem_interpolation:
            self.cursor.set_interpolation(
                self._oem_interpolation, self._oem_interpolation_degree
            )
        self.control_window.update_active_interpolation(
            self._active_interpolation_summary()
        )
        pending_bounds = self._pending_playback_bounds
        if pending_bounds is None:
            self._restore_recent_file_playback_range(
                self.clock, normalize_recent_path(self._active_load_path or "")
            )
        else:
            if (
                self.clock.t_start <= pending_bounds[0]
                and pending_bounds[1] <= self.clock.t_end
            ):
                self._pending_playback_bounds = None
                self.clock.set_playback_bounds(*pending_bounds)
        self._station_access_cache.clear()
        self._incremental_view_refresh_pending = True

    def _refresh_incremental_views(self, *, force: bool = False) -> None:
        """Rebuild plots at a bounded rate, or immediately when loading ends."""
        now = time.monotonic()
        last_refresh = self._last_incremental_view_refresh_monotonic_s
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
        full_resolution_series = self.series
        if not force and not self._oem_coverage_complete:
            resolved_plot_range = time_range.resolve_plot_range(
                self.plot_time_range,
                (self.clock.t_start, self.clock.t_end),
                (self.clock.playback_start, self.clock.playback_end),
                self.clock.t_now,
            )
            elapsed_bounds = (
                None
                if resolved_plot_range is None
                else (
                    (resolved_plot_range.start_s - self.clock.t_start)
                    / self.time_unit.get_divisor_s(),
                    (resolved_plot_range.end_s - self.clock.t_start)
                    / self.time_unit.get_divisor_s(),
                )
            )
            self.series = series.downsample_orbit_series(
                full_resolution_series,
                INCREMENTAL_PLOT_MAX_SAMPLES,
                elapsed_bounds,
            )
        try:
            if panel_layout:
                for panel_id, view_name, stack in panel_layout:
                    self.open_panel_view(
                        view_name,
                        panel_id,
                        stack,
                        force_replace=True,
                    )
            elif self._oem_loaded:
                self.open_plots(self._plots)
            self.workspace.draw_initial_graphs()
            wx.CallAfter(self._refresh_graph_stack_layouts)
            self._last_incremental_view_refresh_monotonic_s = now
        except Exception as error:
            self.status_bar.set_message(f"Could not refresh OEM views: {error}")
        finally:
            self.series = full_resolution_series
            self._incremental_view_refresh_pending = False

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
        loaded.clock.set_playback_bounds(
            loaded.clock.t_start,
            loaded.clock.t_end,
            follow_coverage=loaded.incremental_store is not None,
        )
        if file_path is not None and loaded.incremental_store is None:
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
        self._playback_handle_bounds = (
            loaded.clock.playback_start,
            loaded.clock.playback_end,
        )
        if loaded.incremental_store is None:
            self._pending_file_playback_bounds = None
            self._pending_playback_bounds = None
        self._slider_bounds = loaded.slider_bounds or (
            loaded.clock.t_start,
            loaded.clock.t_end,
        )
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
        self._oem_interpolation = loaded.oem_interpolation
        self._oem_interpolation_degree = loaded.oem_interpolation_degree
        if loaded.incremental_store is None:
            self._configure_cursor_interpolation(self.cursor, loaded)
        self.object_name = loaded.object_name
        self._dashboard_context = dict(loaded.dashboard_context)
        self._metadata_details = tuple(loaded.metadata_details)
        self.object_id = dict(self._metadata_details).get("Object ID", "").strip()
        if file_name is not None:
            self._loaded_file_name = file_name
        self.status_bar.set_file_name(self._loaded_file_name)
        self.status_bar.set_object(self.object_name, self.object_id)
        self.status_bar.set_message("")
        self.frame_context = loaded.frame_context
        self._ground_track_source = loaded.ground_track_source
        self._incremental_store = loaded.incremental_store
        self._oem_coverage_complete = loaded.incremental_store is None
        self._ground_track_coordinates = None
        # Start the new file's playback schedule at its load time.
        self._last_frame_monotonic_s = time.monotonic()
        self.workspace.update_oem_information(
            self._formatted_dashboard_context(),
            self._formatted_metadata_details(),
            self.clock.t_start < self.clock.t_end,
        )
        self.frame.Layout()
        self._oem_loaded = True
        self.workspace.set_oem_loaded(True)
        self.control_window.update_active_interpolation(
            self._active_interpolation_summary()
        )
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
            self._incremental_loader.cancel()
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
        self._poll_incremental_load()
        current_time_s = time.monotonic()
        if (
            self._active_load_first_batch
            and not self._active_load_failed
            and not self._oem_coverage_complete
            and not self.clock.playing
            and self.clock.t_now >= self.clock.t_end
        ):
            self.status_bar.set_message("Loading more data…")
        if not self.clock.playing:
            self._last_frame_monotonic_s = current_time_s
            return
        if self._last_frame_monotonic_s is None:
            self._last_frame_monotonic_s = current_time_s
            return
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

    def _configure_cursor_interpolation(
        self,
        state_cursor: cursor.OemCursor,
        loaded: playback_data.PlaybackData,
    ) -> None:
        if self._use_oem_interpolation:
            interpolation = loaded.oem_interpolation
            interpolation_degree = loaded.oem_interpolation_degree
        else:
            interpolation = self._interpolation_method
            interpolation_degree = self._interpolation_degree
        state_cursor.set_interpolation(interpolation, interpolation_degree)

    def _set_interpolation_settings(
        self, use_oem_metadata: bool, method: str, degree: int
    ) -> None:
        """Apply interpolation settings immediately and mark them for persistence."""
        if (
            use_oem_metadata == self._use_oem_interpolation
            and method == self._interpolation_method
            and degree == self._interpolation_degree
        ):
            return
        if self._oem_loaded:
            interpolation = self._oem_interpolation if use_oem_metadata else method
            interpolation_degree = (
                self._oem_interpolation_degree if use_oem_metadata else degree
            )
            self.cursor.set_interpolation(interpolation, interpolation_degree)
        self._use_oem_interpolation = use_oem_metadata
        self._interpolation_method = method
        self._interpolation_degree = degree
        self._interpolation_config_dirty = True
        self._station_access_cache.clear()
        self._refresh_open_ground_station_access()
        self.control_window.update_active_interpolation(
            self._active_interpolation_summary()
        )
        if self._oem_loaded:
            self._update_time_display()

    def _active_interpolation_summary(self) -> str:
        if not self._oem_loaded:
            return "No OEM loaded"
        if self._use_oem_interpolation:
            interpolation = (self._oem_interpolation or "").strip().lower()
            degree = self._oem_interpolation_degree
            if not interpolation:
                return "Linear (OEM metadata unspecified)"
            if interpolation == "linear":
                return "Linear (OEM metadata)"
            source = "OEM metadata"
        else:
            interpolation = self._interpolation_method
            degree = self._interpolation_degree
            source = "Settings"

        interpolation_type = InterpolationType(interpolation)
        spec = InterpolationSpec(interpolation_type, degree=degree or None)
        return f"{interpolation_type.value.title()}, degree {spec.degree} ({source})"

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
        timestamp = format_tt(self.clock.t_now, self._display_time_zone)
        slider_start, slider_end = self._slider_bounds
        span_s = slider_end - slider_start
        progress = (
            0.0 if span_s == 0.0 else (self.clock.t_now - slider_start) / span_s
        )
        self.workspace.update_timeline(
            progress, timestamp, playing=self.clock.playing
        )
        self.workspace.set_time_range_controls(
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            self.plot_time_range,
            self.clock.t_now,
            self._slider_bounds,
            self._playback_handle_bounds,
        )
        self.workspace.update_playback_state(self.clock.playing, self.clock.rate)
        self.control_window.update_current_state(self.cursor.lookup(self.clock.t_now))

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
