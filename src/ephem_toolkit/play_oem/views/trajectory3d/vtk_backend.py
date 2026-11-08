"""VTK 3D trajectory playback view hosted by wxPython."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from math import ceil

import numpy as np
import wx
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import (
    vtkCellArray,
    vtkPolyData,
    vtkPolyLine,
    vtkVertex,
)
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
from ...time_range import ResolvedTimeRange
from ..base import StoreViewContext
from ..plotting import MAX_MATPLOTLIB_3D_DISPLAY_POINTS
from .selection import VTKBackendUnavailableError
from .selection import select_segmented_positions

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
        oem_cursor: cursor.OemCursor | None,
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
        self._orbit_mapper: vtkPolyDataMapper | None = None
        self._earth_actor: vtkActor | None = None
        self._tail_actor: vtkActor | None = None
        self._tail_poly_data: vtkPolyData | None = None
        self._orbit_point_data: np.ndarray | None = None
        self._tail_point_data: np.ndarray | None = None
        self._cursor_actor: vtkActor | None = None
        self._positions_km: np.ndarray | None = None
        self._orbit_display_positions_km: np.ndarray | None = None
        self._orbit_display_segment_ids: np.ndarray | None = None
        self._sample_times_s: np.ndarray | None = None
        self._segment_ids: np.ndarray | None = None
        self._range_bounds: ResolvedTimeRange | None = None
        self._range_applied = False
        self._current_time_s = 0.0 if oem_cursor is None else oem_cursor.t_start
        self._store_context: StoreViewContext | None = None
        self._store_positions_m: np.ndarray | None = None
        self._store_sample_times_s: np.ndarray | None = None
        self._store_display_spans: tuple[tuple[int, int], ...] = ()

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
        if self._cursor is None:
            raise RuntimeError("legacy VTK build requires an OEM cursor")
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
        self._sample_times_s = (
            self._cursor.t_start
            + orbit_series.elapsed_time * _time_unit.get_divisor_s()
        )
        self._segment_ids = orbit_series.segment_ids.copy()
        (
            self._orbit_display_positions_km,
            self._orbit_display_segment_ids,
        ) = select_segmented_positions(
            self._positions_km,
            self._sample_times_s,
            self._segment_ids,
            (self._cursor.t_start, self._cursor.t_end),
        )
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

    def build_from_store(self, context: StoreViewContext) -> wx.Window:
        """Build from raw positions, packing only the bounded VTK display path."""
        if self._widget is not None:
            raise RuntimeError("VTK trajectory view has already been built")
        self._store_context = context
        self._range_bounds = context.plot_range
        self._range_applied = True
        self._current_time_s = context.coverage[0]
        self._store_positions_m = context.snapshot.positions_m
        self._store_sample_times_s = context.snapshot.raw[:, 0]
        self._refresh_store_display_path()

        try:
            widget = wxVTKRenderWindowInteractor(self._parent, wx.ID_ANY)
        except (ImportError, OSError, RuntimeError) as error:
            self._store_context = None
            self._store_positions_m = None
            self._store_sample_times_s = None
            self._orbit_display_positions_km = None
            self._store_display_spans = ()
            raise VTKBackendUnavailableError(
                f"could not create the embedded VTK render window: {error}"
            ) from error

        self._widget = widget
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
        if context.snapshot.sample_count:
            self.update(context.coverage[0])
        return widget

    def update_data(
        self, orbit_series: series.OrbitSeries, time_unit: time_unit.TimeUnit
    ) -> bool:
        if self._store_context is not None:
            return False
        if self._cursor is None:
            return False
        positions_km = np.asarray(orbit_series.position_km, dtype=float)
        segment_ids = np.asarray(orbit_series.segment_ids, dtype=int)
        if (
            self._widget is None
            or self._orbit_mapper is None
            or self._orbit_actor is None
            or positions_km.ndim != 2
            or positions_km.shape[1] != 3
            or positions_km.shape[0] == 0
            or not np.all(np.isfinite(positions_km))
            or segment_ids.shape != positions_km.shape[:1]
            or orbit_series.elapsed_time.shape != positions_km.shape[:1]
        ):
            return False

        self._positions_km = positions_km.copy()
        self._sample_times_s = (
            self._cursor.t_start
            + orbit_series.elapsed_time * time_unit.get_divisor_s()
        )
        self._segment_ids = segment_ids.copy()
        if self._range_applied:
            selected_bounds = (
                None
                if self._range_bounds is None
                else (self._range_bounds.start_s, self._range_bounds.end_s)
            )
        else:
            selected_bounds = (self._cursor.t_start, self._cursor.t_end)
        (
            self._orbit_display_positions_km,
            self._orbit_display_segment_ids,
        ) = select_segmented_positions(
            self._positions_km,
            self._sample_times_s,
            self._segment_ids,
            selected_bounds,
        )
        poly_data, self._orbit_point_data = self._create_polyline(
            self._orbit_display_positions_km, self._orbit_display_segment_ids
        )
        self._orbit_mapper.SetInputData(poly_data)
        self._orbit_actor.SetVisibility(len(self._orbit_display_positions_km) > 0)
        return True

    def update_from_store(self, context: StoreViewContext) -> None:
        """Refresh the bounded VTK path from a newer raw snapshot or range."""
        if self._store_context is None or self._widget is None:
            raise RuntimeError("VTK trajectory view was not built from a store")
        self._store_context = context
        self._range_bounds = context.plot_range
        self._store_positions_m = context.snapshot.positions_m
        self._store_sample_times_s = context.snapshot.raw[:, 0]
        self._refresh_store_display_path()
        self._set_store_orbit_input()
        self.update(self._current_time_s)

    def set_time_range(
        self, bounds: ResolvedTimeRange | None, _coverage: tuple[float, float], /
    ) -> None:
        """Filter source positions before decimation without moving the camera."""
        if self._store_context is not None:
            self.update_from_store(
                replace(self._store_context, plot_range=bounds, coverage=_coverage)
            )
            return
        self._range_bounds = bounds
        self._range_applied = True
        if (
            self._positions_km is None
            or self._sample_times_s is None
            or self._segment_ids is None
            or self._orbit_mapper is None
            or self._orbit_actor is None
        ):
            return
        selected_bounds = None if bounds is None else (bounds.start_s, bounds.end_s)
        (
            self._orbit_display_positions_km,
            self._orbit_display_segment_ids,
        ) = select_segmented_positions(
            self._positions_km,
            self._sample_times_s,
            self._segment_ids,
            selected_bounds,
        )
        poly_data, self._orbit_point_data = self._create_polyline(
            self._orbit_display_positions_km, self._orbit_display_segment_ids
        )
        self._orbit_mapper.SetInputData(poly_data)
        self._orbit_actor.SetVisibility(len(self._orbit_display_positions_km) > 0)
        in_range = (
            bounds is not None
            and bounds.start_s <= self._current_time_s <= bounds.end_s
        )
        if not in_range:
            if self._cursor_actor is not None:
                self._cursor_actor.SetVisibility(False)
            if self._tail_actor is not None:
                self._tail_actor.SetVisibility(False)

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
            or (
                self._store_context is None
                and (
                    self._positions_km is None
                    or self._sample_times_s is None
                    or self._segment_ids is None
                )
            )
        ):
            raise RuntimeError("VTK trajectory view has not been built")

        self._current_time_s = time_s
        if self._store_context is not None:
            if self._store_context.snapshot.sample_count == 0:
                self._cursor_actor.SetVisibility(False)
                self._tail_actor.SetVisibility(False)
                self._widget.Render()
                return
            state = self._store_context.store.state_at(
                self._store_context.snapshot, time_s
            )
        elif self._cursor is not None:
            state = self._cursor.lookup(time_s)
        else:
            raise RuntimeError("VTK trajectory view has no active data source")
        in_range = not self._range_applied or (
            self._range_bounds is not None
            and self._range_bounds.start_s <= time_s <= self._range_bounds.end_s
        )
        if state.r_km is None or not in_range:
            self._cursor_actor.SetVisibility(False)
            self._tail_actor.SetVisibility(False)
        else:
            self._cursor_actor.SetPosition(*(float(value) for value in state.r_km))
            self._cursor_actor.SetVisibility(True)
            tail_positions_km = (
                self._select_store_tail_positions(time_s, state.r_km)
                if self._store_context is not None
                else self._select_tail_positions(time_s, state.r_km)
            )
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
        self._orbit_mapper = None
        self._earth_actor = None
        self._tail_actor = None
        self._tail_poly_data = None
        self._orbit_point_data = None
        self._tail_point_data = None
        self._cursor_actor = None
        self._positions_km = None
        self._orbit_display_positions_km = None
        self._orbit_display_segment_ids = None
        self._sample_times_s = None
        self._segment_ids = None
        self._store_context = None
        self._store_positions_m = None
        self._store_sample_times_s = None
        self._store_display_spans = ()

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
        if self._orbit_display_positions_km is None:
            raise RuntimeError("orbit positions are not initialized")
        orbit_mapper = vtkPolyDataMapper()
        if self._store_context is not None:
            poly_data, self._orbit_point_data = self._create_polyline(
                self._orbit_display_positions_km,
                segment_spans=self._store_display_spans,
            )
        elif self._orbit_display_segment_ids is not None:
            poly_data, self._orbit_point_data = self._create_polyline(
                self._orbit_display_positions_km,
                self._orbit_display_segment_ids,
            )
        else:
            raise RuntimeError("orbit segment metadata is not initialized")
        orbit_mapper.SetInputData(poly_data)
        self._orbit_actor = vtkActor()
        self._orbit_actor.SetMapper(orbit_mapper)
        self._orbit_mapper = orbit_mapper
        self._orbit_actor.GetProperty().SetColor(ORBIT_COLOR_RGB)
        self._orbit_actor.GetProperty().SetLineWidth(2.0)
        self._orbit_actor.SetVisibility(len(self._orbit_display_positions_km) > 0)
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
        if self._range_applied:
            if self._range_bounds is None:
                return np.empty((0, 3), dtype=float)
            range_start = int(
                np.searchsorted(
                    self._sample_times_s, self._range_bounds.start_s, side="left"
                )
            )
            range_end = int(
                np.searchsorted(
                    self._sample_times_s, self._range_bounds.end_s, side="right"
                )
            )
            segment_start = max(segment_start, range_start)
            segment_end = min(segment_end, range_end)
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

    def _refresh_store_display_path(self) -> None:
        if (
            self._store_context is None
            or self._store_positions_m is None
            or self._store_sample_times_s is None
        ):
            raise RuntimeError("store-backed orbit positions are not initialized")
        snapshot = self._store_context.snapshot
        bounds = self._store_context.plot_range
        position_views: list[np.ndarray] = []
        segment_spans: list[tuple[int, int]] = []
        first_selected = 0
        last_selected = 0
        if bounds is not None:
            first_selected = int(
                np.searchsorted(
                    self._store_sample_times_s, bounds.start_s, side="left"
                )
            )
            last_selected = int(
                np.searchsorted(
                    self._store_sample_times_s, bounds.end_s, side="right"
                )
            )
        point_offset = 0
        for segment_start, segment_stop in snapshot.segment_bounds:
            first = max(int(segment_start), first_selected)
            stop = min(int(segment_stop), last_selected)
            if first >= stop:
                continue
            count = stop - first
            stride = max(1, ceil(count / MAX_MATPLOTLIB_3D_DISPLAY_POINTS))
            segment_view = self._store_positions_m[first:stop:stride]
            position_views.append(segment_view)
            segment_spans.append((point_offset, point_offset + len(segment_view)))
            point_offset += len(segment_view)
        if position_views:
            display_positions_km = np.concatenate(position_views, axis=0)
            np.multiply(display_positions_km, 0.001, out=display_positions_km)
        else:
            display_positions_km = np.empty((0, 3), dtype=np.float64)
        self._orbit_display_positions_km = display_positions_km
        self._orbit_display_segment_ids = None
        self._store_display_spans = tuple(segment_spans)

    def _set_store_orbit_input(self) -> None:
        if self._orbit_mapper is None or self._orbit_actor is None:
            raise RuntimeError("VTK orbit actor has not been initialized")
        if self._orbit_display_positions_km is None:
            raise RuntimeError("store-backed orbit path is not initialized")
        poly_data, self._orbit_point_data = self._create_polyline(
            self._orbit_display_positions_km,
            segment_spans=self._store_display_spans,
        )
        self._orbit_mapper.SetInputData(poly_data)
        self._orbit_actor.SetVisibility(len(self._orbit_display_positions_km) > 0)

    def _select_store_tail_positions(
        self, time_s: float, cursor_position_km: np.ndarray
    ) -> np.ndarray:
        if (
            self._store_context is None
            or self._store_positions_m is None
            or self._store_sample_times_s is None
        ):
            raise RuntimeError("store-backed orbit positions are not initialized")
        if self._range_bounds is None:
            return np.empty((0, 3), dtype=np.float64)

        sample_count = len(self._store_positions_m)
        upper_index = int(
            np.searchsorted(self._store_sample_times_s, time_s, side="right")
        )
        lower_index = min(max(upper_index - 1, 0), sample_count - 1)
        segment_start = segment_stop = 0
        for first, stop in self._store_context.snapshot.segment_bounds:
            if int(first) <= lower_index < int(stop):
                segment_start, segment_stop = int(first), int(stop)
                break
        if segment_stop <= segment_start:
            return np.empty((0, 3), dtype=np.float64)

        range_start = int(
            np.searchsorted(
                self._store_sample_times_s,
                self._range_bounds.start_s,
                side="left",
            )
        )
        range_stop = int(
            np.searchsorted(
                self._store_sample_times_s,
                self._range_bounds.end_s,
                side="right",
            )
        )
        segment_start = max(segment_start, range_start)
        segment_stop = min(segment_stop, range_stop)
        tail_count = min(
            MAX_MATPLOTLIB_3D_DISPLAY_POINTS,
            max(
                TAIL_MINIMUM_SAMPLE_COUNT,
                int(ceil(sample_count * TAIL_SAMPLE_FRACTION)),
            ),
        )
        is_exact_sample = self._store_sample_times_s[lower_index] == time_s
        if self._playback_rate() >= 0.0:
            first = max(segment_start, upper_index - tail_count)
            stop = min(segment_stop, upper_index)
            source = self._store_positions_m[first:stop]
            includes_cursor = not is_exact_sample
        else:
            first = max(segment_start, upper_index)
            stop = min(segment_stop, upper_index + tail_count)
            source = self._store_positions_m[first:stop]
            includes_cursor = True

        source_limit = MAX_MATPLOTLIB_3D_DISPLAY_POINTS - int(includes_cursor)
        stride = max(1, ceil(len(source) / max(1, source_limit)))
        source = source[::stride]
        cursor_count = 1 if includes_cursor else 0
        if self._playback_rate() >= 0.0:
            result = np.empty((len(source) + cursor_count, 3), dtype=np.float64)
            if len(source):
                np.multiply(source, 0.001, out=result[: len(source)])
            if includes_cursor:
                result[-1] = cursor_position_km
        else:
            result = np.empty((len(source) + 1, 3), dtype=np.float64)
            result[0] = cursor_position_km
            if len(source):
                np.multiply(source, 0.001, out=result[1:])
        return result

    def _set_polyline(self, poly_data: vtkPolyData, positions_km: np.ndarray) -> None:
        updated_data, self._tail_point_data = self._create_polyline(positions_km)
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
        *,
        segment_spans: tuple[tuple[int, int], ...] | None = None,
    ) -> tuple[vtkPolyData, np.ndarray]:
        poly_data = vtkPolyData()
        points = vtkPoints()
        point_data = np.ascontiguousarray(positions_km, dtype=np.float64)
        points.SetData(numpy_to_vtk(point_data, deep=False))
        cells = vtkCellArray()
        vertices = vtkCellArray()
        if segment_spans is not None:
            ranges = segment_spans
        else:
            ids = (
                segment_ids
                if segment_ids is not None
                else np.zeros(len(point_data), dtype=int)
            )
            ranges_list: list[tuple[int, int]] = []
            start = 0
            while start < len(point_data):
                stop = start + 1
                while stop < len(point_data) and ids[stop] == ids[start]:
                    stop += 1
                ranges_list.append((start, stop))
                start = stop
            ranges = tuple(ranges_list)
        for start, stop in ranges:
            if stop - start > 1:
                polyline = vtkPolyLine()
                polyline.GetPointIds().SetNumberOfIds(stop - start)
                for offset, point_index in enumerate(range(start, stop)):
                    polyline.GetPointIds().SetId(offset, point_index)
                cells.InsertNextCell(polyline)
            elif stop - start == 1:
                vertex = vtkVertex()
                vertex.GetPointIds().SetId(0, start)
                vertices.InsertNextCell(vertex)
        poly_data.SetPoints(points)
        poly_data.SetLines(cells)
        poly_data.SetVerts(vertices)
        return poly_data, point_data
