"""Structural state contract shared by PlayerApp behavior mixins."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from queue import SimpleQueue
from typing import TYPE_CHECKING, Protocol

import wx
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg

from .. import (
    clock,
    control_window,
    cursor,
    series,
    time_range,
    time_unit,
    workspace,
)
from ..ground_stations import GroundStation
from ..incremental_loader import IncrementalLoader, LoadEvent
from ..oem_data_store import OemDataStore, StoreSnapshot
from ..saved_state import SavedAppState
from ..station_analysis import StationAnalysisContext
from ..views import base, registry
from ..views.base import StoreViewContext
from .player_app_support import _OpenView

if TYPE_CHECKING:
    from .status_bar import PlaybackStatusBar


@dataclass(frozen=True)
class PlayerCoreConfig:
    """Constructor configuration for one play-oem player instance."""

    clock: clock.PlaybackClock
    """Playback clock shared by the player."""
    series: series.OrbitSeries
    """Computed orbit-series source."""
    time_unit: time_unit.TimeUnit
    """Display unit used by plot views."""
    cursor: cursor.StoreCursor
    """OEM state cursor."""
    object_name: str
    """Object name used in titles and labels."""
    frame_context: str
    """Reference-frame context used by plot views."""
    dashboard_context: dict[str, str]
    """Initial dashboard metadata."""
    metadata_details: tuple[tuple[str, str], ...]
    """Initial OEM metadata details."""
    tick_interval_ms: int
    """wx timer cadence in milliseconds."""
    render_rate_fps: int | None
    """Optional exact render frame rate."""
    display_time_zone: str
    """Display time zone."""
    use_oem_interpolation: bool
    """Whether OEM interpolation metadata should be used."""
    interpolation_method: str
    """Fallback interpolation method."""
    interpolation_degree: int
    """Fallback interpolation degree."""
    oem_interpolation: str | None
    """OEM metadata interpolation method."""
    oem_interpolation_degree: int | None
    """OEM metadata interpolation degree."""
    oem_loaded: bool
    """Whether OEM data is available at startup."""
    loaded_file_name: str | None
    """Initial loaded OEM file name."""
    config_path: str | Path | None
    """Optional play-oem configuration path."""
    state_path: str | Path | None
    """Optional play-oem saved-state path."""
    three_d_backend: str
    """Requested 3D trajectory backend."""

    @classmethod
    def create(
        cls,
        *,
        clock: clock.PlaybackClock,
        series: series.OrbitSeries,
        time_unit: time_unit.TimeUnit,
        cursor: cursor.StoreCursor,
        object_name: str,
        frame_context: str,
        dashboard_context: dict[str, str] | None,
        metadata_details: Sequence[tuple[str, str]],
        tick_interval_ms: int,
        render_rate_fps: int | None,
        display_time_zone: str,
        use_oem_interpolation: bool,
        interpolation_method: str,
        interpolation_degree: int,
        oem_interpolation: str | None,
        oem_interpolation_degree: int | None,
        oem_loaded: bool,
        loaded_file_name: str | None,
        config_path: str | Path | None,
        state_path: str | Path | None,
        three_d_backend: str,
    ) -> "PlayerCoreConfig":
        """Normalize constructor values into immutable core configuration."""
        return cls(
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


@dataclass
class RefreshState:
    """Cohesive state for store and incremental plot refresh scheduling."""

    pending_store_view_ids: set[str] = field(default_factory=set)
    """Panel IDs waiting for a store or incremental refresh."""
    incremental_view_refresh_pending: bool = False
    """Whether a pending refresh should be retained for a later tick."""
    last_incremental_view_refresh_monotonic_s: float | None = None
    """Monotonic timestamp of the latest incremental refresh."""


@dataclass
class LoadState:
    """State owned by progressive OEM loading and snapshot installation."""

    generation: int | None = None
    """Loader-generation identifier for the active OEM file."""
    path: str | None = None
    """Normalized path of the active OEM load."""
    first_batch: bool = False
    """Whether the first usable snapshot is installed."""
    failed: bool = False
    """Whether the active load encountered an installation or parse failure."""
    coverage_complete: bool = True
    """Whether full OEM coverage has been installed."""
    pending_slider_bounds: tuple[float, float] | None = None
    """Slider domain bounds discovered before the first snapshot."""
    loading_progress_s: float | None = None
    """Latest TT timestamp loaded into the active store."""
    cursor_anchor_s: float | None = None
    """Time to preserve while incremental coverage is arriving."""


@dataclass
class TimelineRestoreState:
    """Saved and progressively-restored timeline state."""

    playback_bounds: tuple[float, float] | None = None
    """Playback bounds restored for incremental loading."""
    file_playback_bounds: tuple[float, float] | None = None
    """Per-file playback bounds pending coverage validation."""
    viewport: tuple[float, float] | None = None
    """Viewport bounds restored for the active file."""
    file_current_time_s: float | None = None
    """Current TT time restored for the active file."""
    metadata_restored: bool = False
    """Whether segment metadata has been applied to the scrubber."""
    metadata_coverage: tuple[float, float] | None = None
    """OEM coverage associated with restored metadata."""
    metadata_playback: tuple[float, float] | None = None
    """Playback bounds associated with restored metadata."""
    metadata_viewport: tuple[float, float] | None = None
    """Viewport associated with restored metadata."""
    loading_locked: bool = False
    """Whether timeline controls are locked while metadata is loading."""


@dataclass
class StoreState:
    """Active and pending store ownership."""

    active: OemDataStore | None = None
    """Currently active OEM data store."""
    pending: OemDataStore | None = None
    """Store being populated by the pending incremental load."""
    retired: OemDataStore | None = None
    """Previously active store awaiting retirement."""
    view_context: StoreViewContext | None = None
    """Latest snapshot-bound view context."""


class StorePlayerState(Protocol):
    """Store ownership and notice state required by player mixins."""

    _store_notice_queue: SimpleQueue[tuple[OemDataStore, object]]
    _store_notice_unsubscribe: Callable[[], None]
    _store_state: StoreState


class LoadPlayerState(Protocol):
    """Incremental-load and coverage state required by player mixins."""

    _incremental_loader: IncrementalLoader
    _oem_loaded: bool
    _installing_incremental_batch: bool
    _load_state: LoadState


class TimelinePlayerState(Protocol):
    """Timeline, scrubber, and playback-range state."""

    _slider_bounds: tuple[float, float]
    _playback_handle_bounds: tuple[float, float]
    _playback_handles_fixed_during_load: bool
    plot_time_range: time_range.PlotTimeRange
    _timeline_restore_state: TimelineRestoreState


class RefreshPlayerState(Protocol):
    """View refresh scheduling state."""

    _refresh_state: RefreshState


class PreferencesPlayerState(Protocol):
    """Saved state and configuration ownership."""

    _saved_state: SavedAppState | None
    _persist_saved_state: bool
    _recent_oem_paths: list[str]
    _config_path: object
    _state_path: object
    _render_rate_config_dirty: bool
    _display_time_zone_config_dirty: bool
    _interpolation_config_dirty: bool
    _ground_stations_config_dirty: bool


class PlayerAppState(
    StorePlayerState,
    LoadPlayerState,
    TimelinePlayerState,
    RefreshPlayerState,
    PreferencesPlayerState,
    Protocol,
):
    """Application data and operations required by the extracted mixins."""

    clock: clock.PlaybackClock
    control_window: control_window.ControlWindow
    cursor: cursor.StoreCursor
    frame: wx.Frame
    frame_context: str
    _range_dragging: bool
    _ground_stations: list[GroundStation]
    _station_analysis_contexts: dict[str, StationAnalysisContext]
    object_name: str
    series: series.OrbitSeries
    time_unit: time_unit.TimeUnit
    workspace: workspace.Workspace
    wx_app: wx.App
    _closed: bool
    _in_timer_tick: bool
    _last_frame_monotonic_s: float | None
    """Time of the last consumed playback frame period, from a monotonic clock."""
    _render_rate_fps: int
    _display_time_zone: str
    """Requested render-rate FPS used to calculate each playback time increment."""
    _oem_loaded: bool
    _current_oem_path: str | None
    _use_oem_interpolation: bool
    _interpolation_method: str
    _interpolation_degree: int
    _open_panels: dict[str, _OpenView]
    _open_views: dict[str, _OpenView]
    _clock_unsubscribe: Callable[[], None]
    plot_time_range: time_range.PlotTimeRange
    _panel_view_choices: tuple[tuple[str, str], ...]
    _plots: tuple[str, ...]
    _requested_3d_backend: str
    _selected_3d_backend: str | None
    _started: bool
    status_bar: PlaybackStatusBar
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
    def open_ground_station_access_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_ground_station_passes_view(
        self,
        initial_station_id: str | None = None,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_station_status_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_pass_strip_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_elevation_profile_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_azimuth_profile_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_range_profile_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_pass_list_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_sky_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def open_pass_ground_track_view(
        self,
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
    def _publish_range_hint(self) -> None: ...
    def _queue_store_view_refresh(self, view_ids: set[str] | None = None) -> None: ...
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
    def open_ground_track_view(
        self,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None: ...
    def _set_ground_track_minimum_elevation(self, value: int) -> None: ...
    def _update_ground_stations(self, stations: list[GroundStation]) -> None: ...
    def _seek_from_ground_station_timeline(self, time_s: float) -> None: ...
    def open_panel_view(
        self,
        name: str,
        *,
        panel_id: str,
        stack: str = "middle",
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
    def _set_render_rate_fps(self, render_rate_fps: int) -> None: ...
    def _set_playback_rate(self, rate: float) -> None: ...
    def _play_reverse_at_current_speed(self) -> None: ...
    def _play_forward_at_current_speed(self) -> None: ...
    def _reverse_playback(self) -> None: ...
    def _step_samples(self, count: int) -> None: ...
    def _step_seconds(self, amount_s: float) -> None: ...
    def _jump_to_start(self) -> None: ...
    def _jump_to_end(self) -> None: ...
    def _seek_to_time(self, time_entry_text: str) -> None: ...
    def _dispatch_time_range(
        self,
        resolved: time_range.ResolvedTimeRange | None,
        time_s: float | None = None,
        *,
        dragging: bool | None = None,
    ) -> None: ...
    def _should_defer_incremental_view_refresh(self) -> bool: ...
    def _refresh_incremental_views(self, *, force: bool = False) -> None: ...
    def _poll_incremental_load(self) -> None: ...
    def _handle_segment_metadata_event(self, event: LoadEvent, path: str) -> None: ...
    def _handle_raw_append_event(self, event: LoadEvent, path: str) -> bool: ...
    def _handle_load_complete_event(self, event: LoadEvent) -> tuple[bool, bool]: ...
    def _handle_load_failed_event(self, event: LoadEvent) -> bool: ...
    def _restore_completed_scrubber_state(self) -> None: ...
    def _install_store_snapshot(
        self, store: OemDataStore, snapshot: StoreSnapshot, path: str
    ) -> None: ...
    def _install_first_store_snapshot(
        self,
        store: OemDataStore,
        snapshot: StoreSnapshot,
        path: str,
        meta: dict[str, object],
    ) -> None: ...
    def _advance_store_snapshot(
        self, store: OemDataStore, snapshot: StoreSnapshot
    ) -> None: ...
    def _apply_pending_playback_bounds(self) -> None: ...
    def _close_pending_oem_store(self) -> None: ...
    def _finish_incremental_metadata(self, completion: object) -> None: ...
    def _saved_state_size(self) -> tuple[int, int]: ...
    def _restore_saved_window_size(self) -> None: ...
    def _restore_saved_window_position(self) -> None: ...
    def _save_application_state(
        self,
        *,
        save_geometry: bool = True,
        save_file_ranges: bool = True,
    ) -> None: ...
    def _save_render_rate_config(self) -> None: ...
    def _save_display_time_zone_config(self) -> None: ...
    def _save_interpolation_config(self) -> None: ...
    def _save_ground_stations_config(self) -> None: ...
    def _capture_current_file_settings(self) -> None: ...
    def _restore_file_plot_range(self, path: str) -> None: ...
    def _restore_scrubber_from_metadata(
        self,
        path: str,
        coverage: tuple[float, float],
        *,
        use_defaults_for_invalid_state: bool = False,
    ) -> None: ...
    def _restore_file_timeline(
        self, path: str, target_clock: clock.PlaybackClock
    ) -> tuple[float, float] | None: ...
    def _subscribe_store_notices(self, store: OemDataStore) -> None: ...
    def _drain_store_notices(self) -> None: ...
    def _queue_store_view_refresh(self, view_ids: set[str] | None = None) -> None: ...
    def _refresh_store_views(self) -> None: ...
    def _begin_time_range_edit(self) -> None: ...
    def _apply_playback_bounds(self, start_s: float, end_s: float) -> None: ...
    def _apply_plot_time_range(
        self, rule: time_range.PlotTimeRange, *, dragging: bool = False
    ) -> None: ...
    def _focus_ground_station_pass(self, start_s: float, end_s: float) -> None: ...
    def _set_plot_endpoint_mode(
        self, name: str, mode: time_range.EndpointMode
    ) -> None: ...
    def _is_time_range_panel_visible(self, panel: object) -> bool: ...
    def _queue_time_range_redraw(
        self, panel: object, *, cursor_only: bool = False
    ) -> None: ...
    def _sync_open_panel(self, panel_id: str) -> None: ...
