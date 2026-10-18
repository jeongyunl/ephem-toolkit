"""Tests for the wxPython playback application lifecycle."""

from __future__ import annotations

import signal
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.backend_bases import MouseButton
from matplotlib.figure import Figure

from ephem_toolkit.core.time_utils import tt_s_to_datetime
from ephem_toolkit.play_oem import app
from ephem_toolkit.play_oem.clock import PlaybackClock
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.play_oem_cli import build_arg_parser, parse_arguments
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
        self.focused = False
        self.sizer = None

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer

    def SetMinSize(self, _size) -> None:
        pass

    def SetSize(self, size) -> None:
        self.size = size

    def SetTitle(self, title: str) -> None:
        self.title = title

    def Bind(self, event_type, callback, _source=None) -> None:
        self.bindings[event_type] = callback

    def Show(self) -> bool:
        was_shown = self.shown
        self.shown = True
        return not was_shown

    def IsShown(self) -> bool:
        return self.shown

    def Raise(self) -> None:
        self.raised = True

    def SetFocus(self) -> None:
        self.focused = True

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
        self.callbacks: dict[int, tuple[str, object]] = {}
        self.disconnected_callbacks: list[int] = []
        self._next_callback_id = 0

    def draw(self) -> None:
        self.draw_count += 1

    def draw_idle(self) -> None:
        self.draw_idle_count += 1

    def mpl_connect(self, event_name: str, callback) -> int:
        self._next_callback_id += 1
        self.callbacks[self._next_callback_id] = (event_name, callback)
        return self._next_callback_id

    def mpl_disconnect(self, callback_id: int) -> None:
        self.disconnected_callbacks.append(callback_id)
        self.callbacks.pop(callback_id, None)

    def emit(self, event_name: str, event) -> None:
        for registered_event, callback in tuple(self.callbacks.values()):
            if registered_event == event_name:
                callback(event)


class FakeToolbar:
    def __init__(self, canvas: FakeCanvas) -> None:
        self.canvas = canvas
        self.mode = ""
        self.realized = False
        canvas.toolbar = self

    def Realize(self) -> None:
        self.realized = True

    def _wait_cursor_for_draw_cm(self):
        return nullcontext()


class FakeGraphPanelHost:
    instances: list[FakeGraphPanelHost] = []

    def __init__(
        self,
        parent,
        title: str,
        on_close,
        *,
        is_visible=None,
        on_redraw_request=None,
        panel_id: str,
        **_kwargs,
    ) -> None:
        self.parent = parent
        self.title = title
        self.on_close = on_close
        self.panel_id = panel_id
        self.canvas = None
        self.toolbar = None
        self.native_content = None
        self.focused = False
        self.destroyed = False
        self.redraw_requests = 0
        self.view_choices = _kwargs.get("view_choices", ())
        self.selected_view = _kwargs.get("selected_view")
        self.on_view_selected = _kwargs.get("on_view_selected")
        self.on_duplicate = _kwargs.get("on_duplicate")
        self.on_move_up = _kwargs.get("on_move_up")
        self.on_move_down = _kwargs.get("on_move_down")
        self.__class__.instances.append(self)

    def set_matplotlib_content(self, toolbar, canvas) -> None:
        self.toolbar = toolbar
        self.canvas = canvas

    def set_native_content(self, content) -> None:
        self.native_content = content

    def request_redraw(self) -> None:
        self.redraw_requests += 1
        if self.canvas is not None:
            self.canvas.draw_idle()

    def draw_if_needed(self) -> None:
        self.request_redraw()

    def draw_initial(self) -> None:
        if self.canvas is not None:
            self.canvas.draw()

    def SetFocus(self) -> None:
        self.focused = True

    def Layout(self) -> None:
        pass

    def Destroy(self) -> bool:
        self.destroyed = True
        return True


class FakeView:
    name = "fake"

    def __init__(self) -> None:
        self.updated_times: list[float] = []
        self.closed = False
        self._cursor_artists = ()

    @property
    def cursor_artists(self):
        return self._cursor_artists

    def build(self, _series, _time_unit) -> Figure:
        figure = Figure()
        self._cursor_artists = (figure.subplots().axvline(0.0),)
        return figure

    def update(self, t_s: float) -> None:
        self.updated_times.append(t_s)
        for artist in self._cursor_artists:
            artist.set_xdata([t_s, t_s])

    def close(self) -> None:
        self.closed = True


