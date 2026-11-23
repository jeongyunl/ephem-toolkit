"""3D trajectory view factories for the play-oem player."""

from __future__ import annotations

import sys

from ..views import trajectory3d
from ..views.trajectory3d import selection as trajectory3d_selection
from .player_app_state import PlayerAppState


class Player3dViewFactoryMixin:
    """Open Matplotlib or VTK trajectory panels."""

    def open_trajectory_view(
        self: PlayerAppState,
        panel_id: str | None = None,
        stack: str = "middle",
        force_replace: bool = False,
    ) -> None:
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
