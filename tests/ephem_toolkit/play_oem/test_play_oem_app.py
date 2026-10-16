"""Tests for the play-oem Tk application lifecycle."""

from __future__ import annotations

import signal
from pathlib import Path

import numpy as np
import pytest

from ephem_toolkit.play_oem import app, control_window
from ephem_toolkit.play_oem.clock import PlaybackClock
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit


class FakeRoot:
    def __init__(self, patchlevel: str = "8.6.0") -> None:
        self.callbacks: dict[str, object] = {}
        self.protocols: dict[str, object] = {}
        self.cancelled: list[str] = []
        self.destroyed = False
        self.quit_called = False
        self.idle_updates = 0
        self._next_after_id = 0
        self.bindings: dict[str, object] = {}
        self.tk = FakeTclInterpreter(patchlevel)

    def title(self, _title: str) -> None:
        pass

    def configure(self, **_kwargs) -> None:
        pass

    def minsize(self, _width: int, _height: int) -> None:
        pass

    def protocol(self, name: str, callback) -> None:
        self.protocols[name] = callback

    def bind_all(self, sequence: str, callback) -> None:
        self.bindings[sequence] = callback

    def update_idletasks(self) -> None:
        self.idle_updates += 1

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


class FakeTclInterpreter:
    def __init__(self, patchlevel: str) -> None:
        self.patchlevel = patchlevel
        self.image_commands: list[tuple[object, ...]] = []

    def call(self, *args: object) -> str:
        if args == ("info", "patchlevel"):
            return self.patchlevel
        self.image_commands.append(args)
        return ""


def test_control_window_uses_visible_classic_button_for_time_readout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    widgets = []
    seek_values: list[float] = []
    speed_values: list[float] = []
    toggle_calls: list[bool] = []

    class FakeButton:
        def __init__(self, _master, **options) -> None:
            self.options = options
            self.text = options.get("text", "")
            self.bindings: dict[str, object] = {}
            widgets.append(self)

        def pack(self, **_kwargs) -> None:
            pass

        def bind(self, sequence: str, callback) -> None:
            self.bindings[sequence] = callback

        def configure(self, **options) -> None:
            self.options.update(options)
            self.text = options.get("text", self.text)

    class FakeFrame:
        def __init__(self, _master, **_options) -> None:
            pass

        def pack(self, **_kwargs) -> None:
            pass

    class FakePhotoImage:
        _next_id = 0

        def __init__(self, *, master, width: int, height: int) -> None:
            type(self)._next_id += 1
            self.name = f"fake-control-image-{type(self)._next_id}"
            self.tk = master.tk
            self.width = width
            self.height = height
            self.put_calls: list[tuple[str, tuple[int, ...]]] = []

        def __str__(self) -> str:
            return self.name

        def put(self, color: str, *, to: tuple[int, ...]) -> None:
            self.put_calls.append((color, to))

    monkeypatch.setattr(control_window.tk, "Button", FakeButton)
    monkeypatch.setattr(control_window.tk, "Frame", FakeFrame)
    monkeypatch.setattr(control_window.tk, "PhotoImage", FakePhotoImage)
    window = control_window.ControlWindow(
        root,
        lambda: None,
        lambda: None,
        lambda: toggle_calls.append(True),
        seek_values.append,
        speed_values.append,
        timeline_enabled=True,
    )
    window.update_time("Elapsed: 1 s\nUTC: example")
    window.update_playback_state("Elapsed: 2 s\nUTC: example", 0.25, False, 10.0)

    assert widgets[0].options["state"] == "normal"
    assert widgets[0].options["relief"] == "flat"
    assert widgets[0].text == "Elapsed: 2 s"
    assert widgets[1].text == "UTC: example"
    assert window._play_pause_button.text == "Play"
    assert window._speed_label.text == "Speed: 10x"
    assert window._speed_10_button.options["relief"] == "sunken"
    assert window._timeline_button.options["image"] is window._timeline_image
    assert window._timeline_image.width == 480
    assert any(color == "#2878c8" for color, _to in window._timeline_image.put_calls)
    assert seek_values == []
    assert window._play_pause_button.bindings["<space>"](None) == "break"
    window._play_pause_button.bindings["<space>"](None)
    assert toggle_calls == [True]
    window._play_pause_button.bindings["<KeyRelease-space>"](None)
    window._play_pause_button.bindings["<space>"](None)
    assert toggle_calls == [True, True]
    window._timeline_button.bindings["<Button-1>"](
        type("ClickEvent", (), {"x": 240, "y": 16})()
    )
    assert seek_values[-1] == 0.5
    window._timeline_button.bindings["<B1-Motion>"](
        type("ClickEvent", (), {"x": 354, "y": 16})()
    )
    assert seek_values[-1] == 0.75
    window._speed_1_button.options["command"]()
    window._speed_10_button.options["command"]()
    assert speed_values == [1.0, 10.0]


