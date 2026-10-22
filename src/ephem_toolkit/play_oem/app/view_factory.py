"""Registered graph-view factories for the play-oem application."""

from __future__ import annotations

import sys

from ..views import (
    angular_velocity,
    distance,
    direction_change,
    ground_track as ground_track_view,
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
                coordinates = prepare_ground_track(source)
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
                on_minimum_elevation=self._set_ground_track_minimum_elevation,
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
