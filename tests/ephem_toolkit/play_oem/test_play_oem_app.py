"""Tests for the wxPython playback application lifecycle."""

from __future__ import annotations

import signal
import time
from datetime import datetime, timezone
from collections.abc import Callable
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from matplotlib.backend_bases import MouseButton
from matplotlib.figure import Figure

from ephem_toolkit.core.time_utils import datetime_to_tt_s, tt_s_to_datetime
from ephem_toolkit.play_oem.app import controller as app
from ephem_toolkit.play_oem.app import panel_management
from ephem_toolkit.play_oem.app import support as app_support
from ephem_toolkit.play_oem.app import view_factory
from ephem_toolkit.play_oem.clock import PlaybackClock
from ephem_toolkit.play_oem.cursor import OemCursor
from ephem_toolkit.play_oem.ground_track import GroundTrackSource
from ephem_toolkit.play_oem.ground_stations import GroundStation
from ephem_toolkit.play_oem import time_range
from ephem_toolkit.play_oem.play_oem_cli import build_arg_parser, parse_arguments
from ephem_toolkit.play_oem.series import compute_orbit_series
from ephem_toolkit.play_oem.time_unit import TimeUnit
from ephem_toolkit.play_oem.views.registry import VIEW_LABELS


@pytest.mark.parametrize(
    ("initial_rate", "selected_rate", "expected_rate"),
    [
        (1.0, 10.0, 10.0),
        (10.0, 10.0, 20.0),
        (20.0, 10.0, 30.0),
        (90.0, 10.0, 100.0),
        (100.0, 10.0, 10.0),
        (1000.0, 100.0, 100.0),
        (-10.0, -10.0, -20.0),
        (-100.0, -10.0, -10.0),
        (1000.0, -10.0, -10.0),
        (-1000.0, -1000.0, -2000.0),
        (100.0, 1.0, 1.0),
        (-100.0, -1.0, -1.0),
        (100.0, -1.0, -1.0),
    ],
)
def test_playback_rate_selection_handles_direction_progression_and_reset(
    monkeypatch: pytest.MonkeyPatch,
    initial_rate: float,
    selected_rate: float,
    expected_rate: float,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, clock=make_clock(rate=initial_rate, playing=True)
    )

    player._set_playback_rate(selected_rate)

    assert player.clock.rate == expected_rate
    assert player.clock.playing
    assert player.workspace.playback_state == (True, expected_rate)


@pytest.mark.parametrize(
    ("initial_rate", "direction", "expected_rate"),
    [(100.0, -1, -100.0), (-100.0, 1, 100.0)],
)
def test_direction_play_button_preserves_current_speed_and_resumes(
    monkeypatch: pytest.MonkeyPatch,
    initial_rate: float,
    direction: int,
    expected_rate: float,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, clock=make_clock(rate=initial_rate, playing=False)
    )

    play = (
        player._play_reverse_at_current_speed
        if direction < 0
        else player._play_forward_at_current_speed
    )
    play()

    assert player.clock.rate == expected_rate
    assert player.clock.playing
    assert player.workspace.playback_state == (True, expected_rate)


@pytest.mark.parametrize(
    ("initial_rate", "selected_rate"),
    [(100.0, -1.0), (-100.0, 1.0)],
)
def test_one_x_speed_button_sets_rate_without_starting_paused_playback(
    monkeypatch: pytest.MonkeyPatch,
    initial_rate: float,
    selected_rate: float,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, clock=make_clock(rate=initial_rate, playing=False)
    )

    player._set_playback_rate(selected_rate)

    assert player.clock.rate == selected_rate
    assert not player.clock.playing
    assert player.workspace.playback_state == (False, selected_rate)


def test_playback_speed_selection_while_paused_does_not_start_playback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, clock=make_clock(playing=False)
    )

    player._set_playback_rate(100.0)

    assert player.clock.rate == 100.0
    assert not player.clock.playing
    assert player.workspace.playback_state == (False, 100.0)


def test_timeline_tooltip_omits_fractional_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)

    assert "." not in player._timeline_tooltip_at(0.12345)


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


class FakePlaybackStatusBar:
    def __init__(self, _parent=None) -> None:
        self.file_name: str | None = None
        self.object: tuple[str, str] | None = None
        self.message = ""

    def set_file_name(self, file_name: str | None) -> None:
        self.file_name = file_name

    def set_object(self, object_name: str, object_id: str = "") -> None:
        self.object = (object_name, object_id)

    def set_message(self, message: str) -> None:
        self.message = message


class FakeFrame:
    def __init__(self, parent, *, title: str, size=None) -> None:
        self.parent = parent
        self.title = title
        self.size = size
        self.bindings: dict[object, Callable[..., object]] = {}
        self.destroyed = False
        self.shown = False
        self.raised = False
        self.focused = False
        self.sizer = None
        self.menu_bar = None
        self.position = (0, 0)

    def SetMenuBar(self, menu_bar) -> None:
        self.menu_bar = menu_bar

    def SetSizer(self, sizer) -> None:
        self.sizer = sizer

    def SetMinSize(self, _size) -> None:
        pass

    def IsMaximized(self) -> bool:
        return False

    def GetSize(self):
        return SimpleNamespace(width=1200, height=800)

    def SetSize(self, size) -> None:
        self.size = size

    def GetPosition(self):
        return SimpleNamespace(x=self.position[0], y=self.position[1])

    def SetPosition(self, position) -> None:
        self.position = tuple(position)

    def SetTitle(self, title: str) -> None:
        self.title = title

    def Bind(self, event_type, callback, _source=None, **_kwargs) -> None:
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
        # A native frame destroys its descendant windows after EVT_CLOSE.
        for panel in FakeGraphPanelHost.instances:
            panel.Destroy()
        self.destroyed = True
        return True

    def Destroy(self) -> None:
        self.destroyed = True


