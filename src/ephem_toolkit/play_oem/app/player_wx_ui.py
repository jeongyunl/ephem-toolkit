"""wx UI assembly for the play-oem playback application."""

from __future__ import annotations

import warnings
from typing import cast

import wx

from .. import control_window, workspace
from .player_app_state import PlayerAppState
from .player_app_support import (
    PLAYER_FRAME_MIN_SIZE,
    PLAYER_FRAME_SIZE,
    _configure_settings_backend_without_session_bus,
)
from .status_bar import PlaybackStatusBar


class PlayerWxUiMixin:
    """Create and bind the main wx frame, workspace, controls, and timer."""

    def _initialize_player_frame(
        self: PlayerAppState,
        three_d_backend: str,
        theme: str,
        loaded_file_name: str | None,
        oem_loaded: bool,
    ) -> None:
        _configure_settings_backend_without_session_bus()
        self.wx_app = cast(wx.App, wx.GetApp())
        if self.wx_app is None:
            self.wx_app = wx.App(False)
        set_appearance = getattr(self.wx_app, "SetAppearance", None)
        appearance_enum = getattr(wx.PyApp, "Appearance", None)
        appearance_result = getattr(wx.PyApp, "AppearanceResult", None)
        if set_appearance is None or appearance_enum is None:
            if theme != "system":
                warnings.warn(
                    f"wxPython does not support forcing the {theme!r} theme; "
                    "using the system appearance.",
                    RuntimeWarning,
                    stacklevel=2,
                )
        else:
            result = set_appearance(getattr(appearance_enum, theme.capitalize()))
            if appearance_result is not None and result != appearance_result.Ok:
                if theme != "system":
                    warnings.warn(
                        f"wxPython could not apply the {theme!r} theme; "
                        "using the system appearance.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
        self.frame = wx.Frame(
            None,
            title=f"play-oem (3D backend: {three_d_backend})",
        )
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Open File...\\tCtrl+O")
        self._recent_oem_menu = wx.Menu()
        self._recent_menu_parent = self._recent_oem_menu
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
        self._recent_menu_item_ids = []
        self._refresh_recent_files_menu()

    def _initialize_workspace_and_controls(
        self: PlayerAppState,
    ) -> None:
        self.workspace = workspace.Workspace(
            self.frame,
            self._seek_to_fraction,
            on_toggle_play=self._toggle_playback,
            on_play_reverse=self._play_reverse_at_current_speed,
            on_play_forward=self._play_forward_at_current_speed,
            on_set_playback_rate=self._set_playback_rate,
            on_step_samples=self._step_samples,
            timeline_enabled=self.clock.t_start < self.clock.t_end,
            on_seek_to_time=self._seek_to_time,
            timeline_tooltip_at=self._timeline_tooltip_at,
            context=self._formatted_dashboard_context(),
            details=self._formatted_metadata_details(),
            view_choices=self._panel_view_choices,
            on_add_graph=self._add_graph_panel,
            on_open_preset=self._open_station_preset,
            on_follow_selection=self._set_follow_station_selection,
            status_bar=self.status_bar,
            playback_bounds=(self.clock.playback_start, self.clock.playback_end),
            oem_coverage=(self.clock.t_start, self.clock.t_end),
            slider_bounds=self._slider_bounds,
            playback_handle_bounds=self._playback_handle_bounds,
            time_scrubber_viewport=self._initial_time_scrubber_viewport,
            plot_time_range=self.plot_time_range,
            now_s=lambda: self.clock.t_now,
            on_playback_bounds=self._apply_playback_bounds,
            on_time_range_dragging=self._set_range_dragging,
            on_plot_endpoint=self._drag_plot_endpoint,
            on_plot_endpoint_mode=self._set_plot_endpoint_mode,
            on_begin_time_range_edit=self._begin_time_range_edit,
            display_time_zone=self._display_time_zone,
            ground_stations=self._ground_stations,
            on_ground_stations_changed=self._update_ground_stations,
        )
        self.control_window = control_window.ControlWindow(
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
            time_snapping=self._time_snapping,
            on_set_time_snapping=self._set_time_snapping,
            on_step_samples=self._step_samples,
            on_step_seconds=self._step_seconds,
            on_jump_to_start=self._jump_to_start,
            on_jump_to_end=self._jump_to_end,
            accelerator_parent=self.frame,
            state_parent=self.workspace.state_page,
        )
        self.control_window.bind_time_entry(self.workspace.timeline_time_entry)
        self.workspace.set_settings_content(self.control_window.settings_scroller)
        self.workspace.set_state_content(self.control_window.state_scroller)

    def _initialize_wx_ui(
        self: PlayerAppState,
        three_d_backend: str,
        theme: str,
        loaded_file_name: str | None,
        oem_loaded: bool,
    ) -> None:
        self._initialize_player_frame(
            three_d_backend, theme, loaded_file_name, oem_loaded
        )
        self._initialize_workspace_and_controls()
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

        self._timer = wx.Timer(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._in_timer_tick = False
        self._started = False
        self._closed = False
        self._open_views = {}
        self._open_panels = {}
        self.workspace.set_oem_loaded(oem_loaded)
        if not oem_loaded:
            self.status_bar.set_message("Open an OEM file to begin playback.")
        self._clock_unsubscribe = self.clock.subscribe(self._on_clock_time_changed)