class FakeNativeWindow:
    pass


class FakeEmptyContent(FakeNativeWindow):
    def __init__(self, _parent, _widget_id: int, label: str) -> None:
        self.label = label
        self.name = ""

    def SetName(self, name: str) -> None:
        self.name = name


class FakeNativeView(FakeView):
    def build(self, _series, _time_unit) -> FakeNativeWindow:
        return FakeNativeWindow()


class FakeControlWindow:
    def __init__(
        self,
        _parent,
        on_toggle_play,
        on_set_speed,
        on_reverse,
        *,
        on_seek_to_time,
        on_step_samples,
        on_step_seconds,
        on_jump_to_start,
        on_jump_to_end,
        accelerator_parent=None,
        state_parent=None,
    ) -> None:
        self.panel = object()
        self.state_panel = object()
        self.state_parent = state_parent
        self.callbacks = {
            "toggle": on_toggle_play,
            "speed": on_set_speed,
            "reverse": on_reverse,
            "seek_to_time": on_seek_to_time,
            "step_samples": on_step_samples,
            "step_seconds": on_step_seconds,
            "jump_to_start": on_jump_to_start,
            "jump_to_end": on_jump_to_end,
        }
        self.accelerator_parent = accelerator_parent
        self.text = ""
        self.time_errors: list[str] = []

    def update_playback_state(self, text: str, playing: bool, rate: float) -> None:
        state = "Playing" if playing else "Paused"
        self.text = f"{text}\n{state} | {rate:+g}x"

    def update_current_state(self, state) -> None:
        self.current_state = state

    def show_time_error(self, message: str) -> None:
        self.time_errors.append(message)

    def clear_time_error(self) -> None:
        self.time_errors.clear()


