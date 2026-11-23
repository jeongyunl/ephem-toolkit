"""Saved-window, file-state, and configuration persistence for PlayerApp."""

from __future__ import annotations

import warnings

import wx

from .. import config, time_range
from ..saved_state import (
    MAX_RECENT_FILES,
    MAX_STORED_WINDOW_DIMENSION,
    MAX_STORED_WINDOW_POSITION,
    MIN_STORED_WINDOW_DIMENSION,
    MIN_STORED_WINDOW_POSITION,
    FileSettings,
    TimeScrubberSettings,
    normalize_recent_path,
    save_saved_state,
)
from ..views.ground_track import GroundTrackView
from .player_app_state import PlayerAppState
from .player_app_support import EMPTY_GRAPH_VIEW, PLAYER_FRAME_SIZE


class PlayerAppPreferencesMixin:
    """Restore and persist play-oem application preferences."""

    def _capture_saved_window_geometry(self: PlayerAppState) -> None:
        if self._saved_state is None:
            return
        self._saved_state.maximized = self.frame.IsMaximized()
        if self._saved_state.maximized:
            return
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

    def _capture_saved_open_views(self: PlayerAppState) -> None:
        if self._saved_state is None:
            return
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
                self._saved_state.ground_track_xlim = (
                    float(xlim[0]),
                    float(xlim[1]),
                )
                self._saved_state.ground_track_ylim = (
                    float(ylim[0]),
                    float(ylim[1]),
                )
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

    def _saved_state_size(self: PlayerAppState) -> tuple[int, int]:
        if self._saved_state is None:
            return PLAYER_FRAME_SIZE
        return self._saved_state.width, self._saved_state.height

    def _restore_saved_window_size(self: PlayerAppState) -> None:
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
        from .player_app_support import PLAYER_FRAME_MIN_SIZE

        min_width = min(PLAYER_FRAME_MIN_SIZE[0], display_width)
        min_height = min(PLAYER_FRAME_MIN_SIZE[1], display_height)
        self.frame.SetMinSize((min_width, min_height))
        self._saved_state.width = min(
            display_width, max(min_width, self._saved_state.width)
        )
        self._saved_state.height = min(
            display_height, max(min_height, self._saved_state.height)
        )

    def _restore_saved_window_position(self: PlayerAppState) -> None:
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
                0,
                min(saved_x + width, area_x + area_width) - max(saved_x, area_x),
            )
            overlap_height = max(
                0,
                min(saved_y + height, area_y + area_height) - max(saved_y, area_y),
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
        self: PlayerAppState,
        *,
        save_geometry: bool = True,
        save_file_ranges: bool = True,
    ) -> None:
        """Persist state without allowing a state-file error to close the app."""
        self._save_render_rate_config()
        self._save_display_time_zone_config()
        self._save_interpolation_config()
        self._save_ground_stations_config()
        if not self._persist_saved_state or self._saved_state is None:
            return
        if save_file_ranges:
            self._capture_current_file_settings()
        if save_geometry:
            self._capture_saved_window_geometry()
        self._saved_state.recent_files = list(self._recent_oem_paths[:MAX_RECENT_FILES])
        self._capture_saved_open_views()
        try:
            save_saved_state(self._saved_state)
        except OSError as error:
            warnings.warn(
                f"Could not save play-oem state: {error}",
                RuntimeWarning,
                stacklevel=2,
            )

    def _save_render_rate_config(self: PlayerAppState) -> None:
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

    def _save_display_time_zone_config(self: PlayerAppState) -> None:
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

    def _save_interpolation_config(self: PlayerAppState) -> None:
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

    def _save_ground_stations_config(self: PlayerAppState) -> None:
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

    def _capture_current_file_settings(self: PlayerAppState) -> None:
        timeline_slider = getattr(
            getattr(self, "workspace", None),
            "timeline_slider",
            None,
        )
        if (
            self._saved_state is None
            or not self._oem_loaded
            or self._current_oem_path is None
        ):
            return
        settings = self._saved_state.file_settings.setdefault(
            self._current_oem_path, FileSettings()
        )
        loading_current_file = (
            not self._load_state.coverage_complete
            and self._load_state.path is not None
            and normalize_recent_path(self._load_state.path) == self._current_oem_path
        )
        if (
            self._timeline_restore_state.playback_bounds is None
            and not loading_current_file
        ):
            playback = self._timeline_restore_state.metadata_playback
            if not self._timeline_restore_state.loading_locked or playback is None:
                playback = (
                    self.clock.playback_start,
                    self.clock.playback_end,
                )
            settings.playback_range = playback
        settings.plot_range = self.plot_time_range
        if timeline_slider is not None and not loading_current_file:
            viewport = timeline_slider.viewport
            settings.time_scrubber = TimeScrubberSettings(
                current_time_tt=self.clock.t_now,
                viewport_tt=viewport,
            )

    def _restore_file_plot_range(self: PlayerAppState, path: str) -> None:
        """Restore the plot rule, which does not depend on loaded coverage."""
        if self._saved_state is None:
            return
        settings = self._saved_state.file_settings.get(path)
        if settings is None or settings.plot_range is None:
            return
        try:
            self.plot_time_range = time_range.validate_plot_range(settings.plot_range)
        except ValueError as error:
            settings.plot_range = None
            warnings.warn(
                f"Ignoring saved plot range for {path}: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