class FakeStaticText:
    def __init__(self, _parent, _id: int, label: str) -> None:
        self.label = label

    def SetLabel(self, label: str) -> None:
        self.label = label


class FakeMenuBar:
    def __init__(self) -> None:
        self.menus = []

    def Append(self, menu, title: str) -> None:
        self.menus.append((menu, title))


class FakeMenu:
    def __init__(self) -> None:
        self.items = []
        self._next_item_id = 1

    def Append(self, item_id: int, label: str):
        if item_id == app.wx.ID_ANY:
            item_id = self._next_item_id
            self._next_item_id += 1
        self.items.append((item_id, label))
        return SimpleNamespace(GetId=lambda: item_id)

    def Delete(self, item_id: int) -> None:
        self.items = [item for item in self.items if item[0] != item_id]


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
    def __init__(self, parent, _id: int, _figure) -> None:
        self.parent = parent
        self.draw_count = 0
        self.draw_idle_count = 0
        self.callbacks: dict[int, tuple[str, Callable[..., object]]] = {}
        self.disconnected_callbacks: list[int] = []
        self._next_callback_id = 0
        self.toolbar: FakeToolbar | None = None

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
        self.graph_scroller = object()
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

    def build(self, _series, _time_unit) -> object:
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
        on_reverse,
        *,
        on_set_render_rate_fps,
        render_rate_fps,
        on_set_interpolation,
        use_oem_interpolation,
        interpolation_method,
        interpolation_degree,
        active_interpolation,
        display_time_zone="UTC",
        on_set_display_time_zone=None,
        on_step_samples,
        on_step_seconds,
        on_jump_to_start,
        on_jump_to_end,
        accelerator_parent=None,
        state_parent=None,
    ) -> None:
        self.settings_scroller = object()
        self.state_scroller = object()
        self.state_parent = state_parent
        self.active_interpolation = active_interpolation
        self.callbacks = {
            "toggle": on_toggle_play,
            "render_rate": on_set_render_rate_fps,
            "interpolation": on_set_interpolation,
            "use_oem_interpolation": use_oem_interpolation,
            "interpolation_method": interpolation_method,
            "interpolation_degree": interpolation_degree,
            "reverse": on_reverse,
            "step_samples": on_step_samples,
            "step_seconds": on_step_seconds,
            "jump_to_start": on_jump_to_start,
            "jump_to_end": on_jump_to_end,
        }
        self.accelerator_parent = accelerator_parent

    def bind_time_entry(self, _time_entry) -> None:
        pass

    def update_active_interpolation(self, summary: str) -> None:
        self.active_interpolation = summary

    def update_current_state(self, state) -> None:
        self.current_state = state


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
        self.settings_page = object()
        self.state_page = object()
        self.main_analysis_stack = object()
        self.comparison_stack = object()
        self.graph_panels = []
        self.progress = 0.0
        self.current_utc = ""
        self.timeline_time_entry = object()
        self.callbacks = {"seek_to_time": _kwargs["on_seek_to_time"]}
        self.time_errors: list[str] = []
        self.playback_speed_buttons = {
            rate: SimpleNamespace(SetFocus=lambda: None)
            for rate in (-1000.0, -100.0, -10.0, 10.0, 100.0, 1000.0)
        }
        self.playback_state = None
        self.settings_content = None
        self.state_content = None
        self.neutral_focus_count = 0

    def set_settings_content(self, panel) -> None:
        self.settings_content = panel

    def set_state_content(self, panel) -> None:
        self.state_content = panel

    def focus_neutral_target(self) -> None:
        self.neutral_focus_count += 1

    def set_oem_loaded(self, _loaded: bool) -> None:
        pass

    def select_ground_stations(self) -> None:
        pass

    def update_oem_information(self, _context, _details, _timeline_enabled) -> None:
        pass

    def set_time_range_controls(self, *controls) -> None:
        self.time_range_controls = controls

    def update_timeline(
        self, progress: float, current_utc: str, *, playing: bool = False
    ) -> None:
        self.progress = progress
        self.current_utc = current_utc

    def show_time_error(self, message: str) -> None:
        self.time_errors.append(message)

    def clear_time_error(self) -> None:
        self.time_errors.clear()

    def set_current_time_entry(self, current_utc: str) -> None:
        self.current_utc = current_utc

    def update_playback_state(self, playing: bool, rate: float) -> None:
        self.playback_state = (playing, rate)

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
    render_rate_fps: int | None = None,
    saved_state: app.SavedAppState | None = None,
    config_path=None,
    initial_file_path: str | None = None,
    oem_loaded: bool = True,
) -> tuple[Any, list[FakeView], list[FakeCanvas], list[FakeFrame]]:
    frames: list[FakeFrame] = []
    views: list[FakeView] = []
    canvases: list[FakeCanvas] = []
    FakeGraphPanelHost.instances = []
    monkeypatch.setattr(app.wx, "GetApp", lambda: None)
    monkeypatch.setattr(app.wx, "App", FakeWxApp)
    monkeypatch.setattr(
        app.wx, "Frame", lambda *args, **kwargs: _frame(*args, **kwargs)
    )
    monkeypatch.setattr(app, "PlaybackStatusBar", FakePlaybackStatusBar)
    monkeypatch.setattr(app.wx, "MenuBar", FakeMenuBar)
    monkeypatch.setattr(app.wx, "Menu", FakeMenu)
    monkeypatch.setattr(app.wx, "StaticText", FakeStaticText)
    monkeypatch.setattr(app.wx, "BoxSizer", FakeBoxSizer)
    monkeypatch.setattr(app.wx, "Timer", FakeTimer)
    monkeypatch.setattr(app.wx, "CallAfter", lambda callback, *args: callback(*args))
    monkeypatch.setattr(app.control_window, "ControlWindow", FakeControlWindow)
    monkeypatch.setattr(app.workspace, "Workspace", FakeWorkspace)
    monkeypatch.setattr(panel_management, "GraphPanelHost", FakeGraphPanelHost)
    monkeypatch.setattr(
        panel_management, "FigureCanvasWxAgg", lambda *args: _canvas(*args)
    )
    monkeypatch.setattr(panel_management, "NavigationToolbar2WxAgg", FakeToolbar)
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

    monkeypatch.setattr(view_factory.speed_altitude, "SpeedAltitudeView", create_view)
    monkeypatch.setattr(view_factory.rtn, "RtnDeltaView", create_view)
    monkeypatch.setattr(
        view_factory.angular_velocity, "AngularVelocityView", create_view
    )
    monkeypatch.setattr(
        view_factory.direction_change, "DirectionChangeView", create_view
    )
    monkeypatch.setattr(view_factory.distance, "GeocentricDistanceView", create_view)
    monkeypatch.setattr(
        view_factory.state_components, "StateComponentsView", create_view
    )
    monkeypatch.setattr(view_factory.trajectory3d, "Trajectory3DView", create_view)
    timestamps = [100.0, 200.0]
    series = compute_orbit_series(timestamps, make_states(), TimeUnit.MINUTES)
    # PlayerApp is typed against native wx controls; these tests replace them
    # with fakes, so expose the resulting test instance dynamically.
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
        render_rate_fps=render_rate_fps,
        saved_state=saved_state,
        config_path=config_path,
        initial_file_path=initial_file_path,
        oem_loaded=oem_loaded,
    )
    return player, views, canvases, frames


