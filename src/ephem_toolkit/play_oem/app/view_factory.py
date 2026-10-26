"""Registered graph-view factories for the play-oem application."""

from __future__ import annotations

import sys

from ..views import (
    angular_velocity,
    distance,
    direction_change,
    ground_track as ground_track_view,
    ground_station_access as ground_station_access_view,
    ground_station_passes as ground_station_passes_view,
    rtn,
    speed_altitude,
    state_components,
    trajectory3d,
)
from ..views.trajectory3d import selection as trajectory3d_selection
from ..ground_track import (
    GroundTrackPreparationError,
    prepare_ground_track,
)
from .state import PlayerAppState


class ViewFactoryMixin:
    """Create registered views using the current playback and OEM context."""

    _selected_3d_backend: str | None

    def open_ground_track_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
        """Open a Ground Track panel, preparing its static coordinates once per OEM."""
        source = self._ground_track_source
        coordinates = self._ground_track_coordinates
        error_message: str | None = None
        if source is None:
            error_message = "Load an Earth-centered OEM to view its ground track."
        elif coordinates is None:
            try:
                coordinates = prepare_ground_track(
                    source,
                    position_cache=self._station_access_cache.position_cache,
                )
                self._ground_track_coordinates = coordinates
            except GroundTrackPreparationError as error:
                error_message = str(error)

        self._open_view(
            "ground-track",
            lambda panel: ground_track_view.GroundTrackView(
                panel,
                source,
                coordinates,
                self.cursor,
                self.object_name,
                error_message=error_message,
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
        """Open a lazily prepared multi-station access timeline."""
        self._open_view(
            "ground-station-access",
            lambda panel: ground_station_access_view.GroundStationAccessView(
                panel,
                self._ground_track_source if self._oem_loaded else None,
                self.cursor,
                self._ground_stations,
                self.time_unit,
                self.object_name,
                oem_loaded=self._oem_loaded,
                on_seek=self._seek_from_ground_station_timeline,
                on_station_manager=self.workspace.select_ground_stations,
                access_cache=self._station_access_cache,
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
        """Open or focus a pass panel, optionally selecting the requested station."""
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
                self._ground_track_source if self._oem_loaded else None,
                self.cursor,
                self._ground_stations,
                self.object_name,
                oem_loaded=self._oem_loaded,
                on_seek=self._seek_from_ground_station_timeline,
                on_focus_pass=self._focus_ground_station_pass,
                on_station_manager=self.workspace.select_ground_stations,
                access_cache=self._station_access_cache,
                initial_station_id=initial_station_id,
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
