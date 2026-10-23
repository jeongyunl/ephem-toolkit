"""Selection and lazy loading for the 3D trajectory backends."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

from ... import cursor
from .. import base
from ..plotting import MAX_MATPLOTLIB_3D_DISPLAY_POINTS, decimate_indices


def select_segmented_positions(
    positions_km: np.ndarray,
    timestamps_s: np.ndarray,
    segment_ids: np.ndarray,
    bounds: tuple[float, float] | None,
    *,
    maximum: int = MAX_MATPLOTLIB_3D_DISPLAY_POINTS,
) -> tuple[np.ndarray, np.ndarray]:
    """Filter inclusive timestamps before decimation without joining OEM runs."""
    positions = np.asarray(positions_km, dtype=float)
    times = np.asarray(timestamps_s, dtype=float)
    segments = np.asarray(segment_ids, dtype=int)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("positions_km must have shape (N, 3)")
    if times.shape != (len(positions),) or segments.shape != times.shape:
        raise ValueError("timestamps_s and segment_ids must match positions")
    if maximum < 4:
        raise ValueError("maximum must be at least four")
    if bounds is None:
        return np.empty((0, 3), dtype=float), np.empty(0, dtype=int)
    lower, upper = bounds
    if lower > upper:
        raise ValueError("bounds must be ordered")
    first = int(np.searchsorted(times, lower, side="left"))
    last = int(np.searchsorted(times, upper, side="right"))
    selected_positions: list[np.ndarray] = []
    selected_segments: list[np.ndarray] = []
    start = 0
    while start < len(segments):
        segment_id = int(segments[start])
        stop = start + 1
        while stop < len(segments) and segments[stop] == segment_id:
            stop += 1
        left = max(start, first)
        right = min(stop, last)
        if segment_id >= 0 and left < right:
            run = positions[left:right]
            indices = (
                decimate_indices(run, maximum)
                if len(run) > maximum
                else np.arange(len(run))
            )
            selected_positions.append(run[indices])
            selected_segments.append(np.full(len(indices), segment_id, dtype=int))
        start = stop
    if not selected_positions:
        return np.empty((0, 3), dtype=float), np.empty(0, dtype=int)
    return np.concatenate(selected_positions), np.concatenate(selected_segments)


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