def test_ground_station_edits_persist_to_selected_user_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config_path = tmp_path / "play-oem.toml"
    config_path.write_text("config_version = 1\n")
    player, _views, _canvases, _frames = make_app(
        monkeypatch, config_path=config_path
    )
    station = GroundStation("station", "Site", 10.0, 20.0, 30.0)

    player._update_ground_stations([station])

    assert app.config.load_config(config_path).ground_stations == (station,)

    player._update_ground_stations([])

    loaded = app.config.load_config(config_path)
    assert loaded.ground_stations == ()
    assert loaded.ground_stations_configured


def test_ground_station_updates_refresh_open_station_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    station = GroundStation("station", "Site", 10.0, 20.0, 30.0)
    updates: list[tuple[GroundStation, ...]] = []
    monkeypatch.setattr(player, "_save_ground_stations_config", lambda: None)
    player._open_panels["ground-track"] = cast(
        Any,
        SimpleNamespace(
            view=SimpleNamespace(
                set_stations=lambda stations: updates.append(tuple(stations))
            )
        ),
    )
    player._open_panels["ground-station-passes"] = cast(
        Any,
        SimpleNamespace(
            view=SimpleNamespace(
                set_stations=lambda stations: updates.append(tuple(stations))
            )
        ),
    )

    player._update_ground_stations([station])
    player._update_ground_stations([])

    assert updates == [(station,), (station,), (), ()]


def test_legacy_saved_panel_names_open_focused_station_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    opened: list[str] = []
    monkeypatch.setattr(
        player,
        "_open_view",
        lambda name, _create_view, **_kwargs: opened.append(name),
    )

    player.open_panel_view("ground-station-access", "legacy-access")
    player.open_panel_view("ground-station-passes", "legacy-passes")

    assert opened == ["elevation-profile", "pass-list"]


def test_pass_ground_track_panel_refresh_uses_new_source_and_shared_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    first_source = GroundTrackSource.from_samples(
        [0.0, 10.0], np.zeros((2, 6)), [0, 0], "EARTH", "ITRF"
    )
    second_source = GroundTrackSource.from_samples(
        [10.0, 20.0], np.ones((2, 6)), [0, 0], "EARTH", "ITRF"
    )
    created = []
    monkeypatch.setattr(
        player,
        "_open_view",
        lambda _name, create_view, **_kwargs: created.append(
            create_view(cast(Any, None))
        ),
    )
    player._ground_track_source = first_source

    player.open_pass_ground_track_view(panel_id="pass-track")
    player._ground_track_source = second_source
    player.open_pass_ground_track_view(
        panel_id="pass-track", force_replace=True
    )

    assert len(created) == 2
    assert created[0]._source is first_source
    assert created[1]._source is second_source
    assert all(
        view._access_cache is player._station_access_cache for view in created
    )
    for view in created:
        view.close()


def test_comparison_station_selection_follows_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    main = player._station_analysis_contexts["middle"]
    comparison = player._station_analysis_contexts["right"]

    main.select_station("main-station")
    main.select_interval((10.0, 20.0))
    assert comparison.selection.station_id is None

    player._set_follow_station_selection(True)
    assert comparison.selection.station_id == "main-station"
    assert comparison.selection.interval_key == (10.0, 20.0)

    main.select_interval((30.0, 40.0))
    assert comparison.selection.interval_key == (30.0, 40.0)
    player._set_follow_station_selection(False)
    main.select_interval((50.0, 60.0))
    assert comparison.selection.interval_key == (30.0, 40.0)