class FakeToplevel:
    def __init__(self) -> None:
        self.protocols: dict[str, object] = {}
        self.destroyed = False
        self.lifted = False
        self.events: list[str] = []
        self.window_title = ""

    def title(self, title: str) -> None:
        self.window_title = title

    def protocol(self, name: str, callback) -> None:
        self.protocols[name] = callback

    def lift(self) -> None:
        self.lifted = True

    def update_idletasks(self) -> None:
        self.events.append("idle")

    def destroy(self) -> None:
        self.destroyed = True


class FakeControlWindow:
    def __init__(
        self,
        root,
        on_close,
        _on_open_speed_altitude,
        on_toggle_play,
        on_seek,
        on_set_speed,
        *,
        timeline_enabled,
    ) -> None:
        self.on_close = on_close
        self.on_toggle_play = on_toggle_play
        self.on_seek = on_seek
        self.on_set_speed = on_set_speed
        self.timeline_enabled = timeline_enabled
        self.readouts: list[str] = []
        self.states: list[tuple[float, bool, float]] = []
        root.protocol("WM_DELETE_WINDOW", on_close)

    def update_playback_state(
        self, text: str, progress: float, playing: bool, rate: float
    ) -> None:
        self.readouts.append(text)
        self.states.append((progress, playing, rate))


def make_states() -> list[np.ndarray]:
    return [
        np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0]),
        np.array([0.0, 7_000_000.0, 0.0, -7_500.0, 0.0, 0.0]),
    ]


def make_series():
    return compute_orbit_series([100.0, 200.0], make_states(), TimeUnit.MINUTES)


def make_app(monkeypatch: pytest.MonkeyPatch, root: FakeRoot) -> app.PlayerApp:
    monkeypatch.setattr(app.tk, "Tk", lambda: root)
    monkeypatch.setattr(app, "ControlWindow", FakeControlWindow)
    return app.PlayerApp(
        PlaybackClock(100.0, 200.0, playing=True),
        make_series(),
        TimeUnit.MINUTES,
        OemCursor([100.0, 200.0], make_states()),
        "TEST",
        "GCRF / Earth",
    )


def test_timer_advances_clock_updates_readout_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    monkeypatch.setattr(player, "open_overview", lambda: None)
    monotonic_values = iter((10.0, 12.5))
    monkeypatch.setattr(app.time, "monotonic", lambda: next(monotonic_values))

    player.start()
    assert root.idle_updates == 1
    initial_timer = player._timer_id
    callback = root.callbacks[initial_timer]
    callback()

    assert player.clock.t_now == 102.5
    assert player.control_window.readouts[-1].startswith("Elapsed: 2.500 s")
    assert "UTC:" in player.control_window.readouts[-1]
    assert player.control_window.states[-1] == (0.025, True, 1.0)
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
    monkeypatch.setattr(player, "open_overview", lambda: None)
    monkeypatch.setattr(app.time, "monotonic", lambda: 0.0)

    player.start()
    root.protocols["WM_DELETE_WINDOW"]()

    assert root.destroyed
    assert not root.callbacks


def test_play_pause_space_seek_and_speed_controls_update_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    assert player.control_window.timeline_enabled

    space_callback = root.bindings["<space>"]
    assert space_callback(None) == "break"
    assert not player.clock.playing
    space_callback(None)
    assert not player.clock.playing
    root.bindings["<KeyRelease-space>"](None)
    player.control_window.on_toggle_play()
    assert player.clock.playing

    player.control_window.on_seek(0.5)
    assert player.clock.t_now == 150.0
    assert player.control_window.states[-1][0] == 0.5

    player.control_window.on_set_speed(10.0)
    assert player.clock.rate == 10.0
    assert player.control_window.states[-1][2] == 10.0


