"""Tests for the wxPython playback application lifecycle."""

from __future__ import annotations

import signal
from types import SimpleNamespace

import numpy as np
import pytest

from ephem_toolkit.play_oem import app
from ephem_toolkit.play_oem.clock import PlaybackClock
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


class FakeEvent:
    def __init__(self) -> None:
        self.skipped = False

    def Skip(self) -> None:
        self.skipped = True


class FakeWxApp:
    def __init__(self, _redirect: bool) -> None:
        self.main_loop_calls = 0

    def MainLoop(self) -> None:
        self.main_loop_calls += 1


class FakeFrame:
    def __init__(self, parent, *, title: str, size=None) -> None:
        self.parent = parent
        self.title = title
        self.size = size
        self.bindings: dict[object, object] = {}
        self.destroyed = False
        self.shown = False
        self.raised = False
        self.sizer = None

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer

    def SetMinSize(self, _size) -> None:
        pass

    def SetSize(self, size) -> None:
        self.size = size

    def Bind(self, event_type, callback, _source=None) -> None:
        self.bindings[event_type] = callback

    def Show(self) -> bool:
        self.shown = True
        return True

    def Raise(self) -> None:
        self.raised = True

    def Layout(self) -> None:
        pass

    def Close(self, *, force: bool = False) -> bool:
        assert force
        if self.destroyed:
            return True
        handler = self.bindings.get(app.wx.EVT_CLOSE)
        if handler is not None:
            handler(FakeEvent())
        self.destroyed = True
        return True

    def Destroy(self) -> None:
        self.destroyed = True


class FakeStaticText:
    def __init__(self, _parent, _id: int, label: str) -> None:
        self.label = label

    def SetLabel(self, label: str) -> None:
        self.label = label


class FakeBoxSizer:
    def __init__(self, _orientation: int) -> None:
        self.items = []

    def Add(self, item, proportion: int, flags: int, border: int = 0) -> None:
        self.items.append((item, proportion, flags, border))


class FakeTimer:
    def __init__(self, _owner) -> None:
        self.interval: int | None = None
        self.running = False

    def Start(self, interval: int) -> bool:
        self.interval = interval
        self.running = True
        return True

    def Stop(self) -> None:
        self.running = False


class FakeCanvas:
    def __init__(self, _parent, _id: int, _figure) -> None:
        self.draw_count = 0
        self.draw_idle_count = 0

    def draw(self) -> None:
        self.draw_count += 1

    def draw_idle(self) -> None:
        self.draw_idle_count += 1


class FakeView:
    name = "fake"

    def __init__(self) -> None:
        self.updated_times: list[float] = []
        self.closed = False

    def build(self, _series, _time_unit):
        return object()

    def update(self, t_s: float) -> None:
        self.updated_times.append(t_s)

    def close(self) -> None:
        self.closed = True


def make_states() -> list[np.ndarray]:
    return [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
    ]


def make_clock(
    *,
    t_now: float = 100.0,
    rate: float = 1.0,
    playing: bool = False,
    loop: bool = False,
) -> PlaybackClock:
    return PlaybackClock(
        100.0,
        200.0,
        t_now=t_now,
        rate=rate,
        playing=playing,
        loop=loop,
        sample_times=(100.0, 200.0),
    )


def make_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plots: tuple[str, ...] = ("overview",),
    clock: PlaybackClock | None = None,
    tick_interval_ms: int = 33,
) -> tuple[app.PlayerApp, list[FakeView], list[FakeCanvas], list[FakeFrame]]:
    frames: list[FakeFrame] = []
    views: list[FakeView] = []
    canvases: list[FakeCanvas] = []
    monkeypatch.setattr(app.wx, "GetApp", lambda: None)
    monkeypatch.setattr(app.wx, "App", FakeWxApp)
    monkeypatch.setattr(
        app.wx, "Frame", lambda *args, **kwargs: _frame(*args, **kwargs)
    )
    monkeypatch.setattr(app.wx, "StaticText", FakeStaticText)
    monkeypatch.setattr(app.wx, "BoxSizer", FakeBoxSizer)
    monkeypatch.setattr(app.wx, "Timer", FakeTimer)
    monkeypatch.setattr(app, "FigureCanvasWxAgg", lambda *args: _canvas(*args))
    monkeypatch.setattr(app.wx, "EVT_CLOSE", "close")
    monkeypatch.setattr(app.wx, "EVT_TIMER", "timer")
    monkeypatch.setattr(app.wx, "ID_ANY", -1)
    monkeypatch.setattr(app.wx, "VERTICAL", 1)
    monkeypatch.setattr(app.wx, "EXPAND", 2)
    monkeypatch.setattr(app.wx, "ALL", 4)

    def _frame(*args, **kwargs) -> FakeFrame:
        frame = FakeFrame(*args, **kwargs)
        frames.append(frame)
        return frame

    def _canvas(*args) -> FakeCanvas:
        canvas = FakeCanvas(*args)
        canvases.append(canvas)
        return canvas

    def create_view(*_args) -> FakeView:
        view = FakeView()
        views.append(view)
        return view

    monkeypatch.setattr(app, "SpeedAltitudeView", create_view)
    monkeypatch.setattr(app, "StateComponentsView", create_view)
    monkeypatch.setattr(app, "Trajectory3DView", create_view)
    timestamps = [100.0, 200.0]
    series = compute_orbit_series(timestamps, make_states(), TimeUnit.MINUTES)
    player = app.PlayerApp(
        make_clock() if clock is None else clock,
        series,
        TimeUnit.MINUTES,
        OemCursor(timestamps, make_states()),
        "TEST",
        "GCRF / Earth",
        plots=plots,
        tick_interval_ms=tick_interval_ms,
    )
    return player, views, canvases, frames