class FakeWorkspace:
    def __init__(
        self,
        frame,
        on_seek,
        *,
        timeline_enabled,
        context=None,
        details=(),
        **_kwargs,
    ) -> None:
        self.frame = frame
        self.on_seek = on_seek
        self.timeline_enabled = timeline_enabled
        self.context = context
        self.details = details
        self.playback_page = object()
        self.state_page = object()
        self.middle_stack = object()
        self.right_stack = object()
        self.graph_panels = []
        self.progress = 0.0
        self.current_utc = ""
        self.playback_content = None
        self.state_content = None

    def set_playback_content(self, panel) -> None:
        self.playback_content = panel

    def set_state_content(self, panel) -> None:
        self.state_content = panel

    def update_timeline(self, progress: float, current_utc: str) -> None:
        self.progress = progress
        self.current_utc = current_utc

    def add_graph_panel(self, panel, stack: str = "middle") -> None:
        panel.stack = stack
        self.graph_panels.append(panel)

    def remove_graph_panel(self, panel, stack: str = "middle") -> None:
        self.graph_panels.remove(panel)

    def replace_graph_panel(self, old_panel, new_panel, stack: str = "middle") -> None:
        new_panel.stack = stack
        self.graph_panels[self.graph_panels.index(old_panel)] = new_panel

    def draw_initial_graphs(self) -> None:
        for panel in self.graph_panels:
            panel.draw_initial()

    def queue_graph_redraw(self, panel) -> None:
        panel.draw_if_needed()

    def close(self) -> None:
        pass


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
    three_d_backend: str = "matplotlib",
    clock: PlaybackClock | None = None,
    tick_interval_ms: int = 33,
) -> tuple[app.PlayerApp, list[FakeView], list[FakeCanvas], list[FakeFrame]]:
    frames: list[FakeFrame] = []
    views: list[FakeView] = []
    canvases: list[FakeCanvas] = []
    FakeGraphPanelHost.instances = []
    monkeypatch.setattr(app.wx, "GetApp", lambda: None)
    monkeypatch.setattr(app.wx, "App", FakeWxApp)
    monkeypatch.setattr(
        app.wx, "Frame", lambda *args, **kwargs: _frame(*args, **kwargs)
    )
    monkeypatch.setattr(app.wx, "StaticText", FakeStaticText)
    monkeypatch.setattr(app.wx, "BoxSizer", FakeBoxSizer)
    monkeypatch.setattr(app.wx, "Timer", FakeTimer)
    monkeypatch.setattr(app.control_window, "ControlWindow", FakeControlWindow)
    monkeypatch.setattr(app.workspace, "Workspace", FakeWorkspace)
    monkeypatch.setattr(app, "GraphPanelHost", FakeGraphPanelHost)
    monkeypatch.setattr(app, "FigureCanvasWxAgg", lambda *args: _canvas(*args))
    monkeypatch.setattr(app, "NavigationToolbar2WxAgg", FakeToolbar)
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

    monkeypatch.setattr(app.speed_altitude, "SpeedAltitudeView", create_view)
    monkeypatch.setattr(app.rtn, "RtnDeltaView", create_view)
    monkeypatch.setattr(app.angular_velocity, "AngularVelocityView", create_view)
    monkeypatch.setattr(app.direction_change, "DirectionChangeView", create_view)
    monkeypatch.setattr(app.distance, "GeocentricDistanceView", create_view)
    monkeypatch.setattr(app.state_components, "StateComponentsView", create_view)
    monkeypatch.setattr(app.trajectory3d, "Trajectory3DView", create_view)
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
        three_d_backend=three_d_backend,
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
    assert len(frames) == 1
    assert frames[0].title == "play-oem (3D backend: matplotlib)"
    assert frames[0].shown
    assert len(views) == len(canvases) == 1
    assert player._open_views["state-components"].panel in player.workspace.graph_panels
    assert views[0].updated_times == [150.0]
    assert player._timer.interval == 40
    assert player._timer.running
    assert player.clock.t_now == 150.0
    assert player.clock.rate == -10.0
    assert player.clock.playing
    assert player.clock.loop
    assert "Elapsed: 50.000 s" in player.control_window.text
    assert "Paused" not in player.control_window.text
    assert player.workspace.progress == 0.5
    assert player.workspace.playback_content is player.control_window.panel
    assert player.control_window.state_parent is player.workspace.state_page
    assert player.workspace.state_content is player.control_window.state_panel

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
    assert player.workspace.progress == pytest.approx(0.025)
    assert player.workspace.current_utc in player.control_window.text
    assert "Elapsed: 2.500 s" in player.control_window.text
    assert "UTC:" in player.control_window.text
    assert "Playing | +1x" in player.control_window.text
    assert all(view.updated_times[-1] == 102.5 for view in views)
    assert all(canvas.draw_idle_count == 2 for canvas in canvases)

    player.close()


def test_workspace_timeline_uses_the_existing_fraction_seek_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    player.start()

    player.workspace.on_seek(0.5)

    assert player.clock.t_now == 150.0
    assert player.workspace.progress == 0.5
    player.close()


def test_matplotlib_cursor_updates_use_full_redraw_not_partial_blits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    player, _views, _canvases, _frames = make_app(
        monkeypatch, plots=("speed-altitude",)
    )
    monkeypatch.setattr(
        app, "FigureCanvasWxAgg", lambda _parent, _id, figure: FigureCanvasAgg(figure)
    )

    player.start()
    opened = player._open_views["speed-altitude"]
    canvas = opened.canvas
    assert canvas is not None and canvas.supports_blit
    redraw_calls: list[bool] = []
    partial_blit_calls: list[bool] = []
    restore_region = canvas.restore_region
    blit = canvas.blit
    draw_idle = canvas.draw_idle
    canvas.restore_region = lambda *args, **kwargs: (
        partial_blit_calls.append(True),
        restore_region(*args, **kwargs),
    )[1]
    canvas.blit = lambda *args, **kwargs: (
        partial_blit_calls.append(True),
        blit(*args, **kwargs),
    )[1]
    canvas.draw_idle = lambda: (redraw_calls.append(True), draw_idle())[1]

    player.clock.seek(150.0)
    assert len(redraw_calls) == 1
    assert not partial_blit_calls
    assert all(not artist.get_animated() for artist in opened.view.cursor_artists)
    player.close()


