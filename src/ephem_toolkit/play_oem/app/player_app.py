"""wxPython application shell for OEM playback."""

from __future__ import annotations

import gc
import logging
import math
import os
import signal
import time
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from queue import SimpleQueue
from typing import cast

import wx

from ephem_toolkit.core.app_utils import activate_application
from ephem_toolkit.core.interpolator.interpolation_spec import (
    DEFAULT_HERMITE_DEGREE,
    InterpolationSpec,
    InterpolationType,
)

from .. import (
    clock,
    control_window,
    cursor,
    series,
    time_range,
    time_unit,
    time_snapping,
    workspace,
)
from ..display_time import DISPLAY_TIME_ZONES, format_timestamp_text, format_tt
from ..ground_stations import GroundStation
from ..incremental_loader import (
    IncrementalLoader,
)
from ..oem_data_store import (
    OemDataStore,
    RangeHint,
    StoreNotice,
)
from ..saved_state import (
    MAX_RECENT_FILES,
    SavedAppState,
    normalize_recent_path,
    remember_recent_file,
)
from ..station_analysis import StationAnalysisContext, StationAnalysisSelection
from ..views import registry
from ..views.angular_velocity import AngularVelocityView
from ..views.direction_change import DirectionChangeView
from ..views.distance import GeocentricDistanceView
from ..views.ground_track import GroundTrackView
from ..views.ground_station_passes import GroundStationPassListView, GroundStationSkyView
from ..views.rtn import RtnDeltaView
from ..views.speed_altitude import SpeedAltitudeView
from ..views.state_components import StateComponentsView
from ..views.trajectory3d import selection as trajectory3d_selection
from ..views.trajectory3d.mpl_backend import Trajectory3DView
from .player_3d_view_factory import Player3dViewFactoryMixin
from .player_app_preferences import PlayerAppPreferencesMixin
from .player_app_state import (
    LoadState,
    PlayerCoreConfig,
    RefreshState,
    StoreState,
    TimelineRestoreState,
)
from .player_app_support import (
    DEFAULT_TICK_INTERVAL_MS,
    EMPTY_GRAPH_LABEL,
    EMPTY_GRAPH_VIEW,
)
from .player_incremental_loader import (
    PlayerIncrementalLoadingMixin,
)
from .player_incremental_metadata import PlayerIncrementalMetadataMixin
from .player_incremental_snapshot import PlayerIncrementalSnapshotMixin
from .player_panel_management import PanelManagementMixin
from .player_playback_actions import PlaybackActionsMixin
from .player_standard_plot_factory import PlayerStandardPlotFactoryMixin
from .player_store_view_refresh import PlayerStoreViewRefreshMixin
from .player_time_range_actions import (
    TimeRangeActionsMixin,
    playback_range_plot_rule,
)
from .player_timeline_restore import PlayerTimelineRestoreMixin
from .player_view_factory import PlayerViewFactoryMixin
from .player_wx_ui import PlayerWxUiMixin
from .status_bar import PlaybackStatusBar

MILLISECONDS_PER_SECOND = 1000
"""Conversion factor between playback seconds and wx timer milliseconds."""

FRAME_COUNT_EPSILON: float = 1e-9
"""Tolerance in seconds for counting a frame at a timer deadline."""

_LOGGER = logging.getLogger(__name__)


