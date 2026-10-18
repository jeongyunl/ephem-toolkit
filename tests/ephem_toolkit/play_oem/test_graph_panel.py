"""Behavioral tests for graph-panel redraw scheduling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ephem_toolkit.play_oem import graph_panel


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
    assert pending is not None and 10 <= pending.delay_ms <= 15

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

    graph_panel.GraphPanelHost.draw_if_needed(panel)

    assert native_content.refresh_count == 1