def test_matplotlib_3d_render_throttle_does_not_skip_clock_ticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, canvases, _frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        clock=make_clock(playing=True),
    )
    monotonic_values = iter((0.0, 0.05, 0.09, 0.16))
    monkeypatch.setattr(app.time, "monotonic", lambda: next(monotonic_values))
    player.start()
    canvas = canvases[0]

    player._on_timer(SimpleNamespace())
    player._on_timer(SimpleNamespace())
    player._on_timer(SimpleNamespace())

    assert player.clock.t_now == pytest.approx(100.16)
    assert views[0].updated_times == [100.0, 100.05, 100.09, 100.16]
    assert canvas.draw_idle_count == 4
    player.close()


def test_time_entry_changes_clock_only_for_valid_in_range_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)

    player.control_window.callbacks["seek_to_time"]("not-a-time")
    assert player.clock.t_now == 100.0
    assert player.control_window.time_errors

    player.control_window.callbacks["seek_to_time"]("10s")
    assert player.clock.t_now == 110.0
    assert not player.control_window.time_errors

    utc_timestamp = tt_s_to_datetime(150.0).isoformat().replace("+00:00", "Z")
    player.control_window.callbacks["seek_to_time"](utc_timestamp)
    assert player.clock.t_now == pytest.approx(150.0)

    player.control_window.callbacks["seek_to_time"]("1000s")
    assert player.clock.t_now == pytest.approx(150.0)
    assert player.control_window.time_errors

    player.close()


def test_clock_notifications_update_views_and_existing_plot_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, frames = make_app(
        monkeypatch,
        plots=("overview", "trajectory-3d"),
    )
    player.start()
    plot_panels = [view.panel for view in player._open_views.values()]

    player.clock.seek(150.0)
    player.open_group("overview")
    player.open_view("trajectory-3d")

    assert all(view.updated_times == [100.0, 150.0] for view in views)
    assert all(panel.focused for panel in plot_panels)
    assert len(frames) == 1

    player.close()


def test_cli_selection_opens_through_the_dashboard_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli_args = parse_arguments(
        build_arg_parser(),
        ["orbit.oem", "--plots", "state-vectors"],
    )
    player, _views, _canvases, frames = make_app(monkeypatch, plots=cli_args.plots)

    player.start()

    assert set(player._open_views) == {"trajectory-3d", "state-components"}
    assert len(frames) == 1

    player.open_group("state")
    player.open_view("trajectory-3d")

    assert len(frames) == 1
    assert all(view.panel.focused for view in player._open_views.values())

    player.close()


def test_rtn_selection_opens_through_the_dashboard_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(monkeypatch, plots=("rtn",))

    player.start()

    assert len(views) == 1
    assert set(player._open_views) == {"rtn"}
    player.close()


def test_angular_velocity_selection_opens_through_the_dashboard_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(
        monkeypatch, plots=("angular-velocity",)
    )

    player.start()

    assert len(views) == 1
    assert set(player._open_views) == {"angular-velocity"}
    player.close()


def test_direction_change_selection_opens_through_the_dashboard_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(
        monkeypatch, plots=("direction-change",)
    )

    player.start()

    assert len(views) == 1
    assert set(player._open_views) == {"direction-change"}
    player.close()


def test_distance_selection_opens_through_the_dashboard_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(monkeypatch, plots=("distance",))

    player.start()

    assert len(views) == 1
    assert set(player._open_views) == {"distance"}
    player.close()

    player.close()


def test_motion_group_opens_all_diagnostic_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(monkeypatch, plots=("motion",))

    player.start()

    assert len(views) == 4
    assert set(player._open_views) == {
        "rtn",
        "angular-velocity",
        "direction-change",
        "distance",
    }
    player.close()


@pytest.mark.parametrize(
    "view_name", ("rtn", "angular-velocity", "direction-change", "distance")
)
def test_closing_one_diagnostic_view_keeps_other_motion_views_open(
    monkeypatch: pytest.MonkeyPatch,
    view_name: str,
) -> None:
    player, views, _canvases, _frames = make_app(monkeypatch, plots=("motion",))
    player.start()

    player.close_view(view_name)

    assert view_name not in player._open_views
    assert len(player._open_views) == 3
    view_names = ("rtn", "angular-velocity", "direction-change", "distance")
    assert views[view_names.index(view_name)].closed
    assert all(
        view.closed == (name == view_name) for name, view in zip(view_names, views)
    )
    player.close()