def test_start_uses_one_wx_app_and_opens_the_selected_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, canvases, frames = make_app(
        monkeypatch,
        plots=("state-components",),
        clock=make_clock(t_now=150.0, rate=-10.0, playing=True, loop=True),
        tick_interval_ms=40,
    )

    player.start()

    assert player.wx_app.main_loop_calls == 0
    assert len(frames) == 2
    assert frames[0].title == "play-oem"
    assert frames[1].title == "State Components"
    assert frames[0].shown and frames[1].shown
    assert len(views) == len(canvases) == 1
    assert views[0].updated_times == [150.0]
    assert player._timer.interval == 40
    assert player._timer.running
    assert player.clock.t_now == 150.0
    assert player.clock.rate == -10.0
    assert player.clock.playing
    assert player.clock.loop
    assert "Elapsed: 50.000 s" in player._time_display.label
    assert "Paused" not in player._time_display.label

    player.close()


def test_wx_timer_advances_clock_and_updates_playback_display_and_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, canvases, _frames = make_app(
        monkeypatch,
        clock=make_clock(playing=True),
    )
    monotonic_values = iter((10.0, 12.5))
    monkeypatch.setattr(app.time, "monotonic", lambda: next(monotonic_values))

    player.start()
    player._on_timer(SimpleNamespace())

    assert player.clock.t_now == 102.5
    assert "Elapsed: 2.500 s" in player._time_display.label
    assert "UTC:" in player._time_display.label
    assert "Playing | +1x | No loop" in player._time_display.label
    assert all(view.updated_times[-1] == 102.5 for view in views)
    assert all(canvas.draw_idle_count == 1 for canvas in canvases)

    player.close()


def test_clock_notifications_update_views_and_existing_plot_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
    )
    player.start()
    plot_frame = frames[1]

    player.clock.seek(150.0)
    player.open_view("speed-altitude")

    assert views[0].updated_times == [100.0, 150.0]
    assert plot_frame.raised
    assert len(frames) == 2

    player.close()


def test_closing_one_plot_unsubscribes_only_that_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, frames = make_app(
        monkeypatch,
        plots=("state-components",),
    )
    player.start()
    plot_frame = frames[1]

    player.close_view("state-components")
    player.clock.seek(160.0)

    assert plot_frame.destroyed
    assert views[0].closed
    assert views[0].updated_times == [100.0]
    assert not player._closed
    assert player._timer.running

    player.close()


def test_closing_primary_frame_stops_timer_and_closes_all_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, frames = make_app(monkeypatch)
    player.start()

    frames[0].Close(force=True)
    player.clock.seek(160.0)

    assert player._closed
    assert not player._timer.running
    assert all(view.closed for view in views)
    assert all(frame.destroyed for frame in frames)
    assert all(view.updated_times == [100.0] for view in views)
    player.close()


def test_sigint_is_forwarded_with_call_after_and_previous_handler_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, frames = make_app(
        monkeypatch, plots=("state-components",)
    )
    signal_handlers: list[object] = []
    previous_handler = object()
    scheduled: list[tuple[object, tuple[object, ...]]] = []
    monkeypatch.setattr(app.signal, "getsignal", lambda _signum: previous_handler)
    monkeypatch.setattr(
        app.signal,
        "signal",
        lambda _signum, handler: signal_handlers.append(handler),
    )
    monkeypatch.setattr(
        app.wx,
        "CallAfter",
        lambda callback, *args: scheduled.append((callback, args)),
    )

    def main_loop() -> None:
        signal_handlers[0](signal.SIGINT, None)
        assert scheduled == [(player.close, ())]
        scheduled[0][0](*scheduled[0][1])

    player.wx_app.MainLoop = main_loop
    player.run()

    assert frames[0].destroyed
    assert len(signal_handlers) == 2
    assert signal_handlers[1] is previous_handler


def test_existing_wx_app_is_reused_instead_of_created_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_app = FakeWxApp(False)
    monkeypatch.setattr(app.wx, "GetApp", lambda: existing_app)
    monkeypatch.setattr(app.wx, "Frame", FakeFrame)
    monkeypatch.setattr(app.wx, "StaticText", FakeStaticText)
    monkeypatch.setattr(app.wx, "BoxSizer", FakeBoxSizer)
    monkeypatch.setattr(app.wx, "Timer", FakeTimer)
    monkeypatch.setattr(app.wx, "EVT_CLOSE", "close")
    monkeypatch.setattr(app.wx, "EVT_TIMER", "timer")
    monkeypatch.setattr(app.wx, "ID_ANY", -1)
    monkeypatch.setattr(app.wx, "VERTICAL", 1)
    monkeypatch.setattr(app.wx, "EXPAND", 2)
    monkeypatch.setattr(app.wx, "ALL", 4)

    def fail_if_created(_redirect: bool):
        raise AssertionError("must not create a second wx.App")

    monkeypatch.setattr(app.wx, "App", fail_if_created)
    series = compute_orbit_series([100.0, 200.0], make_states(), TimeUnit.MINUTES)
    player = app.PlayerApp(
        make_clock(),
        series,
        TimeUnit.MINUTES,
        OemCursor([100.0, 200.0], make_states()),
        "TEST",
        "GCRF / Earth",
        plots=("state-components",),
    )

    assert player.wx_app is existing_app
    player.close()


def test_tick_interval_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.wx, "GetApp", lambda: None)

    with pytest.raises(ValueError, match="tick_interval_ms"):
        app.PlayerApp(
            make_clock(),
            compute_orbit_series([100.0, 200.0], make_states(), TimeUnit.MINUTES),
            TimeUnit.MINUTES,
            OemCursor([100.0, 200.0], make_states()),
            "TEST",
            "GCRF / Earth",
            tick_interval_ms=0,
        )