def test_ground_track_open_passes_callback_seeds_station_without_seeking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    station = GroundStation("station", "Site", 10.0, 20.0, 30.0)
    player._ground_stations = [station]
    monkeypatch.setattr(
        player.workspace, "select_ground_stations", lambda: None, raising=False
    )
    created: list[tuple[str, Any]] = []

    def capture_view(name, create_view, **_kwargs) -> None:
        created.append((name, create_view(cast(Any, None))))

    monkeypatch.setattr(player, "_open_view", capture_view)
    initial_time = player.clock.t_now

    player.open_ground_track_view()
    ground_track_view = created[-1][1]
    ground_track_view._select_station(station.station_id)
    ground_track_view._open_selected_station_passes()

    pass_view = created[-1][1]
    assert [name for name, _view in created] == [
        "ground-track",
        "ground-station-passes",
    ]
    assert pass_view.selected_station_id == station.station_id
    assert player.clock.t_now == initial_time
    assert not player._station_access_cache._results


def test_replacing_pass_panel_for_new_oem_retains_station_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    station = GroundStation("station", "Site", 10.0, 20.0, 30.0)
    player._ground_stations = [station]
    monkeypatch.setattr(
        player.workspace, "select_ground_stations", lambda: None, raising=False
    )
    player._open_panels["panel"] = cast(
        Any,
        SimpleNamespace(view=SimpleNamespace(selected_station_id=station.station_id)),
    )
    created: list[Any] = []

    def capture_view(_name, create_view, **_kwargs) -> None:
        created.append(create_view(cast(Any, None)))

    monkeypatch.setattr(player, "_open_view", capture_view)

    player.open_ground_station_passes_view(
        panel_id="panel",
        force_replace=True,
    )

    assert len(created) == 1
    assert created[0].selected_station_id == station.station_id


def test_focus_ground_station_pass_changes_plot_range_without_seeking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, clock=make_clock(t_now=150.0, playing=True)
    )
    initial_time = player.clock.t_now

    player._focus_ground_station_pass(120.0, 180.0)

    assert player.clock.t_now == initial_time
    assert player.plot_time_range.enabled
    assert player.plot_time_range.start == time_range.TimeRangeEndpoint(
        "fixed", 120.0
    )
    assert player.plot_time_range.end == time_range.TimeRangeEndpoint(
        "fixed", 180.0
    )


def test_open_file_dialog_accepts_lower_and_uppercase_oem_extensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog_arguments: dict[str, Any] = {}

    class FakeFileDialog:
        def __init__(self, _parent: object, **kwargs: Any) -> None:
            dialog_arguments.update(kwargs)

        def ShowModal(self) -> int:
            return app.wx.ID_CANCEL

        def Destroy(self) -> None:
            pass

    monkeypatch.setattr(app.wx, "FileDialog", FakeFileDialog)
    player, _views, _canvases, _frames = make_app(monkeypatch)

    player._on_open_file(cast(app.wx.CommandEvent, None))

    assert dialog_arguments["wildcard"] == (
        "OEM files (*.oem, *.OEM)|*.oem;*.OEM|All files (*.*)|*.*"
    )


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
    content_scroller = player._open_views["state-components"].panel.graph_scroller
    assert canvases[0].parent is content_scroller
    assert views[0].updated_times == [150.0]
    assert player._timer.interval == 40
    assert player._timer.running
    assert player.clock.t_now == 150.0
    assert player.clock.rate == -10.0
    assert player.clock.playing
    assert player.clock.loop
    assert player.workspace.progress == 0.5
    assert player.workspace.settings_content is player.control_window.settings_scroller
    assert player.control_window.state_parent is player.workspace.state_page
    assert player.workspace.state_content is player.control_window.state_scroller

    player.close()


def test_wx_timer_advances_clock_and_updates_timeline_and_views(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monotonic_time = [0.0]
    monkeypatch.setattr(app.time, "monotonic", lambda: monotonic_time[0])
    config_path = tmp_path / "play-oem.toml"
    player, views, canvases, _frames = make_app(
        monkeypatch,
        clock=make_clock(rate=10.0, playing=True),
        config_path=config_path,
    )
    player.start()
    player.control_window.callbacks["render_rate"](1)
    assert player._timer.interval == 1000
    # Timer dispatch must preserve exact ten-second steps at 1 FPS and 10x speed.
    for expected_time in (110.0, 120.0, 130.0):
        monotonic_time[0] += 1.0
        player._on_timer(SimpleNamespace())
        assert player.clock.t_now == expected_time
        assert all(view.updated_times[-1] == expected_time for view in views)

    assert player.workspace.progress == pytest.approx(0.3)
    assert player.workspace.current_utc
    assert player.workspace.playback_state == (True, 10.0)
    assert all(canvas.draw_idle_count == 4 for canvas in canvases)

    # Changing FPS while playing updates both cadence and simulated step size.
    player.control_window.callbacks["render_rate"](2)
    monotonic_time[0] += 0.5
    player._on_timer(SimpleNamespace())
    assert player._timer.interval == 500
    assert player.clock.t_now == 135.0

    assert not config_path.exists()
    player.close()
    assert app.config.load_config(config_path).render_rate_fps == 2


def test_start_moves_focus_out_of_settings_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)

    player.start()

    assert player.workspace.neutral_focus_count == 1
    player.close()


def test_interpolation_settings_update_cursor_and_save_to_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_path = tmp_path / "play-oem.toml"
    player, _views, _canvases, _frames = make_app(monkeypatch, config_path=config_path)

    player.control_window.callbacks["interpolation"](False, "lagrange", 3)

    assert player._interpolation_config_dirty
    assert player.cursor._interpolators
    assert player.control_window.active_interpolation == "Lagrange, degree 3 (Settings)"
    player.close()

    config = app.config.load_config(config_path)
    assert not config.use_oem_interpolation
    assert config.interpolation_method == "lagrange"
    assert config.interpolation_degree == 3