def test_auto_3d_backend_falls_back_to_matplotlib_with_warning(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_to_create_vtk_view(*_args, **_kwargs):
        raise app.trajectory3d_selection.VTKBackendUnavailableError(
            "OpenGL context unavailable"
        )

    monkeypatch.setattr(
        app.trajectory3d_selection, "create_vtk_view", fail_to_create_vtk_view
    )
    player, views, _canvases, frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        three_d_backend="auto",
    )

    player.start()

    assert len(views) == 1
    assert player._selected_3d_backend == "matplotlib"
    assert player.frame.title == "play-oem (3D backend: matplotlib)"
    assert len(frames) == 1
    assert len(FakeGraphPanelHost.instances) == 2
    assert FakeGraphPanelHost.instances[0].destroyed
    assert not FakeGraphPanelHost.instances[1].destroyed
    assert "falling back to Matplotlib" in capsys.readouterr().err

    player.close()


def test_auto_3d_backend_falls_back_when_vtk_render_context_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vtk_view = FakeNativeView()

    def fail_render_context(_view) -> None:
        raise app.trajectory3d_selection.VTKBackendUnavailableError(
            "VTK did not complete its initial render"
        )

    monkeypatch.setattr(app.wx, "Window", FakeNativeWindow)
    monkeypatch.setattr(
        app.trajectory3d_selection, "create_vtk_view", lambda *_args: vtk_view
    )
    monkeypatch.setattr(
        app.trajectory3d_selection,
        "validate_vtk_render_context",
        fail_render_context,
    )
    player, views, _canvases, frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        three_d_backend="auto",
    )

    player.start()

    assert len(views) == 1
    assert vtk_view.closed
    assert player._selected_3d_backend == "matplotlib"
    assert len(frames) == 1
    assert len(FakeGraphPanelHost.instances) == 2
    assert FakeGraphPanelHost.instances[0].destroyed
    assert not FakeGraphPanelHost.instances[1].destroyed
    assert "VTK did not complete its initial render" in capsys.readouterr().err

    player.close()


def test_vtk_view_is_embedded_in_a_graph_panel_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vtk_view = FakeNativeView()
    validated_views: list[FakeView] = []
    monkeypatch.setattr(app.wx, "Window", FakeNativeWindow)
    monkeypatch.setattr(
        app.trajectory3d_selection, "create_vtk_view", lambda *_args: vtk_view
    )
    monkeypatch.setattr(
        app.trajectory3d_selection,
        "validate_vtk_render_context",
        validated_views.append,
    )
    player, _views, _canvases, frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        three_d_backend="vtk",
    )

    player.start()

    opened = player._open_views["trajectory-3d"]
    assert len(frames) == 1
    assert opened.view is vtk_view
    assert opened.panel.native_content is not None
    assert opened.panel.parent is player.workspace.middle_stack
    assert opened.panel.panel_id == opened.panel_id
    assert validated_views == [vtk_view]

    player.close()

    assert vtk_view.closed
    assert opened.panel.destroyed


def test_explicit_vtk_backend_reports_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_create_vtk_view(*_args, **_kwargs):
        raise app.trajectory3d_selection.VTKBackendUnavailableError(
            "OpenGL context unavailable"
        )

    monkeypatch.setattr(
        app.trajectory3d_selection, "create_vtk_view", fail_to_create_vtk_view
    )
    player, views, _canvases, frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        three_d_backend="vtk",
    )

    with pytest.raises(RuntimeError, match="playback,vtk"):
        player.start()

    assert views == []
    assert len(frames) == 1
    assert len(FakeGraphPanelHost.instances) == 1
    assert FakeGraphPanelHost.instances[0].destroyed
    assert not player._open_panels
    assert player._selected_3d_backend is None

    player.close()


def test_matplotlib_backend_does_not_load_vtk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_vtk_loaded(*_args, **_kwargs):
        raise AssertionError("Matplotlib backend must not load VTK")

    monkeypatch.setattr(
        app.trajectory3d_selection, "create_vtk_view", fail_if_vtk_loaded
    )
    player, views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        three_d_backend="matplotlib",
    )

    player.start()

    assert len(views) == 1
    assert player._selected_3d_backend == "matplotlib"

    player.close()