def test_start_opens_the_overview_and_overview_opens_both_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    opened: list[str] = []
    monkeypatch.setattr(
        player,
        "open_trajectory_view",
        lambda: opened.append("trajectory"),
    )
    monkeypatch.setattr(
        player,
        "open_speed_altitude_view",
        lambda: opened.append("speed-altitude"),
    )
    monkeypatch.setattr(app.time, "monotonic", lambda: 0.0)

    player.open_overview()
    assert opened == ["trajectory", "speed-altitude"]
    opened.clear()
    player.start()
    assert opened == ["trajectory", "speed-altitude"]
    player.close()


def test_overview_views_stay_synchronized_during_seek_and_playback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    windows = [FakeToplevel(), FakeToplevel()]
    monkeypatch.setattr(app.tk, "Toplevel", lambda _root: windows.pop(0))

    class FakeTrajectoryView:
        def __init__(self, *_args) -> None:
            self.states = []

        def build(self, _series, _time_unit):
            return object()

        def update_cursor(self, state) -> None:
            self.states.append(state.t)

        def close(self) -> None:
            pass

    class FakeSpeedAltitudeView:
        def __init__(self, _t_start_s) -> None:
            self.times = []

        def build(self, _series, _time_unit):
            return object()

        def update(self, t_s: float) -> None:
            self.times.append(t_s)

        def close(self) -> None:
            pass

    class FakeWidget:
        def pack(self, **_kwargs) -> None:
            pass

    class FakeCanvas:
        def __init__(self, _figure, *, master) -> None:
            assert isinstance(master, FakeToplevel)
            self.draw_idle_count = 0

        def get_tk_widget(self):
            return FakeWidget()

        def draw(self) -> None:
            pass

        def draw_idle(self) -> None:
            self.draw_idle_count += 1

    trajectory = FakeTrajectoryView()
    speed_altitude = FakeSpeedAltitudeView(100.0)
    monkeypatch.setattr(app, "Trajectory3DView", lambda *_args: trajectory)
    monkeypatch.setattr(app, "SpeedAltitudeView", lambda _t_start: speed_altitude)
    monkeypatch.setattr(app, "FigureCanvasTkAgg", FakeCanvas)

    player.open_overview()
    player.clock.pause()
    player.clock.seek(150.0)
    assert trajectory.states == [100.0, 150.0]
    assert speed_altitude.times == [100.0, 150.0]

    player.clock.play()
    player.clock.tick(2.0)
    assert trajectory.states[-1] == 152.0
    assert speed_altitude.times[-1] == 152.0

    player.control_window.on_set_speed(10.0)
    player.clock.tick(1.0)
    assert trajectory.states[-1] == 162.0
    assert speed_altitude.times[-1] == 162.0
    player.close()


def test_run_handles_sigint_and_restores_previous_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    monkeypatch.setattr(player, "open_overview", lambda: None)
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
            OemCursor([100.0, 200.0], make_states()),
            "TEST",
            "GCRF / Earth",
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
            self.updated_times: list[float] = []

        def build(self, _series, _time_unit):
            return object()

        def update(self, t_s: float) -> None:
            self.updated_times.append(t_s)

        def close(self) -> None:
            self.closed = True

    class FakeWidget:
        def __init__(self, events: list[str]) -> None:
            self.events = events

        def pack(self, **_kwargs) -> None:
            self.events.append("pack")

    class FakeCanvas:
        def __init__(self, _figure, *, master) -> None:
            assert master is window
            self.draw_idle_count = 0
            self.events = master.events

        def draw(self) -> None:
            self.events.append("draw")

        def draw_idle(self) -> None:
            self.draw_idle_count += 1

        def get_tk_widget(self):
            return FakeWidget(self.events)

    view = FakeView(100.0)
    monkeypatch.setattr(app, "SpeedAltitudeView", lambda t_start_s: view)
    monkeypatch.setattr(app, "FigureCanvasTkAgg", FakeCanvas)

    player.open_speed_altitude_view()
    assert player._speed_altitude_view is view
    assert player._speed_altitude_window is window
    assert view.updated_times == [100.0]
    assert window.events == ["pack", "idle", "draw"]
    canvas = player._speed_altitude_canvas
    assert canvas is not None
    player.open_speed_altitude_view()
    assert window.lifted

    player.clock.pause()
    player.clock.seek(150.0)
    assert view.updated_times[-1] == 150.0
    assert canvas.draw_idle_count == 1

    player.clock.play()
    player.clock.tick(2.0)
    assert view.updated_times[-1] == 152.0
    assert canvas.draw_idle_count == 2

    window.protocols["WM_DELETE_WINDOW"]()

    assert view.closed
    assert window.destroyed
    assert player._speed_altitude_view is None
    assert player._speed_altitude_window is None
    player.clock.seek(180.0)
    assert view.updated_times == [100.0, 150.0, 152.0]


