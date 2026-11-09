"""Registered graph-view factories for the play-oem application."""

from __future__ import annotations

import sys

from .. import time_range
from ..views import (
    angular_velocity,
    distance,
    direction_change,
    ground_track as ground_track_view,
    ground_station_access as ground_station_access_view,
    ground_station_passes as ground_station_passes_view,
    ground_station_analysis as ground_station_analysis_view,
    ground_station_pass_track as ground_station_pass_track_view,
    rtn,
    speed_altitude,
    state_components,
    trajectory3d,
)
from ..views.trajectory3d import selection as trajectory3d_selection
from .state import PlayerAppState


class ViewFactoryMixin:
    """Create registered views using the current playback and OEM context."""

    _selected_3d_backend: str | None

    def _open_station_analysis_panel(
        self,
        name: str,
        panel_type: str,
        panel_id: str | None,
        stack: str,
        force_replace: bool,
    ) -> None:
        self._open_view(
            name,
            lambda panel: ground_station_analysis_view.GroundStationAnalysisView(
                panel,
                panel_type,
                self.cursor,
                self._ground_stations,
                self.time_unit,
                self.object_name,
                oem_loaded=self._oem_loaded,
                on_station_manager=self.workspace.select_ground_stations,
                selection_context=self._station_analysis_contexts[stack],
                initial_range=self._resolved_plot_range(),
                display_time_zone=self._display_time_zone,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_station_status_view(
        self, panel_id: str | None = None, stack: str = "middle", force_replace: bool = False
    ) -> None:
        self._open_station_analysis_panel(
            "station-status", "station-status", panel_id, stack, force_replace
        )

    def open_pass_strip_view(
        self, panel_id: str | None = None, stack: str = "middle", force_replace: bool = False
    ) -> None:
        self._open_station_analysis_panel(
            "pass-strip", "pass-strip", panel_id, stack, force_replace
        )

    def open_elevation_profile_view(
        self, panel_id: str | None = None, stack: str = "middle", force_replace: bool = False
    ) -> None:
        self._open_station_analysis_panel(
            "elevation-profile", "elevation-profile", panel_id, stack, force_replace
        )

    def open_azimuth_profile_view(
        self, panel_id: str | None = None, stack: str = "middle", force_replace: bool = False
    ) -> None:
        self._open_station_analysis_panel(
            "azimuth-profile", "azimuth-profile", panel_id, stack, force_replace
        )

    def open_range_profile_view(
        self, panel_id: str | None = None, stack: str = "middle", force_replace: bool = False
    ) -> None:
        self._open_station_analysis_panel(
            "range-profile", "range-profile", panel_id, stack, force_replace
        )

    def _resolved_plot_range(self) -> time_range.ResolvedTimeRange | None:
        return time_range.resolve_plot_range(
            self.plot_time_range,
            (self.clock.t_start, self.clock.t_end),
            (self.clock.playback_start, self.clock.playback_end),
            self.clock.t_now,
        )

    def open_ground_track_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open a Ground Track panel backed by the active OEM store."""
        self._open_view(
            "ground-track",
            lambda panel: ground_track_view.GroundTrackView(
                panel,
                self.object_name,
                minimum_elevation_deg=(
                    self._saved_state.minimum_elevation_deg
                    if self._saved_state is not None
                    else 10
                ),
                projection_name=(
                    self._saved_state.ground_track_projection
                    if self._saved_state
                    else "Robinson"
                ),
                background_style=(
                    self._saved_state.ground_track_background
                    if self._saved_state
                    else "Shaded relief"
                ),
                center_longitude_deg=(
                    self._saved_state.ground_track_center_longitude_deg
                    if self._saved_state
                    else 0.0
                ),
                saved_xlim=(
                    self._saved_state.ground_track_xlim if self._saved_state else None
                ),
                saved_ylim=(
                    self._saved_state.ground_track_ylim if self._saved_state else None
                ),
                stations=self._ground_stations,
                on_open_passes=lambda station_id: self.open_ground_station_passes_view(
                    initial_station_id=station_id
                ),
                on_minimum_elevation=self._set_ground_track_minimum_elevation,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_ground_station_access_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open access analysis for the loaded part of the active plot range."""
        self._open_view(
            "ground-station-access",
            lambda panel: ground_station_access_view.GroundStationAccessView(
                panel,
                self.cursor,
                self._ground_stations,
                self.time_unit,
                self.object_name,
                oem_loaded=self._oem_loaded,
                on_seek=self._seek_from_ground_station_timeline,
                on_station_manager=self.workspace.select_ground_stations,
                selection_context=self._station_analysis_contexts[stack],
                limit_to_range=True,
                initial_range=self._resolved_plot_range(),
                display_time_zone=self._display_time_zone,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_ground_station_passes_view(
        self: PlayerAppState,
        initial_station_id: str | None = None,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or focus passes found in the loaded part of the plot range."""
        if panel_id is None:
            existing = self._open_views.get("ground-station-passes")
            if existing is not None:
                if initial_station_id is not None:
                    select_station = getattr(
                        existing.view, "select_station_by_id", None
                    )
                    if callable(select_station):
                        select_station(initial_station_id)
                existing.panel.SetFocus()
                return
        elif force_replace and initial_station_id is None:
            existing_panel = self._open_panels.get(panel_id)
            if existing_panel is not None:
                initial_station_id = getattr(
                    existing_panel.view, "selected_station_id", None
                )

        self._open_view(
            "ground-station-passes",
            lambda panel: ground_station_passes_view.GroundStationPassesView(
                panel,
                self.cursor,
                self._ground_stations,
                self.object_name,
                oem_loaded=self._oem_loaded,
                on_seek=self._seek_from_ground_station_timeline,
                on_focus_pass=self._focus_ground_station_pass,
                on_station_manager=self.workspace.select_ground_stations,
                selection_context=self._station_analysis_contexts[stack],
                limit_to_range=True,
                initial_range=self._resolved_plot_range(),
                initial_station_id=initial_station_id,
                display_time_zone=self._display_time_zone,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def _open_focused_pass_view(
        self: PlayerAppState,
        name: str,
        view_class: type[ground_station_passes_view.GroundStationPassesView],
        panel_id: str | None,
        stack: str,
        force_replace: bool,
    ) -> None:
        self._open_view(
            name,
            lambda panel: view_class(
                panel,
                self.cursor,
                self._ground_stations,
                self.object_name,
                oem_loaded=self._oem_loaded,
                on_seek=self._seek_from_ground_station_timeline,
                on_focus_pass=self._focus_ground_station_pass,
                on_station_manager=self.workspace.select_ground_stations,
                selection_context=self._station_analysis_contexts[stack],
                limit_to_range=True,
                initial_range=self._resolved_plot_range(),
                display_time_zone=self._display_time_zone,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_pass_list_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        self._open_focused_pass_view(
            "pass-list",
            ground_station_passes_view.GroundStationPassListView,
            panel_id,
            stack,
            force_replace,
        )

    def open_sky_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        self._open_focused_pass_view(
            "sky-view",
            ground_station_passes_view.GroundStationSkyView,
            panel_id,
            stack,
            force_replace,
        )

    def open_pass_ground_track_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        self._open_view(
            "pass-ground-track",
            lambda panel: ground_station_pass_track_view.GroundStationPassTrackView(
                panel,
                self.cursor,
                self._ground_stations,
                oem_loaded=self._oem_loaded,
                selection_context=self._station_analysis_contexts[stack],
                display_time_zone=self._display_time_zone,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_speed_altitude_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the speed and altitude plot."""
        self._open_view(
            "speed-altitude",
            lambda _panel: speed_altitude.SpeedAltitudeView(self.clock.t_start),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_rtn_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the RTN position-delta plot."""
        self._open_view(
            "rtn",
            lambda _panel: rtn.RtnDeltaView(self.clock.t_start, self.object_name),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_angular_velocity_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the angular-velocity plot."""
        self._open_view(
            "angular-velocity",
            lambda _panel: angular_velocity.AngularVelocityView(
                self.clock.t_start, self.object_name
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_direction_change_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the direction-change plot."""
        self._open_view(
            "direction-change",
            lambda _panel: direction_change.DirectionChangeView(
                self.clock.t_start, self.object_name
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_distance_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the geocentric-distance plot."""
        self._open_view(
            "distance",
            lambda _panel: distance.GeocentricDistanceView(
                self.clock.t_start, self.object_name
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_state_components_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the Cartesian state-components plot."""
        self._open_view(
            "state-components",
            lambda _panel: state_components.StateComponentsView(
                self.clock.t_start, self.frame_context
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )

    def open_trajectory_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open or raise the selected 3D orbit backend."""
        if self._selected_3d_backend == "matplotlib":
            self._open_matplotlib_trajectory_view(panel_id, stack, force_replace)
            return

        try:
            self._open_view(
                "trajectory-3d",
                lambda panel: trajectory3d_selection.create_vtk_view(
                    panel,
                    self.cursor,
                    self.object_name,
                    self.frame_context,
                    lambda: self.clock.rate,
                ),
                panel_id=panel_id,
                stack=stack,
                force_replace=force_replace,
            )
        except trajectory3d_selection.VTKBackendUnavailableError as error:
            if self._requested_3d_backend == "vtk":
                raise RuntimeError(
                    "the requested VTK 3D backend is unavailable: "
                    f"{error}. Install it with "
                    '`pip install "ephem-toolkit[playback,vtk]"`.'
                ) from error
            print(
                "Warning: VTK 3D backend is unavailable "
                f"({error}); falling back to Matplotlib.",
                file=sys.stderr,
            )
            self._set_3d_backend("matplotlib")
            self._open_matplotlib_trajectory_view(panel_id, stack, force_replace)
            return

        self._set_3d_backend("vtk")

    def _open_matplotlib_trajectory_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        self._open_view(
            "trajectory-3d",
            lambda _panel: trajectory3d.Trajectory3DView(
                self.cursor,
                self.object_name,
                self.frame_context,
            ),
            panel_id=panel_id,
            stack=stack,
            force_replace=force_replace,
        )
        self._set_3d_backend("matplotlib")

    def _set_3d_backend(self: PlayerAppState, backend_name: str) -> None:
        self._selected_3d_backend = backend_name
        self.frame.SetTitle(f"play-oem (3D backend: {backend_name})")
