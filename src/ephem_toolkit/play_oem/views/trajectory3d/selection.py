"""Selection and lazy loading for the 3D trajectory backends."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ... import cursor
from .. import base

THREE_D_BACKEND_CHOICES: tuple[str, ...] = ("auto", "vtk", "matplotlib")
"""Accepted values for the ``--3d-backend`` option."""

if TYPE_CHECKING:
    import wx

    from .vtk_backend import VTKTrajectory3DView


class VTKBackendUnavailableError(RuntimeError):
    """Raised when the optional VTK wx backend cannot be loaded or created."""


def create_vtk_view(
    parent: wx.Window,
    oem_cursor: cursor.OemCursor,
    object_name: str,
    frame_context: str,
    playback_rate: Callable[[], float],
) -> VTKTrajectory3DView:
    """Create a VTK trajectory view without importing VTK on Matplotlib paths.

    Parameters
    ----------
    parent : wx.Window
        wx graph-panel host that will own the VTK render-window widget.
    oem_cursor : cursor.OemCursor
        State lookup used to position the satellite marker.
    object_name : str
        Object name displayed in the plot context.
    frame_context : str
        Reference-frame and origin description displayed in the plot context.
    playback_rate : Callable[[], float]
        Returns the current signed playback rate for direction-aware tails.

    Returns
    -------
    VTKTrajectory3DView
        A view that embeds VTK in the supplied graph-panel host.

    Raises
    ------
    VTKBackendUnavailableError
        If VTK or its wx rendering integration cannot be imported.
    """
    try:
        from .vtk_backend import VTKTrajectory3DView
    except (ImportError, OSError) as error:
        raise VTKBackendUnavailableError(
            f"could not load VTK's wx/OpenGL integration: {error}"
        ) from error

    return VTKTrajectory3DView(
        parent,
        oem_cursor,
        object_name,
        frame_context,
        playback_rate,
    )


def validate_vtk_render_context(view: base.View) -> None:
    """Verify that an embedded VTK view rendered after its graph panel was shown."""
    from .vtk_backend import VTKTrajectory3DView

    if isinstance(view, VTKTrajectory3DView):
        view.validate_render_context()
