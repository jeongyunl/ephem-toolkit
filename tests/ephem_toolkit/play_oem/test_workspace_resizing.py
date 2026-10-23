"""Native workspace layout checks while the main window is resized."""

from __future__ import annotations

import gc
import os

import pytest
import wx

from ephem_toolkit.play_oem.workspace import Workspace


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_narrow_timeline_scrolls_without_shrinking_transport_buttons() -> None:
    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx cannot connect to the available X display")
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, size=(1500, 700))
    workspace = Workspace(
        frame,
        lambda _fraction: None,
        timeline_enabled=True,
        playback_bounds=(10.0, 90.0),
        oem_coverage=(0.0, 100.0),
    )
    try:
        frame.Show()
        for width in (1500, 900, 640, 400, 1500):
            frame.SetSize((width, 700))
            app.Yield()
            timeline = workspace.timeline_panel
            for button in workspace.transport_speed_buttons.values():
                assert button.GetSize().width >= button.GetBestSize().width
                assert button.GetSize().height >= button.GetBestSize().height
            assert (
                workspace.timeline_slider.GetRect().bottom
                <= timeline.GetClientSize().height
            )
            if width == 400:
                assert (
                    timeline.GetVirtualSize().width > timeline.GetClientSize().width
                )
                timeline.Scroll(timeline.GetScrollRange(wx.HORIZONTAL), 0)
                app.Yield()
                last_button = workspace.transport_speed_buttons[1000.0]
                assert (
                    last_button.GetScreenRect().right <= timeline.GetScreenRect().right
                )
    finally:
        frame.Destroy()
        app.Yield()
        del workspace
        gc.collect()