def test_active_interpolation_summary_identifies_oem_metadata_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, config_path=tmp_path / "play-oem.toml"
    )
    player._oem_interpolation = "Lagrange"
    player._oem_interpolation_degree = 5

    player.control_window.callbacks["interpolation"](True, "hermite", 5)

    assert player.control_window.active_interpolation == (
        "Lagrange, degree 5 (OEM metadata)"
    )
    player.close()


def test_explicit_render_rate_is_not_reconstructed_from_rounded_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch,
        tick_interval_ms=34,
        render_rate_fps=30,
    )

    assert player._render_rate_fps == 30

    player.close()


def test_playback_pause_state_updates_when_playback_reaches_an_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_time = [0.0]
    monkeypatch.setattr(app.time, "monotonic", lambda: monotonic_time[0])
    player, _views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("state-components",),
        clock=make_clock(t_now=199.5, playing=True),
        tick_interval_ms=1000,
    )

    player.start()
    monotonic_time[0] += 1.0
    player._on_timer(SimpleNamespace())

    assert player.clock.t_now == 200.0
    assert not player.clock.playing
    assert player.workspace.playback_state == (False, 1.0)
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
        panel_management,
        "FigureCanvasWxAgg",
        lambda _parent, _id, figure: FigureCanvasAgg(figure),
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


def test_slow_redraw_skips_frames_and_catches_up_the_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_values = iter((0.0, 0.05, 0.09, 0.16))
    monkeypatch.setattr(app.time, "monotonic", lambda: next(monotonic_values))
    player, views, canvases, _frames = make_app(
        monkeypatch,
        plots=("trajectory-3d",),
        clock=make_clock(playing=True),
        tick_interval_ms=50,
    )
    player.start()
    canvas = canvases[0]
    assert canvas.toolbar is not None

    player._on_timer(SimpleNamespace())
    player._on_timer(SimpleNamespace())
    player._on_timer(SimpleNamespace())

    assert player.clock.t_now == pytest.approx(100.15)
    # The callback at 0.09 s misses a frame deadline and is skipped; the 0.16 s
    # callback consumes the two elapsed periods in one step and redraws once.
    assert views[0].updated_times == pytest.approx([100.0, 100.05, 100.15])
    assert canvas.draw_idle_count == 3
    player.close()


def test_time_entry_changes_clock_only_for_valid_in_range_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)

    player.workspace.callbacks["seek_to_time"]("not-a-time")
    assert player.clock.t_now == 100.0
    assert player.workspace.time_errors

    player.workspace.callbacks["seek_to_time"]("10s")
    assert player.clock.t_now == 110.0
    assert not player.workspace.time_errors

    utc_timestamp = tt_s_to_datetime(150.0).isoformat().replace("+00:00", "Z")
    player.workspace.callbacks["seek_to_time"](utc_timestamp)
    assert player.clock.t_now == pytest.approx(150.0)

    player.workspace.callbacks["seek_to_time"]("1000s")
    assert player.clock.t_now == pytest.approx(150.0)
    assert player.workspace.time_errors

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
    assert opened.panel.parent is player.workspace.main_analysis_stack
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
    assert canvas.toolbar is not None
    click_event = SimpleNamespace(
        button=MouseButton.LEFT,
        inaxes=SimpleNamespace(name="rectilinear"),
        xdata=1.0,
    )

    canvas.emit("button_press_event", click_event)

    assert player.clock.t_now == 160.0
    assert views[0].updated_times == [100.0, 160.0]
    assert player.workspace.current_utc

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


def test_controller_owns_one_clock_dispatch_and_hidden_panels_catch_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(monkeypatch, plots=("speed-altitude",))
    player.start()
    opened = next(iter(player._open_panels.values()))
    shown = [True]
    monkeypatch.setattr(
        player.workspace,
        "is_graph_panel_visible",
        lambda _panel: shown[0],
        raising=False,
    )
    monkeypatch.setattr(
        player.workspace,
        "queue_graph_redraw",
        lambda _panel: None,
        raising=False,
    )

    assert len(player.clock._observers) == 1
    player.open_panel_view("speed-altitude", "duplicate")
    assert len(player.clock._observers) == 1
    player.clock.seek(150.0)
    assert views[0].updated_times[-1] == 150.0

    shown[0] = False
    player.clock.seek(160.0)
    player.clock.seek(170.0)
    assert views[0].updated_times[-1] == 150.0
    assert opened.pending_time_s == 170.0
    shown[0] = True
    player._sync_open_panel(opened.panel_id)
    assert views[0].updated_times[-1] == 170.0
    assert opened.pending_time_s is None

    player.close_panel("duplicate")
    assert len(player.clock._observers) == 1
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
    assert right_duplicate.panel.parent is player.workspace.comparison_stack
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