def test_plot_click_seeks_and_respects_toolbar_modes_and_non_time_axes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
    )
    player.start()
    canvas = canvases[0]
    click_event = SimpleNamespace(
        button=MouseButton.LEFT,
        inaxes=SimpleNamespace(name="rectilinear"),
        xdata=1.0,
    )

    canvas.emit("button_press_event", click_event)

    assert player.clock.t_now == 160.0
    assert views[0].updated_times == [100.0, 160.0]
    assert "Elapsed: 60.000 s" in player.control_window.text

    for toolbar_mode in ("pan/zoom", "zoom rect"):
        canvas.toolbar.mode = toolbar_mode
        canvas.emit(
            "button_press_event",
            SimpleNamespace(
                button=MouseButton.LEFT,
                inaxes=SimpleNamespace(name="rectilinear"),
                xdata=1.5,
            ),
        )
        assert player.clock.t_now == 160.0

    canvas.toolbar.mode = ""
    for ignored_event in (
        SimpleNamespace(button=MouseButton.RIGHT, inaxes=click_event.inaxes, xdata=1.5),
        SimpleNamespace(button=MouseButton.LEFT, inaxes=None, xdata=1.5),
        SimpleNamespace(
            button=MouseButton.LEFT,
            inaxes=SimpleNamespace(name="3d"),
            xdata=1.5,
        ),
        SimpleNamespace(button=MouseButton.LEFT, inaxes=click_event.inaxes, xdata=None),
    ):
        canvas.emit("button_press_event", ignored_event)
        assert player.clock.t_now == 160.0

    player.close()


def test_all_open_views_stay_synchronized_for_seeks_and_time_plot_clicks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, canvases, _frames = make_app(
        monkeypatch,
        plots=(
            "trajectory-3d",
            "state-components",
            "speed-altitude",
            "rtn",
            "angular-velocity",
            "direction-change",
            "distance",
        ),
    )
    player.start()
    player.clock.seek(150.0)

    assert all(view.updated_times[-1] == 150.0 for view in views)

    for canvas, elapsed_minutes in zip(canvases[1:], (0.5, 1.0, 1.25, 1.5, 1.6, 1.65)):
        canvas.emit(
            "button_press_event",
            SimpleNamespace(
                button=MouseButton.LEFT,
                inaxes=SimpleNamespace(name="rectilinear"),
                xdata=elapsed_minutes,
            ),
        )
        assert all(view.updated_times[-1] == player.clock.t_now for view in views)

    assert player.clock.t_now == 199.0

    player.close()


def test_closing_one_plot_unsubscribes_only_that_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, canvases, frames = make_app(
        monkeypatch,
        plots=("state-components",),
    )
    player.start()
    plot_panel = player._open_views["state-components"].panel

    player.close_view("state-components")
    player.clock.seek(160.0)

    assert plot_panel.destroyed
    assert canvases[0].disconnected_callbacks == [1]
    assert canvases[0].callbacks == {}
    assert views[0].closed
    assert views[0].updated_times == [100.0]
    assert not player._closed
    assert player._timer.running

    player.clock.play()
    player.open_view("state-components")
    reopened_view = views[-1]
    assert reopened_view.updated_times == [160.0]

    player.clock.tick(1.0)
    assert reopened_view.updated_times == [160.0, 161.0]
    assert views[0].updated_times == [100.0]

    player.close()


def test_panel_instances_can_duplicate_views_and_keep_independent_lifecycles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
    )
    player.start()
    default = player._open_views["speed-altitude"]

    player.open_panel_view("speed-altitude", "duplicate-middle")
    player.open_panel_view("speed-altitude", "duplicate-right", stack="right")
    middle_duplicate = player._open_panels["duplicate-middle"]
    right_duplicate = player._open_panels["duplicate-right"]

    assert len(player._open_panels) == 3
    assert (
        len({default.panel_id, middle_duplicate.panel_id, right_duplicate.panel_id})
        == 3
    )
    assert default.panel.panel_id == default.panel_id
    assert middle_duplicate.panel.panel_id == "duplicate-middle"
    assert right_duplicate.panel.parent is player.workspace.right_stack
    assert dict(middle_duplicate.panel.view_choices)["speed-altitude"] == (
        "Speed / Altitude"
    )
    assert middle_duplicate.panel.selected_view == "speed-altitude"

    player.clock.seek(150.0)
    player.close_panel("duplicate-middle")
    player.clock.seek(160.0)

    assert views[0].updated_times == [100.0, 150.0, 160.0]
    assert views[1].closed
    assert views[1].updated_times == [100.0, 150.0]
    assert views[2].updated_times == [100.0, 150.0, 160.0]
    assert "duplicate-middle" not in player._open_panels

    right_duplicate.panel.on_view_selected("rtn")
    assert views[2].closed
    assert player._open_panels["duplicate-right"].view_name == "rtn"
    assert player._open_panels["duplicate-right"].panel.panel_id == "duplicate-right"
    player.clock.seek(170.0)
    assert views[-1].updated_times == [160.0, 170.0]

    player.close_panel("duplicate-right")
    player.clock.seek(180.0)
    assert views[-1].updated_times == [160.0, 170.0]
    assert views[0].updated_times[-1] == 180.0
    player.close()


