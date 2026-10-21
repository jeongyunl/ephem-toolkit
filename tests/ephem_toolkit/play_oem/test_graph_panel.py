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


class FakeScrolledWindow:
    def __init__(
        self,
        parent=None,
        *,
        scroll_range: int = 0,
        scroll_thumb: int = 1,
        view_y: int = 0,
    ) -> None:
        self.parent = parent
        self.scroll_range = scroll_range
        self.scroll_thumb = scroll_thumb
        self.view_y = view_y
        self.scroll_calls: list[tuple[int, int]] = []

    def GetParent(self):
        return self.parent

    def GetViewStart(self) -> tuple[int, int]:
        return 0, self.view_y

    def GetScrollRange(self, _orientation: int) -> int:
        return self.scroll_range

    def GetScrollThumb(self, _orientation: int) -> int:
        return self.scroll_thumb

    def Scroll(self, x: int, y: int) -> None:
        self.scroll_calls.append((x, y))
        self.view_y = y


class FakeMouseWheelEvent:
    def __init__(self, rotation: int, delta: int = 120) -> None:
        self.rotation = rotation
        self.delta = delta
        self.skipped = False

    def GetWheelRotation(self) -> int:
        return self.rotation

    def GetWheelDelta(self) -> int:
        return self.delta

    def Skip(self) -> None:
        self.skipped = True


def test_panel_content_wheel_hands_off_to_stack_only_at_panel_scroll_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph_panel.wx, "ScrolledWindow", FakeScrolledWindow)
    outer_stack = FakeScrolledWindow(
        scroll_range=30,
        scroll_thumb=10,
        view_y=0,
    )
    panel_content = FakeScrolledWindow(
        outer_stack,
        scroll_range=15,
        scroll_thumb=5,
        view_y=0,
    )
    host = SimpleNamespace(
        graph_scroller=panel_content,
        _parent_stack_scroller=lambda: outer_stack,
    )

    inner_event = FakeMouseWheelEvent(-120)
    graph_panel.GraphPanelHost._on_content_mousewheel(
        cast(graph_panel.GraphPanelHost, host), inner_event
    )
    assert inner_event.skipped
    assert outer_stack.scroll_calls == []

    panel_content.view_y = 10
    handoff_event = FakeMouseWheelEvent(-120)
    graph_panel.GraphPanelHost._on_content_mousewheel(
        cast(graph_panel.GraphPanelHost, host), handoff_event
    )
    assert not handoff_event.skipped
    assert outer_stack.scroll_calls == [(0, 3)]