def test_reloading_oem_replaces_views_without_removing_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude", "state-components", "rtn"),
    )
    player.start()
    old_clock = player.clock
    player._apply_playback_bounds(120.0, 180.0)
    player._apply_plot_time_range(
        app.time_range.PlotTimeRange(
            True,
            app.time_range.TimeRangeEndpoint("fixed", 130.0),
            app.time_range.TimeRangeEndpoint("fixed", 170.0),
        )
    )
    original_panels = tuple(player.workspace.graph_panels)
    original_views = tuple(player._open_panels.values())
    monkeypatch.setattr(
        player.workspace, "update_oem_information", lambda *_args: None, raising=False
    )
    monkeypatch.setattr(
        player.workspace,
        "remove_graph_panel",
        lambda *_args, **_kwargs: pytest.fail("reload must keep graph panels in place"),
    )
    loaded = app.playback_data.PlaybackData(
        clock=make_clock(t_now=100.0),
        series=player.series,
        time_unit=TimeUnit.MINUTES,
        cursor=OemCursor((100.0, 200.0), make_states()),
        object_name="RELOADED",
        frame_context="GCRF / Earth",
        dashboard_context={},
        metadata_details=(),
        source_sample_count=2,
    )
    loaded.clock.set_playback_bounds(100.0, 180.0)
    # Keep the existing clock-subscription assertions focused on replacement.
    for view in views:
        view.updated_times[:] = [100.0]

    player._replace_playback_data(loaded)

    assert player.clock is loaded.clock
    assert (player.clock.playback_start, player.clock.playback_end) == (100.0, 200.0)
    assert player.plot_time_range == app.time_range.PlotTimeRange(
        True,
        app.time_range.TimeRangeEndpoint("follow", 0.0),
        app.time_range.TimeRangeEndpoint("follow", 0.0),
    )
    assert len(player.workspace.graph_panels) == len(original_panels)
    assert all(panel.destroyed for panel in original_panels)
    assert all(view.view.closed for view in original_views)
    assert all(
        refreshed.panel_id == original.panel_id
        for refreshed, original in zip(player._open_panels.values(), original_views)
    )
    old_clock.seek(150.0)
    assert all(view.updated_times == [100.0] for view in views[:3])
    player.clock.seek(150.0)
    assert all(view.updated_times == [100.0, 150.0] for view in views[3:])
    player.close()


def test_failed_oem_load_retains_session_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    player._apply_playback_bounds(120.0, 180.0)
    applied_plot_range = app.time_range.PlotTimeRange(
        True,
        app.time_range.TimeRangeEndpoint("fixed", 130.0),
        app.time_range.TimeRangeEndpoint("fixed", 170.0),
    )
    player._apply_plot_time_range(applied_plot_range)
    clock_before = player.clock
    player._on_open_file_callback = lambda _path: (_ for _ in ()).throw(
        ValueError("invalid OEM")
    )

    player._load_oem_file("broken.oem")

    assert player.clock is clock_before
    assert (player.clock.playback_start, player.clock.playback_end) == (120.0, 180.0)
    assert player.plot_time_range == applied_plot_range
    player.close()


def test_incremental_replacement_keeps_old_oem_until_first_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch, plots=("speed-altitude",))
    old_clock = player.clock
    source = tmp_path / "replacement.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = REPLACEMENT\n"
        "OBJECT_ID = 2026-001A\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n",
        encoding="utf-8",
    )

    player._load_oem_file(str(source))
    assert player.clock is old_clock
    assert player.object_name == "TEST"

    session = player._incremental_loader.session
    assert session is not None
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        player._poll_incremental_load()
        if session.finished and not session._events.qsize():
            break
        time.sleep(0.005)

    assert player.clock is not old_clock
    assert player.object_name == "REPLACEMENT"
    assert player._current_oem_path == app.normalize_recent_path(str(source))
    assert player._recent_oem_paths[0] == app.normalize_recent_path(str(source))
    player.close()


def test_start_shows_workspace_before_initial_oem_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    source = tmp_path / "initial.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = INITIAL\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n",
        encoding="utf-8",
    )
    player, _views, _canvases, frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
        initial_file_path=str(source),
        oem_loaded=False,
    )
    assert player.object_name == "TEST"
    assert not frames[0].shown
    assert str(source) not in player._recent_oem_paths

    player.start()
    assert frames[0].shown
    session = player._incremental_loader.session
    assert session is not None
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        player._poll_incremental_load()
        if session.finished and not session._events.qsize():
            break
        time.sleep(0.005)

    assert player.object_name == "INITIAL"
    assert str(source) in player._recent_oem_paths
    player.close()


def test_failed_incremental_replacement_leaves_current_oem_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch, plots=("speed-altitude",))
    old_clock = player.clock
    bad_source = tmp_path / "bad.oem"
    bad_source.write_text("CCSDS_OEM_VERS = 2.0\nCOVARIANCE_STOP\n", encoding="utf-8")

    player._load_oem_file(str(bad_source))
    session = player._incremental_loader.session
    assert session is not None
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        player._poll_incremental_load()
        if session.finished and not session._events.qsize():
            break
        time.sleep(0.005)

    assert player.clock is old_clock
    assert player.object_name == "TEST"
    assert "Could not open OEM" in player.status_bar.message
    player.close()


def test_incremental_batches_extend_clock_and_complete_full_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    player, _views, _canvases, _frames = make_app(
        monkeypatch, plots=("speed-altitude",)
    )
    player._incremental_loader = app.IncrementalLoader(batch_size=1)
    source = tmp_path / "growing.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = GROWING\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n"
        "2026-01-01T00:00:20 7000 2 0 0 7.5 0\n",
        encoding="utf-8",
    )
    player._load_oem_file(str(source))
    session = player._incremental_loader.session
    assert session is not None
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        player._poll_incremental_load()
        if session.finished and not session._events.qsize():
            break
        time.sleep(0.005)

    assert player._oem_coverage_complete
    assert player._incremental_store is not None
    assert player._incremental_store.source_sample_count == 3
    assert player.clock.t_end == player._incremental_store.timestamps_s[-1]
    assert player._dashboard_context["sample_count"] == "3"
    assert not player._incremental_view_refresh_pending
    player.close()


def test_completed_incremental_refresh_keeps_large_plot_data_downsampled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    sample_count = app.INCREMENTAL_PLOT_MAX_SAMPLES + 1
    timestamps_s = np.arange(100.0, 100.0 + sample_count)
    state = np.array([7_000_000.0, 0.0, 0.0, 0.0, 7_500.0, 0.0])
    full_series = app.series.compute_orbit_series(
        timestamps_s.tolist(),
        [state] * sample_count,
        player.time_unit,
    )
    player.series = full_series
    player._incremental_store = object()
    player._oem_coverage_complete = True
    player._plots = ()
    displayed_series = []
    player.open_plots = lambda _plots: displayed_series.append(player.series)
    monkeypatch.setattr(app.wx, "CallAfter", lambda *_args: None)

    player._refresh_incremental_views(force=True)

    assert len(displayed_series) == 1
    assert len(displayed_series[0].elapsed_time) <= app.INCREMENTAL_PLOT_MAX_SAMPLES
    assert player.series is full_series
    player.close()