def test_trajectory_view_uses_shared_cursor_and_closes_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot()
    player = make_app(monkeypatch, root)
    window = FakeToplevel()
    monkeypatch.setattr(app.tk, "Toplevel", lambda _root: window)

    class FakeTrajectoryView:
        def __init__(self, cursor, object_name, frame_context) -> None:
            assert cursor is player.cursor
            assert object_name == "TEST"
            assert frame_context == "GCRF / Earth"
            self.closed = False
            self.states = []

        def build(self, _series, _time_unit):
            return object()

        def update_cursor(self, state) -> None:
            self.states.append(state)

        def close(self) -> None:
            self.closed = True

    class FakeWidget:
        def __init__(self, events: list[str]) -> None:
            self.events = events

        def pack(self, **_kwargs) -> None:
            self.events.append("pack")

    class FakeCanvas:
        def __init__(self, _figure, *, master) -> None:
            assert master is window
            self.events = master.events
            self.draw_idle_count = 0

        def get_tk_widget(self):
            return FakeWidget(self.events)

        def draw(self) -> None:
            self.events.append("draw")

        def draw_idle(self) -> None:
            self.draw_idle_count += 1

    view = FakeTrajectoryView(player.cursor, "TEST", "GCRF / Earth")
    monkeypatch.setattr(app, "Trajectory3DView", lambda *_args: view)
    monkeypatch.setattr(app, "FigureCanvasTkAgg", FakeCanvas)

    player.open_trajectory_view()
    assert player._trajectory_view is view
    assert player._trajectory_window is window
    assert view.states[-1].t == 100.0
    assert window.window_title == "3D Orbit"
    canvas = player._trajectory_canvas
    assert canvas is not None

    player.clock.pause()
    player.clock.seek(150.0)
    assert view.states[-1].t == 150.0
    assert canvas.draw_idle_count == 1
    player.clock.play()
    player.clock.tick(2.0)
    assert view.states[-1].t == 152.0
    assert canvas.draw_idle_count == 2

    window.protocols["WM_DELETE_WINDOW"]()
    assert view.closed
    assert window.destroyed
    assert player._trajectory_view is None
    player.clock.seek(180.0)
    assert [state.t for state in view.states] == [100.0, 150.0, 152.0]


def test_old_tk_trajectory_uses_raster_image_for_moving_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot(patchlevel="8.5.9")
    player = make_app(monkeypatch, root)
    window = FakeToplevel()
    window.tk = root.tk

    class FakeTrajectoryView:
        def __init__(self, *_args) -> None:
            self.states = []
            self.closed = False

        def build(self, _series, _time_unit):
            return object()

        def update_cursor(self, state) -> None:
            self.states.append(state)

        def render_raster(self):
            return FakeRaster()

        def cursor_pixel(self, state) -> tuple[int, int]:
            return (7, 7) if state.t == 100.0 else (10, 11)

        def close(self) -> None:
            self.closed = True

    class FakeRaster:
        width = 20
        height = 20
        ppm_data = b"P6\n20 20\n255\n" + bytes(20 * 20 * 3)

    class FakeButton:
        def __init__(self, _master, **options) -> None:
            self.options = options

        def pack(self, **_kwargs) -> None:
            pass

    class FakePhotoImage:
        _next_id = 0

        def __init__(
            self,
            *,
            master,
            file: str | None = None,
            width: int = 0,
            height: int = 0,
        ) -> None:
            type(self)._next_id += 1
            self.name = f"fake-trajectory-image-{type(self)._next_id}"
            self.tk = master.tk
            self.width = width
            self.height = height
            self.source_data = Path(file).read_bytes() if file is not None else None
            self.put_calls: list[tuple[str, tuple[int, ...]]] = []

        def __str__(self) -> str:
            return self.name

        def put(self, color: str, *, to: tuple[int, ...]) -> None:
            self.put_calls.append((color, to))

    view = FakeTrajectoryView()
    monkeypatch.setattr(app.tk, "Toplevel", lambda _root: window)
    monkeypatch.setattr(app.tk, "Button", FakeButton)
    monkeypatch.setattr(app.tk, "PhotoImage", FakePhotoImage)
    monkeypatch.setattr(app, "Trajectory3DView", lambda *_args: view)

    player.open_trajectory_view()
    assert window.window_title == "3D Orbit (Tk 8.5.9 raster view)"
    assert player._trajectory_base_image is not None
    assert player._trajectory_base_image.source_data == FakeRaster.ppm_data
    assert player._trajectory_cursor_pixel == (7, 7)
    assert player._trajectory_image is not None
    assert player._trajectory_image.put_calls[-2:] == [
        ("#303030", (1, 1, 14, 14)),
        ("#ffcc00", (3, 3, 12, 12)),
    ]

    player.clock.seek(150.0)
    assert view.states[-1].t == 150.0
    assert player._trajectory_cursor_pixel == (10, 11)
    assert root.tk.image_commands
    assert player._trajectory_image.put_calls[-2:] == [
        ("#303030", (4, 5, 17, 18)),
        ("#ffcc00", (6, 7, 15, 16)),
    ]
    player.close_trajectory_view()
    assert view.closed
    assert window.destroyed


