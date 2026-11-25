"""Reusable floating panel checks."""

from __future__ import annotations

import gc
import os
from collections.abc import Iterator
from typing import Any, cast

import pytest

from ephem_toolkit.play_oem.widgets import PanelCorner, PanelInteraction


@pytest.fixture(scope="module")
def wx_app() -> Iterator[Any]:
    import wx

    if not wx.App.IsDisplayAvailable():
        pytest.skip("wx cannot connect to the available X display")
    app = wx.App.Get() or wx.App(False)
    yield app
    gc.collect()


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_floating_panel_collapses_expands_and_stays_in_bounds(
    wx_app: Any,
) -> None:
    import wx

    from ephem_toolkit.play_oem.widgets import FloatingPanel

    frame = wx.Frame(None, size=(800, 500))
    host = wx.Panel(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(host, 1, wx.EXPAND)
    panel = FloatingPanel(host, name="Test panel")
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(wx.StaticText(panel.GetContentWindow(), label="Projection"), 0)
    choice = wx.Choice(panel.GetContentWindow(), choices=["A", "B"])
    sizer.Add(choice, 0)
    panel.SetContentSizer(sizer)
    frame.Show()
    wx_app.Yield()
    host.SetFocus()
    wx_app.Yield()

    assert not panel.IsExpanded()
    assert panel.GetHandleSize().width == host.FromDIP(24)
    handle_rect = panel.GetCollapsedScreenRect()
    host_screen_rect = host.GetScreenRect()
    assert handle_rect.width == host.FromDIP(24)
    assert handle_rect.top == host_screen_rect.top
    assert handle_rect.right == host_screen_rect.right
    assert (
        panel._handle.GetBackgroundColour()
        == wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWFRAME)
    )

    content = panel.GetContentWindow()
    panel.Expand()
    assert panel.IsExpanded()
    wx_app.Yield()
    assert wx.Window.FindFocus() == content
    panel.Collapse()
    assert not panel.IsExpanded()
    wx_app.Yield()
    assert wx.Window.FindFocus() == host
    assert panel._handle.AcceptsFocus()
    bounds = panel.GetExpandedBounds()
    expanded_screen_rect = panel.GetExpandedScreenRect()
    assert expanded_screen_rect.right == host_screen_rect.right
    assert expanded_screen_rect.top == host_screen_rect.top
    assert content.GetBackgroundColour() == wx.SystemSettings.GetColour(
        wx.SYS_COLOUR_WINDOW
    )
    assert not content.GetWindowStyleFlag() & wx.BORDER_SIMPLE
    assert (
        panel._popup.GetBackgroundColour()
        == wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWFRAME)
    )
    assert content.GetWindowStyleFlag() & wx.HSCROLL
    assert content.GetWindowStyleFlag() & wx.VSCROLL
    virtual_height = content.GetVirtualSize().height
    assert virtual_height >= content.GetSizer().CalcMin().height
    assert bounds.GetTop() >= host.FromDIP(8)
    screen_width = wx.Display().GetClientArea().width
    assert bounds.GetRight() <= screen_width
    expanded_screen = panel.GetExpandedScreenRect()
    frame_screen = frame.GetScreenRect()
    assert expanded_screen.left >= frame_screen.left
    assert expanded_screen.right <= frame_screen.right
    assert content.GetVirtualSize().width == content.GetClientSize().width
    assert content.GetVirtualSize().height == content.GetClientSize().height
    assert bounds.GetBottom() <= host.GetClientSize().height - host.FromDIP(8)

    frame.SetSize((280, 300))
    wx_app.Yield()
    bounds = panel.GetExpandedBounds()
    assert bounds.width <= wx.Display().GetClientArea().width

    panel.ScheduleCollapse(delay_ms=1)
    wx_app.Yield()
    wx_app.GetTopWindow()
    assert panel.Close()
    frame.Destroy()
    wx_app.Yield()