class PlayerApp(
    PlayerStandardPlotFactoryMixin,
    Player3dViewFactoryMixin,
    PlayerIncrementalSnapshotMixin,
    PlayerIncrementalMetadataMixin,
    PlayerIncrementalLoadingMixin,
    PlayerStoreViewRefreshMixin,
    PlayerTimelineRestoreMixin,
    PlayerAppPreferencesMixin,
    PlayerWxUiMixin,
    PlayerViewFactoryMixin,
    PlaybackActionsMixin,
    TimeRangeActionsMixin,
    PanelManagementMixin,
):
    """Own the wx application, playback timer and playback windows."""

    @staticmethod
    def _validate_initial_options(
        *,
        tick_interval_ms: int,
        render_rate_fps: int | None,
        three_d_backend: str,
        display_time_zone: str,
    ) -> None:
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        if three_d_backend not in trajectory3d_selection.THREE_D_BACKEND_CHOICES:
            raise ValueError(
                "three_d_backend must be one of "
                f"{', '.join(trajectory3d_selection.THREE_D_BACKEND_CHOICES)}"
            )
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
        if display_time_zone not in DISPLAY_TIME_ZONES:
            raise ValueError("display_time_zone must be 'UTC' or 'local'")

    def _initialize_player_core(
        self,
        *,
        config: PlayerCoreConfig,
    ) -> None:
        self._store_state = StoreState()
        self._load_state = LoadState(
            coverage_complete=config.oem_loaded,
        )
        self._timeline_restore_state = TimelineRestoreState(
            playback_bounds=(config.clock.playback_start, config.clock.playback_end)
        )
        self._refresh_state = RefreshState()
        self.clock = config.clock
        self.clock.set_playback_bounds(self.clock.t_start, self.clock.t_end)
        self._slider_bounds = (config.clock.t_start, config.clock.t_end)
        self._playback_handle_bounds = (
            config.clock.playback_start,
            config.clock.playback_end,
        )
        self._timeline_restore_state.playback_bounds = None
        self._load_state.cursor_anchor_s = None
        self.series = config.series
        self.time_unit = config.time_unit
        self.cursor = config.cursor
        self.object_name = config.object_name
        self._loaded_file_name = config.loaded_file_name
        self.object_id = dict(config.metadata_details).get("Object ID", "").strip()
        self.frame_context = config.frame_context
        self._tick_interval_ms = config.tick_interval_ms
        self._config_path = config.config_path
        self._state_path = config.state_path
        self._display_time_zone = config.display_time_zone
        self._time_snapping = config.time_snapping
        self._time_sampling_policy = time_snapping.TimeSamplingPolicy(
            align_to_utc_half_seconds=config.time_snapping
        )
        self._dashboard_context = dict(config.dashboard_context)
        self._metadata_details = config.metadata_details
        self._display_time_zone_config_dirty = False
        self._time_snapping_config_dirty = False
        self._render_rate_config_dirty = False
        self._interpolation_config_dirty = False
        self._ground_stations_config_dirty = False
        self._use_oem_interpolation = config.use_oem_interpolation
        self._interpolation_method = config.interpolation_method
        self._interpolation_degree = config.interpolation_degree
        self._oem_interpolation = config.oem_interpolation
        self._oem_interpolation_degree = config.oem_interpolation_degree
        if config.oem_loaded:
            self.cursor.set_interpolation(
                (
                    self._oem_interpolation
                    if config.use_oem_interpolation
                    else config.interpolation_method
                ),
                self._oem_interpolation_degree
                if config.use_oem_interpolation
                else config.interpolation_degree,
            )
        self._render_rate_fps = (
            config.render_rate_fps
            if config.render_rate_fps is not None
            else min(
                control_window.RENDER_RATE_FPS_MAX,
                max(
                    control_window.RENDER_RATE_FPS_MIN,
                    round(MILLISECONDS_PER_SECOND / config.tick_interval_ms),
                ),
            )
        )
        self._requested_3d_backend = config.three_d_backend
        self._selected_3d_backend = (
            "matplotlib" if config.three_d_backend == "matplotlib" else None
        )
        self._last_frame_monotonic_s = None
        self._load_state.pending_slider_bounds = None
        self._load_state.loading_progress_s = None
        self._playback_handles_fixed_during_load = False
        self._timeline_restore_state.file_playback_bounds = None
        self._timeline_restore_state.file_current_time_s = None
        self._timeline_restore_state.viewport = None
        self._timeline_restore_state.metadata_restored = False
        self._timeline_restore_state.metadata_coverage = None
        self._timeline_restore_state.metadata_playback = None
        self._timeline_restore_state.metadata_viewport = None
        self._timeline_restore_state.loading_locked = False

    def _initialize_store_load_state(self, oem_loaded: bool) -> None:
        self._oem_loaded = oem_loaded
        self._incremental_loader = IncrementalLoader()
        self._store_notice_unsubscribe = lambda: None
        self._store_notice_queue = SimpleQueue[tuple[OemDataStore, StoreNotice]]()
        self._range_dragging = False
        self._installing_incremental_batch = False

    def _initialize_file_state(
        self,
        *,
        saved_state: SavedAppState | None,
        ground_stations: Sequence[GroundStation] | None,
        initial_file_path: str | None,
        oem_loaded: bool,
    ) -> None:
        self._saved_state = saved_state
        self._ground_stations = (
            list(ground_stations)
            if ground_stations is not None
            else (list(saved_state.ground_stations) if saved_state is not None else [])
        )
        self._station_analysis_contexts = {
            "middle": StationAnalysisContext(),
            "right": StationAnalysisContext(),
        }
        self._follow_station_selection = False
        self._follow_selection_unsubscribe = self._station_analysis_contexts[
            "middle"
        ].subscribe(self._on_main_station_selection)
        self._persist_saved_state = saved_state is not None
        self._recent_oem_paths = (
            list(saved_state.recent_files[:MAX_RECENT_FILES])
            if saved_state is not None
            else []
        )
        if initial_file_path is not None and oem_loaded:
            if saved_state is not None:
                remember_recent_file(saved_state, initial_file_path)
                self._recent_oem_paths = list(saved_state.recent_files)
            else:
                normalized = normalize_recent_path(initial_file_path)
                self._recent_oem_paths = [
                    normalized,
                    *(
                        path
                        for path in self._recent_oem_paths
                        if normalize_recent_path(path) != normalized
                    ),
                ][:MAX_RECENT_FILES]
        self._current_oem_path = (
            normalize_recent_path(initial_file_path)
            if initial_file_path is not None and oem_loaded
            else None
        )
        self._startup_file_path = initial_file_path if not oem_loaded else None

    def _initialize_application(
        self,
        *,
        saved_state: SavedAppState | None,
        ground_stations: Sequence[GroundStation] | None,
        initial_file_path: str | None,
        oem_loaded: bool,
        plots: Sequence[str],
        three_d_backend: str,
        theme: str,
        loaded_file_name: str | None,
    ) -> None:
        """Initialize file state, timeline restoration, views, and wx UI."""
        self._initialize_store_load_state(oem_loaded)
        self._initialize_file_state(
            saved_state=saved_state,
            ground_stations=ground_stations,
            initial_file_path=initial_file_path,
            oem_loaded=oem_loaded,
        )
        self.plot_time_range = playback_range_plot_rule()
        if self._oem_loaded and self._current_oem_path is not None:
            self._restore_file_plot_range(self._current_oem_path)
        self._initial_time_scrubber_viewport = (
            self._restore_file_timeline(
                self._current_oem_path,
                self.clock,
            )
            if self._oem_loaded and self._current_oem_path is not None
            else None
        )
        self._initialize_view_registry(plots)
        try:
            self._initialize_wx_ui(
                three_d_backend,
                theme,
                loaded_file_name,
                oem_loaded,
            )
        except BaseException:
            self._rollback_partial_wx_initialization()
            raise

    def __init__(
        self,
        clock: clock.PlaybackClock,
        series: series.OrbitSeries,
        time_unit: time_unit.TimeUnit,
        cursor: cursor.StoreCursor,
        object_name: str,
        frame_context: str,
        *,
        dashboard_context: dict[str, str] | None = None,
        metadata_details: Sequence[tuple[str, str]] = (),
        plots: Sequence[str] = ("overview",),
        three_d_backend: str = "auto",
        theme: str = "system",
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
        render_rate_fps: int | None = None,
        display_time_zone: str = "UTC",
        time_snapping: bool = True,
        use_oem_interpolation: bool = False,
        interpolation_method: str = InterpolationType.HERMITE.value,
        interpolation_degree: int = DEFAULT_HERMITE_DEGREE,
        oem_interpolation: str | None = None,
        oem_interpolation_degree: int | None = None,
        ground_stations: Sequence[GroundStation] | None = None,
        saved_state: SavedAppState | None = None,
        config_path: str | Path | None = None,
        state_path: str | Path | None = None,
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
        cursor : cursor.StoreCursor
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
        state_path : str | Path | None, optional
            Saved-state file to update when window and file settings change.
        initial_file_path : str | None, optional
            Path to the successfully loaded initial OEM, added to recent files.

        Raises
        ------
        ValueError
            If ``tick_interval_ms`` is less than one or the 3D backend is invalid.
        """
        self._validate_initial_options(
            tick_interval_ms=tick_interval_ms,
            render_rate_fps=render_rate_fps,
            three_d_backend=three_d_backend,
            display_time_zone=display_time_zone,
        )
        core_config = PlayerCoreConfig.create(
            clock=clock,
            series=series,
            time_unit=time_unit,
            cursor=cursor,
            object_name=object_name,
            frame_context=frame_context,
            dashboard_context=dict(dashboard_context or {}),
            metadata_details=tuple(metadata_details),
            tick_interval_ms=tick_interval_ms,
            render_rate_fps=render_rate_fps,
            display_time_zone=display_time_zone,
            time_snapping=time_snapping,
            use_oem_interpolation=use_oem_interpolation,
            interpolation_method=interpolation_method,
            interpolation_degree=interpolation_degree,
            oem_interpolation=oem_interpolation,
            oem_interpolation_degree=oem_interpolation_degree,
            oem_loaded=oem_loaded,
            loaded_file_name=loaded_file_name,
            config_path=config_path,
            state_path=state_path,
            three_d_backend=three_d_backend,
        )
        self._initialize_player_core(config=core_config)
        self._initialize_application(
            saved_state=saved_state,
            ground_stations=ground_stations,
            initial_file_path=initial_file_path,
            oem_loaded=oem_loaded,
            plots=plots,
            three_d_backend=three_d_backend,
            theme=theme,
            loaded_file_name=loaded_file_name,
        )

    def _initialize_view_registry(self, plots: Sequence[str]) -> None:
        """Register all graph views and derive startup panel selections."""
        view_groups = (
            registry.ViewGroup("overview", "Overview"),
            registry.ViewGroup("state", "State"),
            registry.ViewGroup("motion", "Motion"),
            registry.ViewGroup("access-overview", "Access Overview"),
            registry.ViewGroup("pass-study", "Pass Study"),
        )
        self._view_registry = registry.ViewRegistry(view_groups)
        view_classes = (
            (Trajectory3DView, self.open_trajectory_view),
            (SpeedAltitudeView, self.open_speed_altitude_view),
            (StateComponentsView, self.open_state_components_view),
            (RtnDeltaView, self.open_rtn_view),
            (AngularVelocityView, self.open_angular_velocity_view),
            (DirectionChangeView, self.open_direction_change_view),
            (GeocentricDistanceView, self.open_distance_view),
            (GroundTrackView, self.open_ground_track_view),
        )
        for view_class, opener in view_classes:
            self._view_registry.register(view_class.view_spec(opener))
        station_view_names = (
            ("elevation-profile", "Elevation Profile", "access-overview", self.open_elevation_profile_view),
            ("azimuth-profile", "Azimuth Profile", "access-overview", self.open_azimuth_profile_view),
            ("range-profile", "Range Profile", "access-overview", self.open_range_profile_view),
        )
        for name, label, group, opener in station_view_names:
            self._view_registry.register(
                registry.ViewSpec(name=name, label=label, group=group, opener=opener)
            )
        pass_view_classes = (
            (GroundStationPassListView, self.open_pass_list_view),
            (GroundStationSkyView, self.open_sky_view),
        )
        for view_class, opener in pass_view_classes:
            self._view_registry.register(view_class.view_spec(opener))
        known_plot_names = set(self._view_registry.registered_views) | {
            "all",
        } | {group.name for group in view_groups}
        unknown_plots: list[str] = []
        recognized_plot_names: list[str] = []
        for item in plots:
            for name in item.split(","):
                normalized = name.strip()
                if normalized in known_plot_names:
                    recognized_plot_names.append(normalized)
                elif normalized:
                    unknown_plots.append(normalized)
        self._unknown_plots = tuple(unknown_plots)
        recognized_plots = tuple(recognized_plot_names)
        self._plots = (
            self._view_registry.expand(recognized_plots) if recognized_plots else ()
        )
        self._panel_view_choices = ((EMPTY_GRAPH_VIEW, EMPTY_GRAPH_LABEL),) + tuple(
            (name, self._view_registry.label_for(name))
            for name in self._view_registry.registered_views
        )

    def _rollback_partial_wx_initialization(self) -> None:
        def release(name: str, action: Callable[[], object]) -> None:
            try:
                action()
            except Exception:
                _LOGGER.exception(
                    "Failed to clean up %s after PlayerApp initialization failed",
                    name,
                )

        clock_unsubscribe = getattr(self, "_clock_unsubscribe", None)
        if clock_unsubscribe is not None:
            release("clock observer", clock_unsubscribe)
        timer = getattr(self, "_timer", None)
        if timer is not None:
            release("playback timer", timer.Stop)
        workspace_instance = getattr(self, "workspace", None)
        if workspace_instance is not None:
            release("workspace", workspace_instance.close)
        frame = getattr(self, "frame", None)
        if frame is not None:
            release("frame", frame.Destroy)

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
        activate_application()
        if self._oem_loaded:
            if self._plots:
                self.open_plots(self._plots)
        else:
            if self._plots:
                self.open_pending_plots(self._plots)
        for name in self._unknown_plots:
            print(f"Error: unknown plot name {name!r}")
            self._add_graph_panel("middle")
        if not self._plots and not self._unknown_plots:
            self._add_graph_panel("middle")
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
        if self._installing_incremental_batch and self._load_state.initial_range_ready:
            resolved = self._resolved_plot_range()
            context = self._store_state.view_context
            if (
                resolved is not None
                and context is not None
                and resolved == context.plot_range
                and resolved.end_s < self.clock.t_end
            ):
                return
        if (
            self._load_state.cursor_anchor_s is not None
            and not self._installing_incremental_batch
        ):
            self._load_state.cursor_anchor_s = None
            self._timeline_restore_state.file_current_time_s = None
        if (
            self._store_state.active is None
            and self._load_state.first_batch
            and not self._load_state.coverage_complete
        ):
            # Coverage extension and playback ticks both notify clock observers.
            # Defer all plot range/cursor updates to the throttled view refresh,
            # which refreshes each plot from the latest store snapshot.
            if not self._installing_incremental_batch:
                self._refresh_state.incremental_view_refresh_pending = True
            return
        resolved = time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            time_s,
        )
        self._dispatch_time_range(resolved, time_s)

    def _set_range_dragging(self, dragging: bool) -> None:
        was_dragging = self._range_dragging
        self._range_dragging = dragging
        self._publish_range_hint()
        if (
            was_dragging
            and not dragging
            and self._refresh_state.incremental_view_refresh_pending
        ):
            self._refresh_incremental_views(force=True)

    @contextmanager
    def _installing_incremental_update(
        self,
    ) -> Generator[None, None, None]:
        was_installing = self._installing_incremental_batch
        self._installing_incremental_batch = True
        try:
            yield
        finally:
            self._installing_incremental_batch = was_installing

    def _publish_range_hint(self) -> None:
        store = self._store_state.active
        if store is None:
            return
        resolved = self._resolved_plot_range()
        store.set_range_hint(
            RangeHint(
                None if resolved is None else (resolved.start_s, resolved.end_s),
                (self.clock.playback_start, self.clock.playback_end),
                self.clock.t_now,
                self._range_dragging,
            )
        )

    def _set_time_snapping(self, enabled: bool) -> None:
        if enabled == self._time_snapping:
            return
        self._time_snapping = enabled
        self._time_sampling_policy.align_to_utc_half_seconds = enabled
        self._time_snapping_config_dirty = True
        if self._store_state.view_context is not None:
            self._queue_store_view_refresh()
            self._refresh_store_views()

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

    def _set_ground_track_minimum_elevation(self, value: int) -> None:
        """Apply the shared mask setting to every open Ground Track panel."""
        if self._saved_state is not None:
            self._saved_state.minimum_elevation_deg = int(value)
        for opened in self._open_panels.values():
            setter = getattr(opened.view, "set_minimum_elevation", None)
            if setter is not None:
                setter(value)

    def _update_ground_stations(self, stations: list[GroundStation]) -> None:
        """Persist station definitions and refresh open station-analysis panels."""
        ids = [station.station_id for station in stations]
        if len(ids) != len(set(ids)):
            raise ValueError("ground station IDs must be unique")
        self._ground_stations = list(stations)
        self._ground_stations_config_dirty = True
        self._save_ground_stations_config()
        station_ids = {station.station_id for station in stations}
        for context in self._station_analysis_contexts.values():
            context.retain_stations(station_ids)
        self._refresh_open_station_views()

    def _open_station_preset(self, name: str) -> None:
        """Open an optional station-analysis preset in Main Analysis."""
        self._view_registry.open_group(name)

    def _set_follow_station_selection(self, enabled: bool) -> None:
        """Link Comparison to Main Analysis only when the user enables it."""
        self._follow_station_selection = enabled
        if enabled:
            self._sync_comparison_station_selection()

    def _on_main_station_selection(self, _selection: StationAnalysisSelection) -> None:
        if self._follow_station_selection:
            self._sync_comparison_station_selection()

    def _sync_comparison_station_selection(self) -> None:
        selection = self._station_analysis_contexts["middle"].selection
        comparison_context = self._station_analysis_contexts["right"]
        comparison_context.select_station(selection.station_id)
        comparison_context.select_interval(selection.interval_key)

    def _refresh_open_station_views(self) -> None:
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

    def _remember_recent_oem(self, path: str, *, save_file_ranges: bool = True) -> None:
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
            if self._range_dragging:
                self._range_dragging = False
                self._publish_range_hint()
            self._refresh_state.incremental_view_refresh_pending = False
            self._refresh_state.pending_store_view_ids.clear()
            self._follow_selection_unsubscribe()
            self._incremental_loader.cancel()
            self._clock_unsubscribe()
            self._store_notice_unsubscribe()
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
                stores = {
                    store
                    for store in (
                        self._store_state.active,
                        self._store_state.pending,
                        self._store_state.retired,
                    )
                    if store is not None
                }
                self._store_notice_unsubscribe()
                for store in stores:
                    store.close()
                self._store_state.active = None
                self._store_state.pending = None
                self._store_state.retired = None
                self._store_state.view_context = None
                self.workspace.close()
        event.Skip()

    def _on_timer(self, _event: wx.TimerEvent) -> None:
        if self._closed:
            return
        self._poll_incremental_load()
        self._drain_store_notices()
        current_time_s = time.monotonic()
        if (
            self._load_state.first_batch
            and not self._load_state.failed
            and not self._load_state.coverage_complete
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
        frames_due = math.floor(elapsed_s * self._render_rate_fps + FRAME_COUNT_EPSILON)
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
        if self._store_state.view_context is not None:
            self._store_state.view_context = self._store_state.view_context.refresh()
            self._queue_store_view_refresh()
            self._publish_range_hint()
        self._refresh_open_station_views()
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
        display_time_s = (
            self._load_state.cursor_anchor_s
            if (
                self._load_state.first_batch
                and not self._load_state.coverage_complete
                and self._load_state.cursor_anchor_s is not None
            )
            else self.clock.t_now
        )
        timeline_coverage, timeline_playback, slider_bounds = (
            self._resolve_timeline_display_bounds()
        )
        slider_start, slider_end = slider_bounds
        span_s = slider_end - slider_start
        progress = 0.0 if span_s == 0.0 else (display_time_s - slider_start) / span_s
        self.workspace.update_timeline(
            progress,
            format_tt(display_time_s, self._display_time_zone),
            playing=self.clock.playing,
        )
        self.workspace.set_time_range_controls(
            timeline_coverage,
            timeline_playback,
            self.plot_time_range,
            display_time_s,
            slider_bounds,
            (
                timeline_playback
                if self._timeline_restore_state.loading_locked
                else self._playback_handle_bounds
            ),
            unloaded_from_s=self._unloaded_loading_progress(),
        )
        self.workspace.update_playback_state(self.clock.playing, self.clock.rate)
        self._update_current_state_display(display_time_s)

    def _resolve_timeline_display_bounds(
        self,
    ) -> tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ]:
        visible_slider = getattr(
            getattr(self, "workspace", None),
            "timeline_slider",
            None,
        )
        viewport = getattr(visible_slider, "viewport", None)
        if (
            isinstance(viewport, tuple)
            and len(viewport) == 2
            and isinstance(viewport[0], (int, float))
            and isinstance(viewport[1], (int, float))
        ):
            slider_start, slider_end = viewport
        else:
            slider_start, slider_end = self._slider_bounds
        timeline_coverage = (self.clock.t_start, self.clock.t_end)
        if self._load_state.first_batch and not self._load_state.coverage_complete:
            timeline_coverage = (
                self._timeline_restore_state.metadata_coverage or timeline_coverage
            )
        timeline_playback = (
            self.clock.playback_start,
            self.clock.playback_end,
        )
        if self._timeline_restore_state.loading_locked:
            if self._timeline_restore_state.metadata_viewport is not None and (
                abs(slider_start - self._timeline_restore_state.metadata_viewport[0])
                > 1e-6
                or abs(slider_end - self._timeline_restore_state.metadata_viewport[1])
                > 1e-6
            ):
                self._timeline_restore_state.loading_locked = False
        if self._timeline_restore_state.loading_locked:
            timeline_coverage = (
                self._timeline_restore_state.metadata_coverage or timeline_coverage
            )
            timeline_playback = (
                self._timeline_restore_state.metadata_playback or timeline_playback
            )
            if self._timeline_restore_state.metadata_viewport is not None:
                slider_start, slider_end = (
                    self._timeline_restore_state.metadata_viewport
                )
        return (
            timeline_coverage,
            timeline_playback,
            (slider_start, slider_end),
        )

    def _unloaded_loading_progress(self) -> float | None:
        if self._load_state.first_batch and not self._load_state.coverage_complete:
            return self._load_state.loading_progress_s
        return None

    def _update_current_state_display(self, display_time_s: float) -> None:
        current_state = (
            self._store_state.view_context.state_at(display_time_s)
            if self._store_state.view_context is not None
            else self.cursor.lookup(display_time_s)
        )
        self.control_window.update_current_state(current_state)

    def _handle_sigint(self, _signum: int, _frame: object) -> None:
        wx.CallAfter(self.close)