def test_old_tk_uses_graphical_raster_plot_and_updates_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeRoot(patchlevel="8.5.9")
    player = make_app(monkeypatch, root)
    window = FakeToplevel()
    window.tk = root.tk

    class FakeView:
        def __init__(self, _t_start_s) -> None:
            self.updated_times: list[float] = []
            self.closed = False

        def build(self, _series, _time_unit):
            return object()

        def update(self, t_s: float) -> None:
            self.updated_times.append(t_s)

        def render_rasters(self):
            return (FakeRaster(), FakeRaster())

        def close(self) -> None:
            self.closed = True

    class FakeRaster:
        width = 10
        height = 10
        ppm_data = b"P6\n10 10\n255\n"
        plot_left = 1
        plot_right = 8
        x_start = 0.0
        x_end = 2.0
        plot_top = 1
        plot_bottom = 8

        def cursor_column(self, elapsed_time: float) -> int:
            fraction = min(max(elapsed_time / 2.0, 0.0), 1.0)
            return round(self.plot_left + fraction * (self.plot_right - self.plot_left))

    class FakeButton:
        def __init__(self, _master, **kwargs) -> None:
            self.options = kwargs
            self.text = kwargs.get("text", "")

        def pack(self, **_kwargs) -> None:
            pass

    class FakePhotoImage:
        _next_id = 0

        def __init__(self, *, master, file: str | None = None, **_kwargs) -> None:
            type(self)._next_id += 1
            self.name = f"fake-image-{type(self)._next_id}"
            self.tk = master.tk
            self.put_calls: list[tuple[str, tuple[int, ...]]] = []
            self.loaded_file_path = file
            self.loaded_file_data = (
                Path(file).read_bytes() if file is not None else None
            )

        def __str__(self) -> str:
            return self.name

        def put(self, color: str, *, to: tuple[int, ...]) -> None:
            self.put_calls.append((color, to))

    view = FakeView(100.0)
    monkeypatch.setattr(app.tk, "Toplevel", lambda _root: window)
    monkeypatch.setattr(app.tk, "Button", FakeButton)
    monkeypatch.setattr(app.tk, "PhotoImage", FakePhotoImage)
    monkeypatch.setattr(app, "SpeedAltitudeView", lambda t_start_s: view)

    player.open_speed_altitude_view()

    assert player._speed_altitude_canvas is None
    assert len(player._speed_altitude_images) == 2
    assert player._speed_altitude_cursor_x == 1
    assert window.window_title == "Speed / Altitude (Tk 8.5.9 raster view)"
    assert player._speed_altitude_base_images[0].loaded_file_data is not None
    assert player._speed_altitude_base_images[0].loaded_file_data.startswith(
        b"P6\n10 10\n255\n"
    )
    assert all(
        image.loaded_file_path is not None and not Path(image.loaded_file_path).exists()
        for image in player._speed_altitude_base_images
    )
    assert all(
        image.put_calls[-1][0] == "#d62728" for image in player._speed_altitude_images
    )
    player.clock.seek(150.0)
    assert player._speed_altitude_cursor_x == 4
    assert all(
        image.put_calls[-1][0] == "#d62728" for image in player._speed_altitude_images
    )
    assert root.tk.image_commands

    player.close_speed_altitude_view()
    assert view.closed
    assert window.destroyed