@pytest.mark.parametrize(
    ("corner", "at_left", "at_top"),
    [
        (PanelCorner.TOP_LEFT, True, True),
        (PanelCorner.TOP_RIGHT, False, True),
        (PanelCorner.BOTTOM_LEFT, True, False),
        (PanelCorner.BOTTOM_RIGHT, False, False),
    ],
)
@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_floating_panel_can_anchor_to_each_parent_corner(
    wx_app: Any,
    corner: PanelCorner,
    at_left: bool,
    at_top: bool,
) -> None:
    import wx

    from ephem_toolkit.play_oem.widgets import FloatingPanel

    frame = wx.Frame(None, size=(800, 500))
    host = wx.Panel(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(host, 1, wx.EXPAND)
    panel = FloatingPanel(host, corner=corner)
    frame.Show()
    wx_app.Yield()

    host_rect = host.GetScreenRect()
    handle_rect = panel.GetCollapsedScreenRect()
    expected_left = (
        host_rect.left
        if at_left
        else host_rect.right - host.FromDIP(24)
    )
    expected_top = (
        host_rect.top
        if at_top
        else host_rect.bottom - host.FromDIP(24)
    )
    assert handle_rect.left == expected_left
    assert handle_rect.top == expected_top

    panel.Expand()
    wx_app.Yield()
    expanded_rect = panel.GetExpandedScreenRect()
    if at_left:
        assert expanded_rect.left == host_rect.left
    else:
        assert expanded_rect.right == host_rect.right
    if at_top:
        assert expanded_rect.top == host_rect.top
    else:
        assert expanded_rect.bottom == host_rect.bottom

    assert panel.Close()
    frame.Destroy()
    wx_app.Yield()


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
def test_floating_panel_can_start_expanded(wx_app: Any) -> None:
    import wx

    from ephem_toolkit.play_oem.widgets import FloatingPanel

    frame = wx.Frame(None, size=(500, 300))
    host = wx.Panel(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(host, 1, wx.EXPAND)
    panel = FloatingPanel(host, initially_expanded=True)
    content = wx.BoxSizer(wx.VERTICAL)
    content.Add(wx.StaticText(panel.GetContentWindow(), label="Readout"))
    panel.SetContentSizer(content)
    frame.Show()
    wx_app.Yield()

    assert panel.IsExpanded()

    panel.Close()
    frame.Destroy()
    wx_app.Yield()


@pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires an X display (use xvfb-run)"
)
@pytest.mark.parametrize("corner", list(PanelCorner))
def test_floating_panel_click_control_stays_open_and_follows_corner(
    wx_app: Any,
    corner: PanelCorner,
) -> None:
    import wx

    from ephem_toolkit.play_oem.widgets import FloatingPanel

    frame = wx.Frame(None, size=(500, 300))
    host = wx.Panel(frame)
    frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
    frame.GetSizer().Add(host, 1, wx.EXPAND)
    panel = FloatingPanel(
        host,
        corner=corner,
        interaction=PanelInteraction.CLICK,
    )
    readout = wx.StaticText(panel.GetContentWindow(), label="Lat: —  ·  Long: —")
    row_height = readout.GetBestSize().height
    content_sizer = wx.BoxSizer(wx.VERTICAL)
    content_sizer.Add(readout, 0, wx.EXPAND)
    panel.SetContentSizer(content_sizer)
    frame.Show()
    wx_app.Yield()

    class Event:
        @staticmethod
        def Skip() -> None:
            pass

    panel._on_handle_click(cast(Any, Event()))
    wx_app.Yield()
    assert panel.IsExpanded()
    assert panel._collapse_control is not None
    assert panel._collapse_control.GetLabel() == "≡"
    assert panel._collapse_control.GetMinSize().height == row_height
    assert panel._collapse_control.GetMaxSize().height == row_height
    assert panel._content_sizer is not None
    body_sizer = panel._content_sizer.GetItem(0).GetSizer()
    assert body_sizer is not None
    assert body_sizer.GetOrientation() == wx.HORIZONTAL
    control_index = 0 if corner.value.endswith("left") else 1
    control_item = body_sizer.GetItem(control_index)
    assert control_item.GetWindow() == panel._collapse_control
    expected_alignment = (
        wx.ALIGN_TOP if corner.value.startswith("top") else wx.ALIGN_BOTTOM
    )
    assert control_item.GetFlag() & expected_alignment
    panel._on_collapse_control_click(cast(Any, Event()))
    wx_app.Yield()
    assert not panel.IsExpanded()

    panel.Close()
    frame.Destroy()
    wx_app.Yield()
