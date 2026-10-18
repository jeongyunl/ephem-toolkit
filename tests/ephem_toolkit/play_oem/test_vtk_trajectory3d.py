"""Tests for the optional VTK trajectory scene."""

from __future__ import annotations

from importlib import import_module

import numpy as np
import pytest

from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


def test_vtk_backend_registers_an_opengl_render_window_factory() -> None:
    pytest.importorskip("vtk")
    from vtkmodules.vtkRenderingCore import vtkRenderWindow

    import_module("ephem_toolkit.play_oem.views.trajectory3d.vtk_backend")

    render_window = vtkRenderWindow()

    assert render_window.IsA("vtkOpenGLRenderWindow")


class FakeRenderWindow:
    def __init__(self, interactor) -> None:
        self.interactor = interactor
        self.renderers = []
        self.finalized = False
        self.never_rendered = 0
        self.opengl = True

    def AddRenderer(self, renderer) -> None:
        self.renderers.append(renderer)

    def GetNeverRendered(self) -> int:
        return self.never_rendered

    def GetInteractor(self):
        return self.interactor

    def IsA(self, class_name: str) -> bool:
        return class_name == "vtkOpenGLRenderWindow" and self.opengl

    def Finalize(self) -> None:
        self.finalized = True

    def RemoveRenderer(self, renderer) -> None:
        self.renderers.remove(renderer)

    def SetInteractor(self, interactor) -> None:
        self.interactor = interactor


class FakeInteractor:
    def __init__(self) -> None:
        self.disabled = False
        self.render_window = None

    def Disable(self) -> None:
        self.disabled = True

    def SetRenderWindow(self, render_window) -> None:
        self.render_window = render_window


class FakeWidget:
    def __init__(self, _parent, _window_id: int) -> None:
        self.interactor = FakeInteractor()
        self.render_window = FakeRenderWindow(self.interactor)
        self.interactor.render_window = self.render_window
        self.interactor_style = None
        self.enabled = False
        self.render_count = 0

    def GetRenderWindow(self) -> FakeRenderWindow:
        return self.render_window

    def SetInteractorStyle(self, interactor_style) -> None:
        self.interactor_style = interactor_style

    def Enable(self, enabled: int) -> None:
        self.enabled = bool(enabled)

    def Render(self) -> None:
        self.render_count += 1

    def Refresh(self) -> None:
        pass


def make_orbit():
    timestamps_s = [100.0, 160.0, 220.0]
    states_m = [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        np.array([-7_000_000.0, 0.0, 0.0, 0.0, -7_500.0, 0.0]),
    ]
    return (
        compute_orbit_series(timestamps_s, states_m, TimeUnit.MINUTES),
        OemCursor(timestamps_s, states_m),
    )


def test_vtk_view_builds_wgs84_scene_and_direction_aware_cursor_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("vtk")
    pytest.importorskip("wx")
    from ephem_toolkit.play_oem.views.trajectory3d import vtk_backend

    monkeypatch.setattr(vtk_backend, "wxVTKRenderWindowInteractor", FakeWidget)
    series, cursor = make_orbit()
    playback_state = {"rate": 1.0}
    view = vtk_backend.VTKTrajectory3DView(
        object(),
        cursor,
        "ISS",
        "EME2000 / Earth",
        lambda: playback_state["rate"],
    )

    widget = view.build(series, TimeUnit.MINUTES)
    view.update(160.0)

    assert isinstance(widget, FakeWidget)
    assert widget.enabled
    assert widget.render_count == 1
    assert widget.interactor_style.IsA("vtkInteractorStyleTrackballCamera")
    assert len(widget.render_window.renderers) == 1
    assert view._renderer is not None
    assert view._renderer.GetActors().GetNumberOfItems() == 4
    assert view._earth_actor is not None
    earth_filter = view._earth_actor.GetMapper().GetInputConnection(0, 0).GetProducer()
    assert earth_filter.GetTransform().GetScale()[2] == pytest.approx(
        vtk_backend.EARTH_POLAR_SCALE
    )
    assert view._cursor_actor is not None
    assert tuple(view._cursor_actor.GetPosition()) == pytest.approx(
        tuple(cursor.lookup(160.0).r_km)
    )

    assert view._tail_actor is not None
    forward_tail = view._tail_actor.GetMapper().GetInput().GetPoints()
    assert forward_tail.GetNumberOfPoints() == 2
    assert forward_tail.GetPoint(0) == pytest.approx(tuple(series.position_km[0]))
    assert forward_tail.GetPoint(1) == pytest.approx(tuple(series.position_km[1]))

    playback_state["rate"] = -1.0
    view.update(160.0)
    reverse_tail = view._tail_actor.GetMapper().GetInput().GetPoints()
    assert reverse_tail.GetNumberOfPoints() == 2
    assert reverse_tail.GetPoint(0) == pytest.approx(tuple(series.position_km[1]))
    assert reverse_tail.GetPoint(1) == pytest.approx(tuple(series.position_km[2]))

    view.update(99.0)
    assert not view._cursor_actor.GetVisibility()
    assert not view._tail_actor.GetVisibility()

    view.close()
    assert widget.render_window.finalized
    assert not widget.render_window.renderers
    assert widget.interactor.disabled
    assert widget.interactor.render_window is None
    assert widget.render_window.interactor is None
    view.close()
    with pytest.raises(RuntimeError, match="not been built"):
        view.update(160.0)


def test_vtk_view_reports_a_failed_initial_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("vtk")
    pytest.importorskip("wx")
    from ephem_toolkit.play_oem.views.trajectory3d import vtk_backend

    monkeypatch.setattr(vtk_backend, "wxVTKRenderWindowInteractor", FakeWidget)
    monkeypatch.setattr(vtk_backend.wx, "YieldIfNeeded", lambda: None)
    series, cursor = make_orbit()
    view = vtk_backend.VTKTrajectory3DView(
        object(),
        cursor,
        "ISS",
        "EME2000 / Earth",
        lambda: 1.0,
    )
    widget = view.build(series, TimeUnit.MINUTES)
    widget.render_window.never_rendered = 1

    with pytest.raises(vtk_backend.VTKBackendUnavailableError, match="initial render"):
        view.validate_render_context()

    view.close()


def test_vtk_view_rejects_a_missing_opengl_window_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("vtk")
    pytest.importorskip("wx")
    from ephem_toolkit.play_oem.views.trajectory3d import vtk_backend

    monkeypatch.setattr(vtk_backend, "wxVTKRenderWindowInteractor", FakeWidget)
    series, cursor = make_orbit()
    view = vtk_backend.VTKTrajectory3DView(
        object(),
        cursor,
        "ISS",
        "EME2000 / Earth",
        lambda: 1.0,
    )
    widget = view.build(series, TimeUnit.MINUTES)
    widget.render_window.opengl = False

    with pytest.raises(
        vtk_backend.VTKBackendUnavailableError,
        match="OpenGL render-window implementation",
    ):
        view.validate_render_context()

    view.close()