def test_incremental_panel_data_update_reuses_view_and_canvas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    calls = []

    class UpdatableView:
        def update_data(self, orbit_series, time_unit):
            calls.append(("data", orbit_series, time_unit))
            return True

        def set_time_range(self, bounds, coverage):
            calls.append(("range", bounds, coverage))

        def update(self, time_s):
            calls.append(("cursor", time_s))

    view = UpdatableView()
    canvas = FakeCanvas(None, 0, None)
    opened = SimpleNamespace(
        view=view,
        canvas=canvas,
        panel=SimpleNamespace(),
        applied_range=None,
        applied_coverage=None,
        range_initialized=False,
    )
    player._open_panels["incremental"] = opened

    assert player._update_incremental_panel_data("incremental")

    assert opened.view is view
    assert opened.canvas is canvas
    assert opened.range_initialized
    assert calls[0][0] == "data"
    assert calls[0][1] is player.series
    assert calls[0][2] is player.time_unit
    assert calls[1][0] == "range"
    assert calls[2] == ("cursor", player.clock.t_now)
    assert canvas.draw_idle_count == 1
    player._open_panels.pop("incremental")
    player.close()


def test_incremental_load_preserves_and_restores_saved_file_ranges(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from ephem_toolkit.play_oem.saved_state import RecentFileSettings

    source = tmp_path / "range-restore.oem"
    source.write_text(
        "CCSDS_OEM_VERS = 2.0\n"
        "META_START\n"
        "OBJECT_NAME = RANGE RESTORE\n"
        "CENTER_NAME = EARTH\n"
        "REF_FRAME = GCRF\n"
        "TIME_SYSTEM = UTC\n"
        "START_TIME = 2025-12-31T23:59:00\n"
        "STOP_TIME = 2026-01-01T00:01:00\n"
        "META_STOP\n"
        "2026-01-01T00:00:00 7000 0 0 0 7.5 0\n"
        "2026-01-01T00:00:10 7000 1 0 0 7.5 0\n"
        "2026-01-01T00:00:20 7000 2 0 0 7.5 0\n",
        encoding="utf-8",
    )
    start_s = datetime_to_tt_s(datetime(2026, 1, 1, tzinfo=timezone.utc))
    playback_range = (start_s + 5.0, start_s + 15.0)
    plot_range = time_range.PlotTimeRange(
        True,
        time_range.TimeRangeEndpoint("fixed", start_s + 2.0),
        time_range.TimeRangeEndpoint("fixed", start_s + 18.0),
    )
    path = app.normalize_recent_path(source)
    saved_state = app.SavedAppState(
        recent_files=[path],
        recent_file_settings={
            path: RecentFileSettings(playback_range, plot_range)
        },
    )
    monkeypatch.setattr(app, "save_saved_state", lambda _state: None)
    player, _views, _canvases, _frames = make_app(
        monkeypatch,
        plots=("speed-altitude",),
        saved_state=saved_state,
        oem_loaded=False,
    )
    player._incremental_loader = app.IncrementalLoader(batch_size=1)
    player._load_oem_file(str(source))
    session = player._incremental_loader.session
    assert session is not None

    deadline = time.monotonic() + 3.0
    while not player._active_load_first_batch and time.monotonic() < deadline:
        player._poll_incremental_load()
        time.sleep(0.005)
    assert player._active_load_first_batch
    assert player._slider_bounds == (
        datetime_to_tt_s(datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)),
        datetime_to_tt_s(datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)),
    )
    assert player._playback_handle_bounds == playback_range
    assert (player.clock.playback_start, player.clock.playback_end) != playback_range
    assert player.workspace.time_range_controls[2] == plot_range
    assert player.workspace.time_range_controls[-1] == playback_range
    player._save_current_playback_range()
    assert saved_state.recent_file_settings[path].playback_range == playback_range
    assert player.plot_time_range == plot_range

    while time.monotonic() < deadline:
        player._poll_incremental_load()
        if session.finished and not session._events.qsize():
            break
        time.sleep(0.005)
    assert player._oem_coverage_complete
    assert (player.clock.playback_start, player.clock.playback_end) == playback_range
    assert player.plot_time_range == plot_range
    player.close()


def test_ground_station_preview_is_limited_to_plot_range_until_coverage_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player, _views, _canvases, _frames = make_app(monkeypatch)
    timestamps_s = np.asarray([100.0, 120.0, 140.0, 160.0, 180.0, 200.0])
    states_m = np.repeat(make_states()[0][None, :], len(timestamps_s), axis=0)
    source = GroundTrackSource.from_samples(
        timestamps_s,
        states_m,
        np.zeros(len(timestamps_s), dtype=int),
        "EARTH",
        "GCRF",
    )
    player._ground_track_source = source
    player.plot_time_range = time_range.PlotTimeRange(
        True,
        time_range.TimeRangeEndpoint("fixed", 130.0),
        time_range.TimeRangeEndpoint("fixed", 170.0),
    )
    player._oem_coverage_complete = False

    preview = player._ground_track_source_for_plot_range()

    assert preview is not None
    np.testing.assert_array_equal(preview.timestamps_s, [120.0, 140.0, 160.0, 180.0])
    np.testing.assert_array_equal(preview.states_m, states_m[1:5])
    player._oem_coverage_complete = True
    assert player._ground_track_source_for_plot_range() is source
    player.close()


