"""Projection and wx-hosted Ground Track rendering checks."""

from __future__ import annotations

import os
from typing import Any, cast

import numpy as np
import pytest

from ephem_toolkit.play_oem.ground_track import GroundTrackCoordinates
from ephem_toolkit.play_oem.views import ground_track


@pytest.mark.parametrize("name", ground_track.PROJECTION_NAMES)
@pytest.mark.parametrize("center", [-179.0, 0.0, 123.0])
def test_projection_covers_poles_and_center_seam(name: str, center: float) -> None:
    projection = ground_track._make_projection(name, center)
    x, y = projection(
        np.array([center, center, center - 180, center + 180]),
        np.array([-90, 90, 0, 0]),
        errcheck=True,
    )
    assert np.isfinite(x).all()
    assert np.isfinite(y).all()


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_wx_view_builds_controls_and_updates_minimum_elevation() -> None:
    import wx

    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx cannot connect to the available X display")
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None)
    coordinates = GroundTrackCoordinates(
        np.array([0.0, 10.0]),
        np.deg2rad(np.array([0.0, 10.0])),
        np.deg2rad(np.array([0.0, 20.0])),
        np.array([0, 0]),
        "ITRF",
    )
    updates: list[int] = []
    view = ground_track.GroundTrackView(
        frame,
        None,
        coordinates,
        cast(Any, None),
        "Test object",
        on_minimum_elevation=updates.append,
    )
    content = view.build(cast(Any, None), cast(Any, None))
    assert isinstance(content, wx.Window)
    assert view._axes is not None
    assert "Ground Track" in view._axes.get_title()
    view._on_projection_choice(
        cast(Any, type("Event", (), {"GetString": lambda _self: "Equirectangular"})())
    )
    assert view.projection_name == "Equirectangular"
    view.set_minimum_elevation(15)
    assert view.minimum_elevation_deg == 15
    minimum_control = view._minimum_control
    assert minimum_control is not None
    assert minimum_control.GetValue() == 15
    view.close()
    frame.Destroy()
    app.ProcessPendingEvents()
