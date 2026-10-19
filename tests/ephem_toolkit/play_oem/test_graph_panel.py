"""Behavioral tests for graph-panel redraw scheduling."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from ephem_toolkit.play_oem import graph_panel


def test_actions_menu_dismisses_tooltip_before_opening() -> None:
    operations: list[str] = []
    menu = object()

    def open_menu(selected_menu: object) -> None:
        assert selected_menu is menu
        # Mapping a menu while the tooltip is still open fails on GTK.
        assert operations == ["hide tooltip"]
        operations.append("open menu")

    # Record ordering without native popup windows so the GTK regression can
    # be checked in headless unit tests as well as the GUI reproduction.
    panel = SimpleNamespace(
        _actions_tooltip=SimpleNamespace(
            DoHideNow=lambda: operations.append("hide tooltip")
        ),
        _actions_menu=menu,
        PopupMenu=open_menu,
    )
    graph_panel.GraphPanelHost._on_actions_button(
        cast(graph_panel.GraphPanelHost, panel), graph_panel.wx.CommandEvent()
    )

    assert operations == ["hide tooltip", "open menu"]


class FakeCallLater:
    def __init__(self, delay_ms: int, callback) -> None:
        self.delay_ms = delay_ms
        self.callback = callback
        self.running = True

    def IsRunning(self) -> bool:
        return self.running

    def Stop(self) -> None:
        self.running = False

    def fire(self) -> None:
        self.running = False
        self.callback()


def test_redraw_throttle_coalesces_requests_and_skips_hidden_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    visible = [True]
    draw_count = [0]
    monkeypatch.setattr(graph_panel.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(graph_panel.wx, "CallLater", FakeCallLater)
    throttle = graph_panel._RedrawThrottle(
        lambda: visible[0],
        lambda: draw_count.__setitem__(0, draw_count[0] + 1),
    )

    throttle.request()
    assert draw_count == [1]

    now[0] = 0.02
    throttle.request()
    pending = throttle._timer
    throttle.request()
    assert pending is throttle._timer
    # The monkeypatched scheduler supplies the fake timer's test-only API.
    assert isinstance(pending, FakeCallLater)
    assert 10 <= pending.delay_ms <= 15

    visible[0] = False
    now[0] = 0.1
    pending.fire()
    assert draw_count == [1]

    visible[0] = True
    throttle.request()
    assert draw_count == [2]


def test_closing_redraw_throttle_cancels_deferred_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    monkeypatch.setattr(graph_panel.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(graph_panel.wx, "CallLater", FakeCallLater)
    throttle = graph_panel._RedrawThrottle(lambda: True, lambda: None)
    throttle.request()
    now[0] = 0.01
    throttle.request()
    pending = throttle._timer
    assert pending is not None and pending.IsRunning()

    throttle.close()

    assert not pending.IsRunning()


def test_scheduled_redraw_refreshes_visible_native_content() -> None:
    native_content = SimpleNamespace(refresh_count=0)
    native_content.Refresh = lambda: setattr(
        native_content, "refresh_count", native_content.refresh_count + 1
    )
    panel = SimpleNamespace(
        _on_redraw_request=lambda _panel: None,
        _canvas=None,
        _native_content=native_content,
        _is_visible=lambda: True,
    )

    # Exercise the method with a lightweight host instead of native wx controls.
    graph_panel.GraphPanelHost.draw_if_needed(cast(graph_panel.GraphPanelHost, panel))

    assert native_content.refresh_count == 1
