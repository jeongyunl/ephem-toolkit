"""VTK 3D trajectory playback view hosted by wxPython."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import wx
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData, vtkPolyLine
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersGeneral import vtkTransformPolyDataFilter
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

# Load before wx creates its window; native contexts need per-platform checks.
from vtkmodules.vtkRenderingOpenGL2 import vtkOpenGLRenderWindow
from vtkmodules.wx.wxVTKRenderWindowInteractor import wxVTKRenderWindowInteractor

import ephem_toolkit.core.consts as consts
import ephem_toolkit.core.wgs as wgs

from ... import cursor, series, time_unit
from ..plotting import decimate_indices
from .selection import VTKBackendUnavailableError

EARTH_COLOR_RGB: tuple[float, float, float] = (0.12, 0.32, 0.62)
"""Color of the WGS84 Earth."""
EARTH_OPACITY: float = 0.32
"""Opacity of the WGS84 Earth."""
EARTH_POLAR_SCALE: float = 1.0 - wgs.EARTH_FLATTENING
"""WGS84 polar radius divided by the equatorial radius."""
EARTH_RADIUS_KM: float = consts.EARTH_EQUATORIAL_RADIUS_M / 1000.0
"""WGS84 equatorial radius in kilometers."""
MARKER_COLOR_RGB: tuple[float, float, float] = (1.0, 0.26, 0.12)
"""Color of the satellite marker."""
MARKER_RADIUS_KM: float = 90.0
"""Display radius of the satellite marker in kilometers."""
ORBIT_COLOR_RGB: tuple[float, float, float] = (0.28, 0.76, 0.95)
"""Color of the complete orbit polyline."""
TAIL_COLOR_RGB: tuple[float, float, float] = (1.0, 0.72, 0.22)
"""Color of the direction-aware trajectory tail."""
TAIL_SAMPLE_FRACTION: float = 0.1
"""Fraction of the sample count displayed in the trajectory tail."""
TAIL_MINIMUM_SAMPLE_COUNT: int = 2
"""Minimum number of samples considered when selecting tail extent."""


class VTKTrajectory3DView:
    """Render the orbit, WGS84 Earth and cursor marker in an embedded VTK view."""

    name: str = "trajectory3d"

    def __init__(
        self,
        parent: wx.Window,
        oem_cursor: cursor.OemCursor,
        object_name: str,
        frame_context: str,
        playback_rate: Callable[[], float],
    ) -> None:
        """Create a VTK view attached to the supplied wx parent.

        Parameters
        ----------
        parent : wx.Window
            Graph-panel content scroller that owns the render-window widget.
        oem_cursor : cursor.OemCursor
            State lookup used to position the satellite marker.
        object_name : str
            Object name included in the window title.
        frame_context : str
            Reference-frame and origin context included in the window title.
        playback_rate : Callable[[], float]
            Returns the signed rate used to orient the trajectory tail.
        """
        self._parent = parent
        self._cursor = oem_cursor
        self._object_name = object_name
        self._frame_context = frame_context
        self._playback_rate = playback_rate
        self._widget: wxVTKRenderWindowInteractor | None = None
        self._renderer: vtkRenderer | None = None
        self._orbit_actor: vtkActor | None = None
        self._earth_actor: vtkActor | None = None
        self._tail_actor: vtkActor | None = None
        self._tail_poly_data: vtkPolyData | None = None
        self._cursor_actor: vtkActor | None = None
        self._positions_km: np.ndarray | None = None
        self._orbit_display_positions_km: np.ndarray | None = None
        self._orbit_display_segment_ids: np.ndarray | None = None
        self._sample_times_s: np.ndarray | None = None
        self._segment_ids: np.ndarray | None = None

    def build(
        self, orbit_series: series.OrbitSeries, _time_unit: time_unit.TimeUnit
    ) -> wx.Window:
        """Build the VTK scene and return its wx render-window widget.

        Parameters
        ----------
        orbit_series : series.OrbitSeries
            Orbit positions and elapsed times used by the scene.
        _time_unit : time_unit.TimeUnit
            Display unit paired with the shared view contract; unused in 3D.

        Returns
        -------
        wx.Window
            VTK render-window widget embedded in the graph-panel host.

        Raises
        ------
        RuntimeError
            If this view has already been built.
        ValueError
            If the orbit has no finite three-dimensional positions.
        VTKBackendUnavailableError
            If the wx VTK widget cannot be created.
        """
        if self._widget is not None:
            raise RuntimeError("VTK trajectory view has already been built")
        positions_km = np.asarray(orbit_series.position_km, dtype=float)
        if (
            positions_km.ndim != 2
            or positions_km.shape[1] != 3
            or positions_km.shape[0] == 0
            or not np.all(np.isfinite(positions_km))
        ):
            raise ValueError("position_km must be a non-empty finite (N, 3) array")

        try:
            widget = wxVTKRenderWindowInteractor(self._parent, wx.ID_ANY)
        except (ImportError, OSError, RuntimeError) as error:
            raise VTKBackendUnavailableError(
                f"could not create the embedded VTK render window: {error}"
            ) from error

        self._widget = widget
        self._positions_km = positions_km.copy()
        display_positions: list[np.ndarray] = []
        display_segment_ids: list[np.ndarray] = []
        for segment_id in np.unique(orbit_series.segment_ids):
            segment_positions = positions_km[orbit_series.segment_ids == segment_id]
            selected = decimate_indices(segment_positions)
            display_positions.append(segment_positions[selected])
            display_segment_ids.append(np.full(len(selected), segment_id, dtype=int))
        self._orbit_display_positions_km = np.concatenate(display_positions)
        self._orbit_display_segment_ids = np.concatenate(display_segment_ids)
        self._sample_times_s = (
            self._cursor.t_start
            + orbit_series.elapsed_time * _time_unit.get_divisor_s()
        )
        self._segment_ids = orbit_series.segment_ids.copy()
        self._renderer = vtkRenderer()
        self._renderer.SetBackground(0.06, 0.09, 0.15)
        widget.GetRenderWindow().AddRenderer(self._renderer)
        widget.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        widget.Enable(1)

        self._add_earth()
        self._add_orbit()
        self._add_tail()
        self._add_cursor_marker()
        self._renderer.ResetCamera()
        self._renderer.GetActiveCamera().Zoom(1.15)
        return widget

    def update(self, time_s: float) -> None:
        """Update the marker and direction-aware tail from the shared cursor.

        Parameters
        ----------
        time_s : float
            Absolute OEM time in TT seconds since J2000.

        Raises
        ------
        RuntimeError
            If this view has not been built or has already been closed.
        """
        if (
            self._widget is None
            or self._cursor_actor is None
            or self._tail_actor is None
            or self._tail_poly_data is None
            or self._positions_km is None
            or self._sample_times_s is None
        ):
            raise RuntimeError("VTK trajectory view has not been built")

        state = self._cursor.lookup(time_s)
        if state.r_km is None:
            self._cursor_actor.SetVisibility(False)
            self._tail_actor.SetVisibility(False)
        else:
            self._cursor_actor.SetPosition(*(float(value) for value in state.r_km))
            self._cursor_actor.SetVisibility(True)
            tail_positions_km = self._select_tail_positions(time_s, state.r_km)
            self._set_polyline(self._tail_poly_data, tail_positions_km)
            self._tail_actor.SetVisibility(len(tail_positions_km) > 1)

        self._widget.Render()

    def close(self) -> None:
        """Finalize the VTK render window and release scene references."""
        widget = self._widget
        if widget is not None:
            render_window = widget.GetRenderWindow()
            interactor = render_window.GetInteractor()
            if interactor is not None:
                interactor.Disable()
            render_window.Finalize()
            if self._renderer is not None:
                render_window.RemoveRenderer(self._renderer)
            if interactor is not None:
                interactor.SetRenderWindow(None)
                render_window.SetInteractor(None)
        self._widget = None
        self._renderer = None
        self._orbit_actor = None
        self._earth_actor = None
        self._tail_actor = None
        self._tail_poly_data = None
        self._cursor_actor = None
        self._positions_km = None
        self._orbit_display_positions_km = None
        self._orbit_display_segment_ids = None
        self._sample_times_s = None
        self._segment_ids = None

    def validate_render_context(self) -> None:
        """Ensure the shown wx widget successfully initialized its VTK context.

        Raises
        ------
        RuntimeError
            If this view has not been built.
        VTKBackendUnavailableError
            If VTK did not complete its initial render.
        """
        if self._widget is None:
            raise RuntimeError("VTK trajectory view has not been built")

        render_window = self._widget.GetRenderWindow()
        if not render_window.IsA(vtkOpenGLRenderWindow.__name__):
            raise VTKBackendUnavailableError(
                "VTK did not register an OpenGL render-window implementation"
            )

        try:
            self._widget.Refresh()
            wx.YieldIfNeeded()
        except (OSError, RuntimeError) as error:
            raise VTKBackendUnavailableError(
                f"could not initialize the VTK render context: {error}"
            ) from error

        if render_window.GetNeverRendered():
            raise VTKBackendUnavailableError(
                "VTK did not complete its initial render; the OpenGL render "
                "context may be unavailable"
            )

    def _add_earth(self) -> None:
        earth_source = vtkSphereSource()
        earth_source.SetRadius(EARTH_RADIUS_KM)
        earth_source.SetThetaResolution(48)
        earth_source.SetPhiResolution(32)

        earth_transform = vtkTransform()
        earth_transform.Scale(1.0, 1.0, EARTH_POLAR_SCALE)
        earth_filter = vtkTransformPolyDataFilter()
        earth_filter.SetInputConnection(earth_source.GetOutputPort())
        earth_filter.SetTransform(earth_transform)

        earth_mapper = vtkPolyDataMapper()
        earth_mapper.SetInputConnection(earth_filter.GetOutputPort())
        self._earth_actor = vtkActor()
        self._earth_actor.SetMapper(earth_mapper)
        self._earth_actor.GetProperty().SetColor(EARTH_COLOR_RGB)
        self._earth_actor.GetProperty().SetOpacity(EARTH_OPACITY)
        self._get_renderer().AddActor(self._earth_actor)

    def _add_orbit(self) -> None:
        if (
            self._orbit_display_positions_km is None
            or self._orbit_display_segment_ids is None
        ):
            raise RuntimeError("orbit positions are not initialized")
        orbit_mapper = vtkPolyDataMapper()
        orbit_mapper.SetInputData(
            self._create_polyline(
                self._orbit_display_positions_km,
                self._orbit_display_segment_ids,
            )
        )
        self._orbit_actor = vtkActor()
        self._orbit_actor.SetMapper(orbit_mapper)
        self._orbit_actor.GetProperty().SetColor(ORBIT_COLOR_RGB)
        self._orbit_actor.GetProperty().SetLineWidth(2.0)
        self._get_renderer().AddActor(self._orbit_actor)

    def _add_tail(self) -> None:
        self._tail_poly_data = vtkPolyData()
        tail_mapper = vtkPolyDataMapper()
        tail_mapper.SetInputData(self._tail_poly_data)
        self._tail_actor = vtkActor()
        self._tail_actor.SetMapper(tail_mapper)
        self._tail_actor.GetProperty().SetColor(TAIL_COLOR_RGB)
        self._tail_actor.GetProperty().SetLineWidth(3.0)
        self._tail_actor.SetVisibility(False)
        self._get_renderer().AddActor(self._tail_actor)

    def _add_cursor_marker(self) -> None:
        marker_source = vtkSphereSource()
        marker_source.SetRadius(MARKER_RADIUS_KM)
        marker_source.SetThetaResolution(16)
        marker_source.SetPhiResolution(12)
        marker_mapper = vtkPolyDataMapper()
        marker_mapper.SetInputConnection(marker_source.GetOutputPort())
        self._cursor_actor = vtkActor()
        self._cursor_actor.SetMapper(marker_mapper)
        self._cursor_actor.GetProperty().SetColor(MARKER_COLOR_RGB)
        self._get_renderer().AddActor(self._cursor_actor)

    def _select_tail_positions(
        self, time_s: float, cursor_position_km: np.ndarray
    ) -> np.ndarray:
        if (
            self._positions_km is None
            or self._sample_times_s is None
            or self._segment_ids is None
        ):
            raise RuntimeError("orbit positions are not initialized")

        sample_count = len(self._positions_km)
        tail_sample_count = max(
            TAIL_MINIMUM_SAMPLE_COUNT,
            int(np.ceil(sample_count * TAIL_SAMPLE_FRACTION)),
        )
        upper_index = int(np.searchsorted(self._sample_times_s, time_s, side="right"))
        lower_index = max(0, upper_index - 1)
        segment_id = self._segment_ids[lower_index]
        segment_start = int(np.searchsorted(self._segment_ids, segment_id, side="left"))
        segment_end = int(np.searchsorted(self._segment_ids, segment_id, side="right"))
        is_exact_sample = self._sample_times_s[lower_index] == time_s

        if self._playback_rate() >= 0.0:
            start_index = max(segment_start, upper_index - tail_sample_count)
            sample_positions_km = self._positions_km[start_index:upper_index]
            if not is_exact_sample:
                sample_positions_km = np.vstack(
                    (sample_positions_km, cursor_position_km)
                )
        else:
            end_index = min(segment_end, upper_index + tail_sample_count)
            sample_positions_km = np.vstack(
                (cursor_position_km, self._positions_km[upper_index:end_index])
            )
        return np.asarray(sample_positions_km, dtype=float)

    def _set_polyline(self, poly_data: vtkPolyData, positions_km: np.ndarray) -> None:
        updated_data = self._create_polyline(positions_km)
        poly_data.SetPoints(updated_data.GetPoints())
        poly_data.SetLines(updated_data.GetLines())
        poly_data.Modified()

    def _get_renderer(self) -> vtkRenderer:
        if self._renderer is None:
            raise RuntimeError("VTK renderer has not been initialized")
        return self._renderer

    @staticmethod
    def _create_polyline(
        positions_km: np.ndarray,
        segment_ids: np.ndarray | None = None,
    ) -> vtkPolyData:
        poly_data = vtkPolyData()
        points = vtkPoints()
        point_data = np.ascontiguousarray(positions_km, dtype=np.float64)
        points.SetData(numpy_to_vtk(point_data, deep=True))
        cells = vtkCellArray()
        ids = (
            segment_ids
            if segment_ids is not None
            else np.zeros(len(point_data), dtype=int)
        )
        start = 0
        while start < len(point_data):
            stop = start + 1
            while stop < len(point_data) and ids[stop] == ids[start]:
                stop += 1
            if stop - start > 1:
                polyline = vtkPolyLine()
                polyline.GetPointIds().SetNumberOfIds(stop - start)
                for offset, point_index in enumerate(range(start, stop)):
                    polyline.GetPointIds().SetId(offset, point_index)
                cells.InsertNextCell(polyline)
            start = stop
        poly_data.SetPoints(points)
        poly_data.SetLines(cells)
        return poly_data