def test_recent_file_playback_ranges_save_and_restore_on_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_path = "/tmp/first.oem"
    second_path = "/tmp/second.oem"
    first_plot_range = app.time_range.PlotTimeRange(
        True,
        app.time_range.TimeRangeEndpoint("fixed", 125.0),
        app.time_range.TimeRangeEndpoint("offset", 40.0),
    )
    second_plot_range = app.time_range.PlotTimeRange(
        False,
        app.time_range.TimeRangeEndpoint("follow", 0.0),
        app.time_range.TimeRangeEndpoint("fixed", 190.0),
    )
    saved_state = app.SavedAppState(
        recent_files=[first_path, second_path],
        recent_file_settings={
            first_path: app.RecentFileSettings((110.0, 190.0), first_plot_range),
            second_path: app.RecentFileSettings((130.0, 170.0), second_plot_range),
        },
    )
    player, _views, _canvases, _frames = make_app(
        monkeypatch,
        saved_state=saved_state,
        initial_file_path=first_path,
    )
    assert (player.clock.playback_start, player.clock.playback_end) == (110.0, 190.0)
    assert player.plot_time_range == first_plot_range
    monkeypatch.setattr(app, "save_saved_state", lambda _state: None)
    monkeypatch.setattr(
        player.workspace,
        "update_oem_information",
        lambda *_args: None,
        raising=False,
    )
    player.start()
    player._apply_playback_bounds(120.0, 180.0)
    updated_first_plot_range = app.time_range.PlotTimeRange(
        True,
        app.time_range.TimeRangeEndpoint("offset", -15.0),
        app.time_range.TimeRangeEndpoint("fixed", 195.0),
    )
    player._apply_plot_time_range(updated_first_plot_range)
    loaded = app.playback_data.PlaybackData(
        clock=make_clock(),
        series=player.series,
        time_unit=TimeUnit.MINUTES,
        cursor=OemCursor((100.0, 200.0), make_states()),
        object_name="SECOND",
        frame_context="GCRF / Earth",
        dashboard_context={},
        metadata_details=(),
        source_sample_count=2,
    )
    player._on_open_file_callback = lambda _path: loaded

    player._load_oem_file(second_path)

    assert saved_state.recent_files[:2] == [second_path, first_path]
    assert saved_state.recent_file_settings[first_path].playback_range == (
        120.0,
        180.0,
    )
    assert (player.clock.playback_start, player.clock.playback_end) == (130.0, 170.0)
    assert player.plot_time_range == second_plot_range
    assert saved_state.recent_file_settings[first_path].plot_range == (
        updated_first_plot_range
    )
    player._save_application_state(save_geometry=False)
    assert saved_state.recent_file_settings[second_path].playback_range == (
        130.0,
        170.0,
    )
    assert saved_state.recent_file_settings[second_path].plot_range == (
        second_plot_range
    )
    player.close()


def test_window_position_is_restored_clamped_and_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDisplay:
        @staticmethod
        def GetCount() -> int:
            return 1

        def __init__(self, _index: int) -> None:
            pass

        def GetClientArea(self):
            return SimpleNamespace(x=0, y=0, width=1920, height=1080)

    monkeypatch.setattr(app.wx, "Display", FakeDisplay)
    monkeypatch.setattr(app, "save_saved_state", lambda _state: None)
    saved_state = app.SavedAppState(position=(1800, 900))
    player, _views, _canvases, frames = make_app(
        monkeypatch,
        saved_state=saved_state,
    )

    assert frames[0].position == (720, 280)
    assert saved_state.position == (720, 280)

    frames[0].position = (320, 140)
    player._save_application_state()

    assert saved_state.position == (320, 140)
    frames[0].position = (500, 400)
    frames[0].IsMaximized = lambda: True
    player._save_application_state()
    assert saved_state.position == (320, 140)
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
    assert empty_panel.view_name == app_support.EMPTY_GRAPH_VIEW
    assert empty_panel.panel.selected_view == app_support.EMPTY_GRAPH_VIEW
    assert empty_panel.panel.view_choices[0] == (
        app_support.EMPTY_GRAPH_VIEW,
        app_support.EMPTY_GRAPH_LABEL,
    )
    assert empty_panel.panel.view_choices == (
        (app_support.EMPTY_GRAPH_VIEW, app_support.EMPTY_GRAPH_LABEL),
        *VIEW_LABELS,
    )
    assert empty_panel.panel.native_content.label == "Select a graph view above"

    empty_panel.panel.on_view_selected("rtn")
    rtn_panel = player._open_panels[empty_panel.panel_id]
    assert empty_panel.panel.destroyed
    assert rtn_panel.view_name == "rtn"
    assert player.workspace.graph_panels.index(rtn_panel.panel) == 1

    rtn_panel.panel.on_view_selected(app_support.EMPTY_GRAPH_VIEW)
    empty_again = player._open_panels[empty_panel.panel_id]
    assert views[-1].closed
    assert empty_again.view_name == app_support.EMPTY_GRAPH_VIEW
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
    monkeypatch.setattr(view_factory.rtn, "RtnDeltaView", lambda *_args: failed_view)
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
    signal_handlers: list[Any] = []
    previous_handler = object()
    scheduled: list[tuple[Any, tuple[Any, ...]]] = []
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
        assert scheduled[-1] == (player.close, ())
        scheduled[-1][0](*scheduled[-1][1])

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
    monkeypatch.setattr(app, "PlaybackStatusBar", FakePlaybackStatusBar)
    monkeypatch.setattr(app.wx, "MenuBar", FakeMenuBar)
    monkeypatch.setattr(app.wx, "Menu", FakeMenu)
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