def test_new_graph_panel_starts_empty_and_can_switch_between_empty_and_a_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
    )
    monkeypatch.setattr(app.wx, "Window", FakeNativeWindow)
    monkeypatch.setattr(app.wx, "StaticText", FakeEmptyContent)
    player.start()

    player._add_graph_panel("middle")

    empty_panel = player._open_panels[FakeGraphPanelHost.instances[-1].panel_id]
    assert empty_panel.view_name == app.EMPTY_GRAPH_VIEW
    assert empty_panel.panel.selected_view == app.EMPTY_GRAPH_VIEW
    assert empty_panel.panel.view_choices[0] == (app.EMPTY_GRAPH_VIEW, "Empty")
    assert empty_panel.panel.native_content.label == "Select a graph view above"

    empty_panel.panel.on_view_selected("rtn")
    rtn_panel = player._open_panels[empty_panel.panel_id]
    assert empty_panel.panel.destroyed
    assert rtn_panel.view_name == "rtn"
    assert player.workspace.graph_panels.index(rtn_panel.panel) == 1

    rtn_panel.panel.on_view_selected(app.EMPTY_GRAPH_VIEW)
    empty_again = player._open_panels[empty_panel.panel_id]
    assert views[-1].closed
    assert empty_again.view_name == app.EMPTY_GRAPH_VIEW
    assert player.workspace.graph_panels.index(empty_again.panel) == 1

    player.close()


def test_failed_view_change_restores_the_original_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
    )
    monkeypatch.setattr(app.wx, "Window", FakeNativeWindow)
    monkeypatch.setattr(app.wx, "StaticText", FakeEmptyContent)

    class FailingView(FakeView):
        def build(self, _series, _time_unit):
            raise RuntimeError("view initialization failed")

    failed_view = FailingView()
    errors: list[tuple[object, ...]] = []
    monkeypatch.setattr(app.rtn, "RtnDeltaView", lambda *_args: failed_view)
    monkeypatch.setattr(app.wx, "MessageBox", lambda *args: errors.append(args))
    player.start()
    player._add_graph_panel("middle")

    original = player._open_panels[FakeGraphPanelHost.instances[-1].panel_id]
    original_index = player.workspace.graph_panels.index(original.panel)
    original.panel.on_view_selected("rtn")

    assert player._open_panels[original.panel_id] is original
    assert player.workspace.graph_panels[original_index] is original.panel
    assert not original.panel.destroyed
    assert failed_view.closed
    assert len(errors) == 1
    player.close()


def test_panel_action_duplicates_as_a_new_independent_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
    )
    player.start()
    original = player._open_views["speed-altitude"]

    original.panel.on_duplicate()

    assert len(player._open_panels) == 2
    duplicate = next(
        opened for opened in player._open_panels.values() if opened is not original
    )
    assert duplicate.view_name == original.view_name
    assert duplicate.panel_id != original.panel_id
    assert duplicate.view is not original.view
    player.close_panel(duplicate.panel_id)
    assert views[1].closed
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
    assert player.frame is None
    assert player.workspace is None
    assert player.control_window is None
    assert player._timer is None
    assert not player._view_registry.registered_views
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
    monkeypatch.setattr(app.control_window, "ControlWindow", FakeControlWindow)
    monkeypatch.setattr(app.workspace, "Workspace", FakeWorkspace)

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
