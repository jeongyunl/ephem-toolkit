"""Tests for the play-oem Tk application lifecycle."""

from __future__ import annotations

import signal

import numpy as np
import pytest

from ephem_toolkit.play_oem import app
from ephem_toolkit.play_oem.clock import PlaybackClock
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


class FakeRoot:
    def __init__(self) -> None:
        self.callbacks: dict[str, object] = {}
        self.protocols: dict[str, object] = {}
        self.cancelled: list[str] = []
        self.destroyed = False
        self.quit_called = False
        self._next_after_id = 0

    def title(self, _title: str) -> None:
        pass

    def protocol(self, name: str, callback) -> None:
        self.protocols[name] = callback

    def after(self, _delay_ms: int, callback) -> str:
        self._next_after_id += 1
        after_id = f"after-{self._next_after_id}"
        self.callbacks[after_id] = callback
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.cancelled.append(after_id)
        self.callbacks.pop(after_id, None)

    def mainloop(self) -> None:
        pass

    def quit(self) -> None:
        self.quit_called = True

    def destroy(self) -> None:
        self.destroyed = True


class FakeToplevel:
    def __init__(self) -> None:
        self.protocols: dict[str, object] = {}
        self.destroyed = False
        self.lifted = False

    def title(self, _title: str) -> None:
        pass

    def protocol(self, name: str, callback) -> None:
        self.protocols[name] = callback

    def lift(self) -> None:
        self.lifted = True

    def destroy(self) -> None:
        self.destroyed = True


class FakeControlWindow:
    def __init__(self, root, on_close, _on_open_speed_altitude) -> None:
        self.on_close = on_close
        self.readouts: list[str] = []
        root.protocol("WM_DELETE_WINDOW", on_close)

    def update_time(self, text: str) -> None:
        self.readouts.append(text)


def make_series():
    return compute_orbit_series(
        [100.0, 200.0],
        [
            np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
            np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
        ],
        TimeUnit.MINUTES,
    )


def make_app(monkeypatch: pytest.MonkeyPatch, root: FakeRoot) -> app.PlayerApp:
    monkeypatch.setattr(app.tk, "Tk", lambda: root)
    monkeypatch.setattr(app, "ControlWindow", FakeControlWindow)
    return app.PlayerApp(
        PlaybackClock(100.0, 200.0, playing=True),
        make_series(),
        TimeUnit.MINUTES,
    )


def test_timer_advances_clock_updates_readout_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    monotonic_values = iter((10.0, 12.5))
    monkeypatch.setattr(app.time, "monotonic", lambda: next(monotonic_values))

    player.start()
    initial_timer = player._timer_id
    callback = root.callbacks[initial_timer]
    callback()

    assert player.clock.t_now == 102.5
    assert player.control_window.readouts[-1].startswith("Elapsed: 2.500 s")
    assert "UTC:" in player.control_window.readouts[-1]
    assert player._timer_id is not None

    active_timer = player._timer_id
    player.close()
    assert active_timer in root.cancelled
    assert root.quit_called
    assert root.destroyed


def test_window_close_callback_stops_timer_and_destroys_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    monkeypatch.setattr(app.time, "monotonic", lambda: 0.0)

    player.start()
    root.protocols["WM_DELETE_WINDOW"]()

    assert root.destroyed
    assert not root.callbacks


def test_run_handles_sigint_and_restores_previous_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    monkeypatch.setattr(app.time, "monotonic", lambda: 0.0)
    signal_handlers: list[object] = []
    previous_handler = object()
    monkeypatch.setattr(app.signal, "getsignal", lambda _signum: previous_handler)

    def set_signal_handler(_signum, handler):
        signal_handlers.append(handler)

    monkeypatch.setattr(app.signal, "signal", set_signal_handler)

    def mainloop() -> None:
        handler = signal_handlers[0]
        handler(signal.SIGINT, None)

    root.mainloop = mainloop
    player.run()

    assert root.destroyed
    assert len(signal_handlers) == 2
    assert signal_handlers[1] is previous_handler


def test_tick_interval_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    root = FakeRoot()
    monkeypatch.setattr(app.tk, "Tk", lambda: root)
    monkeypatch.setattr(app, "ControlWindow", FakeControlWindow)

    with pytest.raises(ValueError, match="tick_interval_ms"):
        app.PlayerApp(
            PlaybackClock(0.0, 1.0),
            make_series(),
            TimeUnit.MINUTES,
            tick_interval_ms=0,
        )


def test_speed_altitude_view_window_can_be_opened_raised_and_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    window = FakeToplevel()
    monkeypatch.setattr(app.tk, "Toplevel", lambda _root: window)

    class FakeView:
        def __init__(self, t_start_s) -> None:
            self.t_start_s = t_start_s
            self.closed = False

        def build(self, _series, _time_unit):
            return object()

        def close(self) -> None:
            self.closed = True

    class FakeWidget:
        def pack(self, **_kwargs) -> None:
            pass

    class FakeCanvas:
        def __init__(self, _figure, *, master) -> None:
            assert master is window

        def draw(self) -> None:
            pass

        def get_tk_widget(self):
            return FakeWidget()

    view = FakeView(100.0)
    monkeypatch.setattr(app, "SpeedAltitudeView", lambda t_start_s: view)
    monkeypatch.setattr(app, "FigureCanvasTkAgg", FakeCanvas)

    player.open_speed_altitude_view()
    assert player._speed_altitude_view is view
    assert player._speed_altitude_window is window
    player.open_speed_altitude_view()
    assert window.lifted

    window.protocols["WM_DELETE_WINDOW"]()

    assert view.closed
    assert window.destroyed
    assert player._speed_altitude_view is None
    assert player._speed_altitude_window is None
